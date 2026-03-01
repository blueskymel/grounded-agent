from typing import Callable, Any
from app.tools.incident_tools import create_incident_ticket, draft_change_plan

ToolFn = Callable[[dict], dict]

TOOL_REGISTRY: dict[str, ToolFn] = {
    "create_incident_ticket": create_incident_ticket,
    "draft_change_plan": draft_change_plan,
}


def run_tool(name: str, tool_input: dict) -> dict:
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool not allowed: {name}")
    return TOOL_REGISTRY[name](tool_input)