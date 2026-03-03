from typing import Any

def summarize_tool_calls(tool_calls: list[dict[str, Any]] | None) -> dict[str, Any]:
    tool_calls = tool_calls or []
    names = [tc.get("name") for tc in tool_calls if tc.get("name")]
    return {"tool_calls_count": len(tool_calls), "tool_names": names}