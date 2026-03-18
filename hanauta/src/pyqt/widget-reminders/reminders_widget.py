#!/usr/bin/env python3
from __future__ import annotations

import json
import shlex
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"
QCAL_WRAPPER = APP_DIR / "pyqt" / "widget-calendar" / "qcal-wrapper.py"
REMINDER_ALERT_SCRIPT = APP_DIR / "pyqt" / "widget-reminders" / "reminder_alert.py"
REMINDER_DAEMON_SCRIPT = APP_DIR / "pyqt" / "widget-reminders" / "reminder_daemon.py"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))

from pyqt.shared.runtime import entry_command, python_executable
from pyqt.shared.theme import blend, load_theme_palette, palette_mtime, rgba
from reminder_queue import enqueue_reminder, ensure_daemon_running, load_queue


MATERIAL_ICONS = {
    "settings": "\ue8b8",
    "refresh": "\ue5d5",
    "alarm": "\ue855",
    "notifications_active": "\ue7f7",
    "coffee": "\uefef",
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


def run_wrapper(*args: str) -> dict:
    try:
        command = entry_command(QCAL_WRAPPER, *args)
        if not command:
            return {"error": "Unable to load calendar data."}
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return {"error": str(exc)}
    try:
        return json.loads(proc.stdout or "{}")
    except Exception:
        return {"error": proc.stderr.strip() or "Unable to load calendar data."}


def load_settings_state() -> dict:
    default = {
        "reminders": {
            "default_lead_minutes": 20,
            "default_intensity": "discrete",
            "tracked_events": [],
            "tea_label": "Tea",
            "tea_minutes": 5,
        }
    }
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default
    reminders = payload.get("reminders", {})
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
    payload["reminders"] = settings.get("reminders", {})
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_iso(value: str) -> datetime:
    if "T" in value:
        return datetime.fromisoformat(value)
    return datetime.fromisoformat(f"{value}T09:00:00")


def format_relative(moment: datetime) -> str:
    delta = moment - datetime.now()
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 0:
        return "Due now"
    if minutes < 60:
        return f"In {minutes} min"
    hours, rem = divmod(minutes, 60)
    return f"In {hours}h {rem:02d}m"


def reminder_shell(title: str, body: str, severity: str) -> str:
    title_q = shlex.quote(title)
    body_q = shlex.quote(body)
    if severity == "quiet":
        return f"notify-send -u low {title_q} {body_q}"
    if severity == "disturbing":
        return (
            f"for _ in 1 2 3 4; do "
            f"notify-send -u critical {title_q} {body_q}; "
            f"sleep 2; "
            f"done"
        )
    return f"notify-send -u normal {title_q} {body_q}"


def launch_reminder(title: str, body: str, severity: str, delay_seconds: int = 0) -> None:
    enqueue_reminder(title, body, severity, delay_seconds=delay_seconds)
    ensure_daemon_running(entry_command(REMINDER_DAEMON_SCRIPT))


class ReminderDataWorker(QThread):
    loaded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self) -> None:
        payload = run_wrapper("list", "--days", "14")
        if payload.get("error"):
            self.failed.emit(str(payload["error"]))
            return
        self.loaded.emit(payload)


