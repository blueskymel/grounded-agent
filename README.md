# GroundedAgent — Agentic RAG Copilot (Azure-first)

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
- Builds a local FAISS vector index

Optional chunking controls:

```bash
python -m ingest.build_faiss_index --input_dir data/raw --out_dir data/index --chunk_size 300 --chunk_overlap 50
```

- `chunk_size`: max characters per chunk
- `chunk_overlap`: overlapping characters between adjacent chunks

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