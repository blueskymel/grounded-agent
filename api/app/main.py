from dotenv import load_dotenv

from app.llm.grounded_answer import generate_grounded_answer
from fastapi import FastAPI
from fastapi import Request, HTTPException
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse, Citation, ToolCall
from app.retrieval.factory import get_retriever
from app.core.agent import run_agent
from app.schemas.docs import DocSummary
from app.retrieval.stats import faiss_doc_stats, azure_search_doc_stats
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
import uuid
from app.observability.logger import log_event
from app.observability.errors import format_exception
from app.observability.tools import summarize_tool_calls

load_dotenv()
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
    
LOG_FILE = LOG_DIR / "groundedagent.log"
# Root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clear existing handlers (important during reload)
logger.handlers.clear()

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)

# File handler (rotates at 5MB, keeps 3 backups)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5_000_000,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(file_handler)

# Reduce noisy SDK logs
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

app = FastAPI(title="GroundedAgent API", version="0.1.0")

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id

    t0 = time.perf_counter()
    response = await call_next(request)
    total_ms = int((time.perf_counter() - t0) * 1000)

    response.headers["x-request-id"] = request_id

    # Basic request log (we'll add chat-specific logs in /chat too)
    log_event(
        "http_request",
        request_id=request_id,
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        total_ms=total_ms,
    )
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "retrieval_backend": settings.retrieval_backend,
    }

