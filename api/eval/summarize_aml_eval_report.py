import argparse
import json
from pathlib import Path
from typing import Any


def load_report(report_path: Path) -> dict[str, Any]:
    return json.loads(report_path.read_text(encoding="utf-8"))


def build_summary(
    report: dict[str, Any],
    *,
    min_recall: float,
    min_format: float,
    min_refusal: float,
) -> dict[str, Any]:
    recall = float(report.get("recall_hit_rate", 0.0))
    format_rate = float(report.get("format_rate", 0.0))
    refusal = float(report.get("refusal_correct_rate", 0.0))

    checks = {
        "recall": {"actual": recall, "min": min_recall, "passed": recall >= min_recall},
        "format": {"actual": format_rate, "min": min_format, "passed": format_rate >= min_format},
        "refusal": {"actual": refusal, "min": min_refusal, "passed": refusal >= min_refusal},
    }

    return {
        "backend": report.get("backend", "unknown"),
        "cases": int(report.get("cases", 0)),
        "total_ms": int(report.get("total_ms", 0)),
        "checks": checks,
        "all_passed": all(c["passed"] for c in checks.values()),
    }


def to_markdown(summary: dict[str, Any]) -> str:
    checks = summary["checks"]

    def pct(v: float) -> str:
        return f"{v * 100:.1f}%"

    lines = [
        "# Azure ML Eval Summary",
        "",
        f"- Backend: `{summary['backend']}`",
        f"- Cases: `{summary['cases']}`",
        f"- Total time: `{summary['total_ms']} ms`",
        f"- Overall gate: `{'PASS' if summary['all_passed'] else 'FAIL'}`",
        "",
        "| Metric | Actual | Min | Status |",
        "|---|---:|---:|---|",
    ]

    for name in ("recall", "format", "refusal"):
        chk = checks[name]
        lines.append(
            f"| {name} | {pct(chk['actual'])} | {pct(chk['min'])} | {'PASS' if chk['passed'] else 'FAIL'} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="eval/report.json", help="Path to eval report JSON")
    parser.add_argument("--out-json", default="eval/aml_eval_summary.json", help="Output summary JSON path")
    parser.add_argument("--out-md", default="eval/aml_eval_summary.md", help="Output summary markdown path")
    parser.add_argument("--min-recall", type=float, default=0.80)
    parser.add_argument("--min-format", type=float, default=0.95)
    parser.add_argument("--min-refusal", type=float, default=0.95)
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        raise SystemExit(f"Report file not found: {report_path}")

    summary = build_summary(
        load_report(report_path),
        min_recall=args.min_recall,
        min_format=args.min_format,
        min_refusal=args.min_refusal,
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    out_md.write_text(to_markdown(summary), encoding="utf-8")

    print(f"Wrote summary JSON: {out_json}")
    print(f"Wrote summary markdown: {out_md}")
    print(f"Overall gate: {'PASS' if summary['all_passed'] else 'FAIL'}")


if __name__ == "__main__":
    main()
