from app.tools.retail_tools import triage_low_stock, check_promo_compliance


def test_triage_low_stock_ok():
    r = triage_low_stock({"store_id": "2045", "sku": "SKU777", "on_hand": 0, "forecast_per_day": 5, "lead_time_days": 2})
    assert r["ok"] is True
    assert r["priority"] == "P1"
    assert r["sku"] == "SKU777"


def test_check_promo_compliance_ok():
    r = check_promo_compliance({"promo_id": "PROMO-99", "sku": "SKU123", "price": 9.99, "channel": "online"})
    assert r["ok"] is True
    assert r["channel"] == "online"
    assert "required_approvals" in r