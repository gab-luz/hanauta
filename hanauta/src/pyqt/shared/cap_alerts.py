from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def _load_plugin_module():
    candidates = [
        Path.home() / "dev" / "hanauta-plugin-cap-alerts" / "cap_alerts_shared.py",
        Path.home() / ".config" / "i3" / "hanauta" / "plugins" / "cap_alerts" / "cap_alerts_shared.py",
        Path(__file__).resolve().parents[3] / "plugins" / "cap_alerts" / "cap_alerts_shared.py",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location("hanauta_cap_alerts_shared", str(candidate))
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    return None


_plugin = _load_plugin_module()

if _plugin is not None:
    CapAlert = _plugin.CapAlert
    load_runtime_settings = _plugin.load_runtime_settings
    cap_alert_settings = _plugin.cap_alert_settings
    test_mode_enabled = _plugin.test_mode_enabled
    configured_alert_location = _plugin.configured_alert_location
    icon_name_for_event = _plugin.icon_name_for_event
    fetch_active_alerts = _plugin.fetch_active_alerts
    random_test_alerts = _plugin.random_test_alerts
    top_alert = _plugin.top_alert
    relative_expiry = _plugin.relative_expiry
    fallback_tip = _plugin.fallback_tip
    cap_alert_accent = getattr(
        _plugin,
        "cap_alert_accent",
        lambda severity, provider_color: provider_color or "#FBC02D",
    )
    alert_accent_color = getattr(_plugin, "alert_accent_color", lambda _alert: "#FBC02D")
else:
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
