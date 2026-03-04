import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Intent:
    name: str
    sku: Optional[str] = None
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    store_id: Optional[str] = None
    incident_type: Optional[str] = None
    duration_minutes: Optional[int] = None


PRICE_CHANGE_RE = re.compile(
    r"price change.*?(?P<sku>sku\w+).*?(?P<old>\d+\.\d+).*?(?P<new>\d+\.\d+)",
    re.IGNORECASE,
)

STORE_INCIDENT_RE = re.compile(
    r"store\s*(?P<store>\d+).*?(?P<incident>outage|incident|failure).*?(?P<duration>\d+)",
    re.IGNORECASE,
)


def parse_intent(message: str) -> Optional[Intent]:
    msg = message

    m = PRICE_CHANGE_RE.search(msg)
    if m:
        return Intent(
            name="ANALYZE_PRICE_CHANGE",
            sku=m.group("sku").upper(),
            old_price=float(m.group("old")),
            new_price=float(m.group("new")),
        )

    m = STORE_INCIDENT_RE.search(msg)
    if m:
        return Intent(
            name="STORE_INCIDENT",
            store_id=m.group("store"),
            incident_type=m.group("incident"),
            duration_minutes=int(m.group("duration")),
        )

    return None