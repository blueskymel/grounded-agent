import os
from typing import List, Iterator
from app.retrieval.base import RetrievedChunk
from app.llm.client import get_aoai_client, get_chat_deployment
from app.llm.langchain_answer_chain import generate_grounded_answer_lcel
from dataclasses import dataclass
import re

_SLA_TERMS = re.compile(r"\b(sla|slo|rto|rpo)\b", re.IGNORECASE)

@dataclass
class GroundedResult:
    answer: str
    is_refusal: bool

SYSTEM_PROMPT = """You are GroundedAgent, an IT Ops assistant.

NON-NEGOTIABLE RULES:
- Use ONLY the provided SOURCES. Do not use outside knowledge.
- Output MUST be a bulleted list (each line starts with "- ").
- EACH bullet MUST end with one or more citations in the form [doc_id#chunk_id].
- Do NOT cite a chunk that does not contain the claim.
- If the question asks for info not explicitly stated in the sources (e.g., SLA/SLO/RTO/RPO), answer exactly:
  "I don't have enough information in the provided runbooks to answer that."

STYLE:
- Be concise and action-oriented.
- 3-7 bullets max.

OUTPUT FORMAT EXAMPLE (follow exactly):
- First action step. [doc_id#chunk_id]
- Second action step. [doc_id#chunk_id][doc_id#chunk_id]
"""

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


def _generate_aoai_chat_response(user_prompt: str) -> str:
    client = get_aoai_client()
    deployment = get_chat_deployment()

    resp = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=400,
    )

    return (resp.choices[0].message.content or "").strip()

def generate_grounded_answer(question: str, chunks: List[RetrievedChunk]) -> GroundedResult:
    provider = os.environ.get("LLM_PROVIDER", "aoai").lower().strip()

    # Hard refusal rule: if user asks for SLA/SLO/RTO/RPO, only answer if sources explicitly mention it
    # Applies to BOTH aoai and mock modes.
    if _SLA_TERMS.search(question) and not _sources_explicitly_define_terms(chunks):
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

    if not is_answerable(question, chunks):
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
    if answer_framework == "langchain":
        try:
            raw = generate_grounded_answer_lcel(question=question, sources_text=sources_text)
        except Exception:
            # Safe fallback to the legacy completion path if LCEL orchestration fails.
            raw = _generate_aoai_chat_response(user_prompt)
    else:
        raw = _generate_aoai_chat_response(user_prompt)

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

def stream_grounded_answer(question: str, chunks: List[RetrievedChunk]) -> Iterator[str]:
    provider = os.environ.get("LLM_PROVIDER", "aoai").lower().strip()

    refusal_text = "I don't have enough information in the provided runbooks to answer that."

    # Same refusal rule as non-streaming path
    if _SLA_TERMS.search(question) and not _sources_explicitly_define_terms(chunks):
        yield refusal_text
        return

    if provider == "mock":
        # Mock mode cannot do real token streaming from a model,
        # so we stream the already-generated answer word by word.
        result = generate_grounded_answer(question, chunks)
        answer = result.answer if hasattr(result, "answer") else str(result)
        for word in answer.split():
            yield word + " "
        return

    if not is_answerable(question, chunks):
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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=400,
        stream=True,
    )

    for chunk in stream:
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta.content
        if delta:
            yield delta    