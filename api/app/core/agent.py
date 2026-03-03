from dataclasses import dataclass
from app.tools.registry import run_tool


@dataclass
class PlanResult:
    answer: str
    tool_calls: list[dict]


def simple_plan(message: str) -> tuple[str, dict | None]:
    """
    Very small heuristic planner:
    - If user asks to 'create ticket' -> tool call
    - If user asks for 'change plan' -> tool call
    - Retail:
      - If user asks for store incident summary -> tool call
      - If user asks for price change impact -> tool call
    - Otherwise -> retrieval + answer (stub for now)
    """
    m = message.lower()

    if "create" in m and "ticket" in m:
        return "create_incident_ticket", {"title": message, "severity": "P1"}

    if "change plan" in m or "rollout plan" in m:
        return "draft_change_plan", {"title": "Change Plan", "summary": message}

    # Retail: store incident summary
    if "store incident" in m or ("incident" in m and "store" in m and "summary" in m):
        # lightweight parsing: store id like "store 1234"
        store_id = "unknown"
        for token in m.replace("#", " ").split():
            if token.isdigit() and len(token) >= 3:
                store_id = token
                break
        return "draft_store_incident_summary", {
            "store_id": store_id,
            "incident_type": "unspecified",
            "duration_minutes": 0,
        }

    # Retail: price change impact
    if "price change" in m or ("impact" in m and "price" in m):
        return "analyze_price_change", {
            "sku": "unknown",
            "old_price": 0,
            "new_price": 0,
        }

    return "retrieve", None


def run_agent(message: str, retrieval_backend: str) -> PlanResult:
    action, tool_input = simple_plan(message)

    if action == "retrieve":
        # retrieval + LLM later; stub for now
        return PlanResult(
            answer=f"(stub) I will retrieve runbook context for: {message}",
            tool_calls=[],
        )

    output = run_tool(action, tool_input or {})
    return PlanResult(
        answer=f"(tool) Ran {action}",
        tool_calls=[{"name": action, "input": tool_input or {}, "output": output}],
    )