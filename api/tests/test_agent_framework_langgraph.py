def test_run_agent_uses_langgraph_when_enabled(monkeypatch):
    from app.core import agent as agent_mod
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "agent_framework", "langgraph", raising=False)

    def fake_run_agent_langgraph(message: str, retrieval_backend: str):
        return "langgraph-answer", [{"name": "stub_tool", "input": {}, "output": {"ok": True}}]

    monkeypatch.setattr("app.core.agent_langgraph.run_agent_langgraph", fake_run_agent_langgraph)

    result = agent_mod.run_agent("hello", "faiss")
    assert result.answer == "langgraph-answer"
    assert result.tool_calls and result.tool_calls[0]["name"] == "stub_tool"
