from dataclasses import dataclass


@dataclass
class DummyAgentResult:
    answer: str
    tool_calls: list[dict]


def test_chat_low_stock_tool_path(client, monkeypatch):
    import app.main as main_mod

    dummy = DummyAgentResult(
        answer="(tool) Ran triage_low_stock",
        tool_calls=[{
            "name": "triage_low_stock",
            "input": {"store_id": "2045", "sku": "SKU777", "on_hand": 0},
            "output": {"ok": True, "priority": "P1"}
        }]
    )
    monkeypatch.setattr(main_mod, "run_agent", lambda msg, backend: dummy)

    r = client.post("/chat", json={"message": "Low stock store 2045 SKU777 on hand 0"})
    assert r.status_code == 200
    body = r.json()
    assert body["tool_calls"]
    assert body["tool_calls"][0]["name"] == "triage_low_stock"
    assert body["citations"] == []


def test_chat_promo_compliance_tool_path(client, monkeypatch):
    import app.main as main_mod

    dummy = DummyAgentResult(
        answer="(tool) Ran check_promo_compliance",
        tool_calls=[{
            "name": "check_promo_compliance",
            "input": {"promo_id": "PROMO-99", "sku": "SKU123", "price": 0.49, "channel": "online"},
            "output": {"ok": True, "passed": False}
        }]
    )
    monkeypatch.setattr(main_mod, "run_agent", lambda msg, backend: dummy)

    r = client.post("/chat", json={"message": "Check promo compliance PROMO-99 SKU123 price 0.49 channel online"})
    assert r.status_code == 200
    body = r.json()
    assert body["tool_calls"]
    assert body["tool_calls"][0]["name"] == "check_promo_compliance"
    assert body["citations"] == []