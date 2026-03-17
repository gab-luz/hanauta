#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import signal
import subprocess
import sys
import textwrap
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

import requests
from PyQt6.QtCore import QDateTime, QEasingCurve, QEvent, QPropertyAnimation, QThread, QTime, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "life-organizer"
STATE_FILE = STATE_DIR / "state.json"
GLOBAL_SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import ThemePalette, blend, load_theme_palette, palette_mtime, pick_foreground, rgba


MATERIAL_ICONS = {
    "dashboard": "\ue871",
    "task": "\ue6b1",
    "routine": "\ue8b5",
    "project": "\ue8f9",
    "recovery": "\ue87d",
    "library": "\ue02f",
    "settings": "\ue8b8",
    "sync": "\ue627",
    "today": "\ue8df",
    "bolt": "\uea0b",
    "play": "\ue037",
    "book": "\ue865",
    "school": "\ue80c",
    "streak": "\ue838",
}

WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "material_symbols": FONTS_DIR / "MaterialSymbolsRounded.ttf",
    }
    for key, path in font_map.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def parse_iso_datetime(value: str) -> datetime | None:
    try:
        if not value:
            return None
        return datetime.fromisoformat(value)
    except Exception:
        return None


def parse_time_value(value: str, fallback: time) -> time:
    try:
        return time.fromisoformat(value)
    except Exception:
        return fallback


