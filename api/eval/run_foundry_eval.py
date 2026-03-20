import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from eval.foundry_dataset import build_and_write_foundry_dataset


load_dotenv()


def _require_foundry_packages() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from azure.ai.evaluation import (
            CoherenceEvaluator,
            FluencyEvaluator,
            GroundednessEvaluator,
            RelevanceEvaluator,
            evaluate,
        )
    except ImportError as exc:
        raise SystemExit(
            "Missing Foundry evaluation dependencies. Install api/requirements.txt to add azure-ai-evaluation."
        ) from exc

    return evaluate, GroundednessEvaluator, RelevanceEvaluator, CoherenceEvaluator, FluencyEvaluator


def _model_config() -> dict[str, str]:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
    deployment = os.environ.get("FOUNDRY_EVAL_MODEL_DEPLOYMENT") or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")

    missing = [
        name
        for name, value in {
            "AZURE_OPENAI_ENDPOINT": endpoint,
            "AZURE_OPENAI_API_KEY": api_key,
            "AZURE_OPENAI_CHAT_DEPLOYMENT or FOUNDRY_EVAL_MODEL_DEPLOYMENT": deployment,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing environment variables for Foundry eval: {', '.join(missing)}")

    return {
        "azure_endpoint": endpoint,
        "api_key": api_key,
        "api_version": api_version,
        "azure_deployment": deployment,
    }


def _build_evaluator_config() -> dict[str, Any]:
    return {
        "groundedness": {
            "column_mapping": {
                "query": "${data.query}",
                "response": "${data.response}",
                "context": "${data.context}",
            }
        },
        "relevance": {
            "column_mapping": {
                "query": "${data.query}",
                "response": "${data.response}",
                "context": "${data.context}",
            }
        },
        "coherence": {
            "column_mapping": {
                "query": "${data.query}",
                "response": "${data.response}",
            }
        },
        "fluency": {
            "column_mapping": {
                "response": "${data.response}",
            }
        },
    }


def _summarize(result: dict[str, Any]) -> dict[str, Any]:
    metrics = result.get("metrics") or result.get("summary") or {}
    foundry_url = result.get("studio_url") or result.get("azure_ai_project_url")
    return {
        "metrics": metrics,
        "foundry_url": foundry_url,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Run only first N cases (0 = all)")
    parser.add_argument(
        "--dataset-path",
        default="eval/qa_dataset.json",
        help="Path to the repo's JSON eval cases",
    )
    parser.add_argument(
        "--jsonl-path",
        default="eval/foundry_eval_dataset.jsonl",
        help="Output JSONL path consumed by azure-ai-evaluation",
    )
    parser.add_argument(
        "--output-path",
        default="eval/foundry_eval_results.json",
        help="Output JSON summary written by azure-ai-evaluation",
    )
    parser.add_argument(
        "--refresh-dataset",
        action="store_true",
        help="Regenerate the JSONL dataset before running evaluators",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset_path)
    jsonl_path = Path(args.jsonl_path)
    output_path = Path(args.output_path)

    if args.refresh_dataset or not jsonl_path.exists():
        rows = build_and_write_foundry_dataset(dataset_path, jsonl_path, limit=args.limit)
        print(f"Prepared Foundry eval dataset with {len(rows)} rows at {jsonl_path}")

    evaluate, GroundednessEvaluator, RelevanceEvaluator, CoherenceEvaluator, FluencyEvaluator = (
        _require_foundry_packages()
    )

    model_config = _model_config()
    azure_ai_project = os.environ.get("AZURE_AI_PROJECT_ENDPOINT") or None

    result = evaluate(
        data=str(jsonl_path),
        evaluators={
            "groundedness": GroundednessEvaluator(model_config=model_config),
            "relevance": RelevanceEvaluator(model_config=model_config),
            "coherence": CoherenceEvaluator(model_config=model_config),
            "fluency": FluencyEvaluator(model_config=model_config),
        },
        evaluator_config=_build_evaluator_config(),
        azure_ai_project=azure_ai_project,
        output_path=str(output_path),
        tags={
            "app": "grounded-agent",
            "workflow": "foundry-eval",
            "backend": os.environ.get("RETRIEVAL_BACKEND", "faiss"),
        },
    )

    summary = _summarize(result)
    print("\n=== Foundry Eval Summary ===")
    print(json.dumps(summary["metrics"], indent=2))
    print(f"Saved raw evaluation output to {output_path}")
    if summary["foundry_url"]:
        print(f"Foundry results URL: {summary['foundry_url']}")
    elif azure_ai_project:
        print("Foundry project tracking was requested, but no portal URL was returned by the SDK.")
    else:
        print("Foundry project tracking disabled. Set AZURE_AI_PROJECT_ENDPOINT to log the run to a Foundry project.")


if __name__ == "__main__":
    main()