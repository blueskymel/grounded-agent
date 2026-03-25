# Architecture Notes

## Multi-Tenant Security Patterns (SaaS Layer)

GroundedAgent enforces tenant-aware retrieval to isolate private data across tenants.

### Request Tenant Resolution

- HTTP requests resolve tenant context from `x-tenant-id` header in middleware.
- If header is missing, the system uses `default_tenant_id` (configurable).
- Optional strict mode (`enforce_tenant_header=true`) rejects requests missing tenant context.

Code references:

- `api/app/main.py`
- `api/app/core/config.py`

### Metadata Filtering in Retrieval

Every vector retrieval call passes tenant context into the retriever API.

```python
chunks = retriever.retrieve(req.message, top_k=5, tenant_id=tenant_id)
```

Azure AI Search path:

- Applies server-side filter: `tenant_id eq '<tenant>'`
- Requires `tenant_id` to exist as a filterable field in index schema.

FAISS path:

- Uses chunk metadata field `tenant_id` in `chunks.jsonl`
- Over-fetches nearest neighbors and then drops chunks from other tenants before returning `top_k`

Code references:

- `api/app/retrieval/base.py`
- `api/app/retrieval/azure_search_retriever.py`
- `api/app/retrieval/faiss_retriever.py`
- `api/ingest/create_search_index.py`
- `api/ingest/upload_to_azure_search.py`
- `api/ingest/build_faiss_index.py`

### SaaS Isolation Narrative

"Every vector retrieval in my framework is hard-scoped to a TenantID. In this repo, middleware and retriever-level metadata filtering ensure Builder A cannot retrieve Builder B private pricing data."

## Operational Observability (SaaS-Ops Layer)

GroundedAgent provides structured observability and optional OpenTelemetry export.

### Structured Logs + Timing

- Emits JSON logs for request lifecycle and failure events.
- Captures stage timings (`retrieval_ms`, `embed_ms`, `search_ms`, `llm_ms`, `total_ms`).
- Logs include tenant context on chat paths.

Code references:

- `api/app/observability/logger.py`
- `api/app/main.py`
- `api/app/mcp_server.py`

### OpenTelemetry / App Insights

- Optional Azure Monitor OpenTelemetry export via connection string.
- Added span wrappers around chain stages:
  - `agent.plan`
  - `retrieval.search`
  - `llm.answer`
  - MCP equivalents (`mcp.*`)

Code references:

- `api/app/observability/app_insights.py`
- `api/app/observability/tracing.py`

### SaaS Ops Narrative

"Tracing is built in so we can pinpoint whether failures happen in retrieval, embedding latency, or final LLM reasoning."
