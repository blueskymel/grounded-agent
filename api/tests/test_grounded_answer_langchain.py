from dataclasses import dataclass


@dataclass
class DummyChunk:
    doc_id: str
    chunk_id: str
    text: str


def test_generate_grounded_answer_uses_langchain_framework(monkeypatch):
    from app.llm import grounded_answer as ga

    monkeypatch.setenv("LLM_PROVIDER", "aoai")
    monkeypatch.setenv("ANSWER_FRAMEWORK", "langchain")

    chunks = [DummyChunk(doc_id="runbook1", chunk_id="c1", text="Reset the service from portal.")]

    monkeypatch.setattr(
        ga,
        "generate_grounded_answer_lcel",
        lambda question, sources_text: "- Reset the service from portal. [runbook1#c1]",
    )

    # If this gets called, langchain path was not used.
    monkeypatch.setattr(
        ga,
        "_generate_aoai_chat_response",
        lambda _prompt: (_ for _ in ()).throw(AssertionError("legacy AOAI path should not run")),
    )

    result = ga.generate_grounded_answer("How do I recover the service?", chunks)

    assert result.is_refusal is False
    assert result.answer.strip().endswith("[runbook1#c1]")


def test_generate_grounded_answer_langchain_fallback_to_legacy(monkeypatch):
    from app.llm import grounded_answer as ga

    monkeypatch.setenv("LLM_PROVIDER", "aoai")
    monkeypatch.setenv("ANSWER_FRAMEWORK", "langchain")

    chunks = [DummyChunk(doc_id="runbook1", chunk_id="c1", text="Restart worker process.")]

    def _raise(*_args, **_kwargs):
        raise RuntimeError("simulated lcel failure")

    monkeypatch.setattr(ga, "generate_grounded_answer_lcel", _raise)
    monkeypatch.setattr(
        ga,
        "_generate_aoai_chat_response",
        lambda _prompt: "- Restart worker process. [runbook1#c1]",
    )

    result = ga.generate_grounded_answer("How do I recover the worker?", chunks)

    assert result.is_refusal is False
    assert result.answer.strip().endswith("[runbook1#c1]")
