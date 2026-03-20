from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import parse, request

from pyqt.shared.weather import WeatherCity, configured_location


NWS_ALERTS_API = "https://api.weather.gov/alerts/active"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
NWS_HEADERS = {
    "User-Agent": "Hanauta CAP Alerts/1.0 (weather integration)",
    "Accept": "application/geo+json, application/json",
}
_DEMO_CACHE: list["CapAlert"] = []
_DEMO_CACHE_EXPIRES: datetime | None = None
SEVERITY_RANK = {
    "extreme": 4,
    "severe": 3,
    "moderate": 2,
    "minor": 1,
    "unknown": 0,
}


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


def _request_json(url: str) -> dict[str, Any]:
    req = request.Request(url, headers=NWS_HEADERS)
    with request.urlopen(req, timeout=8.0) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def load_runtime_settings() -> dict[str, Any]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def cap_alert_settings() -> dict[str, Any]:
    settings = load_runtime_settings()
    services = settings.get("services", {})
    if not isinstance(services, dict):
        return {}
    cap = services.get("cap_alerts", {})
    return cap if isinstance(cap, dict) else {}


def test_mode_enabled() -> bool:
    return bool(cap_alert_settings().get("test_mode", False))


def configured_alert_location() -> WeatherCity | None:
    return configured_location()


def icon_name_for_event(event: str) -> str:
    lowered = event.strip().lower()
    if any(token in lowered for token in ("thunder", "storm", "tornado")):
        return "thunderstorms"
    if any(token in lowered for token in ("flood", "rain", "flash flood")):
        return "overcast-rain"
    if any(token in lowered for token in ("snow", "blizzard", "ice", "sleet")):
        return "overcast-snow"
    if any(token in lowered for token in ("wind", "hurricane", "tropical")):
        return "wind"
    if any(token in lowered for token in ("fog",)):
        return "fog"
    if any(token in lowered for token in ("heat", "fire", "red flag")):
        return "clear-day"
    return "not-available"


def fetch_active_alerts(location: WeatherCity | None) -> list[CapAlert]:
    if test_mode_enabled():
        return random_test_alerts()
    if location is None:
        return []
    params = parse.urlencode(
        {
            "point": f"{location.latitude:.4f},{location.longitude:.4f}",
            "status": "actual",
            "message_type": "alert",
        }
    )
    try:
        payload = _request_json(f"{NWS_ALERTS_API}?{params}")
    except Exception:
        return []
    features = payload.get("features", [])
    if not isinstance(features, list):
        return []
    alerts: list[CapAlert] = []
    for feature in features:
        props = feature.get("properties", {}) if isinstance(feature, dict) else {}
        if not isinstance(props, dict):
            continue
        event = str(props.get("event", "")).strip()
        if not event:
            continue
        alert = CapAlert(
            identifier=str(props.get("id", "")).strip() or str(feature.get("id", "")).strip() or event,
            event=event,
            headline=str(props.get("headline", "")).strip() or event,
            severity=str(props.get("severity", "Unknown")).strip() or "Unknown",
            urgency=str(props.get("urgency", "Unknown")).strip() or "Unknown",
            certainty=str(props.get("certainty", "Unknown")).strip() or "Unknown",
            area_desc=str(props.get("areaDesc", "")).strip(),
            sender_name=str(props.get("senderName", "")).strip() or "National Weather Service",
            sent=str(props.get("sent", "")).strip(),
            effective=str(props.get("effective", "")).strip(),
            expires=str(props.get("expires", "")).strip(),
            instruction=str(props.get("instruction", "")).strip(),
            description=str(props.get("description", "")).strip(),
            response=str(props.get("response", "")).strip(),
            web=str(props.get("web", "")).strip(),
            icon_name=icon_name_for_event(event),
            contact_number="911",
        )
        alerts.append(alert)
    alerts.sort(key=lambda item: (-SEVERITY_RANK.get(item.severity.lower(), 0), item.event.lower()))
    return alerts


