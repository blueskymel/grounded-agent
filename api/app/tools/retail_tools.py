from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional


def draft_store_incident_summary(tool_input: dict) -> dict:
    """
    Existing tool (keep if you already have it elsewhere).
    Leaving here as a placeholder in case your file contains it.
    If you already have it implemented, remove this duplicate.
    """
    store_id = str(tool_input.get("store_id", "unknown"))
    incident_type = str(tool_input.get("incident_type", "unspecified"))
    duration_minutes = int(tool_input.get("duration_minutes", 0))

    return {
        "ok": True,
        "store_id": store_id,
        "incident_type": incident_type,
        "duration_minutes": duration_minutes,
        "summary": f"Store {store_id}: {incident_type} for {duration_minutes} minutes.",
    }


def analyze_price_change(tool_input: dict) -> dict:
    """
    Existing tool (keep if you already have it elsewhere).
    Leaving here as a placeholder in case your file contains it.
    If you already have it implemented, remove this duplicate.
    """
    sku = str(tool_input.get("sku", "unknown"))
    old_price = float(tool_input.get("old_price", 0))
    new_price = float(tool_input.get("new_price", 0))
    unit_cost = tool_input.get("unit_cost", None)

    delta = new_price - old_price
    pct = (delta / old_price) * 100 if old_price else None

    return {
        "ok": True,
        "sku": sku,
        "old_price": old_price,
        "new_price": new_price,
        "delta": round(delta, 4),
        "delta_pct": round(pct, 4) if pct is not None else None,
        "unit_cost": float(unit_cost) if unit_cost is not None else None,
    }


def triage_low_stock(tool_input: dict) -> Dict[str, Any]:
    """
    Retail Ops: low-stock triage.
    Tool registry compatible: accepts tool_input dict.
    """
    store_id = tool_input.get("store_id")
    sku = tool_input.get("sku")
    on_hand = tool_input.get("on_hand")

    forecast_per_day = tool_input.get("forecast_per_day", None)
    lead_time_days = tool_input.get("lead_time_days", None)

    if not store_id or not sku:
        return {"ok": False, "error": "store_id and sku are required"}

    try:
        on_hand_int = int(on_hand)
    except Exception:
        return {"ok": False, "error": "on_hand must be an integer"}

    if on_hand_int < 0:
        return {"ok": False, "error": "on_hand must be >= 0"}

    forecast = None
    if forecast_per_day is not None:
        try:
            forecast = float(forecast_per_day)
        except Exception:
            return {"ok": False, "error": "forecast_per_day must be a number"}

    lead = None
    if lead_time_days is not None:
        try:
            lead = int(lead_time_days)
        except Exception:
            return {"ok": False, "error": "lead_time_days must be an integer"}

    priority = "P3"
    if on_hand_int == 0:
        priority = "P1"
    elif on_hand_int <= 3:
        priority = "P2"

    days_cover = None
    if forecast and forecast > 0:
        days_cover = round(on_hand_int / forecast, 2)

    recommended_actions = []
    if on_hand_int == 0:
        recommended_actions.append("Mark as out-of-stock; enable substitutions if allowed.")
        recommended_actions.append("Check inbound shipments and update ETA.")
        recommended_actions.append("Consider transfer from nearby stores if policy allows.")
    elif on_hand_int <= 3:
        recommended_actions.append("Trigger replenishment review and confirm shelf availability.")
        recommended_actions.append("Check if recent promo drove demand spike.")
    else:
        recommended_actions.append("Monitor; no immediate action required.")

    suggested_order_qty = None
    if forecast and lead and forecast > 0 and lead > 0:
        suggested_order_qty = int(round((lead * forecast) + max(0, 2 - on_hand_int)))

    notify = []
    if priority in ("P1", "P2"):
        notify = ["Store Manager", "Replenishment Planner"]
        if on_hand_int == 0:
            notify.append("Customer Support (if online availability impacted)")

    return {
        "ok": True,
        "tool": "triage_low_stock",
        "store_id": str(store_id),
        "sku": str(sku).upper(),
        "priority": priority,
        "on_hand": on_hand_int,
        "forecast_per_day": forecast,
        "lead_time_days": lead,
        "days_cover": days_cover,
        "suggested_order_qty": suggested_order_qty,
        "notify": notify,
        "recommended_actions": recommended_actions,
    }


def check_promo_compliance(tool_input: dict) -> Dict[str, Any]:
    """
    Commercial: promotion compliance check (mock).
    Tool registry compatible: accepts tool_input dict.
    """
    promo_id = tool_input.get("promo_id")
    sku = tool_input.get("sku")
    price = tool_input.get("price")
    channel = tool_input.get("channel", "both")
    start_date = tool_input.get("start_date", None)
    end_date = tool_input.get("end_date", None)

    if not promo_id or not sku:
        return {"ok": False, "error": "promo_id and sku are required"}

    channel_norm = (channel or "both").lower().strip()
    if channel_norm not in ("online", "store", "both"):
        return {"ok": False, "error": "channel must be one of: online, store, both"}

    try:
        price_f = float(price)
    except Exception:
        return {"ok": False, "error": "price must be a number"}

    if price_f <= 0:
        return {"ok": False, "error": "price must be > 0"}

    def _parse_date(s: Optional[str]) -> Optional[date]:
        if not s:
            return None
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))

    sd = _parse_date(start_date) if isinstance(start_date, str) else None
    ed = _parse_date(end_date) if isinstance(end_date, str) else None

    reasons = []
    passed = True

    if sd and ed and ed < sd:
        passed = False
        reasons.append("End date is before start date.")

    if price_f < 0.5:
        passed = False
        reasons.append("Price appears unusually low; requires finance approval.")

    if not (str(promo_id).upper().startswith("PROMO") or str(promo_id).upper().startswith("PR")):
        reasons.append("Promo ID does not match standard naming convention (PROMO*/PR*).")

    required_approvals = []
    if price_f < 1.0:
        required_approvals.append("Finance")
    if channel_norm in ("online", "both"):
        required_approvals.append("eCommerce")
    if channel_norm in ("store", "both"):
        required_approvals.append("Store Operations")

    return {
        "ok": True,
        "tool": "check_promo_compliance",
        "promo_id": str(promo_id),
        "sku": str(sku).upper(),
        "price": price_f,
        "channel": channel_norm,
        "start_date": start_date if isinstance(start_date, str) else None,
        "end_date": end_date if isinstance(end_date, str) else None,
        "passed": passed,
        "reasons": reasons,
        "required_approvals": required_approvals,
    }