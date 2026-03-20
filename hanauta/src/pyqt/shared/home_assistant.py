from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from PyQt6.QtCore import QUrl


ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
HOME_ASSISTANT_ICON_DIR = ASSETS_DIR / "home-assistant-icons"
MDI_ICON_BASE_URL = "https://raw.githubusercontent.com/Templarian/MaterialDesign/master/svg"
SERVICE_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
SERVICE_HOME_ASSISTANT_CACHE = SERVICE_STATE_DIR / "home_assistant.json"

_FILL_ATTR_RE = re.compile(r'\sfill="[^"]*"')
_HEX_RE = re.compile(r"[^0-9a-fA-F]")


def normalize_ha_url(url: str) -> str:
    return str(url).strip().rstrip("/")


def load_service_home_assistant_cache(base_url: str = "") -> dict | None:
    try:
        payload = json.loads(SERVICE_HOME_ASSISTANT_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("payload")
    if not isinstance(raw, list):
        return None
    cached_url = normalize_ha_url(str(payload.get("url", "")))
    if base_url and cached_url and cached_url != normalize_ha_url(base_url):
        return None
    return payload


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


def entity_custom_mdi_icon_name(entity: dict) -> str:
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
    if isinstance(attrs, dict):
        icon_value = str(attrs.get("icon", "")).strip()
        if icon_value.startswith("mdi:"):
            return icon_value.split(":", 1)[1].strip()
    return ""


def entity_mdi_icon_name(entity: dict) -> str:
    custom = entity_custom_mdi_icon_name(entity)
    if custom:
        return custom

    domain = entity_domain(str(entity.get("entity_id", "")))
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
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


def _normalize_hex_color(color: str, default: str = "#FFFFFF") -> str:
    text = str(color or "").strip()
    if text.startswith("#"):
        text = text[1:]
    text = _HEX_RE.sub("", text)
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return default
    return f"#{text.upper()}"


def cached_mdi_icon_path(icon_name: str, tint_color: str = "#FFFFFF") -> Path:
    safe_name = str(icon_name).strip().replace("/", "-")
    return HOME_ASSISTANT_ICON_DIR / f"{safe_name}.svg"


def _tinted_svg_markup(svg_text: str, tint_color: str) -> str:
    clean = str(svg_text or "").replace("\ufeff", "").strip()
    if not clean:
        return clean
    clean = _FILL_ATTR_RE.sub("", clean)
    if "<svg" in clean:
        clean = clean.replace(
            "<svg",
            f'<svg fill="{_normalize_hex_color(tint_color)}" preserveAspectRatio="xMidYMid meet"',
            1,
        )
    return clean


def _purge_legacy_tinted_icon_variants(icon_name: str, keep: Path) -> None:
    safe_name = str(icon_name).strip().replace("/", "-")
    for candidate in HOME_ASSISTANT_ICON_DIR.glob(f"{safe_name}--*.svg"):
        if candidate == keep:
            continue
        try:
            candidate.unlink(missing_ok=True)
        except Exception:
            pass


def ensure_mdi_icon_downloaded(icon_name: str, *, tint_color: str = "#FFFFFF", timeout: float = 8.0) -> Path | None:
    icon_name = str(icon_name).strip()
    if not icon_name:
        return None

    HOME_ASSISTANT_ICON_DIR.mkdir(parents=True, exist_ok=True)
    target = cached_mdi_icon_path(icon_name, tint_color=tint_color)

    try:
        req = request.Request(
            f"{MDI_ICON_BASE_URL}/{icon_name}.svg",
            headers={"User-Agent": "Mozilla/5.0 HanautaHomeAssistant/1.0"},
        )
        with request.urlopen(req, timeout=timeout) as response:
            raw_text = response.read().decode("utf-8", errors="replace")
        desired = _tinted_svg_markup(raw_text, tint_color)
        if target.exists() and target.is_file():
            try:
                if target.read_text(encoding="utf-8") == desired:
                    _purge_legacy_tinted_icon_variants(icon_name, target)
                    return target
            except Exception:
                pass
        target.write_text(desired, encoding="utf-8")
        _purge_legacy_tinted_icon_variants(icon_name, target)
        return target if target.exists() else None
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def prefetch_entity_icons(entities: list[dict], *, tint_color: str = "#FFFFFF", limit: int = 96) -> None:
    seen: set[str] = set()
    count = 0
    for entity in entities:
        icon_name = entity_mdi_icon_name(entity)
        if not icon_name or icon_name in seen:
            continue
        seen.add(icon_name)
        ensure_mdi_icon_downloaded(icon_name, tint_color=tint_color)
        count += 1
        if count >= limit:
            break


def _existing_cached_icon_path(icon_name: str, tint_color: str = "#FFFFFF") -> Path | None:
    tinted = cached_mdi_icon_path(icon_name, tint_color=tint_color)
    if tinted.exists() and tinted.is_file():
        return tinted
    plain = HOME_ASSISTANT_ICON_DIR / f"{str(icon_name).strip().replace('/', '-')}.svg"
    if plain.exists() and plain.is_file():
        return plain
    return None


def icon_source_for_entity(entity: dict, *, tint_color: str = "#FFFFFF") -> str:
    icon_name = entity_mdi_icon_name(entity)
    if not icon_name:
        return ""
    icon_path = _existing_cached_icon_path(icon_name, tint_color=tint_color)
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
