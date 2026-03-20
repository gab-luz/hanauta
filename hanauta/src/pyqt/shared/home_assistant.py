from __future__ import annotations

import json
from urllib import error, request


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

