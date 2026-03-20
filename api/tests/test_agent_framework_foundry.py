def test_run_agent_uses_foundry_when_enabled(monkeypatch):
    from app.core import agent as agent_mod
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "agent_framework", "foundry", raising=False)

    def fake_run_agent_foundry(message: str, retrieval_backend: str):
        return "foundry-answer", [{"name": "foundry_hosted_agent", "input": {}, "output": {"ok": True}}]

    monkeypatch.setattr("app.core.agent_foundry.run_agent_foundry", fake_run_agent_foundry)

    result = agent_mod.run_agent("hello", "faiss")
    assert result.answer == "foundry-answer"
    assert result.tool_calls and result.tool_calls[0]["name"] == "foundry_hosted_agent"


def test_run_agent_foundry_fallback_when_unavailable(monkeypatch):
    from app.core import agent as agent_mod
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "agent_framework", "foundry", raising=False)

    def fake_run_agent_foundry(message: str, retrieval_backend: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.core.agent_foundry.run_agent_foundry", fake_run_agent_foundry)

    result = agent_mod.run_agent("hello", "faiss")
    assert "Foundry agent path unavailable" in result.answer
    assert result.tool_calls == []
