from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from app.llm.grounded_answer import generate_grounded_answer, stream_grounded_answer
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse, Citation, ToolCall
from app.retrieval.factory import get_retriever
from app.core.agent import run_agent
from app.schemas.docs import DocSummary
from app.retrieval.stats import faiss_doc_stats, azure_search_doc_stats
from app.security.prompt_injection import (
    PROMPT_INJECTION_REFUSAL,
    check_user_message_for_prompt_injection,
    filter_retrieved_chunks_for_prompt_injection,
)

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
import uuid
import os

from app.observability.logger import log_event
from app.observability.errors import format_exception
from app.observability.tools import summarize_tool_calls
from app.observability.app_insights import init_app_insights
from app.observability.tracing import trace_step
from fastapi.responses import StreamingResponse
import json
import asyncio

load_dotenv()

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "groundedagent.log"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers.clear()

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5_000_000,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(file_handler)

logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# Optional telemetry export. No-op when connection string is not set.
init_app_insights(settings.applicationinsights_connection_string)

app = FastAPI(title="GroundedAgent API", version="0.1.0")
_SAFE_MIN_CITATION_CONFIDENCE = float(os.environ.get("SAFE_MIN_CITATION_CONFIDENCE", "0.95"))
_MIN_CITATION_SCORE_TO_DISPLAY = 0.25  # Filter only junk matches (very low scores); normal good matches in 0.32-0.40 range

_ALLOWED_ORIGINS = [o.strip() for o in
        (os.environ.get("CORS_ORIGINS",
            "http://localhost:4200,https://blue-pond-03f20770f.6.azurestaticapps.net")).split(",")
        if o.strip()]

app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    expose_headers=["x-request-id", "x-tenant-id"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id

    t0 = time.perf_counter()
    response = await call_next(request)
    total_ms = int((time.perf_counter() - t0) * 1000)

    response.headers["x-request-id"] = request_id

    log_event(
        "http_request",
        request_id=request_id,
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        total_ms=total_ms,
    )

    return response


@app.middleware("http")
async def add_tenant_context(request: Request, call_next):
    tenant_id = (request.headers.get("x-tenant-id") or "").strip()

    if not tenant_id:
        if settings.enforce_tenant_header:
            return Response(
                content=json.dumps({"detail": "Missing x-tenant-id header"}),
                status_code=400,
                media_type="application/json",
            )
        tenant_id = settings.default_tenant_id

    request.state.tenant_id = tenant_id
    response = await call_next(request)
    response.headers["x-tenant-id"] = tenant_id
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "retrieval_backend": settings.retrieval_backend,
    }


@app.get("/kb", response_model=list[DocSummary])
def list_docs(response: Response):
    response.headers["Cache-Control"] = "public, max-age=30"

    if settings.retrieval_backend == "azure_search":
        return azure_search_doc_stats()

    return faiss_doc_stats()


