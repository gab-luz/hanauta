from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic

from PyQt6.QtCore import QThread, pyqtSignal

from notif_center.paths import SCRIPTS_DIR
from notif_center.utils import run_cmd, run_script


DAEMON_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
WIFI_STATE_FILE = DAEMON_STATE_DIR / "wifi.json"
SYSTEM_STATE_FILE = DAEMON_STATE_DIR / "system_state.json"
PHONE_CACHE_FILE = Path.home() / ".cache" / "hanauta" / "phone_state.json"
CACHE_DIR = Path.home() / ".cache" / "hanauta"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PollResult:
    timestamp: float = 0.0
    wifi_on: bool = False
    wifi_ssid: str = "Disconnected"
    bt_on: bool = False
    dnd_on: bool = False
    airplane_on: bool = False
    night_on: bool = False
    caffeine_on: bool = False
    brightness: int = 67
    volume: int = 82
    media_title: str = ""
    media_artist: str = ""
    media_status: str = ""
    media_player: str = ""
    media_art: str = ""
    media_url: str = ""
    media_position_ms: int = 0
    media_duration_ms: int = 0
    phone_raw: str = ""
    uptime: str = ""


def _read_daemon_wifi() -> dict:
    try:
        raw = WIFI_STATE_FILE.read_text(encoding="utf-8", errors="ignore")
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _read_system_state() -> dict:
    try:
        raw = SYSTEM_STATE_FILE.read_text(encoding="utf-8", errors="ignore")
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _run_script(script: str, *args: str) -> str:
    path = SCRIPTS_DIR / script
    if not path.exists():
        return ""
    try:
        res = subprocess.run(
            [str(path), *args],
            capture_output=True, text=True, timeout=2.0,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def poll_all() -> PollResult:
    r = PollResult(timestamp=monotonic())

    wifi_data = _read_daemon_wifi()
    if wifi_data:
        scanning = wifi_data.get("scanning", [])
        connected = any(ap.get("in_use") for ap in scanning) or bool(
            wifi_data.get("active_ssid")
        )
        active_ssid = wifi_data.get("active_ssid", "")
        radio_on = wifi_data.get("radio_on", True)
        r.wifi_on = connected
        r.wifi_ssid = str(active_ssid or "Connected" if connected else "Disconnected")
        r.airplane_on = not radio_on
    else:
        wifi_status = _run_script("network.sh", "status")
        r.wifi_on = wifi_status == "Connected"
        r.wifi_ssid = _run_script("network.sh", "ssid") or "Disconnected"
        radio_raw = _run_script("network.sh", "radio-status")
        r.airplane_on = radio_raw == "off"

    sys_state = _read_system_state()

    bt_raw = sys_state.get("bluetooth", "") if sys_state else ""
    r.bt_on = bt_raw == "on"
    if not bt_raw:
        bt_raw = _run_script("bluetooth", "state")
        r.bt_on = bt_raw == "on"

    dnd_raw = run_cmd([
        "gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
        "--object-path", "/org/freedesktop/Notifications",
        "--method", "org.freedesktop.DBus.Properties.Get",
        "org.freedesktop.Notifications", "Inhibited",
    ])
    r.dnd_on = dnd_raw.strip() == "(true,)" if dnd_raw else False

    night_raw = sys_state.get("redshift", "") if sys_state else ""
    r.night_on = night_raw == "on"
    if not night_raw:
        night_raw = _run_script("redshift", "state")
        r.night_on = night_raw == "on"

    caffeine_raw = sys_state.get("caffeine", "") if sys_state else ""
    r.caffeine_on = caffeine_raw == "on"
    if not caffeine_raw:
        caffeine_raw = _run_script("caffeine.sh", "status")
        r.caffeine_on = caffeine_raw == "on"

    try:
        br = sys_state.get("brightness", "") if sys_state else ""
        r.brightness = int(br) if br else int(_run_script("brightness.sh", "br") or "67")
    except Exception:
        r.brightness = 67
    try:
        vol = sys_state.get("volume", "") if sys_state else ""
        r.volume = int(vol) if vol else int(_run_script("volume.sh", "vol") or "82")
    except Exception:
        r.volume = 82

    r.media_title = _run_script("mpris.sh", "title") or ""
    r.media_artist = _run_script("mpris.sh", "artist") or ""

    player = _run_script("mpris.sh", "player")
    r.media_player = player
    r.media_status = _run_script("mpris.sh", "status") or "Stopped"
    r.media_art = _run_script("mpris.sh", "coverloc")
    if player:
        r.media_url = run_cmd([
            "playerctl", f"--player={player}", "metadata",
            "--format", "{{xesam:url}}",
        ])
        pos_raw = run_cmd(["playerctl", f"--player={player}", "position"])
        try:
            r.media_position_ms = max(0, int(float(pos_raw) * 1000))
        except Exception:
            r.media_position_ms = 0
        len_raw = run_cmd([
            "playerctl", f"--player={player}", "metadata",
            "--format", "{{mpris:length}}",
        ])
        try:
            r.media_duration_ms = max(0, int(int(len_raw) / 1000))
        except Exception:
            r.media_duration_ms = 0

    phone_data = sys_state.get("phone", {}) if sys_state else {}
    r.phone_raw = json.dumps(phone_data) if isinstance(phone_data, dict) and phone_data else _run_script("phone_info.sh")

    uptime_raw = run_cmd(["uptime", "-p"])
    r.uptime = uptime_raw.removeprefix("up ").strip()

    return r


class BackgroundPoller(QThread):
    pollComplete = pyqtSignal(object)

    def __init__(self, interval_ms: int = 3500, parent=None):
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._stop = False
        self._last_result: PollResult | None = None

    def stop(self):
        self._stop = True

    @property
    def last_result(self) -> PollResult | None:
        return self._last_result

    def run(self):
        import time
        while not self._stop:
            result = poll_all()
            self._last_result = result
            self.pollComplete.emit(result)
            deadline = monotonic() + self._interval_ms / 1000.0
            while monotonic() < deadline and not self._stop:
                time.sleep(0.05)


_STATIC_CACHE: dict[str, tuple[str, float]] = {}
_STATIC_TTL = 60.0


def poll_static(key: str, cmd: list[str], ttl: float = _STATIC_TTL) -> str:
    now = monotonic()
    cached = _STATIC_CACHE.get(key)
    if cached and (now - cached[1]) < ttl:
        return cached[0]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
        val = res.stdout.strip()
        _STATIC_CACHE[key] = (val, now)
        return val
    except Exception:
        return ""


def get_static_val(key: str, cmd: list[str]) -> str:
    return poll_static(key, cmd, ttl=3600.0)


_PIXMAP_CACHE: dict[str, object] = {}


def cache_pixmap(key: str, factory):
    if key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[key]
    pixmap = factory()
    if pixmap is not None:
        _PIXMAP_CACHE[key] = pixmap
    return pixmap


def has_cached_pixmap(key: str) -> bool:
    return key in _PIXMAP_CACHE


def get_cached_pixmap(key: str):
    return _PIXMAP_CACHE.get(key)


def store_pixmap(key: str, pixmap):
    _PIXMAP_CACHE[key] = pixmap


def clear_pixmap_cache():
    _PIXMAP_CACHE.clear()
