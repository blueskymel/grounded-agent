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

    assert intent.name == "STORE_INCIDENT"
    assert intent.store_id == "1234"
    assert intent.duration_minutes == 45