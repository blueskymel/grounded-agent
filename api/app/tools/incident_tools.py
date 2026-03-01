from datetime import datetime
from pathlib import Path
import json


def create_incident_ticket(payload: dict) -> dict:
    """
    Mock ticket creation tool.
    Writes a JSON file locally (api/data/tickets/...) and returns the ticket id.
    """
    tickets_dir = Path("data") / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)

    ticket_id = f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    record = {
        "ticket_id": ticket_id,
        "created_utc": datetime.utcnow().isoformat() + "Z",
        "payload": payload,
        "status": "created (mock)",
    }

    out_path = tickets_dir / f"{ticket_id}.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return {"ticket_id": ticket_id, "status": "created", "path": str(out_path)}


def draft_change_plan(context: dict) -> dict:
    """
    Mock change plan generator.
    For now returns a structured template (LLM will fill later).
    """
    return {
        "title": context.get("title", "Change Plan"),
        "summary": context.get("summary", ""),
        "steps": [
            "Validate impact and affected services",
            "Prepare rollback plan",
            "Apply change in staging",
            "Deploy to production during change window",
            "Monitor metrics and logs",
        ],
        "risks": [
            "Service degradation during deployment",
            "Unexpected dependency failures",
        ],
        "rollback": "Revert deployment and restore previous configuration",
    }