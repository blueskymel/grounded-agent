export interface Citation {
  doc_id: string
  chunk_id: string
  title?: string
  source_uri?: string
  score?: number
  snippet?: string
}

export interface ToolCall {
  name: string
  input: any
  output?: any
}

export interface RetrievedChunkDebug {
  doc_id: string
  chunk_id: string
  score?: number
}

export interface TimingInfo {
  retrieval_ms: number
  embed_ms: number
  search_ms: number
  llm_ms: number
  total_ms: number
}

export interface DecisionAudit {
  mode: string
  blocked_by_prompt_injection: boolean
  blocked_chunk_count: number
  raw_chunk_count: number
  safe_chunk_count: number
  displayable_citation_count: number
  max_citation_score?: number
  min_display_score?: number
  safe_min_confidence?: number
  refusal_triggered: boolean
  refusal_reason?: string
  evidence: RetrievedChunkDebug[]
}

export interface ChatResponse {
  request_id?: string
  answer: string
  citations: Citation[]
  tool_calls: ToolCall[]
  retrieval_backend: string
  timings?: TimingInfo
  retrieved_chunks?: RetrievedChunkDebug[]
  decision_audit?: DecisionAudit
}

export interface HealthResponse {
  status: string
  app_env: string
  retrieval_backend: string
}