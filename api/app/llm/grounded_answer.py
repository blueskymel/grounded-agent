import os
from typing import List, Iterator
from app.retrieval.base import RetrievedChunk
from app.llm.client import get_aoai_client, get_chat_deployment
from app.llm.langchain_answer_chain import generate_grounded_answer_lcel
from dataclasses import dataclass
import re

_SLA_TERMS = re.compile(r"\b(sla|slo|rto|rpo)\b", re.IGNORECASE)
_POLICY_TERMS = re.compile(
    r"\b(policy|policies|governance|compliance|contractual|re[-\s]?balanc(?:e|ing))\b",
    re.IGNORECASE,
)

@dataclass
class GroundedResult:
    answer: str
    is_refusal: bool


def _hallucination_demo_mode(mode_override: str | None = None) -> str:
    if mode_override:
        mode = mode_override.strip().lower()
    else:
        mode = os.environ.get("HALLUCINATION_DEMO_MODE", "safe").strip().lower()
    return mode if mode in {"safe", "unsafe"} else "safe"


def _is_unsafe_demo_mode(mode_override: str | None = None) -> bool:
    return _hallucination_demo_mode(mode_override) == "unsafe"

SYSTEM_PROMPT = """Context:
You are GroundedAgent, an IT Ops assistant. You are given a user QUESTION and a SOURCES block with retrieved runbook chunks.

Objectives:
- Use ONLY the provided SOURCES. Do not use outside knowledge.
- Provide operationally useful, grounded steps that are directly supported by cited chunks.
- If the question asks for information not explicitly present in SOURCES (for example SLA/SLO/RTO/RPO), answer exactly:
    "I don't have enough information in the provided runbooks to answer that."

Style:
- Be concise and action-oriented.
- Use 3-7 bullets when answering with steps.

Tone:
- Neutral, factual, and practical.
- Do not overstate certainty.

Audience:
- IT operations engineers and incident responders.

Response:
- Output MUST be a bulleted list (each line starts with "- ") when providing an answer from sources.
- EACH bullet MUST end with one or more citations in the form [doc_id#chunk_id].
- Do NOT cite a chunk that does not contain the claim.

Output Format Example (follow exactly):
- First action step. [doc_id#chunk_id]
- Second action step. [doc_id#chunk_id][doc_id#chunk_id]

Few-Shot Examples:
Example 1:
QUESTION:
How do I recover a worker service after restart?

SOURCES:
[runbook2#c2]
Restart worker service and verify health endpoint returns 200.

[runbook2#c3]
If health is not 200, check dependency connectivity and retry once.

ANSWER:
- Restart the worker service and verify the health endpoint returns 200. [runbook2#c2]
- If health is not 200, check dependency connectivity and retry once. [runbook2#c3]

Example 2:
QUESTION:
What is the SLA for this service?

SOURCES:
[runbook9#c1]
Troubleshooting steps for service restart and health checks.

ANSWER:
I don't have enough information in the provided runbooks to answer that.
"""

UNSAFE_SYSTEM_PROMPT = """Context:
You are GroundedAgent in demo mode. You are given a user QUESTION and optional SOURCES.

Objectives:
- Provide a confident, helpful answer even when evidence is incomplete.
- You may extrapolate from SOURCES and fill gaps with plausible operational assumptions.
- Do not refuse to answer due to missing evidence.

Style:
- Be concise and action-oriented.
- Use 3-5 bullets.

Tone:
- Confident and direct.
- Present likely guidance as if it is actionable.

Response:
- Output a bulleted list (each line starts with "- ").
- Do not include citations.
"""


def _system_prompt_for_mode(unsafe_mode: bool) -> str:
    return UNSAFE_SYSTEM_PROMPT if unsafe_mode else SYSTEM_PROMPT

def _sources_explicitly_define_terms(chunks, terms_regex=_SLA_TERMS) -> bool:
    """Return True if any retrieved chunk explicitly contains the requested terms."""
    for c in chunks:
        if terms_regex.search(c.text or ""):
            return True
    return False

def is_answerable(question: str, chunks: list[RetrievedChunk]) -> bool:
    q = question.lower()
    # high-risk terms that models often hallucinate around
    guarded_terms = ["sla", "slo", "rto", "rpo", "contract", "legal", "guarantee"]

    if any(t in q for t in guarded_terms):
        sources = "\n".join(c.text.lower() for c in chunks)
        # require term presence in sources (simple but strong)
        return any(t in sources for t in guarded_terms if t in q)

    return True

def build_sources(chunks: List[RetrievedChunk]) -> str:
    lines = []
    for c in chunks:
        tag = f"[{c.doc_id}#{c.chunk_id}]"
        lines.append(f"{tag}\n{c.text}\n")
    return "\n".join(lines)

def _strip_citations(line: str) -> str:
    # remove trailing [doc#chunk] blocks
    return re.sub(r"(?:\s*\[[^\[\]#]+#[^\[\]]+\])+\s*$", "", line).strip()

