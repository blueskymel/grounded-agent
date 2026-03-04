from app.agent.intent_parser import parse_intent


def test_parse_price_change():
    msg = "Analyze price change impact for SKU123 from 12.99 to 11.99"
    intent = parse_intent(msg)

    assert intent.name == "ANALYZE_PRICE_CHANGE"
    assert intent.sku == "SKU123"
    assert intent.old_price == 12.99
    assert intent.new_price == 11.99


def test_parse_store_incident():
    msg = "Create store incident summary for store 1234 POS outage lasting 45 minutes"
    intent = parse_intent(msg)

    assert intent.name == "DRAFT_STORE_INCIDENT_SUMMARY"
    assert intent.store_id == "1234"
    assert "pos outage" in (intent.incident_type or "")
    assert intent.duration_minutes == 45


def test_parse_low_stock():
    msg = "Low stock store 2045 SKU777 on hand 3"
    intent = parse_intent(msg)

    assert intent.name == "LOW_STOCK_TRIAGE"
    assert intent.store_id == "2045"
    assert intent.sku == "SKU777"
    assert intent.on_hand == 3


def test_parse_promo_compliance():
    msg = "Check promo compliance promo PROMO-99 SKU123 price 9.99 channel online"
    intent = parse_intent(msg)

    assert intent.name == "PROMO_COMPLIANCE_CHECK"
    assert intent.promo_id == "PROMO-99"
    assert intent.sku == "SKU123"
    assert intent.price == 9.99
    assert intent.channel == "online"


def test_parse_complaint_response():
    msg = "Draft response to customer complaint about missing item"
    intent = parse_intent(msg)

    assert intent.name == "CUSTOMER_COMPLAINT_RESPONSE"
    assert intent.complaint_type == "missing item"