#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.home_assistant import load_service_home_assistant_cache, prefetch_entity_icons
from pyqt.shared.theme import load_theme_palette


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"


def load_settings_state() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    services = payload.get("services", {})
    if not isinstance(services, dict):
        services = {}
    payload["services"] = services
    home_assistant = payload.get("home_assistant", {})
    if not isinstance(home_assistant, dict):
        home_assistant = {}
    payload["home_assistant"] = home_assistant
    return payload


def home_assistant_enabled(settings: dict) -> bool:
    services = settings.get("services", {})
    if not isinstance(services, dict):
        return False
    service = services.get("home_assistant", {})
    if not isinstance(service, dict):
        return False
    return bool(service.get("enabled", True))


def configured_base_url(settings: dict) -> str:
    home_assistant = settings.get("home_assistant", {})
    if not isinstance(home_assistant, dict):
        return ""
    return str(home_assistant.get("url", "")).strip()


def prefetch_once() -> int:
    settings = load_settings_state()
    if not home_assistant_enabled(settings):
        return 0
    cache = load_service_home_assistant_cache(configured_base_url(settings))
    if not isinstance(cache, dict):
        return 0
    payload = cache.get("payload", [])
    if not isinstance(payload, list):
        return 0
    theme = load_theme_palette()
    entities = [item for item in payload if isinstance(item, dict)]
    prefetch_entity_icons(entities, tint_color=theme.primary, limit=180)
    return len(entities)


def main() -> int:
    if "--once" in sys.argv:
        prefetch_once()
        return 0

    last_stamp = ""
    while True:
        settings = load_settings_state()
        if home_assistant_enabled(settings):
            cache = load_service_home_assistant_cache(configured_base_url(settings))
            stamp = str(cache.get("updated_at", "")).strip() if isinstance(cache, dict) else ""
            if stamp and stamp != last_stamp:
                prefetch_once()
                last_stamp = stamp
        else:
            last_stamp = ""
        time.sleep(45)


if __name__ == "__main__":
    raise SystemExit(main())
