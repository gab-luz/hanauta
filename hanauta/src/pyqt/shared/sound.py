#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sound manager for Hanauta - handles soundpack loading and playback.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from pyqt.shared.runtime import source_root, project_root


SOUNDPACK_DIR = project_root() / "assets" / "sounds"
DEFAULT_SOUNDPACK = "default"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

SOUND_EVENTS = {
    "notification": "New notification received",
    "click": "Button/UI click",
    "alert": "Alert/urgent notification",
    "message": "New message",
    "bell": "Bell/attention",
    "info": "Information dialog",
    "warning": "Warning dialog",
    "error": "Error dialog",
    "incoming": "Incoming call/connection",
    "outgoing": "Outgoing call/connection",
    "close": "Window/dialog close",
    "open": "Window/dialog open",
    "login": "Login/session start",
    "logout": "Logout/session end",
    "trash": "Trash empty/delete",
    "workspace_switch": "Workspace switched",
    "media_play": "Media playback started",
    "media_pause": "Media playback paused",
    "media_next": "Media next track",
    "media_prev": "Media previous track",
    "volume_change": "Volume changed",
    "brightness_change": "Brightness changed",
    "dnd_toggle": "Do Not Disturb toggled",
    "wifi_toggle": "Wi-Fi toggled",
    "bluetooth_toggle": "Bluetooth toggled",
}


def load_sound_settings() -> dict[str, Any]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload.get("sound", {}) if isinstance(payload.get("sound"), dict) else {}


def save_sound_settings(settings: dict[str, Any]) -> None:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    payload["sound"] = settings
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_soundpack_dir(soundpack_name: Optional[str] = None) -> Path:
    settings = load_sound_settings()
    name = soundpack_name or settings.get("soundpack", DEFAULT_SOUNDPACK)
    pack_dir = SOUNDPACK_DIR / name
    if not pack_dir.exists():
        pack_dir = SOUNDPACK_DIR / DEFAULT_SOUNDPACK
    return pack_dir


def list_soundpacks() -> list[str]:
    if not SOUNDPACK_DIR.exists():
        return [DEFAULT_SOUNDPACK]
    packs = [p.name for p in SOUNDPACK_DIR.iterdir() if p.is_dir()]
    return packs if packs else [DEFAULT_SOUNDPACK]


def get_sound_file(event: str, soundpack_name: Optional[str] = None) -> Optional[Path]:
    pack_dir = get_soundpack_dir(soundpack_name)
    sound_file = pack_dir / f"{event}.oga"
    if sound_file.exists():
        return sound_file
    fallbacks = [
        pack_dir / f"{event}.ogg",
        pack_dir / f"{event}.wav",
    ]
    for fb in fallbacks:
        if fb.exists():
            return fb
    return None


def play_sound(
    event: str,
    soundpack_name: Optional[str] = None,
    volume: int = 65536,
    async_play: bool = True,
) -> bool:
    settings = load_sound_settings()
    if not settings.get("enabled", True):
        return False

    sound_file = get_sound_file(event, soundpack_name)
    if not sound_file:
        return False

    if not shutil.which("paplay"):
        return False

    cmd = ["paplay", f"--volume={volume}", str(sound_file)]

    try:
        if async_play:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=2.0)
        return True
    except Exception:
        return False


def play_sound_sync(event: str, soundpack_name: Optional[str] = None, volume: int = 65536) -> bool:
    return play_sound(event, soundpack_name, volume, async_play=False)


def is_sound_enabled() -> bool:
    settings = load_sound_settings()
    return settings.get("enabled", True)


def set_sound_enabled(enabled: bool) -> None:
    settings = load_sound_settings()
    settings["enabled"] = bool(enabled)
    save_sound_settings(settings)


def get_current_soundpack() -> str:
    settings = load_sound_settings()
    return settings.get("soundpack", DEFAULT_SOUNDPACK)


def set_soundpack(name: str) -> bool:
    if name not in list_soundpacks():
        return False
    settings = load_sound_settings()
    settings["soundpack"] = name
    save_sound_settings(settings)
    return True


def get_event_volume(event: str) -> int:
    settings = load_sound_settings()
    volumes = settings.get("volumes", {}) if isinstance(settings.get("volumes"), dict) else {}
    default_volume = settings.get("default_volume", 65536)
    return int(volumes.get(event, default_volume))


def set_event_volume(event: str, volume: int) -> None:
    settings = load_sound_settings()
    volumes = settings.get("volumes", {}) if isinstance(settings.get("volumes"), dict) else {}
    volumes[event] = max(0, min(65536, int(volume)))
    settings["volumes"] = volumes
    save_sound_settings(settings)


def get_default_volume() -> int:
    settings = load_sound_settings()
    return int(settings.get("default_volume", 65536))


def set_default_volume(volume: int) -> None:
    settings = load_sound_settings()
    settings["default_volume"] = max(0, min(65536, int(volume)))
    save_sound_settings(settings)


def get_soundpack_info(soundpack_name: Optional[str] = None) -> dict[str, Any]:
    pack_dir = get_soundpack_dir(soundpack_name)
    info_file = pack_dir / "soundpack.json"
    if info_file.exists():
        try:
            return json.loads(info_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "name": pack_dir.name,
        "display_name": pack_dir.name.replace("-", " ").title(),
        "description": "Soundpack",
        "author": "",
        "version": "1.0",
        "sounds": {},
    }


def create_soundpack_template(name: str, display_name: str, description: str = "", author: str = "") -> Path:
    pack_dir = SOUNDPACK_DIR / name
    pack_dir.mkdir(parents=True, exist_ok=True)
    info = {
        "name": name,
        "display_name": display_name,
        "description": description,
        "author": author,
        "version": "1.0",
        "sounds": {event: f"{event}.oga" for event in SOUND_EVENTS},
    }
    (pack_dir / "soundpack.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return pack_dir


DEFAULT_SOUND_SETTINGS = {
    "enabled": True,
    "soundpack": DEFAULT_SOUNDPACK,
    "default_volume": 65536,
    "volumes": {},
}


def ensure_sound_settings() -> dict[str, Any]:
    settings = load_sound_settings()
    merged = dict(DEFAULT_SOUND_SETTINGS)
    for key, default in DEFAULT_SOUND_SETTINGS.items():
        if key not in settings:
            settings[key] = default
    save_sound_settings(settings)
    return load_sound_settings()