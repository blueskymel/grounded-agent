from pydantic import BaseModel, Field
from typing import Any

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, max_length=200)


class Citation(BaseModel):
    doc_id: str
    title: str | None = None
    source_uri: str | None = None
    chunk_id: str
    score: float | None = None
    snippet: str


class ToolCall(BaseModel):
    name: str
    input: dict
    output: dict | None = None

class RetrievedChunkDebug(BaseModel):
    doc_id: str
    chunk_id: str
    score: float | None = None

class TimingInfo(BaseModel):
    retrieval_ms: int = 0
    embed_ms: int = 0
    search_ms: int = 0
    llm_ms: int = 0
    total_ms: int = 0    


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    tool_calls: list[ToolCall]
    retrieval_backend: str
    timings: TimingInfo | None = None
    retrieved_chunks: list[RetrievedChunkDebug] = []    