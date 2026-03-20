import argparse
import os
from pathlib import Path
from typing import Any


def _require_azureml_packages() -> tuple[Any, Any, Any]:
    try:
        from azure.ai.ml import MLClient, command
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise SystemExit(
            "Missing Azure ML dependencies. Install azure-ai-ml and azure-identity to submit AML jobs."
        ) from exc

    return MLClient, command, DefaultAzureCredential


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compute", default="cpu-cluster", help="Azure ML compute target name")
    parser.add_argument("--experiment", default="grounded-agent-eval", help="Azure ML experiment name")
    parser.add_argument("--limit", type=int, default=25, help="Eval case limit")
    parser.add_argument("--min-recall", type=float, default=0.80)
    parser.add_argument("--min-format", type=float, default=0.95)
    parser.add_argument("--min-refusal", type=float, default=0.95)
    args = parser.parse_args()

    subscription_id = _require_env("AZURE_SUBSCRIPTION_ID")
    resource_group = _require_env("AZURE_ML_RESOURCE_GROUP")
    workspace_name = _require_env("AZURE_ML_WORKSPACE_NAME")

    MLClient, command, DefaultAzureCredential = _require_azureml_packages()

    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name,
    )

    eval_cmd = command(
        code=str(Path(__file__).resolve().parents[1]),
        command=(
            "python -m pip install --upgrade pip && "
            "pip install -r requirements.txt && "
            "python -m ingest.build_faiss_index --input_dir fixtures/raw --out_dir data/index --provider mock && "
            f"python -m eval.run_eval --limit {args.limit} && "
            f"python -m eval.gate --min_recall {args.min_recall} --min_format {args.min_format} --min_refusal {args.min_refusal} && "
            "cp eval/report.json ${{outputs.eval_report}}/report.json"
        ),
        environment="AzureML-sklearn-1.5:1",
        compute=args.compute,
        experiment_name=args.experiment,
        display_name="grounded-agent-eval-gate",
        outputs={"eval_report": {"type": "uri_folder"}},
    )

    created = ml_client.jobs.create_or_update(eval_cmd)
    print(f"Submitted Azure ML eval job: {created.name}")
    print(f"Status: {created.status}")
    print("Open in Studio:")
    print(created.studio_url)


if __name__ == "__main__":
    main()