def _chat_impl(req: ChatRequest, request: Request, mode_override: str | None = None):

    request_id = getattr(request.state, "request_id", None)
    backend = settings.retrieval_backend
    tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)

    t_total0 = time.perf_counter()

    llm_ms = 0
    retrieval_ms = 0
    embed_ms = 0
    search_ms = 0
    #refused = False

    citations: list[Citation] = []
    tool_calls_out: list[ToolCall] = []
    agent_tool_calls_raw: list[dict] = []
    mode_name = mode_override or "default"
    decision_audit = {
        "mode": mode_name,
        "blocked_by_prompt_injection": False,
        "blocked_chunk_count": 0,
        "raw_chunk_count": 0,
        "safe_chunk_count": 0,
        "displayable_citation_count": 0,
        "max_citation_score": None,
        "min_display_score": _MIN_CITATION_SCORE_TO_DISPLAY,
        "safe_min_confidence": _SAFE_MIN_CITATION_CONFIDENCE,
        "refusal_triggered": False,
        "refusal_reason": None,
        "evidence": [],
    }

    try:

        # ----------------------------------
        # Prompt injection guard (direct)
        # ----------------------------------

        pi_check = check_user_message_for_prompt_injection(req.message)
        if pi_check.blocked:
            decision_audit["blocked_by_prompt_injection"] = True
            decision_audit["refusal_triggered"] = True
            decision_audit["refusal_reason"] = "prompt_injection_signals"
            total_ms = int((time.perf_counter() - t_total0) * 1000)
            log_event(
                "chat_blocked_prompt_injection",
                request_id=request_id,
                retrieval_backend=backend,
                total_ms=total_ms,
                signals=pi_check.matched_signals,
            )
            log_event(
                "chat_decision_audit",
                request_id=request_id,
                retrieval_backend=backend,
                tenant_id=tenant_id,
                decision=decision_audit,
            )
            return ChatResponse(
                request_id=request_id,
                answer=PROMPT_INJECTION_REFUSAL,
                citations=[],
                tool_calls=[],
                retrieval_backend=backend,
                timings={
                    "retrieval_ms": 0,
                    "embed_ms": 0,
                    "search_ms": 0,
                    "llm_ms": 0,
                    "total_ms": total_ms,
                },
                retrieved_chunks=[],
                decision_audit=decision_audit,
            )

        # ----------------------------------
        # Tool-first agent path
        # ----------------------------------

        with trace_step("agent.plan"):
            agent_result = run_agent(req.message, backend)

        if getattr(agent_result, "tool_calls", None):

            agent_tool_calls_raw = agent_result.tool_calls

            tool_calls_out = [
                ToolCall(name=t["name"], input=t["input"], output=t.get("output"))
                for t in agent_result.tool_calls
            ]

            answer = agent_result.answer

            total_ms = int((time.perf_counter() - t_total0) * 1000)

            log_event(
                "chat_request",
                request_id=request_id,
                retrieval_backend=backend,
                tenant_id=tenant_id,
                retrieval_ms=0,
                llm_ms=0,
                total_ms=total_ms,
                top_k=0,
                top_chunks=[],
                answer_len=len(answer),
                citations_count=0,
                **summarize_tool_calls(agent_tool_calls_raw),
            )
            decision_audit["refusal_reason"] = "tool_path_no_retrieval"
            log_event(
                "chat_decision_audit",
                request_id=request_id,
                retrieval_backend=backend,
                tenant_id=tenant_id,
                decision=decision_audit,
            )

            return ChatResponse(
                request_id=request_id,
                answer=answer,
                citations=[],
                tool_calls=tool_calls_out,
                retrieval_backend=backend,
                timings={
                    "retrieval_ms": 0,
                    "embed_ms": 0,
                    "search_ms": 0,
                    "llm_ms": 0,
                    "total_ms": total_ms,
                },
                retrieved_chunks=[],
                decision_audit=decision_audit,
            )

        # ----------------------------------
        # Retrieval
        # ----------------------------------

        retriever = get_retriever()
        t_retrieval0 = time.perf_counter()

        with trace_step("retrieval.search"):
            try:
                chunks = retriever.retrieve(req.message, top_k=5, tenant_id=tenant_id)
            except TypeError:
                chunks = retriever.retrieve(req.message, top_k=5)
        retrieval_wall_ms = int((time.perf_counter() - t_retrieval0) * 1000)
        raw_chunk_count = len(chunks)
        decision_audit["raw_chunk_count"] = raw_chunk_count
        chunks, blocked_chunk_count = filter_retrieved_chunks_for_prompt_injection(chunks)
        decision_audit["blocked_chunk_count"] = blocked_chunk_count
        decision_audit["safe_chunk_count"] = len(chunks)

        if blocked_chunk_count:
            log_event(
                "chat_filtered_prompt_injection_chunks",
                request_id=request_id,
                retrieval_backend=backend,
                tenant_id=tenant_id,
                blocked_chunk_count=blocked_chunk_count,
                safe_chunk_count=len(chunks),
            )

        embed_ms = getattr(retriever, "last_embed_ms", 0) or 0
        search_ms = getattr(retriever, "last_search_ms", 0) or 0
        retrieval_ms = embed_ms + search_ms
        if retrieval_ms == 0 and retrieval_wall_ms > 0:
            retrieval_ms = retrieval_wall_ms
        if retrieval_ms == 0 and raw_chunk_count > 0:
            retrieval_ms = 1

        # Build all citations for max_score calculation and filtering
        all_citations = [
            Citation(
                doc_id=c.doc_id,
                title=c.title,
                source_uri=c.source_uri,
                chunk_id=c.chunk_id,
                score=c.score,
                snippet=(c.text or "")[:400],
            )
            for c in chunks
        ]
        
        # Filter citations to only display strong ones (>= MIN_CITATION_SCORE_TO_DISPLAY)
        # But use all citations for refusal decision (max_score gate)
        citations = [
            c for c in all_citations
            if isinstance(c.score, (int, float)) and c.score >= _MIN_CITATION_SCORE_TO_DISPLAY
        ]
        all_citation_scores = [c.score for c in all_citations if isinstance(c.score, (int, float))]
        decision_audit["max_citation_score"] = max(all_citation_scores) if all_citation_scores else None
        decision_audit["displayable_citation_count"] = len(citations)

        # ----------------------------------
        # Grounded answer
        # ----------------------------------

        if chunks:

            t_llm0 = time.perf_counter()

            with trace_step("llm.answer"):
                result = generate_grounded_answer(req.message, chunks, mode_override=mode_override)

            llm_ms = int((time.perf_counter() - t_llm0) * 1000)
            if llm_ms == 0:
                llm_ms = 1

            # Support both GroundedResult objects and dict-returning mock mode
            if hasattr(result, "answer"):
                answer = result.answer
                refused = bool(getattr(result, "is_refusal", False))
            elif isinstance(result, dict):
                answer = result.get("answer", "")
                refused = bool(result.get("refused", False) or result.get("is_refusal", False))
            else:
                answer = str(result)
                refused = False

            if refused:
                decision_audit["refusal_triggered"] = True
                decision_audit["refusal_reason"] = "llm_refusal"
                citations = []
                top_chunks = []

            # Explicit safe endpoint hardening: only return an answer when
            # citation evidence exists and confidence is at/above threshold.
            if mode_override == "safe" and not refused:
                # Use all citations (not filtered) to calculate max score for refusal decision
                max_score = max(all_citation_scores) if all_citation_scores else 0.0
                if (not all_citation_scores) or (max_score < _SAFE_MIN_CITATION_CONFIDENCE):
                    answer = "I don't have enough information in the provided runbooks to answer that."
                    refused = True
                    decision_audit["refusal_triggered"] = True
                    decision_audit["refusal_reason"] = "safe_mode_low_citation_confidence"
                    citations = []
                    top_chunks = []
                # Note: citations list is already filtered to >= _MIN_CITATION_SCORE_TO_DISPLAY above
        elif raw_chunk_count > 0 and not chunks:

            answer = PROMPT_INJECTION_REFUSAL
            refused = True
            decision_audit["refusal_triggered"] = True
            decision_audit["refusal_reason"] = "all_retrieved_chunks_blocked_by_prompt_injection"
            citations = []
            top_chunks = []

        else:

            answer = "I don't have any indexed runbooks yet. Upload/ingest documents first."
            refused = False
            decision_audit["refusal_reason"] = "no_chunks_available"

        total_ms = int((time.perf_counter() - t_total0) * 1000)
        if total_ms == 0:
            total_ms = 1

        top_chunks = [
            {"doc_id": c.doc_id, "chunk_id": c.chunk_id, "score": getattr(c, "score", None)}
            for c in chunks[:5]
        ]
        decision_audit["evidence"] = top_chunks

        log_event(
            "chat_request",
            request_id=request_id,
            retrieval_backend=backend,
            tenant_id=tenant_id,
            retrieval_ms=retrieval_ms,
            embed_ms=embed_ms,
            search_ms=search_ms,
            llm_ms=llm_ms,
            total_ms=total_ms,
            top_k=len(chunks),
            top_chunks=top_chunks,
            answer_len=len(answer),
            citations_count=len(citations),
            **summarize_tool_calls([]),
        )
        log_event(
            "chat_decision_audit",
            request_id=request_id,
            retrieval_backend=backend,
            tenant_id=tenant_id,
            decision=decision_audit,
        )

        return ChatResponse(
            request_id=request_id,
            answer=answer,
            citations=citations,
            tool_calls=[],
            retrieval_backend=backend,
            timings={
                "retrieval_ms": retrieval_ms,
                "embed_ms": embed_ms,
                "search_ms": search_ms,
                "llm_ms": llm_ms,
                "total_ms": total_ms,
            },
            retrieved_chunks=top_chunks,
            decision_audit=decision_audit,
        )

    except Exception as e:

        total_ms = int((time.perf_counter() - t_total0) * 1000)

        log_event(
            "chat_error",
            request_id=request_id,
            retrieval_backend=backend,
            tenant_id=tenant_id,
            total_ms=total_ms,
            error=format_exception(e),
        )

        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    return _chat_impl(req, request, mode_override=None)