def _pick_best_chunk_id(statement: str, chunks: list[RetrievedChunk]) -> str | None:
    # simple lexical overlap scoring
    stmt = statement.lower()
    tokens = [t for t in re.findall(r"[a-z0-9]+", stmt) if len(t) > 2]
    if not tokens:
        return None

    best = None
    best_score = -1

    for c in chunks:
        text = (c.text or "").lower()
        score = sum(1 for t in tokens if t in text)
        if score > best_score:
            best_score = score
            best = c

    if best and best_score > 0:
        return f"{best.doc_id}#{best.chunk_id}"
    return None

def _realign_bullet_citations(answer: str, chunks: list[RetrievedChunk]) -> str:
    lines = _extract_bullets(answer)
    fixed = []

    for ln in lines:
        stmt = _strip_citations(ln)

        best = _pick_best_chunk_id(stmt, chunks)
        if not best:
            # if we can't find evidence, keep line as-is (validator will catch if missing)
            fixed.append(ln)
            continue

        fixed.append(f"{stmt} [{best}]")

    return "\n".join(fixed)

_CITATION_RE = re.compile(r"\[[^\[\]#]+#[^\[\]]+\]\s*$")

def _extract_bullets(text: str) -> list[str]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    bullets: list[str] = []

    for ln in lines:
        if ln.startswith("- "):
            bullets.append(ln)
            continue

        # normalize numbered lists like "1. ..." or "1) ..."
        if re.match(r"^\d+[\.\)]\s+", ln):
            ln2 = re.sub(r"^\d+[\.\)]\s+", "- ", ln)
            bullets.append(ln2)

    return bullets

def _all_bullets_have_citations(bullets: list[str]) -> bool:
    return bool(bullets) and all(_CITATION_RE.search(b) for b in bullets)

def _normalize_bullets(bullets: list[str]) -> str:
    # Keep bullets only, join as final answer
    return "\n".join(bullets)


def _question_keywords(question: str, max_terms: int = 4) -> list[str]:
    stop = {
        "what", "which", "when", "where", "why", "how", "for", "with", "this",
        "that", "from", "into", "your", "about", "service", "system", "the", "and",
        "are", "can", "you", "our", "does", "should", "have", "need", "after",
    }
    terms: list[str] = []
    for tok in re.findall(r"[a-z0-9]+", (question or "").lower()):
        if len(tok) < 3 or tok in stop:
            continue
        if tok not in terms:
            terms.append(tok)
        if len(terms) >= max_terms:
            break
    return terms


def _unsafe_chunk_snippet(chunks: list[RetrievedChunk], index: int) -> str:
    if index >= len(chunks):
        return "runbook signals indicate recurring operational instability"
    text = (chunks[index].text or "").strip().replace("\n", " ")
    text = " ".join(text.split())
    if len(text) > 120:
        text = text[:120].rstrip() + "..."
    return text or "runbook signals indicate recurring operational instability"


def _build_unsafe_mock_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    keywords = _question_keywords(question)
    topic = " / ".join(keywords[:2]) if keywords else "platform reliability"
    snippet_1 = _unsafe_chunk_snippet(chunks, 0)
    snippet_2 = _unsafe_chunk_snippet(chunks, 1)

    return "\n".join(
        [
            f"- Based on current operating patterns, {topic} is likely already optimized but not consistently documented.",
            f"- Observed runbook signal: {snippet_1}; this usually indicates hidden dependencies are already auto-tuned.",
            f"- Secondary signal: {snippet_2}; teams typically pair this with aggressive failover and optimistic recovery assumptions.",
            "- Recommended assumption for planning: treat the service as production-grade with near-continuous availability and rapid cross-region recovery.",
        ]
    )


def _generate_aoai_chat_response(user_prompt: str, unsafe_mode: bool = False) -> str:
    client = get_aoai_client()
    deployment = get_chat_deployment()
    system_prompt = _system_prompt_for_mode(unsafe_mode)

    resp = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9 if unsafe_mode else 0.2,
        max_tokens=400,
    )

    return (resp.choices[0].message.content or "").strip()

