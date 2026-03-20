from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, Response
from app.llm.grounded_answer import generate_grounded_answer, stream_grounded_answer
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
from app.observability.app_insights import init_app_insights
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


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):

    request_id = getattr(request.state, "request_id", None)
    backend = settings.retrieval_backend

    t_total0 = time.perf_counter()

    llm_ms = 0
    retrieval_ms = 0
    embed_ms = 0
    search_ms = 0
    #refused = False

    citations: list[Citation] = []
    tool_calls_out: list[ToolCall] = []
    agent_tool_calls_raw: list[dict] = []

    try:

        # ----------------------------------
        # Tool-first agent path
        # ----------------------------------

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
                retrieval_ms=0,
                llm_ms=0,
                total_ms=total_ms,
                top_k=0,
                top_chunks=[],
                answer_len=len(answer),
                citations_count=0,
                **summarize_tool_calls(agent_tool_calls_raw),
            )

            return ChatResponse(
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
            )

        # ----------------------------------
        # Retrieval
        # ----------------------------------

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

        # ----------------------------------
        # Grounded answer
        # ----------------------------------

        if chunks:

            t_llm0 = time.perf_counter()

            result = generate_grounded_answer(req.message, chunks)

            llm_ms = int((time.perf_counter() - t_llm0) * 1000)

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
                citations = []
                top_chunks = []
        else:

            answer = "I don't have any indexed runbooks yet. Upload/ingest documents first."
            refused = False

        total_ms = int((time.perf_counter() - t_total0) * 1000)

        top_chunks = [
            {"doc_id": c.doc_id, "chunk_id": c.chunk_id, "score": getattr(c, "score", None)}
            for c in chunks[:5]
        ]

        log_event(
            "chat_request",
            request_id=request_id,
            retrieval_backend=backend,
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

        return ChatResponse(
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

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_stream():
        retriever = get_retriever()
        chunks = retriever.retrieve(req.message, top_k=5)

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