def random_test_alerts() -> list[CapAlert]:
    global _DEMO_CACHE, _DEMO_CACHE_EXPIRES
    now = datetime.now(timezone.utc)
    if _DEMO_CACHE and _DEMO_CACHE_EXPIRES is not None and now < _DEMO_CACHE_EXPIRES:
        return list(_DEMO_CACHE)
    samples = [
        CapAlert(
            identifier="test-br-sp-1",
            event="Severe Thunderstorm Warning",
            headline="Strong storms may impact Sao Paulo state through the evening.",
            severity="Severe",
            urgency="Immediate",
            certainty="Likely",
            area_desc="Sao Paulo, Brazil",
            sender_name="Brazil Civil Defense Demo Feed",
            sent=now.isoformat(),
            effective=now.isoformat(),
            expires=(now + timedelta(hours=3)).isoformat(),
            instruction="Stay indoors, avoid flooded streets, and watch official civil defense updates.",
            description="Demo alert for Hanauta test mode.",
            response="Shelter",
            web="https://www.gov.br/defesacivil",
            icon_name="thunderstorms",
            contact_number="199 / 193",
        ),
        CapAlert(
            identifier="test-jp-1",
            event="Heavy Rain Emergency Warning",
            headline="Very heavy rainfall may trigger flash flooding and landslides.",
            severity="Extreme",
            urgency="Immediate",
            certainty="Observed",
            area_desc="Kansai region, Japan",
            sender_name="Japan Meteorological Agency Demo Feed",
            sent=now.isoformat(),
            effective=now.isoformat(),
            expires=(now + timedelta(hours=6)).isoformat(),
            instruction="Move to higher ground or a designated shelter immediately.",
            description="Demo alert for Hanauta test mode.",
            response="Evacuate",
            web="https://www.jma.go.jp/jma/indexe.html",
            icon_name="overcast-rain",
            contact_number="119 / 110",
        ),
        CapAlert(
            identifier="test-au-1",
            event="Bushfire Advice",
            headline="Hot, dry conditions may cause fast-moving grass and bush fires.",
            severity="Moderate",
            urgency="Expected",
            certainty="Likely",
            area_desc="Victoria, Australia",
            sender_name="Emergency Victoria Demo Feed",
            sent=now.isoformat(),
            effective=now.isoformat(),
            expires=(now + timedelta(hours=10)).isoformat(),
            instruction="Review your bushfire plan and leave early if conditions worsen.",
            description="Demo alert for Hanauta test mode.",
            response="Prepare",
            web="https://www.emergency.vic.gov.au/respond/",
            icon_name="clear-day",
            contact_number="000",
        ),
        CapAlert(
            identifier="test-de-1",
            event="Wind Warning",
            headline="Powerful gusts may cause debris, falling branches, and travel disruption.",
            severity="Severe",
            urgency="Expected",
            certainty="Likely",
            area_desc="Hamburg, Germany",
            sender_name="DWD Demo Feed",
            sent=now.isoformat(),
            effective=now.isoformat(),
            expires=(now + timedelta(hours=5)).isoformat(),
            instruction="Secure loose outdoor items and avoid parks or wooded areas.",
            description="Demo alert for Hanauta test mode.",
            response="Monitor",
            web="https://www.dwd.de/EN/weather/warnings/warnings_node.html",
            icon_name="wind",
            contact_number="112",
        ),
        CapAlert(
            identifier="test-us-1",
            event="Flash Flood Warning",
            headline="Rapid flooding is possible in low-lying roads and creeks.",
            severity="Severe",
            urgency="Immediate",
            certainty="Observed",
            area_desc="Texas, United States",
            sender_name="National Weather Service Demo Feed",
            sent=now.isoformat(),
            effective=now.isoformat(),
            expires=(now + timedelta(hours=2)).isoformat(),
            instruction="Turn around, don't drown. Move to higher ground immediately.",
            description="Demo alert for Hanauta test mode.",
            response="Avoid",
            web="https://www.weather.gov/alerts",
            icon_name="overcast-rain",
            contact_number="911",
        ),
    ]
    count = random.randint(1, min(3, len(samples)))
    alerts = random.sample(samples, count)
    alerts.sort(key=lambda item: (-SEVERITY_RANK.get(item.severity.lower(), 0), item.event.lower()))
    _DEMO_CACHE = list(alerts)
    _DEMO_CACHE_EXPIRES = now + timedelta(minutes=10)
    return list(alerts)


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
    delta = moment - now
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 0:
        return "Ending now"
    if minutes < 60:
        return f"Ends in {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"Ends in {hours}h"
    days = hours // 24
    return f"Ends in {days}d"


def fallback_tip(alert: CapAlert) -> str:
    lowered = alert.event.lower()
    if "thunder" in lowered or "tornado" in lowered:
        return "Move indoors, stay away from windows, and monitor official local instructions."
    if "flood" in lowered:
        return "Move to higher ground immediately and never drive through flood waters."
    if "wind" in lowered or "hurricane" in lowered or "tropical" in lowered:
        return "Shelter away from windows, secure loose objects, and follow official evacuation guidance."
    if "snow" in lowered or "ice" in lowered or "blizzard" in lowered:
        return "Avoid unnecessary travel, keep charged devices nearby, and prepare for outages."
    if "heat" in lowered:
        return "Hydrate, limit exertion, and check on vulnerable people nearby."
    if "fire" in lowered:
        return "Be ready to leave quickly, follow evacuation orders, and watch official fire updates."
    return "Follow official alert instructions and call emergency services if you are in immediate danger."
