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
    QSlider,
    QVBoxLayout,
    QWidget,
)


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"
QCAL_WRAPPER = APP_DIR / "pyqt" / "widget-calendar" / "qcal-wrapper.py"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba


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
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def run_wrapper(*args: str) -> dict:
    try:
        proc = subprocess.run(
            [_python_bin(), str(QCAL_WRAPPER), *args],
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
    command = reminder_shell(title, body, severity)
    if delay_seconds > 0:
        command = f"sleep {max(1, int(delay_seconds))}; {command}"
    try:
        subprocess.Popen(
            ["bash", "-lc", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


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

    def __init__(self, reminder: dict, ui_font: str, display_font: str) -> None:
        super().__init__()
        self.reminder = reminder
        self.setObjectName("reminderCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(4)
        text_wrap.setContentsMargins(0, 0, 0, 0)

        title = QLabel(str(reminder.get("title", "Reminder")))
        title.setObjectName("cardTitle")
        title.setFont(QFont(display_font, 12, QFont.Weight.DemiBold))

        detail = QLabel(
            f"{format_relative(reminder['remind_at'])}  •  {reminder['event_at'].strftime('%a %d %b %H:%M')}"
        )
        detail.setObjectName("cardDetail")
        detail.setFont(QFont(ui_font, 9))
        detail.setWordWrap(True)

        text_wrap.addWidget(title)
        text_wrap.addWidget(detail)

        severity = QLabel(str(reminder.get("severity", "discrete")).capitalize())
        severity.setObjectName("severityBadge")
        severity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        severity.setFont(QFont(ui_font, 9, QFont.Weight.DemiBold))
        severity.setMinimumWidth(92)

        top.addLayout(text_wrap, 1)
        top.addWidget(severity, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        ping_button = QPushButton("Notify now")
        ping_button.setObjectName("secondaryButton")
        ping_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ping_button.clicked.connect(lambda: self.notify_requested.emit(self.reminder))
        dismiss_button = QPushButton("Stop tracking")
        dismiss_button.setObjectName("secondaryButton")
        dismiss_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        dismiss_button.clicked.connect(lambda: self.dismiss_requested.emit(self.reminder))
        actions.addWidget(ping_button)
        actions.addWidget(dismiss_button)
        actions.addStretch(1)
        layout.addLayout(actions)


class RemindersWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font(fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font(fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.settings_state = load_settings_state()
        self._fade: QPropertyAnimation | None = None
        self.worker: ReminderDataWorker | None = None
        self._events: list[dict] = []

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
        root.setContentsMargins(14, 14, 14, 14)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(3)
        eyebrow = QLabel("WIDGET REMINDERS")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        title = QLabel("Keep me honest")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 24, QFont.Weight.Bold))
        self.subtitle = QLabel("Tracked CalDAV events plus a tea/eggs/custom quick timer.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setFont(QFont(self.ui_font, 10))
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
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
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(6)
        self.hero_title = QLabel("")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 16, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setFont(QFont(self.ui_font, 9))
        self.hero_detail.setWordWrap(True)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_detail)
        layout.addWidget(self.hero)

        self.quick_timer = QFrame()
        self.quick_timer.setObjectName("quickTimer")
        timer_layout = QVBoxLayout(self.quick_timer)
        timer_layout.setContentsMargins(16, 16, 16, 16)
        timer_layout.setSpacing(10)

        timer_title = QLabel("Tea reminder")
        timer_title.setObjectName("sectionTitle")
        timer_title.setFont(QFont(self.display_font, 15, QFont.Weight.DemiBold))
        timer_layout.addWidget(timer_title)

        self.timer_label_input = QLineEdit(str(self.settings_state["reminders"].get("tea_label", "Tea")))
        self.timer_label_input.setPlaceholderText("Tea, eggs, pasta, laundry...")
        timer_layout.addWidget(self.timer_label_input)

        self.timer_slider = QSlider(Qt.Orientation.Horizontal)
        self.timer_slider.setRange(1, 30)
        self.timer_slider.setValue(int(self.settings_state["reminders"].get("tea_minutes", 5)))
        timer_layout.addWidget(self.timer_slider)

        self.timer_value = QLabel("")
        self.timer_value.setObjectName("timerValue")
        self.timer_value.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        timer_layout.addWidget(self.timer_value)

        timer_actions = QHBoxLayout()
        for minutes in (3, 6, 10):
            button = QPushButton(f"{minutes} min")
            button.setObjectName("secondaryButton")
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.clicked.connect(lambda checked=False, value=minutes: self._start_quick_timer(value))
            timer_actions.addWidget(button)
        self.start_custom_timer = QPushButton("Start custom")
        self.start_custom_timer.setObjectName("primaryButton")
        self.start_custom_timer.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_custom_timer.clicked.connect(lambda: self._start_quick_timer(int(self.timer_slider.value())))
        timer_actions.addWidget(self.start_custom_timer)
        timer_layout.addLayout(timer_actions)
        layout.addWidget(self.quick_timer)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll, 1)

        self.timer_slider.valueChanged.connect(self._update_timer_value)
        self._update_timer_value()
        self._refresh_hero([])

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(38, 38)
        button.setFont(QFont(self.icon_font, 18))
        return button

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(46)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 130))
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
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#panel {{
                background: {rgba(theme.surface_container, 0.97)};
                border: 1px solid {rgba(theme.outline, 0.86)};
                border-radius: 28px;
            }}
            QLabel#eyebrow {{
                color: {primary};
                letter-spacing: 0.12em;
            }}
            QLabel#title, QLabel#heroTitle, QLabel#sectionTitle, QLabel#cardTitle {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#heroDetail, QLabel#cardDetail, QLabel#statusLabel {{
                color: {theme.text_muted};
            }}
            QFrame#heroCard, QFrame#quickTimer, QFrame#reminderCard {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border: 1px solid {rgba(theme.outline, 0.24)};
                border-radius: 22px;
            }}
            QFrame#heroCard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {rgba(primary, 0.22)},
                    stop:1 {rgba(theme.surface_container_high, 0.98)}
                );
            }}
            QPushButton#iconButton {{
                background: {rgba(primary, 0.14)};
                color: {primary};
                border: 1px solid {rgba(primary, 0.18)};
                border-radius: 19px;
                font-family: "{self.icon_font}";
            }}
            QPushButton#primaryButton, QPushButton#secondaryButton {{
                border-radius: 14px;
                padding: 8px 12px;
                font-weight: 600;
            }}
            QPushButton#primaryButton {{
                background: {primary};
                color: {theme.active_text};
                border: none;
            }}
            QPushButton#secondaryButton {{
                background: {rgba(primary, 0.14)};
                color: {primary};
                border: 1px solid {rgba(primary, 0.18)};
            }}
            QLabel#severityBadge, QLabel#timerValue {{
                background: {rgba(primary, 0.14)};
                color: {primary};
                border: 1px solid {rgba(primary, 0.18)};
                border-radius: 12px;
                padding: 6px 10px;
            }}
            QLineEdit {{
                border-radius: 14px;
                border: 1px solid {rgba(theme.outline, 0.34)};
                background: {rgba(theme.surface_container_high, 0.82)};
                padding: 10px 12px;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {rgba(theme.outline, 0.32)};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {primary};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: {theme.text};
            }}
            QScrollArea {{
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

    def _refresh_hero(self, reminders: list[dict]) -> None:
        severity = str(self.settings_state["reminders"].get("default_intensity", "discrete")).capitalize()
        self.hero_title.setText(f"{len(reminders)} tracked reminder(s)")
        self.hero_detail.setText(
            f"Default style: {severity}. Tea reminder: "
            f"{self.settings_state['reminders'].get('tea_label', 'Tea')} "
            f"for {self.settings_state['reminders'].get('tea_minutes', 5)} min."
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
        reminders = self._build_tracked_reminders()
        self._rebuild_list(reminders)
        self._refresh_hero(reminders)
        self.subtitle.setText(f"Updated {datetime.now().strftime('%H:%M')}  •  {len(reminders)} active reminder(s)")
        self.status_label.setText("")

    def _handle_failed(self, message: str) -> None:
        self._events = []
        reminders = self._build_tracked_reminders()
        self._rebuild_list(reminders)
        self._refresh_hero(reminders)
        self.status_label.setText(message)

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

    def _rebuild_list(self, reminders: list[dict]) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not reminders:
            empty = QLabel("No tracked reminders yet. Open the calendar popup and press “Remind me” on an event.")
            empty.setObjectName("statusLabel")
            empty.setWordWrap(True)
            self.list_layout.insertWidget(0, empty)
            return

        for reminder in reminders:
            card = ReminderCard(reminder, self.ui_font, self.display_font)
            card.notify_requested.connect(self._notify_now)
            card.dismiss_requested.connect(self._dismiss_tracking)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def _notify_now(self, reminder: dict) -> None:
        launch_reminder(
            str(reminder.get("title", "Reminder")),
            f"Event at {reminder['event_at'].strftime('%H:%M')}",
            str(reminder.get("severity", "discrete")),
        )
        self.status_label.setText(f"Sent a {reminder.get('severity', 'discrete')} alert for {reminder.get('title', 'Reminder')}.")

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
        self.status_label.setText(f"{label} reminder scheduled for {minutes} minute(s).")
        self._refresh_hero(self._build_tracked_reminders())

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        subprocess.Popen(
            [sys.executable, str(SETTINGS_PAGE_SCRIPT), "--page", "services", "--service-section", "reminders_widget"],
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
