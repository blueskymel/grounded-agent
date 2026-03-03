import json
import os
import sys
import argparse
from pathlib import Path
# Ensure 'api/' is on PYTHONPATH so `import app...` works when running from api/eval
API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

import re
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from app.retrieval.factory import get_retriever
from app.llm.grounded_answer import generate_grounded_answer

load_dotenv()

REFUSAL_TEXT = "I don't have enough information in the provided runbooks to answer that."
CITATION_RE = re.compile(r"\[[^\[\]#]+#[^\[\]]+\]\s*$")

@dataclass
class EvalRowResult:
    id: str
    question: str
    backend: str
    retrieved_doc_ids: list[str]
    expected_doc_ids: list[str]
    should_refuse: bool
    refused: bool
    format_ok: bool
    recall_hit: bool
    latency_ms: int
    answer_preview: str

def extract_cited_doc_ids(answer: str) -> set[str]:
    # Extract doc_id from [doc_id#chunk_id]
    cites = re.findall(r"\[([^\[\]#]+)#[^\[\]]+\]", answer or "")
    return set(cites)

def answer_format_ok(answer: str) -> bool:
    if not answer:
        return False
    if answer.strip() == REFUSAL_TEXT:
        return True  # refusal is allowed
    lines = [ln.strip() for ln in answer.splitlines() if ln.strip()]
    if not lines:
        return False
    # bullets only
    if not all(ln.startswith("- ") for ln in lines):
        return False
    # each bullet ends with citation
    if not all(CITATION_RE.search(ln) for ln in lines):
        return False
    return True

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Run only first N cases (0 = all)")
    args = parser.parse_args()
    dataset_path = os.path.join("eval", "qa_dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)
        if args.limit and args.limit > 0:
            cases = cases[: args.limit]

    retriever = get_retriever()

    results: list[EvalRowResult] = []
    start_all = time.time()

    for case in cases:
        qid = case["id"]
        question = case["question"]
        expected = case.get("expected_doc_ids", [])
        should_refuse = bool(case.get("should_refuse", False))

        t0 = time.time()
        chunks = retriever.retrieve(question, top_k=5)
        retrieved_doc_ids = [c.doc_id for c in chunks]

        grounded = generate_grounded_answer(question, chunks)
        # Supports both string-returning and GroundedResult-returning versions
        if hasattr(grounded, "answer"):
            answer = grounded.answer
        else:
            answer = str(grounded)

        t1 = time.time()
        latency_ms = int((t1 - t0) * 1000)

        refused = answer.strip() == REFUSAL_TEXT
        format_ok = answer_format_ok(answer)

        # Recall@k (hit if ANY expected doc_id is retrieved)
        recall_hit = True
        if expected:
            recall_hit = any(doc in retrieved_doc_ids for doc in expected)

        results.append(
            EvalRowResult(
                id=qid,
                question=question,
                backend=os.environ.get("RETRIEVAL_BACKEND", "faiss"),
                retrieved_doc_ids=retrieved_doc_ids,
                expected_doc_ids=expected,
                should_refuse=should_refuse,
                refused=refused,
                format_ok=format_ok,
                recall_hit=recall_hit,
                latency_ms=latency_ms,
                answer_preview=(answer[:180] + "…") if len(answer) > 180 else answer,
            )
        )

    total_ms = int((time.time() - start_all) * 1000)

    # Summary
    n = len(results)
    recall_hits = sum(1 for r in results if r.recall_hit)
    format_hits = sum(1 for r in results if r.format_ok)
    refusal_correct = sum(1 for r in results if (r.refused == r.should_refuse))

    print("\n=== GroundedAgent Eval Summary ===")
    print(f"Backend: {os.environ.get('RETRIEVAL_BACKEND', 'faiss')}")
    print(f"Cases: {n}")
    print(f"Recall@5 hit rate: {recall_hits}/{n} = {recall_hits/n:.0%}")
    print(f"Format compliance: {format_hits}/{n} = {format_hits/n:.0%}")
    print(f"Refusal correctness: {refusal_correct}/{n} = {refusal_correct/n:.0%}")
    print(f"Total time: {total_ms} ms")

    print("\n=== Per-case ===")
    for r in results:
        status = []
        status.append("recall✅" if r.recall_hit else "recall❌")
        status.append("format✅" if r.format_ok else "format❌")
        status.append("refusal✅" if (r.refused == r.should_refuse) else "refusal❌")
        print(f"- {r.id}: {' | '.join(status)} | {r.latency_ms}ms | retrieved={list(dict.fromkeys(r.retrieved_doc_ids))}")
        print(f"  Q: {r.question}")
        print(f"  A: {r.answer_preview}")

    # Non-zero exit if something fails (good for CI later)
    failed = any(
        (not r.format_ok) or (r.refused != r.should_refuse) or (not r.recall_hit and len(r.expected_doc_ids) > 0)
        for r in results
    )
    if failed:
        raise SystemExit(1)

    report = {
    "backend": os.environ.get("RETRIEVAL_BACKEND", "faiss"),
    "cases": n,
    "recall_hit_rate": recall_hits / n if n else 0,
    "format_rate": format_hits / n if n else 0,
    "refusal_correct_rate": refusal_correct / n if n else 0,
    "total_ms": total_ms,
    }
    Path("eval").mkdir(exist_ok=True)
    Path("eval/report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()