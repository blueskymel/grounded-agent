import argparse, json
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", default="eval/report.json")
    p.add_argument("--min_recall", type=float, default=0.85)
    p.add_argument("--min_format", type=float, default=0.95)
    p.add_argument("--min_refusal", type=float, default=0.95)
    args = p.parse_args()

    rpt = json.loads(Path(args.report).read_text(encoding="utf-8"))

    def chk(name, val, minv):
        if val < minv:
            raise SystemExit(f"{name} too low: {val:.3f} < {minv:.3f}")

    chk("recall_hit_rate", rpt["recall_hit_rate"], args.min_recall)
    chk("format_rate", rpt["format_rate"], args.min_format)
    chk("refusal_correct_rate", rpt["refusal_correct_rate"], args.min_refusal)

    print("Eval thresholds passed.")

if __name__ == "__main__":
    main()