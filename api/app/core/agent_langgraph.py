import time
from typing import Any, TypedDict
from app.core.memory_dashboard import update_dashboard

class AgentState(TypedDict, total=False):
    message: str
    retrieval_backend: str
    intent_name: str
    tool_name: str
    tool_input: dict[str, Any]
    answer: str
    tool_calls: list[dict[str, Any]]
    memory: 'ConversationMemory'
    semantic_memory: 'SemanticMemory'

# List of tool names that require human approval before execution
TOOLS_REQUIRING_APPROVAL = {"analyze_price_change", "draft_store_incident_summary"}

def _human_approval(state: AgentState) -> AgentState:
    tool_name = state.get("tool_name")
    tool_input = state.get("tool_input")
    # In a real system, this would trigger a UI or notification for human approval
    print(f"[APPROVAL NEEDED] Tool: {tool_name}, Input: {tool_input}")
    # Simulate waiting for human approval (replace with async/queue in prod)
    approved = True  # For demo, auto-approve; replace with real check
    if approved:
        print(f"[APPROVED] Tool: {tool_name}")
        return state
    else:
        print(f"[REJECTED] Tool: {tool_name}")
        return {"answer": f"Action '{tool_name}' was rejected by human approver.", "tool_calls": []}

from langgraph.graph import END, StateGraph
from app.core.memory import ConversationMemory
from app.core.semantic_memory import SemanticMemory
import numpy as np
def dummy_embed(text: str):
    # Simple embedding stub: hash chars to vector for demo; replace with real model in prod
    arr = np.zeros(384)
    for i, c in enumerate(text):
        arr[i % 384] += ord(c)
    return arr

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
    memory: ConversationMemory
def default_summariser(history):
    # Simple concatenation summariser for demo; replace with LLM call for enterprise
    turns = [f"User: {turn['message']}" + (f"\nAgent: {turn.get('agent_response','')}" if 'agent_response' in turn else '') for turn in history]
    return '\n'.join(turns)[-1024:]



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
    memory = state.get("memory")
    intent = parse_intent(message)

    # Add user turn to memory
    if memory:
        memory.add_turn(user="user", message=message)

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
    tool_name = state.get("tool_name")
    if tool_name == "retrieve":
        return "retrieve_fallback"
    if tool_name in TOOLS_REQUIRING_APPROVAL:
        return "human_approval"
    return "run_tool"


def run_agent_langgraph(message: str, retrieval_backend: str) -> tuple[str, list[dict[str, Any]]]:
    graph = StateGraph(AgentState)
    graph.add_node("resolve_action", _resolve_action)

    graph.add_node("run_tool", _run_tool)
    graph.add_node("retrieve_fallback", _retrieve_fallback)
    graph.add_node("human_approval", _human_approval)

    graph.set_entry_point("resolve_action")
    graph.add_conditional_edges(
        "resolve_action",
        _route_tool_or_retrieve,
        {
            "run_tool": "run_tool",
            "retrieve": "retrieve_fallback",
            "human_approval": "human_approval",
        },
    )
    graph.add_edge("run_tool", END)
    graph.add_edge("retrieve_fallback", END)
    graph.add_edge("human_approval", "run_tool")


    # Attach conversation memory and semantic memory
    memory = ConversationMemory()
    semantic_memory = SemanticMemory(embedding_fn=dummy_embed, dim=384)

    # Initial state

    state: AgentState = {
        "message": message,
        "retrieval_backend": retrieval_backend,
        "tool_calls": [],
        "memory": memory,
        "semantic_memory": semantic_memory,
    }

    # Compile and run the graph
    compiled = graph.compile()
    state = compiled.invoke(state)

    # Demo: Add decision/fact to semantic memory after each run
    semantic_memory.add_entry(
        text=state.get("answer", ""),
        meta={"tool_calls": state.get("tool_calls", [])}
    )

    # Demo: Retrieve prior similar facts/decisions
    retrievals = semantic_memory.search(message, top_k=2)
    for r in retrievals:
        r['why'] = f"Similar to: {message[:40]}..."

    # Summarise after run for visibility/demo
    summary = memory.summarise(default_summariser)

    # Token savings (demo: difference between full history and summary)
    history_tokens = sum(len(turn['message']) + len(turn.get('agent_response','')) for turn in memory.get_recent_history())
    summary_tokens = len(summary)
    token_savings = max(history_tokens - summary_tokens, 0)

    # Summarisation lifecycle (demo: always 'updated' after each run)
    lifecycle = f"Summary updated after user message: '{message[:40]}...'"

    # Update dashboard state
    update_dashboard(
        summary=summary,
        retrievals=retrievals,
        token_savings=token_savings,
        lifecycle=lifecycle
    )

    print("Conversation summary (demo):\n", summary)
    print("Semantic memory retrievals (demo):")
    for r in retrievals:
        print(f"- {r['text']} (score={r['score']:.2f})")

    return state.get("answer", ""), state.get("tool_calls", [])