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

export interface ChatResponse {
  answer: string
  citations: Citation[]
  tool_calls: ToolCall[]
  retrieval_backend: string
}

export interface HealthResponse {
  status: string
  app_env: string
  retrieval_backend: string
}