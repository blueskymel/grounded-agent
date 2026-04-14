from dataclasses import dataclass


@dataclass
class DummyChunk:
    doc_id: str
    chunk_id: str
    text: str
    title: str | None = None
    source_uri: str | None = None
    score: float | None = 0.9


@dataclass
class DummyAgentResult:
    answer: str
    tool_calls: list


class TenantAwareDummyRetriever:
    last_embed_ms = 1
    last_search_ms = 2

    def __init__(self):
        self.seen_tenant_id = None

    def retrieve(self, query: str, top_k: int = 5, tenant_id: str | None = None):
        self.seen_tenant_id = tenant_id
        return [DummyChunk(doc_id="tenant_doc", chunk_id="c1", text="tenant evidence")]


def test_chat_passes_tenant_id_to_retriever(client, monkeypatch):
    from app.core import config
    import app.main as main_mod

    retriever = TenantAwareDummyRetriever()

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)
    monkeypatch.setattr(main_mod, "get_retriever", lambda: retriever)
    monkeypatch.setattr(main_mod, "run_agent", lambda *_: DummyAgentResult(answer="", tool_calls=[]))

    class DummyResult:
        answer = "- use tenant runbook [tenant_doc#c1]"
        is_refusal = False

    monkeypatch.setattr(main_mod, "generate_grounded_answer", lambda *args, **kwargs: DummyResult())

    r = client.post(
        "/chat",
        json={"message": "How do I recover service?"},
        headers={"x-tenant-id": "builder-a"},
    )

    assert r.status_code == 200
    assert retriever.seen_tenant_id == "builder-a"


def test_chat_rejects_missing_tenant_header_when_enforced(client, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "enforce_tenant_header", True, raising=False)

    r = client.post("/chat", json={"message": "hello"})

    assert r.status_code == 400
    assert "Missing x-tenant-id header" in r.text
