from dataclasses import dataclass
import re


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
        lambda _prompt, **_kwargs: (_ for _ in ()).throw(AssertionError("legacy AOAI path should not run")),
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
        lambda _prompt, **_kwargs: "- Restart worker process. [runbook1#c1]",
    )

    result = ga.generate_grounded_answer("How do I recover the worker?", chunks)

    assert result.is_refusal is False
    assert result.answer.strip().endswith("[runbook1#c1]")


def test_generate_grounded_answer_unsafe_demo_mode_can_hallucinate(monkeypatch):
    from app.llm import grounded_answer as ga

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("HALLUCINATION_DEMO_MODE", "unsafe")

    chunks = [DummyChunk(doc_id="runbook1", chunk_id="c1", text="Restart worker process.")]

    result = ga.generate_grounded_answer("What is the SLA for this service?", chunks)

    assert result.is_refusal is False
    assert "- " in result.answer
    assert "likely" in result.answer.lower()
    assert re.search(r"\[[^\[\]#]+#[^\[\]]+\]", result.answer) is None


def test_generate_grounded_answer_unsafe_demo_mode_varies_by_question(monkeypatch):
    from app.llm import grounded_answer as ga

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("HALLUCINATION_DEMO_MODE", "unsafe")

    chunks = [
        DummyChunk(doc_id="runbook1", chunk_id="c1", text="Restart worker process and verify service health."),
        DummyChunk(doc_id="runbook2", chunk_id="c2", text="Escalate to on-call if dependency latency exceeds threshold."),
    ]

    answer_a = ga.generate_grounded_answer("What is the SLA for this service?", chunks)
    answer_b = ga.generate_grounded_answer("How should we recover after dependency latency spikes?", chunks)

    assert answer_a.is_refusal is False
    assert answer_b.is_refusal is False
    assert answer_a.answer != answer_b.answer


def test_generate_grounded_answer_safe_mode_refuses_missing_sla(monkeypatch):
    from app.llm import grounded_answer as ga

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("HALLUCINATION_DEMO_MODE", "safe")

    chunks = [DummyChunk(doc_id="runbook1", chunk_id="c1", text="Restart worker process.")]

    result = ga.generate_grounded_answer("What is the SLA for this service?", chunks)

    assert result.is_refusal is True
    assert result.answer == "I don't have enough information in the provided runbooks to answer that."


def test_generate_grounded_answer_safe_mode_refuses_missing_policy(monkeypatch):
    from app.llm import grounded_answer as ga

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("HALLUCINATION_DEMO_MODE", "safe")

    chunks = [DummyChunk(doc_id="runbook1", chunk_id="c1", text="Restart worker process.")]

    result = ga.generate_grounded_answer("What is our re-balancing policy?", chunks)

    assert result.is_refusal is True
    assert result.answer == "I don't have enough information in the provided runbooks to answer that."


def test_generate_grounded_answer_safe_mode_allows_when_policy_evidence_exists(monkeypatch):
    from app.llm import grounded_answer as ga

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("HALLUCINATION_DEMO_MODE", "safe")

    chunks = [
        DummyChunk(
            doc_id="runbook1",
            chunk_id="c1",
            text="Re-balancing policy: route overflow traffic to region B and rollback within 15 minutes if error rate rises.",
        )
    ]

    result = ga.generate_grounded_answer("What is our re-balancing policy?", chunks)

    assert result.is_refusal is False
    assert "[runbook1#c1]" in result.answer
