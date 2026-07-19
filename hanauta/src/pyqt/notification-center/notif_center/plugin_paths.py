from __future__ import annotations

from pathlib import Path

from notif_center.paths import ROOT
from pyqt.shared.plugin_runtime import resolve_plugin_script


def _resolve_qcal_wrapper_script() -> Path | None:
    resolved = resolve_plugin_script("qcal-wrapper.py", ["calendar"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-calendar" / "qcal-wrapper.py",
        Path.home() / "dev" / "hanauta-plugin-calendar" / "qcal-wrapper.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None


QCAL_WRAPPER = _resolve_qcal_wrapper_script() or Path()

VPN_CONTROL_SCRIPT = resolve_plugin_script("vpn_control.py", ["vpn-control", "vpn"]) or Path()
CHRISTIAN_WIDGET_SCRIPT = resolve_plugin_script("christian_widget.py", ["religion-christian", "christian"]) or Path()
REMINDERS_WIDGET_SCRIPT = resolve_plugin_script("reminders_widget.py", ["reminders"]) or Path()
POMODORO_WIDGET_SCRIPT = resolve_plugin_script("pomodoro_widget.py", ["pomodoro"]) or Path()
RSS_WIDGET_SCRIPT = resolve_plugin_script("rss_widget.py", ["rss"]) or Path()
OBS_WIDGET_SCRIPT: Path | None = resolve_plugin_script("obs_widget.py", ["obs"])
CRYPTO_WIDGET_SCRIPT: Path | None = resolve_plugin_script("crypto_widget.py", ["crypto"])
VPS_WIDGET_SCRIPT: Path | None = resolve_plugin_script("vps_widget.py", ["vps"])


def _resolve_desktop_clock_widget_script() -> Path | None:
    resolved = resolve_plugin_script("desktop_clock_widget.py", ["desktop-clock", "clock"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-desktop-clock" / "desktop_clock_widget.py",
        Path.home() / "dev" / "hanauta-plugin-desktop-clock" / "desktop_clock_widget.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None


DESKTOP_CLOCK_WIDGET_SCRIPT: Path | None = _resolve_desktop_clock_widget_script()
GAME_MODE_POPUP_SCRIPT: Path | None = resolve_plugin_script("game_mode_popup.py", ["game-mode", "gamemode"])


def resolve_rss_widget_script(settings_state: dict | None = None) -> Path:
    if RSS_WIDGET_SCRIPT.exists():
        return RSS_WIDGET_SCRIPT
    state = settings_state if isinstance(settings_state, dict) else {}
    marketplace = state.get("marketplace", {}) if isinstance(state, dict) else {}
    installed = marketplace.get("installed_plugins", []) if isinstance(marketplace, dict) else []
    if isinstance(installed, list):
        for row in installed:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if plugin_id != "rss_widget":
                continue
            install_path = str(row.get("install_path", "")).strip()
            if not install_path:
                continue
            candidate = Path(install_path).expanduser() / "rss_widget.py"
            if candidate.exists():
                return candidate
    return RSS_WIDGET_SCRIPT
