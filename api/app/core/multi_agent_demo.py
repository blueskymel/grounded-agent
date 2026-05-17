"""
Multi-agent planner/executor demo for LangGraph agent framework.
- Planner agent: parses message, creates a plan (list of tool actions)
- Executor agent: executes each tool action in sequence, collects results
- For demo, both agents are simple Python functions; can be nodes in a LangGraph
"""
from typing import List, Dict, Any
from app.tools.registry import run_tool

# Simple plan step: tool name and input
class PlanStep(Dict[str, Any]):
    pass

def planner_agent(message: str) -> List[PlanStep]:
    # For demo: if message contains 'price' and 'stock', plan both actions
    plan = []
    if 'price' in message:
        plan.append({
            'tool_name': 'analyze_price_change',
            'tool_input': {'sku': 'SKU123', 'old_price': 10, 'new_price': 12}
        })
    if 'stock' in message:
        plan.append({
            'tool_name': 'triage_low_stock',
            'tool_input': {'store_id': '2045', 'sku': 'SKU777', 'on_hand': 3}
        })
    if not plan:
        plan.append({'tool_name': 'retrieve', 'tool_input': {}})
    return plan

def executor_agent(plan: List[PlanStep]) -> List[Dict[str, Any]]:
    results = []
    for step in plan:
        tool_name = step['tool_name']
        tool_input = step['tool_input']
        result = run_tool(tool_name, tool_input)
        results.append({'tool': tool_name, 'input': tool_input, 'output': result})
    return results

# Demo entrypoint

def run_multi_agent_demo(message: str) -> List[Dict[str, Any]]:
    plan = planner_agent(message)
    results = executor_agent(plan)
    return results
