from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class CapAlert:
    identifier: str
    event: str
    headline: str
    severity: str
    urgency: str
    certainty: str
    area_desc: str
    sender_name: str
    sent: str
    effective: str
    expires: str
    instruction: str
    description: str
    response: str
    web: str
    icon_name: str
    contact_number: str = ""
    color: str = ""


def load_runtime_settings() -> dict:
    return {}


def cap_alert_settings() -> dict:
    return {}


def test_mode_enabled() -> bool:
    return False


def configured_alert_location():
    return None


def icon_name_for_event(event: str) -> str:
    return "not-available"


def fetch_active_alerts(location) -> list[CapAlert]:
    return []


def random_test_alerts() -> list[CapAlert]:
    return []


def top_alert(alerts: list[CapAlert]) -> CapAlert | None:
    return alerts[0] if alerts else None


def relative_expiry(alert: CapAlert) -> str:
    raw = alert.expires or alert.effective or alert.sent
    if not raw:
        return ""
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return ""
    now = datetime.now(moment.tzinfo)
    minutes = int((moment - now).total_seconds() // 60)
    if minutes <= 0:
        return "Ending now"
    if minutes < 60:
        return f"Ends in {minutes} min"
    return f"Ends in {minutes // 60}h"


def fallback_tip(alert: CapAlert) -> str:
    return "Follow official alert instructions and call emergency services if you are in immediate danger."


def alert_accent_color(alert: CapAlert | None) -> str:
    if alert is None:
        return "#FBC02D"
    return cap_alert_accent(alert.severity, alert.color)


def cap_alert_accent(severity: str, provider_color: str) -> str:
    color = (provider_color or "").strip()
    if color.startswith("#") and len(color) in {4, 7}:
        return color
    lowered = (severity or "").strip().lower()
    if lowered == "extreme":
        return "#D32F2F"
    if lowered == "severe":
        return "#F57C00"
    if lowered == "moderate":
        return "#FBC02D"
    if lowered == "minor":
        return "#0288D1"
    return "#9E9E9E"
