from __future__ import annotations

from PyQt6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTextCharFormat, QPalette
from PyQt6.QtWidgets import QApplication, QButtonGroup, QDialog, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget, QVBoxLayout, QWidget

from app_locale import t
from notif_center.ha import *
from notif_center.game_carousel import *
from notif_center.paths import *
from notif_center.poller import *
from notif_center.settings_io import *
from notif_center.utils import *
from notif_center.widgets import *
from pyqt.shared.calendar_card import *
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family
from pyqt.shared.runtime import entry_command, entry_patterns, python_executable
from notif_center.plugin_paths import QCAL_WRAPPER


def load_calendar_events(limit: int = 30) -> list[dict]:
    try:
        if CALENDAR_EVENTS_CACHE.exists():
            payload = json.loads(CALENDAR_EVENTS_CACHE.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                events = payload.get("events", [])
                if isinstance(events, list) and events:
                    return [item for item in events if isinstance(item, dict)][:limit]
                err = str(payload.get("error", "")).strip()
                if err:
                    return [{"title": t("events.sync_failed.meta"), "location": t("events.sync_failed.body"), "start": err, "source": "calendar"}][:limit]
    except Exception:
        pass
    if not QCAL_WRAPPER.exists():
        return []
    try:
        result = subprocess.run(
            [python_executable(), str(QCAL_WRAPPER), "list", "--days", "14", "--limit", str(max(1, int(limit)))],
            capture_output=True, text=True, timeout=20.0, check=False,
        )
        payload = json.loads(result.stdout or "{}")
    except Exception as exc:
        return [{"title": t("events.sync_failed.meta"), "location": t("events.sync_failed.body"), "start": str(exc).strip() or "Unable to fetch events.", "source": "calendar"}][:limit]
    if isinstance(payload, dict):
        events = payload.get("events", [])
        if isinstance(events, list) and events:
            return [item for item in events if isinstance(item, dict)][:limit]
        err = str(payload.get("error", "")).strip()
        if err:
            return [{"title": t("events.sync_failed.meta"), "location": t("events.sync_failed.body"), "start": err, "source": "calendar"}][:limit]
    events = payload.get("events", []) if isinstance(payload, dict) else []
    if not isinstance(events, list):
        return []
    return [item for item in events if isinstance(item, dict)][:limit]



def load_notification_history(limit: int = 3) -> list[dict]:
    def _decode_octal_runs(raw_text: str) -> str:
        pattern = re.compile(r"(?:\\[0-7]{3})+")
        def _replace(match: re.Match[str]) -> str:
            run = match.group(0)
            octets = re.findall(r"\\([0-7]{3})", run)
            data = bytes(int(value, 8) for value in octets)
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("latin-1", errors="replace")
        return pattern.sub(_replace, raw_text)

    def _load_payload() -> object:
        try:
            raw = NOTIFICATION_HISTORY_FILE.read_text(encoding="utf-8")
        except Exception:
            return None
        try:
            return json.loads(raw)
        except Exception:
            try:
                return json.loads(_decode_octal_runs(raw))
            except Exception:
                return None

    def _value(raw_value: object) -> object:
        if isinstance(raw_value, dict):
            for key in ("data", "value", "id"):
                if key in raw_value:
                    return raw_value.get(key)
        return raw_value

    try:
        payload = _load_payload()
    except Exception:
        payload = None
    history: list[dict] = []
    if isinstance(payload, list):
        history = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        if payload.get("summary") or payload.get("body"):
            history.append({
                "id": payload.get("id", 0), "app_name": str(payload.get("app_name", "")),
                "summary": str(payload.get("summary", "")), "body": str(payload.get("body", "")),
                "icon": str(payload.get("icon", "")), "desktop_entry": str(payload.get("desktop_entry", "")),
                "timestamp": payload.get("timestamp", 0),
            })
        raw = payload.get("data", [])
        if isinstance(raw, list) and raw and isinstance(raw[0], list):
            for item in raw[0]:
                if not isinstance(item, dict):
                    continue
                history.append({
                    "id": _value(item.get("id", 0)),
                    "app_name": str(_value(item.get("app_name", item.get("appname", ""))) or ""),
                    "summary": str(_value(item.get("summary", "")) or ""),
                    "body": str(_value(item.get("body", "")) or ""),
                    "icon": str(_value(item.get("app_icon", item.get("icon", ""))) or ""),
                    "desktop_entry": str(_value(item.get("desktop_entry", "")) or ""),
                    "timestamp": _value(item.get("timestamp", 0)),
                })
    history = [item for item in history if item.get("summary") or item.get("body")]
    history.reverse()
    return history[:limit]



