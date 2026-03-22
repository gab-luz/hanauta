from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "game-mode"
STATE_FILE = STATE_DIR / "state.json"
SERVICE_NAME = "gamemoded.service"
MANUAL_SOURCE = "manual"
LUTRIS_AUTO_SOURCE = "lutris_auto"
PICOM_CONFIG_FILE = Path(__file__).resolve().parents[4] / "picom.conf"
MATUGEN_SCRIPT = Path(__file__).resolve().parents[4] / "hanauta" / "scripts" / "run_matugen.sh"
CURRENT_WALLPAPER = Path.home() / ".wallpapers" / "wallpaper.png"
MATUGEN_PAUSE_FILE = Path.home() / ".local" / "state" / "hanauta" / "matugen" / "paused-by-gamemode"
I3_CONFIG_FILE = Path(__file__).resolve().parents[4] / "config"
GAME_MODE_I3_KEYS = (
    "default_border",
    "default_floating_border",
    "client.focused",
    "client.focused_inactive",
    "client.unfocused",
    "client.urgent",
    "client.background",
)
GAME_MODE_I3_PROFILE: dict[str, str] = {
    "default_border": "default_border pixel 1",
    "default_floating_border": "default_floating_border pixel 1",
    "client.focused": "client.focused          #5b5b5b #5b5b5b #e8e8e8 #5b5b5b #5b5b5b",
    "client.focused_inactive": "client.focused_inactive #323232 #323232 #bcbcbc #323232 #323232",
    "client.unfocused": "client.unfocused        #323232 #323232 #bcbcbc #323232 #323232",
    "client.urgent": "client.urgent           #7a4a4a #7a4a4a #f0e6e6 #7a4a4a #7a4a4a",
    "client.background": "client.background       #101010",
}
GAME_MODE_PICOM_KEYS = (
    "shadow",
    "shadow-radius",
    "shadow-opacity",
    "shadow-offset-x",
    "shadow-offset-y",
    "fading",
    "active-opacity",
    "inactive-opacity",
    "corner-radius",
    "transparent-clipping",
    "detect-rounded-corners",
)
GAME_MODE_PICOM_PROFILE: dict[str, object] = {
    "shadow": False,
    "shadow-radius": 0,
    "shadow-opacity": 0.0,
    "shadow-offset-x": 0,
    "shadow-offset-y": 0,
    "fading": False,
    "active-opacity": 1.0,
    "inactive-opacity": 1.0,
    "corner-radius": 0,
    "transparent-clipping": False,
    "detect-rounded-corners": False,
}
GAME_MODE_PICOM_RESTORE_FALLBACK: dict[str, object] = {
    "shadow": True,
    "shadow-radius": 42,
    "shadow-opacity": 0.42,
    "shadow-offset-x": 0,
    "shadow-offset-y": 0,
    "fading": True,
    "active-opacity": 1.0,
    "inactive-opacity": 1.0,
    "corner-radius": 18,
    "transparent-clipping": False,
    "detect-rounded-corners": True,
}


def _run_text(cmd: list[str], timeout: float = 4.0) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, (result.stdout or result.stderr or "").strip()
    except Exception as exc:
        return 1, str(exc)


def gamemoded_available() -> bool:
    return shutil.which("gamemoded") is not None


def systemctl_available() -> bool:
    return shutil.which("systemctl") is not None


def service_enabled() -> bool:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return False
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return False
    current = services.get("game_mode", {})
    if not isinstance(current, dict):
        return False
    return bool(current.get("enabled", False))


def is_active() -> bool:
    if systemctl_available():
        code, _ = _run_text(["systemctl", "--user", "is-active", SERVICE_NAME], timeout=2.0)
        if code == 0:
            return True
    code, _ = _run_text(["pgrep", "-x", "gamemoded"], timeout=2.0)
    return code == 0


def _persist_runtime(active: bool, note: str) -> None:
    state = _load_runtime_state()
    state["active"] = bool(active)
    state["note"] = note
    _write_runtime_state(state)


