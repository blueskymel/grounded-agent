# GroundedAgent — Agentic RAG Copilot (Azure-first)

[![CI: passing](https://github.com/blueskymel/grounded-agent/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/blueskymel/grounded-agent/actions/workflows/ci.yml)

**GroundedAgent** is a private, production-style **Agentic RAG Copilot platform** for IT Ops and Retail Enterprise teams. It answers questions grounded in internal runbooks, postmortems, policies, and incident notes **with citations**, and can **take actions via tools** (e.g., draft a change plan, create a ticket — mocked initially).

This repo is designed to demonstrate **real AI Engineer skills**: retrieval, orchestration, safety, observability, deployment, and cost control.

---

## Problem We Solve (IT Ops Pain)

Ops teams lose time and reliability due to:
- knowledge scattered across runbooks, PDFs, tickets, wikis
- repeated “tribal knowledge” questions
- slow incident triage and postmortem preparation
- incorrect answers from ungrounded chatbots (hallucinations)

**GroundedAgent** solves this with:
- **Grounded answers** (RAG) + **citations**
- **Agent orchestration** (tool calling) for multi-step tasks
- **Two retrieval modes** behind a feature flag:
  - **FAISS** (cheap demo mode)
  - **Azure AI Search** (enterprise mode)

---

## Retail AI Extension (Enterprise Workflow Tools)

GroundedAgent is designed as a **platform pattern**: grounded RAG + agentic tool orchestration.

In addition to IT Ops workflows, the system now includes **Retail Operations tool examples** (mocked but production-shaped):

### 🏬 draft_store_incident_summary
Generates a structured incident summary for store operations:
- What happened
- Customer impact
- Actions taken
- Next steps
- Structured metadata (store_id, duration, timestamp)

Designed to model enterprise workflows for:
- Store outages (POS, payments, network)
- Safety incidents
- Operational escalations

---

### 💲 analyze_price_change
Performs a pricing impact analysis:
- Price delta + % change
- Optional margin calculation (if unit cost provided)
- Risk flags (large move, margin drop, negative margin)

Designed to model:
- Pricing ops decision support
- Governance & approval workflows
- Commercial analytics copilots

---

These tools demonstrate how the same **grounded RAG + agent orchestration backend**
can be embedded into large-scale retail environments impacting thousands of stores and millions of customers.

---

## Architecture Philosophy

GroundedAgent follows an enterprise-safe AI architecture pattern:

1. **Tool-first orchestration** (deterministic workflows when appropriate)
2. **Grounded RAG fallback** with citation enforcement
3. **Refusal gating** when evidence is insufficient
4. **Feature-flag infrastructure** (FAISS ↔ Azure AI Search)
5. **Evaluation harness + CI gate** to prevent quality regression
6. **Privacy-first data handling**: Designed to support PII/PHI scrubbing patterns and role-based access control (RBAC) at the retrieval layer

This structure mirrors real-world enterprise AI systems where:
- LLMs augment workflows
- Retrieval must be auditable
- Tool access is explicitly controlled
- Deployment environments vary (local ↔ cloud)
- CI builds the FAISS index from api/fixtures/raw using deterministic mock embeddings (--provider mock) to avoid requiring Azure OpenAI secrets.
- Local dev can still use AOAI embeddings by setting the Azure env vars

## High-Level Architecture

### Components
- **Web UI (React)**: chat UI + citations + tool activity panel
- **API (FastAPI)**: agent orchestrator, retrieval, tools, safety, observability
- **Ingestion pipeline**: upload → extract → chunk → embed → index
- **Retrieval backend (feature-flag)**:
  - Local **FAISS** (demo)
  - **Azure AI Search** (enterprise)
- **Azure OpenAI**:
  - Chat model (agent reasoning + response generation)
  - Embeddings model (indexing + query embedding)
- **Storage**:
  - Azure Blob Storage for documents + artifacts
- **Observability**:
  - Application Insights (optional telemetry export for traces, latency, failures)

---

## Architecture Diagram (Mermaid)

```mermaid
flowchart LR
  U[User] --> UI[React Web UI]
  UI -->|/chat| API[FastAPI API]

  subgraph Orchestration
    API --> AG[Agent Orchestrator]
    AG --> SAF[Safety & Prompt Injection Checks]
    AG --> TOOL[Tool Router / Tool Calls]
  end

  SAF --> AG

  TOOL --> RET[Retriever Interface]
  RET -->|RETRIEVAL_BACKEND=faiss| FAI[FAISS Vector Index<br/>local]
  RET -->|RETRIEVAL_BACKEND=azure_search| AIS[Azure AI Search<br/>hybrid + vector + semantic]

  AG --> AOAI[Azure OpenAI<br/>Chat + Embeddings]
  AG -->|Citations| UI

  subgraph Ingestion
    DOCS[Docs: runbooks, postmortems, PDFs] --> BLOB[Azure Blob Storage]
    BLOB --> ING[Ingestion Worker<br/>extract → chunk → embed]
    ING --> AOAI
    ING -->|faiss mode| FAI
    ING -->|azure_search mode| AIS
  end

  API --> OBS[App Insights / Logs]
  ```



---

## Running GroundedAgent (Local Development)

### 1️⃣ Start the API

From the `api/` directory:

```bash
python -m uvicorn app.main:app --reload --app-dir .
```

Optional: enable Application Insights export

Windows:

```powershell
set APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=https://... python -m uvicorn app.main:app --reload --app-dir .
```

macOS / Linux:

```bash
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=https://..."
python -m uvicorn app.main:app --reload --app-dir .
```

Open:

- Swagger UI: http://127.0.0.1:8000/docs  
- Knowledge Base summary: http://127.0.0.1:8000/kb  

---

### 2️⃣ Start the MCP Server (Basic Wrapper)

From the `api/` directory:

```bash
python -m app.mcp_server
```

Or via Makefile:

```bash
make run-mcp
```

This exposes MCP tools over stdio:

- `chat(message)`
- `health()`
- `kb()`

The `chat` tool uses the same GroundedAgent flow:

- tool-first routing (intent parser + tool registry)
- grounded retrieval fallback with citations

All MCP tool responses use a consistent envelope:

```json
{
  "ok": true,
  "request_id": "uuid",
  "timings": { "total_ms": 12 },
  "data": { "...": "tool-specific payload" },
  "error": null
}
```

---

### 3️⃣ Connect an MCP Client

You can register GroundedAgent as an MCP server in your local client config.

VS Code MCP config example (`.vscode/mcp.json`):

```json
{
  "servers": {
    "grounded-agent": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "api"
    }
  }
}
```

Claude Desktop config example (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "grounded-agent": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "C:\\Users\\roger\\Downloads\\Roger\\grounded-agent\\api"
    }
  }
}
```

If your system Python is not the one with project dependencies, replace `python` with your venv executable path.

---

## Knowledge Base Introspection

GroundedAgent exposes a small introspection endpoint:

```http
GET /kb
```

Example response:

```json
[
  { "doc_id": "incident_comms_teams", "chunks": 3 },
  { "doc_id": "oncall_handoff", "chunks": 2 },
  { "doc_id": "p1_runbook", "chunks": 2 }
]
```

This allows quick inspection of what is currently indexed and how many chunks each document contains.

---

## Ingestion Pipeline

GroundedAgent includes a repeatable ingestion pipeline.

### Rebuild FAISS Index (Demo Mode)

```bash
python ingest/ingest.py
```

Example console output:

```
Total chunks: 13
FAISS index built successfully.
Done: FAISS rebuilt (demo mode).
```

This process:

- Reads all documents in `data/raw/`
- Extracts and chunks content with LangChain `RecursiveCharacterTextSplitter`
- Generates embeddings
- Builds a local FAISS IVF Flat vector index (with flat-index fallback for very small corpora)

Optional chunking controls:

```bash
python -m ingest.build_faiss_index --input_dir data/raw --out_dir data/index --chunk_size 300 --chunk_overlap 50
```

- `chunk_size`: max characters per chunk
- `chunk_overlap`: overlapping characters between adjacent chunks
- `--ivf-nlist`: IVF cluster count (default `64`, automatically capped by chunk count)

---

### Enterprise Mode (Azure AI Search)

If your environment variable is set to:

```
RETRIEVAL_BACKEND=azure_search
```

Then running:

```bash
python ingest/ingest.py
```

Will:

- Rebuild the FAISS index
- Upload documents and embeddings to Azure AI Search

Infrastructure provisioning and teardown are handled via CLI scripts in:

```
infra/azure/
```

---

## Retrieval Modes (Feature Flag)

Controlled via environment variable:

```
RETRIEVAL_BACKEND=faiss          # local demo mode
RETRIEVAL_BACKEND=azure_search   # enterprise mode
```

This enables cost-aware development while supporting production-grade Azure infrastructure.

---

## Security: Prompt Injection Defenses

GroundedAgent includes layered defenses for both direct and indirect prompt injection.

- **Direct user-message checks**: Blocks instruction-override patterns such as attempts to ignore prior instructions, reveal hidden/system prompts, or bypass policy.
- **Indirect retrieval checks**: Filters suspicious retrieved chunks before answer generation to prevent malicious instructions embedded in source documents.
- **Safe refusal path**: If a request is flagged or all retrieved chunks are filtered, the assistant refuses with a safe response and does not execute tools.
- **Coverage across interfaces**: These controls are enforced in both FastAPI (`/chat`, `/chat/stream`) and MCP (`chat` tool) flows.

Implementation references:

- `api/app/security/prompt_injection.py`
- `api/app/main.py`
- `api/app/mcp_server.py`
- `api/tests/test_prompt_injection_guard.py`

---

## Key Engineering Features

- Bullet-based grounded answers
- Per-bullet citation enforcement
- Automatic citation realignment based on retrieved chunks
- Refusal gating when evidence is insufficient
- Multi-document ingestion
- Feature-flag retrieval backend (FAISS ↔ Azure AI Search)
- CLI-based infrastructure automation
- Clean REST API design
- Agent tool registry with allow-list enforcement
- Retail Ops workflow tools (store incident summary, pricing impact analysis)
- Deterministic agent short-circuit path (tool execution before LLM)
- Unit-tested orchestration paths
---

Local Demo Script (5 minutes)

This demonstrates the full GroundedAgent pipeline locally without requiring Azure credentials.

Step 1 — Install Dependencies

From the api directory:

cd api

python -m venv .venv

Windows: .venv\Scripts\activate

macOS / Linux: source .venv/bin/activate

python -m pip install -U pip pip install -r requirements.txt

Step 2 — Build the Local **FAISS** Index

This uses mock embeddings so Azure OpenAI keys are not required.

Windows:

set EMBEDDINGS_PROVIDER=mock python -m ingest.build_faiss_index --input_dir fixtures/raw --out_dir data/index

macOS / Linux:

export EMBEDDINGS_PROVIDER=mock python -m ingest.build_faiss_index --input_dir fixtures/raw --out_dir data/index

Optional tuning:

- Add `--chunk_size` and `--chunk_overlap` to tune retrieval granularity.

Step 3 — Start the **API**

Windows:

set RETRIEVAL_BACKEND=faiss set LLM_PROVIDER=mock uvicorn app.main:app --reload --port **8000**

macOS / Linux:

export RETRIEVAL_BACKEND=faiss export LLM_PROVIDER=mock uvicorn app.main:app --reload --port **8000**

Open the Swagger UI:

[http://**127**.0.0.1:**8000**/docs](http://**127**.0.0.1:**8000**/docs)

### Demo Prompts

These prompts demonstrate **RAG** grounding, refusal safety, and agent tool calls.

Grounded **RAG** Answer

Request message: How do we triage a P1 incident?

Expected behavior:

- Bullet point answer
- Each bullet ends with a citation such as [doc_id#chunk_id]
- Citations appear in the response

Refusal Example (Safety)

Request message: What is our **SLA** for P1 response time?

Expected behavior:

- System refuses to answer
- Citations list is empty
- Prevents hallucinated answers

Tool Call — Price Change Analysis

Request message: Analyze price change impact for **SKU123** from 12.99 to 11.99

Expected behavior:

- analyze_price_change tool executes
- Returns structured analysis of price delta and margin impact

Tool Call — Low Stock Triage

Request message: Low stock store **2045** **SKU777** on hand 3

Expected behavior:

- triage_low_stock tool executes
- Returns priority classification and recommended actions

Tool Call — Promo Compliance

Request message: Check promo compliance promo **PROMO**-99 **SKU123** price 9.99 channel online

Expected behavior:

- check_promo_compliance tool executes
- Returns compliance status and required approvals

Run the Test Suite

pytest -q

Expected result: all tests passed

The test suite validates:

- intent parsing
- tool execution
- retrieval pipeline
- evaluation harness
- grounded answer formatting

### Evaluation Harness

GroundedAgent includes an evaluation harness to verify **RAG** quality.

Run:

python -m eval.run_eval

Example output:

=== GroundedAgent Eval Summary === Cases: 6 Recall@5 hit rate: **100**% Format compliance: **100**% Refusal correctness: **100**%

This ensures the system maintains:

- retrieval accuracy
- citation correctness
- safe refusal behavior

### ML Quality Pipeline (GitHub Actions)

In addition to the main CI workflow, this repo includes a dedicated ML quality pipeline:

- Workflow: `.github/workflows/ml-quality-pipeline.yml`
- Triggers: pull request, push to API/workflow paths, manual dispatch, and weekly schedule
- Stages: build FAISS index (mock embeddings), run eval suite, apply threshold gate, upload `eval/report.json` artifact

This gives you a repeatable quality gate for retrieval and grounded-answer behavior before merge or release.

### ML Quality Pipeline (Azure DevOps)

This repo also includes an Azure DevOps equivalent for teams using Azure-native delivery:

- Pipeline file: `azure-pipelines.yml`
- Triggers: PR/push for `api/**` and pipeline file changes, plus weekly cron
- Stages: install deps, build FAISS index (mock), run eval suite, apply threshold gate, publish `api/eval/report.json` artifact

This mirrors the GitHub Actions gate so quality checks are consistent across CI platforms.

### Azure ML Eval Job (Optional)

For teams that want managed MLOps job history in Azure ML, this repo includes a minimal submission script:

- Script: `python -m eval.submit_azureml_eval_job`
- Behavior: installs dependencies, rebuilds fixture FAISS index, runs eval, applies eval thresholds, uploads `eval/report.json` as a job output artifact

Required environment variables:

```powershell
$env:AZURE_SUBSCRIPTION_ID = "<subscription-guid>"
$env:AZURE_ML_RESOURCE_GROUP = "<resource-group>"
$env:AZURE_ML_WORKSPACE_NAME = "<workspace-name>"
```

Optional arguments:

```powershell
python -m eval.submit_azureml_eval_job --compute cpu-cluster --experiment grounded-agent-eval --limit 25
```

After an eval run produces `eval/report.json`, generate a concise JSON + markdown gate summary:

```powershell
python -m eval.summarize_aml_eval_report --report eval/report.json
```

### Foundry-Backed Evaluation Workflow

This repo now includes an optional Azure AI Foundry evaluation path that reuses the existing local QA dataset instead of inventing a separate benchmark.

- Script: `python -m eval.run_foundry_eval --refresh-dataset`
- Dataset prep: `api/eval/foundry_dataset.py` generates `eval/foundry_eval_dataset.jsonl` from the current retriever + grounded-answer flow
- Evaluators: `groundedness`, `relevance`, `coherence`, `fluency` via `azure-ai-evaluation`
- Foundry tracking: set `AZURE_AI_PROJECT_ENDPOINT` to push the run into a Foundry project for portal-side history/comparison

Required environment variables:

```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://<your-aoai>.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY = "<key>"
$env:AZURE_OPENAI_CHAT_DEPLOYMENT = "gpt-4o"

# Optional: override eval model deployment
$env:FOUNDRY_EVAL_MODEL_DEPLOYMENT = "gpt-4o-mini"

# Optional: log the run into Azure AI Foundry
$env:AZURE_AI_PROJECT_ENDPOINT = "https://<resource>.services.ai.azure.com/api/projects/<project>"
```

Run it from `api/`:

```powershell
python -m eval.run_foundry_eval --refresh-dataset
```

The script writes `eval/foundry_eval_results.json` locally and, when a Foundry project endpoint is configured, also logs the run to Foundry for history and comparison.

### Hosted Foundry Agent Runtime Path (Optional)

In addition to Foundry evaluation, this repo now supports a hosted Foundry agent execution path at runtime.

- Toggle with env var: `AGENT_FRAMEWORK=foundry`
- Dispatch point: `api/app/core/agent.py`
- Hosted agent adapter: `api/app/core/agent_foundry.py`

Required environment variables for hosted-agent mode:

```powershell
$env:AZURE_AI_PROJECT_ENDPOINT = "https://<resource>.services.ai.azure.com/api/projects/<project>"
$env:FOUNDRY_AGENT_ID = "<agent-id>"
```

Optional tuning:

```powershell
$env:FOUNDRY_AGENT_TIMEOUT_SECONDS = "90"
$env:FOUNDRY_AGENT_POLL_SECONDS = "2"
```

If hosted-agent dependencies/config are missing, the API returns a safe fallback answer instead of crashing.

### Managed Identity + Key Vault

The app now supports passwordless secret retrieval from Azure Key Vault using `DefaultAzureCredential` and `SecretClient`.

- Local development keeps working with `.env` values as before
- Azure deployments can provide only `KEY_VAULT_URL`, `MANAGED_IDENTITY_CLIENT_ID`, and secret-name env vars
- Supported Key Vault-backed settings: `AZURE_OPENAI_API_KEY`, `AZURE_SEARCH_API_KEY`, `APPLICATIONINSIGHTS_CONNECTION_STRING`

App-side Key Vault configuration:

```powershell
$env:KEY_VAULT_URL = "https://<vault-name>.vault.azure.net/"
$env:MANAGED_IDENTITY_CLIENT_ID = "<user-assigned-managed-identity-client-id>"
$env:KEYVAULT_AZURE_OPENAI_API_KEY_SECRET_NAME = "azure-openai-api-key"
$env:KEYVAULT_AZURE_SEARCH_API_KEY_SECRET_NAME = "azure-search-api-key"
$env:KEYVAULT_APPLICATIONINSIGHTS_CONNECTION_STRING_SECRET_NAME = "applicationinsights-connection-string"
```

### LangGraph Agent Variant (Optional)

The default orchestration path remains deterministic (`AGENT_FRAMEWORK=classic`), and this repo now includes an optional LangGraph variant for framework fluency.

- Toggle with env var: `AGENT_FRAMEWORK=langgraph`
- Implementation: `api/app/core/agent_langgraph.py`
- Dispatch point: `api/app/core/agent.py`

Example:

```powershell
$env:AGENT_FRAMEWORK = "langgraph"
python -m uvicorn app.main:app --reload
```

When enabled, the LangGraph state graph preserves the same tool-first behavior and retrieval fallback shape used by the existing deterministic flow.

### LangChain LCEL Answer Chain (Optional)

The default grounded answer path remains `ANSWER_FRAMEWORK=classic`, and this repo now includes an optional LangChain LCEL answer chain for framework fluency beyond ingestion chunking.

- Toggle with env var: `ANSWER_FRAMEWORK=langchain`
- LCEL chain implementation: `api/app/llm/langchain_answer_chain.py`
- Grounded-answer dispatch point: `api/app/llm/grounded_answer.py`

Example:

```powershell
$env:ANSWER_FRAMEWORK = "langchain"
python -m uvicorn app.main:app --reload
```

When enabled, the LangChain chain composes prompt construction and AOAI invocation with LCEL and keeps the existing citation/refusal validation path.

---

## Deploy to Azure Container Apps

The API ships with a complete Bicep + `azd` deployment path. Infrastructure created:

- **Azure Container Registry** (Basic, managed-identity pull — no admin keys)
- **Container Apps Environment** backed by **Log Analytics**
- **Container App** (0.5 vCPU / 1 GiB, 1–3 replicas, HTTP scaling rule)
- **User-Assigned Managed Identity** with `AcrPull` role on the registry
- **Key Vault** (optional `deployKeyVault=true`) with `Key Vault Secrets User` role assignment for the app identity
- **API Management** (Consumption, optional `deployApim=true`) — subscription-key auth, rate limiting, CORS policy

### Quick deploy (azd)

```powershell
azd auth login
azd env new grounded-dev
azd env set AZURE_LOCATION australiaeast
# Set AZURE_OPENAI_*, AZURE_SEARCH_* env vars first — see docs/deploy-aca.md
# Optional: use Key Vault + managed identity instead of injecting secrets directly
# azd env set DEPLOY_KEY_VAULT true
# Optional: add APIM in front
# azd env set DEPLOY_APIM true ; azd env set APIM_PUBLISHER_EMAIL you@example.com
azd up
```

### Manual deploy (Azure CLI)

```powershell
az deployment sub create \
  --location australiaeast \
  --template-file infra/main.bicep \
  --parameters environmentName=grounded-dev location=australiaeast ...
```

Full step-by-step instructions, environment variable reference, and post-deploy checks: [docs/deploy-aca.md](docs/deploy-aca.md)

## Azure Functions Hosting Scaffold

This repo now includes a parallel Azure Functions hosting scaffold for the same FastAPI app using `AsgiFunctionApp`.

- Infra module: `infra/azure/function-app.bicep`
- Hosting switch in root infra template: `infra/main.bicep` (`hostingModel=functions`)
- Function runtime entrypoint: `functionapp/function_app.py`
- Deployment guide: [docs/deploy-functions.md](docs/deploy-functions.md)
- CI deploy workflow: `.github/workflows/functions-deploy.yml` (manual dispatch)

The Functions workflow now includes:

- pre-deploy quality gate (`ruff`, `pytest`, eval, threshold gate)
- smoke-test option for `/api/health`
- retry-based post-deploy health verification (6 attempts, 10 seconds apart)
- failure diagnostics collection (`az functionapp` deployment + settings metadata)
- deployment evidence artifact upload (metadata + smoke response)

This keeps the existing Container Apps path as the default while providing a production-shaped Functions option for event-driven/serverless hosting requirements.