@app.get("/kb", response_model=list[DocSummary])
def list_docs():
    if settings.retrieval_backend == "azure_search":
        return azure_search_doc_stats()

    return faiss_doc_stats()

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    refusal_reason = None
    request_id = getattr(request.state, "request_id", None)
    backend = settings.retrieval_backend

    t_total0 = time.perf_counter()

    # Defaults
    llm_ms = 0
    refused = False
    retrieval_ms = 0
    embed_ms = 0
    search_ms = 0
    citations: list[Citation] = []
    tool_calls_out: list[ToolCall] = []
    agent_tool_calls_raw: list[dict] = []
    chunks = []

    try:
        # ---- Agent / tool path FIRST (avoid retrieval coupling/cost)
        agent_result = run_agent(req.message, backend)

        if getattr(agent_result, "tool_calls", None):
            agent_tool_calls_raw = agent_result.tool_calls
            tool_calls_out = [
                ToolCall(name=t["name"], input=t["input"], output=t.get("output"))
                for t in agent_result.tool_calls
            ]

            answer = agent_result.answer

            REFUSAL_TEXT = "I don't have enough information in the provided runbooks to answer that."
            if answer.strip() == REFUSAL_TEXT:
                refused = True
                refusal_reason = "insufficient_evidence_or_policy"

            total_ms = int((time.perf_counter() - t_total0) * 1000)

            log_event(
                "chat_request",
                request_id=request_id,
                retrieval_backend=backend,
                question_preview=(req.message[:120] + "…") if len(req.message) > 120 else req.message,
                question_len=len(req.message),
                retrieval_ms=0,
                llm_ms=0,
                embed_ms=0,
                search_ms=0,
                total_ms=total_ms,
                top_k=0,
                top_chunks=[],
                refused=refused,
                refusal_reason=refusal_reason,
                answer_len=len(answer),
                citations_count=0,
                **summarize_tool_calls(agent_tool_calls_raw),
            )

            return ChatResponse(
                answer=answer,
                citations=[],
                tool_calls=tool_calls_out,
                retrieval_backend=backend,
            )

        # ---- Retrieval + grounded answer path
        retriever = get_retriever()

        chunks = retriever.retrieve(req.message, top_k=5)

        embed_ms = getattr(retriever, "last_embed_ms", 0) or 0
        search_ms = getattr(retriever, "last_search_ms", 0) or 0
        retrieval_ms = embed_ms + search_ms

        citations = [
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

        if chunks:
            t_llm0 = time.perf_counter()
            result = generate_grounded_answer(req.message, chunks)
            llm_ms = int((time.perf_counter() - t_llm0) * 1000)

            answer = result.answer
            refused = bool(getattr(result, "is_refusal", False))
        else:
            answer = "I don't have any indexed runbooks yet. Upload/ingest documents first."
            refused = False

        # ---- Refusal: clear citations for honest UX
        REFUSAL_TEXT = "I don't have enough information in the provided runbooks to answer that."
        if answer.strip() == REFUSAL_TEXT:
            citations = []
            refused = True
            if not chunks:
                refusal_reason = "no_documents"
            elif "sla" in req.message.lower():
                refusal_reason = "sla_term_not_defined"
            else:
                refusal_reason = "insufficient_evidence_or_policy"

        total_ms = int((time.perf_counter() - t_total0) * 1000)

        top_chunks = [
            {"doc_id": c.doc_id, "chunk_id": c.chunk_id, "score": getattr(c, "score", None)}
            for c in chunks[:5]
        ]

        log_event(
            "chat_request",
            request_id=request_id,
            retrieval_backend=backend,
            question_preview=(req.message[:120] + "…") if len(req.message) > 120 else req.message,
            question_len=len(req.message),
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            embed_ms=embed_ms,
            search_ms=search_ms,
            total_ms=total_ms,
            top_k=len(chunks),
            top_chunks=top_chunks,
            refused=refused,
            refusal_reason=refusal_reason,
            answer_len=len(answer),
            citations_count=len(citations),
            **summarize_tool_calls([]),
        )

        return ChatResponse(
            answer=answer,
            citations=citations,
            tool_calls=[],
            retrieval_backend=backend,
        )

    except Exception as e:
        total_ms = int((time.perf_counter() - t_total0) * 1000)
        log_event(
            "chat_error",
            request_id=request_id,
            retrieval_backend=backend,
            total_ms=total_ms,
            error=format_exception(e),
        )
        raise HTTPException(status_code=500, detail="Internal server error")

        # ---- Grounded answer path
        if chunks:
            t_llm0 = time.perf_counter()
            result = generate_grounded_answer(req.message, chunks)
            llm_ms = int((time.perf_counter() - t_llm0) * 1000)

            answer = result.answer
            refused = bool(getattr(result, "is_refusal", False))
        else:
            answer = "I don't have any indexed runbooks yet. Upload/ingest documents first."
            refused = False

        # ---- Refusal: clear citations for honest UX
        REFUSAL_TEXT = "I don't have enough information in the provided runbooks to answer that."
        if answer.strip() == REFUSAL_TEXT:
            citations = []
            refused = True
            if not chunks:
                refusal_reason = "no_documents"
            elif "sla" in req.message.lower():
                refusal_reason = "sla_term_not_defined"
            else:
                refusal_reason = "insufficient_evidence_or_policy"

        total_ms = int((time.perf_counter() - t_total0) * 1000)

        top_chunks = [
            {"doc_id": c.doc_id, "chunk_id": c.chunk_id, "score": getattr(c, "score", None)}
            for c in chunks[:5]
        ]

        log_event(
            "chat_request",
            request_id=request_id,
            retrieval_backend=backend,
            question_preview=(req.message[:120] + "…") if len(req.message) > 120 else req.message,
            question_len=len(req.message),
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            total_ms=total_ms,
            top_k=len(chunks),
            top_chunks=top_chunks,
            refused=refused,
            answer_len=len(answer),
            citations_count=len(citations),
            **summarize_tool_calls(agent_tool_calls_raw),
        )

        return ChatResponse(
            answer=answer,
            citations=citations,
            tool_calls=[],
            retrieval_backend=backend,
        )

    except Exception as e:
        total_ms = int((time.perf_counter() - t_total0) * 1000)
        log_event(
            "chat_error",
            request_id=request_id,
            retrieval_backend=backend,
            total_ms=total_ms,
            error=format_exception(e),
        )
        raise HTTPException(status_code=500, detail="Internal server error")