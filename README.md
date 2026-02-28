# GroundedAgent — Agentic RAG Copilot (Azure-first)

**GroundedAgent** is a private, production-style **Agentic RAG Copilot** for IT Ops teams. It answers questions grounded in internal runbooks, postmortems, policies, and incident notes **with citations**, and can **take actions via tools** (e.g., draft a change plan, create a ticket — mocked initially).

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
  - Application Insights (traces, latency, failures)

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
  RET -->|RETRIEVAL_BACKEND=faiss| FAI[FAISS Vector Index\n(local)]
  RET -->|RETRIEVAL_BACKEND=azure_search| AIS[Azure AI Search\n(hybrid + vector + semantic)]

  AG --> AOAI[Azure OpenAI\n(Chat + Embeddings)]
  AG -->|Citations| UI

  subgraph Ingestion
    DOCS[Docs: runbooks, postmortems, PDFs] --> BLOB[Azure Blob Storage]
    BLOB --> ING[Ingestion Worker\nextract->chunk->embed]
    ING --> AOAI
    ING -->|faiss mode| FAI
    ING -->|azure_search mode| AIS
  end

  API --> OBS[App Insights / Logs]