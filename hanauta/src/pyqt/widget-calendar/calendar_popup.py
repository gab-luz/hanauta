#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"
QCAL_WRAPPER = HERE / "qcal-wrapper.py"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
REMINDERS_WIDGET_SCRIPT = APP_DIR / "pyqt" / "widget-reminders" / "reminders_widget.py"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command, python_executable
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba


MATERIAL_ICONS = {
    "settings": "\ue8b8",
    "refresh": "\ue5d5",
    "alarm_add": "\ue856",
    "notifications_active": "\ue7f7",
    "calendar_month": "\ue935",
    "event_upcoming": "\ue614",
    "schedule": "\ue8b5",
}


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
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


def _python_bin() -> str:
    return python_executable()


def _run_wrapper(*args: str) -> dict:
    try:
        command = entry_command(QCAL_WRAPPER, *args)
        if not command:
            return {"error": "Calendar command failed."}
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return {"error": str(exc)}

    if proc.returncode != 0 and not proc.stdout.strip():
        return {"error": proc.stderr.strip() or "Calendar command failed."}

    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": proc.stderr.strip() or "Calendar data could not be parsed."}


def load_settings_state() -> dict:
    default = {
        "calendar": {
            "show_week_numbers": False,
            "show_other_month_days": True,
            "first_day_of_week": "monday",
            "connected": False,
            "last_sync_status": "",
        },
        "reminders": {
            "default_lead_minutes": 20,
            "default_intensity": "discrete",
            "tracked_events": [],
        },
    }
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default
    calendar = payload.get("calendar", {})
    reminders = payload.get("reminders", {})
    if isinstance(calendar, dict):
        default["calendar"].update(calendar)
    if isinstance(reminders, dict):
        default["reminders"].update(reminders)
    if not isinstance(default["reminders"].get("tracked_events", []), list):
        default["reminders"]["tracked_events"] = []
    return default


def save_settings_state(settings: dict) -> None:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    payload["calendar"] = settings.get("calendar", {})
    payload["reminders"] = settings.get("reminders", {})
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_event_date(value: str) -> date:
    if "T" in value:
        return datetime.fromisoformat(value).date()
    return date.fromisoformat(value)


def format_event_time(event: dict) -> str:
    if event.get("allDay"):
        return "All day"

    start = event.get("start", "")
    end = event.get("end", "")
    if "T" not in start:
        return "Scheduled"

    start_dt = datetime.fromisoformat(start)
    label = start_dt.strftime("%H:%M")
    if "T" in end:
        end_dt = datetime.fromisoformat(end)
        if end_dt != start_dt:
            label += f" - {end_dt.strftime('%H:%M')}"
    return label


def human_day_label(day: date) -> str:
    today = date.today()
    if day == today:
        return "Today"
    if day == today + timedelta(days=1):
        return "Tomorrow"
    return day.strftime("%A, %d %b")


class CalendarDataWorker(QThread):
    loaded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self) -> None:
        events_data = _run_wrapper("list", "--days", "45")
        if events_data.get("error"):
            self.failed.emit(str(events_data["error"]))
            return

        calendars_data = _run_wrapper("calendars")
        if calendars_data.get("error"):
            calendars_data = {"calendars": []}

        self.loaded.emit(
            {
                "events": events_data.get("events", []),
                "count": events_data.get("count", 0),
                "calendars": calendars_data.get("calendars", []),
            }
        )


