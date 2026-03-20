from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from PyQt6.QtCore import QUrl


ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
HOME_ASSISTANT_ICON_DIR = ASSETS_DIR / "home-assistant-icons"
MDI_ICON_BASE_URL = "https://raw.githubusercontent.com/Templarian/MaterialDesign/master/svg"


def normalize_ha_url(url: str) -> str:
    return str(url).strip().rstrip("/")


def fetch_home_assistant_json(base_url: str, token: str, path: str, *, timeout: float = 4.0) -> tuple[object | None, str]:
    if not base_url or not token:
        return None, "Home Assistant URL and token are required."
    try:
        req = request.Request(
            f"{normalize_ha_url(base_url)}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace")), ""
    except error.HTTPError as exc:
        return None, f"Home Assistant returned HTTP {exc.code}."
    except Exception:
        return None, "Unable to reach Home Assistant."


def post_home_assistant_json(
    base_url: str,
    token: str,
    path: str,
    payload: dict,
    *,
    timeout: float = 4.0,
) -> tuple[object | None, str]:
    if not base_url or not token:
        return None, "Home Assistant URL and token are required."
    data = json.dumps(payload).encode("utf-8")
    try:
        req = request.Request(
            f"{normalize_ha_url(base_url)}{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return (json.loads(body) if body else None), ""
    except error.HTTPError as exc:
        return None, f"Home Assistant returned HTTP {exc.code}."
    except Exception:
        return None, "Unable to reach Home Assistant."


def entity_domain(entity_id: str) -> str:
    text = str(entity_id).strip()
    return text.split(".", 1)[0] if "." in text else ""


def entity_friendly_name(entity: dict) -> str:
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
    if isinstance(attrs, dict):
        label = str(attrs.get("friendly_name", "")).strip()
        if label:
            return label
    entity_id = str(entity.get("entity_id", "")).strip()
    if "." in entity_id:
        return entity_id.split(".", 1)[1].replace("_", " ").strip().title()
    return entity_id or "Unknown entity"


def entity_state_label(entity: dict) -> str:
    state = str(entity.get("state", "unknown")).strip()
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
    unit = str(attrs.get("unit_of_measurement", "")).strip() if isinstance(attrs, dict) else ""
    if not state:
        state = "unknown"
    label = state.replace("_", " ").strip()
    return f"{label} {unit}".strip()


def entity_secondary_text(entity: dict) -> str:
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
    if not isinstance(attrs, dict):
        attrs = {}
    pieces: list[str] = []
    area = str(attrs.get("area_id", "")).strip()
    device_class = str(attrs.get("device_class", "")).strip().replace("_", " ")
    if area:
        pieces.append(area.replace("_", " ").title())
    if device_class:
        pieces.append(device_class.title())
    if not pieces:
        entity_id = str(entity.get("entity_id", "")).strip()
        if entity_id:
            pieces.append(entity_id)
    return " • ".join(piece for piece in pieces if piece)


def entity_attributes_text(entity: dict) -> str:
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
    if not isinstance(attrs, dict):
        return ""
    interesting_keys = (
        "brightness",
        "temperature",
        "current_temperature",
        "humidity",
        "friendly_name",
        "device_class",
        "supported_color_modes",
        "hvac_mode",
        "preset_mode",
        "battery_level",
        "current_position",
        "volume_level",
        "media_title",
        "source",
    )
    parts: list[str] = []
    for key in interesting_keys:
        if key not in attrs:
            continue
        value = attrs.get(key)
        if value in ("", None, [], {}):
            continue
        label = key.replace("_", " ").title()
        parts.append(f"{label}: {value}")
    return "\n".join(parts[:5])


def _parse_iso_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def entity_relative_update_text(entity: dict) -> str:
    timestamp = _parse_iso_timestamp(entity.get("last_changed") or entity.get("last_updated"))
    if timestamp is None:
        return "No recent update"
    delta = datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "Updated now"
    if seconds < 3600:
        minutes = max(1, seconds // 60)
        return f"Updated {minutes} min ago"
    if seconds < 86400:
        hours = max(1, seconds // 3600)
        return f"Updated {hours}h ago"
    if seconds < 172800:
        return "Updated yesterday"
    days = max(2, seconds // 86400)
    return f"Updated {days} days ago"


def entity_icon_name(entity: dict) -> str:
    domain = entity_domain(str(entity.get("entity_id", "")))
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
    device_class = str(attrs.get("device_class", "")).strip() if isinstance(attrs, dict) else ""
    mapping = {
        "light": "lightbulb",
        "switch": "toggle_on",
        "input_boolean": "toggle_on",
        "camera": "videocam",
        "climate": "thermostat",
        "sensor": "sensors",
        "binary_sensor": "sensors",
        "lock": "lock",
        "media_player": "music_note",
        "cover": "window",
        "fan": "mode_fan",
        "scene": "auto_awesome",
        "script": "bolt",
        "person": "person",
        "device_tracker": "location_on",
        "sun": "light_mode",
        "weather": "partly_cloudy_day",
        "alarm_control_panel": "shield",
    }
    if domain == "sensor" and device_class == "temperature":
        return "device_thermostat"
    if domain == "sensor" and device_class == "humidity":
        return "water_drop"
    return mapping.get(domain, "home")


def entity_mdi_icon_name(entity: dict) -> str:
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
    if isinstance(attrs, dict):
        icon_value = str(attrs.get("icon", "")).strip()
        if icon_value.startswith("mdi:"):
            return icon_value.split(":", 1)[1].strip()
    domain = entity_domain(str(entity.get("entity_id", "")))
    device_class = str(attrs.get("device_class", "")).strip() if isinstance(attrs, dict) else ""
    mapping = {
        "light": "lightbulb",
        "switch": "toggle-switch",
        "input_boolean": "toggle-switch",
        "camera": "video",
        "climate": "thermostat",
        "sensor": "gauge",
        "binary_sensor": "motion-sensor",
        "lock": "lock",
        "media_player": "music-note",
        "cover": "window-shutter",
        "fan": "fan",
        "scene": "creation",
        "script": "lightning-bolt",
        "person": "account",
        "device_tracker": "map-marker",
        "sun": "white-balance-sunny",
        "weather": "weather-partly-cloudy",
        "alarm_control_panel": "shield-home",
    }
    if domain == "sensor" and device_class == "temperature":
        return "thermometer"
    if domain == "sensor" and device_class == "humidity":
        return "water-percent"
    return mapping.get(domain, "home-assistant")


def cached_mdi_icon_path(icon_name: str) -> Path:
    safe = str(icon_name).strip().replace("/", "-")
    return HOME_ASSISTANT_ICON_DIR / f"{safe}.svg"


def ensure_mdi_icon_downloaded(icon_name: str, *, timeout: float = 8.0) -> Path | None:
    icon_name = str(icon_name).strip()
    if not icon_name:
        return None
    HOME_ASSISTANT_ICON_DIR.mkdir(parents=True, exist_ok=True)
    target = cached_mdi_icon_path(icon_name)
    if target.exists() and target.is_file():
        return target
    try:
        req = request.Request(
            f"{MDI_ICON_BASE_URL}/{icon_name}.svg",
            headers={"User-Agent": "Mozilla/5.0 HanautaHomeAssistant/1.0"},
        )
        with request.urlopen(req, timeout=timeout) as response:
            target.write_bytes(response.read())
        return target if target.exists() else None
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def prefetch_entity_icons(entities: list[dict], *, limit: int = 96) -> None:
    seen: set[str] = set()
    count = 0
    for entity in entities:
        icon_name = entity_mdi_icon_name(entity)
        if not icon_name or icon_name in seen:
            continue
        seen.add(icon_name)
        ensure_mdi_icon_downloaded(icon_name)
        count += 1
        if count >= limit:
            break


def icon_source_for_entity(entity: dict) -> str:
    icon_path = ensure_mdi_icon_downloaded(entity_mdi_icon_name(entity))
    if icon_path is None:
        return ""
    return QUrl.fromLocalFile(str(icon_path)).toString()


def entity_action(entity: dict) -> tuple[str, str, dict] | None:
    entity_id = str(entity.get("entity_id", "")).strip()
    if not entity_id:
        return None
    domain = entity_domain(entity_id)
    state = str(entity.get("state", "")).strip().lower()
    payload = {"entity_id": entity_id}
    if domain in {"light", "switch", "input_boolean", "fan"}:
        return domain, ("turn_off" if state == "on" else "turn_on"), payload
    if domain == "scene":
        return "scene", "turn_on", payload
    if domain == "script":
        return "script", "turn_on", payload
    return None
