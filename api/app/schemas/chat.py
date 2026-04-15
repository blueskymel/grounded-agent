from pydantic import BaseModel, Field

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


class DecisionAudit(BaseModel):
    mode: str
    blocked_by_prompt_injection: bool = False
    blocked_chunk_count: int = 0
    raw_chunk_count: int = 0
    safe_chunk_count: int = 0
    displayable_citation_count: int = 0
    max_citation_score: float | None = None
    min_display_score: float | None = None
    safe_min_confidence: float | None = None
    refusal_triggered: bool = False
    refusal_reason: str | None = None
    evidence: list[RetrievedChunkDebug] = []


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    tool_calls: list[ToolCall]
    retrieval_backend: str
    timings: TimingInfo | None = None
    retrieved_chunks: list[RetrievedChunkDebug] = []
    decision_audit: DecisionAudit | None = None