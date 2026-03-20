import os
import time
from typing import Any


def _require_foundry_agent_packages() -> tuple[Any, Any]:
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "Missing Foundry hosted-agent dependencies. Install azure-ai-projects and azure-identity."
        ) from exc

    return AIProjectClient, DefaultAzureCredential


def _extract_assistant_text(messages: Any) -> str:
    for msg in messages:
        role = getattr(msg, "role", None)
        if role != "assistant":
            continue

        content_items = getattr(msg, "content", None) or []
        text_parts: list[str] = []
        for item in content_items:
            text_value = getattr(getattr(item, "text", None), "value", None)
            if text_value:
                text_parts.append(str(text_value))

        if text_parts:
            return "\n".join(text_parts).strip()

    return ""


def run_agent_foundry(message: str, retrieval_backend: str) -> tuple[str, list[dict[str, Any]]]:
    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    agent_id = os.environ.get("FOUNDRY_AGENT_ID")
    timeout_s = int(os.environ.get("FOUNDRY_AGENT_TIMEOUT_SECONDS", "90"))
    poll_interval_s = float(os.environ.get("FOUNDRY_AGENT_POLL_SECONDS", "2"))

    if not endpoint or not agent_id:
        raise RuntimeError("Set AZURE_AI_PROJECT_ENDPOINT and FOUNDRY_AGENT_ID for hosted Foundry agent mode.")

    AIProjectClient, DefaultAzureCredential = _require_foundry_agent_packages()

    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    thread = client.agents.create_thread()
    client.agents.create_message(thread_id=thread.id, role="user", content=message)
    run = client.agents.create_run(thread_id=thread.id, agent_id=agent_id)

    started = time.time()
    run_status = getattr(run, "status", "unknown")

    while time.time() - started < timeout_s:
        run = client.agents.get_run(thread_id=thread.id, run_id=run.id)
        run_status = getattr(run, "status", "unknown")
        if run_status in {"completed", "failed", "cancelled", "expired"}:
            break
        time.sleep(poll_interval_s)

    if run_status != "completed":
        raise RuntimeError(f"Foundry run did not complete successfully (status={run_status}).")

    messages = client.agents.list_messages(thread_id=thread.id)
    answer = _extract_assistant_text(messages)
    if not answer:
        raise RuntimeError("Foundry run completed but returned no assistant text.")

    tool_calls = [
        {
            "name": "foundry_hosted_agent",
            "input": {
                "message": message,
                "agent_id": agent_id,
                "retrieval_backend": retrieval_backend,
            },
            "output": {
                "thread_id": thread.id,
                "run_id": run.id,
                "status": run_status,
            },
        }
    ]

    return answer, tool_calls