class ReminderCard(QFrame):
    notify_requested = pyqtSignal(dict)
    dismiss_requested = pyqtSignal(dict)

    def __init__(self, reminder: dict, ui_font: str, display_font: str, icon_font: str) -> None:
        super().__init__()
        self.reminder = reminder
        self.icon_font = icon_font
        self.setObjectName("reminderCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(12)

        icon_chip = QLabel(material_icon("notifications_active"))
        icon_chip.setObjectName("cardIcon")
        icon_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_chip.setFixedSize(38, 38)
        icon_chip.setFont(QFont(icon_font, 18))

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(2)
        text_wrap.setContentsMargins(0, 0, 0, 0)

        title = QLabel(str(reminder.get("title", "Reminder")))
        title.setObjectName("cardTitle")
        title.setFont(QFont(display_font, 10, QFont.Weight.DemiBold))

        detail = QLabel(
            reminder["event_at"].strftime("%a %d %b • %H:%M")
        )
        detail.setObjectName("cardDetail")
        detail.setFont(QFont(ui_font, 8))
        detail.setWordWrap(True)

        text_wrap.addWidget(title)
        text_wrap.addWidget(detail)

        severity = QLabel(str(reminder.get("severity", "discrete")).capitalize())
        severity.setObjectName("severityBadge")
        severity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        severity.setFont(QFont(ui_font, 8, QFont.Weight.DemiBold))
        severity.setMinimumWidth(84)

        top.addWidget(icon_chip, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(text_wrap, 1)
        top.addWidget(severity, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        due_badge = QLabel(format_relative(reminder["remind_at"]))
        due_badge.setObjectName("dueBadge")
        due_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        due_badge.setFont(QFont(ui_font, 8, QFont.Weight.DemiBold))
        meta_row.addWidget(due_badge, 0)
        meta_row.addStretch(1)
        layout.addLayout(meta_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        ping_button = QPushButton("Trigger")
        ping_button.setObjectName("secondaryButton")
        ping_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ping_button.setMinimumHeight(32)
        ping_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ping_button.clicked.connect(lambda: self.notify_requested.emit(self.reminder))
        dismiss_button = QPushButton("Untrack")
        dismiss_button.setObjectName("dangerButton")
        dismiss_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        dismiss_button.setMinimumHeight(32)
        dismiss_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        dismiss_button.clicked.connect(lambda: self.dismiss_requested.emit(self.reminder))
        actions.addWidget(ping_button)
        actions.addWidget(dismiss_button)
        layout.addLayout(actions)


class RemindersWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.settings_state = load_settings_state()
        self._fade: QPropertyAnimation | None = None
        self.worker: ReminderDataWorker | None = None
        self._events: list[dict] = []
        self._queued_reminders: list[dict] = []

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("Hanauta Reminders")
        self.setFixedSize(468, 648)

        self._build_ui()
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
        root.setContentsMargins(10, 10, 10, 10)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.header_shell = QFrame()
        self.header_shell.setObjectName("headerShell")
        header_shell_layout = QVBoxLayout(self.header_shell)
        header_shell_layout.setContentsMargins(16, 16, 16, 16)
        header_shell_layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        eyebrow = QLabel("REMINDERS")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        # title = QLabel("Reminder shell")
        # title.setObjectName("title")
        # title.setFont(QFont(self.display_font, 20, QFont.Weight.DemiBold))
        self.subtitle = QLabel("Native popup for tracked calendar nudges and instant home-task timers.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setFont(QFont(self.ui_font, 8))
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        # titles.addWidget(title)
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
        header_shell_layout.addLayout(header)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        self.count_chip = QLabel("0 live")
        self.count_chip.setObjectName("headerChip")
        self.count_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_chip.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        self.mode_chip = QLabel("Discrete mode")
        self.mode_chip.setObjectName("headerChipMuted")
        self.mode_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mode_chip.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        chip_row.addWidget(self.count_chip, 0)
        chip_row.addWidget(self.mode_chip, 0)
        chip_row.addStretch(1)
        header_shell_layout.addLayout(chip_row)
        layout.addWidget(self.header_shell)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(14)
        hero_icon = QLabel(material_icon("alarm"))
        hero_icon.setObjectName("heroIcon")
        hero_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_icon.setFixedSize(48, 48)
        hero_icon.setFont(QFont(self.icon_font, 22))
        hero_layout.addWidget(hero_icon, 0, Qt.AlignmentFlag.AlignTop)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(3)
        self.hero_title = QLabel("")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 14, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setFont(QFont(self.ui_font, 8))
        self.hero_detail.setWordWrap(True)
        self.hero_meta = QLabel("")
        self.hero_meta.setObjectName("heroMeta")
        self.hero_meta.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        hero_text.addWidget(self.hero_title)
        hero_text.addWidget(self.hero_detail)
        hero_text.addWidget(self.hero_meta)
        hero_layout.addLayout(hero_text, 1)
        layout.addWidget(self.hero)

        self.quick_timer = QFrame()
        self.quick_timer.setObjectName("quickTimerShell")
        timer_layout = QVBoxLayout(self.quick_timer)
        timer_layout.setContentsMargins(16, 16, 16, 16)
        timer_layout.setSpacing(10)

        timer_header = QHBoxLayout()
        timer_header.setSpacing(10)
        timer_icon = QLabel(material_icon("coffee"))
        timer_icon.setObjectName("sectionIcon")
        timer_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_icon.setFixedSize(34, 34)
        timer_icon.setFont(QFont(self.icon_font, 17))
        timer_text = QVBoxLayout()
        timer_text.setSpacing(1)
        timer_title = QLabel("Quick timer")
        timer_title.setObjectName("sectionTitle")
        timer_title.setFont(QFont(self.display_font, 12, QFont.Weight.DemiBold))
        timer_hint = QLabel("Tea, laundry, pasta, shower, oven. Schedule a full-screen reminder.")
        timer_hint.setObjectName("sectionHint")
        timer_hint.setFont(QFont(self.ui_font, 8))
        timer_hint.setWordWrap(True)
        timer_text.addWidget(timer_title)
        timer_text.addWidget(timer_hint)
        timer_header.addWidget(timer_icon, 0, Qt.AlignmentFlag.AlignTop)
        timer_header.addLayout(timer_text, 1)
        timer_layout.addLayout(timer_header)

        self.timer_label_input = QLineEdit(str(self.settings_state["reminders"].get("tea_label", "Tea")))
        self.timer_label_input.setPlaceholderText("Tea, eggs, pasta, laundry...")
        self.timer_label_input.setMinimumHeight(36)
        timer_layout.addWidget(self.timer_label_input)

        self.timer_slider = QSlider(Qt.Orientation.Horizontal)
        self.timer_slider.setRange(1, 30)
        self.timer_slider.setValue(int(self.settings_state["reminders"].get("tea_minutes", 5)))
        timer_layout.addWidget(self.timer_slider)

        self.timer_value = QLabel("")
        self.timer_value.setObjectName("timerValue")
        self.timer_value.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        timer_layout.addWidget(self.timer_value)

        timer_actions = QHBoxLayout()
        timer_actions.setSpacing(8)
        for minutes in (3, 6, 10):
            button = QPushButton(f"{minutes} min")
            button.setObjectName("secondaryButton")
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.setMinimumHeight(32)
            button.clicked.connect(lambda checked=False, value=minutes: self._start_quick_timer(value))
            timer_actions.addWidget(button)
        self.start_custom_timer = QPushButton("Start custom")
        self.start_custom_timer.setObjectName("primaryButton")
        self.start_custom_timer.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_custom_timer.setMinimumHeight(34)
        self.start_custom_timer.clicked.connect(lambda: self._start_quick_timer(int(self.timer_slider.value())))
        timer_actions.addWidget(self.start_custom_timer)
        timer_layout.addLayout(timer_actions)
        layout.addWidget(self.quick_timer)

        self.status_shell = QFrame()
        self.status_shell.setObjectName("statusShell")
        status_layout = QHBoxLayout(self.status_shell)
        status_layout.setContentsMargins(14, 10, 14, 10)
        status_layout.setSpacing(10)
        status_icon = QLabel(material_icon("alarm"))
        status_icon.setObjectName("statusIcon")
        status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_icon.setFixedSize(28, 28)
        status_icon.setFont(QFont(self.icon_font, 15))
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setFont(QFont(self.ui_font, 8))
        self.status_label.setWordWrap(True)
        status_layout.addWidget(status_icon, 0, Qt.AlignmentFlag.AlignTop)
        status_layout.addWidget(self.status_label, 1)
        self.status_shell.hide()
        layout.addWidget(self.status_shell)

        self.list_shell = QFrame()
        self.list_shell.setObjectName("listShell")
        list_shell_layout = QVBoxLayout(self.list_shell)
        list_shell_layout.setContentsMargins(12, 12, 12, 12)
        list_shell_layout.setSpacing(10)

        list_header = QHBoxLayout()
        list_header.setSpacing(8)
        list_title = QLabel("Reminder feed")
        list_title.setObjectName("sectionTitle")
        list_title.setFont(QFont(self.display_font, 12, QFont.Weight.DemiBold))
        self.feed_meta = QLabel("No active entries")
        self.feed_meta.setObjectName("feedMeta")
        self.feed_meta.setFont(QFont(self.ui_font, 8))
        self.feed_meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        list_header.addWidget(list_title, 1)
        list_header.addWidget(self.feed_meta, 0)
        list_shell_layout.addLayout(list_header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setObjectName("reminderScroll")
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_container)
        list_shell_layout.addWidget(self.scroll, 1)
        layout.addWidget(self.list_shell, 1)

        self.timer_slider.valueChanged.connect(self._update_timer_value)
        self._update_timer_value()
        self._refresh_hero([])

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(36, 36)
        button.setFont(QFont(self.icon_font, 17))
        return button

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(54)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 220))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        x = available.x() + available.width() - self.width() - 52
        y = available.y() + 78
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
        primary = theme.primary
        shell_bg = rgba(blend(theme.surface_container, "#0B0E14", 0.52), 0.96)
        shell_border = rgba(blend(theme.outline, primary, 0.25), 0.20)
        module_bg = rgba(blend(theme.surface_container_high, "#0D1117", 0.32), 0.92)
        module_border = rgba(blend(theme.outline, primary, 0.18), 0.18)
        chip_bg = rgba(blend(theme.surface_container_high, "#0A0D12", 0.24), 0.88)
        active_chip_bg = rgba(primary, 0.18)
        active_chip_border = rgba(primary, 0.28)
        line_bg = rgba(theme.on_surface, 0.04)
        danger = rgba(theme.error, 0.18)
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {theme.text};
                font-family: "{self.ui_font}";
                background: transparent;
            }}
            QFrame#panel {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {shell_bg},
                    stop: 1 {rgba(blend(theme.surface_container, "#05070B", 0.58), 0.98)}
                );
                border: 1px solid {shell_border};
                border-radius: 30px;
            }}
            QFrame#headerShell, QFrame#heroCard, QFrame#quickTimerShell, QFrame#listShell {{
                background: {module_bg};
                border: 1px solid {module_border};
                border-radius: 24px;
            }}
            QFrame#heroCard {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(blend(primary, theme.surface_container_high, 0.86), 0.30)},
                    stop: 1 {module_bg}
                );
            }}
            QLabel#eyebrow {{
                color: {primary};
                letter-spacing: 2.4px;
            }}
            QLabel#title, QLabel#heroTitle, QLabel#sectionTitle, QLabel#cardTitle {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#heroDetail, QLabel#cardDetail, QLabel#statusLabel, QLabel#sectionHint, QLabel#feedMeta {{
                color: {theme.text_muted};
            }}
            QLabel#heroMeta, QLabel#feedMeta {{
                color: {rgba(primary, 0.92)};
            }}
            QLabel#headerChip, QLabel#headerChipMuted, QLabel#severityBadge, QLabel#timerValue, QLabel#dueBadge {{
                background: {chip_bg};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 14px;
                padding: 5px 10px;
            }}
            QLabel#headerChip {{
                background: {active_chip_bg};
                border: 1px solid {active_chip_border};
                color: {primary};
            }}
            QLabel#headerChipMuted, QLabel#dueBadge {{
                color: {theme.text_muted};
            }}
            QLabel#severityBadge {{
                color: {primary};
            }}
            QLabel#timerValue {{
                color: {theme.text};
            }}
            QLabel#heroIcon, QLabel#cardIcon, QLabel#sectionIcon, QLabel#statusIcon {{
                background: {line_bg};
                border: 1px solid {rgba(primary, 0.18)};
                border-radius: 17px;
                font-family: "{self.icon_font}";
                color: {primary};
            }}
            QPushButton#iconButton {{
                background: {line_bg};
                color: {primary};
                border: 1px solid {rgba(primary, 0.14)};
                border-radius: 18px;
                font-family: "{self.icon_font}";
            }}
            QPushButton#iconButton:hover {{
                background: {rgba(primary, 0.16)};
            }}
            QFrame#reminderCard {{
                background: {rgba(blend(theme.surface_container_high, "#070A0F", 0.26), 0.94)};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 20px;
            }}
            QFrame#statusShell {{
                background: {rgba(blend(primary, theme.surface_container, 0.82), 0.12)};
                border: 1px solid {rgba(primary, 0.18)};
                border-radius: 18px;
            }}
            QFrame#statusShell[error="true"] {{
                background: {rgba(blend(theme.error, theme.surface_container, 0.72), 0.20)};
                border: 1px solid {rgba(theme.error, 0.28)};
            }}
            QPushButton#primaryButton, QPushButton#secondaryButton, QPushButton#dangerButton {{
                border-radius: 18px;
                padding: 0 12px;
                font-weight: 600;
                font-size: 11px;
            }}
            QPushButton#primaryButton {{
                background: {primary};
                color: {theme.active_text};
                border: none;
            }}
            QPushButton#primaryButton:hover {{
                background: {blend(primary, theme.primary_container, 0.38)};
                color: {theme.on_primary_container};
            }}
            QPushButton#secondaryButton {{
                background: {rgba(theme.on_surface, 0.045)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.14)};
            }}
            QPushButton#secondaryButton:hover {{
                background: {rgba(primary, 0.10)};
            }}
            QPushButton#dangerButton {{
                background: {danger};
                color: {theme.text};
                border: 1px solid {rgba(theme.error, 0.24)};
            }}
            QPushButton#dangerButton:hover {{
                background: {rgba(theme.error, 0.24)};
            }}
            QLineEdit {{
                border-radius: 18px;
                border: 1px solid {rgba(theme.outline, 0.14)};
                background: {rgba(theme.on_surface, 0.04)};
                padding: 0 12px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border: 1px solid {rgba(primary, 0.55)};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {rgba(theme.outline, 0.24)};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {primary};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
                background: {primary};
                border: 2px solid {theme.panel_bg};
            }}
            QScrollArea, QScrollArea#reminderScroll {{
                background: transparent;
                border: 0;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: transparent;
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

    def _update_timer_value(self) -> None:
        self.timer_value.setText(f"{int(self.timer_slider.value())} minute default")

    def _load_pending_queue_reminders(self) -> list[dict]:
        now = datetime.now()
        pending: list[dict] = []
        for item in load_queue():
            try:
                due_at = datetime.fromisoformat(str(item.get("due_at", "")))
            except Exception:
                continue
            if due_at < now:
                continue
            pending.append(
                {
                    "title": str(item.get("title", "Reminder")).strip() or "Reminder",
                    "severity": str(item.get("severity", "discrete")).strip() or "discrete",
                    "remind_at": due_at,
                    "event_at": due_at,
                    "source": "queue",
                }
            )
        pending.sort(key=lambda item: item["remind_at"])
        return pending

    def _refresh_hero(self, reminders: list[dict]) -> None:
        severity = str(self.settings_state["reminders"].get("default_intensity", "discrete")).capitalize()
        total_live = len(reminders) + len(self._queued_reminders)
        next_item = sorted(reminders + self._queued_reminders, key=lambda item: item["remind_at"])[0] if total_live else None
        self.count_chip.setText(f"{total_live} live")
        self.mode_chip.setText(f"{severity} mode")
        self.hero_title.setText("Reminder queue armed" if total_live else "Queue standing by")
        if next_item:
            self.hero_detail.setText(
                f"Next alert: {next_item.get('title', 'Reminder')} on {next_item['event_at'].strftime('%a %d %b at %H:%M')}."
            )
            self.hero_meta.setText(f"{format_relative(next_item['remind_at'])} • full-screen warning when due")
        else:
            self.hero_detail.setText(
                "Tracked calendar reminders will appear here, and quick timers will still trigger full-screen alerts."
            )
            self.hero_meta.setText(
                f"Default quick timer: {self.settings_state['reminders'].get('tea_label', 'Tea')} • "
                f"{self.settings_state['reminders'].get('tea_minutes', 5)} min"
            )

    def refresh_data(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.refresh_button.setEnabled(False)
        self.settings_state = load_settings_state()
        self.worker = ReminderDataWorker()
        self.worker.loaded.connect(self._handle_loaded)
        self.worker.failed.connect(self._handle_failed)
        self.worker.finished.connect(self._handle_finished)
        self.worker.start()

    def _handle_loaded(self, payload: dict) -> None:
        self._events = payload.get("events", [])
        self._queued_reminders = self._load_pending_queue_reminders()
        reminders = self._build_tracked_reminders()
        self._rebuild_list(reminders, "")
        self._refresh_hero(reminders)
        total_live = len(reminders) + len(self._queued_reminders)
        self.subtitle.setText(f"Synced at {datetime.now().strftime('%H:%M')} • {total_live} active reminder(s)")
        self._set_status_message("" if total_live else "No tracked reminders right now. Use the calendar popup or quick timer below.", is_error=False)

    def _handle_failed(self, message: str) -> None:
        self._events = []
        self._queued_reminders = self._load_pending_queue_reminders()
        reminders = self._build_tracked_reminders()
        self._rebuild_list(reminders, message)
        self._refresh_hero(reminders)
        self._set_status_message(message or "Unable to load calendar data.", is_error=True)

    def _handle_finished(self) -> None:
        self.refresh_button.setEnabled(True)
        self.worker = None

    def _build_tracked_reminders(self) -> list[dict]:
        tracked = self.settings_state.get("reminders", {}).get("tracked_events", [])
        active: list[dict] = []
        now = datetime.now() - timedelta(hours=1)
        event_lookup = {
            (str(event.get("title", "")).strip(), str(event.get("start", "")).strip()): event
            for event in self._events
        }
        for item in tracked:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            start = str(item.get("start", "")).strip()
            if not title or not start:
                continue
            try:
                event_at = parse_iso(start)
            except Exception:
                continue
            if event_at < now:
                continue
            lead_minutes = int(item.get("lead_minutes", self.settings_state["reminders"].get("default_lead_minutes", 20)))
            reminder = dict(item)
            reminder["event_at"] = event_at
            reminder["remind_at"] = event_at - timedelta(minutes=max(0, lead_minutes))
            reminder["event"] = event_lookup.get((title, start), {})
            active.append(reminder)
        active.sort(key=lambda item: item["remind_at"])
        return active

    def _rebuild_list(self, reminders: list[dict], error_message: str = "") -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not reminders:
            self.list_shell.hide()
            self.feed_meta.setText("Empty")
            return

        self.list_shell.show()
        self.scroll.show()
        self.feed_meta.setText(f"{len(reminders)} active")
        for reminder in reminders:
            card = ReminderCard(reminder, self.ui_font, self.display_font, self.icon_font)
            card.notify_requested.connect(self._notify_now)
            card.dismiss_requested.connect(self._dismiss_tracking)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def _notify_now(self, reminder: dict) -> None:
        launch_reminder(
            str(reminder.get("title", "Reminder")),
            f"Event at {reminder['event_at'].strftime('%H:%M')}",
            str(reminder.get("severity", "discrete")),
        )
        self._set_status_message(
            f"Triggered a {reminder.get('severity', 'discrete')} full-screen alert for {reminder.get('title', 'Reminder')}.",
            is_error=False,
        )

    def _dismiss_tracking(self, reminder: dict) -> None:
        tracked = self.settings_state.setdefault("reminders", {}).setdefault("tracked_events", [])
        tracked[:] = [
            item for item in tracked
            if not (
                str(item.get("title", "")).strip() == str(reminder.get("title", "")).strip()
                and str(item.get("start", "")).strip() == str(reminder.get("start", "")).strip()
            )
        ]
        save_settings_state(self.settings_state)
        self.refresh_data()

    def _start_quick_timer(self, minutes: int) -> None:
        label = self.timer_label_input.text().strip() or str(self.settings_state["reminders"].get("tea_label", "Tea"))
        severity = str(self.settings_state["reminders"].get("default_intensity", "discrete"))
        launch_reminder(
            f"{label} reminder",
            f"{label} is ready.",
            severity,
            delay_seconds=max(1, int(minutes)) * 60,
        )
        self.settings_state.setdefault("reminders", {})["tea_label"] = label
        self.settings_state["reminders"]["tea_minutes"] = int(minutes)
        save_settings_state(self.settings_state)
        self._set_status_message(f"{label} reminder armed for {minutes} minute(s).", is_error=False)
        self._queued_reminders = self._load_pending_queue_reminders()
        self._refresh_hero(self._build_tracked_reminders())

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        command = entry_command(SETTINGS_PAGE_SCRIPT, "--page", "services", "--service-section", "reminders_widget")
        if not command:
            return
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.close()

    def _reload_theme_if_needed(self) -> None:
        mtime = palette_mtime()
        if mtime <= self._theme_mtime:
            return
        self.theme = load_theme_palette()
        self._theme_mtime = mtime
        self._apply_styles()

    def _set_status_message(self, message: str, *, is_error: bool) -> None:
        cleaned = str(message).strip()
        self.status_label.setText(cleaned)
        self.status_shell.setVisible(bool(cleaned))
        self.status_shell.setProperty("error", is_error)
        self.status_shell.style().unpolish(self.status_shell)
        self.status_shell.style().polish(self.status_shell)

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        QTimer.singleShot(0, self.close)


def main() -> int:
    app = QApplication(sys.argv)
    widget = RemindersWidget()
    widget.show()
    widget.raise_()
    widget.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
