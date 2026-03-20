from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.intent_parser import parse_intent
from app.tools.registry import run_tool


class AgentState(TypedDict, total=False):
    message: str
    retrieval_backend: str
    intent_name: str
    tool_name: str
    tool_input: dict[str, Any]
    answer: str
    tool_calls: list[dict[str, Any]]


def _simple_plan(message: str) -> tuple[str, dict | None]:
    m = message.lower()

    if "create" in m and "ticket" in m:
        return "create_incident_ticket", {"title": message, "severity": "P1"}

    if "change plan" in m or "rollout plan" in m:
        return "draft_change_plan", {"title": "Change Plan", "summary": message}

    if "store incident" in m or ("incident" in m and "store" in m and "summary" in m):
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

    if "price change" in m or ("impact" in m and "price" in m):
        return "analyze_price_change", {
            "sku": "unknown",
            "old_price": 0,
            "new_price": 0,
        }

    return "retrieve", None


def _resolve_action(state: AgentState) -> AgentState:
    message = state["message"]
    intent = parse_intent(message)

    if intent and intent.name == "LOW_STOCK_TRIAGE":
        return {
            "tool_name": "triage_low_stock",
            "tool_input": {
                "store_id": intent.store_id,
                "sku": intent.sku,
                "on_hand": intent.on_hand,
                "forecast_per_day": intent.forecast_per_day,
                "lead_time_days": intent.lead_time_days,
            },
        }

    if intent and intent.name == "PROMO_COMPLIANCE_CHECK":
        return {
            "tool_name": "check_promo_compliance",
            "tool_input": {
                "promo_id": intent.promo_id,
                "sku": intent.sku,
                "price": intent.price,
                "channel": intent.channel,
            },
        }

    if intent and intent.name == "ANALYZE_PRICE_CHANGE":
        return {
            "tool_name": "analyze_price_change",
            "tool_input": {
                "sku": intent.sku,
                "old_price": intent.old_price,
                "new_price": intent.new_price,
            },
        }

    if intent and intent.name in ("STORE_INCIDENT", "DRAFT_STORE_INCIDENT_SUMMARY"):
        return {
            "tool_name": "draft_store_incident_summary",
            "tool_input": {
                "store_id": intent.store_id,
                "incident_type": intent.incident_type,
                "duration_minutes": intent.duration_minutes,
            },
        }

    action, tool_input = _simple_plan(message)
    if action == "retrieve":
        return {
            "tool_name": "retrieve",
            "tool_input": {},
        }

    return {
        "tool_name": action,
        "tool_input": tool_input or {},
    }


def _run_tool(state: AgentState) -> AgentState:
    tool_name = state["tool_name"]
    tool_input = state.get("tool_input") or {}
    output = run_tool(tool_name, tool_input)
    return {
        "answer": f"(tool) Ran {tool_name}",
        "tool_calls": [{"name": tool_name, "input": tool_input, "output": output}],
    }


def _retrieve_fallback(state: AgentState) -> AgentState:
    message = state["message"]
    return {
        "answer": f"(stub) I will retrieve runbook context for: {message}",
        "tool_calls": [],
    }


def _route_tool_or_retrieve(state: AgentState) -> str:
    if state.get("tool_name") == "retrieve":
        return "retrieve_fallback"
    return "run_tool"


def run_agent_langgraph(message: str, retrieval_backend: str) -> tuple[str, list[dict[str, Any]]]:
    graph = StateGraph(AgentState)
    graph.add_node("resolve_action", _resolve_action)
    graph.add_node("run_tool", _run_tool)
    graph.add_node("retrieve_fallback", _retrieve_fallback)

    graph.set_entry_point("resolve_action")
    graph.add_conditional_edges(
        "resolve_action",
        _route_tool_or_retrieve,
        {
            "run_tool": "run_tool",
            "retrieve_fallback": "retrieve_fallback",
        },
    )
    graph.add_edge("run_tool", END)
    graph.add_edge("retrieve_fallback", END)

    app = graph.compile()
    result = app.invoke({"message": message, "retrieval_backend": retrieval_backend})
    return result.get("answer", ""), result.get("tool_calls", [])