def clamp_hex(value: str, fallback: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if len(raw) != 7:
        return fallback
    try:
        int(raw[1:], 16)
    except ValueError:
        return fallback
    return raw.upper()


def compare_updated(left: str, right: str) -> int:
    left_dt = parse_iso_datetime(left) or datetime.min
    right_dt = parse_iso_datetime(right) or datetime.min
    if left_dt > right_dt:
        return 1
    if left_dt < right_dt:
        return -1
    return 0


def format_countdown(delta: timedelta) -> str:
    total = max(0, int(delta.total_seconds()))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def days_since(value: str) -> int:
    moment = parse_iso_datetime(value)
    if moment is None:
        return 0
    return max(0, (datetime.now() - moment).days)


@dataclass
class OrganizerTask:
    id: str
    title: str
    notes: str = ""
    due_at: str = ""
    priority: int = 3
    done: bool = False
    area: str = "Life"
    project: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "local"
    remote_uid: str = ""
    updated_at: str = field(default_factory=now_iso)
    completed_at: str = ""


@dataclass
class RoutineEntry:
    id: str
    title: str
    weekday: int
    start_time: str
    end_time: str
    area: str = "Routine"
    location: str = ""
    notes: str = ""
    notify_minutes: int = 10
    updated_at: str = field(default_factory=now_iso)


@dataclass
class ProjectItem:
    id: str
    name: str
    status: str = "Active"
    next_step: str = ""
    deadline: str = ""
    notes: str = ""
    updated_at: str = field(default_factory=now_iso)


@dataclass
class StreakItem:
    id: str
    label: str
    last_reset_at: str
    category: str = "Recovery"
    notes: str = ""
    updated_at: str = field(default_factory=now_iso)


@dataclass
class ResourceItem:
    id: str
    kind: str
    title: str
    link: str = ""
    progress: int = 0
    notes: str = ""
    current: bool = True
    updated_at: str = field(default_factory=now_iso)


@dataclass
class AppSettings:
    appearance_mode: str = "follow"
    custom_accent: str = "#89B4FA"
    todo_txt_path: str = str(Path.home() / "todo.txt")
    notify_lead_minutes: int = 10
    reuse_calendar_credentials: bool = True
    caldav_tasks_url: str = ""
    caldav_username: str = ""
    caldav_password: str = ""
    sync_base_url: str = "http://127.0.0.1:8787"
    sync_api_key: str = "change-me"
    sync_device_name: str = "desktop"


@dataclass
class OrganizerState:
    tasks: list[OrganizerTask] = field(default_factory=list)
    routines: list[RoutineEntry] = field(default_factory=list)
    projects: list[ProjectItem] = field(default_factory=list)
    streaks: list[StreakItem] = field(default_factory=list)
    resources: list[ResourceItem] = field(default_factory=list)
    settings: AppSettings = field(default_factory=AppSettings)


def default_seed_state() -> OrganizerState:
    now = datetime.now()
    return OrganizerState(
        tasks=[
            OrganizerTask(
                id=str(uuid.uuid4()),
                title="Take the trash out",
                due_at=(now + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0).isoformat(),
                priority=2,
                area="Home",
                tags=["chores"],
            ),
            OrganizerTask(
                id=str(uuid.uuid4()),
                title="Review lecture notes",
                due_at=(now + timedelta(hours=4)).replace(minute=30, second=0, microsecond=0).isoformat(),
                priority=3,
                area="Study",
                project="Networks exam",
                tags=["study", "review"],
            ),
        ],
        routines=[
            RoutineEntry(
                id=str(uuid.uuid4()),
                title="Shower and get ready",
                weekday=now.weekday(),
                start_time="07:15:00",
                end_time="07:35:00",
                area="Morning",
                notify_minutes=10,
            ),
            RoutineEntry(
                id=str(uuid.uuid4()),
                title="Deep work block",
                weekday=now.weekday(),
                start_time="19:00:00",
                end_time="20:30:00",
                area="Study",
                location="Desk",
                notes="Theory plus summary notes",
                notify_minutes=15,
            ),
        ],
        projects=[
            ProjectItem(
                id=str(uuid.uuid4()),
                name="Networks exam",
                status="Active",
                next_step="Finish chapter 4 exercises",
                deadline=(now + timedelta(days=6)).date().isoformat(),
                notes="Focus on subnetting and routing tables.",
            ),
            ProjectItem(
                id=str(uuid.uuid4()),
                name="Room reset",
                status="Planning",
                next_step="Sort clothes and donate extras",
                notes="Weekend cleanup sprint.",
            ),
        ],
        streaks=[
            StreakItem(
                id=str(uuid.uuid4()),
                label="Cigarettes",
                last_reset_at=(now - timedelta(days=12, hours=3)).replace(microsecond=0).isoformat(),
                category="Addiction control",
                notes="Track cravings in notes instead of breaking the streak.",
            ),
            StreakItem(
                id=str(uuid.uuid4()),
                label="Self-harm",
                last_reset_at=(now - timedelta(days=34)).replace(microsecond=0).isoformat(),
                category="Safety",
                notes="Reach out before the urge spikes.",
            ),
        ],
        resources=[
            ResourceItem(
                id=str(uuid.uuid4()),
                kind="Udemy",
                title="Complete Python Developer",
                link="https://www.udemy.com/",
                progress=48,
                notes="Currently in async and testing.",
                current=True,
            ),
            ResourceItem(
                id=str(uuid.uuid4()),
                kind="PDF",
                title="Distributed Systems Notes",
                link=str(Path.home() / "Documents" / "distributed-systems.pdf"),
                progress=27,
                current=False,
            ),
        ],
    )


def _safe_int(value: object, fallback: int, lower: int, upper: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return fallback
    return max(lower, min(upper, parsed))


def load_state() -> OrganizerState:
    if not STATE_FILE.exists():
        state = default_seed_state()
        save_state(state)
        return state
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default_seed_state()

    settings_payload = payload.get("settings", {})
    settings = AppSettings(
        appearance_mode=str(settings_payload.get("appearance_mode", "follow")),
        custom_accent=clamp_hex(str(settings_payload.get("custom_accent", "#89B4FA")), "#89B4FA"),
        todo_txt_path=str(settings_payload.get("todo_txt_path", str(Path.home() / "todo.txt"))),
        notify_lead_minutes=_safe_int(settings_payload.get("notify_lead_minutes", 10), 10, 1, 120),
        reuse_calendar_credentials=bool(settings_payload.get("reuse_calendar_credentials", True)),
        caldav_tasks_url=str(settings_payload.get("caldav_tasks_url", "")),
        caldav_username=str(settings_payload.get("caldav_username", "")),
        caldav_password=str(settings_payload.get("caldav_password", "")),
        sync_base_url=str(settings_payload.get("sync_base_url", "http://127.0.0.1:8787")).rstrip("/"),
        sync_api_key=str(settings_payload.get("sync_api_key", "change-me")),
        sync_device_name=str(settings_payload.get("sync_device_name", "desktop")) or "desktop",
    )

    tasks = [
        OrganizerTask(
            id=str(item.get("id") or uuid.uuid4()),
            title=str(item.get("title", "Untitled task")).strip() or "Untitled task",
            notes=str(item.get("notes", "")),
            due_at=str(item.get("due_at", "")),
            priority=_safe_int(item.get("priority", 3), 3, 1, 5),
            done=bool(item.get("done", False)),
            area=str(item.get("area", "Life")),
            project=str(item.get("project", "")),
            tags=[str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()],
            source=str(item.get("source", "local")),
            remote_uid=str(item.get("remote_uid", "")),
            updated_at=str(item.get("updated_at", now_iso())),
            completed_at=str(item.get("completed_at", "")),
        )
        for item in payload.get("tasks", [])
        if isinstance(item, dict)
    ]
    routines = [
        RoutineEntry(
            id=str(item.get("id") or uuid.uuid4()),
            title=str(item.get("title", "Routine block")).strip() or "Routine block",
            weekday=_safe_int(item.get("weekday", 0), 0, 0, 6),
            start_time=str(item.get("start_time", "08:00:00")),
            end_time=str(item.get("end_time", "09:00:00")),
            area=str(item.get("area", "Routine")),
            location=str(item.get("location", "")),
            notes=str(item.get("notes", "")),
            notify_minutes=_safe_int(item.get("notify_minutes", 10), 10, 1, 120),
            updated_at=str(item.get("updated_at", now_iso())),
        )
        for item in payload.get("routines", [])
        if isinstance(item, dict)
    ]
    projects = [
        ProjectItem(
            id=str(item.get("id") or uuid.uuid4()),
            name=str(item.get("name", "Untitled project")).strip() or "Untitled project",
            status=str(item.get("status", "Active")),
            next_step=str(item.get("next_step", "")),
            deadline=str(item.get("deadline", "")),
            notes=str(item.get("notes", "")),
            updated_at=str(item.get("updated_at", now_iso())),
        )
        for item in payload.get("projects", [])
        if isinstance(item, dict)
    ]
    streaks = [
        StreakItem(
            id=str(item.get("id") or uuid.uuid4()),
            label=str(item.get("label", "Untitled streak")).strip() or "Untitled streak",
            last_reset_at=str(item.get("last_reset_at", now_iso())),
            category=str(item.get("category", "Recovery")),
            notes=str(item.get("notes", "")),
            updated_at=str(item.get("updated_at", now_iso())),
        )
        for item in payload.get("streaks", [])
        if isinstance(item, dict)
    ]
    resources = [
        ResourceItem(
            id=str(item.get("id") or uuid.uuid4()),
            kind=str(item.get("kind", "Other")),
            title=str(item.get("title", "Untitled resource")).strip() or "Untitled resource",
            link=str(item.get("link", "")),
            progress=_safe_int(item.get("progress", 0), 0, 0, 100),
            notes=str(item.get("notes", "")),
            current=bool(item.get("current", True)),
            updated_at=str(item.get("updated_at", now_iso())),
        )
        for item in payload.get("resources", [])
        if isinstance(item, dict)
    ]

    return OrganizerState(
        tasks=tasks,
        routines=routines,
        projects=projects,
        streaks=streaks,
        resources=resources,
        settings=settings,
    )


def save_state(state: OrganizerState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "tasks": [asdict(item) for item in state.tasks],
        "routines": [asdict(item) for item in state.routines],
        "projects": [asdict(item) for item in state.projects],
        "streaks": [asdict(item) for item in state.streaks],
        "resources": [asdict(item) for item in state.resources],
        "settings": asdict(state.settings),
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_global_calendar_settings() -> dict:
    try:
        payload = json.loads(GLOBAL_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    calendar = payload.get("calendar", {})
    return calendar if isinstance(calendar, dict) else {}


def resolve_caldav_credentials(settings: AppSettings) -> tuple[str, str, str]:
    url = settings.caldav_tasks_url.strip()
    username = settings.caldav_username.strip()
    password = settings.caldav_password
    if settings.reuse_calendar_credentials:
        calendar = load_global_calendar_settings()
        if not url:
            url = str(calendar.get("caldav_url", "")).strip()
        if not username:
            username = str(calendar.get("caldav_username", "")).strip()
        if not password:
            password = str(calendar.get("caldav_password", ""))
    return url.rstrip("/"), username, password


def due_label(task: OrganizerTask) -> str:
    due = parse_iso_datetime(task.due_at)
    if due is None:
        return "No due date"
    delta = due - datetime.now()
    if delta.days == 0 and delta.total_seconds() > 0:
        return f"Due today at {due:%H:%M}"
    if delta.days == 1:
        return f"Due tomorrow at {due:%H:%M}"
    if delta.total_seconds() < 0:
        return f"Overdue since {due:%d %b %H:%M}"
    return due.strftime("Due %a %d %b %H:%M")


def to_todo_txt_line(task: OrganizerTask) -> str:
    pieces: list[str] = []
    if task.done:
        completed = parse_iso_datetime(task.completed_at) or datetime.now()
        pieces.extend(["x", completed.date().isoformat()])
    if 1 <= task.priority <= 3:
        pieces.append(f"({chr(ord('A') + task.priority - 1)})")
    pieces.append(task.title.strip())
    if task.area.strip():
        pieces.append(f"+{re.sub(r'\\s+', '-', task.area.strip())}")
    if task.project.strip():
        pieces.append(f"project:{re.sub(r'\\s+', '-', task.project.strip())}")
    due = parse_iso_datetime(task.due_at)
    if due is not None:
        pieces.append(f"due:{due.date().isoformat()}")
    for tag in task.tags:
        safe = re.sub(r"\s+", "-", tag.strip())
        if safe:
            pieces.append(f"+{safe}")
    return " ".join(part for part in pieces if part).strip()


def parse_todo_txt_line(line: str) -> OrganizerTask | None:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None
    done = False
    completed_at = ""
    priority = 4
    tags: list[str] = []
    area = "Life"
    project = ""
    due_at = ""

    if raw.startswith("x "):
        done = True
        raw = raw[2:].strip()
        parts = raw.split(maxsplit=1)
        if parts and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[0]):
            completed_at = f"{parts[0]}T12:00:00"
            raw = parts[1] if len(parts) > 1 else ""

    priority_match = re.match(r"^\(([A-Z])\)\s+(.*)$", raw)
    if priority_match:
        priority = _safe_int(ord(priority_match.group(1)) - ord("A") + 1, 4, 1, 5)
        raw = priority_match.group(2).strip()

    title_parts: list[str] = []
    for token in raw.split():
        if token.startswith("due:") and re.fullmatch(r"due:\d{4}-\d{2}-\d{2}", token):
            due_at = f"{token[4:]}T18:00:00"
            continue
        if token.startswith("project:"):
            project = token[len("project:") :].replace("-", " ").strip()
            continue
        if token.startswith("+") and len(token) > 1:
            cleaned = token[1:].replace("-", " ").strip()
            if area == "Life":
                area = cleaned
            tags.append(cleaned)
            continue
        title_parts.append(token)

    title = " ".join(title_parts).strip()
    if not title:
        return None
    return OrganizerTask(
        id=str(uuid.uuid4()),
        title=title,
        due_at=due_at,
        priority=priority,
        done=done,
        area=area,
        project=project,
        tags=tags,
        source="todo.txt",
        completed_at=completed_at,
    )


def escape_ical(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")


def unescape_ical(value: str) -> str:
    return value.replace(r"\n", "\n").replace(r"\,", ",").replace(r"\;", ";").replace("\\\\", "\\")


def fold_ical_line(line: str) -> str:
    if len(line) <= 75:
        return line
    chunks = textwrap.wrap(line, 73, break_long_words=True, break_on_hyphens=False)
    if not chunks:
        return line
    return chunks[0] + "".join(f"\r\n {chunk}" for chunk in chunks[1:])


def ical_datetime(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%S")


def task_to_ics(task: OrganizerTask) -> str:
    uid = task.remote_uid or f"{task.id}@hanauta-life-organizer"
    updated = parse_iso_datetime(task.updated_at) or datetime.now()
    due = parse_iso_datetime(task.due_at)
    description = task.notes
    if task.project.strip():
        description = f"Project: {task.project}\n{description}".strip()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Hanauta//Life Organizer//EN",
        "BEGIN:VTODO",
        fold_ical_line(f"UID:{uid}"),
        fold_ical_line(f"DTSTAMP:{ical_datetime(updated)}"),
        fold_ical_line(f"LAST-MODIFIED:{ical_datetime(updated)}"),
        fold_ical_line(f"SUMMARY:{escape_ical(task.title)}"),
        fold_ical_line(f"DESCRIPTION:{escape_ical(description)}"),
        fold_ical_line(f"PRIORITY:{max(0, min(9, task.priority))}"),
        fold_ical_line(f"STATUS:{'COMPLETED' if task.done else 'NEEDS-ACTION'}"),
        fold_ical_line(f"CATEGORIES:{escape_ical(task.area)}"),
    ]
    if due is not None:
        lines.append(fold_ical_line(f"DUE:{ical_datetime(due)}"))
    if task.done:
        completed = parse_iso_datetime(task.completed_at) or updated
        lines.append(fold_ical_line(f"COMPLETED:{ical_datetime(completed)}"))
    lines.extend(["END:VTODO", "END:VCALENDAR", ""])
    return "\r\n".join(lines)


def unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw.rstrip())
    return lines


def parse_vtodo_ics(text: str) -> OrganizerTask | None:
    data: dict[str, list[str]] = {}
    inside = False
    for line in unfold_ics(text):
        if line == "BEGIN:VTODO":
            inside = True
            continue
        if line == "END:VTODO":
            break
        if not inside or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data.setdefault(key.split(";", 1)[0].upper(), []).append(value)
    title = unescape_ical((data.get("SUMMARY") or [""])[0]).strip()
    if not title:
        return None
    description = unescape_ical((data.get("DESCRIPTION") or [""])[0])
    project = ""
    if description.startswith("Project: "):
        first, _, rest = description.partition("\n")
        project = first.replace("Project: ", "", 1).strip()
        description = rest.strip()
    due_at = ""
    if data.get("DUE"):
        try:
            due_at = datetime.strptime(data["DUE"][0][:15], "%Y%m%dT%H%M%S").isoformat()
        except ValueError:
            pass
    updated_at = now_iso()
    if data.get("LAST-MODIFIED") or data.get("DTSTAMP"):
        raw = (data.get("LAST-MODIFIED") or data.get("DTSTAMP") or [""])[0]
        try:
            updated_at = datetime.strptime(raw[:15], "%Y%m%dT%H%M%S").isoformat()
        except ValueError:
            pass
    completed_at = ""
    if data.get("COMPLETED"):
        try:
            completed_at = datetime.strptime(data["COMPLETED"][0][:15], "%Y%m%dT%H%M%S").isoformat()
        except ValueError:
            pass
    return OrganizerTask(
        id=str(uuid.uuid4()),
        title=title,
        notes=description,
        due_at=due_at,
        priority=_safe_int((data.get("PRIORITY") or ["3"])[0], 3, 1, 5),
        done=((data.get("STATUS") or ["NEEDS-ACTION"])[0]).upper() == "COMPLETED",
        area=unescape_ical((data.get("CATEGORIES") or ["Life"])[0]) or "Life",
        project=project,
        source="caldav",
        remote_uid=(data.get("UID") or [""])[0],
        updated_at=updated_at,
        completed_at=completed_at,
    )


def fetch_remote_tasks(url: str, username: str, password: str) -> list[OrganizerTask]:
    query = """<?xml version="1.0" encoding="UTF-8"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><d:getetag /><c:calendar-data /></d:prop>
  <c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VTODO" /></c:comp-filter></c:filter>
</c:calendar-query>
"""
    response = requests.request(
        "REPORT",
        url,
        data=query.encode("utf-8"),
        headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
        auth=(username, password),
        timeout=25,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    namespaces = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav"}
    tasks: list[OrganizerTask] = []
    for node in root.findall(".//d:response", namespaces):
        calendar_data = node.find(".//c:calendar-data", namespaces)
        if calendar_data is None or not (calendar_data.text or "").strip():
            continue
        task = parse_vtodo_ics(calendar_data.text or "")
        if task is not None:
            tasks.append(task)
    return tasks


def upload_task(url: str, username: str, password: str, task: OrganizerTask) -> str:
    uid = task.remote_uid or f"{task.id}@hanauta-life-organizer"
    response = requests.put(
        f"{url.rstrip('/')}/{uid}.ics",
        data=task_to_ics(task).encode("utf-8"),
        headers={"Content-Type": "text/calendar; charset=utf-8"},
        auth=(username, password),
        timeout=25,
    )
    response.raise_for_status()
    return uid


def exportable_cloud_state(state: OrganizerState) -> dict[str, object]:
    return {
        "tasks": [asdict(item) for item in state.tasks],
        "routines": [asdict(item) for item in state.routines],
        "projects": [asdict(item) for item in state.projects],
        "streaks": [asdict(item) for item in state.streaks],
        "resources": [asdict(item) for item in state.resources],
        "settings": {
            "appearance_mode": state.settings.appearance_mode,
            "custom_accent": state.settings.custom_accent,
            "notify_lead_minutes": state.settings.notify_lead_minutes,
        },
    }


def _merge_records(local: list[object], remote: list[object]) -> list[object]:
    merged: dict[str, object] = {}
    for item in local:
        item_id = str(getattr(item, "id", ""))
        if item_id:
            merged[item_id] = item
    for item in remote:
        item_id = str(getattr(item, "id", ""))
        if not item_id:
            continue
        existing = merged.get(item_id)
        if existing is None or compare_updated(str(getattr(item, "updated_at", "")), str(getattr(existing, "updated_at", ""))) >= 0:
            merged[item_id] = item
    return list(merged.values())


def apply_cloud_payload(local: OrganizerState, payload: dict[str, object]) -> OrganizerState:
    remote = OrganizerState(
        tasks=[OrganizerTask(**item) for item in payload.get("tasks", []) if isinstance(item, dict)],
        routines=[RoutineEntry(**item) for item in payload.get("routines", []) if isinstance(item, dict)],
        projects=[ProjectItem(**item) for item in payload.get("projects", []) if isinstance(item, dict)],
        streaks=[StreakItem(**item) for item in payload.get("streaks", []) if isinstance(item, dict)],
        resources=[ResourceItem(**item) for item in payload.get("resources", []) if isinstance(item, dict)],
        settings=local.settings,
    )
    merged = OrganizerState(
        tasks=[item for item in _merge_records(local.tasks, remote.tasks) if isinstance(item, OrganizerTask)],
        routines=[item for item in _merge_records(local.routines, remote.routines) if isinstance(item, RoutineEntry)],
        projects=[item for item in _merge_records(local.projects, remote.projects) if isinstance(item, ProjectItem)],
        streaks=[item for item in _merge_records(local.streaks, remote.streaks) if isinstance(item, StreakItem)],
        resources=[item for item in _merge_records(local.resources, remote.resources) if isinstance(item, ResourceItem)],
        settings=local.settings,
    )
    safe_settings = payload.get("settings", {})
    if isinstance(safe_settings, dict):
        merged.settings.appearance_mode = str(safe_settings.get("appearance_mode", merged.settings.appearance_mode))
        merged.settings.custom_accent = clamp_hex(str(safe_settings.get("custom_accent", merged.settings.custom_accent)), merged.settings.custom_accent)
        merged.settings.notify_lead_minutes = _safe_int(safe_settings.get("notify_lead_minutes", merged.settings.notify_lead_minutes), merged.settings.notify_lead_minutes, 1, 120)
    return merged


class CalDAVSyncWorker(QThread):
    synced = pyqtSignal(list, str)
    failed = pyqtSignal(str)

    def __init__(self, tasks: list[OrganizerTask], settings: AppSettings) -> None:
        super().__init__()
        self.tasks = [OrganizerTask(**asdict(task)) for task in tasks]
        self.settings = AppSettings(**asdict(settings))

    def run(self) -> None:
        url, username, password = resolve_caldav_credentials(self.settings)
        if not url or not username or not password:
            self.failed.emit("CalDAV credentials are incomplete. Set a task collection URL, username, and password.")
            return
        try:
            remote_tasks = fetch_remote_tasks(url, username, password)
            local_by_uid = {task.remote_uid: task for task in self.tasks if task.remote_uid}
            merged = [OrganizerTask(**asdict(task)) for task in self.tasks]
            imported = 0
            uploaded = 0

            for remote in remote_tasks:
                if remote.remote_uid and remote.remote_uid in local_by_uid:
                    local = local_by_uid[remote.remote_uid]
                    if compare_updated(remote.updated_at, local.updated_at) > 0:
                        remote.id = local.id
                        merged = [remote if item.id == local.id else item for item in merged]
                else:
                    merged.append(remote)
                    imported += 1

            for index, task in enumerate(merged):
                if task.done and not task.remote_uid:
                    continue
                existing_remote = next((item for item in remote_tasks if item.remote_uid == task.remote_uid), None)
                if task.remote_uid and existing_remote and compare_updated(task.updated_at, existing_remote.updated_at) < 0:
                    continue
                uid = upload_task(url, username, password, task)
                merged[index].remote_uid = uid
                uploaded += 1

            self.synced.emit(merged, f"Synced {uploaded} task(s); imported {imported} remote task(s).")
        except Exception as exc:
            self.failed.emit(str(exc))


class CloudSyncWorker(QThread):
    synced = pyqtSignal(dict, str)
    failed = pyqtSignal(str)

    def __init__(self, state: OrganizerState) -> None:
        super().__init__()
        self.state = OrganizerState(
            tasks=[OrganizerTask(**asdict(item)) for item in state.tasks],
            routines=[RoutineEntry(**asdict(item)) for item in state.routines],
            projects=[ProjectItem(**asdict(item)) for item in state.projects],
            streaks=[StreakItem(**asdict(item)) for item in state.streaks],
            resources=[ResourceItem(**asdict(item)) for item in state.resources],
            settings=AppSettings(**asdict(state.settings)),
        )

    def run(self) -> None:
        try:
            base = self.state.settings.sync_base_url.rstrip("/")
            api_key = self.state.settings.sync_api_key.strip()
            device = self.state.settings.sync_device_name.strip() or "desktop"
            if not base or not api_key:
                self.failed.emit("Cloud sync needs both a base URL and an API key.")
                return
            headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
            put_payload = {
                "device": device,
                "state": exportable_cloud_state(self.state),
            }
            put_response = requests.put(f"{base}/api/v1/state/{device}", headers=headers, json=put_payload, timeout=25)
            put_response.raise_for_status()
            get_response = requests.get(f"{base}/api/v1/state/{device}", headers=headers, timeout=25)
            get_response.raise_for_status()
            payload = get_response.json()
            state_payload = payload.get("state", {})
            if not isinstance(state_payload, dict):
                self.failed.emit("Server returned an invalid state payload.")
                return
            self.synced.emit(state_payload, f"Cloud sync finished with device '{device}'.")
        except Exception as exc:
            self.failed.emit(str(exc))


class NavButton(QPushButton):
    def __init__(self, icon_text: str, title: str, subtitle: str) -> None:
        super().__init__()
        self.setObjectName("navButton")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(12)
        self.icon_label = QLabel(icon_text)
        self.icon_label.setObjectName("navIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setMinimumWidth(26)
        self.text_wrap = QWidget()
        text_wrap_layout = QVBoxLayout(self.text_wrap)
        text_wrap_layout.setContentsMargins(0, 0, 0, 0)
        text_wrap_layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("navTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("navSubtitle")
        text_wrap_layout.addWidget(self.title_label)
        text_wrap_layout.addWidget(self.subtitle_label)
        self.layout.addWidget(self.icon_label)
        self.layout.addWidget(self.text_wrap, 1)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_collapsed(self, collapsed: bool) -> None:
        self.text_wrap.setVisible(not collapsed)
        if collapsed:
            self.layout.setContentsMargins(0, 12, 0, 12)
            self.layout.setSpacing(0)
            self.icon_label.setMinimumWidth(0)
            self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self.layout.setContentsMargins(14, 12, 14, 12)
            self.layout.setSpacing(12)
            self.icon_label.setMinimumWidth(26)
            self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)


class MetricCard(QFrame):
    def __init__(self, icon_text: str, title: str) -> None:
        super().__init__()
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        icon = QLabel(icon_text)
        icon.setObjectName("metricIcon")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricEyebrow")
        self.value_label = QLabel("--")
        self.value_label.setObjectName("metricValue")
        self.caption_label = QLabel("")
        self.caption_label.setObjectName("bodyText")
        self.caption_label.setWordWrap(True)
        layout.addWidget(icon)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)

    def set_content(self, value: str, caption: str) -> None:
        self.value_label.setText(value)
        self.caption_label.setText(caption)


class ItemCard(QFrame):
    def __init__(self, title: str, badge: str = "") -> None:
        super().__init__()
        self.setObjectName("itemCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("itemTitle")
        title_label.setWordWrap(True)
        top.addWidget(title_label, 1)
        if badge:
            badge_label = QLabel(badge)
            badge_label.setObjectName("badge")
            top.addWidget(badge_label, 0, Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(top)


class OrganizerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.material_font = detect_font(
            self.loaded_fonts.get("material_icons", ""),
            self.loaded_fonts.get("material_outlined", ""),
            self.loaded_fonts.get("material_symbols", ""),
            "Material Icons",
            "Material Symbols Rounded",
        )
        self.state = load_state()
        self.base_theme = load_theme_palette()
        self.theme = self._resolved_theme(self.base_theme)
        self._theme_mtime = palette_mtime()
        self.ui_font = detect_font(self.theme.ui_font_family, "Rubik", "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font(self.theme.display_font_family, self.theme.serif_font_family, "Outfit", self.ui_font)
        self.mono_font = detect_font(self.theme.mono_font_family, "JetBrains Mono", "DejaVu Sans Mono", "Monospace")
        self.selected_task_id = ""
        self.selected_routine_id = ""
        self.selected_project_id = ""
        self.selected_streak_id = ""
        self.selected_resource_id = ""
        self._last_notice_key = ""
        self.caldav_worker: CalDAVSyncWorker | None = None
        self.cloud_worker: CloudSyncWorker | None = None
        self.sidebar_collapsed_width = 82
        self.sidebar_expanded_width = 260
        self.dashboard_compact_threshold = 1320

        self.setWindowTitle("Hanauta Life Organizer")
        self.resize(1360, 900)
        self.setMinimumSize(1180, 760)

        self._build_ui()
        self._apply_window_effects()
        self._apply_styles()
        self._set_sidebar_collapsed(True, animate=False)
        self._refresh_all()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick)
        self.clock_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self.sidebar_close_timer = QTimer(self)
        self.sidebar_close_timer.setSingleShot(True)
        self.sidebar_close_timer.timeout.connect(lambda: self._set_sidebar_collapsed(True))
        self.sidebar_min_animation = QPropertyAnimation(self.sidebar, b"minimumWidth", self)
        self.sidebar_max_animation = QPropertyAnimation(self.sidebar, b"maximumWidth", self)
        for animation in (self.sidebar_min_animation, self.sidebar_max_animation):
            animation.setDuration(180)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _resolved_theme(self, base: ThemePalette) -> ThemePalette:
        settings = self.state.settings if hasattr(self, "state") else load_state().settings
        payload = asdict(base)
        mode = settings.appearance_mode
        if mode == "dark":
            payload.update(
                {
                    "primary": "#8DB4FF",
                    "on_primary": "#102E6D",
                    "primary_container": "#1D3F89",
                    "on_primary_container": "#D9E2FF",
                    "secondary": "#C0B6FF",
                    "on_secondary": "#2E2760",
                    "tertiary": "#F2A5D0",
                    "on_tertiary": "#5D173E",
                    "background": "#0E1016",
                    "on_background": "#EFF2F8",
                    "surface": "#0E1016",
                    "on_surface": "#EFF2F8",
                    "surface_container": "#171B26",
                    "surface_container_high": "#202635",
                    "surface_variant": "#2A3143",
                    "on_surface_variant": "#AFB7CA",
                    "outline": "#6B7894",
                    "use_matugen": False,
                }
            )
        elif mode == "light":
            payload.update(
                {
                    "primary": "#3553E2",
                    "on_primary": "#FFFFFF",
                    "primary_container": "#DCE2FF",
                    "on_primary_container": "#132B8A",
                    "secondary": "#6B5BD2",
                    "on_secondary": "#FFFFFF",
                    "tertiary": "#A2467E",
                    "on_tertiary": "#FFFFFF",
                    "background": "#F5F6FB",
                    "on_background": "#1A1B22",
                    "surface": "#F5F6FB",
                    "on_surface": "#1A1B22",
                    "surface_container": "#FFFFFF",
                    "surface_container_high": "#EEF2F9",
                    "surface_variant": "#E0E6F0",
                    "on_surface_variant": "#556073",
                    "outline": "#9AA5B5",
                    "use_matugen": False,
                }
            )
        elif mode == "custom":
            accent = clamp_hex(settings.custom_accent, base.primary)
            payload["primary"] = accent
            payload["secondary"] = blend(accent, base.secondary, 0.45)
            payload["tertiary"] = blend(accent, base.tertiary, 0.35)
            payload["primary_container"] = blend(accent, base.surface_container, 0.58)
            payload["on_primary"] = pick_foreground(accent, "#FFFFFF", "#101114")
            payload["on_primary_container"] = pick_foreground(payload["primary_container"], "#FFFFFF", "#101114")
            payload["use_matugen"] = False
        return ThemePalette(**payload)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        self.shell = QFrame()
        self.shell.setObjectName("shell")
        shell_layout = QHBoxLayout(self.shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(self.sidebar_collapsed_width)
        self.sidebar.setMaximumWidth(self.sidebar_collapsed_width)
        self.sidebar.installEventFilter(self)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)
        shell_layout.addWidget(self.sidebar)

        brand = QFrame()
        brand.setObjectName("editorCard")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(18, 18, 18, 18)
        brand_layout.setSpacing(6)
        self.brand_icon = QLabel(material_icon("bolt"))
        self.brand_icon.setObjectName("brandIcon")
        self.brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_title = QLabel("Life Organizer")
        self.brand_title.setObjectName("brandTitle")
        self.brand_body = QLabel("Daily routine, recovery streaks, projects, chores, and study in one place.")
        self.brand_body.setObjectName("bodyText")
        self.brand_body.setWordWrap(True)
        brand_layout.addWidget(self.brand_icon, 0, Qt.AlignmentFlag.AlignLeft)
        brand_layout.addWidget(self.brand_title)
        brand_layout.addWidget(self.brand_body)
        sidebar_layout.addWidget(brand)

        nav_items = [
            ("dashboard", "Overview", "Today and next up"),
            ("task", "Tasks", "Life + study tasks"),
            ("routine", "Routines", "Shower, trash, work blocks"),
            ("project", "Projects", "Personal and study projects"),
            ("recovery", "Recovery", "Streaks and addiction control"),
            ("library", "Library", "Udemy, PDFs, YouTube"),
            ("settings", "Settings", "Themes and sync"),
        ]
        self.nav_buttons: list[NavButton] = []
        for index, (icon_name, title_text, subtitle) in enumerate(nav_items):
            button = NavButton(material_icon(icon_name), title_text, subtitle)
            button.clicked.connect(lambda _checked=False, idx=index: self._set_page(idx))
            sidebar_layout.addWidget(button)
            self.nav_buttons.append(button)
        sidebar_layout.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusText")
        self.status_label.setWordWrap(True)
        sidebar_layout.addWidget(self.status_label)

        self.content = QFrame()
        self.content.setObjectName("contentArea")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(22, 22, 22, 22)
        content_layout.setSpacing(16)
        shell_layout.addWidget(self.content, 1)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)
        self.page_kicker = QLabel("HANAUTA")
        self.page_kicker.setObjectName("pageKicker")
        self.page_title = QLabel("Overview")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("A calm command center for home, study, recovery, and projects.")
        self.page_subtitle.setObjectName("bodyText")
        title_wrap.addWidget(self.page_kicker)
        title_wrap.addWidget(self.page_title)
        title_wrap.addWidget(self.page_subtitle)
        header.addLayout(title_wrap, 1)

        self.clock_label = QLabel("")
        self.clock_label.setObjectName("clockBadge")
        header.addWidget(self.clock_label, 0, Qt.AlignmentFlag.AlignTop)
        content_layout.addLayout(header)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_dashboard_page())
        self.stack.addWidget(self._build_tasks_page())
        self.stack.addWidget(self._build_routines_page())
        self.stack.addWidget(self._build_projects_page())
        self.stack.addWidget(self._build_recovery_page())
        self.stack.addWidget(self._build_library_page())
        self.stack.addWidget(self._build_settings_page())
        self._set_page(0)

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 22, 22, 22)
        hero_layout.setSpacing(8)
        self.hero_title = QLabel("No routine blocks yet")
        self.hero_title.setObjectName("heroTitle")
        self.hero_meta = QLabel("Add recurring life blocks like shower, trash, work, or study.")
        self.hero_meta.setObjectName("heroBody")
        self.hero_meta.setWordWrap(True)
        countdown_row = QHBoxLayout()
        countdown_row.setSpacing(12)
        self.hero_countdown = QLabel("--:--:--")
        self.hero_countdown.setObjectName("heroCountdown")
        self.hero_focus = QLabel("No current library item selected.")
        self.hero_focus.setObjectName("heroBody")
        self.hero_focus.setWordWrap(True)
        countdown_row.addWidget(self.hero_countdown, 0, Qt.AlignmentFlag.AlignLeft)
        countdown_row.addWidget(self.hero_focus, 1)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_meta)
        hero_layout.addLayout(countdown_row)
        layout.addWidget(hero)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.metric_tasks = MetricCard(material_icon("task"), "Open tasks")
        self.metric_routines = MetricCard(material_icon("routine"), "Today's routine")
        self.metric_projects = MetricCard(material_icon("project"), "Active projects")
        self.metric_streak = MetricCard(material_icon("recovery"), "Best streak")
        for card in (self.metric_tasks, self.metric_routines, self.metric_projects, self.metric_streak):
            metrics.addWidget(card, 1)
        layout.addLayout(metrics)

        self.dashboard_tasks = self._make_scroll_section("Next tasks")
        self.dashboard_routines = self._make_scroll_section("Today")
        self.dashboard_streaks = self._make_scroll_section("Recovery")
        self.dashboard_section_frames = [
            self.dashboard_tasks["frame"],
            self.dashboard_routines["frame"],
            self.dashboard_streaks["frame"],
        ]
        self.dashboard_columns_host = QWidget()
        self.dashboard_columns_layout = QHBoxLayout(self.dashboard_columns_host)
        self.dashboard_columns_layout.setContentsMargins(0, 0, 0, 0)
        self.dashboard_columns_layout.setSpacing(16)
        layout.addWidget(self.dashboard_columns_host, 1)

        self.dashboard_carousel = QSlider(Qt.Orientation.Horizontal)
        self.dashboard_carousel.setObjectName("dashboardCarousel")
        self.dashboard_carousel.setRange(0, 1)
        self.dashboard_carousel.setValue(0)
        self.dashboard_carousel.valueChanged.connect(lambda _value: self._update_dashboard_columns_layout())
        layout.addWidget(self.dashboard_carousel)
        self._update_dashboard_columns_layout()
        return page

    def _build_tasks_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        editor = self._editor_card()
        form = editor.layout()
        assert isinstance(form, QVBoxLayout)
        form.addWidget(self._section_heading("Task composer", "Use this for chores, appointments, study action items, and project tasks."))
        self.task_title_input = QLineEdit()
        self.task_area_input = QComboBox()
        self.task_area_input.addItems(["Life", "Home", "Study", "Health", "Work", "Recovery"])
        self.task_project_input = QLineEdit()
        self.task_project_input.setPlaceholderText("Optional project")
        self.task_due_toggle = QCheckBox("Set due date")
        self.task_due_input = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.task_due_input.setCalendarPopup(True)
        self.task_due_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.task_due_input.setEnabled(False)
        self.task_due_toggle.toggled.connect(self.task_due_input.setEnabled)
        self.task_priority_input = QComboBox()
        self.task_priority_input.addItems(["1 - Critical", "2 - High", "3 - Medium", "4 - Low", "5 - Backlog"])
        self.task_priority_input.setCurrentIndex(2)
        self.task_tags_input = QLineEdit()
        self.task_notes_input = QTextEdit()
        self.task_notes_input.setFixedHeight(100)
        for label, widget in [
            ("Title", self.task_title_input),
            ("Area", self.task_area_input),
            ("Project", self.task_project_input),
            ("Priority", self.task_priority_input),
            ("Tags", self.task_tags_input),
            ("Notes", self.task_notes_input),
        ]:
            form.addWidget(self._field_label(label))
            form.addWidget(widget)
        form.addWidget(self.task_due_toggle)
        form.addWidget(self.task_due_input)

        actions = QHBoxLayout()
        self.task_save_button = QPushButton("Add task")
        self.task_save_button.setObjectName("primaryButton")
        self.task_save_button.clicked.connect(self._save_task)
        clear = QPushButton("Clear")
        clear.setObjectName("ghostButton")
        clear.clicked.connect(self._reset_task_form)
        actions.addWidget(self.task_save_button, 1)
        actions.addWidget(clear)
        form.addLayout(actions)

        tools = QVBoxLayout()
        tools.setSpacing(8)
        for label, callback in [
            ("Import todo.txt", self._import_todo_txt),
            ("Export todo.txt", self._export_todo_txt),
            ("Sync CalDAV Tasks", self._sync_caldav_tasks),
            ("Sync Cloud", self._sync_cloud_state),
        ]:
            button = QPushButton(label)
            button.setObjectName("ghostButton")
            button.clicked.connect(callback)
            tools.addWidget(button)
        form.addLayout(tools)
        layout.addWidget(editor, 0)

        self.tasks_section = self._make_scroll_section("Task list")
        layout.addWidget(self.tasks_section["frame"], 1)
        return page

    def _build_routines_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        editor = self._editor_card()
        form = editor.layout()
        assert isinstance(form, QVBoxLayout)
        form.addWidget(self._section_heading("Routine block", "Recurring time blocks for daily life and study: shower, trash, meals, chores, workouts, classes, deep work."))
        self.routine_title_input = QLineEdit()
        self.routine_area_input = QComboBox()
        self.routine_area_input.addItems(["Routine", "Morning", "Home", "Study", "Health", "Work"])
        self.routine_weekday_input = QComboBox()
        self.routine_weekday_input.addItems(WEEKDAYS)
        self.routine_start_input = QTimeEdit(QTime(7, 0))
        self.routine_end_input = QTimeEdit(QTime(7, 30))
        self.routine_location_input = QLineEdit()
        self.routine_notify_input = QSpinBox()
        self.routine_notify_input.setRange(1, 120)
        self.routine_notify_input.setValue(10)
        self.routine_notes_input = QTextEdit()
        self.routine_notes_input.setFixedHeight(100)
        for label, widget in [
            ("Title", self.routine_title_input),
            ("Area", self.routine_area_input),
            ("Weekday", self.routine_weekday_input),
            ("Start", self.routine_start_input),
            ("End", self.routine_end_input),
            ("Location", self.routine_location_input),
            ("Notify minutes before", self.routine_notify_input),
            ("Notes", self.routine_notes_input),
        ]:
            form.addWidget(self._field_label(label))
            form.addWidget(widget)
        actions = QHBoxLayout()
        self.routine_save_button = QPushButton("Add routine")
        self.routine_save_button.setObjectName("primaryButton")
        self.routine_save_button.clicked.connect(self._save_routine)
        clear = QPushButton("Clear")
        clear.setObjectName("ghostButton")
        clear.clicked.connect(self._reset_routine_form)
        actions.addWidget(self.routine_save_button, 1)
        actions.addWidget(clear)
        form.addLayout(actions)
        layout.addWidget(editor, 0)

        self.routines_section = self._make_scroll_section("Routine schedule")
        layout.addWidget(self.routines_section["frame"], 1)
        return page

    def _build_projects_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        editor = self._editor_card()
        form = editor.layout()
        assert isinstance(form, QVBoxLayout)
        form.addWidget(self._section_heading("Project board", "Track personal projects, home resets, and study goals without opening a separate PM tool."))
        self.project_name_input = QLineEdit()
        self.project_status_input = QComboBox()
        self.project_status_input.addItems(["Planning", "Active", "Paused", "Done"])
        self.project_next_step_input = QLineEdit()
        self.project_deadline_toggle = QCheckBox("Set deadline")
        self.project_deadline_input = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        self.project_deadline_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.project_deadline_input.setCalendarPopup(True)
        self.project_deadline_input.setEnabled(False)
        self.project_deadline_toggle.toggled.connect(self.project_deadline_input.setEnabled)
        self.project_notes_input = QTextEdit()
        self.project_notes_input.setFixedHeight(110)
        for label, widget in [
            ("Project name", self.project_name_input),
            ("Status", self.project_status_input),
            ("Next step", self.project_next_step_input),
            ("Notes", self.project_notes_input),
        ]:
            form.addWidget(self._field_label(label))
            form.addWidget(widget)
        form.addWidget(self.project_deadline_toggle)
        form.addWidget(self.project_deadline_input)
        actions = QHBoxLayout()
        self.project_save_button = QPushButton("Add project")
        self.project_save_button.setObjectName("primaryButton")
        self.project_save_button.clicked.connect(self._save_project)
        clear = QPushButton("Clear")
        clear.setObjectName("ghostButton")
        clear.clicked.connect(self._reset_project_form)
        actions.addWidget(self.project_save_button, 1)
        actions.addWidget(clear)
        form.addLayout(actions)
        layout.addWidget(editor, 0)

        self.projects_section = self._make_scroll_section("Projects")
        layout.addWidget(self.projects_section["frame"], 1)
        return page

    def _build_recovery_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        editor = self._editor_card()
        form = editor.layout()
        assert isinstance(form, QVBoxLayout)
        form.addWidget(self._section_heading("Streak tracker", "Track days since last cigarette, self-harm, or any other harmful behavior."))
        self.streak_label_input = QLineEdit()
        self.streak_category_input = QComboBox()
        self.streak_category_input.addItems(["Addiction control", "Safety", "Health", "Custom"])
        self.streak_last_reset_input = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.streak_last_reset_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.streak_last_reset_input.setCalendarPopup(True)
        self.streak_notes_input = QTextEdit()
        self.streak_notes_input.setFixedHeight(110)
        for label, widget in [
            ("Label", self.streak_label_input),
            ("Category", self.streak_category_input),
            ("Last reset / event", self.streak_last_reset_input),
            ("Notes", self.streak_notes_input),
        ]:
            form.addWidget(self._field_label(label))
            form.addWidget(widget)
        actions = QHBoxLayout()
        self.streak_save_button = QPushButton("Add streak")
        self.streak_save_button.setObjectName("primaryButton")
        self.streak_save_button.clicked.connect(self._save_streak)
        reset_now = QPushButton("Record reset now")
        reset_now.setObjectName("ghostButton")
        reset_now.clicked.connect(self._record_streak_reset_now)
        clear = QPushButton("Clear")
        clear.setObjectName("ghostButton")
        clear.clicked.connect(self._reset_streak_form)
        actions.addWidget(self.streak_save_button, 1)
        actions.addWidget(reset_now)
        actions.addWidget(clear)
        form.addLayout(actions)
        layout.addWidget(editor, 0)

        self.streaks_section = self._make_scroll_section("Recovery and streaks")
        layout.addWidget(self.streaks_section["frame"], 1)
        return page

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        editor = self._editor_card()
        form = editor.layout()
        assert isinstance(form, QVBoxLayout)
        form.addWidget(self._section_heading("Current item", "Keep your current Udemy course, PDF, or YouTube video visible on the dashboard."))
        self.resource_kind_input = QComboBox()
        self.resource_kind_input.addItems(["Udemy", "PDF", "YouTube", "Other"])
        self.resource_title_input = QLineEdit()
        self.resource_link_input = QLineEdit()
        self.resource_progress_input = QSpinBox()
        self.resource_progress_input.setRange(0, 100)
        self.resource_current_input = QCheckBox("Mark as current focus")
        self.resource_current_input.setChecked(True)
        self.resource_notes_input = QTextEdit()
        self.resource_notes_input.setFixedHeight(110)
        for label, widget in [
            ("Type", self.resource_kind_input),
            ("Title", self.resource_title_input),
            ("Link / Path", self.resource_link_input),
            ("Progress %", self.resource_progress_input),
            ("Notes", self.resource_notes_input),
        ]:
            form.addWidget(self._field_label(label))
            form.addWidget(widget)
        form.addWidget(self.resource_current_input)
        actions = QHBoxLayout()
        self.resource_save_button = QPushButton("Add item")
        self.resource_save_button.setObjectName("primaryButton")
        self.resource_save_button.clicked.connect(self._save_resource)
        clear = QPushButton("Clear")
        clear.setObjectName("ghostButton")
        clear.clicked.connect(self._reset_resource_form)
        actions.addWidget(self.resource_save_button, 1)
        actions.addWidget(clear)
        form.addLayout(actions)
        layout.addWidget(editor, 0)

        self.resources_section = self._make_scroll_section("Library")
        layout.addWidget(self.resources_section["frame"], 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(16)

        appearance = self._editor_card()
        appearance_layout = appearance.layout()
        assert isinstance(appearance_layout, QVBoxLayout)
        appearance_layout.addWidget(self._section_heading("Appearance", "Follow Matugen, force light or dark, or add your own accent."))
        self.appearance_mode_input = QComboBox()
        self.appearance_mode_input.addItems(["follow", "dark", "light", "custom"])
        self.appearance_mode_input.setCurrentText(self.state.settings.appearance_mode)
        self.custom_accent_input = QLineEdit(self.state.settings.custom_accent)
        self.notify_lead_input = QSpinBox()
        self.notify_lead_input.setRange(1, 120)
        self.notify_lead_input.setValue(self.state.settings.notify_lead_minutes)
        for label, widget in [
            ("Theme mode", self.appearance_mode_input),
            ("Custom accent", self.custom_accent_input),
            ("Default routine reminder lead", self.notify_lead_input),
        ]:
            appearance_layout.addWidget(self._field_label(label))
            appearance_layout.addWidget(widget)
        top.addWidget(appearance, 1)

        sync = self._editor_card()
        sync_layout = sync.layout()
        assert isinstance(sync_layout, QVBoxLayout)
        sync_layout.addWidget(self._section_heading("Sync + paths", "Use Baikal for CalDAV tasks and the separate self-hosted Flask service for broader organizer data."))
        self.todo_path_input = QLineEdit(self.state.settings.todo_txt_path)
        self.caldav_reuse_input = QCheckBox("Reuse Hanauta calendar credentials for task sync")
        self.caldav_reuse_input.setChecked(self.state.settings.reuse_calendar_credentials)
        self.caldav_url_input = QLineEdit(self.state.settings.caldav_tasks_url)
        self.caldav_user_input = QLineEdit(self.state.settings.caldav_username)
        self.caldav_password_input = QLineEdit(self.state.settings.caldav_password)
        self.caldav_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.sync_url_input = QLineEdit(self.state.settings.sync_base_url)
        self.sync_key_input = QLineEdit(self.state.settings.sync_api_key)
        self.sync_device_input = QLineEdit(self.state.settings.sync_device_name)
        for label, widget in [
            ("todo.txt path", self.todo_path_input),
            ("CalDAV tasks URL", self.caldav_url_input),
            ("CalDAV username", self.caldav_user_input),
            ("CalDAV password", self.caldav_password_input),
            ("Cloud sync URL", self.sync_url_input),
            ("Cloud API key", self.sync_key_input),
            ("Device name", self.sync_device_input),
        ]:
            sync_layout.addWidget(self._field_label(label))
            sync_layout.addWidget(widget)
        sync_layout.addWidget(self.caldav_reuse_input)
        top.addWidget(sync, 1)
        layout.addLayout(top)

        actions = QHBoxLayout()
        save = QPushButton("Save settings")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save_settings)
        cloud = QPushButton("Sync cloud now")
        cloud.setObjectName("ghostButton")
        cloud.clicked.connect(self._sync_cloud_state)
        actions.addWidget(save)
        actions.addWidget(cloud)
        actions.addStretch(1)
        layout.addLayout(actions)

        info = self._editor_card()
        info_layout = info.layout()
        assert isinstance(info_layout, QVBoxLayout)
        info_layout.addWidget(self._section_heading("How this sync split works", "CalDAV is still only for tasks. The self-hosted Flask service stores the broader organizer JSON state."))
        for text in [
            "Tasks can be pushed to Baikal through VTODO sync and also exported to todo.txt.",
            "The Flask sync stores tasks, routines, projects, streaks, and library items for this app.",
            "Cloud sync intentionally does not carry your CalDAV password to the Flask backend.",
        ]:
            label = QLabel(text)
            label.setObjectName("bodyText")
            label.setWordWrap(True)
            info_layout.addWidget(label)
        layout.addWidget(info)
        layout.addStretch(1)
        return page

    def _editor_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("editorCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        return frame

    def _section_heading(self, title: str, body: str) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        body_label = QLabel(body)
        body_label.setObjectName("bodyText")
        body_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(body_label)
        return wrapper

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _make_scroll_section(self, title: str) -> dict[str, object]:
        frame = self._editor_card()
        layout = frame.layout()
        assert isinstance(layout, QVBoxLayout)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("contentScroll")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return {"frame": frame, "layout": content_layout}

    def _replace_cards(self, section: dict[str, object], cards: list[QWidget], empty: str) -> None:
        layout = section["layout"]
        assert isinstance(layout, QVBoxLayout)
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not cards:
            label = QLabel(empty)
            label.setObjectName("bodyText")
            label.setWordWrap(True)
            layout.addWidget(label)
        else:
            for card in cards:
                layout.addWidget(card)
        layout.addStretch(1)

    def _apply_window_effects(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(46)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.shell.setGraphicsEffect(shadow)

    def _apply_styles(self) -> None:
        self.theme = self._resolved_theme(load_theme_palette())
        theme = self.theme
        self.ui_font = detect_font(theme.ui_font_family, "Rubik", "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font(theme.display_font_family, theme.serif_font_family, "Outfit", self.ui_font)
        self.mono_font = detect_font(theme.mono_font_family, "JetBrains Mono", "DejaVu Sans Mono", "Monospace")
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QMainWindow {{
                background: {blend(theme.background, theme.surface, 0.2)};
            }}
            QFrame#shell {{
                background: {rgba(theme.surface_container, 0.90)};
                border: 1px solid {rgba(theme.outline, 0.24)};
                border-radius: 32px;
            }}
            QFrame#sidebar {{
                background: {rgba(theme.surface_container_high, 0.72)};
                border-right: 1px solid {rgba(theme.outline, 0.16)};
                border-top-left-radius: 32px;
                border-bottom-left-radius: 32px;
            }}
            QFrame#editorCard, QFrame#itemCard, QFrame#metricCard {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                border-radius: 24px;
            }}
            QFrame#heroCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {rgba(theme.primary_container, 0.97)},
                    stop:0.58 {rgba(blend(theme.primary, theme.secondary, 0.38), 0.92)},
                    stop:1 {rgba(theme.surface_container_high, 0.98)});
                border: 1px solid {rgba(theme.primary, 0.34)};
                border-radius: 28px;
            }}
            QLabel#brandIcon {{
                color: rgba(255, 255, 255, 0.98);
                font-family: "{self.material_font}";
                font-size: 24px;
            }}
            QLabel#brandTitle {{
                color: {theme.text};
                font-family: "{self.display_font}";
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#pageKicker {{
                color: {rgba(theme.primary, 0.84)};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 2px;
            }}
            QLabel#pageTitle {{
                color: {theme.text};
                font-family: "{self.display_font}";
                font-size: 28px;
                font-weight: 700;
            }}
            QLabel#bodyText, QLabel#statusText {{
                color: {theme.text_muted};
            }}
            QLabel#heroTitle {{
                color: {theme.on_primary_container};
                font-family: "{self.display_font}";
                font-size: 25px;
                font-weight: 700;
            }}
            QLabel#heroBody {{
                color: {rgba(theme.on_primary_container, 0.82)};
            }}
            QLabel#heroCountdown {{
                background: {rgba(theme.surface, 0.22)};
                border: 1px solid {rgba(theme.on_primary, 0.24)};
                border-radius: 20px;
                color: {theme.on_primary};
                font-family: "{self.mono_font}";
                font-size: 22px;
                font-weight: 700;
                padding: 12px 18px;
            }}
            QLabel#clockBadge {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                border-radius: 18px;
                color: {theme.text};
                padding: 10px 14px;
                font-family: "{self.mono_font}";
                font-size: 12px;
            }}
            QLabel#sectionTitle, QLabel#itemTitle {{
                color: {theme.text};
                font-weight: 700;
            }}
            QLabel#fieldLabel, QLabel#metricEyebrow {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#navTitle {{
                color: rgba(255, 255, 255, 0.98);
                font-weight: 700;
            }}
            QLabel#navSubtitle {{
                color: rgba(255, 255, 255, 0.74);
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#metricValue {{
                color: {theme.text};
                font-family: "{self.display_font}";
                font-size: 24px;
                font-weight: 700;
            }}
            QLabel#metricIcon, QLabel#navIcon {{
                color: rgba(255, 255, 255, 0.98);
                font-family: "{self.material_font}";
                font-size: 19px;
            }}
            QLabel#badge {{
                background: {rgba(theme.primary, 0.14)};
                border: 1px solid {rgba(theme.primary, 0.24)};
                border-radius: 13px;
                color: {theme.primary};
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton#navButton {{
                background: {rgba(theme.surface, 0.20)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 20px;
                text-align: left;
            }}
            QPushButton#navButton:hover {{
                background: {rgba(theme.primary, 0.14)};
                border-color: {rgba(theme.primary, 0.22)};
            }}
            QPushButton#navButton[active="true"] {{
                background: {rgba(theme.primary, 0.18)};
                border-color: {rgba(theme.primary, 0.24)};
            }}
            QSlider#dashboardCarousel {{
                min-height: 20px;
            }}
            QSlider#dashboardCarousel::groove:horizontal {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                height: 8px;
                border-radius: 4px;
            }}
            QSlider#dashboardCarousel::handle:horizontal {{
                background: {theme.primary};
                border: none;
                width: 28px;
                margin: -6px 0;
                border-radius: 14px;
            }}
            QPushButton#primaryButton {{
                background: {theme.primary};
                border: none;
                border-radius: 18px;
                color: {theme.active_text};
                min-height: 40px;
                padding: 0 16px;
                font-weight: 700;
            }}
            QPushButton#ghostButton {{
                background: {rgba(theme.surface_container, 0.62)};
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 16px;
                color: {theme.text};
                min-height: 36px;
                padding: 0 14px;
                font-weight: 600;
            }}
            QPushButton#ghostButton:hover, QPushButton#primaryButton:hover {{
                border-color: {rgba(theme.primary, 0.22)};
            }}
            QLineEdit, QTextEdit, QComboBox, QDateTimeEdit, QTimeEdit, QSpinBox {{
                background: {rgba(theme.surface, 0.18)};
                border: 1px solid {rgba(theme.outline, 0.22)};
                border-radius: 16px;
                padding: 10px 12px;
                color: {theme.text};
                selection-background-color: {theme.primary};
                selection-color: {theme.active_text};
            }}
            QTextEdit {{
                padding: 12px;
            }}
            QCheckBox {{
                color: {theme.text};
                spacing: 8px;
            }}
            QScrollArea#contentScroll {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {rgba(theme.primary, 0.24)};
                border-radius: 5px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0;
            }}
            """
        )

    def _set_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        titles = [
            ("Overview", "A calm command center for home, study, recovery, and projects."),
            ("Tasks", "Track chores, life admin, and study actions in one place."),
            ("Routines", "Build repeatable blocks for showers, trash day, workouts, and deep work."),
            ("Projects", "Keep personal and study projects moving without extra tool sprawl."),
            ("Recovery", "Track days since harmful behaviors and keep a visible streak."),
            ("Library", "Remember what you're currently watching or reading."),
            ("Settings", "Matugen-aware theming plus split CalDAV and cloud sync."),
        ]
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])
        for idx, button in enumerate(self.nav_buttons):
            button.set_active(idx == index)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_dashboard_columns_layout()

    def eventFilter(self, watched, event):  # type: ignore[override]
        if watched is self.sidebar:
            if event.type() == QEvent.Type.Enter:
                self.sidebar_close_timer.stop()
                self._set_sidebar_collapsed(False)
            elif event.type() == QEvent.Type.Leave:
                self.sidebar_close_timer.start(3000)
        return super().eventFilter(watched, event)

    def _set_sidebar_collapsed(self, collapsed: bool, animate: bool = True) -> None:
        target_width = self.sidebar_collapsed_width if collapsed else self.sidebar_expanded_width
        for button in self.nav_buttons:
            button.set_collapsed(collapsed)
        self.brand_title.setVisible(not collapsed)
        self.brand_body.setVisible(not collapsed)
        self.status_label.setVisible(not collapsed)
        self.brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter if collapsed else Qt.AlignmentFlag.AlignLeft)
        if animate:
            for animation in (self.sidebar_min_animation, self.sidebar_max_animation):
                animation.stop()
            self.sidebar_min_animation.setStartValue(self.sidebar.minimumWidth())
            self.sidebar_min_animation.setEndValue(target_width)
            self.sidebar_max_animation.setStartValue(self.sidebar.maximumWidth())
            self.sidebar_max_animation.setEndValue(target_width)
            self.sidebar_min_animation.start()
            self.sidebar_max_animation.start()
        else:
            self.sidebar.setMinimumWidth(target_width)
            self.sidebar.setMaximumWidth(target_width)

    def _update_dashboard_columns_layout(self) -> None:
        if not hasattr(self, "dashboard_columns_layout"):
            return
        layout = self.dashboard_columns_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        compact = self.width() <= self.dashboard_compact_threshold
        if compact:
            self.dashboard_carousel.setVisible(True)
            start_index = self.dashboard_carousel.value()
            visible_frames = self.dashboard_section_frames[start_index : start_index + 2]
        else:
            self.dashboard_carousel.setVisible(False)
            self.dashboard_carousel.setValue(0)
            visible_frames = self.dashboard_section_frames
        for frame in visible_frames:
            frame.setParent(self.dashboard_columns_host)
            layout.addWidget(frame, 1)

    def _refresh_all(self) -> None:
        self._refresh_clock()
        self._refresh_status()
        self._refresh_dashboard()
        self._refresh_tasks()
        self._refresh_routines()
        self._refresh_projects()
        self._refresh_streaks()
        self._refresh_resources()

    def _refresh_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%a %d %b  %H:%M:%S"))

    def _tick(self) -> None:
        self._refresh_clock()
        self._refresh_dashboard()
        self._maybe_notify_next_routine()

    def _reload_theme_if_needed(self) -> None:
        current = palette_mtime()
        if current == self._theme_mtime and self.state.settings.appearance_mode != "follow":
            return
        self._theme_mtime = current
        self.base_theme = load_theme_palette()
        self._apply_styles()
        self._refresh_all()

    def _refresh_status(self) -> None:
        self.status_label.setText(
            f"{sum(not item.done for item in self.state.tasks)} open task(s)\n"
            f"{len(self.state.routines)} routine block(s)\n"
            f"{len([item for item in self.state.projects if item.status != 'Done'])} active project(s)\n"
            f"{len(self.state.streaks)} streak(s) tracked"
        )

    def _today_routine_minutes(self) -> int:
        total = 0
        today = datetime.now().weekday()
        for entry in self.state.routines:
            if entry.weekday != today:
                continue
            start = parse_time_value(entry.start_time, time(0, 0))
            end = parse_time_value(entry.end_time, time(0, 0))
            delta = datetime.combine(date.today(), end) - datetime.combine(date.today(), start)
            total += max(0, int(delta.total_seconds() // 60))
        return total

    def _next_routine(self) -> tuple[RoutineEntry | None, datetime | None]:
        upcoming: list[tuple[datetime, RoutineEntry]] = []
        ref = datetime.now()
        for entry in self.state.routines:
            entry_time = parse_time_value(entry.start_time, time(8, 0))
            days_ahead = (entry.weekday - ref.weekday()) % 7
            start = datetime.combine((ref + timedelta(days=days_ahead)).date(), entry_time)
            if start < ref:
                start += timedelta(days=7)
            upcoming.append((start, entry))
        if not upcoming:
            return None, None
        next_start, entry = min(upcoming, key=lambda item: item[0])
        return entry, next_start

    def _refresh_dashboard(self) -> None:
        next_entry, next_start = self._next_routine()
        if next_entry is None or next_start is None:
            self.hero_title.setText("No routine blocks yet")
            self.hero_meta.setText("Add recurring life blocks like shower, trash, work, or study.")
            self.hero_countdown.setText("--:--:--")
        else:
            self.hero_title.setText(next_entry.title)
            details = [f"{WEEKDAYS[next_entry.weekday]} at {next_entry.start_time[:5]}", next_entry.area]
            if next_entry.location.strip():
                details.append(next_entry.location.strip())
            self.hero_meta.setText("  •  ".join(details))
            self.hero_countdown.setText(format_countdown(next_start - datetime.now()))
        current = next((item for item in self.state.resources if item.current), None)
        self.hero_focus.setText(
            f"Current focus: {current.kind} • {current.title} • {current.progress}%"
            if current
            else "No current library item selected."
        )
        best_streak = max(self.state.streaks, key=lambda item: days_since(item.last_reset_at), default=None)
        self.metric_tasks.set_content(str(sum(not item.done for item in self.state.tasks)), "Life, home, and study tasks still open")
        minutes = self._today_routine_minutes()
        self.metric_routines.set_content(f"{minutes // 60}h {minutes % 60:02d}m", "Planned recurring routine today")
        self.metric_projects.set_content(str(len([item for item in self.state.projects if item.status != 'Done'])), "Projects still in motion")
        self.metric_streak.set_content(
            f"{days_since(best_streak.last_reset_at)}d" if best_streak else "0d",
            best_streak.label if best_streak else "No streak tracked yet",
        )

        task_cards = [self._task_card(item) for item in sorted(self.state.tasks, key=lambda t: (t.done, parse_iso_datetime(t.due_at) or datetime.max))[:5]]
        routine_cards = [self._routine_card(item) for item in sorted(self.state.routines, key=lambda r: (r.weekday, r.start_time))[:5]]
        streak_cards = [self._streak_card(item) for item in sorted(self.state.streaks, key=lambda s: -days_since(s.last_reset_at))[:5]]
        self._replace_cards(self.dashboard_tasks, task_cards, "No tasks yet.")
        self._replace_cards(self.dashboard_routines, routine_cards, "No routines scheduled yet.")
        self._replace_cards(self.dashboard_streaks, streak_cards, "No recovery streaks tracked yet.")

    def _task_card(self, task: OrganizerTask) -> QWidget:
        card = ItemCard(task.title, f"P{task.priority}")
        meta = QLabel(f"{task.area}  •  {due_label(task)}  •  {task.source}")
        meta.setObjectName("bodyText")
        card.layout.addWidget(meta)
        if task.project.strip():
            project = QLabel(f"Project: {task.project}")
            project.setObjectName("bodyText")
            card.layout.addWidget(project)
        if task.notes.strip():
            notes = QLabel(task.notes.strip())
            notes.setObjectName("bodyText")
            notes.setWordWrap(True)
            card.layout.addWidget(notes)
        button = QPushButton("Edit")
        button.setObjectName("ghostButton")
        button.clicked.connect(lambda: self._load_task(task.id))
        card.layout.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)
        return card

    def _routine_card(self, routine: RoutineEntry) -> QWidget:
        card = ItemCard(routine.title, routine.area)
        meta = QLabel(f"{WEEKDAYS[routine.weekday]}  •  {routine.start_time[:5]}-{routine.end_time[:5]}")
        meta.setObjectName("bodyText")
        card.layout.addWidget(meta)
        if routine.location.strip():
            location = QLabel(routine.location.strip())
            location.setObjectName("bodyText")
            card.layout.addWidget(location)
        if routine.notes.strip():
            notes = QLabel(routine.notes.strip())
            notes.setObjectName("bodyText")
            notes.setWordWrap(True)
            card.layout.addWidget(notes)
        button = QPushButton("Edit")
        button.setObjectName("ghostButton")
        button.clicked.connect(lambda: self._load_routine(routine.id))
        card.layout.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)
        return card

    def _project_card(self, project: ProjectItem) -> QWidget:
        card = ItemCard(project.name, project.status)
        if project.next_step.strip():
            next_step = QLabel(f"Next: {project.next_step}")
            next_step.setObjectName("bodyText")
            next_step.setWordWrap(True)
            card.layout.addWidget(next_step)
        if project.deadline.strip():
            deadline = QLabel(f"Deadline: {project.deadline}")
            deadline.setObjectName("bodyText")
            card.layout.addWidget(deadline)
        if project.notes.strip():
            notes = QLabel(project.notes.strip())
            notes.setObjectName("bodyText")
            notes.setWordWrap(True)
            card.layout.addWidget(notes)
        button = QPushButton("Edit")
        button.setObjectName("ghostButton")
        button.clicked.connect(lambda: self._load_project(project.id))
        card.layout.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)
        return card

    def _streak_card(self, streak: StreakItem) -> QWidget:
        card = ItemCard(streak.label, f"{days_since(streak.last_reset_at)}d")
        meta = QLabel(streak.category)
        meta.setObjectName("bodyText")
        card.layout.addWidget(meta)
        if streak.notes.strip():
            notes = QLabel(streak.notes.strip())
            notes.setObjectName("bodyText")
            notes.setWordWrap(True)
            card.layout.addWidget(notes)
        actions = QHBoxLayout()
        reset = QPushButton("Reset now")
        reset.setObjectName("ghostButton")
        reset.clicked.connect(lambda: self._reset_streak_now(streak.id))
        edit = QPushButton("Edit")
        edit.setObjectName("ghostButton")
        edit.clicked.connect(lambda: self._load_streak(streak.id))
        actions.addWidget(reset)
        actions.addWidget(edit)
        card.layout.addLayout(actions)
        return card

    def _resource_card(self, resource: ResourceItem) -> QWidget:
        card = ItemCard(resource.title, resource.kind)
        meta = QLabel(f"Progress {resource.progress}%  •  {'Current focus' if resource.current else 'Queued'}")
        meta.setObjectName("bodyText")
        card.layout.addWidget(meta)
        if resource.link.strip():
            link = QLabel(resource.link.strip())
            link.setObjectName("bodyText")
            link.setWordWrap(True)
            card.layout.addWidget(link)
        if resource.notes.strip():
            notes = QLabel(resource.notes.strip())
            notes.setObjectName("bodyText")
            notes.setWordWrap(True)
            card.layout.addWidget(notes)
        button = QPushButton("Edit")
        button.setObjectName("ghostButton")
        button.clicked.connect(lambda: self._load_resource(resource.id))
        card.layout.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)
        return card

    def _refresh_tasks(self) -> None:
        ordered = sorted(self.state.tasks, key=lambda t: (t.done, parse_iso_datetime(t.due_at) or datetime.max, t.priority, t.title.lower()))
        self._replace_cards(self.tasks_section, [self._task_card(item) for item in ordered], "No tasks yet.")

    def _refresh_routines(self) -> None:
        ordered = sorted(self.state.routines, key=lambda r: (r.weekday, r.start_time))
        self._replace_cards(self.routines_section, [self._routine_card(item) for item in ordered], "No routines yet.")

    def _refresh_projects(self) -> None:
        ordered = sorted(self.state.projects, key=lambda p: (p.status == "Done", p.name.lower()))
        self._replace_cards(self.projects_section, [self._project_card(item) for item in ordered], "No projects yet.")

    def _refresh_streaks(self) -> None:
        ordered = sorted(self.state.streaks, key=lambda s: -days_since(s.last_reset_at))
        self._replace_cards(self.streaks_section, [self._streak_card(item) for item in ordered], "No streaks yet.")

    def _refresh_resources(self) -> None:
        ordered = sorted(self.state.resources, key=lambda r: (not r.current, r.kind, r.title.lower()))
        self._replace_cards(self.resources_section, [self._resource_card(item) for item in ordered], "No library items yet.")

    def _save_all(self) -> None:
        save_state(self.state)
        self._refresh_all()

    def _reset_task_form(self) -> None:
        self.selected_task_id = ""
        self.task_title_input.clear()
        self.task_area_input.setCurrentText("Life")
        self.task_project_input.clear()
        self.task_due_toggle.setChecked(False)
        self.task_due_input.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.task_priority_input.setCurrentIndex(2)
        self.task_tags_input.clear()
        self.task_notes_input.clear()
        self.task_save_button.setText("Add task")

    def _save_task(self) -> None:
        title = self.task_title_input.text().strip()
        if not title:
            self.status_label.setText("Task title cannot be empty.")
            return
        task = next((item for item in self.state.tasks if item.id == self.selected_task_id), None)
        if task is None:
            task = OrganizerTask(id=str(uuid.uuid4()), title=title)
            self.state.tasks.append(task)
        task.title = title
        task.area = self.task_area_input.currentText()
        task.project = self.task_project_input.text().strip()
        task.due_at = self.task_due_input.dateTime().toPyDateTime().replace(second=0, microsecond=0).isoformat() if self.task_due_toggle.isChecked() else ""
        task.priority = int(self.task_priority_input.currentText().split(" ", 1)[0])
        task.tags = [part.strip() for part in self.task_tags_input.text().split(",") if part.strip()]
        task.notes = self.task_notes_input.toPlainText().strip()
        task.updated_at = now_iso()
        self._save_all()
        self._reset_task_form()

    def _load_task(self, task_id: str) -> None:
        task = next((item for item in self.state.tasks if item.id == task_id), None)
        if task is None:
            return
        self.selected_task_id = task.id
        self.task_title_input.setText(task.title)
        self.task_area_input.setCurrentText(task.area)
        self.task_project_input.setText(task.project)
        has_due = parse_iso_datetime(task.due_at) is not None
        self.task_due_toggle.setChecked(has_due)
        if has_due:
            self.task_due_input.setDateTime(QDateTime(parse_iso_datetime(task.due_at)))
        self.task_priority_input.setCurrentIndex(max(0, min(4, task.priority - 1)))
        self.task_tags_input.setText(", ".join(task.tags))
        self.task_notes_input.setPlainText(task.notes)
        self.task_save_button.setText("Update task")
        self._set_page(1)

    def _reset_routine_form(self) -> None:
        self.selected_routine_id = ""
        self.routine_title_input.clear()
        self.routine_area_input.setCurrentText("Routine")
        self.routine_weekday_input.setCurrentIndex(datetime.now().weekday())
        self.routine_start_input.setTime(QTime(7, 0))
        self.routine_end_input.setTime(QTime(7, 30))
        self.routine_location_input.clear()
        self.routine_notify_input.setValue(10)
        self.routine_notes_input.clear()
        self.routine_save_button.setText("Add routine")

    def _save_routine(self) -> None:
        title = self.routine_title_input.text().strip()
        if not title:
            self.status_label.setText("Routine title cannot be empty.")
            return
        routine = next((item for item in self.state.routines if item.id == self.selected_routine_id), None)
        if routine is None:
            routine = RoutineEntry(id=str(uuid.uuid4()), title=title, weekday=0, start_time="08:00:00", end_time="09:00:00")
            self.state.routines.append(routine)
        routine.title = title
        routine.area = self.routine_area_input.currentText()
        routine.weekday = self.routine_weekday_input.currentIndex()
        routine.start_time = self.routine_start_input.time().toString("HH:mm:ss")
        routine.end_time = self.routine_end_input.time().toString("HH:mm:ss")
        routine.location = self.routine_location_input.text().strip()
        routine.notify_minutes = self.routine_notify_input.value()
        routine.notes = self.routine_notes_input.toPlainText().strip()
        routine.updated_at = now_iso()
        self._save_all()
        self._reset_routine_form()

    def _load_routine(self, routine_id: str) -> None:
        routine = next((item for item in self.state.routines if item.id == routine_id), None)
        if routine is None:
            return
        self.selected_routine_id = routine.id
        self.routine_title_input.setText(routine.title)
        self.routine_area_input.setCurrentText(routine.area)
        self.routine_weekday_input.setCurrentIndex(routine.weekday)
        self.routine_start_input.setTime(QTime.fromString(routine.start_time, "HH:mm:ss"))
        self.routine_end_input.setTime(QTime.fromString(routine.end_time, "HH:mm:ss"))
        self.routine_location_input.setText(routine.location)
        self.routine_notify_input.setValue(routine.notify_minutes)
        self.routine_notes_input.setPlainText(routine.notes)
        self.routine_save_button.setText("Update routine")
        self._set_page(2)

    def _reset_project_form(self) -> None:
        self.selected_project_id = ""
        self.project_name_input.clear()
        self.project_status_input.setCurrentText("Planning")
        self.project_next_step_input.clear()
        self.project_deadline_toggle.setChecked(False)
        self.project_deadline_input.setDateTime(QDateTime.currentDateTime().addDays(7))
        self.project_notes_input.clear()
        self.project_save_button.setText("Add project")

    def _save_project(self) -> None:
        name = self.project_name_input.text().strip()
        if not name:
            self.status_label.setText("Project name cannot be empty.")
            return
        project = next((item for item in self.state.projects if item.id == self.selected_project_id), None)
        if project is None:
            project = ProjectItem(id=str(uuid.uuid4()), name=name)
            self.state.projects.append(project)
        project.name = name
        project.status = self.project_status_input.currentText()
        project.next_step = self.project_next_step_input.text().strip()
        project.deadline = self.project_deadline_input.dateTime().toPyDateTime().replace(second=0, microsecond=0).isoformat() if self.project_deadline_toggle.isChecked() else ""
        project.notes = self.project_notes_input.toPlainText().strip()
        project.updated_at = now_iso()
        self._save_all()
        self._reset_project_form()

    def _load_project(self, project_id: str) -> None:
        project = next((item for item in self.state.projects if item.id == project_id), None)
        if project is None:
            return
        self.selected_project_id = project.id
        self.project_name_input.setText(project.name)
        self.project_status_input.setCurrentText(project.status)
        self.project_next_step_input.setText(project.next_step)
        has_deadline = parse_iso_datetime(project.deadline) is not None
        self.project_deadline_toggle.setChecked(has_deadline)
        if has_deadline:
            self.project_deadline_input.setDateTime(QDateTime(parse_iso_datetime(project.deadline)))
        self.project_notes_input.setPlainText(project.notes)
        self.project_save_button.setText("Update project")
        self._set_page(3)

    def _reset_streak_form(self) -> None:
        self.selected_streak_id = ""
        self.streak_label_input.clear()
        self.streak_category_input.setCurrentText("Addiction control")
        self.streak_last_reset_input.setDateTime(QDateTime.currentDateTime().addDays(-1))
        self.streak_notes_input.clear()
        self.streak_save_button.setText("Add streak")

    def _save_streak(self) -> None:
        label = self.streak_label_input.text().strip()
        if not label:
            self.status_label.setText("Streak label cannot be empty.")
            return
        streak = next((item for item in self.state.streaks if item.id == self.selected_streak_id), None)
        if streak is None:
            streak = StreakItem(id=str(uuid.uuid4()), label=label, last_reset_at=now_iso())
            self.state.streaks.append(streak)
        streak.label = label
        streak.category = self.streak_category_input.currentText()
        streak.last_reset_at = self.streak_last_reset_input.dateTime().toPyDateTime().replace(second=0, microsecond=0).isoformat()
        streak.notes = self.streak_notes_input.toPlainText().strip()
        streak.updated_at = now_iso()
        self._save_all()
        self._reset_streak_form()

    def _load_streak(self, streak_id: str) -> None:
        streak = next((item for item in self.state.streaks if item.id == streak_id), None)
        if streak is None:
            return
        self.selected_streak_id = streak.id
        self.streak_label_input.setText(streak.label)
        self.streak_category_input.setCurrentText(streak.category)
        self.streak_last_reset_input.setDateTime(QDateTime(parse_iso_datetime(streak.last_reset_at) or datetime.now()))
        self.streak_notes_input.setPlainText(streak.notes)
        self.streak_save_button.setText("Update streak")
        self._set_page(4)

    def _reset_streak_now(self, streak_id: str) -> None:
        streak = next((item for item in self.state.streaks if item.id == streak_id), None)
        if streak is None:
            return
        streak.last_reset_at = now_iso()
        streak.updated_at = now_iso()
        self._save_all()

    def _record_streak_reset_now(self) -> None:
        if not self.selected_streak_id:
            self.streak_last_reset_input.setDateTime(QDateTime.currentDateTime())
            return
        self._reset_streak_now(self.selected_streak_id)

    def _reset_resource_form(self) -> None:
        self.selected_resource_id = ""
        self.resource_kind_input.setCurrentText("Udemy")
        self.resource_title_input.clear()
        self.resource_link_input.clear()
        self.resource_progress_input.setValue(0)
        self.resource_current_input.setChecked(True)
        self.resource_notes_input.clear()
        self.resource_save_button.setText("Add item")

    def _save_resource(self) -> None:
        title = self.resource_title_input.text().strip()
        if not title:
            self.status_label.setText("Library item title cannot be empty.")
            return
        resource = next((item for item in self.state.resources if item.id == self.selected_resource_id), None)
        if resource is None:
            resource = ResourceItem(id=str(uuid.uuid4()), kind="Other", title=title)
            self.state.resources.append(resource)
        if self.resource_current_input.isChecked():
            for item in self.state.resources:
                item.current = False
        resource.kind = self.resource_kind_input.currentText()
        resource.title = title
        resource.link = self.resource_link_input.text().strip()
        resource.progress = self.resource_progress_input.value()
        resource.current = self.resource_current_input.isChecked()
        resource.notes = self.resource_notes_input.toPlainText().strip()
        resource.updated_at = now_iso()
        self._save_all()
        self._reset_resource_form()

    def _load_resource(self, resource_id: str) -> None:
        resource = next((item for item in self.state.resources if item.id == resource_id), None)
        if resource is None:
            return
        self.selected_resource_id = resource.id
        self.resource_kind_input.setCurrentText(resource.kind)
        self.resource_title_input.setText(resource.title)
        self.resource_link_input.setText(resource.link)
        self.resource_progress_input.setValue(resource.progress)
        self.resource_current_input.setChecked(resource.current)
        self.resource_notes_input.setPlainText(resource.notes)
        self.resource_save_button.setText("Update item")
        self._set_page(5)

    def _save_settings(self) -> None:
        self.state.settings.appearance_mode = self.appearance_mode_input.currentText()
        self.state.settings.custom_accent = clamp_hex(self.custom_accent_input.text(), self.state.settings.custom_accent)
        self.state.settings.notify_lead_minutes = self.notify_lead_input.value()
        self.state.settings.todo_txt_path = self.todo_path_input.text().strip() or str(Path.home() / "todo.txt")
        self.state.settings.reuse_calendar_credentials = self.caldav_reuse_input.isChecked()
        self.state.settings.caldav_tasks_url = self.caldav_url_input.text().strip()
        self.state.settings.caldav_username = self.caldav_user_input.text().strip()
        self.state.settings.caldav_password = self.caldav_password_input.text()
        self.state.settings.sync_base_url = self.sync_url_input.text().strip().rstrip("/")
        self.state.settings.sync_api_key = self.sync_key_input.text().strip()
        self.state.settings.sync_device_name = self.sync_device_input.text().strip() or "desktop"
        save_state(self.state)
        self._apply_styles()
        self._refresh_all()
        self.status_label.setText("Settings saved.")

    def _import_todo_txt(self) -> None:
        path = Path(self.state.settings.todo_txt_path).expanduser()
        if not path.exists():
            self.status_label.setText(f"todo.txt not found at {path}")
            return
        imported = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            task = parse_todo_txt_line(line)
            if task is None:
                continue
            if any(existing.title == task.title and existing.due_at == task.due_at for existing in self.state.tasks):
                continue
            self.state.tasks.append(task)
            imported += 1
        self._save_all()
        self.status_label.setText(f"Imported {imported} task(s) from todo.txt.")

    def _export_todo_txt(self) -> None:
        path = Path(self.state.settings.todo_txt_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [to_todo_txt_line(task) for task in sorted(self.state.tasks, key=lambda t: (t.done, t.title.lower()))]
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        self.status_label.setText(f"Exported {len(lines)} task(s) to {path}.")

    def _sync_caldav_tasks(self) -> None:
        if self.caldav_worker is not None and self.caldav_worker.isRunning():
            self.status_label.setText("CalDAV sync is already running.")
            return
        self.status_label.setText("Syncing tasks with CalDAV…")
        self.caldav_worker = CalDAVSyncWorker(self.state.tasks, self.state.settings)
        self.caldav_worker.synced.connect(self._on_caldav_synced)
        self.caldav_worker.failed.connect(lambda message: self.status_label.setText(f"CalDAV sync failed: {message}"))
        self.caldav_worker.start()

    def _on_caldav_synced(self, tasks: list, message: str) -> None:
        self.state.tasks = [item if isinstance(item, OrganizerTask) else OrganizerTask(**item) for item in tasks]
        self._save_all()
        self.status_label.setText(message)

    def _sync_cloud_state(self) -> None:
        if self.cloud_worker is not None and self.cloud_worker.isRunning():
            self.status_label.setText("Cloud sync is already running.")
            return
        self.status_label.setText("Syncing organizer state to Flask backend…")
        self.cloud_worker = CloudSyncWorker(self.state)
        self.cloud_worker.synced.connect(self._on_cloud_synced)
        self.cloud_worker.failed.connect(lambda message: self.status_label.setText(f"Cloud sync failed: {message}"))
        self.cloud_worker.start()

    def _on_cloud_synced(self, payload: dict, message: str) -> None:
        self.state = apply_cloud_payload(self.state, payload)
        save_state(self.state)
        self._apply_styles()
        self._refresh_all()
        self.status_label.setText(message)

    def _maybe_notify_next_routine(self) -> None:
        entry, start = self._next_routine()
        if entry is None or start is None:
            return
        lead = max(1, entry.notify_minutes or self.state.settings.notify_lead_minutes)
        delta = start - datetime.now()
        if timedelta() < delta <= timedelta(minutes=lead):
            key = f"{entry.id}:{start.isoformat()}"
            if key == self._last_notice_key:
                return
            body_bits = [f"Starts at {start:%A %H:%M}", entry.area]
            if entry.location.strip():
                body_bits.append(entry.location.strip())
            self._notify("Next routine block", " • ".join(body_bits))
            self._last_notice_key = key

    def _notify(self, title: str, body: str) -> None:
        try:
            subprocess.Popen(
                ["notify-send", title, body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    app.setStyle("Fusion")
    window = OrganizerWindow()
    window.show()
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