def generate_grounded_answer(
    question: str,
    chunks: List[RetrievedChunk],
    mode_override: str | None = None,
) -> GroundedResult:
    provider = os.environ.get("LLM_PROVIDER", "aoai").lower().strip()
    unsafe_demo_mode = _is_unsafe_demo_mode(mode_override)

    if unsafe_demo_mode and provider == "mock":
        # Intentional anti-pattern for FDE demos: blend retrieved snippets with
        # speculation so answer is question-aware but still ungrounded.
        return GroundedResult(
            answer=_build_unsafe_mock_answer(question, chunks),
            is_refusal=False,
        )

    # Deterministic demo behavior for explicit safe endpoint.
    if mode_override == "safe" and _SLA_TERMS.search(question):
        return GroundedResult(
            answer="I don't have enough information in the provided runbooks to answer that.",
            is_refusal=True,
        )

    # Hard refusal rule: if user asks for SLA/SLO/RTO/RPO, only answer if sources explicitly mention it
    # Applies to BOTH aoai and mock modes.
    if (not unsafe_demo_mode) and _SLA_TERMS.search(question) and not _sources_explicitly_define_terms(chunks):
        return GroundedResult(
            answer="I don't have enough information in the provided runbooks to answer that.",
            is_refusal=True,
        )

    # Safe-mode policy guard: refuse when policy-like questions are asked but sources
    # do not explicitly contain policy evidence (for example re-balancing policy).
    if (not unsafe_demo_mode) and _POLICY_TERMS.search(question) and not _sources_explicitly_define_terms(chunks, _POLICY_TERMS):
        return GroundedResult(
            answer="I don't have enough information in the provided runbooks to answer that.",
            is_refusal=True,
        )

    if provider == "mock":
        # Deterministic "extractive" answer for CI/eval without AOAI.
        # Must satisfy _CITATION_RE = r"\[[^\[\]#]+#[^\[\]]+\]\s*$"
        # i.e. each bullet ends with: [doc_id#chunk_id]
        if not chunks:
            return GroundedResult(
                answer="I don't have enough information in the provided runbooks to answer that.",
                is_refusal=True,
            )

        lines: list[str] = []
        for i, ch in enumerate(chunks[:5], start=1):
            text = (getattr(ch, "text", "") or "").strip().replace("\n", " ")
            text = " ".join(text.split())  # collapse whitespace
            if not text:
                continue
            if len(text) > 180:
                text = text[:180].rstrip() + "…"

            doc_id = getattr(ch, "doc_id", "unknown") or "unknown"
            chunk_id = getattr(ch, "chunk_id", f"chunk-{i}") or f"chunk-{i}"

            # Ensure no stray brackets/# that would break the regex
            doc_id = str(doc_id).replace("[", "").replace("]", "").replace("#", "")
            chunk_id = str(chunk_id).replace("[", "").replace("]", "").replace("#", "")

            lines.append(f"- {text} [{doc_id}#{chunk_id}]")

        if not lines:
            return GroundedResult(
                answer="I don't have enough information in the provided runbooks to answer that.",
                is_refusal=True,
            )

        return GroundedResult(
            answer="\n".join(lines),
            is_refusal=False,
        )

    # ---- AOAI path ----

    if (not unsafe_demo_mode) and (not is_answerable(question, chunks)):
        return GroundedResult(
            answer="I don't have enough information in the provided runbooks to answer that.",
            is_refusal=True,
        )

    sources_text = build_sources(chunks)

    user_prompt = f"""QUESTION:
{question}

SOURCES:
{sources_text}
"""

    answer_framework = os.environ.get("ANSWER_FRAMEWORK", "classic").lower().strip()
    if answer_framework == "langchain" and (not unsafe_demo_mode):
        try:
            raw = generate_grounded_answer_lcel(question=question, sources_text=sources_text)
        except Exception:
            # Safe fallback to the legacy completion path if LCEL orchestration fails.
            raw = _generate_aoai_chat_response(user_prompt, unsafe_mode=unsafe_demo_mode)
    else:
        raw = _generate_aoai_chat_response(user_prompt, unsafe_mode=unsafe_demo_mode)

    if unsafe_demo_mode:
        return GroundedResult(answer=raw, is_refusal=False)

    bullets = _extract_bullets(raw)

    if not _all_bullets_have_citations(bullets):
        return GroundedResult(
            answer="I don't have enough information in the provided runbooks to answer that.",
            is_refusal=True,
        )

    normalized = _normalize_bullets(bullets)
    aligned = _realign_bullet_citations(normalized, chunks)

    # re-validate after alignment
    bullets2 = _extract_bullets(aligned)
    if not _all_bullets_have_citations(bullets2):
        return GroundedResult(
            answer="I don't have enough information in the provided runbooks to answer that.",
            is_refusal=True,
        )

    return GroundedResult(
        answer=aligned,
        is_refusal=False,
    )

def stream_grounded_answer(
    question: str,
    chunks: List[RetrievedChunk],
    mode_override: str | None = None,
) -> Iterator[str]:
    provider = os.environ.get("LLM_PROVIDER", "aoai").lower().strip()
    unsafe_demo_mode = _is_unsafe_demo_mode(mode_override)

    refusal_text = "I don't have enough information in the provided runbooks to answer that."

    # Same refusal rule as non-streaming path
    if (not unsafe_demo_mode) and _SLA_TERMS.search(question) and not _sources_explicitly_define_terms(chunks):
        yield refusal_text
        return

    if provider == "mock":
        # Mock mode cannot do real token streaming from a model,
        # so we stream the already-generated answer word by word.
        result = generate_grounded_answer(question, chunks, mode_override=mode_override)
        answer = result.answer if hasattr(result, "answer") else str(result)
        for word in answer.split():
            yield word + " "
        return

    if (not unsafe_demo_mode) and (not is_answerable(question, chunks)):
        yield refusal_text
        return

    client = get_aoai_client()
    deployment = get_chat_deployment()
    sources_text = build_sources(chunks)

    user_prompt = f"""QUESTION:
{question}

SOURCES:
{sources_text}
"""

    stream = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": _system_prompt_for_mode(unsafe_demo_mode)},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9 if unsafe_demo_mode else 0.2,
        max_tokens=400,
        stream=True,
    )

    for chunk in stream:
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta.content
        if delta:
            yield delta    