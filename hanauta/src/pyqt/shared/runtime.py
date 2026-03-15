from __future__ import annotations

import sys
from pathlib import Path


ENTRYPOINT_BINARIES = {
    "pyqt/ai-popup/ai_popup.py": "hanauta-ai-popup",
    "pyqt/bar/ui_bar.py": "hanauta-bar",
    "pyqt/control-center/control_center.py": "hanauta-control-center",
    "pyqt/dock/dock.py": "hanauta-dock",
    "pyqt/launcher/launcher.py": "hanauta-launcher",
    "pyqt/notification-center/notification_center.py": "hanauta-notification-center",
    "pyqt/notification-daemon/notification_daemon.py": "hanauta-notification-daemon",
    "pyqt/powermenu/powermenu.py": "hanauta-powermenu",
    "pyqt/settings-page/settings.py": "hanauta-settings",
    "pyqt/shared/action_notification.py": "hanauta-action-notification",
    "pyqt/widget-calendar/calendar_popup.py": "hanauta-calendar-popup",
    "pyqt/widget-calendar/qcal-wrapper.py": "hanauta-qcal-wrapper",
    "pyqt/widget-crypto/crypto_widget.py": "hanauta-crypto-widget",
    "pyqt/widget-desktop-clock/desktop_clock_widget.py": "hanauta-clock",
    "pyqt/widget-game-mode/game_mode_popup.py": "hanauta-game-mode-popup",
    "pyqt/widget-hotkeys-overlay/hotkeys_overlay.py": "hanauta-hotkeys-overlay",
    "pyqt/widget-ntfy-control/ntfy_popup.py": "hanauta-ntfy-popup",
    "pyqt/widget-obs/obs_widget.py": "hanauta-obs-widget",
    "pyqt/widget-pomodoro/pomodoro_widget.py": "hanauta-pomodoro-widget",
    "pyqt/widget-religion-christian/christian_widget.py": "hanauta-christian-widget",
    "pyqt/widget-reminders/reminders_widget.py": "hanauta-reminders-widget",
    "pyqt/widget-rss/rss_widget.py": "hanauta-rss-widget",
    "pyqt/widget-vpn-control/vpn_control.py": "hanauta-vpn-control",
    "pyqt/widget-vps/vps_widget.py": "hanauta-vps-widget",
    "pyqt/widget-weather/weather_popup.py": "hanauta-weather-popup",
    "pyqt/widget-wifi-control/wifi_control.py": "hanauta-wifi-control",
    "pyqt/widget-window-switcher/window_switcher.py": "hanauta-window-switcher",
}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_executable_path() -> Path:
    argv0 = str(sys.argv[0]).strip()
    if argv0:
        try:
            return Path(argv0).resolve()
        except Exception:
            pass
    return Path(__file__).resolve()


def project_root() -> Path:
    if is_frozen():
        exe_path = Path(sys.argv[0]).resolve()
        if exe_path.parent.name.endswith(".dist") and exe_path.parent.parent.name == "nuitka":
            return exe_path.parents[4]
        if exe_path.parent.name == "bin" and exe_path.parent.parent.name == "hanauta":
            return exe_path.parents[2]
        return exe_path.parent
    return Path(__file__).resolve().parents[4]


def hanauta_root() -> Path:
    return project_root() / "hanauta"


def source_root() -> Path:
    return hanauta_root() / "src"


def assets_root() -> Path:
    return project_root() / "assets"


def fonts_root() -> Path:
    return assets_root() / "fonts"


def scripts_root() -> Path:
    return hanauta_root() / "scripts"


def python_executable() -> str:
    venv_python = project_root() / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _normalize_script_path(script_path: Path | str) -> Path:
    return Path(script_path).resolve()


def entry_binary_name(script_path: Path | str) -> str | None:
    try:
        relative = _normalize_script_path(script_path).relative_to(source_root())
    except ValueError:
        return None
    return ENTRYPOINT_BINARIES.get(relative.as_posix())


def entry_binary_path(script_path: Path | str) -> Path | None:
    binary_name = entry_binary_name(script_path)
    if not binary_name:
        return None
    candidate = hanauta_root() / "bin" / binary_name
    if candidate.exists():
        return candidate
    return None


def entry_target(script_path: Path | str) -> Path:
    return entry_binary_path(script_path) or _normalize_script_path(script_path)


def entry_command(script_path: Path | str, *args: str) -> list[str]:
    binary = entry_binary_path(script_path)
    if binary is not None:
        return [str(binary), *args]
    script = _normalize_script_path(script_path)
    if not script.exists():
        return []
    return [python_executable(), str(script), *args]


def entry_patterns(script_path: Path | str) -> list[str]:
    script = _normalize_script_path(script_path)
    patterns = {str(script)}
    binary = entry_binary_path(script)
    if binary is not None:
        patterns.add(str(binary.resolve()))
        patterns.add(str(binary))
    return [pattern for pattern in patterns if pattern]
