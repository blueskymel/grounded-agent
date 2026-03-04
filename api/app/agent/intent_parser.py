import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Intent:
    name: str

    # Common entities
    sku: Optional[str] = None
    store_id: Optional[str] = None

    # Price change
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    unit_cost: Optional[float] = None

    # Store incident
    incident_type: Optional[str] = None
    duration_minutes: Optional[int] = None

    # Low stock
    on_hand: Optional[int] = None
    forecast_per_day: Optional[float] = None
    lead_time_days: Optional[int] = None

    # Promo compliance
    promo_id: Optional[str] = None
    price: Optional[float] = None
    channel: Optional[str] = None  # online|store|both

    # Complaint response
    complaint_type: Optional[str] = None


# ---- Regex patterns ----
PRICE_CHANGE_RE = re.compile(
    r"(price change|change price|update price|reduce price|lower price)"
    r".*?(?P<sku>sku\w+)"
    r".*?(from\s*)?(?P<old>\d+(?:\.\d+)?)"
    r".*?(to\s*)?(?P<new>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

STORE_INCIDENT_RE = re.compile(
    r"(store\s*(?P<store>\d+)).*?"
    r"(?P<incident>pos outage|payments down|outage|incident|failure)"
    r".*?(?P<duration>\d+)\s*(min|mins|minutes)?",
    re.IGNORECASE,
)

LOW_STOCK_RE_1 = re.compile(
    r"(low stock|out of stock|oos|stockout)"
    r".*?store\s*(?P<store>\d+)"
    r".*?(?P<sku>sku\w+)"
    r".*?(on hand|on-hand|soh)\s*(?P<on_hand>\d+)",
    re.IGNORECASE,
)

LOW_STOCK_RE_2 = re.compile(
    r"(low stock|out of stock|oos|stockout)"
    r".*?(?P<sku>sku\w+)"
    r".*?store\s*(?P<store>\d+)"
    r".*?(on hand|on-hand|soh)\s*(?P<on_hand>\d+)",
    re.IGNORECASE,
)

PROMO_COMPLIANCE_RE = re.compile(
    r"(promo compliance|promotion compliance|check promo|promo check)"
    r".*?(promo\s*(?P<promo>[\w\-]+))"
    r".*?(?P<sku>sku\w+)"
    r".*?(price\s*(?P<price>\d+(?:\.\d+)?))"
    r"(?:.*?(channel\s*(?P<channel>online|store|both)))?",
    re.IGNORECASE,
)

COMPLAINT_RESPONSE_RE = re.compile(
    r"(complaint|customer complaint|draft response|reply to customer)"
    r".*?(delivery|late delivery|missing item|wrong item|refund|rude staff|damaged item|quality)",
    re.IGNORECASE,
)


def parse_intent(message: str) -> Optional[Intent]:
    msg = message.strip()
    if not msg:
        return None

    # Price change
    m = PRICE_CHANGE_RE.search(msg)
    if m:
        return Intent(
            name="ANALYZE_PRICE_CHANGE",
            sku=m.group("sku").upper(),
            old_price=float(m.group("old")),
            new_price=float(m.group("new")),
        )

    # Store incident summary
    m = STORE_INCIDENT_RE.search(msg)
    if m:
        incident = m.group("incident").lower().strip()
        return Intent(
            name="DRAFT_STORE_INCIDENT_SUMMARY",
            store_id=m.group("store"),
            incident_type=incident,
            duration_minutes=int(m.group("duration")),
        )

    # Low stock triage
    m = LOW_STOCK_RE_1.search(msg) or LOW_STOCK_RE_2.search(msg)
    if m:
        return Intent(
            name="LOW_STOCK_TRIAGE",
            store_id=m.group("store"),
            sku=m.group("sku").upper(),
            on_hand=int(m.group("on_hand")),
        )

    # Promo compliance
    m = PROMO_COMPLIANCE_RE.search(msg)
    if m:
        channel = (m.group("channel") or "both").lower().strip()
        return Intent(
            name="PROMO_COMPLIANCE_CHECK",
            promo_id=m.group("promo"),
            sku=m.group("sku").upper(),
            price=float(m.group("price")),
            channel=channel,
        )

    # Complaint response
    m = COMPLAINT_RESPONSE_RE.search(msg)
    if m:
        complaint_type = m.group(2).lower().strip()
        return Intent(
            name="CUSTOMER_COMPLAINT_RESPONSE",
            complaint_type=complaint_type,
        )

    return None