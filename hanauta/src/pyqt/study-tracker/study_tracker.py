#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import uuid
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

_chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
_quiet_flags = [
    "--disable-logging",
    "--log-level=3",
]
for _flag in _quiet_flags:
    if _flag not in _chromium_flags:
        _chromium_flags = f"{_chromium_flags} {_flag}".strip()
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _chromium_flags
_logging_rules = os.environ.get("QT_LOGGING_RULES", "").strip()
if "qt.qpa.gl=false" not in _logging_rules:
    _logging_rules = f"{_logging_rules};qt.qpa.gl=false".strip(";")
if "qt.rhi.*=false" not in _logging_rules:
    _logging_rules = f"{_logging_rules};qt.rhi.*=false".strip(";")
os.environ["QT_LOGGING_RULES"] = _logging_rules

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

try:
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
    WEBENGINE_ERROR = ""
except Exception as exc:
    QWebChannel = Any  # type: ignore[assignment]
    QWebEngineSettings = Any  # type: ignore[assignment]
    QWebEngineView = Any  # type: ignore[assignment]
    WEBENGINE_AVAILABLE = False
    WEBENGINE_ERROR = str(exc)


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
HTML_FILE = HERE / "code.html"
SETTINGS_HTML_FILE = HERE / "settingspage.html"
SCHEDULES_HTML_FILE = HERE / "schedules.html"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "study-tracker"
STATE_FILE = STATE_DIR / "state.json"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command, python_executable
from pyqt.shared.theme import ThemePalette, blend, load_theme_palette, palette_mtime, rgba

try:
    import requests
except Exception:
    requests = None  # type: ignore[assignment]


HANAUTA_DARK_PALETTE = {
    "source": "#D0BCFF",
    "primary": "#D0BCFF",
    "on_primary": "#381E72",
    "primary_container": "#4F378B",
    "on_primary_container": "#EADDFF",
    "secondary": "#CCC2DC",
    "on_secondary": "#332D41",
    "tertiary": "#EFB8C8",
    "on_tertiary": "#492532",
    "background": "#141218",
    "on_background": "#E6E0E9",
    "surface": "#141218",
    "on_surface": "#E6E0E9",
    "surface_container": "#211F26",
    "surface_container_high": "#2B2930",
    "surface_variant": "#49454F",
    "on_surface_variant": "#CAC4D0",
    "outline": "#938F99",
    "error": "#F2B8B5",
    "on_error": "#601410",
}

HANAUTA_LIGHT_PALETTE = {
    "source": "#8E4BC3",
    "primary": "#7A3EA8",
    "on_primary": "#FFFFFF",
    "primary_container": "#F2DAFF",
    "on_primary_container": "#300047",
    "secondary": "#745A77",
    "on_secondary": "#FFFFFF",
    "tertiary": "#9D3F73",
    "on_tertiary": "#FFFFFF",
    "background": "#FFF7FB",
    "on_background": "#221925",
    "surface": "#FFF7FB",
    "on_surface": "#221925",
    "surface_container": "#F8EDF5",
    "surface_container_high": "#F2E2EC",
    "surface_variant": "#E7D8E4",
    "on_surface_variant": "#655865",
    "outline": "#968797",
    "error": "#BA1A1A",
    "on_error": "#FFFFFF",
}

RETROWAVE_PALETTE = {
    "source": "#FC29A8",
    "primary": "#FC29A8",
    "on_primary": "#25031A",
    "primary_container": "#5C1650",
    "on_primary_container": "#FFD4EF",
    "secondary": "#03EDF9",
    "on_secondary": "#001F23",
    "tertiary": "#FFF951",
    "on_tertiary": "#292500",
    "background": "#1A1326",
    "on_background": "#F4EBFF",
    "surface": "#221A30",
    "on_surface": "#F4EBFF",
    "surface_container": "#2A2139",
    "surface_container_high": "#372D4B",
    "surface_variant": "#4B4061",
    "on_surface_variant": "#D3C6E8",
    "outline": "#8C7AA7",
    "error": "#FE4450",
    "on_error": "#FFFFFF",
}

DRACULA_PALETTE = {
    "source": "#BD93F9",
    "primary": "#BD93F9",
    "on_primary": "#221534",
    "primary_container": "#4C3E6E",
    "on_primary_container": "#F1E5FF",
    "secondary": "#8BE9FD",
    "on_secondary": "#032730",
    "tertiary": "#FF79C6",
    "on_tertiary": "#3B0F2B",
    "background": "#282A36",
    "on_background": "#F8F8F2",
    "surface": "#282A36",
    "on_surface": "#F8F8F2",
    "surface_container": "#2E3140",
    "surface_container_high": "#343746",
    "surface_variant": "#44475A",
    "on_surface_variant": "#CAD0F8",
    "outline": "#6272A4",
    "error": "#FF5555",
    "on_error": "#FFFFFF",
}

HANAUTA_FONT_PROFILE = {
    "ui_font_family": "Rubik",
    "display_font_family": "Rubik",
    "mono_font_family": "JetBrains Mono",
    "serif_font_family": "Playfair Display",
}


DEFAULT_INSIGHTS: list[dict[str, str]] = [
    {
        "icon": "smart_toy",
        "accent": "primary",
        "title": "AI Enhanced Learning",
        "body": "Use Gemini or NotebookLM to condense dense material into summaries, drills, and quiz prompts before your first focus block.",
    },
    {
        "icon": "timer",
        "accent": "secondary",
        "title": "Time Management",
        "body": "Keep sessions short and intentional. A clean 25-minute block usually beats a vague hour of distracted studying.",
    },
    {
        "icon": "psychology",
        "accent": "tertiary",
        "title": "Cognitive Science",
        "body": "Practice active recall after each session. Closing the notes and explaining the idea back to yourself boosts retention fast.",
    },
    {
        "icon": "repeat",
        "accent": "primary",
        "title": "Retention Habits",
        "body": "Revisit yesterday's material before starting new content. Spaced repetition works best when it feels routine, not heroic.",
    },
]


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def python_bin() -> str:
    return python_executable()


