#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse
from xml.etree import ElementTree as ET

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
RESOURCES_HTML_FILE = HERE / "resources.html"
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

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None  # type: ignore[assignment]

try:
    from yt_dlp import YoutubeDL
except Exception:
    YoutubeDL = None  # type: ignore[assignment]


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
            ["notify-send", "-a", "Hanauta Study Track", title, body],
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
        "linked_resource_id": "",
        "linked_item_id": "",
        "linked_resource_title": "",
        "linked_item_title": "",
        "done": False,
        "active": active,
        "completed_at": "",
        "created_at": now_iso(),
    }


def make_resource_item(
    title: str,
    *,
    duration_seconds: int = 0,
    position: int = 0,
    kind: str = "lesson",
    external_url: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "title": title.strip() or "Untitled item",
        "duration_seconds": max(0, int(duration_seconds or 0)),
        "position": max(0, int(position or 0)),
        "kind": str(kind or "lesson").strip().lower() or "lesson",
        "external_url": str(external_url or "").strip(),
        "notes": str(notes or "").strip(),
        "tracked_minutes": 0,
        "tracked_sessions": 0,
        "done": False,
        "completed_at": "",
    }


def make_resource(
    title: str,
    *,
    kind: str,
    source_url: str,
    author: str = "",
    summary: str = "",
    thumbnail_url: str = "",
    tags: list[str] | None = None,
    items: list[dict[str, Any]] | None = None,
    duration_seconds: int = 0,
    provider: str = "",
) -> dict[str, Any]:
    normalized_items = items if isinstance(items, list) else [make_resource_item(title, duration_seconds=duration_seconds)]
    return {
        "id": str(uuid.uuid4()),
        "title": title.strip() or "Untitled resource",
        "kind": str(kind or "other").strip().lower() or "other",
        "provider": str(provider or kind or "other").strip(),
        "source_url": str(source_url or "").strip(),
        "author": str(author or "").strip(),
        "summary": str(summary or "").strip(),
        "thumbnail_url": str(thumbnail_url or "").strip(),
        "tags": [str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()],
        "items": normalized_items,
        "duration_seconds": max(0, int(duration_seconds or 0)),
        "tracked_minutes": 0,
        "tracked_sessions": 0,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "today_minutes": 0,
        "last_reset_date": today_iso(),
        "activity_dates": [],
        "insights": list(DEFAULT_INSIGHTS),
        "session_length_minutes": 25,
        "schedule_templates": [
            {
                "id": str(uuid.uuid4()),
                "title": "School",
                "category": "Life",
                "kind": "life",
                "recurrence": "weekly",
                "day_of_week": 0,
                "start_time": "08:00",
                "duration_minutes": 180,
                "notify": False,
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Evening Study Slot",
                "category": "Study Slot",
                "kind": "study_slot",
                "recurrence": "weekly",
                "day_of_week": 0,
                "start_time": "19:00",
                "duration_minutes": 90,
                "notify": True,
            },
        ],
        "schedule_blocks": [],
        "resource_plans": [],
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
        "resources": [
            make_resource(
                "Japanese Listening Sprint",
                kind="youtube",
                provider="YouTube",
                source_url="https://www.youtube.com/watch?v=demo-listening",
                author="Hanauta Sample",
                summary="Sample listening resource with chapters to test schedules and focus references.",
                tags=["japanese", "listening"],
                items=[
                    make_resource_item("Warmup and context", duration_seconds=420, position=1, kind="chapter"),
                    make_resource_item("Main listening exercise", duration_seconds=1320, position=2, kind="chapter"),
                    make_resource_item("Review and recap", duration_seconds=360, position=3, kind="chapter"),
                ],
                duration_seconds=2100,
            ),
            make_resource(
                "Distributed Systems Notes",
                kind="book",
                provider="Manual",
                source_url="",
                author="Personal notes",
                summary="Reference notes and excerpts to revisit before backend study blocks.",
                tags=["backend", "distributed-systems"],
                items=[
                    make_resource_item("Consensus chapter", position=1, kind="chapter"),
                    make_resource_item("Replication chapter", position=2, kind="chapter"),
                ],
            ),
        ],
        "selected_focus_resource_id": "",
        "selected_focus_item_id": "",
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
            "resource_policy": {
                "loose_single_limit": 5,
                "schedule_loose_single_limit": 5,
            },
            "notifications": {
                "study_blocks": True,
                "life_blocks": False,
                "caldav_events": False,
                "resource_plans": True,
            },
            "jellyfin": {
                "instance_url": "",
                "api_token": "",
                "user_id": "",
                "last_status": "Jellyfin is not configured yet.",
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
        base["linked_resource_id"] = str(base.get("linked_resource_id", "") or "")
        base["linked_item_id"] = str(base.get("linked_item_id", "") or "")
        base["linked_resource_title"] = str(base.get("linked_resource_title", "") or "")
        base["linked_item_title"] = str(base.get("linked_item_title", "") or "")
        normalized_tasks.append(base)
    if not normalized_tasks:
        normalized_tasks = default_state()["tasks"]
    state["tasks"] = normalized_tasks
    resources = state.get("resources", [])
    if not isinstance(resources, list):
        resources = []
    normalized_resources: list[dict[str, Any]] = []
    for raw_resource in resources:
        if not isinstance(raw_resource, dict):
            continue
        items = raw_resource.get("items", [])
        normalized_items: list[dict[str, Any]] = []
        if isinstance(items, list):
            for index, raw_item in enumerate(items, start=1):
                if not isinstance(raw_item, dict):
                    continue
                item = make_resource_item(
                    str(raw_item.get("title", "Untitled item")),
                    duration_seconds=int(raw_item.get("duration_seconds", 0) or 0),
                    position=int(raw_item.get("position", index) or index),
                    kind=str(raw_item.get("kind", "lesson") or "lesson"),
                    external_url=str(raw_item.get("external_url", "") or ""),
                    notes=str(raw_item.get("notes", "") or ""),
                )
                item.update(raw_item)
                item["done"] = bool(item.get("done", False))
                item["completed_at"] = str(item.get("completed_at", "") or "")
                item["tracked_minutes"] = max(0, int(item.get("tracked_minutes", 0) or 0))
                item["tracked_sessions"] = max(0, int(item.get("tracked_sessions", 0) or 0))
                normalized_items.append(item)
        resource = make_resource(
            str(raw_resource.get("title", "Untitled resource")),
            kind=str(raw_resource.get("kind", "other") or "other"),
            provider=str(raw_resource.get("provider", raw_resource.get("kind", "other")) or "other"),
            source_url=str(raw_resource.get("source_url", "") or ""),
            author=str(raw_resource.get("author", "") or ""),
            summary=str(raw_resource.get("summary", "") or ""),
            thumbnail_url=str(raw_resource.get("thumbnail_url", "") or ""),
            tags=list(raw_resource.get("tags", [])) if isinstance(raw_resource.get("tags"), list) else [],
            items=normalized_items,
            duration_seconds=int(raw_resource.get("duration_seconds", 0) or 0),
        )
        resource.update(raw_resource)
        resource["tags"] = [str(tag).strip().lower() for tag in resource.get("tags", []) if str(tag).strip()]
        resource["updated_at"] = str(resource.get("updated_at", resource.get("created_at", now_iso())) or now_iso())
        resource["created_at"] = str(resource.get("created_at", now_iso()) or now_iso())
        resource["items"] = sorted(normalized_items, key=lambda item: int(item.get("position", 0) or 0))
        resource["document_total_pages"] = max(0, int(resource.get("document_total_pages", 0) or 0))
        resource["document_current_page"] = max(0, int(resource.get("document_current_page", 0) or 0))
        resource["document_path"] = str(resource.get("document_path", "") or "")
        resource["tracked_minutes"] = max(0, int(resource.get("tracked_minutes", 0) or 0))
        resource["tracked_sessions"] = max(0, int(resource.get("tracked_sessions", 0) or 0))
        normalized_resources.append(resource)
    if not normalized_resources:
        normalized_resources = default_state()["resources"]
    state["resources"] = normalized_resources
    templates = state.get("schedule_templates", [])
    normalized_templates: list[dict[str, Any]] = []
    if isinstance(templates, list):
        for raw in templates:
            if not isinstance(raw, dict):
                continue
            normalized_templates.append(
                {
                    "id": str(raw.get("id", uuid.uuid4()) or uuid.uuid4()),
                    "title": str(raw.get("title", "Schedule Slot") or "Schedule Slot"),
                    "category": str(raw.get("category", "General") or "General"),
                    "kind": str(raw.get("kind", "life") or "life").strip().lower(),
                    "resource_id": str(raw.get("resource_id", "") or ""),
                    "item_id": str(raw.get("item_id", "") or ""),
                    "recurrence": str(raw.get("recurrence", "weekly") or "weekly").strip().lower(),
                    "day_of_week": max(0, min(6, int(raw.get("day_of_week", 0) or 0))),
                    "start_time": str(raw.get("start_time", "08:00") or "08:00"),
                    "duration_minutes": max(15, int(raw.get("duration_minutes", 60) or 60)),
                    "notify": bool(raw.get("notify", False)),
                }
            )
    state["schedule_templates"] = normalized_templates
    blocks = state.get("schedule_blocks", [])
    normalized_blocks: list[dict[str, Any]] = []
    if isinstance(blocks, list):
        for raw in blocks:
            if not isinstance(raw, dict):
                continue
            normalized_blocks.append(
                {
                    "id": str(raw.get("id", uuid.uuid4()) or uuid.uuid4()),
                    "title": str(raw.get("title", "Study Block") or "Study Block"),
                    "category": str(raw.get("category", "General") or "General"),
                    "kind": str(raw.get("kind", "study") or "study").strip().lower(),
                    "date": str(raw.get("date", today_iso()) or today_iso()),
                    "start_time": str(raw.get("start_time", "08:00") or "08:00"),
                    "duration_minutes": max(15, int(raw.get("duration_minutes", 60) or 60)),
                    "resource_id": str(raw.get("resource_id", "") or ""),
                    "item_id": str(raw.get("item_id", "") or ""),
                    "source": str(raw.get("source", "manual") or "manual"),
                    "notify": bool(raw.get("notify", False)),
                    "notes": str(raw.get("notes", "") or ""),
                }
            )
    state["schedule_blocks"] = normalized_blocks
    plans = state.get("resource_plans", [])
    normalized_plans: list[dict[str, Any]] = []
    if isinstance(plans, list):
        for raw in plans:
            if not isinstance(raw, dict):
                continue
            normalized_plans.append(
                {
                    "id": str(raw.get("id", uuid.uuid4()) or uuid.uuid4()),
                    "resource_id": str(raw.get("resource_id", "") or ""),
                    "resource_title": str(raw.get("resource_title", "") or ""),
                    "classes_per_day": max(1, int(raw.get("classes_per_day", 1) or 1)),
                    "created_at": str(raw.get("created_at", now_iso()) or now_iso()),
                    "active": bool(raw.get("active", True)),
                }
            )
    state["resource_plans"] = normalized_plans
    active_session = state.get("active_session")
    if not isinstance(active_session, dict):
        state["active_session"] = None
    else:
        state["active_session"] = {
            "task_id": str(active_session.get("task_id", "")),
            "resource_id": str(active_session.get("resource_id", "") or ""),
            "item_id": str(active_session.get("item_id", "") or ""),
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
    resource_policy = merged_preferences.get("resource_policy", {})
    if not isinstance(resource_policy, dict):
        resource_policy = {}
    merged_policy = dict(default_preferences["resource_policy"])
    merged_policy.update(resource_policy)
    loose_single_limit = merged_policy.get("loose_single_limit", 5)
    schedule_loose_single_limit = merged_policy.get("schedule_loose_single_limit", 5)
    merged_policy["loose_single_limit"] = -1 if int(loose_single_limit or 0) < 0 else max(0, int(loose_single_limit or 0))
    merged_policy["schedule_loose_single_limit"] = -1 if int(schedule_loose_single_limit or 0) < 0 else max(0, int(schedule_loose_single_limit or 0))
    merged_preferences["resource_policy"] = merged_policy
    notifications = merged_preferences.get("notifications", {})
    if not isinstance(notifications, dict):
        notifications = {}
    merged_notifications = dict(default_preferences["notifications"])
    merged_notifications.update(notifications)
    for key in ("study_blocks", "life_blocks", "caldav_events", "resource_plans"):
        merged_notifications[key] = bool(merged_notifications.get(key, False))
    merged_preferences["notifications"] = merged_notifications
    jellyfin = merged_preferences.get("jellyfin", {})
    if not isinstance(jellyfin, dict):
        jellyfin = {}
    merged_jellyfin = dict(default_preferences["jellyfin"])
    merged_jellyfin.update(jellyfin)
    merged_jellyfin["instance_url"] = str(merged_jellyfin.get("instance_url", "") or "").strip().rstrip("/")
    merged_jellyfin["api_token"] = str(merged_jellyfin.get("api_token", "") or "").strip()
    merged_jellyfin["user_id"] = str(merged_jellyfin.get("user_id", "") or "").strip()
    merged_jellyfin["last_status"] = str(merged_jellyfin.get("last_status", "Jellyfin is not configured yet.") or "Jellyfin is not configured yet.")
    merged_preferences["jellyfin"] = merged_jellyfin
    merged_preferences["anki_enabled"] = bool(merged_preferences.get("anki_enabled", True))
    merged_preferences["pomodoro_bridge_enabled"] = bool(merged_preferences.get("pomodoro_bridge_enabled", True))
    theme_mode = str(merged_preferences.get("theme_mode", "system") or "system").strip().lower()
    if theme_mode not in {"system", "dark", "light", "custom"}:
        theme_mode = "system"
    merged_preferences["theme_mode"] = theme_mode
    custom_theme_id = str(merged_preferences.get("custom_theme_id", "retrowave") or "retrowave").strip().lower()
    merged_preferences["custom_theme_id"] = custom_theme_id if custom_theme_id in {"retrowave", "dracula"} else "retrowave"
    state["preferences"] = merged_preferences
    state["selected_focus_resource_id"] = str(state.get("selected_focus_resource_id", "") or "")
    state["selected_focus_item_id"] = str(state.get("selected_focus_item_id", "") or "")
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
        "schedule_templates": deepcopy(state.get("schedule_templates", [])),
        "schedule_blocks": deepcopy(state.get("schedule_blocks", [])),
        "resource_plans": deepcopy(state.get("resource_plans", [])),
        "tasks": deepcopy(state.get("tasks", [])),
        "resources": deepcopy(state.get("resources", [])),
        "active_session": deepcopy(state.get("active_session")),
        "preferences": {
            "anki_enabled": bool(state.get("preferences", {}).get("anki_enabled", True)) if isinstance(state.get("preferences"), dict) else True,
            "pomodoro_bridge_enabled": bool(state.get("preferences", {}).get("pomodoro_bridge_enabled", True)) if isinstance(state.get("preferences"), dict) else True,
            "theme_mode": str(state.get("preferences", {}).get("theme_mode", "system")) if isinstance(state.get("preferences"), dict) else "system",
            "custom_theme_id": str(state.get("preferences", {}).get("custom_theme_id", "retrowave")) if isinstance(state.get("preferences"), dict) else "retrowave",
            "resource_policy": deepcopy(state.get("preferences", {}).get("resource_policy", {})) if isinstance(state.get("preferences"), dict) else {},
            "notifications": deepcopy(state.get("preferences", {}).get("notifications", {})) if isinstance(state.get("preferences"), dict) else {},
        },
    }


def merge_remote_sync_payload(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return state
    merged = deepcopy(state)
    for key in ("today_minutes", "last_reset_date", "activity_dates", "insights", "session_length_minutes", "schedule_templates", "schedule_blocks", "resource_plans", "tasks", "resources", "active_session"):
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


def resource_by_id(state: dict[str, Any], resource_id: str) -> dict[str, Any] | None:
    for resource in state.get("resources", []):
        if isinstance(resource, dict) and str(resource.get("id", "")) == resource_id:
            return resource
    return None


def resource_item_by_id(state: dict[str, Any], resource_id: str, item_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    resource = resource_by_id(state, resource_id)
    if not isinstance(resource, dict):
        return None, None
    if item_id == "__resource__":
        synthetic = {
            "id": "__resource__",
            "title": str(resource.get("title", "Untitled resource") or "Untitled resource"),
            "kind": "document" if str(resource.get("kind", "")).lower() == "document" else "resource",
            "tracked_minutes": int(resource.get("tracked_minutes", 0) or 0),
            "tracked_sessions": int(resource.get("tracked_sessions", 0) or 0),
            "external_url": str(resource.get("source_url", "") or ""),
            "notes": str(resource.get("summary", "") or ""),
        }
        return resource, synthetic
    for item in resource.get("items", []):
        if isinstance(item, dict) and str(item.get("id", "")) == item_id:
            return resource, item
    return resource, None


def build_focus_class_options(state: dict[str, Any]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for resource in state.get("resources", []):
        if not isinstance(resource, dict):
            continue
        items = resource.get("items", [])
        if str(resource.get("kind", "")).strip().lower() == "document" or not isinstance(items, list) or not items:
            options.append(
                {
                    "resource_id": str(resource.get("id", "")),
                    "item_id": "__resource__",
                    "value": f"{resource.get('id', '')}::__resource__",
                    "title": str(resource.get("title", "Untitled study target") or "Untitled study target"),
                    "resource_title": str(resource.get("title", "Resource") or "Resource"),
                    "tracked_minutes": int(resource.get("tracked_minutes", 0) or 0),
                    "tracked_sessions": int(resource.get("tracked_sessions", 0) or 0),
                }
            )
            continue
        for item in resource.get("items", []):
            if not isinstance(item, dict):
                continue
            options.append(
                {
                    "resource_id": str(resource.get("id", "")),
                    "item_id": str(item.get("id", "")),
                    "value": f"{resource.get('id', '')}::{item.get('id', '')}",
                    "title": str(item.get("title", "Untitled class") or "Untitled class"),
                    "resource_title": str(resource.get("title", "Resource") or "Resource"),
                    "tracked_minutes": int(item.get("tracked_minutes", 0) or 0),
                    "tracked_sessions": int(item.get("tracked_sessions", 0) or 0),
                }
            )
    return options


def focus_target_from_state(state: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    selected_resource_id = str(state.get("selected_focus_resource_id", "") or "")
    selected_item_id = str(state.get("selected_focus_item_id", "") or "")
    if not selected_resource_id:
        return None, None
    return resource_item_by_id(state, selected_resource_id, selected_item_id)


def parse_clock_minutes(value: str) -> int:
    try:
        hours, minutes = str(value or "08:00").split(":", 1)
        return max(0, min(23 * 60 + 59, int(hours) * 60 + int(minutes)))
    except Exception:
        return 8 * 60


def format_clock(minutes: int) -> str:
    total = max(0, int(minutes or 0))
    hours, mins = divmod(total, 60)
    return f"{hours:02d}:{mins:02d}"


def end_clock(start_time: str, duration_minutes: int) -> str:
    return format_clock(parse_clock_minutes(start_time) + max(0, int(duration_minutes or 0)))


def format_schedule_when(date_value: str, start_time: str, duration_minutes: int) -> str:
    try:
        parsed = datetime.strptime(str(date_value), "%Y-%m-%d")
        day_label = parsed.strftime("%A")
    except Exception:
        day_label = "Scheduled"
    return f"{day_label}, {start_time} - {end_clock(start_time, duration_minutes)}"


def is_loose_single_resource(resource: dict[str, Any]) -> bool:
    kind = str(resource.get("kind", "") or "").strip().lower()
    items = resource.get("items", [])
    if kind == "document":
        return True
    if not isinstance(items, list):
        return True
    return len(items) <= 1 and kind in {"youtube", "jellyfin", "book", "audio", "other"}


def loose_single_resources(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [resource for resource in state.get("resources", []) if isinstance(resource, dict) and is_loose_single_resource(resource)]


def build_schedule_target_options(state: dict[str, Any]) -> list[dict[str, Any]]:
    policy = state.get("preferences", {}).get("resource_policy", {}) if isinstance(state.get("preferences"), dict) else {}
    loose_limit = int(policy.get("schedule_loose_single_limit", 5) or 0) if isinstance(policy, dict) else 5
    unlimited = loose_limit < 0
    loose_used = 0
    options: list[dict[str, Any]] = []
    for resource in state.get("resources", []):
        if not isinstance(resource, dict):
            continue
        if is_loose_single_resource(resource):
            if not unlimited and loose_used >= loose_limit:
                continue
            loose_used += 1
            option_type = "single"
        else:
            option_type = "resource"
        title = str(resource.get("title", "Resource") or "Resource")
        options.append(
            {
                "resource_id": str(resource.get("id", "")),
                "item_id": "__resource__" if is_loose_single_resource(resource) else "",
                "title": title,
                "label": f"{title} ({'single item' if option_type == 'single' else 'resource'})",
                "type": option_type,
                "kind": str(resource.get("kind", "resource") or "resource"),
            }
        )
    return options


def find_or_create_task_for_focus_target(state: dict[str, Any], resource: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    linked_resource_id = str(resource.get("id", "") or "")
    linked_item_id = str(item.get("id", "") or "")
    for task in state.get("tasks", []):
        if (
            isinstance(task, dict)
            and not bool(task.get("done", False))
            and str(task.get("linked_resource_id", "") or "") == linked_resource_id
            and str(task.get("linked_item_id", "") or "") == linked_item_id
        ):
            return task
    title = str(item.get("title", resource.get("title", "Study session")) or "Study session")
    estimate = max(10, int(state.get("session_length_minutes", 25) or 25))
    task = make_task(title, estimate)
    task["linked_resource_id"] = linked_resource_id
    task["linked_item_id"] = linked_item_id
    task["linked_resource_title"] = str(resource.get("title", "") or "")
    task["linked_item_title"] = title
    for existing in state.get("tasks", []):
        if isinstance(existing, dict):
            existing["active"] = False
    state.setdefault("tasks", []).append(task)
    _ensure_single_active_task(state)
    return task


def build_summary_payload(state: dict[str, Any]) -> dict[str, Any]:
    current_task = active_task(state)
    session = state.get("active_session")
    session_payload: dict[str, Any] | None = None
    focus_options = build_focus_class_options(state)
    selected_focus_resource_id = str(state.get("selected_focus_resource_id", "") or "")
    selected_focus_item_id = str(state.get("selected_focus_item_id", "") or "")
    selected_focus_option = next((option for option in focus_options if option["resource_id"] == selected_focus_resource_id and option["item_id"] == selected_focus_item_id), None)
    selected_resource, selected_item = focus_target_from_state(state)
    if isinstance(session, dict):
        session_payload = {
            "task_id": str(session.get("task_id", "")),
            "resource_id": str(session.get("resource_id", "") or ""),
            "item_id": str(session.get("item_id", "") or ""),
            "elapsed_seconds": max(0, int(session.get("elapsed_seconds", 0) or 0)),
            "target_seconds": max(60, int(session.get("target_seconds", 25 * 60) or 25 * 60)),
            "running": bool(session.get("running", False)),
        }
    objective = {
        "prefix": "Choose your next",
        "title": "study target",
        "meta": "Link a resource, document, or lesson to start intentional focus blocks.",
        "progress_text": "0 / 0",
        "progress_percent": 0,
    }
    if isinstance(selected_item, dict):
        objective["prefix"] = "Current focus target"
        objective["title"] = str(selected_item.get("title", "study target") or "study target")
        resource_title = str(selected_resource.get("title", "") or "") if isinstance(selected_resource, dict) else ""
        item_minutes = int(selected_item.get("tracked_minutes", 0) or 0)
        item_sessions = int(selected_item.get("tracked_sessions", 0) or 0)
        objective["meta"] = resource_title if resource_title and resource_title != objective["title"] else "Selected study target"
        if current_task:
            objective["meta"] = f"{objective['meta']} • Plan: {current_task.get('title', 'Study task')}" if objective["meta"] else f"Plan: {current_task.get('title', 'Study task')}"
        objective["progress_text"] = f"{item_minutes} min • {item_sessions} session{'s' if item_sessions != 1 else ''}"
        objective["progress_percent"] = min(100, max(8, item_minutes if item_minutes > 0 else item_sessions * 25))
    elif current_task:
        completed = max(0, int(current_task.get("sessions_completed", 0) or 0))
        target = max(1, int(current_task.get("target_sessions", 1) or 1))
        remaining = max(0, target - completed)
        objective["prefix"] = f"Finish {remaining} Pomodoro{'s' if remaining != 1 else ''} of" if remaining > 0 else "Keep momentum with"
        objective["title"] = str(current_task.get("title", "study target") or "study target")
        objective["meta"] = "Agenda item ready to become your next focused study block."
        objective["progress_text"] = f"{completed} / {target}"
        objective["progress_percent"] = 100 if current_task.get("done") else max(8, int((completed / target) * 100))
    if isinstance(session, dict):
        elapsed = max(0, int(session.get("elapsed_seconds", 0) or 0))
        target_seconds = max(1, int(session.get("target_seconds", 1) or 1))
        objective["prefix"] = "Focus session"
        objective["progress_text"] = f"{elapsed // 60} min tracked • {max(0, target_seconds - elapsed) // 60} min left"
        objective["progress_percent"] = min(100, max(8, int((elapsed / target_seconds) * 100)))
    schedule_blocks: list[dict[str, Any]] = []
    for block in sorted(state.get("schedule_blocks", []), key=lambda item: (str(item.get("date", "")), str(item.get("start_time", "")))):
        if not isinstance(block, dict):
            continue
        schedule_blocks.append(
            {
                "id": str(block.get("id", "")),
                "title": str(block.get("title", "Study Block") or "Study Block"),
                "category": str(block.get("category", "General") or "General"),
                "kind": str(block.get("kind", "study") or "study"),
                "date": str(block.get("date", today_iso()) or today_iso()),
                "start_time": str(block.get("start_time", "08:00") or "08:00"),
                "end_time": end_clock(str(block.get("start_time", "08:00") or "08:00"), int(block.get("duration_minutes", 60) or 60)),
                "duration_minutes": int(block.get("duration_minutes", 60) or 60),
                "when": format_schedule_when(str(block.get("date", today_iso()) or today_iso()), str(block.get("start_time", "08:00") or "08:00"), int(block.get("duration_minutes", 60) or 60)),
                "source": str(block.get("source", "manual") or "manual"),
                "notes": str(block.get("notes", "") or ""),
            }
        )
    schedule_templates = [
        {
            "id": str(template.get("id", "")),
            "title": str(template.get("title", "Schedule Slot") or "Schedule Slot"),
            "category": str(template.get("category", "General") or "General"),
            "kind": str(template.get("kind", "life") or "life"),
            "day_of_week": int(template.get("day_of_week", 0) or 0),
            "start_time": str(template.get("start_time", "08:00") or "08:00"),
            "duration_minutes": int(template.get("duration_minutes", 60) or 60),
            "notify": bool(template.get("notify", False)),
        }
        for template in state.get("schedule_templates", [])
        if isinstance(template, dict)
    ]
    return {
        "streak_days": compute_streak_days(state),
        "today_minutes": max(0, int(state.get("today_minutes", 0) or 0)),
        "agenda_date": datetime.now().strftime("%A, %b %d"),
        "session_length_minutes": max(1, int(state.get("session_length_minutes", 25) or 25)),
        "insights": state.get("insights", []),
        "tasks": state.get("tasks", []),
        "current_task": current_task,
        "objective": objective,
        "focus_class_options": focus_options,
        "selected_focus_class": selected_focus_option,
        "schedule_target_options": build_schedule_target_options(state),
        "schedule_blocks": schedule_blocks,
        "schedule_templates": schedule_templates,
        "active_session": session_payload,
    }


def build_settings_payload(state: dict[str, Any]) -> dict[str, Any]:
    preferences = state.get("preferences", {})
    if not isinstance(preferences, dict):
        preferences = {}
    sync = preferences.get("sync", {})
    if not isinstance(sync, dict):
        sync = {}
    jellyfin = preferences.get("jellyfin", {})
    if not isinstance(jellyfin, dict):
        jellyfin = {}
    resource_policy = preferences.get("resource_policy", {})
    if not isinstance(resource_policy, dict):
        resource_policy = {}
    notifications = preferences.get("notifications", {})
    if not isinstance(notifications, dict):
        notifications = {}
    theme_mode = str(preferences.get("theme_mode", "system") or "system").strip().lower()
    custom_theme_id = str(preferences.get("custom_theme_id", "retrowave") or "retrowave").strip().lower()
    sync_provider = str(sync.get("provider", "none") or "none").strip().lower()
    sync_summary = {
        "none": "Local only",
        "nextcloud": "Nextcloud sync",
        "webdav": "WebDAV sync",
        "postgres": "PostgreSQL sync",
    }.get(sync_provider, "Local only")
    jellyfin_instance = str(jellyfin.get("instance_url", "") or "").strip()
    jellyfin_summary = jellyfin_instance or "Not configured"
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
        "jellyfin": {
            "instance_url": jellyfin_instance,
            "api_token": str(jellyfin.get("api_token", "") or ""),
            "last_status": str(jellyfin.get("last_status", "Jellyfin is not configured yet.") or "Jellyfin is not configured yet."),
        },
        "resource_policy": {
            "loose_single_limit": int(resource_policy.get("loose_single_limit", 5) or 0),
            "schedule_loose_single_limit": int(resource_policy.get("schedule_loose_single_limit", 5) or 0),
        },
        "notifications": {
            "study_blocks": bool(notifications.get("study_blocks", True)),
            "life_blocks": bool(notifications.get("life_blocks", False)),
            "caldav_events": bool(notifications.get("caldav_events", False)),
            "resource_plans": bool(notifications.get("resource_plans", True)),
        },
        "theme_summary": theme_summary,
        "sync_summary": sync_summary,
        "jellyfin_summary": jellyfin_summary,
        "caldav_summary": "Schedules can sync through Hanauta Settings independently from Study Tracker cloud sync.",
    }


def seconds_to_compact(seconds: int) -> str:
    total = max(0, int(seconds or 0))
    if total <= 0:
        return ""
    hours, rem = divmod(total, 3600)
    minutes, _ = divmod(rem, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def resource_progress(resource: dict[str, Any]) -> tuple[int, int]:
    if str(resource.get("kind", "")).strip().lower() == "document":
        current = max(0, int(resource.get("document_current_page", 0) or 0))
        total = max(1, int(resource.get("document_total_pages", 0) or 1))
        return min(current, total), total
    items = resource.get("items", [])
    if not isinstance(items, list) or not items:
        return 0, 0
    total = len(items)
    done = sum(1 for item in items if isinstance(item, dict) and bool(item.get("done", False)))
    return done, total


def build_resources_payload(state: dict[str, Any]) -> dict[str, Any]:
    resources = state.get("resources", [])
    if not isinstance(resources, list):
        resources = []
    cards: list[dict[str, Any]] = []
    total_completed = 0
    total_items = 0
    total_duration = 0
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        done, total = resource_progress(resource)
        total_completed += done
        total_items += total
        duration_seconds = max(0, int(resource.get("duration_seconds", 0) or 0))
        total_duration += duration_seconds
        kind = str(resource.get("kind", "other") or "other").strip().lower()
        accent = {
            "youtube": "tertiary",
            "udemy": "primary",
            "jellyfin": "primary",
            "book": "secondary",
            "audio": "primary-fixed",
            "anki": "error",
        }.get(kind, "primary")
        kind_label = str(resource.get("kind_label", resource.get("media_kind", kind))).strip()
        if not kind_label:
            kind_label = kind
        cards.append(
            {
                "id": str(resource.get("id", "")),
                "title": str(resource.get("title", "Untitled resource") or "Untitled resource"),
                "kind": kind,
                "provider": str(resource.get("provider", kind.title()) or kind.title()),
                "kind_label": kind_label.upper(),
                "media_kind": str(resource.get("media_kind", kind) or kind),
                "author": str(resource.get("author", "") or ""),
                "summary": str(resource.get("summary", "") or ""),
                "source_url": str(resource.get("source_url", "") or ""),
                "thumbnail_url": str(resource.get("thumbnail_url", "") or ""),
                "tags": list(resource.get("tags", [])) if isinstance(resource.get("tags"), list) else [],
                "done_items": done,
                "total_items": total,
                "progress_percent": int(round((done / total) * 100)) if total else 0,
                "duration_label": seconds_to_compact(duration_seconds) or "Open",
                "accent": accent,
                "updated_label": str(resource.get("updated_at", "") or "")[:10],
                "items": deepcopy(resource.get("items", [])),
                "document_total_pages": int(resource.get("document_total_pages", 0) or 0),
                "document_current_page": int(resource.get("document_current_page", 0) or 0),
            }
        )
    cards.sort(key=lambda item: item.get("updated_label", ""), reverse=True)
    preferences = state.get("preferences", {}) if isinstance(state.get("preferences"), dict) else {}
    policy = preferences.get("resource_policy", {}) if isinstance(preferences, dict) else {}
    return {
        "resources": cards,
        "summary": {
            "resource_count": len(cards),
            "completed_items": total_completed,
            "total_items": total_items,
            "tracked_hours": round(total_duration / 3600, 1) if total_duration else 0,
            "loose_single_count": len(loose_single_resources(state)),
            "loose_single_limit": int(policy.get("loose_single_limit", 5) or 0) if isinstance(policy, dict) else 5,
        },
        "import": {
            "busy": False,
            "message": "",
        },
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


def is_youtube_url(value: str) -> bool:
    host = urlparse(value).netloc.lower()
    return "youtube.com" in host or "youtu.be" in host


def is_udemy_url(value: str) -> bool:
    return "udemy.com" in urlparse(value).netloc.lower()


def jellyfin_url_base(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = str(parsed.path or "").strip("/")
    if path:
        parts = path.split("/")
        if parts and parts[0].lower() in {"jellyfin", "emby"}:
            return f"{parsed.scheme}://{parsed.netloc}/{parts[0]}".rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def extract_jellyfin_item_id(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    candidates = [parsed.query, parsed.fragment]
    for candidate in candidates:
        if not candidate:
            continue
        query_part = candidate.split("?", 1)[1] if "?" in candidate else candidate
        params = parse_qs(query_part.lstrip("!/"))
        for key in ("id", "itemId", "itemid"):
            found = params.get(key)
            if found and found[0]:
                return str(found[0]).strip()
    parts = [part for part in parsed.path.split("/") if part]
    for index, part in enumerate(parts):
        if part.lower() == "items" and index + 1 < len(parts):
            return str(parts[index + 1]).strip()
    return ""


def slug_tags(*values: str) -> list[str]:
    seen: list[str] = []
    for value in values:
        for tag in re.findall(r"[a-zA-Z0-9\+\#]{3,}", value.lower()):
            if tag not in seen:
                seen.append(tag)
    return seen[:6]


DOCUMENT_SUFFIXES = {".pdf", ".epub", ".doc", ".odt", ".docx", ".mobi", ".djvu"}


def is_document_reference(value: str) -> bool:
    expanded = Path(os.path.expanduser(value)).expanduser()
    if expanded.suffix.lower() in DOCUMENT_SUFFIXES:
        return True
    parsed = urlparse(value)
    return parsed.scheme == "file" and Path(unquote(parsed.path)).suffix.lower() in DOCUMENT_SUFFIXES


def estimate_pages_from_text(text: str) -> int:
    words = re.findall(r"\w+", text)
    return max(1, math.ceil(len(words) / 300)) if words else 1


def data_uri_for_bytes(payload: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(payload).decode('ascii')}"


def generated_document_cover(title: str, extension: str) -> str:
    label = extension.upper().lstrip(".") or "DOC"
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="480" height="640" viewBox="0 0 480 640">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#2d2340"/>
      <stop offset="100%" stop-color="#141218"/>
    </linearGradient>
  </defs>
  <rect width="480" height="640" rx="42" fill="url(#g)"/>
  <rect x="34" y="34" width="412" height="572" rx="30" fill="rgba(255,255,255,0.04)" stroke="rgba(212,187,255,0.18)"/>
  <text x="60" y="120" fill="#d4bbff" font-size="30" font-family="Segoe UI, sans-serif" font-weight="700">{label}</text>
  <text x="60" y="190" fill="#f3ecff" font-size="42" font-family="Segoe UI, sans-serif" font-weight="700">{title[:26]}</text>
  <text x="60" y="236" fill="#f3ecff" font-size="42" font-family="Segoe UI, sans-serif" font-weight="700">{title[26:52]}</text>
  <rect x="60" y="292" width="220" height="10" rx="5" fill="rgba(212,187,255,0.24)"/>
  <rect x="60" y="324" width="280" height="10" rx="5" fill="rgba(212,187,255,0.18)"/>
  <rect x="60" y="356" width="180" height="10" rx="5" fill="rgba(212,187,255,0.12)"/>
</svg>
""".strip()
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def youtube_sign_in_required(message: str) -> bool:
    lowered = message.lower()
    triggers = [
        "sign in",
        "confirm you’re not a bot",
        "confirm you're not a bot",
        "use --cookies",
        "video unavailable",
        "precondition check failed",
        "login required",
    ]
    return any(trigger in lowered for trigger in triggers)


def extract_youtube_video_id(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        return parsed.path.strip("/").split("/")[0]
    query = parse_qs(parsed.query)
    if query.get("v"):
        return query["v"][0]
    parts = [part for part in parsed.path.split("/") if part]
    if "watch" in parts and query.get("v"):
        return query["v"][0]
    return ""


def extract_youtube_playlist_id(value: str) -> str:
    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    if query.get("list"):
        return query["list"][0]
    return ""


def build_runtime_script(page_name: str) -> str:
    return f"""
<script src="htmx.min.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
(function () {{
  const INITIAL_PAGE = {json.dumps(page_name)};
  const PAGE_FRAGMENT_MAP = {{
    dashboard: "code.html",
    resources: "resources.html",
    schedule: "schedules.html",
    settings: "settingspage.html",
  }};
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  let studyState = null;
  let settingsState = null;
  let resourcesState = null;
  let insightIndex = 0;
  let selectedResourceId = "";
  let resourceFilter = "all";
  let currentPage = INITIAL_PAGE;
  let bridge = null;
  let focusClassQuery = "";
  let focusClassOpen = false;
  let focusClassActiveIndex = -1;
  let scheduleViewMode = "week";
  let scheduleAnchorDate = new Date();
  let scheduleSidebarMode = "empty";
  let selectedScheduleBlockId = "";
  let editingScheduleBlockId = "";
  let editingScheduleTemplateId = "";
  let scheduleTargetState = {{
    block: {{ query: "", open: false, activeIndex: -1 }},
    template: {{ query: "", open: false, activeIndex: -1 }},
  }};

  function setNavActive(page) {{
    const dashboard = $("navDashboardButton");
    const resources = $("navResourcesButton");
    const schedule = $("navScheduleButton");
    const settings = $("navSettingsButton");
    [dashboard, resources, schedule, settings].forEach((button) => {{
      if (!button) return;
      button.classList.remove("is-active");
    }});
    const active = page === "settings" ? settings : page === "schedule" ? schedule : page === "resources" ? resources : dashboard;
    if (active) {{
      active.classList.add("is-active");
    }}
  }}

  function updatePageLayout(page) {{
    const content = $("studyPageContent");
    if (!content) return;
    content.dataset.page = page;
    content.classList.toggle("is-centered-page", page === "dashboard");
  }}

  function showPage(page) {{
    const normalized = PAGE_FRAGMENT_MAP[page] ? page : "dashboard";
    currentPage = normalized;
    setNavActive(normalized);
    updatePageLayout(normalized);
    document.title = `${{normalized.charAt(0).toUpperCase() + normalized.slice(1)}} | Hanauta Study Track`;
    if (!window.htmx) return;
    window.htmx.ajax("GET", PAGE_FRAGMENT_MAP[normalized], {{
      target: "#studyPageContent",
      swap: "innerHTML"
    }});
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

  function isoDateKey(date) {{
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${{year}}-${{month}}-${{day}}`;
  }}

  function parseIsoDate(value) {{
    const [year, month, day] = String(value || "").split("-").map((part) => Number.parseInt(part || "0", 10));
    if (!year || !month || !day) return new Date();
    return new Date(year, month - 1, day, 12, 0, 0, 0);
  }}

  function addDays(date, amount) {{
    const next = new Date(date);
    next.setDate(next.getDate() + amount);
    return next;
  }}

  function startOfWeek(date) {{
    const next = new Date(date);
    const day = (next.getDay() + 6) % 7;
    next.setDate(next.getDate() - day);
    next.setHours(12, 0, 0, 0);
    return next;
  }}

  function minutesFromClock(value) {{
    const [hours, minutes] = String(value || "08:00").split(":");
    return (Number.parseInt(hours || "0", 10) * 60) + Number.parseInt(minutes || "0", 10);
  }}

  function blockEndClock(startTime, durationMinutes) {{
    const total = minutesFromClock(startTime) + Number(durationMinutes || 0);
    const hours = Math.floor(total / 60);
    const mins = total % 60;
    return `${{String(hours).padStart(2, "0")}}:${{String(mins).padStart(2, "0")}}`;
  }}

  function calendarRangeLabel() {{
    const anchor = new Date(scheduleAnchorDate);
    if (scheduleViewMode === "day") return anchor.toLocaleDateString([], {{ weekday: "long", month: "short", day: "numeric" }});
    if (scheduleViewMode === "week") {{
      const weekStart = startOfWeek(anchor);
      const weekEnd = addDays(weekStart, 6);
      return `${{weekStart.toLocaleDateString([], {{ month: "short", day: "numeric" }})}} - ${{weekEnd.toLocaleDateString([], {{ month: "short", day: "numeric", year: "numeric" }})}}`;
    }}
    if (scheduleViewMode === "month") return anchor.toLocaleDateString([], {{ month: "long", year: "numeric" }});
    return String(anchor.getFullYear());
  }}

  function virtualScheduleBlocks() {{
    const blocks = Array.isArray(studyState?.schedule_blocks) ? [...studyState.schedule_blocks] : [];
    const templates = Array.isArray(studyState?.schedule_templates) ? studyState.schedule_templates : [];
    const rangeStart = scheduleViewMode === "year"
      ? new Date(scheduleAnchorDate.getFullYear(), 0, 1)
      : scheduleViewMode === "month"
        ? new Date(scheduleAnchorDate.getFullYear(), scheduleAnchorDate.getMonth(), 1)
        : scheduleViewMode === "day"
          ? new Date(scheduleAnchorDate.getFullYear(), scheduleAnchorDate.getMonth(), scheduleAnchorDate.getDate())
          : startOfWeek(scheduleAnchorDate);
    const rangeEnd = scheduleViewMode === "year"
      ? new Date(scheduleAnchorDate.getFullYear(), 11, 31)
      : scheduleViewMode === "month"
        ? new Date(scheduleAnchorDate.getFullYear(), scheduleAnchorDate.getMonth() + 1, 0)
        : scheduleViewMode === "day"
          ? new Date(scheduleAnchorDate.getFullYear(), scheduleAnchorDate.getMonth(), scheduleAnchorDate.getDate())
          : addDays(startOfWeek(scheduleAnchorDate), 6);
    templates.forEach((template) => {{
      for (let date = new Date(rangeStart); date <= rangeEnd; date = addDays(date, 1)) {{
        const isDaily = String(template.recurrence || "weekly") === "daily";
        const matchesWeekday = Number(template.day_of_week || 0) === ((date.getDay() + 6) % 7);
        if (!isDaily && !matchesWeekday) continue;
        blocks.push({{
          id: `template-${{template.id}}-${{isoDateKey(date)}}`,
          template_id: template.id,
          resource_id: template.resource_id || "",
          item_id: template.item_id || "",
          title: template.title,
          category: template.category || (template.kind === "study_slot" ? "Study Slot" : "Life"),
          kind: template.kind === "study_slot" ? "study" : "life",
          date: isoDateKey(date),
          start_time: template.start_time || "08:00",
          end_time: blockEndClock(template.start_time || "08:00", template.duration_minutes || 60),
          duration_minutes: template.duration_minutes || 60,
          when: `${{date.toLocaleDateString([], {{ weekday: "long", month: "short", day: "numeric" }})}}, ${{template.start_time || "08:00"}} - ${{blockEndClock(template.start_time || "08:00", template.duration_minutes || 60)}}`,
          source: "recurring slot",
          notes: `Recurring ${{template.kind === "study_slot" ? "study slot" : "life slot"}}`,
          is_template: true,
        }});
      }}
    }});
    return blocks.sort((a, b) => `${{a.date}} ${{a.start_time}}`.localeCompare(`${{b.date}} ${{b.start_time}}`));
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
    const headline = $("objectiveHeadline");
    const meta = $("objectiveMeta");
    const progressText = $("objectiveProgressText");
    const progressBar = $("objectiveProgressBar");
    if (!headline || !progressText || !progressBar) return;
    const objective = studyState?.objective || null;
    if (!objective) {{
      headline.innerHTML = `Choose your next <br><span class="text-primary" id="objectiveSubject">study target</span>`;
      if (meta) meta.textContent = "Choose a study target to tie sessions, resources, and schedules together.";
      progressText.textContent = "0 / 0";
      progressBar.style.width = "0%";
      return;
    }}
    headline.innerHTML = `${{escapeHtml(objective.prefix || "Choose your next")}} <br><span class="text-primary" id="objectiveSubject">${{escapeHtml(objective.title || "study target")}}</span>`;
    if (meta) meta.textContent = objective.meta || "";
    progressText.textContent = objective.progress_text || "0 / 0";
    const percent = Math.max(0, Math.min(100, Number(objective.progress_percent || 0)));
    progressBar.style.width = `${{percent}}%`;
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
    const linkedLabel = task.linked_item_title
      ? `${{task.linked_item_title}}${{task.linked_resource_title ? ` • ${{task.linked_resource_title}}` : ""}}`
      : "";
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
          ${{linkedLabel ? `<p class="text-[11px] font-label text-on-surface-variant/60 mt-1">${{escapeHtml(linkedLabel)}}</p>` : ""}}
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
    const selectedClass = studyState?.selected_focus_class || null;
    const stopButton = $("studyStopButton");
    if (!label || !hint || !icon) return;
    if (stopButton) stopButton.classList.toggle("hidden", !session);
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
      hint.textContent = selectedClass ? `Counts toward ${{selectedClass.title}}` : `Focused on ${{task.title}}`;
      icon.textContent = "play_arrow";
    }} else {{
      label.textContent = "Add a Study Task";
      hint.textContent = "Build a small plan first";
      icon.textContent = "add";
    }}
  }}

  function focusClassLabel(option) {{
    if (!option) return "";
    return `${{option.title || "Untitled class"}} — ${{option.resource_title || "Resource"}}`;
  }}

  function focusClassOptions() {{
    return Array.isArray(studyState?.focus_class_options) ? studyState.focus_class_options : [];
  }}

  function filteredFocusClassOptions(query = focusClassQuery) {{
    const needle = String(query || "").trim().toLowerCase();
    const options = focusClassOptions();
    if (!needle) return options;
    return options.filter((option) => {{
      const title = String(option.title || "").toLowerCase();
      const resourceTitle = String(option.resource_title || "").toLowerCase();
      return title.includes(needle) || resourceTitle.includes(needle);
    }});
  }}

  function closeFocusClassMenu() {{
    focusClassOpen = false;
    focusClassActiveIndex = -1;
    $("sessionClassOptions")?.classList.add("hidden");
  }}

  function commitFocusClassSelection(option) {{
    if (!option) return;
    focusClassQuery = focusClassLabel(option);
    const input = $("sessionClassInput");
    const hidden = $("sessionClassValue");
    if (input) input.value = focusClassQuery;
    if (hidden) hidden.value = option.value || "";
    closeFocusClassMenu();
    bridge?.setSessionClass(String(option.resource_id || ""), String(option.item_id || ""));
  }}

  function renderFocusClassOptionsList(query = focusClassQuery) {{
    const menu = $("sessionClassOptions");
    if (!menu) return;
    const options = filteredFocusClassOptions(query);
    if (!focusClassOpen || !options.length) {{
      if (!options.length && focusClassOpen) {{
        menu.innerHTML = `<div class="study-combobox-empty">No classes matched that search yet.</div>`;
        menu.classList.remove("hidden");
      }} else {{
        menu.classList.add("hidden");
      }}
      return;
    }}
    if (focusClassActiveIndex >= options.length) focusClassActiveIndex = options.length - 1;
    menu.innerHTML = options.map((option, index) => {{
      const trackedMinutes = Number(option.tracked_minutes || 0);
      const trackedSessions = Number(option.tracked_sessions || 0);
      const trackedLabel = trackedMinutes > 0
        ? `${{trackedMinutes}} tracked min • ${{trackedSessions}} sessions`
        : "Ready to track";
      return `
        <button class="study-combobox-option${{index === focusClassActiveIndex ? " is-active" : ""}}" data-focus-class-value="${{escapeHtml(option.value)}}" type="button">
          <span class="study-combobox-option-title">${{escapeHtml(option.title || "Untitled class")}}</span>
          <span class="study-combobox-option-meta">${{escapeHtml(option.resource_title || "Resource")}} • ${{escapeHtml(trackedLabel)}}</span>
        </button>
      `;
    }}).join("");
    menu.classList.remove("hidden");
    menu.querySelectorAll("[data-focus-class-value]").forEach((node) => {{
      node.addEventListener("mousedown", (event) => {{
        event.preventDefault();
        const option = options.find((entry) => entry.value === (node.getAttribute("data-focus-class-value") || ""));
        if (option) commitFocusClassSelection(option);
      }});
    }});
  }}

  function renderFocusClassSelector() {{
    const input = $("sessionClassInput");
    const hidden = $("sessionClassValue");
    const meta = $("sessionClassMeta");
    const combobox = $("sessionClassCombobox");
    if (!input || !hidden || !meta || !combobox) return;
    const options = focusClassOptions();
    const selected = studyState?.selected_focus_class || null;
    if (!options.length) {{
      input.value = "";
      hidden.value = "";
      input.disabled = true;
      input.placeholder = "Add study resources first";
      combobox.classList.add("is-disabled");
      meta.textContent = "Import a resource with classes or chapters so Pomodoro time can be counted toward it.";
      closeFocusClassMenu();
      return;
    }}
    input.disabled = false;
    input.placeholder = "Search classes or courses";
    combobox.classList.remove("is-disabled");
    if (selected) {{
      hidden.value = selected.value || `${{selected.resource_id}}::${{selected.item_id}}`;
    }}
    if (document.activeElement !== input) {{
      input.value = selected ? focusClassLabel(selected) : "";
      focusClassQuery = input.value;
    }}
    if (selected) {{
      meta.textContent = `${{selected.tracked_minutes || 0}} tracked minutes across ${{selected.tracked_sessions || 0}} focus session${{selected.tracked_sessions === 1 ? "" : "s"}}.`;
    }} else {{
      meta.textContent = "Choose the class that should receive this focus time.";
    }}
    renderFocusClassOptionsList(input.value);
  }}

  function renderSettings() {{
    if (!settingsState) return;
    if ($("settingsThemeSummary")) $("settingsThemeSummary").textContent = settingsState.theme_summary || "System theme";
    if ($("settingsSyncSummary")) $("settingsSyncSummary").textContent = settingsState.sync_summary || "Local only";
    if ($("settingsFooterStatus")) $("settingsFooterStatus").textContent = settingsState.sync?.last_sync_at ? `Last sync ${{settingsState.sync.last_sync_at}}` : "Encrypted local state";
    if ($("caldavSyncSummary")) $("caldavSyncSummary").textContent = settingsState.caldav_summary || "Schedules can sync through Hanauta Settings independently from Study Tracker cloud sync.";
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
    if ($("jellyfinInstanceUrlInput")) $("jellyfinInstanceUrlInput").value = settingsState.jellyfin?.instance_url || "";
    if ($("jellyfinApiTokenInput")) $("jellyfinApiTokenInput").value = settingsState.jellyfin?.api_token || "";
    if ($("jellyfinStatusText")) $("jellyfinStatusText").textContent = settingsState.jellyfin?.last_status || "Jellyfin is not configured yet.";
    if ($("looseSingleLimitInput")) $("looseSingleLimitInput").value = String(settingsState.resource_policy?.loose_single_limit ?? 5);
    if ($("scheduleLooseSingleLimitInput")) $("scheduleLooseSingleLimitInput").value = String(settingsState.resource_policy?.schedule_loose_single_limit ?? 5);
    setToggleButton("notifyStudyBlocksButton", !!settingsState.notifications?.study_blocks, ["Enabled", "Disabled"]);
    setToggleButton("notifyLifeBlocksButton", !!settingsState.notifications?.life_blocks, ["Enabled", "Disabled"]);
    setToggleButton("notifyCaldavEventsButton", !!settingsState.notifications?.caldav_events, ["Enabled", "Disabled"]);
    setToggleButton("notifyResourcePlansButton", !!settingsState.notifications?.resource_plans, ["Enabled", "Disabled"]);
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

  function filteredResources() {{
    const items = Array.isArray(resourcesState?.resources) ? resourcesState.resources : [];
    if (resourceFilter === "all") return items;
    return items.filter((item) => {{
      const kind = String(item.kind || "").toLowerCase();
      const mediaKind = String(item.media_kind || "").toLowerCase();
      const provider = String(item.provider || "").toLowerCase();
      if (resourceFilter === "jellyfin") return kind === "jellyfin" || provider.includes("jellyfin");
      if (resourceFilter === "book") return kind === "book" || mediaKind === "book";
      if (resourceFilter === "audio") return kind === "audio" || mediaKind === "audiobook";
      return kind === resourceFilter || mediaKind === resourceFilter;
    }});
  }}

  function renderResourceDetail(resource) {{
    const empty = $("resourceDetailEmpty");
    const panel = $("resourceDetailPanel");
    if (!resource) {{
      if (empty) empty.classList.remove("hidden");
      if (panel) panel.classList.add("hidden");
      return;
    }}
    if (empty) empty.classList.add("hidden");
    if (panel) panel.classList.remove("hidden");
    if ($("resourceDetailKind")) $("resourceDetailKind").textContent = String(resource.kind_label || resource.kind || "resource").toUpperCase();
    if ($("resourceDetailTitle")) $("resourceDetailTitle").textContent = resource.title || "Resource";
    if ($("resourceDetailMeta")) $("resourceDetailMeta").textContent = `${{resource.provider || "Reference"}}${{resource.author ? ` • ${{resource.author}}` : ""}}`;
    if ($("resourceDetailSummary")) $("resourceDetailSummary").textContent = resource.summary || "No summary yet.";
    if ($("resourceDetailProgressText")) $("resourceDetailProgressText").textContent = `${{resource.done_items || 0}} / ${{resource.total_items || 0}} completed`;
    if ($("resourceOpenSourceButton")) $("resourceOpenSourceButton").dataset.resourceId = resource.id || "";
    if ($("resourceCreatePlanButton")) $("resourceCreatePlanButton").dataset.resourceId = resource.id || "";
    if ($("resourceToggleAllButton")) {{
      $("resourceToggleAllButton").dataset.resourceId = resource.id || "";
      $("resourceToggleAllButton").textContent = resource.done_items >= resource.total_items && resource.total_items > 0 ? "Reset All" : "Mark All Done";
    }}
    const isDocument = String(resource.kind || "").toLowerCase() === "document";
    if ($("resourceDocumentTracker")) $("resourceDocumentTracker").classList.toggle("hidden", !isDocument);
    if ($("resourceDocumentProgressText")) $("resourceDocumentProgressText").textContent = `${{resource.document_current_page || 0}} / ${{resource.document_total_pages || 0}} pages`;
    if ($("resourceDocumentPageInput")) {{
      $("resourceDocumentPageInput").value = String(resource.document_current_page || 0);
      $("resourceDocumentPageInput").max = String(resource.document_total_pages || 0);
      $("resourceDocumentPageInput").dataset.resourceId = resource.id || "";
    }}
    if ($("resourceDocumentOpenButton")) $("resourceDocumentOpenButton").dataset.resourceId = resource.id || "";
    if ($("resourceDocumentPrevButton")) $("resourceDocumentPrevButton").dataset.resourceId = resource.id || "";
    if ($("resourceDocumentNextButton")) $("resourceDocumentNextButton").dataset.resourceId = resource.id || "";
    const itemsNode = $("resourceItemsList");
    if (!itemsNode) return;
    itemsNode.classList.toggle("hidden", isDocument);
    if (isDocument) {{
      itemsNode.innerHTML = "";
      return;
    }}
    const items = Array.isArray(resource.items) ? resource.items : [];
    itemsNode.innerHTML = items.map((item) => {{
      const done = !!item.done;
      const itemType = item.kind || "item";
      const estimated = Number(item.duration_seconds || 0) > 0 ? formatMinutes(Math.max(1, Math.round(Number(item.duration_seconds || 0) / 60))).replace(" Today", "") : itemType;
      const tracked = Number(item.tracked_minutes || 0) > 0 ? `${{item.tracked_minutes}} tracked min • ${{item.tracked_sessions || 0}} sessions` : estimated;
      return `
        <button class="study-resource-item${{done ? " is-done" : ""}}" data-resource-id="${{escapeHtml(resource.id)}}" data-resource-item-id="${{escapeHtml(item.id || "")}}" type="button">
          <span class="study-resource-item-check">${{done ? "done" : "radio_button_unchecked"}}</span>
          <span class="study-resource-item-copy">
            <strong>${{escapeHtml(item.title || "Untitled item")}}</strong>
            <span>${{escapeHtml(tracked)}}</span>
          </span>
        </button>
      `;
    }}).join("");
    itemsNode.querySelectorAll(".study-resource-item").forEach((node) => {{
      node.addEventListener("click", () => {{
        bridge?.toggleResourceItem(node.dataset.resourceId || "", node.dataset.resourceItemId || "");
      }});
    }});
  }}

  function renderResources() {{
    if (!resourcesState) return;
    if ($("resourcesCountText")) $("resourcesCountText").textContent = String(resourcesState.summary?.resource_count || 0);
    if ($("resourcesHoursText")) $("resourcesHoursText").textContent = `${{resourcesState.summary?.tracked_hours || 0}}h`;
    if ($("resourcesCompletedText")) $("resourcesCompletedText").textContent = `${{resourcesState.summary?.completed_items || 0}} / ${{resourcesState.summary?.total_items || 0}}`;
    if ($("resourcesLooseSinglesText")) {{
      const limit = Number(resourcesState.summary?.loose_single_limit ?? 5);
      $("resourcesLooseSinglesText").textContent = `${{resourcesState.summary?.loose_single_count || 0}} / ${{limit < 0 ? "inf" : limit}}`;
    }}
    const importBusy = !!resourcesState.import?.busy;
    const importButton = $("resourceImportButton");
    const importInput = $("resourceUrlInput");
    const importStatus = $("resourceImportStatus");
    if (importButton) {{
      importButton.disabled = importBusy;
      importButton.classList.toggle("is-busy", importBusy);
      importButton.innerHTML = importBusy
        ? `<span class="study-spinner"></span><span>${{escapeHtml(resourcesState.import?.message || "Fetching resource...")}}</span>`
        : "Add Resource";
    }}
    if (importInput) importInput.disabled = importBusy;
    if (importStatus) importStatus.textContent = resourcesState.import?.message || "You can keep browsing while new sources are imported.";
    document.querySelectorAll("[data-resource-filter]").forEach((button) => {{
      button.classList.toggle("active", button.getAttribute("data-resource-filter") === resourceFilter);
    }});
    const grid = $("resourcesGrid");
    if (!grid) return;
    const resources = filteredResources();
    grid.innerHTML = resources.map((resource) => `
      <button class="study-resource-card${{selectedResourceId === resource.id ? " is-selected" : ""}}" data-resource-id="${{escapeHtml(resource.id)}}" type="button">
        <div class="study-resource-cover" style="${{resource.thumbnail_url ? `background-image:url('${{escapeHtml(resource.thumbnail_url)}}')` : ''}}"></div>
        <div class="study-resource-card-top">
          <span class="study-resource-type-badge">${{escapeHtml(String(resource.kind || "resource").toUpperCase())}}</span>
          <span class="study-resource-progress-badge">${{resource.progress_percent || 0}}%</span>
        </div>
        <h3 class="font-headline text-lg font-bold text-on-surface">${{escapeHtml(resource.title || "Untitled resource")}}</h3>
        <p class="study-muted-copy">${{escapeHtml(resource.provider || "")}}${{resource.author ? ` • ${{escapeHtml(resource.author)}}` : ""}}</p>
        <p class="study-resource-summary-copy">${{escapeHtml(resource.summary || "No summary yet.")}}</p>
        <div class="study-resource-meter">
          <div class="study-resource-meter-fill" style="width:${{resource.progress_percent || 0}}%"></div>
        </div>
        <div class="study-resource-card-foot">
          <span>${{String(resource.kind || "").toLowerCase() === "document" ? `${{resource.document_current_page || 0}} / ${{resource.document_total_pages || 0}} pages` : `${{resource.done_items || 0}} / ${{resource.total_items || 0}} items`}}</span>
          <span>${{escapeHtml(resource.duration_label || "Open")}}</span>
        </div>
      </button>
    `).join("");
    grid.querySelectorAll(".study-resource-card").forEach((node) => {{
      node.addEventListener("click", () => {{
        selectedResourceId = node.dataset.resourceId || "";
        renderResources();
      }});
    }});
    const selected = resources.find((resource) => resource.id === selectedResourceId) || resources[0] || null;
    if (!selected && selectedResourceId) selectedResourceId = "";
    renderResourceDetail(selected || null);
  }}

  function setSchedulePanelVisible(visible) {{
    setScheduleSidebarMode(visible ? "selection" : "empty");
  }}

  function scheduleBlockById(blockId) {{
    const blocks = Array.isArray(studyState?.schedule_blocks) ? studyState.schedule_blocks : [];
    return blocks.find((block) => String(block.id || "") === String(blockId || "")) || null;
  }}

  function scheduleTemplateById(templateId) {{
    const templates = Array.isArray(studyState?.schedule_templates) ? studyState.schedule_templates : [];
    return templates.find((template) => String(template.id || "") === String(templateId || "")) || null;
  }}

  function scheduleTargetValue(resourceId, itemId) {{
    const item = String(itemId || "").trim();
    return item ? `${{resourceId}}::${{item}}` : `${{resourceId}}::__resource__`;
  }}

  function scheduleTargetOptions() {{
    return Array.isArray(studyState?.schedule_target_options) ? studyState.schedule_target_options : [];
  }}

  function scheduleTargetElements(kind) {{
    return {{
      combobox: $(`schedule${{kind === "template" ? "Template" : "Block"}}TargetCombobox`),
      input: $(`schedule${{kind === "template" ? "Template" : "Block"}}TargetInput`),
      hidden: $(`schedule${{kind === "template" ? "Template" : "Block"}}TargetValue`),
      menu: $(`schedule${{kind === "template" ? "Template" : "Block"}}TargetOptions`),
    }};
  }}

  function scheduleTargetOptionByValue(value) {{
    return scheduleTargetOptions().find((option) => scheduleTargetValue(option.resource_id || "", option.item_id || "__resource__") === String(value || "")) || null;
  }}

  function scheduleTargetLabel(option) {{
    if (!option) return "";
    return option.label || option.title || "Study target";
  }}

  function scheduleTargetMeta(option) {{
    if (!option) return "";
    const typeLabel = option.type === "single" ? "Single item" : "Resource";
    const kindLabel = option.kind ? String(option.kind).replace(/_/g, " ") : "study";
    return `${{typeLabel}} • ${{kindLabel}}`;
  }}

  function filteredScheduleTargetOptions(kind) {{
    const query = String(scheduleTargetState[kind]?.query || "").trim().toLowerCase();
    const options = scheduleTargetOptions();
    if (!query) return options;
    return options.filter((option) => {{
      const label = String(scheduleTargetLabel(option)).toLowerCase();
      const kindLabel = String(option.kind || "").toLowerCase();
      return label.includes(query) || kindLabel.includes(query);
    }});
  }}

  function closeScheduleTargetMenu(kind) {{
    const state = scheduleTargetState[kind];
    if (!state) return;
    state.open = false;
    state.activeIndex = -1;
    scheduleTargetElements(kind).menu?.classList.add("hidden");
  }}

  function commitScheduleTargetSelection(kind, option) {{
    if (!option) return;
    const state = scheduleTargetState[kind];
    const elements = scheduleTargetElements(kind);
    const value = scheduleTargetValue(option.resource_id || "", option.item_id || "__resource__");
    state.query = scheduleTargetLabel(option);
    if (elements.input) elements.input.value = state.query;
    if (elements.hidden) elements.hidden.value = value;
    closeScheduleTargetMenu(kind);
    if (kind === "template") {{
      const kindSelect = $("scheduleTemplateKindSelect");
      const titleInput = $("scheduleTemplateTitleInput");
      if (kindSelect?.value === "study_slot" && titleInput && (!titleInput.value.trim() || !editingScheduleTemplateId)) {{
        titleInput.value = option.title || option.label || "Study Slot";
      }}
    }}
  }}

  function renderScheduleTargetOptionsList(kind, query = scheduleTargetState[kind]?.query || "") {{
    const state = scheduleTargetState[kind];
    const elements = scheduleTargetElements(kind);
    const menu = elements.menu;
    if (!state || !menu) return;
    const options = filteredScheduleTargetOptions(kind);
    if (!state.open || !options.length) {{
      if (!options.length && state.open) {{
        menu.innerHTML = `<div class="study-combobox-empty">No study targets matched that search yet.</div>`;
        menu.classList.remove("hidden");
      }} else {{
        menu.classList.add("hidden");
      }}
      return;
    }}
    if (state.activeIndex >= options.length) state.activeIndex = options.length - 1;
    menu.innerHTML = options.map((option, index) => {{
      const value = scheduleTargetValue(option.resource_id || "", option.item_id || "__resource__");
      return `
        <button class="study-combobox-option${{index === state.activeIndex ? " is-active" : ""}}" data-schedule-target-kind="${{kind}}" data-schedule-target-value="${{escapeHtml(value)}}" type="button">
          <span class="study-combobox-option-title">${{escapeHtml(option.title || option.label || "Study target")}}</span>
          <span class="study-combobox-option-meta">${{escapeHtml(scheduleTargetMeta(option))}}</span>
        </button>
      `;
    }}).join("");
    menu.classList.remove("hidden");
    menu.querySelectorAll("[data-schedule-target-value]").forEach((node) => {{
      node.addEventListener("mousedown", (event) => {{
        event.preventDefault();
        const option = scheduleTargetOptionByValue(node.getAttribute("data-schedule-target-value") || "");
        if (option) commitScheduleTargetSelection(kind, option);
      }});
    }});
  }}

  function renderScheduleTargetCombobox(kind, selectedValue = "") {{
    const state = scheduleTargetState[kind];
    const elements = scheduleTargetElements(kind);
    const options = scheduleTargetOptions();
    if (!state || !elements.input || !elements.hidden || !elements.combobox) return options;
    if (!options.length) {{
      elements.input.value = "";
      elements.hidden.value = "";
      elements.input.disabled = true;
      elements.input.placeholder = "Add study resources first";
      elements.combobox.classList.add("is-disabled");
      closeScheduleTargetMenu(kind);
      return options;
    }}
    elements.input.disabled = false;
    elements.input.placeholder = "Search resources, classes, or single items";
    elements.combobox.classList.remove("is-disabled");
    const chosenValue = selectedValue || elements.hidden.value || scheduleTargetValue(options[0].resource_id || "", options[0].item_id || "__resource__");
    const selectedOption = scheduleTargetOptionByValue(chosenValue) || options[0];
    elements.hidden.value = scheduleTargetValue(selectedOption.resource_id || "", selectedOption.item_id || "__resource__");
    if (document.activeElement !== elements.input) {{
      elements.input.value = scheduleTargetLabel(selectedOption);
      state.query = elements.input.value;
    }}
    renderScheduleTargetOptionsList(kind, state.query);
    return options;
  }}

  function syncScheduleTemplateTargetVisibility() {{
    const isStudySlot = ($("scheduleTemplateKindSelect")?.value || "study_slot") === "study_slot";
    const targetField = $("scheduleTemplateTargetField");
    if (targetField) targetField.style.display = isStudySlot ? "" : "none";
    if (!isStudySlot) {{
      closeScheduleTargetMenu("template");
    }} else {{
      renderScheduleTargetCombobox("template", $("scheduleTemplateTargetValue")?.value || "");
    }}
  }}

  function wireScheduleTargetCombobox(kind) {{
    const state = scheduleTargetState[kind];
    const elements = scheduleTargetElements(kind);
    const input = elements.input;
    if (!state || !input) return;
    input.addEventListener("focus", () => {{
      state.open = true;
      state.query = input.value || "";
      state.activeIndex = -1;
      renderScheduleTargetOptionsList(kind, state.query);
    }});
    input.addEventListener("input", () => {{
      state.open = true;
      state.query = input.value || "";
      state.activeIndex = 0;
      if (elements.hidden) elements.hidden.value = "";
      renderScheduleTargetOptionsList(kind, state.query);
    }});
    input.addEventListener("keydown", (event) => {{
      const options = filteredScheduleTargetOptions(kind);
      if (event.key === "ArrowDown") {{
        event.preventDefault();
        state.open = true;
        state.activeIndex = Math.min(options.length - 1, state.activeIndex + 1);
        renderScheduleTargetOptionsList(kind, input.value || "");
        return;
      }}
      if (event.key === "ArrowUp") {{
        event.preventDefault();
        state.open = true;
        state.activeIndex = Math.max(0, state.activeIndex - 1);
        renderScheduleTargetOptionsList(kind, input.value || "");
        return;
      }}
      if (event.key === "Enter") {{
        if (!state.open) return;
        event.preventDefault();
        const option = options[state.activeIndex] || options[0];
        if (option) commitScheduleTargetSelection(kind, option);
        return;
      }}
      if (event.key === "Escape") {{
        event.preventDefault();
        closeScheduleTargetMenu(kind);
      }}
    }});
  }}

  function setScheduleSidebarMode(mode) {{
    scheduleSidebarMode = mode || "empty";
    const visibility = {{
      empty: ["scheduleEmptyState"],
      selection: ["scheduleSelectionPanel"],
      "block-form": ["scheduleBlockFormPanel"],
      "template-form": ["scheduleTemplateFormPanel"],
    }};
    ["scheduleEmptyState", "scheduleSelectionPanel", "scheduleBlockFormPanel", "scheduleTemplateFormPanel"].forEach((id) => {{
      const node = $(id);
      if (!node) return;
      node.classList.toggle("hidden", !(visibility[scheduleSidebarMode] || []).includes(id));
    }});
  }}

  function scheduleNodeById(blockId) {{
    const nodes = Array.from(document.querySelectorAll("[data-schedule-id]"));
    return nodes.find((node) => (node.getAttribute("data-schedule-id") || "") === String(blockId || "")) || null;
  }}

  function updateScheduleFormStatus(message, kind = "block") {{
    const node = kind === "template" ? $("scheduleTemplateFormStatus") : $("scheduleBlockFormStatus");
    if (node) node.textContent = message;
  }}

  function openScheduleBlockForm(block = null) {{
    editingScheduleBlockId = block && !block.is_template ? String(block.id || "") : "";
    const targets = renderScheduleTargetCombobox(
      "block",
      block ? scheduleTargetValue(block.resource_id || "", block.item_id || "__resource__") : ""
    );
    const title = $("scheduleBlockFormTitle");
    const dateInput = $("scheduleBlockDateInput");
    const timeInput = $("scheduleBlockTimeInput");
    const durationInput = $("scheduleBlockDurationInput");
    const notesInput = $("scheduleBlockNotesInput");
    if (title) title.textContent = editingScheduleBlockId ? "Edit Study Block" : "Add Study Block";
    if (dateInput) dateInput.value = String(block?.date || isoDateKey(scheduleAnchorDate) || "");
    if (timeInput) timeInput.value = String(block?.start_time || "19:00");
    if (durationInput) durationInput.value = String(block?.duration_minutes || 60);
    if (notesInput) notesInput.value = String(block?.notes || "");
    if (!targets.length) {{
      updateScheduleFormStatus("Add a resource first, or raise the schedule single-item limit in Settings.", "block");
      setScheduleSidebarMode("block-form");
      return;
    }}
    updateScheduleFormStatus(
      editingScheduleBlockId
        ? "Update the time, target, or notes for this scheduled study block."
        : "Loose singles are limited by the rule in Settings. Larger resources are preferred.",
      "block"
    );
    setScheduleSidebarMode("block-form");
  }}

  function openScheduleTemplateForm(template = null) {{
    editingScheduleTemplateId = template ? String(template.id || "") : "";
    const titleNode = $("scheduleTemplateFormTitle");
    const titleInput = $("scheduleTemplateTitleInput");
    const kindSelect = $("scheduleTemplateKindSelect");
    const recurrenceSelect = $("scheduleTemplateRecurrenceSelect");
    const daySelect = $("scheduleTemplateDaySelect");
    const timeInput = $("scheduleTemplateTimeInput");
    const durationInput = $("scheduleTemplateDurationInput");
    const targetHidden = $("scheduleTemplateTargetValue");
    if (titleNode) titleNode.textContent = editingScheduleTemplateId ? "Edit Recurring Slot" : "Add Recurring Slot";
    if (titleInput) titleInput.value = String(template?.title || "");
    if (kindSelect) kindSelect.value = String(template?.kind || "study_slot");
    if (recurrenceSelect) recurrenceSelect.value = String(template?.recurrence || "weekly");
    if (daySelect) daySelect.value = String(template?.day_of_week ?? 0);
    if (timeInput) timeInput.value = String(template?.start_time || "19:00");
    if (durationInput) durationInput.value = String(template?.duration_minutes || 90);
    if (targetHidden) targetHidden.value = template ? scheduleTargetValue(template.resource_id || "", template.item_id || "__resource__") : "";
    renderScheduleTargetCombobox("template", targetHidden?.value || "");
    syncScheduleTemplateTargetVisibility();
    updateScheduleFormStatus(
      editingScheduleTemplateId
        ? "Adjust this recurring slot so plans and reminders stay aligned."
        : "Use life blocks for things like school, work, sleep, or commuting. Use study slots for resource plans.",
      "template"
    );
    setScheduleSidebarMode("template-form");
  }}

  function extractScheduleBlockPayload(node) {{
    if (!node) return null;
    return {{
      id: node.dataset.scheduleId || "",
      template_id: node.dataset.scheduleTemplateId || "",
      resource_id: node.dataset.scheduleResourceId || "",
      item_id: node.dataset.scheduleItemId || "",
      title: node.dataset.scheduleTitle || "Study Block",
      when: node.dataset.scheduleWhen || "",
      category: node.dataset.scheduleCategory || "General",
      description: node.dataset.scheduleDescription || "",
      notes: node.dataset.scheduleNotes || "",
      kind: node.dataset.scheduleKind || "study",
      date: node.dataset.scheduleDate || "",
      start_time: node.dataset.scheduleStartTime || "08:00",
      duration_minutes: Number.parseInt(node.dataset.scheduleDuration || "60", 10) || 60,
      is_template: node.dataset.scheduleIsTemplate === "true",
    }};
  }}

  function updateScheduleSelectionPanel(payload) {{
    if (!payload) {{
      selectedScheduleBlockId = "";
      if ($("scheduleDeleteBlockButton")) $("scheduleDeleteBlockButton").dataset.blockId = "";
      if ($("scheduleEditBlockButton")) {{
        $("scheduleEditBlockButton").dataset.blockId = "";
        $("scheduleEditBlockButton").dataset.templateId = "";
      }}
      setScheduleSidebarMode("empty");
      return;
    }}
    if ($("scheduleSelectedTitle")) $("scheduleSelectedTitle").textContent = payload.title || "Study Block";
    if ($("scheduleSelectedWhen")) $("scheduleSelectedWhen").textContent = payload.when || "";
    if ($("scheduleSelectedCategory")) $("scheduleSelectedCategory").textContent = String(payload.category || "General").toUpperCase();
    if ($("scheduleSelectedDescription")) $("scheduleSelectedDescription").textContent = payload.description || "";
    if ($("scheduleSelectedBadge")) $("scheduleSelectedBadge").textContent = payload.is_template ? "Recurring Slot" : "Selected Block";
    if ($("scheduleDeleteBlockButton")) {{
      $("scheduleDeleteBlockButton").dataset.blockId = payload.is_template ? "" : (payload.id || "");
      $("scheduleDeleteBlockButton").classList.toggle("hidden", !!payload.is_template);
    }}
    if ($("scheduleEditBlockButton")) {{
      $("scheduleEditBlockButton").dataset.blockId = payload.id || "";
      $("scheduleEditBlockButton").dataset.templateId = payload.template_id || "";
      $("scheduleEditBlockButton").textContent = payload.is_template ? "Edit Slot" : "Edit Block";
    }}
    setScheduleSidebarMode("selection");
  }}

  function selectScheduleBlock(block) {{
    if (!block) {{
      document.querySelectorAll("[data-schedule-id]").forEach((node) => node.classList.remove("is-selected"));
      updateScheduleSelectionPanel(null);
      return;
    }}
    selectedScheduleBlockId = block.dataset.scheduleId || "";
    document.querySelectorAll("[data-schedule-id]").forEach((node) => node.classList.toggle("is-selected", node === block));
    updateScheduleSelectionPanel(extractScheduleBlockPayload(block));
  }}

  function renderSchedule() {{
    const blocks = virtualScheduleBlocks();
    const templates = Array.isArray(studyState?.schedule_templates) ? studyState.schedule_templates : [];
    const targets = Array.isArray(studyState?.schedule_target_options) ? studyState.schedule_target_options : [];
    if ($("scheduleRangeLabel")) $("scheduleRangeLabel").textContent = calendarRangeLabel();
    setPillState("scheduleViewWeekButton", scheduleViewMode === "week");
    setPillState("scheduleViewDayButton", scheduleViewMode === "day");
    setPillState("scheduleViewMonthButton", scheduleViewMode === "month");
    setPillState("scheduleViewYearButton", scheduleViewMode === "year");
    if ($("scheduleBlocksCountText")) $("scheduleBlocksCountText").textContent = String(blocks.length);
    if ($("scheduleTemplatesCountText")) $("scheduleTemplatesCountText").textContent = String(templates.length);
    if ($("scheduleTargetsCountText")) $("scheduleTargetsCountText").textContent = String(targets.length);
    if ($("scheduleLooseSinglesText")) {{
      const limit = Number(settingsState?.resource_policy?.schedule_loose_single_limit ?? 5);
      const used = targets.filter((item) => item.type === "single").length;
      $("scheduleLooseSinglesText").textContent = `${{used}} / ${{limit < 0 ? "inf" : limit}}`;
    }}
    const viewport = $("scheduleCalendarViewport");
    if (viewport) {{
      const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      if (scheduleViewMode === "week" || scheduleViewMode === "day") {{
        const startHour = 8;
        const hourLabels = Array.from({{length: 14}}, (_, index) => `${{String(startHour + index).padStart(2, "0")}}:00`);
        const rangeStart = scheduleViewMode === "day" ? new Date(scheduleAnchorDate) : startOfWeek(scheduleAnchorDate);
        const days = scheduleViewMode === "day" ? [rangeStart] : Array.from({{length: 7}}, (_, index) => addDays(rangeStart, index));
        viewport.innerHTML = `
          <div class="study-calendar-${{scheduleViewMode}}">
            <div class="study-calendar-time-rail">
              <div class="study-calendar-time-head"></div>
              ${{hourLabels.map((label) => `<div class="study-calendar-time-cell">${{label}}</div>`).join("")}}
            </div>
            ${{days.map((day) => {{
              const dayKey = isoDateKey(day);
              const dayBlocks = blocks.filter((block) => block.date === dayKey);
              return `
                <div class="study-calendar-day-column">
                  <div class="study-calendar-day-head">${{scheduleViewMode === "day" ? day.toLocaleDateString([], {{ weekday: "long", month: "short", day: "numeric" }}) : `${{weekdays[(day.getDay() + 6) % 7]}} ${{day.getDate()}}`}}</div>
                  <div class="study-calendar-grid-body">
                    ${{dayBlocks.map((block) => {{
                      const top = Math.max(0, ((minutesFromClock(block.start_time || "08:00") - (startHour * 60)) / 60) * 64);
                      const height = Math.max(42, (Number(block.duration_minutes || 60) / 60) * 64);
                      const blockClass = `study-calendar-block${{block.kind === "life" ? " is-life" : ""}}${{block.is_template ? " is-template" : ""}}`;
                      return `
                        <button class="${{blockClass}}" style="top:${{top}}px;height:${{height}}px" data-schedule-id="${{escapeHtml(block.id)}}" data-schedule-template-id="${{escapeHtml(block.template_id || "")}}" data-schedule-resource-id="${{escapeHtml(block.resource_id || "")}}" data-schedule-item-id="${{escapeHtml(block.item_id || "")}}" data-schedule-date="${{escapeHtml(block.date || "")}}" data-schedule-start-time="${{escapeHtml(block.start_time || "08:00")}}" data-schedule-duration="${{escapeHtml(String(block.duration_minutes || 60))}}" data-schedule-kind="${{escapeHtml(block.kind || "study")}}" data-schedule-is-template="${{block.is_template ? "true" : "false"}}" data-schedule-title="${{escapeHtml(block.title)}}" data-schedule-when="${{escapeHtml(block.when || "")}}" data-schedule-category="${{escapeHtml(block.category || "General")}}" data-schedule-notes="${{escapeHtml(block.notes || "")}}" data-schedule-description="${{escapeHtml(block.notes || `${{block.kind}} block • source: ${{block.source || "manual"}}`)}}" type="button">
                          <span class="study-calendar-block-time">${{escapeHtml(block.start_time || "08:00")}} - ${{escapeHtml(block.end_time || blockEndClock(block.start_time || "08:00", block.duration_minutes || 60))}}</span>
                          <span class="study-calendar-block-title">${{escapeHtml(block.title || "Study Block")}}</span>
                          <span class="study-calendar-block-meta">${{escapeHtml(block.category || "General")}}</span>
                        </button>
                      `;
                    }}).join("")}}
                  </div>
                </div>
              `;
            }}).join("")}}
          </div>
        `;
      }} else if (scheduleViewMode === "month") {{
        const first = new Date(scheduleAnchorDate.getFullYear(), scheduleAnchorDate.getMonth(), 1);
        const firstCell = startOfWeek(first);
        const cells = Array.from({{length: 42}}, (_, index) => addDays(firstCell, index));
        viewport.innerHTML = `
          <div class="study-calendar-month">
            <div class="study-calendar-month-header">${{weekdays.map((label) => `<span>${{label}}</span>`).join("")}}</div>
            <div class="study-calendar-month-grid">
              ${{cells.map((day) => {{
                const dayKey = isoDateKey(day);
                const dayBlocks = blocks.filter((block) => block.date === dayKey).slice(0, 3);
                return `
                  <div class="study-calendar-month-cell">
                    <strong class="text-sm font-headline text-on-surface">${{day.getDate()}}</strong>
                    ${{dayBlocks.map((block) => `<button class="study-calendar-month-chip" data-schedule-id="${{escapeHtml(block.id)}}" data-schedule-template-id="${{escapeHtml(block.template_id || "")}}" data-schedule-resource-id="${{escapeHtml(block.resource_id || "")}}" data-schedule-item-id="${{escapeHtml(block.item_id || "")}}" data-schedule-date="${{escapeHtml(block.date || "")}}" data-schedule-start-time="${{escapeHtml(block.start_time || "08:00")}}" data-schedule-duration="${{escapeHtml(String(block.duration_minutes || 60))}}" data-schedule-kind="${{escapeHtml(block.kind || "study")}}" data-schedule-is-template="${{block.is_template ? "true" : "false"}}" data-schedule-title="${{escapeHtml(block.title)}}" data-schedule-when="${{escapeHtml(block.when || "")}}" data-schedule-category="${{escapeHtml(block.category || "General")}}" data-schedule-notes="${{escapeHtml(block.notes || "")}}" data-schedule-description="${{escapeHtml(block.notes || `${{block.kind}} block • source: ${{block.source || "manual"}}`)}}" type="button">${{escapeHtml(block.start_time || "08:00")}} • ${{escapeHtml(block.title || "Block")}}</button>`).join("")}}
                  </div>
                `;
              }}).join("")}}
            </div>
          </div>
        `;
      }} else {{
        const months = Array.from({{length: 12}}, (_, index) => index);
        viewport.innerHTML = `
          <div class="study-calendar-year">
            ${{months.map((monthIndex) => {{
              const monthBlocks = blocks.filter((block) => {{
                const date = parseIsoDate(block.date || "");
                return date.getFullYear() === scheduleAnchorDate.getFullYear() && date.getMonth() === monthIndex;
              }});
              const studyCount = monthBlocks.filter((block) => block.kind !== "life").length;
              return `
                <div class="study-calendar-year-month">
                  <h4>${{new Date(scheduleAnchorDate.getFullYear(), monthIndex, 1).toLocaleDateString([], {{ month: "long" }})}}</h4>
                  <p>${{monthBlocks.length}} total blocks</p>
                  <p>${{studyCount}} study blocks</p>
                  <p>${{monthBlocks.length - studyCount}} life or recurring slots</p>
                </div>
              `;
            }}).join("")}}
          </div>
        `;
      }}
      viewport.querySelectorAll("[data-schedule-id]").forEach((block) => {{
        block.addEventListener("click", () => selectScheduleBlock(block));
      }});
    }}
    const templatesList = $("scheduleTemplatesList");
    if (templatesList) {{
      templatesList.innerHTML = templates.map((template) => `
        <button class="study-schedule-row" data-template-id="${{escapeHtml(template.id)}}" type="button">
          <div class="study-schedule-row-copy">
            <strong>${{escapeHtml(template.title)}}</strong>
            <span>${{escapeHtml(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][Number(template.day_of_week || 0)] || "Mon")}} • ${{escapeHtml(template.start_time || "08:00")}} • ${{escapeHtml(String(template.duration_minutes || 60))}} min</span>
            <span>${{escapeHtml(template.kind || "life")}}${{template.notify ? " • notifications on" : ""}}</span>
          </div>
        </button>
      `).join("") || `<div class="study-combobox-empty">No recurring slots yet. Add work, school, sleep, commuting, or study windows.</div>`;
      templatesList.querySelectorAll("[data-template-id]").forEach((node) => {{
        node.addEventListener("click", () => {{
          const template = scheduleTemplateById(node.getAttribute("data-template-id") || "");
          openScheduleTemplateForm(template);
        }});
      }});
    }}
    if (scheduleSidebarMode === "block-form") {{
      renderScheduleTargetCombobox("block", $("scheduleBlockTargetValue")?.value || "");
    }} else if (scheduleSidebarMode === "template-form") {{
      renderScheduleTargetCombobox("template", $("scheduleTemplateTargetValue")?.value || "");
      syncScheduleTemplateTargetVisibility();
    }} else if (selectedScheduleBlockId) {{
      const selectedNode = scheduleNodeById(selectedScheduleBlockId);
      if (selectedNode) {{
        document.querySelectorAll("[data-schedule-id]").forEach((node) => node.classList.toggle("is-selected", node === selectedNode));
        updateScheduleSelectionPanel(extractScheduleBlockPayload(selectedNode));
      }} else {{
        updateScheduleSelectionPanel(null);
      }}
    }} else if (scheduleSidebarMode !== "template-form") {{
      setScheduleSidebarMode("empty");
    }}
  }}

  function wireScheduleActions() {{
    wireScheduleTargetCombobox("block");
    wireScheduleTargetCombobox("template");
    $("scheduleSelectionCloseButton")?.addEventListener("click", () => selectScheduleBlock(null));
    $("scheduleViewWeekButton")?.addEventListener("click", () => {{ scheduleViewMode = "week"; renderSchedule(); }});
    $("scheduleViewDayButton")?.addEventListener("click", () => {{ scheduleViewMode = "day"; renderSchedule(); }});
    $("scheduleViewMonthButton")?.addEventListener("click", () => {{ scheduleViewMode = "month"; renderSchedule(); }});
    $("scheduleViewYearButton")?.addEventListener("click", () => {{ scheduleViewMode = "year"; renderSchedule(); }});
    $("scheduleTodayButton")?.addEventListener("click", () => {{ scheduleAnchorDate = new Date(); renderSchedule(); }});
    $("schedulePrevRangeButton")?.addEventListener("click", () => {{
      scheduleAnchorDate = scheduleViewMode === "day" ? addDays(scheduleAnchorDate, -1)
        : scheduleViewMode === "week" ? addDays(scheduleAnchorDate, -7)
        : scheduleViewMode === "month" ? new Date(scheduleAnchorDate.getFullYear(), scheduleAnchorDate.getMonth() - 1, 1)
        : new Date(scheduleAnchorDate.getFullYear() - 1, 0, 1);
      renderSchedule();
    }});
    $("scheduleNextRangeButton")?.addEventListener("click", () => {{
      scheduleAnchorDate = scheduleViewMode === "day" ? addDays(scheduleAnchorDate, 1)
        : scheduleViewMode === "week" ? addDays(scheduleAnchorDate, 7)
        : scheduleViewMode === "month" ? new Date(scheduleAnchorDate.getFullYear(), scheduleAnchorDate.getMonth() + 1, 1)
        : new Date(scheduleAnchorDate.getFullYear() + 1, 0, 1);
      renderSchedule();
    }});
    $("scheduleDeleteBlockButton")?.addEventListener("click", () => {{
      const blockId = $("scheduleDeleteBlockButton")?.dataset.blockId || "";
      if (blockId) bridge?.deleteScheduleBlock(blockId);
    }});
    $("scheduleAddLifeTemplateButton")?.addEventListener("click", () => openScheduleTemplateForm(null));
    $("scheduleAddStudyBlockButton")?.addEventListener("click", () => openScheduleBlockForm(null));
    $("scheduleTemplateKindSelect")?.addEventListener("change", () => syncScheduleTemplateTargetVisibility());
    $("scheduleEditBlockButton")?.addEventListener("click", () => {{
      const templateId = $("scheduleEditBlockButton")?.dataset.templateId || "";
      if (templateId) {{
        openScheduleTemplateForm(scheduleTemplateById(templateId));
        return;
      }}
      const blockId = $("scheduleEditBlockButton")?.dataset.blockId || "";
      if (blockId) openScheduleBlockForm(scheduleBlockById(blockId));
    }});
    $("scheduleBlockFormCancelButton")?.addEventListener("click", () => {{
      if (selectedScheduleBlockId) {{
        const selectedNode = scheduleNodeById(selectedScheduleBlockId);
        if (selectedNode) {{
          selectScheduleBlock(selectedNode);
          return;
        }}
      }}
      setScheduleSidebarMode("empty");
    }});
    $("scheduleTemplateFormCancelButton")?.addEventListener("click", () => {{
      if (selectedScheduleBlockId) {{
        const selectedNode = scheduleNodeById(selectedScheduleBlockId);
        if (selectedNode) {{
          selectScheduleBlock(selectedNode);
          return;
        }}
      }}
      setScheduleSidebarMode("empty");
    }});
    $("scheduleBlockSaveButton")?.addEventListener("click", () => {{
      const targetValue = $("scheduleBlockTargetValue")?.value || "";
      const [resourceId, rawItemId] = targetValue.split("::");
      const itemId = rawItemId || "__resource__";
      const date = ($("scheduleBlockDateInput")?.value || "").trim();
      const startTime = ($("scheduleBlockTimeInput")?.value || "").trim();
      const duration = Number.parseInt($("scheduleBlockDurationInput")?.value || "60", 10) || 60;
      const notes = ($("scheduleBlockNotesInput")?.value || "").trim();
      if (!resourceId || !date || !startTime) {{
        updateScheduleFormStatus("Choose a target, date, and start time before saving.", "block");
        return;
      }}
      setScheduleSidebarMode(selectedScheduleBlockId ? "selection" : "empty");
      bridge?.createScheduleBlock(JSON.stringify({{
        id: editingScheduleBlockId || "",
        resource_id: resourceId,
        item_id: itemId,
        date,
        start_time: startTime,
        duration_minutes: duration,
        notes,
      }}));
    }});
    $("scheduleTemplateSaveButton")?.addEventListener("click", () => {{
      const title = ($("scheduleTemplateTitleInput")?.value || "").trim();
      const kind = ($("scheduleTemplateKindSelect")?.value || "study_slot").trim().toLowerCase();
      const targetValue = $("scheduleTemplateTargetValue")?.value || "";
      const [resourceId, rawItemId] = targetValue.split("::");
      const itemId = rawItemId || "__resource__";
      const recurrence = ($("scheduleTemplateRecurrenceSelect")?.value || "weekly").trim().toLowerCase();
      const dayOfWeek = Number.parseInt($("scheduleTemplateDaySelect")?.value || "0", 10) || 0;
      const startTime = ($("scheduleTemplateTimeInput")?.value || "").trim();
      const duration = Number.parseInt($("scheduleTemplateDurationInput")?.value || "90", 10) || 90;
      if ((kind === "study_slot" && !resourceId) || (!title && kind !== "study_slot") || !startTime) {{
        updateScheduleFormStatus(kind === "study_slot" ? "Pick a study target and start time before saving." : "Give the slot a title and start time before saving.", "template");
        return;
      }}
      setScheduleSidebarMode(selectedScheduleBlockId ? "selection" : "empty");
      bridge?.createScheduleTemplate(JSON.stringify({{
        id: editingScheduleTemplateId || "",
        title: title || (scheduleTargetOptionByValue(targetValue)?.title || "Study Slot"),
        category: kind === "study_slot" ? "Study Slot" : "Life",
        kind,
        resource_id: kind === "study_slot" ? resourceId : "",
        item_id: kind === "study_slot" ? itemId : "",
        recurrence,
        day_of_week: dayOfWeek,
        start_time: startTime,
        duration_minutes: duration,
      }}));
    }});
  }}

  function render() {{
    if (studyState) {{
      renderChips();
    }}
    if (currentPage === "dashboard" && studyState) {{
      renderObjective();
      renderInsights();
      renderAgenda();
      renderFocusClassSelector();
      renderFab();
    }}
    if (currentPage === "settings" && settingsState) {{
      renderSettings();
    }}
    if (currentPage === "resources" && resourcesState) {{
      renderResources();
    }}
    if (currentPage === "schedule" && studyState) {{
      renderSchedule();
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

  function collectJellyfinSettings() {{
    return {{
      instance_url: $("jellyfinInstanceUrlInput")?.value || "",
      api_token: $("jellyfinApiTokenInput")?.value || "",
    }};
  }}

  function collectResourcePolicySettings() {{
    return {{
      loose_single_limit: Number.parseInt($("looseSingleLimitInput")?.value || "5", 10),
      schedule_loose_single_limit: Number.parseInt($("scheduleLooseSingleLimitInput")?.value || "5", 10),
    }};
  }}

  function collectNotificationSettings() {{
    return {{
      study_blocks: !($("notifyStudyBlocksButton")?.classList.contains("off")),
      life_blocks: !($("notifyLifeBlocksButton")?.classList.contains("off")),
      caldav_events: !($("notifyCaldavEventsButton")?.classList.contains("off")),
      resource_plans: !($("notifyResourcePlansButton")?.classList.contains("off")),
    }};
  }}

  function wireNavigation() {{
    $("navDashboardButton")?.addEventListener("click", () => showPage("dashboard"));
    $("navResourcesButton")?.addEventListener("click", () => showPage("resources"));
    $("navScheduleButton")?.addEventListener("click", () => showPage("schedule"));
    $("navSettingsButton")?.addEventListener("click", () => showPage("settings"));
  }}

  function wireDashboardActions() {{
    $("studyFabButton")?.addEventListener("click", () => bridge?.startOrPauseSession());
    $("studyStopButton")?.addEventListener("click", () => bridge?.stopSession());
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
    const input = $("sessionClassInput");
    input?.addEventListener("focus", () => {{
      focusClassOpen = true;
      focusClassQuery = input.value || "";
      focusClassActiveIndex = -1;
      renderFocusClassOptionsList(focusClassQuery);
    }});
    input?.addEventListener("input", () => {{
      focusClassOpen = true;
      focusClassQuery = input.value || "";
      focusClassActiveIndex = 0;
      renderFocusClassOptionsList(focusClassQuery);
    }});
    input?.addEventListener("keydown", (event) => {{
      const options = filteredFocusClassOptions(input.value || "");
      if (event.key === "ArrowDown") {{
        event.preventDefault();
        focusClassOpen = true;
        focusClassActiveIndex = Math.min(options.length - 1, focusClassActiveIndex + 1);
        if (focusClassActiveIndex < 0 && options.length) focusClassActiveIndex = 0;
        renderFocusClassOptionsList(input.value || "");
      }} else if (event.key === "ArrowUp") {{
        event.preventDefault();
        focusClassOpen = true;
        focusClassActiveIndex = Math.max(0, focusClassActiveIndex - 1);
        renderFocusClassOptionsList(input.value || "");
      }} else if (event.key === "Enter") {{
        if (!focusClassOpen) return;
        event.preventDefault();
        const option = options[Math.max(0, focusClassActiveIndex)];
        if (option) commitFocusClassSelection(option);
      }} else if (event.key === "Escape") {{
        closeFocusClassMenu();
        if (studyState?.selected_focus_class) {{
          input.value = focusClassLabel(studyState.selected_focus_class);
          focusClassQuery = input.value;
        }}
      }}
    }});
    input?.addEventListener("blur", () => {{
      window.setTimeout(() => {{
        if (!document.activeElement || !($("sessionClassCombobox")?.contains(document.activeElement))) {{
          closeFocusClassMenu();
          if (!studyState?.selected_focus_class && !(input.value || "").trim()) {{
            focusClassQuery = "";
          }}
        }}
      }}, 120);
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
    ["notifyStudyBlocksButton", "notifyLifeBlocksButton", "notifyCaldavEventsButton", "notifyResourcePlansButton"].forEach((id) => {{
      $(id)?.addEventListener("click", () => setToggleButton(id, $(id)?.classList.contains("off"), ["Enabled", "Disabled"]));
    }});
    $("saveSyncSettingsButton")?.addEventListener("click", () => bridge?.saveSyncSettings(JSON.stringify(collectSyncSettings())));
    $("saveJellyfinSettingsButton")?.addEventListener("click", () => bridge?.saveJellyfinSettings(JSON.stringify(collectJellyfinSettings())));
    $("saveResourcePolicyButton")?.addEventListener("click", () => bridge?.saveResourcePolicy(JSON.stringify(collectResourcePolicySettings())));
    $("saveNotificationPrefsButton")?.addEventListener("click", () => bridge?.saveNotificationSettings(JSON.stringify(collectNotificationSettings())));
    $("syncNowButton")?.addEventListener("click", () => bridge?.syncNow());
    $("backupButton")?.addEventListener("click", () => bridge?.createBackup());
    $("exportButton")?.addEventListener("click", () => bridge?.exportJson());
    $("flushCacheButton")?.addEventListener("click", () => bridge?.flushCache());
  }}

  function wireResourceActions() {{
    $("resourceImportButton")?.addEventListener("click", () => {{
      const url = $("resourceUrlInput")?.value?.trim() || "";
      if (!url) return;
      bridge?.addResourceFromUrl(url);
      $("resourceUrlInput").value = "";
    }});
    $("resourceUrlInput")?.addEventListener("keydown", (event) => {{
      if (event.key === "Enter") {{
        event.preventDefault();
        $("resourceImportButton")?.click();
      }}
    }});
    document.querySelectorAll("[data-resource-filter]").forEach((button) => {{
      button.addEventListener("click", () => {{
        resourceFilter = button.getAttribute("data-resource-filter") || "all";
        renderResources();
      }});
    }});
    $("resourceOpenSourceButton")?.addEventListener("click", () => {{
      const id = $("resourceOpenSourceButton")?.dataset.resourceId || "";
      if (id) bridge?.openResourceSource(id);
    }});
    $("resourceToggleAllButton")?.addEventListener("click", () => {{
      const id = $("resourceToggleAllButton")?.dataset.resourceId || "";
      if (!id || !resourcesState) return;
      const resource = (resourcesState.resources || []).find((item) => item.id === id);
      if (!resource) return;
      if (String(resource.kind || "").toLowerCase() === "document") return;
      const markDone = !(resource.done_items >= resource.total_items && resource.total_items > 0);
      bridge?.setAllResourceItems(id, markDone);
    }});
    $("resourceCreatePlanButton")?.addEventListener("click", () => {{
      const id = $("resourceCreatePlanButton")?.dataset.resourceId || "";
      if (!id) return;
      const perDay = Number.parseInt(window.prompt("How many classes or items per day should this resource schedule automatically?", "1") || "1", 10) || 1;
      bridge?.createResourcePlan(id, perDay);
    }});
    $("resourceDocumentOpenButton")?.addEventListener("click", () => {{
      const id = $("resourceDocumentOpenButton")?.dataset.resourceId || "";
      if (id) bridge?.openResourceSource(id);
    }});
    $("resourceDocumentPrevButton")?.addEventListener("click", () => {{
      const input = $("resourceDocumentPageInput");
      const id = input?.dataset.resourceId || "";
      if (!id || !input) return;
      const nextValue = Math.max(0, Number.parseInt(input.value || "0", 10) - 1);
      bridge?.setDocumentPage(id, nextValue);
    }});
    $("resourceDocumentNextButton")?.addEventListener("click", () => {{
      const input = $("resourceDocumentPageInput");
      const id = input?.dataset.resourceId || "";
      if (!id || !input) return;
      const max = Number.parseInt(input.max || "0", 10) || 0;
      const nextValue = Math.min(max, Number.parseInt(input.value || "0", 10) + 1);
      bridge?.setDocumentPage(id, nextValue);
    }});
    $("resourceDocumentSetButton")?.addEventListener("click", () => {{
      const input = $("resourceDocumentPageInput");
      const id = input?.dataset.resourceId || "";
      if (!id || !input) return;
      bridge?.setDocumentPage(id, Number.parseInt(input.value || "0", 10) || 0);
    }});
  }}

  function bindCurrentPageActions() {{
    if (currentPage === "dashboard") wireDashboardActions();
    if (currentPage === "resources") wireResourceActions();
    if (currentPage === "schedule") wireScheduleActions();
    if (currentPage === "settings") wireSettingsActions();
  }}

  window.setStudyState = function (payloadJson) {{
    studyState = JSON.parse(payloadJson);
    render();
  }};

  window.setStudySettings = function (payloadJson) {{
    settingsState = JSON.parse(payloadJson);
    render();
  }};

  window.setStudyResources = function (payloadJson) {{
    resourcesState = JSON.parse(payloadJson);
    if (selectedResourceId && !(resourcesState.resources || []).some((item) => item.id === selectedResourceId)) {{
      selectedResourceId = "";
    }}
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
    setNavActive(currentPage);
    updatePageLayout(currentPage);
    wireNavigation();
    bindCurrentPageActions();
    document.addEventListener("mousedown", (event) => {{
      const combobox = $("sessionClassCombobox");
      if (combobox && combobox.contains(event.target)) return;
      closeFocusClassMenu();
      ["block", "template"].forEach((kind) => {{
        const targetCombobox = scheduleTargetElements(kind).combobox;
        if (targetCombobox && targetCombobox.contains(event.target)) return;
        closeScheduleTargetMenu(kind);
      }});
    }});
    document.body.addEventListener("htmx:afterSwap", (event) => {{
      const target = event.detail && event.detail.target;
      if (!target || target.id !== "studyPageContent") return;
      bindCurrentPageActions();
      render();
    }});
    new QWebChannel(qt.webChannelTransport, function (channel) {{
      bridge = channel.objects.studyBridge;
      if (bridge) bridge.requestBootstrap();
    }});
    window.showStudyPage = showPage;
  }});
}})();
</script>
"""


def build_html(page_name: str) -> str:
    if page_name == "dashboard":
        html_file = HTML_FILE
        page_label = "Overview"
    elif page_name == "resources":
        html_file = RESOURCES_HTML_FILE
        page_label = "Resources"
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
<button class="study-rail-button p-3 transition-all duration-300 scale-95 active:scale-90 group relative rounded-2xl" id="navResourcesButton" type="button">
<span class="material-symbols-outlined">menu_book</span>
<span class="study-shell-tooltip absolute left-full ml-4 px-2 py-1 text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Resources</span>
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
<div class="study-page-content flex-1 overflow-y-auto no-scrollbar relative z-10 pb-32" id="studyPageContent">
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
    sessionStopRequested = pyqtSignal()
    sessionClassRequested = pyqtSignal(str, str)
    navigateRequested = pyqtSignal(str)
    integrationToggleRequested = pyqtSignal(str, bool)
    openHanautaSettingsRequested = pyqtSignal(str)
    themeModeRequested = pyqtSignal(str)
    customThemeRequested = pyqtSignal(str)
    syncSettingsRequested = pyqtSignal(str)
    jellyfinSettingsRequested = pyqtSignal(str)
    resourcePolicySettingsRequested = pyqtSignal(str)
    notificationSettingsRequested = pyqtSignal(str)
    syncNowRequested = pyqtSignal()
    backupRequested = pyqtSignal()
    exportRequested = pyqtSignal()
    flushCacheRequested = pyqtSignal()
    resourceImportRequested = pyqtSignal(str)
    resourceItemToggleRequested = pyqtSignal(str, str)
    resourceToggleAllRequested = pyqtSignal(str, bool)
    resourceOpenRequested = pyqtSignal(str)
    documentPageRequested = pyqtSignal(str, int)
    scheduleTemplateRequested = pyqtSignal(str)
    scheduleBlockRequested = pyqtSignal(str)
    scheduleBlockDeleteRequested = pyqtSignal(str)
    resourcePlanRequested = pyqtSignal(str, int)

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

    @pyqtSlot()
    def stopSession(self) -> None:
        self.sessionStopRequested.emit()

    @pyqtSlot(str, str)
    def setSessionClass(self, resource_id: str, item_id: str) -> None:
        self.sessionClassRequested.emit(resource_id, item_id)

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

    @pyqtSlot(str)
    def saveJellyfinSettings(self, payload_json: str) -> None:
        self.jellyfinSettingsRequested.emit(payload_json)

    @pyqtSlot(str)
    def saveResourcePolicy(self, payload_json: str) -> None:
        self.resourcePolicySettingsRequested.emit(payload_json)

    @pyqtSlot(str)
    def saveNotificationSettings(self, payload_json: str) -> None:
        self.notificationSettingsRequested.emit(payload_json)

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

    @pyqtSlot(str)
    def addResourceFromUrl(self, url: str) -> None:
        self.resourceImportRequested.emit(url)

    @pyqtSlot(str, str)
    def toggleResourceItem(self, resource_id: str, item_id: str) -> None:
        self.resourceItemToggleRequested.emit(resource_id, item_id)

    @pyqtSlot(str, bool)
    def setAllResourceItems(self, resource_id: str, done: bool) -> None:
        self.resourceToggleAllRequested.emit(resource_id, done)

    @pyqtSlot(str)
    def openResourceSource(self, resource_id: str) -> None:
        self.resourceOpenRequested.emit(resource_id)

    @pyqtSlot(str, int)
    def setDocumentPage(self, resource_id: str, page: int) -> None:
        self.documentPageRequested.emit(resource_id, page)

    @pyqtSlot(str)
    def createScheduleTemplate(self, payload_json: str) -> None:
        self.scheduleTemplateRequested.emit(payload_json)

    @pyqtSlot(str)
    def createScheduleBlock(self, payload_json: str) -> None:
        self.scheduleBlockRequested.emit(payload_json)

    @pyqtSlot(str)
    def deleteScheduleBlock(self, block_id: str) -> None:
        self.scheduleBlockDeleteRequested.emit(block_id)

    @pyqtSlot(str, int)
    def createResourcePlan(self, resource_id: str, classes_per_day: int) -> None:
        self.resourcePlanRequested.emit(resource_id, classes_per_day)


class StudyTrackerWindow(QWidget):
    resourceImportFinished = pyqtSignal(bool, object, str)
    resourceImportStatusChanged = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        if not WEBENGINE_AVAILABLE:
            raise RuntimeError(f"QtWebEngine is unavailable: {WEBENGINE_ERROR}")
        self.state = load_state()
        self.current_page = "dashboard"
        self.theme = resolve_study_theme(self.state)
        self._theme_mtime = palette_mtime()
        self._page_ready = False
        self._resource_import_busy = False
        self._resource_import_message = ""

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
        self.bridge.sessionStopRequested.connect(self.stop_session)
        self.bridge.sessionClassRequested.connect(self.set_session_class)
        self.bridge.navigateRequested.connect(self.navigate_to)
        self.bridge.integrationToggleRequested.connect(self.set_integration_enabled)
        self.bridge.openHanautaSettingsRequested.connect(self.open_hanauta_settings)
        self.bridge.themeModeRequested.connect(self.set_theme_mode)
        self.bridge.customThemeRequested.connect(self.set_custom_theme)
        self.bridge.syncSettingsRequested.connect(self.save_sync_settings)
        self.bridge.jellyfinSettingsRequested.connect(self.save_jellyfin_settings)
        self.bridge.resourcePolicySettingsRequested.connect(self.save_resource_policy)
        self.bridge.notificationSettingsRequested.connect(self.save_notification_settings)
        self.bridge.syncNowRequested.connect(self.sync_now)
        self.bridge.backupRequested.connect(self.create_backup)
        self.bridge.exportRequested.connect(self.export_json)
        self.bridge.flushCacheRequested.connect(self.flush_cache)
        self.bridge.resourceImportRequested.connect(self.add_resource_from_url)
        self.bridge.resourceItemToggleRequested.connect(self.toggle_resource_item)
        self.bridge.resourceToggleAllRequested.connect(self.set_all_resource_items)
        self.bridge.resourceOpenRequested.connect(self.open_resource_source)
        self.bridge.documentPageRequested.connect(self.set_document_page)
        self.bridge.scheduleTemplateRequested.connect(self.create_schedule_template)
        self.bridge.scheduleBlockRequested.connect(self.create_schedule_block)
        self.bridge.scheduleBlockDeleteRequested.connect(self.delete_schedule_block)
        self.bridge.resourcePlanRequested.connect(self.create_resource_plan)
        self.resourceImportFinished.connect(self._finish_resource_import)
        self.resourceImportStatusChanged.connect(self._update_resource_import_status)

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
            self.push_resources()
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

    def push_resources(self) -> None:
        payload_map = build_resources_payload(self.state)
        payload_map["import"] = {
            "busy": self._resource_import_busy,
            "message": self._resource_import_message,
        }
        payload = json.dumps(payload_map)
        self._run_js(f"window.setStudyResources({json.dumps(payload)});")

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
        task = task_by_id(self.state, task_id)
        if isinstance(task, dict):
            linked_resource_id = str(task.get("linked_resource_id", "") or "")
            linked_item_id = str(task.get("linked_item_id", "") or "")
            if linked_resource_id and linked_item_id:
                self.state["selected_focus_resource_id"] = linked_resource_id
                self.state["selected_focus_item_id"] = linked_item_id
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

    def set_session_class(self, resource_id: str, item_id: str) -> None:
        resource, item = resource_item_by_id(self.state, resource_id, item_id)
        if not isinstance(resource, dict) or not isinstance(item, dict):
            return
        self.state["selected_focus_resource_id"] = str(resource_id)
        self.state["selected_focus_item_id"] = str(item_id)
        linked_task = find_or_create_task_for_focus_target(self.state, resource, item)
        for task in self.state.get("tasks", []):
            if isinstance(task, dict):
                task["active"] = str(task.get("id", "")) == str(linked_task.get("id", ""))
        session = self.state.get("active_session")
        if isinstance(session, dict):
            session["resource_id"] = str(resource_id)
            session["item_id"] = str(item_id)
            session["task_id"] = str(linked_task.get("id", "") or "")
        self._save()
        self.push_state()

    def _commit_resources(self, notification: str | None = None) -> None:
        self._save()
        self.push_resources()
        self.push_state()
        if notification:
            notify("Study Resources", notification)
        if bool(self.state.get("preferences", {}).get("sync", {}).get("auto_sync", False)):
            self.sync_now()

    def _jellyfin_settings(self) -> dict[str, Any]:
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            raise RuntimeError("Study tracker preferences are unavailable.")
        jellyfin = preferences.setdefault("jellyfin", {})
        if not isinstance(jellyfin, dict):
            raise RuntimeError("Jellyfin settings are unavailable.")
        jellyfin["instance_url"] = str(jellyfin.get("instance_url", "") or "").strip().rstrip("/")
        jellyfin["api_token"] = str(jellyfin.get("api_token", "") or "").strip()
        jellyfin["user_id"] = str(jellyfin.get("user_id", "") or "").strip()
        jellyfin["last_status"] = str(jellyfin.get("last_status", "Jellyfin is not configured yet.") or "Jellyfin is not configured yet.")
        return jellyfin

    def _looks_like_jellyfin_url(self, source_url: str) -> bool:
        parsed = urlparse(source_url)
        if not parsed.scheme or not parsed.netloc:
            return False
        configured_base = str(self._jellyfin_settings().get("instance_url", "") or "").strip().rstrip("/")
        candidate_base = jellyfin_url_base(source_url)
        if configured_base and candidate_base and candidate_base.lower() == configured_base.lower():
            return True
        payload = f"{parsed.path}?{parsed.query}#{parsed.fragment}".lower()
        return "/web/" in payload or "/items/" in payload or "details?id=" in payload or "itemid=" in payload

    def _jellyfin_headers(self) -> dict[str, str]:
        if requests is None:
            raise RuntimeError("Python requests is unavailable.")
        jellyfin = self._jellyfin_settings()
        base_url = str(jellyfin.get("instance_url", "") or "").strip().rstrip("/")
        token = str(jellyfin.get("api_token", "") or "").strip()
        if not base_url or not token:
            raise RuntimeError("Set the Jellyfin instance URL and API token in Study Tracker settings first.")
        return {
            "Accept": "application/json",
            "X-Emby-Token": token,
            "X-Emby-Client": "Hanauta Study Track",
            "X-Emby-Device-Name": "Hanauta Study Track",
            "X-Emby-Device-Id": "hanauta-study-track",
        }

    def _jellyfin_request_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        jellyfin = self._jellyfin_settings()
        base_url = str(jellyfin.get("instance_url", "") or "").strip().rstrip("/")
        response = requests.get(f"{base_url}{path}", headers=self._jellyfin_headers(), params=params, timeout=20)
        if response.status_code in {401, 403}:
            raise RuntimeError("Jellyfin authentication failed. Check the API token.")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected Jellyfin response.")
        return payload

    def _jellyfin_primary_image(self, item_id: str) -> str:
        jellyfin = self._jellyfin_settings()
        base_url = str(jellyfin.get("instance_url", "") or "").strip().rstrip("/")
        try:
            response = requests.get(
                f"{base_url}/Items/{quote(item_id)}/Images/Primary",
                headers=self._jellyfin_headers(),
                timeout=20,
            )
            if response.ok and response.content:
                return data_uri_for_bytes(response.content, response.headers.get("Content-Type", "image/jpeg"))
        except Exception:
            pass
        return ""

    def _jellyfin_user_id(self) -> str:
        jellyfin = self._jellyfin_settings()
        cached = str(jellyfin.get("user_id", "") or "").strip()
        if cached:
            return cached
        payload = self._jellyfin_request_json("/Users/Me")
        user_id = str(payload.get("Id", "") or "").strip()
        if not user_id:
            raise RuntimeError("Jellyfin did not return a usable user id.")
        jellyfin["user_id"] = user_id
        self._save()
        return user_id

    def _jellyfin_web_url(self, item_id: str) -> str:
        base_url = str(self._jellyfin_settings().get("instance_url", "") or "").strip().rstrip("/")
        return f"{base_url}/web/#/details?id={quote(item_id)}"

    def _jellyfin_runtime_seconds(self, payload: dict[str, Any]) -> int:
        ticks = int(payload.get("RunTimeTicks", 0) or 0)
        return max(0, ticks // 10_000_000)

    def _jellyfin_author(self, payload: dict[str, Any]) -> str:
        for key in ("SeriesName", "AlbumArtist", "Author"):
            value = str(payload.get(key, "") or "").strip()
            if value:
                return value
        artists = payload.get("Artists", [])
        if isinstance(artists, list):
            for artist in artists:
                label = str(artist or "").strip()
                if label:
                    return label
        people = payload.get("People", [])
        if isinstance(people, list):
            for person in people:
                if isinstance(person, dict):
                    name = str(person.get("Name", "") or "").strip()
                    if name:
                        return name
        return "Jellyfin"

    def _jellyfin_child_items(self, user_id: str, parent_id: str, include_types: list[str] | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "ParentId": parent_id,
            "UserId": user_id,
            "Recursive": "true",
            "SortBy": "ParentIndexNumber,IndexNumber,SortName",
            "Fields": "Overview,RunTimeTicks",
        }
        if include_types:
            params["IncludeItemTypes"] = ",".join(include_types)
        payload = self._jellyfin_request_json(f"/Users/{quote(user_id)}/Items", params=params)
        items = payload.get("Items", [])
        return [item for item in items if isinstance(item, dict)]

    def _jellyfin_items_to_resource_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        resource_items: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            item_id = str(item.get("Id", "") or "").strip()
            title = str(item.get("Name", f"Class {index}") or f"Class {index}")
            runtime_seconds = self._jellyfin_runtime_seconds(item)
            item_type = str(item.get("Type", "lesson") or "lesson").strip().lower()
            resource_items.append(
                make_resource_item(
                    title,
                    duration_seconds=runtime_seconds,
                    position=index,
                    kind="lesson" if item_type in {"episode", "video", "movie"} else item_type,
                    external_url=self._jellyfin_web_url(item_id) if item_id else "",
                    notes=str(item.get("Overview", "") or "").strip()[:280],
                )
            )
        return resource_items

    def _jellyfin_resource_from_item(self, item: dict[str, Any], *, user_id: str) -> list[dict[str, Any]]:
        item_id = str(item.get("Id", "") or "").strip()
        if not item_id:
            raise RuntimeError("The Jellyfin item did not include an id.")
        item_type = str(item.get("Type", "") or "").strip().lower()
        title = str(item.get("Name", "Jellyfin item") or "Jellyfin item")
        author = self._jellyfin_author(item)
        summary = str(item.get("Overview", "") or "").strip()[:280]
        thumbnail = self._jellyfin_primary_image(item_id)
        duration_seconds = self._jellyfin_runtime_seconds(item)
        media_kind = {
            "series": "show",
            "movie": "video",
            "video": "video",
            "episode": "video",
            "audiobook": "audiobook",
            "book": "book",
            "playlist": "playlist",
        }.get(item_type, item_type or "resource")
        resource_kind = "jellyfin"
        if media_kind == "book":
            resource_kind = "book"
        elif media_kind == "audiobook":
            resource_kind = "audio"
        resource_items: list[dict[str, Any]] = []
        if item_type == "series":
            children = self._jellyfin_child_items(user_id, item_id, ["Episode"])
            resource_items = self._jellyfin_items_to_resource_items(children)
            duration_seconds = sum(int(entry.get("duration_seconds", 0) or 0) for entry in resource_items)
        elif item_type == "playlist":
            children = self._jellyfin_child_items(user_id, item_id, None)
            resource_items = self._jellyfin_items_to_resource_items(children)
            duration_seconds = sum(int(entry.get("duration_seconds", 0) or 0) for entry in resource_items)
        if not resource_items:
            fallback_kind = "reading" if media_kind == "book" else "lesson" if media_kind in {"show", "playlist"} else "video" if media_kind == "video" else "audio"
            resource_items = [
                make_resource_item(
                    title,
                    duration_seconds=duration_seconds,
                    position=1,
                    kind=fallback_kind,
                    external_url=self._jellyfin_web_url(item_id),
                    notes=summary,
                )
            ]
        resource = make_resource(
            title,
            kind=resource_kind,
            provider=f"Jellyfin ({media_kind.title()})",
            source_url=self._jellyfin_web_url(item_id),
            author=author,
            summary=summary,
            thumbnail_url=thumbnail or generated_document_cover(title, media_kind[:4].upper() or "JF"),
            tags=slug_tags(title, author, media_kind, "jellyfin"),
            items=resource_items,
            duration_seconds=duration_seconds,
        )
        resource["media_kind"] = media_kind
        resource["kind_label"] = media_kind
        resource["source_id"] = item_id
        return [resource]

    def _jellyfin_resources_from_url(self, source_url: str) -> list[dict[str, Any]]:
        item_id = extract_jellyfin_item_id(source_url)
        if not item_id:
            raise RuntimeError("Paste a Jellyfin item URL that includes an item id.")
        configured_base = str(self._jellyfin_settings().get("instance_url", "") or "").strip().rstrip("/")
        candidate_base = jellyfin_url_base(source_url)
        if configured_base and candidate_base and candidate_base.lower() != configured_base.lower():
            raise RuntimeError("That Jellyfin URL does not match the configured Jellyfin instance.")
        self.resourceImportStatusChanged.emit("Connecting to Jellyfin...")
        user_id = self._jellyfin_user_id()
        self.resourceImportStatusChanged.emit("Reading Jellyfin item metadata...")
        item = self._jellyfin_request_json(
            f"/Users/{quote(user_id)}/Items/{quote(item_id)}",
            params={"Fields": "Overview,RunTimeTicks,People"},
        )
        return self._jellyfin_resource_from_item(item, user_id=user_id)

    def _youtube_resources_from_url(self, url: str) -> list[dict[str, Any]]:
        if YoutubeDL is None:
            raise RuntimeError("yt-dlp is unavailable in the current environment.")
        with YoutubeDL({"quiet": True, "extract_flat": False, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = info.get("entries") if isinstance(info, dict) else None
        if isinstance(entries, list) and entries:
            resources: list[dict[str, Any]] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                resources.extend(self._youtube_resources_from_entry(entry))
            return resources
        if isinstance(info, dict):
            return self._youtube_resources_from_entry(info)
        raise RuntimeError("Unable to read YouTube metadata.")

    def _youtube_resources_from_entry(self, info: dict[str, Any]) -> list[dict[str, Any]]:
        if info.get("_type") == "playlist" and isinstance(info.get("entries"), list):
            resources: list[dict[str, Any]] = []
            for entry in info["entries"]:
                if isinstance(entry, dict):
                    resources.extend(self._youtube_resources_from_entry(entry))
            return resources
        title = str(info.get("title", "YouTube resource") or "YouTube resource")
        uploader = str(info.get("uploader") or info.get("channel") or "YouTube")
        webpage_url = str(info.get("webpage_url") or info.get("original_url") or "")
        duration_seconds = max(0, int(info.get("duration", 0) or 0))
        chapters = info.get("chapters") if isinstance(info.get("chapters"), list) else []
        items: list[dict[str, Any]] = []
        if chapters:
            for index, chapter in enumerate(chapters, start=1):
                if not isinstance(chapter, dict):
                    continue
                start_time = max(0, int(chapter.get("start_time", 0) or 0))
                end_time = max(start_time, int(chapter.get("end_time", start_time) or start_time))
                items.append(
                    make_resource_item(
                        str(chapter.get("title", f"Chapter {index}") or f"Chapter {index}"),
                        duration_seconds=max(0, end_time - start_time),
                        position=index,
                        kind="chapter",
                        external_url=f"{webpage_url}&t={start_time}s" if webpage_url and "?" in webpage_url else webpage_url,
                    )
                )
        if not items:
            items = [make_resource_item(title, duration_seconds=duration_seconds, position=1, kind="video", external_url=webpage_url)]
        return [
            make_resource(
                title,
                kind="youtube",
                provider="YouTube",
                source_url=webpage_url,
                author=uploader,
                summary=str(info.get("description", "") or "")[:280],
                thumbnail_url=str(info.get("thumbnail", "") or ""),
                tags=slug_tags(title, uploader),
                items=items,
                duration_seconds=duration_seconds,
            )
        ]

    def _document_cover_from_pdf(self, path: Path) -> str:
        with tempfile.TemporaryDirectory(prefix="hanauta-doc-cover-") as tmpdir:
            target = Path(tmpdir) / "cover"
            subprocess.run(
                ["pdftoppm", "-f", "1", "-singlefile", "-png", str(path), str(target)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            png_path = target.with_suffix(".png")
            if png_path.exists():
                return data_uri_for_bytes(png_path.read_bytes(), "image/png")
        return generated_document_cover(path.stem, path.suffix)

    def _pdf_document_resource(self, path: Path) -> dict[str, Any]:
        output = subprocess.check_output(["pdfinfo", str(path)], text=True, stderr=subprocess.DEVNULL)
        match = re.search(r"^Pages:\s+(\d+)", output, re.MULTILINE)
        page_count = max(1, int(match.group(1))) if match else 1
        cover = self._document_cover_from_pdf(path)
        return make_resource(
            path.stem,
            kind="document",
            provider=path.suffix.upper().lstrip("."),
            source_url=path.resolve().as_uri(),
            summary=f"Track reading progress for {path.name}.",
            thumbnail_url=cover,
            tags=slug_tags(path.stem, path.suffix),
            items=[],
        ) | {"document_total_pages": page_count, "document_current_page": 0, "document_path": str(path)}

    def _document_from_zip_based_file(self, path: Path) -> dict[str, Any]:
        cover = generated_document_cover(path.stem, path.suffix)
        page_count = 1
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            text_payload = ""
            if path.suffix.lower() == ".epub":
                container = ET.fromstring(archive.read("META-INF/container.xml"))
                rootfile = container.find(".//{*}rootfile")
                if rootfile is not None:
                    opf_path = rootfile.attrib.get("full-path", "")
                    opf_dir = str(Path(opf_path).parent)
                    opf = ET.fromstring(archive.read(opf_path))
                    manifest = {}
                    for item in opf.findall(".//{*}manifest/{*}item"):
                        manifest[item.attrib.get("id", "")] = item.attrib
                    cover_id = ""
                    for meta in opf.findall(".//{*}metadata/{*}meta"):
                        if meta.attrib.get("name") == "cover":
                            cover_id = meta.attrib.get("content", "")
                    if cover_id and cover_id in manifest:
                        href = manifest[cover_id].get("href", "")
                        cover_path = str((Path(opf_dir) / href).as_posix()).lstrip("./")
                        if cover_path in names:
                            mime_type = manifest[cover_id].get("media-type", "image/jpeg")
                            cover = data_uri_for_bytes(archive.read(cover_path), mime_type)
                    spine_ids = [item.attrib.get("idref", "") for item in opf.findall(".//{*}spine/{*}itemref")]
                    for spine_id in spine_ids:
                        href = manifest.get(spine_id, {}).get("href", "")
                        spine_path = str((Path(opf_dir) / href).as_posix()).lstrip("./")
                        if spine_path in names:
                            text_payload += " " + re.sub(r"<[^>]+>", " ", archive.read(spine_path).decode("utf-8", errors="ignore"))
            elif path.suffix.lower() == ".docx":
                if "docProps/thumbnail.jpeg" in names:
                    cover = data_uri_for_bytes(archive.read("docProps/thumbnail.jpeg"), "image/jpeg")
                if "word/document.xml" in names:
                    text_payload = re.sub(r"<[^>]+>", " ", archive.read("word/document.xml").decode("utf-8", errors="ignore"))
            elif path.suffix.lower() == ".odt":
                if "Thumbnails/thumbnail.png" in names:
                    cover = data_uri_for_bytes(archive.read("Thumbnails/thumbnail.png"), "image/png")
                if "content.xml" in names:
                    text_payload = re.sub(r"<[^>]+>", " ", archive.read("content.xml").decode("utf-8", errors="ignore"))
            page_count = estimate_pages_from_text(text_payload)
        return make_resource(
            path.stem,
            kind="document",
            provider=path.suffix.upper().lstrip("."),
            source_url=path.resolve().as_uri(),
            summary=f"Track reading progress for {path.name}.",
            thumbnail_url=cover,
            tags=slug_tags(path.stem, path.suffix),
            items=[],
        ) | {"document_total_pages": page_count, "document_current_page": 0, "document_path": str(path)}

    def _document_from_libreoffice(self, path: Path) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="hanauta-doc-pdf-") as tmpdir:
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, str(path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            converted = Path(tmpdir) / f"{path.stem}.pdf"
            if not converted.exists():
                raise RuntimeError("LibreOffice did not generate a PDF preview.")
            resource = self._pdf_document_resource(converted)
            resource["title"] = path.stem
            resource["provider"] = path.suffix.upper().lstrip(".")
            resource["source_url"] = path.resolve().as_uri()
            resource["document_path"] = str(path)
            return resource

    def _generic_document_resource(self, path: Path) -> dict[str, Any]:
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            text = path.stem
        page_count = estimate_pages_from_text(text)
        return make_resource(
            path.stem,
            kind="document",
            provider=path.suffix.upper().lstrip("."),
            source_url=path.resolve().as_uri(),
            summary=f"Track reading progress for {path.name}.",
            thumbnail_url=generated_document_cover(path.stem, path.suffix),
            tags=slug_tags(path.stem, path.suffix),
            items=[],
        ) | {"document_total_pages": page_count, "document_current_page": 0, "document_path": str(path)}

    def _document_resource_from_reference(self, value: str) -> list[dict[str, Any]]:
        parsed = urlparse(value)
        document_path = Path(unquote(parsed.path) if parsed.scheme == "file" else os.path.expanduser(value)).expanduser().resolve()
        if not document_path.exists():
            raise RuntimeError("Document path does not exist.")
        suffix = document_path.suffix.lower()
        if suffix == ".pdf":
            resource = self._pdf_document_resource(document_path)
        elif suffix in {".epub", ".docx", ".odt"}:
            resource = self._document_from_zip_based_file(document_path)
        elif suffix == ".doc":
            resource = self._document_from_libreoffice(document_path)
        else:
            resource = self._generic_document_resource(document_path)
        return [resource]

    def _fetch_invidious_instances(self) -> list[str]:
        candidates: list[str] = []
        if requests is not None:
            try:
                response = requests.get("https://api.invidious.io/instances.json", timeout=20)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, list) and item:
                            host = str(item[0] or "").strip()
                            if host:
                                candidates.append(f"https://{host}")
            except Exception:
                pass
            if not candidates:
                try:
                    response = requests.get("https://docs.invidious.io/instances/", timeout=20)
                    response.raise_for_status()
                    html = response.text
                    for host in re.findall(r'https://([a-zA-Z0-9.-]+)', html):
                        if host not in {"docs.invidious.io", "api.invidious.io"}:
                            candidates.append(f"https://{host}")
                except Exception:
                    pass
        deduped: list[str] = []
        for candidate in candidates:
            if candidate not in deduped:
                deduped.append(candidate.rstrip("/"))
        return deduped

    def _invidious_get(self, base_url: str, path: str) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("Python requests is unavailable.")
        response = requests.get(
            f"{base_url}{path}",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected Invidious response.")
        if payload.get("error"):
            raise RuntimeError(str(payload.get("error")))
        return payload

    def _youtube_resources_from_invidious(self, url: str) -> list[dict[str, Any]]:
        instances = self._fetch_invidious_instances()
        if not instances:
            raise RuntimeError("No public Invidious instances were available.")
        playlist_id = extract_youtube_playlist_id(url)
        video_id = extract_youtube_video_id(url)
        errors: list[str] = []
        if playlist_id:
            for base_url in instances:
                try:
                    self.resourceImportStatusChanged.emit("Fetching playlist metadata...")
                    playlist = self._invidious_get(base_url, f"/api/v1/playlists/{playlist_id}")
                    videos = playlist.get("videos", [])
                    if not isinstance(videos, list) or not videos:
                        raise RuntimeError("Playlist items were not available.")
                    resources: list[dict[str, Any]] = []
                    for index, entry in enumerate(videos, start=1):
                        if index > 1:
                            time.sleep(1)
                        if not isinstance(entry, dict):
                            continue
                        entry_id = str(entry.get("videoId", "") or "")
                        title = str(entry.get("title", "Playlist item") or "Playlist item")
                        if not entry_id:
                            continue
                        try:
                            self.resourceImportStatusChanged.emit(f"Importing class {index} of {len(videos)}...")
                            video_payload = self._invidious_get(base_url, f"/api/v1/videos/{entry_id}")
                            resources.extend(self._youtube_resources_from_entry(video_payload))
                        except Exception:
                            resources.append(
                                make_resource(
                                    title,
                                    kind="youtube",
                                    provider="YouTube",
                                    source_url=f"https://www.youtube.com/watch?v={entry_id}&list={playlist_id}",
                                    author=str(entry.get("author", playlist.get("author", "YouTube")) or "YouTube"),
                                    summary=str(entry.get("description", "") or "")[:280],
                                    thumbnail_url=(entry.get("videoThumbnails") or [{}])[-1].get("url", "") if isinstance(entry.get("videoThumbnails"), list) and entry.get("videoThumbnails") else "",
                                    tags=slug_tags(title, str(playlist.get("title", "") or "")),
                                    items=[make_resource_item(title, duration_seconds=int(entry.get("lengthSeconds", 0) or 0), position=1, kind="video", external_url=f"https://www.youtube.com/watch?v={entry_id}&list={playlist_id}")],
                                    duration_seconds=int(entry.get("lengthSeconds", 0) or 0),
                                )
                            )
                    if resources:
                        return resources
                except Exception as exc:
                    errors.append(f"{base_url}: {exc}")
            raise RuntimeError(errors[0] if errors else "Unable to fetch playlist through Invidious.")
        if video_id:
            for base_url in instances:
                try:
                    video_payload = self._invidious_get(base_url, f"/api/v1/videos/{video_id}")
                    return self._youtube_resources_from_entry(video_payload)
                except Exception as exc:
                    errors.append(f"{base_url}: {exc}")
            raise RuntimeError(errors[0] if errors else "Unable to fetch video through Invidious.")
        raise RuntimeError("The YouTube URL could not be parsed.")

    def _udemy_resources_from_url(self, url: str) -> list[dict[str, Any]]:
        if requests is None:
            raise RuntimeError("Python requests is unavailable.")
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        response.raise_for_status()
        html = response.text
        title = "Udemy course"
        author = "Udemy"
        summary = ""
        tags: list[str] = []
        items: list[dict[str, Any]] = []
        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                title = soup.title.string.split("|")[0].strip() or title
            meta_description = soup.find("meta", attrs={"name": "description"})
            if meta_description and meta_description.get("content"):
                summary = str(meta_description.get("content", "")).strip()
            instructor = soup.select_one("[data-purpose*='instructor-name-top'], .instructor-links a")
            if instructor:
                author = instructor.get_text(" ", strip=True) or author
            for node in soup.select("[data-purpose*='curriculum-item-title'], [data-purpose*='section-panel-title']"):
                label = node.get_text(" ", strip=True)
                if label and label.lower() not in {item["title"].lower() for item in items}:
                    items.append(make_resource_item(label, position=len(items) + 1, kind="lesson"))
            breadcrumb = soup.select("a[href*='/topic/'], a[href*='/course/']")
            tags = slug_tags(title, author, " ".join(node.get_text(" ", strip=True) for node in breadcrumb[:4]))
        if not items:
            script_match = re.search(r'"title"\s*:\s*"([^"]+)"', html)
            if script_match:
                title = script_match.group(1)
            lesson_matches = re.findall(r'"title"\s*:\s*"([^"]+)"\s*,\s*"object_index"\s*:\s*\d+', html)
            for lesson_title in lesson_matches[:200]:
                if lesson_title and lesson_title.lower() != title.lower():
                    items.append(make_resource_item(lesson_title, position=len(items) + 1, kind="lesson"))
        if not items:
            items = [make_resource_item("Open course page", position=1, kind="lesson", external_url=url)]
        return [
            make_resource(
                title,
                kind="udemy",
                provider="Udemy",
                source_url=url,
                author=author,
                summary=summary,
                tags=tags or slug_tags(title, author, "udemy"),
                items=items,
            )
        ]

    def add_resource_from_url(self, url: str) -> None:
        source_url = str(url or "").strip()
        if not source_url or self._resource_import_busy:
            return
        self._resource_import_busy = True
        self._resource_import_message = "Fetching resource..."
        self.push_resources()
        threading.Thread(target=self._import_resources_in_background, args=(source_url,), daemon=True).start()

    def _import_resources_in_background(self, source_url: str) -> None:
        try:
            resources = self._import_resources_from_url(source_url)
            self.resourceImportFinished.emit(True, resources, f"Imported {len(resources)} resource{'s' if len(resources) != 1 else ''}.")
        except Exception as exc:
            self.resourceImportFinished.emit(False, [], f"Unable to import resource: {exc}")

    def _import_resources_from_url(self, source_url: str) -> list[dict[str, Any]]:
        if is_document_reference(source_url):
            return self._document_resource_from_reference(source_url)
        if self._looks_like_jellyfin_url(source_url):
            return self._jellyfin_resources_from_url(source_url)
        if is_youtube_url(source_url):
            try:
                return self._youtube_resources_from_url(source_url)
            except Exception as exc:
                if youtube_sign_in_required(str(exc)):
                    self.resourceImportStatusChanged.emit("Trying an Invidious fallback...")
                    return self._youtube_resources_from_invidious(source_url)
                raise
        if is_udemy_url(source_url):
            return self._udemy_resources_from_url(source_url)
        parsed = urlparse(source_url)
        if parsed.scheme or parsed.netloc:
            label = parsed.netloc or "Manual reference"
            title = source_url
            reference_url = source_url
            summary = "General reference added manually."
            kind = "other"
        else:
            label = "Manual note"
            title = source_url
            reference_url = ""
            summary = "Manual reference note for future schedules, focus sessions, or reminders."
            kind = "book"
        return [
            make_resource(
                title,
                kind=kind,
                provider=label,
                source_url=reference_url,
                summary=summary,
                tags=slug_tags(label, source_url),
                items=[make_resource_item("Reference entry", position=1, kind="reference", external_url=reference_url, notes=source_url)],
            )
        ]

    def _finish_resource_import(self, ok: bool, resources: object, message: str) -> None:
        self._resource_import_busy = False
        self._resource_import_message = ""
        if ok and isinstance(resources, list):
            loose_policy_limit = int(self._resource_policy().get("loose_single_limit", 5) or 0)
            current_loose_count = len(loose_single_resources(self.state))
            accepted: list[dict[str, Any]] = []
            warnings: list[str] = []
            for resource in resources:
                if not isinstance(resource, dict):
                    continue
                if is_loose_single_resource(resource):
                    if loose_policy_limit >= 0 and current_loose_count >= loose_policy_limit:
                        warnings.append(
                            f"Skipped '{resource.get('title', 'resource')}'. Too many standalone single videos/documents become hard to maintain. Add it inside a broader study resource or raise the limit in Settings."
                        )
                        continue
                    current_loose_count += 1
                    warnings.append(
                        f"'{resource.get('title', 'resource')}' is a standalone single item. It is usually better inside a broader study resource so planning stays manageable."
                    )
                accepted.append(resource)
            if not accepted and warnings:
                self.push_resources()
                notify("Study Resources", warnings[0])
                return
            existing = self.state.setdefault("resources", [])
            if isinstance(existing, list):
                existing[0:0] = accepted
            notice = message
            if warnings:
                notice = f"{message} {warnings[0]}"
            self._commit_resources(notice)
            return
        self.push_resources()
        notify("Study Resources", message)

    def _update_resource_import_status(self, message: str) -> None:
        if not self._resource_import_busy:
            return
        self._resource_import_message = str(message or "Fetching resource...")
        self.push_resources()

    def toggle_resource_item(self, resource_id: str, item_id: str) -> None:
        resource = resource_by_id(self.state, resource_id)
        if not isinstance(resource, dict):
            return
        for item in resource.get("items", []):
            if isinstance(item, dict) and str(item.get("id", "")) == item_id:
                item["done"] = not bool(item.get("done", False))
                item["completed_at"] = datetime.now().strftime("%I:%M %p").lstrip("0") if item["done"] else ""
                resource["updated_at"] = now_iso()
                self._commit_resources()
                return

    def set_all_resource_items(self, resource_id: str, done: bool) -> None:
        resource = resource_by_id(self.state, resource_id)
        if not isinstance(resource, dict):
            return
        stamp = datetime.now().strftime("%I:%M %p").lstrip("0") if done else ""
        for item in resource.get("items", []):
            if isinstance(item, dict):
                item["done"] = bool(done)
                item["completed_at"] = stamp if done else ""
        resource["updated_at"] = now_iso()
        self._commit_resources()

    def set_document_page(self, resource_id: str, page: int) -> None:
        resource = resource_by_id(self.state, resource_id)
        if not isinstance(resource, dict):
            return
        total = max(1, int(resource.get("document_total_pages", 0) or 1))
        resource["document_current_page"] = max(0, min(total, int(page or 0)))
        resource["updated_at"] = now_iso()
        self._commit_resources()

    def open_resource_source(self, resource_id: str) -> None:
        resource = resource_by_id(self.state, resource_id)
        if not isinstance(resource, dict):
            return
        source_url = str(resource.get("source_url", "") or "").strip()
        if not source_url:
            return
        try:
            subprocess.Popen(["xdg-open", source_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception as exc:
            notify("Study Resources", f"Unable to open source: {exc}")

    def navigate_to(self, page: str) -> None:
        normalized = str(page).strip().lower()
        if normalized == "settings":
            target = "settings"
        elif normalized == "schedule":
            target = "schedule"
        elif normalized == "resources":
            target = "resources"
        else:
            target = "dashboard"
        if target == self.current_page:
            return
        self.current_page = target
        self._run_js(f"window.showStudyPage({json.dumps(target)});")

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

    def save_jellyfin_settings(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return
        jellyfin = self._jellyfin_settings()
        old_instance = str(jellyfin.get("instance_url", "") or "").strip().rstrip("/")
        old_token = str(jellyfin.get("api_token", "") or "").strip()
        jellyfin["instance_url"] = str(payload.get("instance_url", "") or "").strip().rstrip("/")
        jellyfin["api_token"] = str(payload.get("api_token", "") or "").strip()
        if jellyfin["instance_url"] != old_instance or jellyfin["api_token"] != old_token:
            jellyfin["user_id"] = ""
        jellyfin["last_status"] = (
            "Jellyfin settings saved. Paste a Jellyfin item URL in Resources to import it."
            if jellyfin["instance_url"] and jellyfin["api_token"]
            else "Jellyfin is not configured yet."
        )
        self._save()
        self.push_settings()

    def save_resource_policy(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            return
        policy = preferences.setdefault("resource_policy", {})
        if not isinstance(policy, dict):
            return
        loose_limit = int(payload.get("loose_single_limit", 5) or 0)
        schedule_limit = int(payload.get("schedule_loose_single_limit", 5) or 0)
        policy["loose_single_limit"] = -1 if loose_limit < 0 else max(0, loose_limit)
        policy["schedule_loose_single_limit"] = -1 if schedule_limit < 0 else max(0, schedule_limit)
        self._save()
        self.push_settings()
        self.push_resources()

    def save_notification_settings(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            return
        notifications = preferences.setdefault("notifications", {})
        if not isinstance(notifications, dict):
            return
        for key in ("study_blocks", "life_blocks", "caldav_events", "resource_plans"):
            notifications[key] = bool(payload.get(key, notifications.get(key, False)))
        self._save()
        self.push_settings()

    def _resource_policy(self) -> dict[str, Any]:
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            return {"loose_single_limit": 5, "schedule_loose_single_limit": 5}
        policy = preferences.setdefault("resource_policy", {})
        if not isinstance(policy, dict):
            return {"loose_single_limit": 5, "schedule_loose_single_limit": 5}
        return policy

    def _notifications_policy(self) -> dict[str, Any]:
        preferences = self.state.setdefault("preferences", {})
        if not isinstance(preferences, dict):
            return {}
        notifications = preferences.setdefault("notifications", {})
        return notifications if isinstance(notifications, dict) else {}

    def _single_item_policy_message(self, resource: dict[str, Any], *, for_schedule: bool = False) -> str | None:
        if not is_loose_single_resource(resource):
            return None
        policy = self._resource_policy()
        limit_key = "schedule_loose_single_limit" if for_schedule else "loose_single_limit"
        limit = int(policy.get(limit_key, 5) or 0)
        used = len(loose_single_resources(self.state))
        if limit >= 0 and ((used >= limit and not for_schedule) or (used >= limit and for_schedule)):
            return (
                f"This looks like a single {resource.get('kind', 'item')}. Too many standalone singles make study maintenance harder. "
                f"Put it inside a broader study resource or raise the limit in Settings."
            )
        return (
            f"This is a single standalone item. It is better inside a broader study resource so schedules and progress stay manageable. "
            f"You are using {used}{'+' if limit >= 0 and used > limit else ''} of {limit if limit >= 0 else 'infinite'} allowed loose singles."
        )

    def _notify_schedule_policy(self, kind: str, title: str, body: str) -> None:
        notifications = self._notifications_policy()
        if kind == "study" and not bool(notifications.get("study_blocks", True)):
            return
        if kind == "life" and not bool(notifications.get("life_blocks", False)):
            return
        if kind == "resource_plan" and not bool(notifications.get("resource_plans", True)):
            return
        notify(title, body)

    def create_schedule_template(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return
        template_id = str(payload.get("id", "") or "")
        template = {
            "id": template_id or str(uuid.uuid4()),
            "title": str(payload.get("title", "Schedule Slot") or "Schedule Slot"),
            "category": str(payload.get("category", "General") or "General"),
            "kind": str(payload.get("kind", "life") or "life").strip().lower(),
            "resource_id": str(payload.get("resource_id", "") or ""),
            "item_id": str(payload.get("item_id", "") or ""),
            "recurrence": str(payload.get("recurrence", "weekly") or "weekly").strip().lower(),
            "day_of_week": max(0, min(6, int(payload.get("day_of_week", 0) or 0))),
            "start_time": str(payload.get("start_time", "08:00") or "08:00"),
            "duration_minutes": max(15, int(payload.get("duration_minutes", 60) or 60)),
            "notify": bool(payload.get("notify", str(payload.get("kind", "life")).strip().lower() == "study_slot")),
        }
        templates = self.state.setdefault("schedule_templates", [])
        updated = False
        if isinstance(templates, list) and template_id:
            for index, existing in enumerate(templates):
                if isinstance(existing, dict) and str(existing.get("id", "")) == template_id:
                    templates[index] = template
                    updated = True
                    break
        if not updated and isinstance(templates, list):
            templates.append(template)
        self._save()
        self.push_state()
        self._notify_schedule_policy(
            "life" if template["kind"] == "life" else "study",
            "Schedule Planner",
            f"{'Updated' if updated else 'Added'} recurring slot: {template['title']}.",
        )

    def create_schedule_block(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return
        block_id = str(payload.get("id", "") or "")
        resource_id = str(payload.get("resource_id", "") or "")
        item_id = str(payload.get("item_id", "") or "")
        date_value = str(payload.get("date", today_iso()) or today_iso())
        start_time = str(payload.get("start_time", "19:00") or "19:00")
        duration_minutes = max(15, int(payload.get("duration_minutes", 60) or 60))
        resource, item = resource_item_by_id(self.state, resource_id, item_id or "__resource__")
        if not isinstance(resource, dict):
            return
        warning = self._single_item_policy_message(resource, for_schedule=True)
        if warning and is_loose_single_resource(resource):
            limit = int(self._resource_policy().get("schedule_loose_single_limit", 5) or 0)
            if limit >= 0:
                allowed = len([opt for opt in build_schedule_target_options(self.state) if opt.get("type") == "single"])
                if allowed >= limit:
                    notify("Schedule Planner", warning)
                    return
        title = str((item or {}).get("title", resource.get("title", "Study Block")) or resource.get("title", "Study Block"))
        block = {
            "id": block_id or str(uuid.uuid4()),
            "title": title,
            "category": "Study",
            "kind": "study",
            "date": date_value,
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "resource_id": resource_id,
            "item_id": str((item or {}).get("id", item_id or "__resource__") or "__resource__"),
            "source": "manual",
            "notify": True,
            "notes": str(payload.get("notes", "") or warning or f"Scheduled from {resource.get('title', 'resource')}."),
        }
        blocks = self.state.setdefault("schedule_blocks", [])
        updated = False
        if isinstance(blocks, list) and block_id:
            for index, existing in enumerate(blocks):
                if isinstance(existing, dict) and str(existing.get("id", "")) == block_id:
                    blocks[index] = block
                    updated = True
                    break
        if not updated and isinstance(blocks, list):
            blocks.append(block)
        self._save()
        self.push_state()
        self._notify_schedule_policy("study", "Schedule Planner", f"{'Updated' if updated else 'Added'} study block for {title}.")

    def delete_schedule_block(self, block_id: str) -> None:
        blocks = self.state.get("schedule_blocks", [])
        if not isinstance(blocks, list):
            return
        self.state["schedule_blocks"] = [block for block in blocks if not (isinstance(block, dict) and str(block.get("id", "")) == block_id)]
        self._save()
        self.push_state()

    def create_resource_plan(self, resource_id: str, classes_per_day: int) -> None:
        resource = resource_by_id(self.state, resource_id)
        if not isinstance(resource, dict):
            return
        templates = [template for template in self.state.get("schedule_templates", []) if isinstance(template, dict) and str(template.get("kind", "") or "") == "study_slot"]
        if not templates:
            notify("Schedule Planner", "Create at least one recurring study slot first, then resource plans can fill it automatically.")
            return
        items = resource.get("items", [])
        if not isinstance(items, list) or not items:
            items = [{"id": "__resource__", "title": str(resource.get("title", "Study resource") or "Study resource")}]
        remaining_items = [item for item in items if isinstance(item, dict) and not bool(item.get("done", False))]
        if not remaining_items:
            notify("Schedule Planner", "This resource is already complete.")
            return
        classes_per_day = max(1, int(classes_per_day or 1))
        start_date = date.today()
        created = 0
        day_counts: dict[str, int] = {}
        for offset in range(21):
            current = start_date + timedelta(days=offset)
            applicable_templates = [template for template in templates if str(template.get("recurrence", "weekly")) == "daily" or int(template.get("day_of_week", 0) or 0) == current.weekday()]
            for template in applicable_templates:
                if not remaining_items:
                    break
                day_key = current.isoformat()
                if day_counts.get(day_key, 0) >= classes_per_day:
                    continue
                item = remaining_items.pop(0)
                self.state.setdefault("schedule_blocks", []).append(
                    {
                        "id": str(uuid.uuid4()),
                        "title": str(item.get("title", resource.get("title", "Study Block")) or resource.get("title", "Study Block")),
                        "category": str(resource.get("title", "Study") or "Study"),
                        "kind": "study",
                        "date": current.isoformat(),
                        "start_time": str(template.get("start_time", "19:00") or "19:00"),
                        "duration_minutes": max(15, int(template.get("duration_minutes", 60) or 60)),
                        "resource_id": str(resource.get("id", "")),
                        "item_id": str(item.get("id", "__resource__") or "__resource__"),
                        "source": "resource_plan",
                        "notify": True,
                        "notes": f"Planned automatically from {resource.get('title', 'resource')}.",
                    }
                )
                day_counts[day_key] = day_counts.get(day_key, 0) + 1
                created += 1
        plans = self.state.setdefault("resource_plans", [])
        if isinstance(plans, list):
            plans.append(
                {
                    "id": str(uuid.uuid4()),
                    "resource_id": str(resource.get("id", "")),
                    "resource_title": str(resource.get("title", "Resource") or "Resource"),
                    "classes_per_day": classes_per_day,
                    "created_at": now_iso(),
                    "active": True,
                }
            )
        self._save()
        self.push_state()
        self._notify_schedule_policy("resource_plan", "Schedule Planner", f"Created {created} planned study blocks from {resource.get('title', 'resource')}.")

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

    def stop_session(self) -> None:
        if not isinstance(self.state.get("active_session"), dict):
            return
        self.state["active_session"] = None
        self._save()
        self.push_state()
        notify("Study session", "Focus session stopped without counting progress.")

    def start_or_pause_session(self) -> None:
        selected_resource_id = str(self.state.get("selected_focus_resource_id", "") or "")
        selected_item_id = str(self.state.get("selected_focus_item_id", "") or "")
        selected_resource, selected_item = resource_item_by_id(self.state, selected_resource_id, selected_item_id)
        if not isinstance(selected_resource, dict) or not isinstance(selected_item, dict):
            notify("Study session", "Choose a class from your resources before starting a focus block.")
            return
        task = find_or_create_task_for_focus_target(self.state, selected_resource, selected_item)
        session = self.state.get("active_session")
        target_seconds = max(60, int(self.state.get("session_length_minutes", 25) or 25) * 60)
        if not isinstance(session, dict):
            self.state["active_session"] = {
                "task_id": str(task.get("id", "")),
                "resource_id": selected_resource_id,
                "item_id": selected_item_id,
                "elapsed_seconds": 0,
                "target_seconds": target_seconds,
                "running": True,
                "started_at": now_iso(),
            }
            notify("Study session started", f"Focus on {selected_item.get('title', task.get('title', 'your task'))}.")
        else:
            if str(session.get("task_id", "")) != str(task.get("id", "")):
                session["task_id"] = str(task.get("id", ""))
                session["elapsed_seconds"] = 0
                session["target_seconds"] = target_seconds
            session["resource_id"] = selected_resource_id
            session["item_id"] = selected_item_id
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
        resource, resource_item = resource_item_by_id(self.state, str(session.get("resource_id", "") or ""), str(session.get("item_id", "") or ""))
        added_minutes = max(1, int(session.get("elapsed_seconds", 0) or 0) // 60)
        self.state["today_minutes"] = max(0, int(self.state.get("today_minutes", 0) or 0) + added_minutes)
        self.state.setdefault("activity_dates", [])
        self.state["activity_dates"] = sorted({*self.state["activity_dates"], today_iso()})
        if task is not None:
            task["sessions_completed"] = max(0, int(task.get("sessions_completed", 0) or 0) + 1)
            if int(task.get("sessions_completed", 0) or 0) >= int(task.get("target_sessions", 1) or 1):
                task["done"] = True
                task["active"] = False
                task["completed_at"] = datetime.now().strftime("%I:%M %p").lstrip("0")
        if isinstance(resource_item, dict):
            if str(resource_item.get("id", "")) == "__resource__":
                resource["tracked_minutes"] = max(0, int(resource.get("tracked_minutes", 0) or 0) + added_minutes)
                resource["tracked_sessions"] = max(0, int(resource.get("tracked_sessions", 0) or 0) + 1)
            else:
                resource_item["tracked_minutes"] = max(0, int(resource_item.get("tracked_minutes", 0) or 0) + added_minutes)
                resource_item["tracked_sessions"] = max(0, int(resource_item.get("tracked_sessions", 0) or 0) + 1)
            if isinstance(resource, dict):
                resource["updated_at"] = now_iso()
        self.state["active_session"] = None
        _ensure_single_active_task(self.state)
        self._save()
        if task is not None:
            target_label = resource_item.get("title", task.get("title", "your task")) if isinstance(resource_item, dict) else task.get("title", "your task")
            notify("Study session complete", f"You finished a focus block for {target_label}.")
        else:
            notify("Study session complete", "A focus block has been completed.")
        self.push_state()
        self.push_resources()
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