def _load_runtime_state() -> dict:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _write_runtime_state(payload: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_settings_state() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _save_settings_state(payload: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_picom_text() -> str:
    try:
        return PICOM_CONFIG_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""


def _parse_picom_settings(text: str) -> dict[str, object]:
    defaults: dict[str, object] = {
        "shadow": True,
        "shadow-radius": 18,
        "shadow-opacity": 0.18,
        "shadow-offset-x": -12,
        "shadow-offset-y": -12,
        "fading": False,
        "active-opacity": 1.0,
        "inactive-opacity": 1.0,
        "corner-radius": 18,
        "transparent-clipping": False,
        "detect-rounded-corners": True,
    }

    def find_value(key: str) -> str | None:
        pattern = rf"(?m)^\s*{re.escape(key)}\s*=\s*(.+?);\s*$"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    parsed = dict(defaults)
    for key, default in defaults.items():
        value = find_value(key)
        if value is None:
            continue
        if isinstance(default, bool):
            parsed[key] = value.lower() == "true"
        elif isinstance(default, int):
            try:
                parsed[key] = int(float(value))
            except Exception:
                parsed[key] = default
        elif isinstance(default, float):
            try:
                parsed[key] = float(value)
            except Exception:
                parsed[key] = default
    return parsed


def _format_picom_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        rendered = f"{value:.2f}"
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
    return str(value)


def _update_picom_config(text: str, values: dict[str, object]) -> str:
    updated = text
    for key, value in values.items():
        line = f"{key} = {_format_picom_value(value)};"
        pattern = rf"(?m)^\s*{re.escape(key)}\s*=\s*.+?;\s*(?:#.*)?$"
        if re.search(pattern, updated):
            updated = re.sub(pattern, line, updated)
        else:
            updated = f"{line}\n{updated}"
    return updated


def _restart_picom() -> None:
    subprocess.run(["pkill", "-x", "picom"], capture_output=True, text=True, check=False)
    subprocess.run(
        ["picom", "--config", str(PICOM_CONFIG_FILE), "--daemon"],
        capture_output=True,
        text=True,
        check=False,
    )


def _stop_picom() -> None:
    subprocess.run(["pkill", "-x", "picom"], capture_output=True, text=True, check=False)


def _picom_running() -> bool:
    code, _ = _run_text(["pgrep", "-x", "picom"], timeout=2.0)
    return code == 0


def _restart_window_manager() -> None:
    subprocess.run(["i3-msg", "restart"], capture_output=True, text=True, check=False)


def _reload_window_manager() -> None:
    subprocess.run(["i3-msg", "reload"], capture_output=True, text=True, check=False)


def _refresh_visual_stack(restart_wm: bool = False) -> None:
    _restart_picom()
    if restart_wm:
        _restart_window_manager()


def _matugen_enabled_in_settings(settings: dict | None = None) -> bool:
    payload = settings if isinstance(settings, dict) else _load_settings_state()
    appearance = payload.get("appearance", {})
    if not isinstance(appearance, dict):
        return False
    if bool(appearance.get("use_matugen_palette", False)):
        return True
    return str(appearance.get("theme_choice", "")).strip().lower() == "wallpaper_aware"


def _pause_matugen() -> None:
    MATUGEN_PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MATUGEN_PAUSE_FILE.write_text("paused\n", encoding="utf-8")


def _resume_matugen() -> None:
    try:
        MATUGEN_PAUSE_FILE.unlink()
    except FileNotFoundError:
        pass


def _preferred_wallpaper(settings: dict | None = None) -> Path | None:
    payload = settings if isinstance(settings, dict) else _load_settings_state()
    appearance = payload.get("appearance", {})
    candidate = None
    if isinstance(appearance, dict):
        candidate = Path(str(appearance.get("wallpaper_path", ""))).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate
    if CURRENT_WALLPAPER.exists() and CURRENT_WALLPAPER.is_file():
        return CURRENT_WALLPAPER
    return None


def _refresh_matugen_if_enabled() -> None:
    settings = _load_settings_state()
    if not _matugen_enabled_in_settings(settings):
        return
    wallpaper = _preferred_wallpaper(settings)
    if wallpaper is None or not MATUGEN_SCRIPT.exists():
        return
    env = dict(os.environ)
    env["HANAUTA_SUPPRESS_MATUGEN_NOTIFY"] = "1"
    subprocess.run(
        [str(MATUGEN_SCRIPT), str(wallpaper)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _read_i3_config_text() -> str:
    try:
        return I3_CONFIG_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""


def _extract_i3_lines(text: str) -> dict[str, str]:
    extracted: dict[str, str] = {}
    for key in GAME_MODE_I3_KEYS:
        pattern = re.compile(rf"(?m)^\s*{re.escape(key)}[^\n]*$")
        match = pattern.search(text)
        if match:
            extracted[key] = match.group(0).strip()
    return extracted


def _replace_i3_line(text: str, prefix: str, new_line: str) -> str:
    pattern = re.compile(rf"(?m)^\s*{re.escape(prefix)}[^\n]*$")
    if pattern.search(text):
        return pattern.sub(new_line, text, count=1)
    return text + ("\n" if not text.endswith("\n") else "") + new_line + "\n"


def _apply_i3_profile(lines: dict[str, str]) -> None:
    text = _read_i3_config_text()
    if not text:
        return
    updated = text
    for key, line in lines.items():
        updated = _replace_i3_line(updated, key, line)
    I3_CONFIG_FILE.write_text(updated, encoding="utf-8")
    _reload_window_manager()


def _looks_like_game_mode_profile(values: dict[str, object]) -> bool:
    for key, expected in GAME_MODE_PICOM_PROFILE.items():
        if values.get(key) != expected:
            return False
    return True


def _apply_game_mode_visuals() -> None:
    runtime_state = _load_runtime_state()
    settings = _load_settings_state()
    appearance = settings.get("appearance", {})
    if not isinstance(appearance, dict):
        appearance = {}
        settings["appearance"] = appearance
    visual_backup = runtime_state.get("visual_backup", {})
    if not isinstance(visual_backup, dict):
        visual_backup = {}
    if not visual_backup:
        picom_current = _parse_picom_settings(_read_picom_text())
        i3_current = _extract_i3_lines(_read_i3_config_text())
        visual_backup = {
            "appearance": {
                "transparency": bool(appearance.get("transparency", True)),
            },
            "picom": {key: picom_current.get(key) for key in GAME_MODE_PICOM_KEYS},
            "i3": i3_current,
        }
    else:
        if "appearance" not in visual_backup:
            visual_backup["appearance"] = {"transparency": bool(appearance.get("transparency", True))}
        if "picom" not in visual_backup:
            picom_current = _parse_picom_settings(_read_picom_text())
            visual_backup["picom"] = {key: picom_current.get(key) for key in GAME_MODE_PICOM_KEYS}
        if "i3" not in visual_backup:
            visual_backup["i3"] = _extract_i3_lines(_read_i3_config_text())
    runtime_state["visual_backup"] = visual_backup
    runtime_state["matugen_was_enabled"] = _matugen_enabled_in_settings(settings)
    runtime_state["picom_was_running"] = _picom_running()
    _pause_matugen()
    appearance["transparency"] = False
    _save_settings_state(settings)
    picom_text = _read_picom_text()
    if picom_text:
        PICOM_CONFIG_FILE.write_text(
            _update_picom_config(picom_text, dict(GAME_MODE_PICOM_PROFILE)),
            encoding="utf-8",
        )
        _stop_picom()
    _apply_i3_profile(dict(GAME_MODE_I3_PROFILE))
    _stop_picom()
    runtime_state["visuals_suppressed"] = True
    _write_runtime_state(runtime_state)


def _restore_game_mode_visuals() -> None:
    runtime_state = _load_runtime_state()
    backup = runtime_state.get("visual_backup", {})
    if not isinstance(backup, dict):
        backup = {}

    appearance_backup = backup.get("appearance", {})
    settings = _load_settings_state()
    appearance = settings.get("appearance", {})
    if not isinstance(appearance, dict):
        appearance = {}
        settings["appearance"] = appearance
    if isinstance(appearance_backup, dict) and "transparency" in appearance_backup:
        appearance["transparency"] = bool(appearance_backup.get("transparency", True))
        _save_settings_state(settings)

    picom_backup = backup.get("picom", {})
    i3_backup = backup.get("i3", {})
    picom_text = _read_picom_text()
    should_restart_picom = bool(runtime_state.get("picom_was_running", True))
    if picom_text and isinstance(picom_backup, dict) and picom_backup:
        restored_values = {key: picom_backup[key] for key in GAME_MODE_PICOM_KEYS if key in picom_backup}
        PICOM_CONFIG_FILE.write_text(
            _update_picom_config(picom_text, restored_values),
            encoding="utf-8",
        )
        if should_restart_picom:
            _restart_picom()
    elif picom_text:
        picom_current = _parse_picom_settings(picom_text)
        if _looks_like_game_mode_profile(picom_current):
            if "transparency" not in appearance_backup:
                appearance["transparency"] = True
                _save_settings_state(settings)
            PICOM_CONFIG_FILE.write_text(
                _update_picom_config(picom_text, dict(GAME_MODE_PICOM_RESTORE_FALLBACK)),
                encoding="utf-8",
            )
            if should_restart_picom:
                _restart_picom()

    if isinstance(i3_backup, dict) and i3_backup:
        restored_i3 = {key: str(i3_backup[key]) for key in GAME_MODE_I3_KEYS if key in i3_backup}
        _apply_i3_profile(restored_i3)
    _restart_window_manager()

    should_resume_matugen = bool(runtime_state.get("matugen_was_enabled", False))
    _resume_matugen()
    if should_resume_matugen:
        _refresh_matugen_if_enabled()

    runtime_state = _load_runtime_state()
    runtime_state.pop("visual_backup", None)
    runtime_state.pop("matugen_was_enabled", None)
    runtime_state.pop("picom_was_running", None)
    runtime_state["visuals_suppressed"] = False
    _write_runtime_state(runtime_state)


def _mark_runtime_flag(key: str, value: object) -> None:
    runtime_state = _load_runtime_state()
    runtime_state[key] = value
    _write_runtime_state(runtime_state)


def summary() -> dict[str, object]:
    available = gamemoded_available()
    active = is_active() if available else False
    runtime_state = _load_runtime_state()
    visuals_suppressed = bool(runtime_state.get("visuals_suppressed", False))
    source = str(runtime_state.get("activation_source", MANUAL_SOURCE)).strip() or MANUAL_SOURCE
    if not available:
        note = "Install the gamemode package to control gamemoded."
    elif active:
        note = "gamemoded is active for this session."
        if visuals_suppressed:
            note = "gamemoded is active and compositor effects are temporarily disabled."
        if source == LUTRIS_AUTO_SOURCE:
            note = "gamemoded is active automatically because a Lutris game is running."
    else:
        note = "gamemoded is installed but currently inactive."
    return {
        "available": available,
        "active": active,
        "enabled": service_enabled(),
        "visuals_suppressed": visuals_suppressed,
        "activation_source": source,
        "note": note,
    }


def set_active(enabled: bool, source: str = MANUAL_SOURCE) -> tuple[bool, str]:
    if not gamemoded_available():
        message = "gamemoded is not installed. Install gamemode first."
        _persist_runtime(False, message)
        return False, message

    if not systemctl_available():
        message = "systemctl --user is unavailable, so Hanauta cannot manage gamemoded yet."
        _persist_runtime(False, message)
        return False, message

    runtime_state = _load_runtime_state()
    current_source = str(runtime_state.get("activation_source", MANUAL_SOURCE)).strip() or MANUAL_SOURCE
    if not enabled and source != MANUAL_SOURCE and current_source != source:
        message = "Game Mode is active from another source, so the automatic Lutris watcher left it alone."
        _persist_runtime(is_active(), message)
        return True, message

    action = "start" if enabled else "stop"
    code, output = _run_text(["systemctl", "--user", action, SERVICE_NAME], timeout=6.0)
    if code != 0:
        message = output or f"Failed to {action} {SERVICE_NAME}."
        _persist_runtime(is_active(), message)
        return False, message

    active = is_active()
    runtime_state = _load_runtime_state()
    if source == MANUAL_SOURCE:
        runtime_state["manual_override_disable"] = False
        if not enabled and bool(runtime_state.get("lutris_game_active", False)):
            runtime_state["manual_override_disable"] = True
        _write_runtime_state(runtime_state)
    if enabled and active:
        _apply_game_mode_visuals()
        _mark_runtime_flag("activation_source", source)
        if source == LUTRIS_AUTO_SOURCE:
            message = "Game Mode enabled automatically for a running Lutris game."
        else:
            message = "Game Mode enabled. Transparency and compositor effects are disabled."
    else:
        _restore_game_mode_visuals()
        _mark_runtime_flag("activation_source", MANUAL_SOURCE)
        if source == LUTRIS_AUTO_SOURCE:
            message = "Game Mode disabled automatically after the Lutris session ended."
        else:
            message = "Game Mode disabled. Transparency and compositor effects were restored."
    _persist_runtime(active, message)
    return True, message


def toggle_active() -> tuple[bool, str]:
    return set_active(not is_active())
