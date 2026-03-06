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

export interface ChatResponse {
  answer: string
  citations: Citation[]
  tool_calls: ToolCall[]
  retrieval_backend: string
  timings?: TimingInfo
  retrieved_chunks?: RetrievedChunkDebug[]
}

export interface HealthResponse {
  status: string
  app_env: string
  retrieval_backend: string
}