from dataclasses import dataclass
from app.tools.registry import run_tool
from app.agent.intent_parser import parse_intent

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
    intent = parse_intent(message)

    def _tool_result(tool_name: str, tool_input: dict) -> PlanResult:
        output = run_tool(tool_name, tool_input)
        return PlanResult(
            answer=f"(tool) Ran {tool_name}",
            tool_calls=[{"name": tool_name, "input": tool_input, "output": output}],
        )

    # ---- Intent-first deterministic routing ----
    if intent and intent.name == "LOW_STOCK_TRIAGE":
        tool_input = {
            "store_id": intent.store_id,
            "sku": intent.sku,
            "on_hand": intent.on_hand,
            "forecast_per_day": intent.forecast_per_day,
            "lead_time_days": intent.lead_time_days,
        }
        return _tool_result("triage_low_stock", tool_input)

    if intent and intent.name == "PROMO_COMPLIANCE_CHECK":
        tool_input = {
            "promo_id": intent.promo_id,
            "sku": intent.sku,
            "price": intent.price,
            "channel": intent.channel,
        }
        return _tool_result("check_promo_compliance", tool_input)

    if intent and intent.name == "ANALYZE_PRICE_CHANGE":
        tool_input = {
            "sku": intent.sku,
            "old_price": intent.old_price,
            "new_price": intent.new_price,
        }
        return _tool_result("analyze_price_change", tool_input)

    if intent and intent.name in ("STORE_INCIDENT", "DRAFT_STORE_INCIDENT_SUMMARY"):
        tool_input = {
            "store_id": intent.store_id,
            "incident_type": intent.incident_type,
            "duration_minutes": intent.duration_minutes,
        }
        return _tool_result("draft_store_incident_summary", tool_input)

    # ---- Fallback heuristic planner ----
    action, tool_input = simple_plan(message)

    if action == "retrieve":
        return PlanResult(
            answer=f"(stub) I will retrieve runbook context for: {message}",
            tool_calls=[],
        )

    return _tool_result(action, tool_input or {})