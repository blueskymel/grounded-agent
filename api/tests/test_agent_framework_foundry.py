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


def test_run_agent_foundry_sdk_boundary_mock(monkeypatch):
    from types import SimpleNamespace

    from app.core.agent_foundry import run_agent_foundry

    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/test")
    monkeypatch.setenv("FOUNDRY_AGENT_ID", "agent-123")
    monkeypatch.setenv("FOUNDRY_AGENT_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("FOUNDRY_AGENT_POLL_SECONDS", "0")

    class FakeAgents:
        def create_thread(self):
            return SimpleNamespace(id="thread-1")

        def create_message(self, thread_id: str, role: str, content: str):
            assert thread_id == "thread-1"
            assert role == "user"
            assert content == "hello"

        def create_run(self, thread_id: str, agent_id: str):
            assert thread_id == "thread-1"
            assert agent_id == "agent-123"
            return SimpleNamespace(id="run-1", status="queued")

        def get_run(self, thread_id: str, run_id: str):
            assert thread_id == "thread-1"
            assert run_id == "run-1"
            return SimpleNamespace(id="run-1", status="completed")

        def list_messages(self, thread_id: str):
            assert thread_id == "thread-1"
            return [
                SimpleNamespace(
                    role="assistant",
                    content=[SimpleNamespace(text=SimpleNamespace(value="Foundry response"))],
                )
            ]

    class FakeAIProjectClient:
        def __init__(self, endpoint: str, credential):
            assert endpoint.startswith("https://example.services.ai.azure.com")
            self.agents = FakeAgents()

    class FakeCredential:
        pass

    monkeypatch.setattr(
        "app.core.agent_foundry._require_foundry_agent_packages",
        lambda: (FakeAIProjectClient, FakeCredential),
    )

    answer, tool_calls = run_agent_foundry("hello", "faiss")
    assert answer == "Foundry response"
    assert tool_calls[0]["name"] == "foundry_hosted_agent"
    assert tool_calls[0]["output"]["status"] == "completed"
