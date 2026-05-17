def retrieve_stub(tool_input: dict) -> dict:
    return {"ok": True, "tool": "retrieve", "result": f"Stub retrieval for: {tool_input}"}
from typing import Callable
from app.tools.incident_tools import create_incident_ticket, draft_change_plan
from app.tools.retail_tools import (
    draft_store_incident_summary,
    analyze_price_change,
    triage_low_stock,
    check_promo_compliance,
)
from app.tools.tool_schemas import (
    AnalyzePriceChangeInput,
    TriageLowStockInput,
    DraftStoreIncidentSummaryInput,
    CheckPromoComplianceInput,
)
from pydantic import ValidationError


ToolFn = Callable[[dict], dict]

TOOL_REGISTRY: dict[str, ToolFn] = {
    "create_incident_ticket": create_incident_ticket,
    "draft_change_plan": draft_change_plan,
    "draft_store_incident_summary": draft_store_incident_summary,
    "analyze_price_change": analyze_price_change,
    "triage_low_stock": triage_low_stock,
    "check_promo_compliance": check_promo_compliance,
    "retrieve": retrieve_stub,
}

# Tool input schemas for contract enforcement
TOOL_INPUT_SCHEMAS = {
    "analyze_price_change": AnalyzePriceChangeInput,
    "triage_low_stock": TriageLowStockInput,
    "draft_store_incident_summary": DraftStoreIncidentSummaryInput,
    "check_promo_compliance": CheckPromoComplianceInput,
}


def run_tool(name: str, tool_input: dict) -> dict:
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool not allowed: {name}")
    # Enforce input contract if schema exists
    schema = TOOL_INPUT_SCHEMAS.get(name)
    if schema:
        try:
            validated = schema(**tool_input)
            tool_input = validated.dict()
        except ValidationError as e:
            return {"ok": False, "error": f"Input validation failed: {e.errors()}"}
    return TOOL_REGISTRY[name](tool_input)