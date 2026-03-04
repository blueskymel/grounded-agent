from typing import Callable
from app.tools.incident_tools import create_incident_ticket, draft_change_plan
from app.tools.retail_tools import (
    draft_store_incident_summary,
    analyze_price_change,
    triage_low_stock,
    check_promo_compliance,
)

ToolFn = Callable[[dict], dict]

TOOL_REGISTRY: dict[str, ToolFn] = {
    "create_incident_ticket": create_incident_ticket,
    "draft_change_plan": draft_change_plan,
    "draft_store_incident_summary": draft_store_incident_summary,
    "analyze_price_change": analyze_price_change,
    "triage_low_stock": triage_low_stock,
    "check_promo_compliance": check_promo_compliance,
}


def run_tool(name: str, tool_input: dict) -> dict:
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool not allowed: {name}")
    return TOOL_REGISTRY[name](tool_input)