class EventCard(QFrame):
    remind_requested = pyqtSignal(dict)

    def __init__(self, event: dict, calendar_name: str, ui_font: str, display_font: str) -> None:
        super().__init__()
        self.event = event
        self.setObjectName("eventCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)
        title_wrap.setContentsMargins(0, 0, 0, 0)

        title = QLabel(event.get("title", "Untitled"))
        title.setObjectName("eventTitle")
        title.setFont(QFont(display_font, 12, QFont.Weight.DemiBold))
        title.setWordWrap(True)

        meta_parts = [part for part in (calendar_name, event.get("location", "")) if part]
        meta = QLabel("  •  ".join(meta_parts) if meta_parts else "Upcoming")
        meta.setObjectName("eventMeta")
        meta.setFont(QFont(ui_font, 9))
        meta.setWordWrap(True)

        title_wrap.addWidget(title)
        title_wrap.addWidget(meta)

        time_badge = QLabel(format_event_time(event))
        time_badge.setObjectName("timeBadge")
        time_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_badge.setFont(QFont(ui_font, 9, QFont.Weight.DemiBold))
        time_badge.setMinimumWidth(86)

        top.addLayout(title_wrap, 1)
        top.addWidget(time_badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        reminder_hint = QLabel("Track this event in widget-reminders")
        reminder_hint.setObjectName("eventHint")
        reminder_hint.setFont(QFont(ui_font, 9))

        remind_button = QPushButton("Remind me")
        remind_button.setObjectName("eventActionButton")
        remind_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        remind_button.setFont(QFont(ui_font, 9, QFont.Weight.DemiBold))
        remind_button.clicked.connect(lambda: self.remind_requested.emit(self.event))

        actions.addWidget(reminder_hint, 1)
        actions.addWidget(remind_button)
        layout.addLayout(actions)


class CalendarPopup(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.settings_state = load_settings_state()
        self.worker: CalendarDataWorker | None = None
        self._fade: QPropertyAnimation | None = None
        self._events: list[dict] = []
        self._calendars: dict[int, str] = {}
        self._events_by_day: dict[date, list[dict]] = defaultdict(list)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("Hanauta Calendar")
        self.setFixedSize(508, 704)

        self._build_ui()
        self._apply_calendar_preferences()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self.refresh_data()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.setContentsMargins(0, 0, 0, 0)

        eyebrow = QLabel("CALENDAR SUITE")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))

        title = QLabel("Monthly rhythm")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 24, QFont.Weight.DemiBold))

        self.subtitle = QLabel("Styled around your qcal events and reminder flow.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setFont(QFont(self.ui_font, 9))
        self.subtitle.setWordWrap(True)

        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_data)
        self.settings_button = self._icon_button("settings")
        self.settings_button.clicked.connect(self._open_settings)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.settings_button)
        header.addLayout(actions)
        layout.addLayout(header)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(14)

        hero_left = QVBoxLayout()
        hero_left.setSpacing(4)
        hero_left.setContentsMargins(0, 0, 0, 0)
        self.hero_title = QLabel("CalDAV ready")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 16, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setFont(QFont(self.ui_font, 9))
        self.hero_detail.setWordWrap(True)
        hero_left.addWidget(self.hero_title)
        hero_left.addWidget(self.hero_detail)

        hero_right = QVBoxLayout()
        hero_right.setSpacing(8)
        hero_right.setContentsMargins(0, 0, 0, 0)
        self.connection_badge = QLabel("")
        self.connection_badge.setObjectName("statBadge")
        self.connection_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_badge.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.tracked_badge = QLabel("")
        self.tracked_badge.setObjectName("statBadge")
        self.tracked_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tracked_badge.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        hero_right.addWidget(self.connection_badge)
        hero_right.addWidget(self.tracked_badge)
        hero_right.addStretch(1)

        hero_layout.addLayout(hero_left, 1)
        hero_layout.addLayout(hero_right)
        layout.addWidget(self.hero)

        self.calendar_frame = QFrame()
        self.calendar_frame.setObjectName("calendarFrame")
        calendar_layout = QVBoxLayout(self.calendar_frame)
        calendar_layout.setContentsMargins(16, 16, 16, 16)
        calendar_layout.setSpacing(10)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.setNavigationBarVisible(True)
        self.calendar.clicked.connect(self._handle_date_selected)
        self.calendar.selectionChanged.connect(self._refresh_events_for_selection)
        self.calendar.currentPageChanged.connect(self._refresh_calendar_markers)
        calendar_layout.addWidget(self.calendar)
        layout.addWidget(self.calendar_frame)

        selection_row = QHBoxLayout()
        selection_row.setSpacing(10)
        self.selection_title = QLabel("Today")
        self.selection_title.setObjectName("selectionTitle")
        self.selection_title.setFont(QFont(self.display_font, 16, QFont.Weight.DemiBold))
        selection_row.addWidget(self.selection_title, 1)

        self.count_badge = QLabel("0 events")
        self.count_badge.setObjectName("countBadge")
        self.count_badge.setFont(QFont(self.ui_font, 9, QFont.Weight.Medium))
        selection_row.addWidget(self.count_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(selection_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setFont(QFont(self.ui_font, 10))
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.events_container = QWidget()
        self.events_layout = QVBoxLayout(self.events_container)
        self.events_layout.setContentsMargins(0, 0, 0, 0)
        self.events_layout.setSpacing(10)
        self.events_layout.addStretch(1)

        self.scroll.setWidget(self.events_container)
        layout.addWidget(self.scroll, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.footer_hint = QLabel("Tracked events appear in widget-reminders with your chosen intensity.")
        self.footer_hint.setObjectName("footerHint")
        self.footer_hint.setFont(QFont(self.ui_font, 9))
        self.footer_hint.setWordWrap(True)
        footer.addWidget(self.footer_hint, 1)

        self.reminders_button = QPushButton("Open reminders")
        self.reminders_button.setObjectName("secondaryButton")
        self.reminders_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.reminders_button.clicked.connect(self._open_reminders_widget)
        footer.addWidget(self.reminders_button)
        layout.addLayout(footer)

        self._refresh_hero()

    def _icon_button(self, icon_name: str) -> QPushButton:
        button = QPushButton(material_icon(icon_name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(38, 38)
        button.setFont(QFont(self.icon_font, 18))
        return button

    def _apply_calendar_preferences(self) -> None:
        calendar_settings = self.settings_state.get("calendar", {})
        first_day = str(calendar_settings.get("first_day_of_week", "monday")).strip().lower()
        self.calendar.setFirstDayOfWeek(
            Qt.DayOfWeek.Sunday if first_day == "sunday" else Qt.DayOfWeek.Monday
        )
        self.calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers
            if bool(calendar_settings.get("show_week_numbers", False))
            else QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 130))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        x = available.x() + (available.width() - self.width()) // 2
        y = available.y() + 52
        self.move(x, y)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _apply_styles(self) -> None:
        theme = self.theme
        panel_bg = rgba(theme.surface_container, 0.97)
        outline = rgba(theme.outline, 0.20)
        text = theme.text
        muted = theme.text_muted
        primary = theme.primary
        soft_primary = rgba(primary, 0.16)
        card = rgba(theme.surface_container_high, 0.82)
        glass = rgba(theme.surface_container_high, 0.88)

        self.setStyleSheet(
            f"""
            QWidget {{
                color: {text};
                font-family: "{self.ui_font}";
            }}
            QFrame#panel {{
                background: {panel_bg};
                border: 1px solid {outline};
                border-radius: 30px;
            }}
            QLabel#eyebrow {{
                color: {primary};
                letter-spacing: 1.3px;
            }}
            QLabel#title, QLabel#selectionTitle, QLabel#heroTitle {{
                color: {text};
            }}
            QLabel#subtitle, QLabel#statusLabel, QLabel#heroDetail, QLabel#footerHint {{
                color: {muted};
            }}
            QFrame#heroCard {{
                background: {rgba(theme.surface_container_high, 0.90)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 22px;
            }}
            QLabel#statBadge, QLabel#countBadge, QLabel#timeBadge {{
                color: {primary};
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                padding: 6px 10px;
            }}
            QFrame#calendarFrame, QFrame#eventCard {{
                background: {card};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 22px;
            }}
            QLabel#eventMeta, QLabel#eventHint {{
                color: {muted};
            }}
            QCalendarWidget {{
                background: transparent;
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background: transparent;
            }}
            QCalendarWidget QToolButton {{
                color: {text};
                background: transparent;
                border: 0;
                padding: 8px;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
            }}
            QCalendarWidget QToolButton:hover {{
                background: {soft_primary};
            }}
            QCalendarWidget QMenu {{
                background: {card};
                color: {text};
                border: 1px solid {outline};
            }}
            QCalendarWidget QSpinBox {{
                color: {text};
                background: transparent;
                selection-background-color: {soft_primary};
                border: 0;
            }}
            QCalendarWidget QAbstractItemView:enabled {{
                color: {text};
                background: transparent;
                selection-background-color: {rgba(primary, 0.24)};
                selection-color: {text};
                outline: 0;
            }}
            QPushButton#iconButton {{
                background: {glass};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {primary};
                font-family: "{self.icon_font}";
            }}
            QPushButton#iconButton:hover, QPushButton#secondaryButton:hover, QPushButton#eventActionButton:hover {{
                background: {rgba(primary, 0.20)};
            }}
            QPushButton#secondaryButton, QPushButton#eventActionButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                padding: 8px 12px;
                font-weight: 600;
            }}
            QScrollArea {{
                background: transparent;
                border: 0;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 0 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {rgba(primary, 0.28)};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
                border: 0;
            }}
            """
        )
        self._apply_calendar_formats()

    def _apply_calendar_formats(self) -> None:
        text = QColor(self.theme.text)
        primary = QColor(self.theme.primary)
        muted = QColor(self.theme.text_muted)

        header_format = QTextCharFormat()
        header_format.setForeground(text)
        header_format.setFont(QFont(self.ui_font, 9, QFont.Weight.Medium))
        self.calendar.setHeaderTextFormat(header_format)

        weekday = QTextCharFormat()
        weekday.setForeground(text)
        weekday.setFont(QFont(self.ui_font, 9, QFont.Weight.Medium))
        for day in (
            Qt.DayOfWeek.Monday,
            Qt.DayOfWeek.Tuesday,
            Qt.DayOfWeek.Wednesday,
            Qt.DayOfWeek.Thursday,
            Qt.DayOfWeek.Friday,
            Qt.DayOfWeek.Saturday,
            Qt.DayOfWeek.Sunday,
        ):
            self.calendar.setWeekdayTextFormat(day, weekday)

        other_month = QTextCharFormat()
        show_other_days = bool(self.settings_state.get("calendar", {}).get("show_other_month_days", True))
        other_month.setForeground(muted if show_other_days else QColor(0, 0, 0, 0))

        page_start = self._visible_grid_start()
        for offset in range(42):
            visible_day = page_start.addDays(offset)
            if visible_day.month() != self.calendar.monthShown():
                self.calendar.setDateTextFormat(visible_day, other_month)

        today_format = self.calendar.dateTextFormat(QDate.currentDate())
        today_format.setForeground(primary)
        today_format.setFontWeight(QFont.Weight.Bold)
        self.calendar.setDateTextFormat(QDate.currentDate(), today_format)

        self._refresh_calendar_markers()

    def _visible_grid_start(self) -> QDate:
        first_of_month = QDate(self.calendar.yearShown(), self.calendar.monthShown(), 1)
        first_day = self.calendar.firstDayOfWeek().value
        shift = (first_of_month.dayOfWeek() - first_day) % 7
        return first_of_month.addDays(-shift)

    def _refresh_calendar_markers(self) -> None:
        default_format = QTextCharFormat()
        default_format.setForeground(QColor(self.theme.text))
        show_other_days = bool(self.settings_state.get("calendar", {}).get("show_other_month_days", True))
        muted_other = QTextCharFormat()
        muted_other.setForeground(QColor(self.theme.text_muted) if show_other_days else QColor(0, 0, 0, 0))

        page_start = self._visible_grid_start()
        for offset in range(42):
            qday = page_start.addDays(offset)
            self.calendar.setDateTextFormat(
                qday,
                default_format if qday.month() == self.calendar.monthShown() else muted_other,
            )

        marker_format = QTextCharFormat()
        marker_format.setForeground(QColor(self.theme.primary))
        marker_format.setBackground(QColor(0, 0, 0, 0))
        marker_format.setFontWeight(QFont.Weight.DemiBold)

        for day in self._events_by_day:
            qday = QDate(day.year, day.month, day.day)
            if qday.month() == self.calendar.monthShown() or show_other_days:
                self.calendar.setDateTextFormat(qday, marker_format)

        today_format = self.calendar.dateTextFormat(QDate.currentDate())
        today_format.setForeground(QColor(self.theme.primary))
        today_format.setFontWeight(QFont.Weight.Bold)
        self.calendar.setDateTextFormat(QDate.currentDate(), today_format)

    def _set_status(self, text: str, visible: bool = True) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(visible and bool(text))

    def _refresh_hero(self) -> None:
        calendar_settings = self.settings_state.get("calendar", {})
        reminders = self.settings_state.get("reminders", {})
        tracked = reminders.get("tracked_events", [])
        connected = bool(calendar_settings.get("connected", False))
        self.hero_title.setText("CalDAV linked" if connected else "CalDAV ready")
        self.hero_detail.setText(
            str(calendar_settings.get("last_sync_status", "")).strip()
            or "Use the gear icon to tweak styling and connect your CalDAV calendars."
        )
        self.connection_badge.setText("Connected" if connected else "Local only")
        self.tracked_badge.setText(f"{len(tracked)} reminder(s)")

    def refresh_data(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.refresh_button.setEnabled(False)
        self.subtitle.setText("Loading upcoming events and markers...")
        self._set_status("")
        self.worker = CalendarDataWorker()
        self.worker.loaded.connect(self._handle_loaded)
        self.worker.failed.connect(self._handle_failed)
        self.worker.finished.connect(self._handle_worker_finished)
        self.worker.start()

    def _handle_loaded(self, payload: dict) -> None:
        self._events = payload.get("events", [])
        self._calendars = {
            int(item.get("index", -1)): item.get("name", "")
            for item in payload.get("calendars", [])
            if "index" in item
        }
        self._events_by_day = defaultdict(list)
        for event in self._events:
            try:
                event_day = parse_event_date(event.get("start", ""))
            except Exception:
                continue
            self._events_by_day[event_day].append(event)

        total = payload.get("count", len(self._events))
        self.subtitle.setText(f"Updated {datetime.now().strftime('%H:%M')}  •  {total} upcoming event(s)")
        self._refresh_calendar_markers()
        self._refresh_events_for_selection()

    def _handle_failed(self, message: str) -> None:
        self._events = []
        self._events_by_day = defaultdict(list)
        self.subtitle.setText("Styled around your qcal events and reminder flow.")
        self._refresh_calendar_markers()
        self._refresh_events_for_selection()
        self._set_status(message)

    def _handle_worker_finished(self) -> None:
        self.refresh_button.setEnabled(True)
        self.worker = None

    def _handle_date_selected(self, selected: QDate) -> None:
        self.selection_title.setText(human_day_label(selected.toPyDate()))
        self._refresh_events_for_selection()

    def _refresh_events_for_selection(self) -> None:
        selected_day = self.calendar.selectedDate().toPyDate()
        self.selection_title.setText(human_day_label(selected_day))
        events = self._events_by_day.get(selected_day, [])
        self.count_badge.setText(f"{len(events)} event{'s' if len(events) != 1 else ''}")

        while self.events_layout.count() > 1:
            item = self.events_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not events:
            empty = QLabel("No events for the selected day. Tracked reminders will still appear in widget-reminders.")
            empty.setObjectName("statusLabel")
            empty.setFont(QFont(self.ui_font, 10))
            empty.setWordWrap(True)
            self.events_layout.insertWidget(0, empty)
            return

        for event in events:
            calendar_name = self._calendars.get(event.get("calendarIndex", -1), "")
            card = EventCard(event, calendar_name, self.ui_font, self.display_font)
            card.remind_requested.connect(self._track_event_reminder)
            self.events_layout.insertWidget(self.events_layout.count() - 1, card)

    def _track_event_reminder(self, event: dict) -> None:
        reminders = self.settings_state.setdefault("reminders", {})
        tracked = reminders.setdefault("tracked_events", [])
        title = str(event.get("title", "")).strip()
        start = str(event.get("start", "")).strip()
        if not title or not start:
            self._set_status("That event could not be tracked for reminders.")
            return
        existing = next((item for item in tracked if item.get("title") == title and item.get("start") == start), None)
        if existing is None:
            tracked.append(
                {
                    "title": title,
                    "start": start,
                    "lead_minutes": int(reminders.get("default_lead_minutes", 20)),
                    "severity": str(reminders.get("default_intensity", "discrete")),
                    "calendar_index": int(event.get("calendarIndex", -1)),
                    "filename": str(event.get("filename", "")).strip(),
                }
            )
            save_settings_state(self.settings_state)
            self._refresh_hero()
            self._set_status(f"Reminder saved for {title}.")
        else:
            self._set_status(f"{title} is already tracked in widget-reminders.")

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        command = entry_command(SETTINGS_PAGE_SCRIPT, "--page", "services", "--service-section", "calendar_widget")
        if not command:
            return
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.close()

    def _open_reminders_widget(self) -> None:
        if not REMINDERS_WIDGET_SCRIPT.exists():
            self._set_status("widget-reminders is not available yet.")
            return
        command = entry_command(REMINDERS_WIDGET_SCRIPT)
        if not command:
            self._set_status("widget-reminders is not available yet.")
            return
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _reload_theme_if_needed(self) -> None:
        mtime = palette_mtime()
        if mtime <= self._theme_mtime:
            return
        self.theme = load_theme_palette()
        self._theme_mtime = mtime
        self.settings_state = load_settings_state()
        self._apply_calendar_preferences()
        self._refresh_hero()
        self._apply_styles()

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        QTimer.singleShot(0, self.close)


def main() -> int:
    app = QApplication(sys.argv)
    popup = CalendarPopup()
    popup.show()
    popup.raise_()
    popup.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
