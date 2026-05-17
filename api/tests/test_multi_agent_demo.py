"""
Test for multi-agent planner/executor demo.
"""
from app.core.multi_agent_demo import run_multi_agent_demo

def test_multi_agent_demo():
    # Message that triggers both planner steps
    message = "Analyze price and stock for SKU123"
    results = run_multi_agent_demo(message)
    print("Results:", results)
    assert any(r['tool'] == 'analyze_price_change' for r in results)
    assert any(r['tool'] == 'triage_low_stock' for r in results)
    # Message that triggers only one
    message2 = "Check price for SKU123"
    results2 = run_multi_agent_demo(message2)
    assert any(r['tool'] == 'analyze_price_change' for r in results2)
    # Message that triggers fallback
    message3 = "Just say hi"
    results3 = run_multi_agent_demo(message3)
    assert any(r['tool'] == 'retrieve' for r in results3)

if __name__ == "__main__":
    test_multi_agent_demo()
