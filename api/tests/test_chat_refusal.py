from dataclasses import dataclass

REFUSAL_TEXT = "I don't have enough information in the provided runbooks to answer that."

@dataclass
class DummyChunk:
    doc_id: str
    chunk_id: str
    text: str
    title: str | None = None
    source_uri: str | None = None
    score: float | None = 0.9


class DummyRetriever:
    last_embed_ms = 1
    last_search_ms = 2

    def retrieve(self, q: str, top_k: int = 5):
        return [
            DummyChunk(doc_id="runbook1", chunk_id="c1", text="some evidence"),
            DummyChunk(doc_id="runbook2", chunk_id="c2", text="more evidence"),
        ]


class LowConfidenceRetriever:
    last_embed_ms = 1
    last_search_ms = 2

    def retrieve(self, q: str, top_k: int = 5):
        return [
            DummyChunk(doc_id="runbook1", chunk_id="c1", text="some evidence", score=0.35),
            DummyChunk(doc_id="runbook2", chunk_id="c2", text="more evidence", score=0.34),
        ]


class HighConfidenceRetriever:
    last_embed_ms = 1
    last_search_ms = 2

    def retrieve(self, q: str, top_k: int = 5):
        return [
            DummyChunk(doc_id="runbook1", chunk_id="c1", text="some evidence", score=0.98),
            DummyChunk(doc_id="runbook2", chunk_id="c2", text="more evidence", score=0.97),
        ]


def test_chat_refusal_clears_citations(client, monkeypatch):
    from app.core import config
    import app.main as main_mod

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)

    # Force retriever path
    monkeypatch.setattr(main_mod, "get_retriever", lambda: DummyRetriever())

    # Force grounded answer to be refusal
    class DummyResult:
        def __init__(self):
            self.answer = REFUSAL_TEXT
            self.is_refusal = True

    monkeypatch.setattr(main_mod, "generate_grounded_answer", lambda *args, **kwargs: DummyResult())

    r = client.post("/chat", json={"message": "What is the SLA for system X?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"].strip() == REFUSAL_TEXT
    assert body["citations"] == []  # critical behavior
    assert body["retrieval_backend"] == "faiss"


def test_chat_after_refuses_when_confidence_below_threshold(client, monkeypatch):
    from app.core import config
    import app.main as main_mod

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)
    monkeypatch.setattr(main_mod, "get_retriever", lambda: LowConfidenceRetriever())
    monkeypatch.setattr(main_mod, "run_agent", lambda *_: type("R", (), {"tool_calls": [], "answer": ""})())

    class DummyResult:
        def __init__(self):
            self.answer = "- A grounded answer with citation. [runbook1#c1]"
            self.is_refusal = False

    monkeypatch.setattr(main_mod, "generate_grounded_answer", lambda *args, **kwargs: DummyResult())

    r = client.post("/chat/after", json={"message": "give me the re-balancing policy"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"].strip() == REFUSAL_TEXT
    assert body["citations"] == []


def test_chat_after_allows_when_confidence_at_or_above_threshold(client, monkeypatch):
    from app.core import config
    import app.main as main_mod

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)
    monkeypatch.setattr(main_mod, "get_retriever", lambda: HighConfidenceRetriever())
    monkeypatch.setattr(main_mod, "run_agent", lambda *_: type("R", (), {"tool_calls": [], "answer": ""})())

    class DummyResult:
        def __init__(self):
            self.answer = "- Re-balancing policy guidance. [runbook1#c1]"
            self.is_refusal = False

    monkeypatch.setattr(main_mod, "generate_grounded_answer", lambda *args, **kwargs: DummyResult())

    r = client.post("/chat/after", json={"message": "give me the re-balancing policy"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"].strip().startswith("-")
    assert len(body["citations"]) > 0