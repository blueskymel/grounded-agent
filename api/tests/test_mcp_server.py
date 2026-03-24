from dataclasses import dataclass


@dataclass
class DummyAgentResult:
    answer: str
    tool_calls: list[dict]


@dataclass
class DummyDoc:
    doc_id: str
    chunks: int


def test_mcp_chat_tool_path_enveloped(monkeypatch):
    import app.mcp_server as mcp_server

    dummy = DummyAgentResult(
        answer="(tool) Ran triage_low_stock",
        tool_calls=[
            {
                "name": "triage_low_stock",
                "input": {"store_id": "2045", "sku": "SKU777", "on_hand": 0},
                "output": {"ok": True, "priority": "P1"},
            }
        ],
    )
    monkeypatch.setattr(mcp_server, "run_agent", lambda msg, backend: dummy)

    result = mcp_server.chat("Low stock store 2045 SKU777 on hand 0")

    assert result["ok"] is True
    assert result["error"] is None
    assert result["request_id"]
    assert "timings" in result
    assert result["data"]["tool_calls"][0]["name"] == "triage_low_stock"


def test_mcp_chat_validation_error_enveloped():
    import app.mcp_server as mcp_server

    too_long = "x" * 9001
    result = mcp_server.chat(too_long)

    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"
    assert result["error"]["message"] == "Invalid request payload."


def test_mcp_health_returns_backend(monkeypatch):
    import app.mcp_server as mcp_server
    from app.core import config

    monkeypatch.setattr(config.settings, "app_env", "local", raising=False)
    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)

    result = mcp_server.health()

    assert result["ok"] is True
    assert result["data"]["status"] == "ok"
    assert result["data"]["retrieval_backend"] == "faiss"


def test_mcp_kb_returns_docs(monkeypatch):
    import app.mcp_server as mcp_server
    from app.core import config

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)
    monkeypatch.setattr(
        mcp_server,
        "faiss_doc_stats",
        lambda: [DummyDoc(doc_id="incident_comms_teams", chunks=3)],
    )

    result = mcp_server.kb()

    assert result["ok"] is True
    assert result["data"]["retrieval_backend"] == "faiss"
    assert result["data"]["documents"] == [{"doc_id": "incident_comms_teams", "chunks": 3}]
