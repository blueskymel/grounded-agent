import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))
load_dotenv()

from app.llm.grounded_answer import generate_grounded_answer  # noqa: E402
from app.retrieval.factory import get_retriever  # noqa: E402


@dataclass
class FoundryEvalRow:
    id: str
    query: str
    response: str
    context: str
    expected_doc_ids: list[str]
    should_refuse: bool
    format_required: bool
    recall_required: bool
    retrieved_doc_ids: list[str]
    latency_ms: int


def _chunk_context(chunks: list[Any]) -> str:
    lines: list[str] = []
    for chunk in chunks:
        doc_id = getattr(chunk, "doc_id", "unknown")
        chunk_id = getattr(chunk, "chunk_id", "chunk")
        text = getattr(chunk, "text", "") or ""
        normalized = " ".join(text.split())
        lines.append(f"[{doc_id}#{chunk_id}] {normalized}")
    return "\n".join(lines)


def build_foundry_eval_rows(cases: list[dict[str, Any]]) -> list[FoundryEvalRow]:
    retriever = get_retriever()
    rows: list[FoundryEvalRow] = []

    for case in cases:
        started = time.time()
        question = case["question"]
        chunks = retriever.retrieve(question, top_k=5)
        grounded = generate_grounded_answer(question, chunks)
        answer = grounded.answer if hasattr(grounded, "answer") else str(grounded)

        rows.append(
            FoundryEvalRow(
                id=case["id"],
                query=question,
                response=answer,
                context=_chunk_context(chunks),
                expected_doc_ids=case.get("expected_doc_ids", []),
                should_refuse=bool(case.get("should_refuse", False)),
                format_required=bool(case.get("format_required", True)),
                recall_required=bool(case.get("recall_required", bool(case.get("expected_doc_ids", [])))),
                retrieved_doc_ids=[getattr(chunk, "doc_id", "unknown") for chunk in chunks],
                latency_ms=int((time.time() - started) * 1000),
            )
        )

    return rows


def load_cases(dataset_path: Path, limit: int = 0) -> list[dict[str, Any]]:
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    if limit > 0:
        cases = cases[:limit]
    return cases


def write_rows_jsonl(rows: list[FoundryEvalRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), ensure_ascii=True) + "\n")


def build_and_write_foundry_dataset(
    dataset_path: Path,
    output_path: Path,
    *,
    limit: int = 0,
) -> list[FoundryEvalRow]:
    cases = load_cases(dataset_path, limit=limit)
    rows = build_foundry_eval_rows(cases)
    write_rows_jsonl(rows, output_path)
    return rows