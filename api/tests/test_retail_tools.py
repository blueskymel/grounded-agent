from dataclasses import dataclass

@dataclass
class DummyAgentResult:
    answer: str
    tool_calls: list

class DummyRetriever:
    last_embed_ms = 0
    last_search_ms = 0
    def retrieve(self, q: str, top_k: int = 5):
        return []  # doesn't matter for tool path tests
    
def test_retail_store_incident_tool_path(client, monkeypatch):
    from app.core import config
    import app.main as main_mod

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)
    monkeypatch.setattr(main_mod, "get_retriever", lambda: DummyRetriever())

    # Force agent result with a retail tool call; avoids LLM and retrieval coupling
    dummy = DummyAgentResult(
        answer="(tool) Ran draft_store_incident_summary",
        tool_calls=[{
            "name": "draft_store_incident_summary",
            "input": {"store_id": "1234", "incident_type": "POS outage", "duration_minutes": 45},
            "output": {"ok": True}
        }]
    )
    monkeypatch.setattr(main_mod, "run_agent", lambda msg, backend: dummy)

    r = client.post("/chat", json={"message": "Create a store incident summary for store 1234 POS outage"})
    assert r.status_code == 200
    body = r.json()
    assert body["tool_calls"][0]["name"] == "draft_store_incident_summary"

def test_retail_price_change_tool_path(client, monkeypatch):
    from app.core import config
    import app.main as main_mod

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)

    dummy = DummyAgentResult(
        answer="(tool) Ran analyze_price_change",
        tool_calls=[{
            "name": "analyze_price_change",
            "input": {"sku": "SKU123", "old_price": 12.99, "new_price": 11.99, "unit_cost": 8.50},
            "output": {"ok": True}
        }]
    )
    monkeypatch.setattr(main_mod, "run_agent", lambda msg, backend: dummy)

    r = client.post("/chat", json={"message": "Analyze price change impact for SKU123 from 12.99 to 11.99"})
    assert r.status_code == 200
    body = r.json()
    assert body["tool_calls"][0]["name"] == "analyze_price_change"