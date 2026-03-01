from app.llm.grounded_answer import generate_grounded_answer
from fastapi import FastAPI
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse, Citation, ToolCall
from app.retrieval.factory import get_retriever
from app.core.agent import run_agent

app = FastAPI(title="GroundedAgent API", version="0.1.0")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "retrieval_backend": settings.retrieval_backend,
    }

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    retriever = get_retriever()
    chunks = retriever.retrieve(req.message, top_k=5)

    citations = [
        Citation(
            doc_id=c.doc_id,
            title=c.title,
            source_uri=c.source_uri,
            chunk_id=c.chunk_id,
            score=c.score,
            snippet=c.text[:400],
        )
        for c in chunks
    ]

    agent_result = run_agent(req.message, settings.retrieval_backend)

    # If a tool ran, return tool result (agentic path)
    if agent_result.tool_calls:
        tool_calls = [
            ToolCall(name=t["name"], input=t["input"], output=t.get("output"))
            for t in agent_result.tool_calls
        ]
        return ChatResponse(
            answer=agent_result.answer,
            citations=citations,
            tool_calls=tool_calls,
            retrieval_backend=settings.retrieval_backend,
        )

    # Otherwise: retrieval + grounded answer
    if chunks:
        result = generate_grounded_answer(req.message, chunks)
        answer = result.answer
    else:
        answer = "I don't have any indexed runbooks yet. Upload/ingest documents first."

    REFUSAL_TEXT = "I don't have enough information in the provided runbooks to answer that."
    if answer.strip() == REFUSAL_TEXT:
        citations = []

    return ChatResponse(
        answer=answer,
        citations=citations,
        tool_calls=[],
        retrieval_backend=settings.retrieval_backend,
    )