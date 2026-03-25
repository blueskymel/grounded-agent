from __future__ import annotations

import time
import uuid
from dataclasses import asdict, is_dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from app.core.agent import run_agent
from app.core.config import settings
from app.llm.grounded_answer import generate_grounded_answer
from app.observability.errors import format_exception
from app.observability.logger import log_event
from app.observability.tools import summarize_tool_calls
from app.observability.tracing import trace_step
from app.retrieval.factory import get_retriever
from app.retrieval.stats import azure_search_doc_stats, faiss_doc_stats
from app.security.prompt_injection import (
    PROMPT_INJECTION_REFUSAL,
    check_user_message_for_prompt_injection,
    filter_retrieved_chunks_for_prompt_injection,
)
from app.schemas.chat import ChatRequest, Citation, ToolCall


mcp = FastMCP("grounded-agent")


def _build_response(
    *,
    ok: bool,
    request_id: str,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    total_ms: int = 0,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "request_id": request_id,
        "timings": {"total_ms": total_ms},
        "data": data if data is not None else {},
        "error": error,
    }


def _map_error_code(exc: Exception) -> str:
    exc_type = type(exc).__name__.lower()
    if "validation" in exc_type:
        return "validation_error"
    if "timeout" in exc_type:
        return "timeout_error"
    return "internal_error"


