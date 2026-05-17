"""
Demo/test for human approval workflow in agent_langgraph.
"""
from app.core.agent_langgraph import run_agent_langgraph

def test_human_approval_demo():
    # This message triggers a tool that requires approval
    message = "Please analyze the price change for SKU 123. Old price 10, new price 15."
    answer, tool_calls = run_agent_langgraph(message, retrieval_backend="faiss")
    print("Answer:", answer)
    print("Tool calls:", tool_calls)
    assert any(tc["name"] == "analyze_price_change" for tc in tool_calls)
    assert "APPROVAL" in answer or "Ran" in answer

if __name__ == "__main__":
    test_human_approval_demo()
