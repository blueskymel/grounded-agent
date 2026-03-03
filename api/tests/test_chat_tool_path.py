from dataclasses import dataclass

@dataclass
class DummyChunk:
    doc_id: str
    chunk_id: str
    text: str
    title: str | None = None
    source_uri: str | None = None
    score: float | None = 0.7


class DummyRetriever:
    last_embed_ms = 1
    last_search_ms = 2

    def retrieve(self, q: str, top_k: int = 5):
        return [DummyChunk(doc_id="d1", chunk_id="c1", text="evidence")]


@dataclass
class DummyAgentResult:
    answer: str
    tool_calls: list


def test_chat_tool_path_returns_tool_calls(client, monkeypatch):
    from app.core import config
    import app.main as main_mod

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)
    monkeypatch.setattr(main_mod, "get_retriever", lambda: DummyRetriever())

    # Make agent run return tool calls (triggers the early-return tool path)
    dummy = DummyAgentResult(
        answer="Here is a draft change plan.",
        tool_calls=[{"name": "draft_change_plan", "input": {"service": "X"}, "output": {"ok": True}}],
    )
    monkeypatch.setattr(main_mod, "run_agent", lambda msg, backend: dummy)

    r = client.post("/chat", json={"message": "Draft a change plan for service X"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Here is a draft change plan."
    assert body["tool_calls"][0]["name"] == "draft_change_plan"
    assert body["retrieval_backend"] == "faiss"