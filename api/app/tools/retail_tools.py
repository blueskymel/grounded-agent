from __future__ import annotations

from datetime import datetime
from typing import Any


def draft_store_incident_summary(tool_input: dict[str, Any]) -> dict[str, Any]:
    """
    Retail ops tool: Draft an incident summary for store ops / comms.
    This is intentionally mocked (no external systems).
    """
    store_id = str(tool_input.get("store_id") or "").strip()
    incident_type = str(tool_input.get("incident_type") or "").strip()
    duration_minutes = int(tool_input.get("duration_minutes") or 0)

    if not store_id or not incident_type:
        return {"ok": False, "error": "store_id and incident_type are required"}

    summary = {
        "store_id": store_id,
        "incident_type": incident_type,
        "duration_minutes": duration_minutes,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "draft": {
            "what_happened": f"Store {store_id} reported: {incident_type}.",
            "impact": (
                "Potential customer impact at checkout and store operations. "
                "Impact level depends on affected systems and duration."
            ),
            "actions_taken": [
                "Confirm scope (single store vs regional).",
                "Check known incidents / maintenance windows.",
                "Escalate to on-call service owner if needed.",
            ],
            "next_steps": [
                "Capture timeline and key signals.",
                "Create comms update for store leadership.",
                "Open problem ticket if recurring.",
            ],
        },
    }

    return {"ok": True, "result": summary}


def analyze_price_change(tool_input: dict[str, Any]) -> dict[str, Any]:
    """
    Retail ops tool: Do a simple impact calculation on a price change.
    Mocked logic: margin delta based on optional unit_cost.
    """
    sku = str(tool_input.get("sku") or "").strip()
    old_price = tool_input.get("old_price")
    new_price = tool_input.get("new_price")
    unit_cost = tool_input.get("unit_cost")  # optional

    if not sku or old_price is None or new_price is None:
        return {"ok": False, "error": "sku, old_price, new_price are required"}

    try:
        old_price = float(old_price)
        new_price = float(new_price)
        unit_cost_f = float(unit_cost) if unit_cost is not None else None
    except (TypeError, ValueError):
        return {"ok": False, "error": "old_price/new_price/unit_cost must be numbers"}

    price_delta = new_price - old_price
    pct_change = (price_delta / old_price * 100.0) if old_price != 0 else None

    result: dict[str, Any] = {
        "sku": sku,
        "old_price": old_price,
        "new_price": new_price,
        "price_delta": round(price_delta, 4),
        "pct_change": round(pct_change, 4) if pct_change is not None else None,
        "risk_flags": [],
        "notes": [],
    }

    if pct_change is not None and abs(pct_change) >= 10:
        result["risk_flags"].append("large_price_move_(>=10%)")

    if unit_cost_f is not None:
        old_margin = old_price - unit_cost_f
        new_margin = new_price - unit_cost_f
        result["old_margin"] = round(old_margin, 4)
        result["new_margin"] = round(new_margin, 4)
        result["margin_delta"] = round(new_margin - old_margin, 4)

        if new_margin < 0:
            result["risk_flags"].append("negative_margin")
        if old_margin > 0 and new_margin / old_margin < 0.9:
            result["risk_flags"].append("margin_drop_(>10%)")

    result["notes"].append("Mock analysis only — wire to pricing rules + approvals in production.")

    return {"ok": True, "result": result}