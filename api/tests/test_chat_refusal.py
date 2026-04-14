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