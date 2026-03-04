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


# --- Helpers ---
SKU_RE = r"(?P<sku>SKU[0-9A-Z_-]+)"          # requires SKU prefix
STORE_RE = r"store\s*(?P<store>\d{3,6})"    # 3-6 digits typical
MONEY_RE = r"(?P<num>\d+(?:\.\d+)?)"

def _norm_sku(s: str) -> str:
    s2 = (s or "").strip().upper()
    # ensure SKU prefix (tests expect SKU123)
    if s2 and not s2.startswith("SKU"):
        s2 = "SKU" + s2
    return s2


# ---- Regex patterns ----

# Examples:
# "Analyze price change impact for SKU123 from 12.99 to 11.99"
# "Price change SKU123 12.99 -> 11.99 unit cost 8.50"
PRICE_CHANGE_RE = re.compile(
    r"(price change|change price|update price|reduce price|lower price)"
    r".*?(?P<sku>SKU\w+)"
    r".*?(?:from\s*)?(?P<old>\d+(?:\.\d+)?)"
    r".*?(?:to\s*)?(?P<new>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Examples:
# "Create a store incident summary for store 1234 POS outage 45 mins"
# "store 2045 payments down 30 minutes"
STORE_INCIDENT_RE = re.compile(
    rf"\b{STORE_RE}\b"
    rf".*?(?P<incident>pos outage|payments down|outage|incident|failure)\b"
    rf"(?:.*?(?P<duration>\d+)\s*(?:min|mins|minutes))?",
    re.IGNORECASE,
)

# Examples:
# "Low stock store 2045 SKU777 on hand 3"
# "OOS SKU777 store 2045 SOH 0 forecast 5/day lead time 2 days"
LOW_STOCK_RE_1 = re.compile(
    rf"\b(low stock|out of stock|oos|stockout)\b"
    rf".*?\b{STORE_RE}\b"
    rf".*?\b{SKU_RE}\b"
    rf".*?\b(on hand|on-hand|soh)\s*(?P<on_hand>\d+)\b"
    rf"(?:.*?\b(forecast|demand)\s*(?P<forecast>{MONEY_RE})\s*(?:/day|per day|day)?)?"
    rf"(?:.*?\b(lead time|lead)\s*(?P<lead>\d+)\s*(?:day|days)?)?",
    re.IGNORECASE,
)
LOW_STOCK_RE_2 = re.compile(
    rf"\b(low stock|out of stock|oos|stockout)\b"
    rf".*?\b{SKU_RE}\b"
    rf".*?\b{STORE_RE}\b"
    rf".*?\b(on hand|on-hand|soh)\s*(?P<on_hand>\d+)\b"
    rf"(?:.*?\b(forecast|demand)\s*(?P<forecast>{MONEY_RE})\s*(?:/day|per day|day)?)?"
    rf"(?:.*?\b(lead time|lead)\s*(?P<lead>\d+)\s*(?:day|days)?)?",
    re.IGNORECASE,
)

# Examples:
# "Check promo compliance PROMO-99 SKU123 price 0.49 channel online"
# "promo check PR123 SKU777 9.99 store"
PROMO_COMPLIANCE_RE = re.compile(
    r"(promo compliance|promotion compliance|check promo|promo check)"
    r".*?\bpromo\s+(?P<promo>[A-Za-z0-9][A-Za-z0-9\-]*)\b"
    r".*?(?P<sku>SKU\w+)"
    r".*?\bprice\s+(?P<price>\d+(?:\.\d+)?)\b"
    r"(?:.*?\bchannel\s+(?P<channel>online|store|both)\b)?",
    re.IGNORECASE,
)

COMPLAINT_RESPONSE_RE = re.compile(
    r"\b(complaint|customer complaint|draft response|reply to customer)\b"
    r".*?\b(delivery|late delivery|missing item|wrong item|refund|rude staff|damaged item|quality)\b",
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
        incident = (m.group("incident") or "").lower().strip()
        duration = int(m.group("duration")) if m.group("duration") else 0
        return Intent(
            name="DRAFT_STORE_INCIDENT_SUMMARY",
            store_id=m.group("store"),
            incident_type=incident,
            duration_minutes=duration,
        )

    # Low stock triage
    m = LOW_STOCK_RE_1.search(msg) or LOW_STOCK_RE_2.search(msg)
    if m:
        forecast = float(m.group("forecast")) if m.group("forecast") else None
        lead = int(m.group("lead")) if m.group("lead") else None
        return Intent(
            name="LOW_STOCK_TRIAGE",
            store_id=m.group("store"),
            sku=_norm_sku(m.group("sku")),
            on_hand=int(m.group("on_hand")),
            forecast_per_day=forecast,
            lead_time_days=lead,
        )

    # Promo compliance
    m = PROMO_COMPLIANCE_RE.search(msg)
    if m:
        channel = (m.group("channel") or "both").lower().strip()
        return Intent(
            name="PROMO_COMPLIANCE_CHECK",
            promo_id=m.group("promo").upper(),
            sku=_norm_sku(m.group("sku")),
            price=float(m.group("price")),
            channel=channel,
        )

    # Complaint response
    m = COMPLAINT_RESPONSE_RE.search(msg)
    if m:
        complaint_type = (m.group(2) or "").lower().strip()
        return Intent(
            name="CUSTOMER_COMPLAINT_RESPONSE",
            complaint_type=complaint_type,
        )

    return None