@app.post("/chat/before", response_model=ChatResponse)
def chat_before(req: ChatRequest, request: Request):
    return _chat_impl(req, request, mode_override="unsafe")


@app.post("/chat/after", response_model=ChatResponse)
def chat_after(req: ChatRequest, request: Request):
    return _chat_impl(req, request, mode_override="safe")

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    async def event_stream():
        pi_check = check_user_message_for_prompt_injection(req.message)
        if pi_check.blocked:
            yield f"data: {json.dumps({'type': 'token', 'value': PROMPT_INJECTION_REFUSAL})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        retriever = get_retriever()
        tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)
        with trace_step("stream.retrieval.search"):
            try:
                chunks = retriever.retrieve(req.message, top_k=5, tenant_id=tenant_id)
            except TypeError:
                chunks = retriever.retrieve(req.message, top_k=5)
        raw_chunk_count = len(chunks)
        chunks, _ = filter_retrieved_chunks_for_prompt_injection(chunks)

        if raw_chunk_count > 0 and not chunks:
            yield f"data: {json.dumps({'type': 'token', 'value': PROMPT_INJECTION_REFUSAL})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        if not chunks:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No documents'})}\n\n"
            return

        for token in stream_grounded_answer(req.message, chunks):
            yield f"data: {json.dumps({'type': 'token', 'value': token})}\n\n"
            await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )