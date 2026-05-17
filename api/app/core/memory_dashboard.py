"""
FastAPI endpoint for Memory Observability Dashboard
- Serves dashboard data for web UI
- Demo: returns summary, retrievals, token savings, lifecycle
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
import os

router = APIRouter()

# These would be replaced with real memory objects in a live agent
DASHBOARD_STATE = {
    "summary": "No summary yet.",
    "retrievals": [],
    "token_savings": 0,
    "lifecycle": "Idle",
    "tool_stats": [],  # List of tool call stats: name, retries, error (if any)
}

@router.get("/memory_dashboard")
def dashboard_page():
    path = os.path.join(os.path.dirname(__file__), "index.html")
    return FileResponse(path)

@router.get("/memory_dashboard/data")
def dashboard_data():
    return JSONResponse(DASHBOARD_STATE)

# Utility to update dashboard state from agent code

def update_dashboard(summary, retrievals, token_savings, lifecycle, tool_stats=None):
    DASHBOARD_STATE["summary"] = summary
    DASHBOARD_STATE["retrievals"] = retrievals
    DASHBOARD_STATE["token_savings"] = token_savings
    DASHBOARD_STATE["lifecycle"] = lifecycle
    if tool_stats is not None:
        DASHBOARD_STATE["tool_stats"] = tool_stats