def notify(title: str, body: str) -> None:
    try:
        subprocess.Popen(
            ["notify-send", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def make_task(title: str, estimate_minutes: int, *, active: bool = False) -> dict[str, Any]:
    estimate = max(10, int(estimate_minutes))
    target_sessions = max(1, math.ceil(estimate / 25))
    return {
        "id": str(uuid.uuid4()),
        "title": title.strip() or "Study task",
        "estimate_minutes": estimate,
        "target_sessions": target_sessions,
        "sessions_completed": 0,
        "done": False,
        "active": active,
        "completed_at": "",
        "created_at": now_iso(),
    }


def default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "today_minutes": 0,
        "last_reset_date": today_iso(),
        "activity_dates": [],
        "insights": list(DEFAULT_INSIGHTS),
        "session_length_minutes": 25,
        "tasks": [
            {
                **make_task("Review N2 Vocabulary Flashcards", 25),
                "done": True,
                "active": False,
                "sessions_completed": 1,
                "completed_at": "08:30 AM",
            },
            {
                **make_task("Japanese Podcast: NHK News Easy", 60, active=True),
                "sessions_completed": 1,
            },
            make_task("Shadowing Practice: Genki Chapter 12", 15),
        ],
        "active_session": None,
        "preferences": {
            "anki_enabled": True,
            "pomodoro_bridge_enabled": True,
            "theme_mode": "system",
            "custom_theme_id": "retrowave",
            "sync": {
                "provider": "none",
                "remote_path": "study-tracker/state.json",
                "url": "",
                "username": "",
                "password": "",
                "postgres_dsn": "",
                "postgres_table": "hanauta_study_tracker",
                "auto_sync": False,
                "last_status": "Local only. No remote sync target configured yet.",
                "last_sync_at": "",
            },
        },
    }


def normalize_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    state = default_state()
    if isinstance(payload, dict):
        state.update(payload)
    tasks = state.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    normalized_tasks: list[dict[str, Any]] = []
    for raw_task in tasks:
        if not isinstance(raw_task, dict):
            continue
        base = make_task(str(raw_task.get("title", "Study task")), int(raw_task.get("estimate_minutes", 25) or 25))
        base.update(raw_task)
        base["done"] = bool(base.get("done", False))
        base["active"] = bool(base.get("active", False))
        base["sessions_completed"] = max(0, int(base.get("sessions_completed", 0) or 0))
        base["target_sessions"] = max(1, int(base.get("target_sessions", 1) or 1))
        normalized_tasks.append(base)
    if not normalized_tasks:
        normalized_tasks = default_state()["tasks"]
    state["tasks"] = normalized_tasks
    active_session = state.get("active_session")
    if not isinstance(active_session, dict):
        state["active_session"] = None
    else:
        state["active_session"] = {
            "task_id": str(active_session.get("task_id", "")),
            "elapsed_seconds": max(0, int(active_session.get("elapsed_seconds", 0) or 0)),
            "target_seconds": max(60, int(active_session.get("target_seconds", 25 * 60) or 25 * 60)),
            "running": bool(active_session.get("running", False)),
            "started_at": str(active_session.get("started_at", now_iso())),
        }
    insights = state.get("insights", [])
    if not isinstance(insights, list) or not insights:
        state["insights"] = list(DEFAULT_INSIGHTS)
    state["today_minutes"] = max(0, int(state.get("today_minutes", 0) or 0))
    preferences = state.get("preferences", {})
    if not isinstance(preferences, dict):
        preferences = {}
    default_preferences = default_state()["preferences"]
    merged_preferences = deepcopy(default_preferences)
    merged_preferences.update(preferences)
    sync = merged_preferences.get("sync", {})
    if not isinstance(sync, dict):
        sync = {}
    merged_sync = dict(default_preferences["sync"])
    merged_sync.update(sync)
    merged_sync["provider"] = str(merged_sync.get("provider", "none") or "none").strip().lower()
    if merged_sync["provider"] not in {"none", "nextcloud", "webdav", "postgres"}:
        merged_sync["provider"] = "none"
    merged_sync["remote_path"] = str(merged_sync.get("remote_path", "study-tracker/state.json") or "study-tracker/state.json").strip() or "study-tracker/state.json"
    merged_sync["url"] = str(merged_sync.get("url", "") or "").strip()
    merged_sync["username"] = str(merged_sync.get("username", "") or "").strip()
    merged_sync["password"] = str(merged_sync.get("password", "") or "")
    merged_sync["postgres_dsn"] = str(merged_sync.get("postgres_dsn", "") or "").strip()
    merged_sync["postgres_table"] = str(merged_sync.get("postgres_table", "hanauta_study_tracker") or "hanauta_study_tracker").strip() or "hanauta_study_tracker"
    merged_sync["auto_sync"] = bool(merged_sync.get("auto_sync", False))
    merged_sync["last_status"] = str(merged_sync.get("last_status", "") or "")
    merged_sync["last_sync_at"] = str(merged_sync.get("last_sync_at", "") or "")
    merged_preferences["sync"] = merged_sync
    merged_preferences["anki_enabled"] = bool(merged_preferences.get("anki_enabled", True))
    merged_preferences["pomodoro_bridge_enabled"] = bool(merged_preferences.get("pomodoro_bridge_enabled", True))
    theme_mode = str(merged_preferences.get("theme_mode", "system") or "system").strip().lower()
    if theme_mode not in {"system", "dark", "light", "custom"}:
        theme_mode = "system"
    merged_preferences["theme_mode"] = theme_mode
    custom_theme_id = str(merged_preferences.get("custom_theme_id", "retrowave") or "retrowave").strip().lower()
    merged_preferences["custom_theme_id"] = custom_theme_id if custom_theme_id in {"retrowave", "dracula"} else "retrowave"
    state["preferences"] = merged_preferences
    last_reset = str(state.get("last_reset_date", today_iso()) or today_iso())
    state["last_reset_date"] = last_reset
    activity_dates = state.get("activity_dates", [])
    if not isinstance(activity_dates, list):
        activity_dates = []
    state["activity_dates"] = sorted({str(item) for item in activity_dates if str(item).strip()})
    _normalize_daily_rollover(state)
    _ensure_single_active_task(state)
    return state


def load_state() -> dict[str, Any]:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = default_state()
    return normalize_state(payload)


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_hanauta_settings() -> dict[str, Any]:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_theme_from_palette(palette: dict[str, str]) -> ThemePalette:
    payload = dict(HANAUTA_FONT_PROFILE)
    payload.update(palette)
    payload["use_matugen"] = False
    return ThemePalette(**payload)


def resolve_study_theme(state: dict[str, Any]) -> ThemePalette:
    preferences = state.get("preferences", {})
    if not isinstance(preferences, dict):
        return load_theme_palette()
    theme_mode = str(preferences.get("theme_mode", "system") or "system").strip().lower()
    if theme_mode == "dark":
        return build_theme_from_palette(HANAUTA_DARK_PALETTE)
    if theme_mode == "light":
        return build_theme_from_palette(HANAUTA_LIGHT_PALETTE)
    if theme_mode == "custom":
        custom_theme_id = str(preferences.get("custom_theme_id", "retrowave") or "retrowave").strip().lower()
        return build_theme_from_palette(DRACULA_PALETTE if custom_theme_id == "dracula" else RETROWAVE_PALETTE)
    return load_theme_palette()


def build_sync_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "today_minutes": int(state.get("today_minutes", 0) or 0),
        "last_reset_date": str(state.get("last_reset_date", today_iso()) or today_iso()),
        "activity_dates": list(state.get("activity_dates", [])),
        "insights": list(state.get("insights", [])),
        "session_length_minutes": int(state.get("session_length_minutes", 25) or 25),
        "tasks": deepcopy(state.get("tasks", [])),
        "active_session": deepcopy(state.get("active_session")),
        "preferences": {
            "anki_enabled": bool(state.get("preferences", {}).get("anki_enabled", True)) if isinstance(state.get("preferences"), dict) else True,
            "pomodoro_bridge_enabled": bool(state.get("preferences", {}).get("pomodoro_bridge_enabled", True)) if isinstance(state.get("preferences"), dict) else True,
            "theme_mode": str(state.get("preferences", {}).get("theme_mode", "system")) if isinstance(state.get("preferences"), dict) else "system",
            "custom_theme_id": str(state.get("preferences", {}).get("custom_theme_id", "retrowave")) if isinstance(state.get("preferences"), dict) else "retrowave",
        },
    }


