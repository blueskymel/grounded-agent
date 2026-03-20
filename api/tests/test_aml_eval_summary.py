from eval.summarize_aml_eval_report import build_summary, to_markdown


def test_build_summary_pass_and_markdown_contains_table():
    report = {
        "backend": "faiss",
        "cases": 25,
        "recall_hit_rate": 0.84,
        "format_rate": 0.98,
        "refusal_correct_rate": 0.96,
        "total_ms": 1234,
    }

    summary = build_summary(
        report,
        min_recall=0.80,
        min_format=0.95,
        min_refusal=0.95,
    )

    assert summary["all_passed"] is True
    assert summary["checks"]["recall"]["passed"] is True

    md = to_markdown(summary)
    assert "# Azure ML Eval Summary" in md
    assert "| Metric | Actual | Min | Status |" in md
    assert "| recall |" in md