def _serialize_doc(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if is_dataclass(item):
        return asdict(item)
    if isinstance(item, dict):
        return item
    # Last-resort best effort for simple objects used in tests/mocks.
    return dict(getattr(item, "__dict__", {}))


def _build_rag_response(message: str, tenant_id: str) -> dict[str, Any]:
    retriever = get_retriever()
    with trace_step("mcp.retrieval.search"):
        try:
            chunks = retriever.retrieve(message, top_k=5, tenant_id=tenant_id)
        except TypeError:
            chunks = retriever.retrieve(message, top_k=5)

    raw_chunk_count = len(chunks)
    chunks, _ = filter_retrieved_chunks_for_prompt_injection(chunks)

    if not chunks:
        if raw_chunk_count > 0:
            return {
                "answer": PROMPT_INJECTION_REFUSAL,
                "citations": [],
                "tool_calls": [],
                "retrieval_backend": settings.retrieval_backend,
            }
        return {
            "answer": "I don't have any indexed runbooks yet. Upload/ingest documents first.",
            "citations": [],
            "tool_calls": [],
            "retrieval_backend": settings.retrieval_backend,
        }

    with trace_step("mcp.llm.answer"):
        result = generate_grounded_answer(message, chunks)

    if hasattr(result, "answer"):
        answer = result.answer
        refused = bool(getattr(result, "is_refusal", False))
    elif isinstance(result, dict):
        answer = result.get("answer", "")
        refused = bool(result.get("refused", False) or result.get("is_refusal", False))
    else:
        answer = str(result)
        refused = False

    citations: list[Citation] = []
    if not refused:
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

    return {
        "answer": answer,
        "citations": [c.model_dump() for c in citations],
        "tool_calls": [],
        "retrieval_backend": settings.retrieval_backend,
    }


def _chat_impl(message: str, tenant_id: str) -> dict[str, Any]:
    with trace_step("mcp.agent.plan"):
        agent_result = run_agent(message, settings.retrieval_backend)

    if getattr(agent_result, "tool_calls", None):
        tool_calls = [
            ToolCall(name=t["name"], input=t["input"], output=t.get("output")).model_dump()
            for t in agent_result.tool_calls
        ]
        return {
            "answer": agent_result.answer,
            "citations": [],
            "tool_calls": tool_calls,
            "retrieval_backend": settings.retrieval_backend,
        }

    return _build_rag_response(message, tenant_id=tenant_id)


@mcp.tool(
    description=(
        "Chat with GroundedAgent. Runs tool-first routing first, then falls back to grounded retrieval "
        "with citations."
    )
)
def chat(message: str, tenant_id: str | None = None) -> dict:
    """GroundedAgent MCP entrypoint."""
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    resolved_tenant_id = (tenant_id or settings.default_tenant_id).strip() or settings.default_tenant_id

    try:
        # Reuse API schema rules so MCP and HTTP enforce the same constraints.
        ChatRequest(message=message)

        pi_check = check_user_message_for_prompt_injection(message)
        if pi_check.blocked:
            total_ms = int((time.perf_counter() - t0) * 1000)
            data = {
                "answer": PROMPT_INJECTION_REFUSAL,
                "citations": [],
                "tool_calls": [],
                "retrieval_backend": settings.retrieval_backend,
            }
            log_event(
                "mcp_chat_blocked_prompt_injection",
                request_id=request_id,
                retrieval_backend=settings.retrieval_backend,
                tenant_id=resolved_tenant_id,
                total_ms=total_ms,
                signals=pi_check.matched_signals,
            )
            return _build_response(ok=True, request_id=request_id, data=data, total_ms=total_ms)

        data = _chat_impl(message, tenant_id=resolved_tenant_id)
        total_ms = int((time.perf_counter() - t0) * 1000)

        tool_calls = data.get("tool_calls", [])
        log_event(
            "mcp_chat",
            request_id=request_id,
            retrieval_backend=settings.retrieval_backend,
            tenant_id=resolved_tenant_id,
            total_ms=total_ms,
            answer_len=len(str(data.get("answer", ""))),
            citations_count=len(data.get("citations", [])),
            **summarize_tool_calls(tool_calls),
        )

        return _build_response(ok=True, request_id=request_id, data=data, total_ms=total_ms)
    except ValidationError as exc:
        total_ms = int((time.perf_counter() - t0) * 1000)
        err = {
            "code": _map_error_code(exc),
            "message": "Invalid request payload.",
            "details": exc.errors(),
        }
        log_event(
            "mcp_chat_error",
            request_id=request_id,
            retrieval_backend=settings.retrieval_backend,
            tenant_id=resolved_tenant_id,
            total_ms=total_ms,
            error=err,
        )
        return _build_response(ok=False, request_id=request_id, error=err, total_ms=total_ms)
    except Exception as exc:
        total_ms = int((time.perf_counter() - t0) * 1000)
        err = {
            "code": _map_error_code(exc),
            "message": "Internal server error.",
            "details": format_exception(exc),
        }
        log_event(
            "mcp_chat_error",
            request_id=request_id,
            retrieval_backend=settings.retrieval_backend,
            tenant_id=resolved_tenant_id,
            total_ms=total_ms,
            error=err,
        )
        return _build_response(ok=False, request_id=request_id, error=err, total_ms=total_ms)


@mcp.tool(description="GroundedAgent MCP health check.")
def health() -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    data = {
        "status": "ok",
        "app_env": settings.app_env,
        "retrieval_backend": settings.retrieval_backend,
    }
    total_ms = int((time.perf_counter() - t0) * 1000)
    log_event("mcp_health", request_id=request_id, total_ms=total_ms)
    return _build_response(ok=True, request_id=request_id, data=data, total_ms=total_ms)


@mcp.tool(description="List indexed document summaries from the active retrieval backend.")
def kb() -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()

    try:
        if settings.retrieval_backend == "azure_search":
            docs = azure_search_doc_stats()
        else:
            docs = faiss_doc_stats()

        data = {
            "retrieval_backend": settings.retrieval_backend,
            "documents": [_serialize_doc(d) for d in docs],
        }
        total_ms = int((time.perf_counter() - t0) * 1000)
        log_event(
            "mcp_kb",
            request_id=request_id,
            retrieval_backend=settings.retrieval_backend,
            total_ms=total_ms,
            doc_count=len(docs),
        )
        return _build_response(ok=True, request_id=request_id, data=data, total_ms=total_ms)
    except Exception as exc:
        total_ms = int((time.perf_counter() - t0) * 1000)
        err = {
            "code": _map_error_code(exc),
            "message": "Failed to fetch knowledge base stats.",
            "details": format_exception(exc),
        }
        log_event(
            "mcp_kb_error",
            request_id=request_id,
            retrieval_backend=settings.retrieval_backend,
            total_ms=total_ms,
            error=err,
        )
        return _build_response(ok=False, request_id=request_id, error=err, total_ms=total_ms)


def main() -> None:
    # stdio transport keeps this compatible with MCP clients like VS Code and Claude Desktop.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