def merge_remote_sync_payload(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return state
    merged = deepcopy(state)
    for key in ("today_minutes", "last_reset_date", "activity_dates", "insights", "session_length_minutes", "tasks", "active_session"):
        if key in payload:
            merged[key] = payload[key]
    remote_preferences = payload.get("preferences", {})
    if isinstance(remote_preferences, dict):
        local_preferences = merged.get("preferences", {})
        if not isinstance(local_preferences, dict):
            local_preferences = {}
        for key in ("anki_enabled", "pomodoro_bridge_enabled", "theme_mode", "custom_theme_id"):
            if key in remote_preferences:
                local_preferences[key] = remote_preferences[key]
        merged["preferences"] = local_preferences
    return normalize_state(merged)


def _normalize_daily_rollover(state: dict[str, Any]) -> None:
    current = today_iso()
    if str(state.get("last_reset_date", "")) != current:
        state["today_minutes"] = 0
        state["last_reset_date"] = current


def _ensure_single_active_task(state: dict[str, Any]) -> None:
    active_seen = False
    for task in state.get("tasks", []):
        if task.get("done"):
            task["active"] = False
            continue
        if task.get("active") and not active_seen:
            active_seen = True
        else:
            task["active"] = False
    if active_seen:
        return
    for task in state.get("tasks", []):
        if not task.get("done"):
            task["active"] = True
            return


def compute_streak_days(state: dict[str, Any]) -> int:
    values = sorted({str(item) for item in state.get("activity_dates", []) if str(item).strip()}, reverse=True)
    if not values:
        return 0
    streak = 0
    cursor = date.today()
    value_set = set(values)
    while cursor.isoformat() in value_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def active_task(state: dict[str, Any]) -> dict[str, Any] | None:
    tasks = state.get("tasks", [])
    if not isinstance(tasks, list):
        return None
    for task in tasks:
        if isinstance(task, dict) and task.get("active") and not task.get("done"):
            return task
    for task in tasks:
        if isinstance(task, dict) and not task.get("done"):
            return task
    return None


def task_by_id(state: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for task in state.get("tasks", []):
        if isinstance(task, dict) and str(task.get("id", "")) == task_id:
            return task
    return None


def build_summary_payload(state: dict[str, Any]) -> dict[str, Any]:
    current_task = active_task(state)
    session = state.get("active_session")
    session_payload: dict[str, Any] | None = None
    if isinstance(session, dict):
        session_payload = {
            "task_id": str(session.get("task_id", "")),
            "elapsed_seconds": max(0, int(session.get("elapsed_seconds", 0) or 0)),
            "target_seconds": max(60, int(session.get("target_seconds", 25 * 60) or 25 * 60)),
            "running": bool(session.get("running", False)),
        }
    return {
        "streak_days": compute_streak_days(state),
        "today_minutes": max(0, int(state.get("today_minutes", 0) or 0)),
        "agenda_date": datetime.now().strftime("%A, %b %d"),
        "session_length_minutes": max(1, int(state.get("session_length_minutes", 25) or 25)),
        "insights": state.get("insights", []),
        "tasks": state.get("tasks", []),
        "current_task": current_task,
        "active_session": session_payload,
    }


def build_settings_payload(state: dict[str, Any]) -> dict[str, Any]:
    preferences = state.get("preferences", {})
    if not isinstance(preferences, dict):
        preferences = {}
    sync = preferences.get("sync", {})
    if not isinstance(sync, dict):
        sync = {}
    theme_mode = str(preferences.get("theme_mode", "system") or "system").strip().lower()
    custom_theme_id = str(preferences.get("custom_theme_id", "retrowave") or "retrowave").strip().lower()
    sync_provider = str(sync.get("provider", "none") or "none").strip().lower()
    sync_summary = {
        "none": "Local only",
        "nextcloud": "Nextcloud sync",
        "webdav": "WebDAV sync",
        "postgres": "PostgreSQL sync",
    }.get(sync_provider, "Local only")
    theme_summary = {
        "system": "System theme",
        "dark": "Dark theme",
        "light": "Light theme",
        "custom": f"Custom: {'Dracula' if custom_theme_id == 'dracula' else 'Retrowave'}",
    }.get(theme_mode, "System theme")
    return {
        "anki_enabled": bool(preferences.get("anki_enabled", True)),
        "pomodoro_bridge_enabled": bool(preferences.get("pomodoro_bridge_enabled", True)),
        "theme_mode": theme_mode,
        "custom_theme_id": custom_theme_id if custom_theme_id in {"retrowave", "dracula"} else "retrowave",
        "sync": {
            "provider": sync_provider if sync_provider in {"none", "nextcloud", "webdav", "postgres"} else "none",
            "remote_path": str(sync.get("remote_path", "study-tracker/state.json") or "study-tracker/state.json"),
            "url": str(sync.get("url", "") or ""),
            "username": str(sync.get("username", "") or ""),
            "password": str(sync.get("password", "") or ""),
            "postgres_dsn": str(sync.get("postgres_dsn", "") or ""),
            "postgres_table": str(sync.get("postgres_table", "hanauta_study_tracker") or "hanauta_study_tracker"),
            "auto_sync": bool(sync.get("auto_sync", False)),
            "last_status": str(sync.get("last_status", "Local only. No remote sync target configured yet.") or "Local only. No remote sync target configured yet."),
            "last_sync_at": str(sync.get("last_sync_at", "") or ""),
        },
        "theme_summary": theme_summary,
        "sync_summary": sync_summary,
    }


def theme_payload(theme: ThemePalette) -> dict[str, str]:
    surface_low = blend(theme.surface, theme.surface_container, 0.42)
    surface_lowest = blend(theme.surface, theme.surface_container, 0.18)
    surface_highest = blend(theme.surface_container_high, theme.surface_variant, 0.18)
    return {
        "primary": theme.primary,
        "onPrimary": theme.on_primary,
        "secondary": theme.secondary,
        "tertiary": theme.tertiary,
        "background": theme.background,
        "surface": theme.surface,
        "surfaceLow": surface_low,
        "surfaceLowest": surface_lowest,
        "surfaceHigh": theme.surface_container_high,
        "surfaceHighest": surface_highest,
        "outline": rgba(theme.outline, 0.68),
        "outlineSoft": rgba(theme.outline, 0.18),
        "text": theme.on_surface,
        "textMuted": rgba(theme.on_surface_variant, 0.74),
        "textSoft": rgba(theme.on_surface_variant, 0.44),
        "ambientPrimary": rgba(theme.primary, 0.09),
        "ambientSecondary": rgba(theme.secondary, 0.08),
        "railShadow": rgba(theme.primary, 0.08),
    }


def build_runtime_script(page_name: str) -> str:
    return f"""
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
(function () {{
  const CURRENT_PAGE = {json.dumps(page_name)};
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  let studyState = null;
  let settingsState = null;
  let insightIndex = 0;
  let bridge = null;

  function setNavActive(page) {{
    const dashboard = $("navDashboardButton");
    const schedule = $("navScheduleButton");
    const settings = $("navSettingsButton");
    [dashboard, schedule, settings].forEach((button) => {{
      if (!button) return;
      button.classList.remove("is-active");
    }});
    const active = page === "settings" ? settings : page === "schedule" ? schedule : dashboard;
    if (active) {{
      active.classList.add("is-active");
    }}
  }}

  function formatMinutes(minutes) {{
    const total = Math.max(0, Number(minutes || 0));
    if (total < 60) return `${{total}}m Today`;
    const hours = Math.floor(total / 60);
    const rem = total % 60;
    return rem ? `${{hours}}h ${{rem}}m Today` : `${{hours}}h Today`;
  }}

  function formatSessionRemaining(session) {{
    if (!session) return "";
    const remain = Math.max(0, Number(session.target_seconds || 0) - Number(session.elapsed_seconds || 0));
    const minutes = Math.floor(remain / 60);
    const seconds = remain % 60;
    return `${{minutes}}m ${{String(seconds).padStart(2, "0")}}s left`;
  }}

  function currentTask() {{
    return studyState?.current_task || null;
  }}

  function setToggleButton(id, enabled, labels = ["Enabled", "Disabled"]) {{
    const node = $(id);
    if (!node) return;
    node.textContent = enabled ? labels[0] : labels[1];
    node.classList.toggle("off", !enabled);
  }}

  function setPillState(id, active) {{
    const node = $(id);
    if (!node) return;
    node.classList.toggle("active", !!active);
  }}

  function renderObjective() {{
    const task = currentTask();
    const session = studyState?.active_session || null;
    const headline = $("objectiveHeadline");
    const progressText = $("objectiveProgressText");
    const progressBar = $("objectiveProgressBar");
    if (!headline || !progressText || !progressBar) return;

    if (!task) {{
      headline.innerHTML = `Choose your next <br><span class="text-primary" id="objectiveSubject">study target</span>`;
      progressText.textContent = "0 / 0";
      progressBar.style.width = "0%";
      return;
    }}

    const completed = Math.max(0, Number(task.sessions_completed || 0));
    const target = Math.max(1, Number(task.target_sessions || 1));
    const remaining = Math.max(0, target - completed);
    const actionText = remaining > 0 ? `Finish ${{remaining}} Pomodoro${{remaining === 1 ? "" : "s"}} of` : "Keep momentum with";
    headline.innerHTML = `${{escapeHtml(actionText)}} <br><span class="text-primary" id="objectiveSubject">${{escapeHtml(task.title)}}</span>`;
    progressText.textContent = `${{completed}} / ${{target}}`;
    progressBar.style.width = `${{Math.max(6, (completed / target) * 100)}}%`;
    if (completed <= 0) progressBar.style.width = "8%";
    if (task.done) progressBar.style.width = "100%";
    if (session && String(session.task_id || "") === String(task.id || "")) {{
      progressText.textContent = `${{completed}} / ${{target}} • ${{formatSessionRemaining(session)}}`;
    }}
  }}

  function insightCard(item) {{
    const accent = item.accent || "primary";
    return `
      <div class="min-w-[280px] flex-shrink-0 snap-center glass-panel bg-[#0c0d18]/60 p-5 rounded-2xl border border-primary/10 hover:border-primary/30 transition-all group">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-8 h-8 rounded-lg bg-${{accent}}/10 flex items-center justify-center text-${{accent}} group-hover:scale-110 transition-transform">
            <span class="material-symbols-outlined text-lg">${{escapeHtml(item.icon || "lightbulb")}}</span>
          </div>
          <span class="text-xs font-bold font-headline text-${{accent}}/80">${{escapeHtml(item.title || "Study Insight")}}</span>
        </div>
        <p class="text-sm leading-relaxed text-on-surface/80 font-body">${{escapeHtml(item.body || "")}}</p>
      </div>
    `;
  }}

  function renderInsights() {{
    const track = $("insightsTrack");
    const dots = $("insightDots");
    if (!track || !dots) return;
    const insights = Array.isArray(studyState?.insights) ? studyState.insights : [];
    if (!insights.length) {{
      track.innerHTML = "";
      dots.innerHTML = "";
      return;
    }}
    insightIndex = Math.max(0, Math.min(insightIndex, insights.length - 1));
    track.innerHTML = insights.map(insightCard).join("");
    dots.innerHTML = insights.map((_, index) => {{
      const active = index === insightIndex;
      return `<div class="w-1.5 h-1.5 rounded-full ${{active ? "bg-primary shadow-[0_0_8px_rgba(212,187,255,0.6)]" : "bg-surface-container-highest"}}"></div>`;
    }}).join("");
    const card = track.children[insightIndex];
    if (card) card.scrollIntoView({{behavior: "smooth", inline: "center", block: "nearest"}});
  }}

  function taskRow(task) {{
    const done = Boolean(task.done);
    const active = Boolean(task.active) && !done;
    const completed = Math.max(0, Number(task.sessions_completed || 0));
    const target = Math.max(1, Number(task.target_sessions || 1));
    const statusText = done
      ? `Completed ${{escapeHtml(task.completed_at || "today")}}`
      : active
        ? `In Progress • ${{completed}}/${{target}} sessions complete`
        : `Estimated: ${{escapeHtml(task.estimate_minutes || 25)}} mins • ${{completed}}/${{target}} sessions`;
    const icon = done ? `<span class="material-symbols-outlined text-xs text-on-primary" style="font-variation-settings: 'FILL' 1;">check</span>` : "";
    const badgeClass = done ? "border-primary bg-primary/20" : active ? "border-primary" : "border-outline-variant";
    const rowClass = done
      ? "p-4 rounded-lg bg-surface-container-low/30 hover:bg-surface-container-low/50 group"
      : active
        ? "p-6 rounded-lg bg-surface-container-high shadow-lg border-l-4 border-primary"
        : "p-4 rounded-lg bg-surface-container-low/30 hover:bg-surface-container-low/50 group";
    const titleClass = done
      ? "text-on-surface/50 line-through font-medium"
      : active
        ? "text-on-surface font-semibold text-lg"
        : "text-on-surface-variant font-medium group-hover:text-on-surface transition-colors";
    const detailClass = done
      ? "text-xs font-label text-on-surface-variant opacity-40"
      : active
        ? "text-xs font-label text-primary font-bold"
        : "text-xs font-label text-on-surface-variant/60";
    const controls = done ? `
      <button class="text-xs px-3 py-2 rounded-full bg-surface-container-high text-on-surface-variant" data-action="reactivate" data-task-id="${{escapeHtml(task.id)}}">Reopen</button>
    ` : `
      <button class="text-xs px-3 py-2 rounded-full bg-surface-container-high text-primary" data-action="focus" data-task-id="${{escapeHtml(task.id)}}">${{active ? "Focused" : "Focus"}}</button>
      <button class="text-xs px-3 py-2 rounded-full bg-primary/15 text-primary" data-action="toggle" data-task-id="${{escapeHtml(task.id)}}">${{completed >= target ? "Finish" : "Mark Done"}}</button>
    `;
    return `
      <div class="flex items-center gap-6 ${{rowClass}}" data-task-row="${{escapeHtml(task.id)}}">
        <button class="w-6 h-6 rounded-full border-2 ${{badgeClass}} flex items-center justify-center shrink-0" data-action="${{done ? "reactivate" : "toggle"}}" data-task-id="${{escapeHtml(task.id)}}">${{icon}}</button>
        <div class="flex-1 min-w-0">
          <p class="${{titleClass}}">${{escapeHtml(task.title)}}</p>
          <span class="${{detailClass}}">${{statusText}}</span>
        </div>
        <div class="flex items-center gap-2">${{controls}}</div>
      </div>
    `;
  }}

  function renderAgenda() {{
    const dateNode = $("agendaDate");
    const listNode = $("agendaList");
    if (dateNode) dateNode.textContent = studyState?.agenda_date || "";
    if (!listNode) return;
    const tasks = Array.isArray(studyState?.tasks) ? studyState.tasks : [];
    listNode.innerHTML = tasks.map(taskRow).join("");
    listNode.querySelectorAll("[data-action]").forEach((node) => {{
      node.addEventListener("click", (event) => {{
        event.preventDefault();
        event.stopPropagation();
        if (!bridge) return;
        const taskId = node.getAttribute("data-task-id") || "";
        const action = node.getAttribute("data-action") || "";
        if (action === "toggle") bridge.toggleTask(taskId);
        if (action === "focus") bridge.focusTask(taskId);
        if (action === "reactivate") bridge.reopenTask(taskId);
      }});
    }});
  }}

  function renderChips() {{
    if ($("streakChipText")) $("streakChipText").textContent = `${{studyState?.streak_days || 0}} Day Streak`;
    if ($("todayChipText")) $("todayChipText").textContent = formatMinutes(studyState?.today_minutes || 0);
  }}

  function renderFab() {{
    const label = $("studyFabLabel");
    const hint = $("studyFabHint");
    const icon = $("studyFabIcon");
    const session = studyState?.active_session || null;
    const task = currentTask();
    if (!label || !hint || !icon) return;
    if (session && session.running) {{
      label.textContent = "Pause Session";
      hint.textContent = formatSessionRemaining(session);
      icon.textContent = "pause";
    }} else if (session) {{
      label.textContent = "Resume Session";
      hint.textContent = "Your focus block is waiting";
      icon.textContent = "play_arrow";
    }} else if (task) {{
      label.textContent = "Start Study Session";
      hint.textContent = `Focused on ${{task.title}}`;
      icon.textContent = "play_arrow";
    }} else {{
      label.textContent = "Add a Study Task";
      hint.textContent = "Build a small plan first";
      icon.textContent = "add";
    }}
  }}

  function renderSettings() {{
    if (!settingsState) return;
    if ($("settingsThemeSummary")) $("settingsThemeSummary").textContent = settingsState.theme_summary || "System theme";
    if ($("settingsSyncSummary")) $("settingsSyncSummary").textContent = settingsState.sync_summary || "Local only";
    if ($("settingsFooterStatus")) $("settingsFooterStatus").textContent = settingsState.sync?.last_sync_at ? `Last sync ${{settingsState.sync.last_sync_at}}` : "Encrypted local state";
    setToggleButton("ankiToggleButton", !!settingsState.anki_enabled);
    setToggleButton("pomodoroToggleButton", !!settingsState.pomodoro_bridge_enabled);
    setToggleButton("syncAutoButton", !!settingsState.sync?.auto_sync, ["Enabled", "Disabled"]);
    setPillState("themeSystemButton", settingsState.theme_mode === "system");
    setPillState("themeDarkButton", settingsState.theme_mode === "dark");
    setPillState("themeLightButton", settingsState.theme_mode === "light");
    setPillState("themeCustomButton", settingsState.theme_mode === "custom");
    setPillState("customThemeRetrowaveButton", settingsState.custom_theme_id === "retrowave");
    setPillState("customThemeDraculaButton", settingsState.custom_theme_id === "dracula");
    if ($("syncProviderSelect")) $("syncProviderSelect").value = settingsState.sync?.provider || "none";
    if ($("syncRemotePathInput")) $("syncRemotePathInput").value = settingsState.sync?.remote_path || "";
    if ($("syncUrlInput")) $("syncUrlInput").value = settingsState.sync?.url || "";
    if ($("syncUsernameInput")) $("syncUsernameInput").value = settingsState.sync?.username || "";
    if ($("syncPasswordInput")) $("syncPasswordInput").value = settingsState.sync?.password || "";
    if ($("syncPostgresDsnInput")) $("syncPostgresDsnInput").value = settingsState.sync?.postgres_dsn || "";
    if ($("syncPostgresTableInput")) $("syncPostgresTableInput").value = settingsState.sync?.postgres_table || "";
    if ($("syncStatusText")) $("syncStatusText").textContent = settingsState.sync?.last_status || "Local only. No remote sync target configured yet.";
    const provider = settingsState.sync?.provider || "none";
    const showWebdav = provider === "nextcloud" || provider === "webdav";
    const showPostgres = provider === "postgres";
    ["syncUrlField", "syncUsernameField", "syncPasswordField"].forEach((id) => {{
      const node = $(id);
      if (node) node.style.display = showWebdav ? "" : "none";
    }});
    ["syncDsnField"].forEach((id) => {{
      const node = $(id);
      if (node) node.style.display = showPostgres ? "" : "none";
    }});
    if ($("themeModeExplanation")) {{
      $("themeModeExplanation").textContent = settingsState.theme_mode === "system"
        ? "System follows your current desktop palette. If Matugen is active, the tracker follows it too."
        : settingsState.theme_mode === "custom"
          ? "Custom uses a dedicated study tracker palette without changing your desktop theme."
          : "This overrides the study tracker theme without changing the rest of the desktop.";
    }}
    if ($("customThemeSection")) $("customThemeSection").style.display = settingsState.theme_mode === "custom" ? "" : "none";
  }}

  function setSchedulePanelVisible(visible) {{
    const selectionPanel = $("scheduleSelectionPanel");
    const emptyState = $("scheduleEmptyState");
    if (selectionPanel) selectionPanel.classList.toggle("hidden", !visible);
    if (emptyState) emptyState.classList.toggle("hidden", !!visible);
  }}

  function selectScheduleBlock(block) {{
    if (!block) {{
      document.querySelectorAll(".study-schedule-block").forEach((node) => node.classList.remove("is-selected"));
      setSchedulePanelVisible(false);
      return;
    }}
    const tone = (block.dataset.scheduleTone || "primary").toLowerCase();
    document.querySelectorAll(".study-schedule-block").forEach((node) => node.classList.toggle("is-selected", node === block));
    if ($("scheduleSelectedTitle")) $("scheduleSelectedTitle").textContent = block.dataset.scheduleTitle || "Study Block";
    if ($("scheduleSelectedWhen")) $("scheduleSelectedWhen").textContent = block.dataset.scheduleWhen || "";
    if ($("scheduleSelectedCategory")) {{
      $("scheduleSelectedCategory").textContent = (block.dataset.scheduleCategory || "").toUpperCase();
      $("scheduleSelectedCategory").className = `text-[10px] font-label font-bold text-${{tone}}`;
    }}
    if ($("scheduleSelectedDescription")) $("scheduleSelectedDescription").textContent = block.dataset.scheduleDescription || "";
    if ($("scheduleSelectedBadge")) {{
      $("scheduleSelectedBadge").className = `px-3 py-1 bg-${{tone}}/20 text-${{tone}} text-[9px] font-black uppercase tracking-widest rounded-full`;
      $("scheduleSelectedBadge").textContent = "Selected Block";
    }}
    setSchedulePanelVisible(true);
  }}

  function wireScheduleActions() {{
    document.querySelectorAll(".study-schedule-block").forEach((block) => {{
      block.addEventListener("click", () => selectScheduleBlock(block));
    }});
    $("scheduleSelectionCloseButton")?.addEventListener("click", () => selectScheduleBlock(null));
    setSchedulePanelVisible(false);
  }}

  function render() {{
    if (studyState) {{
      renderChips();
    }}
    if (CURRENT_PAGE === "dashboard" && studyState) {{
      renderObjective();
      renderInsights();
      renderAgenda();
      renderFab();
    }}
    if (CURRENT_PAGE === "settings" && settingsState) {{
      renderSettings();
    }}
  }}

  function collectSyncSettings() {{
    return {{
      provider: $("syncProviderSelect")?.value || "none",
      remote_path: $("syncRemotePathInput")?.value || "",
      url: $("syncUrlInput")?.value || "",
      username: $("syncUsernameInput")?.value || "",
      password: $("syncPasswordInput")?.value || "",
      postgres_dsn: $("syncPostgresDsnInput")?.value || "",
      postgres_table: $("syncPostgresTableInput")?.value || "",
      auto_sync: !($("syncAutoButton")?.classList.contains("off")),
    }};
  }}

  function wireNavigation() {{
    $("navDashboardButton")?.addEventListener("click", () => bridge?.navigateTo("dashboard"));
    $("navScheduleButton")?.addEventListener("click", () => bridge?.navigateTo("schedule"));
    $("navSettingsButton")?.addEventListener("click", () => bridge?.navigateTo("settings"));
  }}

  function wireDashboardActions() {{
    $("studyFabButton")?.addEventListener("click", () => bridge?.startOrPauseSession());
    $("addTaskButton")?.addEventListener("click", () => {{
      if (!bridge) return;
      const title = window.prompt("What do you want to study next?");
      if (!title || !title.trim()) return;
      const estimate = window.prompt("Estimated minutes?", "25");
      bridge.addTask(title.trim(), Number.parseInt(estimate || "25", 10) || 25);
    }});
    $("insightPrevButton")?.addEventListener("click", () => {{
      const items = Array.isArray(studyState?.insights) ? studyState.insights : [];
      if (!items.length) return;
      insightIndex = (insightIndex - 1 + items.length) % items.length;
      renderInsights();
    }});
    $("insightNextButton")?.addEventListener("click", () => {{
      const items = Array.isArray(studyState?.insights) ? studyState.insights : [];
      if (!items.length) return;
      insightIndex = (insightIndex + 1) % items.length;
      renderInsights();
    }});
  }}

  function wireSettingsActions() {{
    $("ankiToggleButton")?.addEventListener("click", () => bridge?.setIntegrationEnabled("anki_enabled", $("ankiToggleButton")?.classList.contains("off")));
    $("pomodoroToggleButton")?.addEventListener("click", () => bridge?.setIntegrationEnabled("pomodoro_bridge_enabled", $("pomodoroToggleButton")?.classList.contains("off")));
    $("openCaldavSettingsButton")?.addEventListener("click", () => bridge?.openHanautaSettings("calendar"));
    $("themeSystemButton")?.addEventListener("click", () => bridge?.setThemeMode("system"));
    $("themeDarkButton")?.addEventListener("click", () => bridge?.setThemeMode("dark"));
    $("themeLightButton")?.addEventListener("click", () => bridge?.setThemeMode("light"));
    $("themeCustomButton")?.addEventListener("click", () => bridge?.setThemeMode("custom"));
    $("customThemeRetrowaveButton")?.addEventListener("click", () => bridge?.setCustomTheme("retrowave"));
    $("customThemeDraculaButton")?.addEventListener("click", () => bridge?.setCustomTheme("dracula"));
    $("syncProviderSelect")?.addEventListener("change", () => {{
      settingsState = settingsState || {{}};
      settingsState.sync = settingsState.sync || {{}};
      settingsState.sync.provider = $("syncProviderSelect").value;
      renderSettings();
    }});
    $("syncAutoButton")?.addEventListener("click", () => {{
      const currentlyOff = $("syncAutoButton")?.classList.contains("off");
      setToggleButton("syncAutoButton", currentlyOff, ["Enabled", "Disabled"]);
    }});
    $("saveSyncSettingsButton")?.addEventListener("click", () => bridge?.saveSyncSettings(JSON.stringify(collectSyncSettings())));
    $("syncNowButton")?.addEventListener("click", () => bridge?.syncNow());
    $("backupButton")?.addEventListener("click", () => bridge?.createBackup());
    $("exportButton")?.addEventListener("click", () => bridge?.exportJson());
    $("flushCacheButton")?.addEventListener("click", () => bridge?.flushCache());
  }}

  window.setStudyState = function (payloadJson) {{
    studyState = JSON.parse(payloadJson);
    render();
  }};

  window.setStudySettings = function (payloadJson) {{
    settingsState = JSON.parse(payloadJson);
    render();
  }};

  window.applyStudyTheme = function (payloadJson) {{
    const studyTheme = JSON.parse(payloadJson);
    const root = document.documentElement;
    Object.entries(studyTheme).forEach(([key, value]) => {{
      root.style.setProperty(`--study-${{key}}`, String(value));
    }});
  }};

  document.addEventListener("DOMContentLoaded", () => {{
    const extraStyle = document.createElement("style");
    extraStyle.textContent = `
      body {{
        background: radial-gradient(circle at top right, var(--study-surfaceLow, #1a1b26) 0%, var(--study-background, #12131d) 100%);
        color: var(--study-text, #e2e1f1);
      }}
      aside, .study-shell-rail {{
        background: var(--study-surfaceLow, #1a1b26) !important;
        box-shadow: 40px 0 60px -15px var(--study-railShadow, rgba(212,187,255,0.05)) !important;
      }}
      header, .study-shell-topbar {{
        background: color-mix(in srgb, var(--study-background, #12131d) 80%, transparent) !important;
      }}
      .study-shell-topbar {{
        border-bottom: 1px solid var(--study-outlineSoft, rgba(149, 142, 156, 0.18));
      }}
      .study-shell-main {{
        background:
          radial-gradient(circle at top right, var(--study-ambientPrimary, rgba(212, 187, 255, 0.09)) 0%, transparent 36%),
          radial-gradient(circle at bottom left, var(--study-ambientSecondary, rgba(255, 178, 188, 0.08)) 0%, transparent 32%),
          transparent;
      }}
      .study-shell-brand,
      .study-shell-title {{
        color: var(--study-primary, #d4bbff) !important;
      }}
      .study-rail-button,
      .study-shell-nav-link,
      .study-shell-action-button {{
        color: var(--study-textMuted, #ccc3d2) !important;
      }}
      .study-rail-button:hover,
      .study-shell-nav-link:hover,
      .study-shell-action-button:hover {{
        color: var(--study-primary, #d4bbff) !important;
        background: color-mix(in srgb, var(--study-surfaceHigh, #282935) 70%, transparent) !important;
      }}
      .study-rail-button.is-active {{
        color: var(--study-primary, #d4bbff) !important;
        background: color-mix(in srgb, var(--study-primary, #d4bbff) 18%, transparent) !important;
      }}
      .study-shell-chip {{
        background: var(--study-surfaceLow, #1a1b26) !important;
      }}
      .study-shell-tooltip {{
        background: var(--study-surfaceHighest, #333440) !important;
        color: var(--study-text, #e2e1f1) !important;
      }}
      .glass-panel {{
        background: color-mix(in srgb, var(--study-surfaceLow, #1a1b26) 70%, transparent) !important;
      }}
      .bg-surface-container-low {{ background: var(--study-surfaceLow, #1a1b26) !important; }}
      .bg-surface-container-high {{ background: var(--study-surfaceHigh, #282935) !important; }}
      .bg-surface-container-highest {{ background: var(--study-surfaceHighest, #333440) !important; }}
      .bg-surface-container-low\\/30 {{ background: color-mix(in srgb, var(--study-surfaceLow, #1a1b26) 30%, transparent) !important; }}
      .hover\\:bg-surface-container-low\\/50:hover {{ background: color-mix(in srgb, var(--study-surfaceLow, #1a1b26) 50%, transparent) !important; }}
      .text-primary, .hover\\:text-primary:hover {{ color: var(--study-primary, #d4bbff) !important; }}
      .text-secondary {{ color: var(--study-secondary, #ffb2bc) !important; }}
      .text-tertiary {{ color: var(--study-tertiary, #aec6ff) !important; }}
      .text-on-surface, .group-hover\\:text-on-surface:hover {{ color: var(--study-text, #e2e1f1) !important; }}
      .text-on-surface-variant, .text-\\[\\#4a4550\\] {{ color: var(--study-textMuted, #ccc3d2) !important; }}
      .text-on-surface-variant\\/60 {{ color: var(--study-textMuted, #ccc3d2) !important; opacity: 0.7 !important; }}
      .text-on-surface-variant\\/20 {{ color: var(--study-textSoft, #777) !important; opacity: 0.5 !important; }}
      .border-primary {{ border-color: var(--study-primary, #d4bbff) !important; }}
      .border-outline-variant {{ border-color: var(--study-outline, #4a4550) !important; }}
      .bg-primary, .hover\\:bg-primary:hover {{ background: var(--study-primary, #d4bbff) !important; }}
      .bg-primary\\/20 {{ background: color-mix(in srgb, var(--study-primary, #d4bbff) 20%, transparent) !important; }}
      .bg-primary\\/15 {{ background: color-mix(in srgb, var(--study-primary, #d4bbff) 15%, transparent) !important; }}
      .bg-primary\\/10 {{ background: color-mix(in srgb, var(--study-primary, #d4bbff) 10%, transparent) !important; }}
      .bg-secondary\\/10 {{ background: color-mix(in srgb, var(--study-secondary, #ffb2bc) 10%, transparent) !important; }}
      .bg-tertiary\\/10 {{ background: color-mix(in srgb, var(--study-tertiary, #aec6ff) 10%, transparent) !important; }}
      .text-on-primary {{ color: var(--study-onPrimary, #3d1b72) !important; }}
    `;
    document.head.appendChild(extraStyle);
    setNavActive(CURRENT_PAGE);
    wireNavigation();
    if (CURRENT_PAGE === "dashboard") wireDashboardActions();
    if (CURRENT_PAGE === "schedule") wireScheduleActions();
    if (CURRENT_PAGE === "settings") wireSettingsActions();
    new QWebChannel(qt.webChannelTransport, function (channel) {{
      bridge = channel.objects.studyBridge;
      if (bridge) bridge.requestBootstrap();
    }});
  }});
}})();
</script>
"""


def build_html(page_name: str) -> str:
    if page_name == "dashboard":
        html_file = HTML_FILE
        page_label = "Overview"
    elif page_name == "schedule":
        html_file = SCHEDULES_HTML_FILE
        page_label = "Schedule"
    else:
        html_file = SETTINGS_HTML_FILE
        page_label = "Settings"
    page_body = html_file.read_text(encoding="utf-8").strip()
    base_html = f"""<!DOCTYPE html>
<html class="dark" lang="en">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>{page_label} | Hanauta Study Track</title>
<link href="study_tracker.css" rel="stylesheet"/>
</head>
<body class="bg-background text-on-surface min-h-screen overflow-hidden">
<aside class="study-shell-rail fixed left-0 top-0 h-full z-50 h-screen w-20 flex flex-col items-center py-8">
<div class="mb-12">
<span class="study-shell-brand text-xl font-bold tracking-tighter font-headline">H</span>
</div>
<nav class="flex flex-col gap-6 flex-1">
<button class="study-rail-button p-3 transition-all duration-300 scale-95 active:scale-90 group relative rounded-2xl" id="navDashboardButton" type="button">
<span class="material-symbols-outlined">dashboard</span>
<span class="study-shell-tooltip absolute left-full ml-4 px-2 py-1 text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Overview</span>
</button>
<button class="study-rail-button p-3 transition-all duration-300 scale-95 active:scale-90 group relative rounded-2xl" type="button">
<span class="material-symbols-outlined">menu_book</span>
</button>
<button class="study-rail-button p-3 transition-all duration-300 scale-95 active:scale-90 group relative rounded-2xl" id="navScheduleButton" type="button">
<span class="material-symbols-outlined">calendar_month</span>
<span class="study-shell-tooltip absolute left-full ml-4 px-2 py-1 text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Schedule</span>
</button>
<button class="study-rail-button p-3 transition-all duration-300 scale-95 active:scale-90 group relative rounded-2xl" type="button">
<span class="material-symbols-outlined">layers</span>
</button>
</nav>
<button class="study-rail-button p-3 transition-all duration-300 scale-95 active:scale-90 group relative rounded-2xl" id="navSettingsButton" type="button">
<span class="material-symbols-outlined">settings</span>
<span class="study-shell-tooltip absolute left-full ml-4 px-2 py-1 text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Settings</span>
</button>
</aside>
<main class="study-shell-main pl-20 pt-16 h-screen flex flex-col overflow-hidden relative">
<header class="study-shell-topbar fixed top-0 right-0 left-20 z-40 px-8 flex justify-between items-center h-16 backdrop-blur-xl">
<div class="flex items-center gap-8">
<h1 class="study-shell-title text-lg font-black font-headline tracking-tight">Hanauta Study Track</h1>
<nav class="hidden md:flex gap-6 items-center">
<a class="study-shell-nav-link font-headline font-semibold text-sm transition-colors" href="#">Focus Mode</a>
<a class="study-shell-nav-link font-headline font-semibold text-sm transition-colors" href="#">Resources</a>
</nav>
</div>
<div class="flex items-center gap-3">
<div class="study-shell-chip flex items-center gap-2 px-3 py-1.5 rounded-full">
<span class="material-symbols-outlined text-sm text-primary">bolt</span>
<span class="text-xs font-bold font-label" id="streakChipText">12 Day Streak</span>
</div>
<div class="study-shell-chip flex items-center gap-2 px-3 py-1.5 rounded-full">
<span class="material-symbols-outlined text-sm text-secondary">timer</span>
<span class="text-xs font-bold font-label" id="todayChipText">45m Today</span>
</div>
<div class="flex gap-3 ml-4">
<button class="study-shell-action-button p-2 rounded-full transition-colors active:opacity-80" type="button">
<span class="material-symbols-outlined">notifications</span>
</button>
<button class="study-shell-action-button p-2 rounded-full transition-colors active:opacity-80" type="button">
<span class="material-symbols-outlined">account_circle</span>
</button>
</div>
</div>
</header>
<div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 blur-[120px] rounded-full pointer-events-none"></div>
<div class="absolute bottom-0 right-0 w-[400px] h-[400px] bg-secondary/5 blur-[100px] rounded-full pointer-events-none"></div>
<div class="flex-1 overflow-y-auto no-scrollbar relative z-10 pb-32">
{page_body}
</div>
</main>
<div class="fixed inset-0 pointer-events-none opacity-[0.03] contrast-150 mix-blend-overlay">
<div class="local-noise w-full h-full"></div>
</div>
</body>
</html>"""
    injected = build_runtime_script(page_name)
    if "</body>" in base_html:
        return base_html.replace("</body>", f"{injected}\n</body>", 1)
    return f"{base_html}\n{injected}"


class StudyBridge(QObject):
    bootstrapRequested = pyqtSignal()
    addTaskRequested = pyqtSignal(str, int)
    toggleTaskRequested = pyqtSignal(str)
    focusTaskRequested = pyqtSignal(str)
    reopenTaskRequested = pyqtSignal(str)
    sessionToggleRequested = pyqtSignal()
    navigateRequested = pyqtSignal(str)
    integrationToggleRequested = pyqtSignal(str, bool)
    openHanautaSettingsRequested = pyqtSignal(str)
    themeModeRequested = pyqtSignal(str)
    customThemeRequested = pyqtSignal(str)
    syncSettingsRequested = pyqtSignal(str)
    syncNowRequested = pyqtSignal()
    backupRequested = pyqtSignal()
    exportRequested = pyqtSignal()
    flushCacheRequested = pyqtSignal()

    @pyqtSlot()
    def requestBootstrap(self) -> None:
        self.bootstrapRequested.emit()

    @pyqtSlot(str, int)
    def addTask(self, title: str, estimate_minutes: int) -> None:
        self.addTaskRequested.emit(title, estimate_minutes)

    @pyqtSlot(str)
    def toggleTask(self, task_id: str) -> None:
        self.toggleTaskRequested.emit(task_id)

    @pyqtSlot(str)
    def focusTask(self, task_id: str) -> None:
        self.focusTaskRequested.emit(task_id)

    @pyqtSlot(str)
    def reopenTask(self, task_id: str) -> None:
        self.reopenTaskRequested.emit(task_id)

    @pyqtSlot()
    def startOrPauseSession(self) -> None:
        self.sessionToggleRequested.emit()

    @pyqtSlot(str)
    def navigateTo(self, page: str) -> None:
        self.navigateRequested.emit(page)

    @pyqtSlot(str, bool)
    def setIntegrationEnabled(self, key: str, enabled: bool) -> None:
        self.integrationToggleRequested.emit(key, enabled)

    @pyqtSlot(str)
    def openHanautaSettings(self, section: str) -> None:
        self.openHanautaSettingsRequested.emit(section)

    @pyqtSlot(str)
    def setThemeMode(self, mode: str) -> None:
        self.themeModeRequested.emit(mode)

    @pyqtSlot(str)
    def setCustomTheme(self, theme_id: str) -> None:
        self.customThemeRequested.emit(theme_id)

    @pyqtSlot(str)
    def saveSyncSettings(self, payload_json: str) -> None:
        self.syncSettingsRequested.emit(payload_json)

    @pyqtSlot()
    def syncNow(self) -> None:
        self.syncNowRequested.emit()

    @pyqtSlot()
    def createBackup(self) -> None:
        self.backupRequested.emit()

    @pyqtSlot()
    def exportJson(self) -> None:
        self.exportRequested.emit()

    @pyqtSlot()
    def flushCache(self) -> None:
        self.flushCacheRequested.emit()


class StudyTrackerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        if not WEBENGINE_AVAILABLE:
            raise RuntimeError(f"QtWebEngine is unavailable: {WEBENGINE_ERROR}")
        self.state = load_state()
        self.current_page = "dashboard"
        self.theme = resolve_study_theme(self.state)
        self._theme_mtime = palette_mtime()
        self._page_ready = False

        self.setWindowTitle("Hanauta Study Track")
        self.resize(1440, 980)
        self.setMinimumSize(1080, 760)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        layout.addWidget(self.view)

        self.channel = QWebChannel(self.view.page())
        self.bridge = StudyBridge()
        self.channel.registerObject("studyBridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.loadFinished.connect(self._handle_load_finished)

        self.bridge.bootstrapRequested.connect(self.push_state)
        self.bridge.addTaskRequested.connect(self.add_task)
        self.bridge.toggleTaskRequested.connect(self.toggle_task)
        self.bridge.focusTaskRequested.connect(self.focus_task)
        self.bridge.reopenTaskRequested.connect(self.reopen_task)
        self.bridge.sessionToggleRequested.connect(self.start_or_pause_session)
        self.bridge.navigateRequested.connect(self.navigate_to)
        self.bridge.integrationToggleRequested.connect(self.set_integration_enabled)
        self.bridge.openHanautaSettingsRequested.connect(self.open_hanauta_settings)
        self.bridge.themeModeRequested.connect(self.set_theme_mode)
        self.bridge.customThemeRequested.connect(self.set_custom_theme)
        self.bridge.syncSettingsRequested.connect(self.save_sync_settings)
        self.bridge.syncNowRequested.connect(self.sync_now)
        self.bridge.backupRequested.connect(self.create_backup)
        self.bridge.exportRequested.connect(self.export_json)
        self.bridge.flushCacheRequested.connect(self.flush_cache)

        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self._tick_session)
        self.session_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self._load_page()

    def _load_page(self) -> None:
        self._page_ready = False
        html = build_html(self.current_page)
        self.view.setHtml(html, QUrl.fromLocalFile(str(HERE) + "/"))

    def _handle_load_finished(self, ok: bool) -> None:
        self._page_ready = ok
        if ok:
            self.push_theme()
            self.push_state()
            self.push_settings()

    def _run_js(self, script: str) -> None:
        if not self._page_ready:
            return
        self.view.page().runJavaScript(script)

    def _save(self) -> None:
        save_state(self.state)

    def push_state(self) -> None:
        payload = json.dumps(build_summary_payload(self.state))
        self._run_js(f"window.setStudyState({json.dumps(payload)});")

    def push_settings(self) -> None:
        payload = json.dumps(build_settings_payload(self.state))
        self._run_js(f"window.setStudySettings({json.dumps(payload)});")

    def push_theme(self) -> None:
        payload = json.dumps(theme_payload(self.theme))
        self._run_js(f"window.applyStudyTheme({json.dumps(payload)});")

    def _reload_theme_if_needed(self) -> None:
        current = palette_mtime()
        system_mode = str(self.state.get("preferences", {}).get("theme_mode", "system")).strip().lower() == "system" if isinstance(self.state.get("preferences"), dict) else True
        if system_mode and current == self._theme_mtime:
            return
        self._theme_mtime = current
        self.theme = resolve_study_theme(self.state)
        self.push_theme()

    def add_task(self, title: str, estimate_minutes: int) -> None:
        task = make_task(title, estimate_minutes)
        if not any(not item.get("done") for item in self.state.get("tasks", [])):
            task["active"] = True
        self.state.setdefault("tasks", []).append(task)
        _ensure_single_active_task(self.state)
        self._save()
        self.push_state()
        if bool(self.state.get("preferences", {}).get("sync", {}).get("auto_sync", False)):
            self.sync_now()

    def toggle_task(self, task_id: str) -> None:
        task = task_by_id(self.state, task_id)
        if task is None:
            return
        done = not bool(task.get("done", False))
        task["done"] = done
        task["completed_at"] = datetime.now().strftime("%I:%M %p").lstrip("0") if done else ""
        if done:
            task["active"] = False
            session = self.state.get("active_session")
            if isinstance(session, dict) and str(session.get("task_id", "")) == task_id:
                self.state["active_session"] = None
        _ensure_single_active_task(self.state)
        self._save()
        self.push_state()
        if bool(self.state.get("preferences", {}).get("sync", {}).get("auto_sync", False)):
            self.sync_now()

    def focus_task(self, task_id: str) -> None:
        for task in self.state.get("tasks", []):
            task["active"] = str(task.get("id", "")) == task_id and not bool(task.get("done", False))
        _ensure_single_active_task(self.state)
        session = self.state.get("active_session")
        if isinstance(session, dict):
            session["task_id"] = task_id
        self._save()
        self.push_state()

    def reopen_task(self, task_id: str) -> None:
        task = task_by_id(self.state, task_id)
        if task is None:
            return
        task["done"] = False
        task["completed_at"] = ""
        for item in self.state.get("tasks", []):
            item["active"] = str(item.get("id", "")) == task_id
        _ensure_single_active_task(self.state)
        self._save()
        self.push_state()

    def navigate_to(self, page: str) -> None:
        normalized = str(page).strip().lower()
        if normalized == "settings":
            target = "settings"
        elif normalized == "schedule":
            target = "schedule"
        else:
            target = "dashboard"
        if target == self.current_page:
            return
        self.current_page = target
        self._load_page()

    def set_integration_enabled(self, key: str, enabled: bool) -> None:
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict) or key not in {"anki_enabled", "pomodoro_bridge_enabled"}:
            return
        preferences[key] = bool(enabled)
        self._save()
        self.push_settings()

    def set_theme_mode(self, mode: str) -> None:
        normalized = str(mode).strip().lower()
        if normalized not in {"system", "dark", "light", "custom"}:
            normalized = "system"
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            return
        preferences["theme_mode"] = normalized
        self.theme = resolve_study_theme(self.state)
        self._save()
        self.push_theme()
        self.push_settings()

    def set_custom_theme(self, theme_id: str) -> None:
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            return
        preferences["custom_theme_id"] = "dracula" if str(theme_id).strip().lower() == "dracula" else "retrowave"
        preferences["theme_mode"] = "custom"
        self.theme = resolve_study_theme(self.state)
        self._save()
        self.push_theme()
        self.push_settings()

    def open_hanauta_settings(self, section: str) -> None:
        del section
        command = entry_command(SETTINGS_PAGE_SCRIPT)
        if not command:
            return
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            notify("Hanauta Settings", "Opened the main Hanauta settings window for CalDAV setup.")
        except Exception as exc:
            notify("Hanauta Settings", f"Unable to open settings: {exc}")

    def save_sync_settings(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            return
        sync = preferences.setdefault("sync", {})
        if not isinstance(sync, dict):
            return
        provider = str(payload.get("provider", "none") or "none").strip().lower()
        sync["provider"] = provider if provider in {"none", "nextcloud", "webdav", "postgres"} else "none"
        sync["remote_path"] = str(payload.get("remote_path", "study-tracker/state.json") or "study-tracker/state.json").strip() or "study-tracker/state.json"
        sync["url"] = str(payload.get("url", "") or "").strip()
        sync["username"] = str(payload.get("username", "") or "").strip()
        sync["password"] = str(payload.get("password", "") or "")
        sync["postgres_dsn"] = str(payload.get("postgres_dsn", "") or "").strip()
        sync["postgres_table"] = str(payload.get("postgres_table", "hanauta_study_tracker") or "hanauta_study_tracker").strip() or "hanauta_study_tracker"
        sync["auto_sync"] = bool(payload.get("auto_sync", False))
        sync["last_status"] = "Sync settings saved."
        self._save()
        self.push_settings()

    def _sync_remote_webdav(self, sync: dict[str, Any]) -> tuple[bool, str]:
        if requests is None:
            return False, "Python requests is unavailable."
        base_url = str(sync.get("url", "") or "").strip().rstrip("/")
        if not base_url:
            return False, "WebDAV or Nextcloud URL is required."
        remote_path = str(sync.get("remote_path", "study-tracker/state.json") or "study-tracker/state.json").strip().lstrip("/")
        endpoint = f"{base_url}/{remote_path}" if remote_path else base_url
        auth = None
        username = str(sync.get("username", "") or "").strip()
        if username:
            auth = (username, str(sync.get("password", "") or ""))
        try:
            response = requests.get(endpoint, auth=auth, timeout=20)
            if response.ok:
                self.state = merge_remote_sync_payload(self.state, response.json())
            elif response.status_code not in {404, 405}:
                return False, f"Remote read failed: HTTP {response.status_code}"
            put_response = requests.put(
                endpoint,
                data=json.dumps(build_sync_payload(self.state)),
                headers={"Content-Type": "application/json"},
                auth=auth,
                timeout=20,
            )
            if not put_response.ok:
                return False, f"Remote sync failed: HTTP {put_response.status_code}"
            return True, "Remote state synced successfully."
        except Exception as exc:
            return False, f"Remote sync failed: {exc}"

    def _sync_remote_postgres(self, sync: dict[str, Any]) -> tuple[bool, str]:
        dsn = str(sync.get("postgres_dsn", "") or "").strip()
        table = str(sync.get("postgres_table", "hanauta_study_tracker") or "hanauta_study_tracker").strip() or "hanauta_study_tracker"
        if not dsn:
            return False, "PostgreSQL DSN is required."
        try:
            import psycopg  # type: ignore
        except Exception:
            return False, "psycopg is not installed in the current environment."
        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, payload JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
                    cur.execute(f"SELECT payload FROM {table} WHERE id = %s", ("study-tracker",))
                    row = cur.fetchone()
                    if row and row[0]:
                        remote_payload = row[0]
                        if isinstance(remote_payload, str):
                            remote_payload = json.loads(remote_payload)
                        if isinstance(remote_payload, dict):
                            self.state = merge_remote_sync_payload(self.state, remote_payload)
                    query = (
                        f"INSERT INTO {table} (id, payload, updated_at) "
                        "VALUES (%s, %s::jsonb, NOW()) "
                        "ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()"
                    )
                    cur.execute(query, ("study-tracker", json.dumps(build_sync_payload(self.state))))
                conn.commit()
            return True, "PostgreSQL sync completed."
        except Exception as exc:
            return False, f"PostgreSQL sync failed: {exc}"

    def sync_now(self) -> None:
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            return
        sync = preferences.setdefault("sync", {})
        if not isinstance(sync, dict):
            return
        provider = str(sync.get("provider", "none") or "none").strip().lower()
        if provider == "none":
            sync["last_status"] = "Local only mode is enabled. Choose a provider first."
            self._save()
            self.push_settings()
            return
        if provider in {"nextcloud", "webdav"}:
            ok, message = self._sync_remote_webdav(sync)
        else:
            ok, message = self._sync_remote_postgres(sync)
        sync["last_status"] = message
        if ok:
            sync["last_sync_at"] = datetime.now().strftime("%b %d, %H:%M")
        self.theme = resolve_study_theme(self.state)
        self._save()
        self.push_theme()
        self.push_state()
        self.push_settings()
        notify("Study Tracker Sync", message)

    def create_backup(self) -> None:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        path = downloads / f"hanauta-study-tracker-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        notify("Study Tracker", f"Backup created: {path.name}")

    def export_json(self) -> None:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        path = downloads / f"hanauta-study-tracker-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(json.dumps(build_sync_payload(self.state), indent=2), encoding="utf-8")
        notify("Study Tracker", f"Exported data: {path.name}")

    def flush_cache(self) -> None:
        self.state["active_session"] = None
        self._save()
        self.push_state()
        self.push_settings()
        notify("Study Tracker", "Live session cache cleared.")

    def start_or_pause_session(self) -> None:
        task = active_task(self.state)
        if task is None:
            return
        session = self.state.get("active_session")
        target_seconds = max(60, int(self.state.get("session_length_minutes", 25) or 25) * 60)
        if not isinstance(session, dict):
            self.state["active_session"] = {
                "task_id": str(task.get("id", "")),
                "elapsed_seconds": 0,
                "target_seconds": target_seconds,
                "running": True,
                "started_at": now_iso(),
            }
            notify("Study session started", f"Focus on {task.get('title', 'your task')}.")
        else:
            if str(session.get("task_id", "")) != str(task.get("id", "")):
                session["task_id"] = str(task.get("id", ""))
                session["elapsed_seconds"] = 0
                session["target_seconds"] = target_seconds
            session["running"] = not bool(session.get("running", False))
            if session["running"]:
                session["started_at"] = now_iso()
        self._save()
        self.push_state()
        if bool(self.state.get("preferences", {}).get("sync", {}).get("auto_sync", False)):
            self.sync_now()

    def _tick_session(self) -> None:
        session = self.state.get("active_session")
        if not isinstance(session, dict) or not bool(session.get("running", False)):
            return
        session["elapsed_seconds"] = max(0, int(session.get("elapsed_seconds", 0) or 0) + 1)
        if int(session.get("elapsed_seconds", 0) or 0) >= int(session.get("target_seconds", 0) or 0):
            self._complete_session()
            return
        self.push_state()

    def _complete_session(self) -> None:
        session = self.state.get("active_session")
        if not isinstance(session, dict):
            return
        task = task_by_id(self.state, str(session.get("task_id", "")))
        added_minutes = max(1, int(session.get("target_seconds", 0) or 0) // 60)
        self.state["today_minutes"] = max(0, int(self.state.get("today_minutes", 0) or 0) + added_minutes)
        self.state.setdefault("activity_dates", [])
        self.state["activity_dates"] = sorted({*self.state["activity_dates"], today_iso()})
        if task is not None:
            task["sessions_completed"] = max(0, int(task.get("sessions_completed", 0) or 0) + 1)
            if int(task.get("sessions_completed", 0) or 0) >= int(task.get("target_sessions", 1) or 1):
                task["done"] = True
                task["active"] = False
                task["completed_at"] = datetime.now().strftime("%I:%M %p").lstrip("0")
        self.state["active_session"] = None
        _ensure_single_active_task(self.state)
        self._save()
        if task is not None:
            notify("Study session complete", f"You finished a focus block for {task.get('title', 'your task')}.")
        else:
            notify("Study session complete", "A focus block has been completed.")
        self.push_state()
        if bool(self.state.get("preferences", {}).get("sync", {}).get("auto_sync", False)):
            self.sync_now()


def main() -> int:
    if not WEBENGINE_AVAILABLE:
        message = (
            "PyQt6 QtWebEngine is not installed in the current environment. "
            "Install the PyQt6 WebEngine package to run Hanauta Study Track."
        )
        print(message, file=sys.stderr)
        notify("Hanauta Study Track", message)
        return 1
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta Study Track")
    window = StudyTrackerWindow()
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        window.move(
            geometry.x() + max(0, (geometry.width() - window.width()) // 2),
            geometry.y() + max(0, (geometry.height() - window.height()) // 2),
        )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
