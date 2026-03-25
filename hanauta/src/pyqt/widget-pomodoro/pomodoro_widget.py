#!/usr/bin/env python3
from __future__ import annotations

import json
import signal
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command, python_executable
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.button_helpers import create_close_button


MATERIAL_ICONS = {
    "play_arrow": "\ue037",
    "pause": "\ue034",
    "restart_alt": "\uf053",
    "settings": "\ue8b8",
    "close": "\ue5cd",
    "timer": "\ue425",
    "coffee": "\uefef",
    "bedtime": "\uf159",
}


MODE_META = {
    "work": {
        "label": "Work",
        "headline": "Focus session",
        "icon": "timer",
        "completion_title": "Focus session done",
        "completion_body": "Time for a break.",
    },
    "short_break": {
        "label": "Short Break",
        "headline": "Short break",
        "icon": "coffee",
        "completion_title": "Short break done",
        "completion_body": "Ready to get back to work.",
    },
    "long_break": {
        "label": "Long Break",
        "headline": "Long break",
        "icon": "bedtime",
        "completion_title": "Long break done",
        "completion_body": "A fresh focus block can start now.",
    },
}


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "ui_display": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
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


def python_bin() -> str:
    return python_executable()


def load_settings_state() -> dict:
    default = {
        "pomodoro": {
            "work_minutes": 25,
            "short_break_minutes": 5,
            "long_break_minutes": 15,
            "long_break_every": 4,
            "auto_start_breaks": False,
            "auto_start_focus": False,
        }
    }
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default
    pomodoro = payload.get("pomodoro", {})
    if isinstance(pomodoro, dict):
        default["pomodoro"].update(pomodoro)
    return default


def notify(title: str, body: str) -> None:
    try:
        subprocess.Popen(
            ["notify-send", "-a", "Hanauta Pomodoro", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def format_duration(seconds: int) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class ProgressRing(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.progress = 0.0
        self.theme = load_theme_palette()
        self.setFixedSize(224, 224)

    def set_progress(self, progress: float) -> None:
        self.progress = max(0.0, min(1.0, progress))
        self.update()

    def set_theme(self, theme) -> None:
        self.theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(16, 16, -16, -16)

        track_pen = QPen(QColor(rgba(self.theme.outline, 0.28)))
        track_pen.setWidth(12)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 90 * 16, -360 * 16)

        glow_pen = QPen(QColor(rgba(self.theme.primary, 0.14)))
        glow_pen.setWidth(18)
        glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(glow_pen)
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * self.progress))

        progress_pen = QPen(QColor(self.theme.primary))
        progress_pen.setWidth(10)
        progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(progress_pen)
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * self.progress))


class PomodoroWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.material_font = self.icon_font
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._settings_mtime = SETTINGS_FILE.stat().st_mtime if SETTINGS_FILE.exists() else 0.0
        self.settings_state = load_settings_state()
        self.mode = "work"
        self.running = False
        self.completed_focus_sessions = 0
        self.remaining_seconds = 0
        self.total_seconds = 0
        self._fade: QPropertyAnimation | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("Hanauta Pomodoro")
        self.setFixedSize(452, 560)

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._tick)
        self.tick_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_or_settings_if_needed)
        self.theme_timer.start(3000)

        self._build_ui()
        self._apply_shadow()
        self._apply_styles()
        self._place_window()
        self._animate_in()
        self._reset_mode(self.mode)

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
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(3)
        title = QLabel("Pomodoro Timer")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 20, QFont.Weight.DemiBold))
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setFont(QFont(self.ui_font, 9))
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.settings_button = self._icon_button("settings")
        self.settings_button.clicked.connect(self._open_settings)
        self.close_button = create_close_button(material_icon("close"), self.material_font)
        self.close_button.clicked.connect(self.close)
        actions.addWidget(self.settings_button)
        actions.addWidget(self.close_button)
        header.addLayout(actions)
        layout.addLayout(header)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(12)

        self.ring = ProgressRing()
        self.ring_wrap = QWidget()
        ring_layout = QVBoxLayout(self.ring_wrap)
        ring_layout.setContentsMargins(0, 0, 0, 0)
        ring_layout.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignCenter)

        self.time_label = QLabel("25:00", self.ring)
        self.time_label.setObjectName("timeLabel")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setGeometry(30, 74, 164, 42)
        self.time_label.setFont(QFont(self.display_font, 27, QFont.Weight.DemiBold))

        self.mode_label = QLabel("Work", self.ring)
        self.mode_label.setObjectName("modeLabel")
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mode_label.setGeometry(56, 120, 112, 28)
        self.mode_label.setFont(QFont(self.ui_font, 11, QFont.Weight.Medium))

        hero_layout.addWidget(self.ring_wrap)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(0, 2, 0, 0)
        self.start_pause_button = self._icon_action_button("play_arrow")
        self.start_pause_button.clicked.connect(self._toggle_running)
        self.reset_button = self._icon_action_button("restart_alt")
        self.reset_button.clicked.connect(lambda: self._reset_mode(self.mode))
        controls.addStretch(1)
        controls.addWidget(self.start_pause_button)
        controls.addWidget(self.reset_button)
        controls.addStretch(1)
        hero_layout.addLayout(controls)
        layout.addWidget(self.hero)

        quick_title = QLabel("Quick Actions")
        quick_title.setObjectName("sectionTitle")
        quick_title.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        layout.addWidget(quick_title)

        quick_actions = QHBoxLayout()
        quick_actions.setSpacing(10)
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode_key in ("work", "short_break", "long_break"):
            button = QPushButton(MODE_META[mode_key]["label"])
            button.setObjectName("modeButton")
            button.setCheckable(True)
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.clicked.connect(lambda checked=False, key=mode_key: self._select_mode(key))
            quick_actions.addWidget(button, 1)
            self.mode_buttons[mode_key] = button
        layout.addLayout(quick_actions)

        self.stats_card = QFrame()
        self.stats_card.setObjectName("statsCard")
        stats_layout = QVBoxLayout(self.stats_card)
        stats_layout.setContentsMargins(16, 14, 16, 14)
        stats_layout.setSpacing(6)
        self.completed_label = QLabel("")
        self.completed_label.setObjectName("statsTitle")
        self.completed_label.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        self.next_long_break_label = QLabel("")
        self.next_long_break_label.setObjectName("statsBody")
        self.next_long_break_label.setFont(QFont(self.ui_font, 10))
        stats_layout.addWidget(self.completed_label)
        stats_layout.addWidget(self.next_long_break_label)
        layout.addWidget(self.stats_card)

        layout.addStretch(1)

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(38, 38)
        button.setFont(QFont(self.icon_font, 18))
        return button

    def _icon_action_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("actionButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(44, 44)
        button.setFont(QFont(self.icon_font, 22))
        return button

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 132))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        x = available.x() + available.width() - self.width() - 56
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
        self.ring.set_theme(theme)
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#panel {{
                background: {rgba(theme.surface_container, 0.94)};
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 30px;
            }}
            QLabel#title {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#statsBody {{
                color: {theme.text_muted};
            }}
            QFrame#heroCard, QFrame#statsCard {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 24px;
            }}
            QFrame#heroCard {{
                background: {rgba(theme.surface_container_high, 0.90)};
            }}
            QLabel#timeLabel {{
                color: {theme.primary};
                background: transparent;
            }}
            QLabel#modeLabel {{
                color: {theme.text};
                background: transparent;
            }}
            QLabel#sectionTitle, QLabel#statsTitle {{
                color: {theme.text};
            }}
            QPushButton#iconButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.primary};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                font-family: "{self.icon_font}";
            }}
            QPushButton#actionButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.primary};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                font-family: "{self.icon_font}";
            }}
            QPushButton#modeButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                padding: 12px 14px;
                font-weight: 600;
            }}
            QPushButton#modeButton:checked {{
                background: {theme.primary};
                color: {theme.active_text};
                border: 1px solid {rgba(theme.primary, 0.80)};
            }}
            QPushButton#modeButton:hover, QPushButton#iconButton:hover, QPushButton#actionButton:hover {{
                background: {theme.hover_bg};
                color: {theme.text};
            }}
            """
        )
        self._update_controls()

    def _reload_theme_or_settings_if_needed(self) -> None:
        theme_mtime = palette_mtime()
        if theme_mtime != self._theme_mtime:
            self._theme_mtime = theme_mtime
            self.theme = load_theme_palette()
            self._apply_styles()
        settings_mtime = SETTINGS_FILE.stat().st_mtime if SETTINGS_FILE.exists() else 0.0
        if settings_mtime != self._settings_mtime:
            self._settings_mtime = settings_mtime
            self.settings_state = load_settings_state()
            if not self.running:
                self._reset_mode(self.mode)
            self._update_stats()

    def _current_duration_seconds(self, mode: str) -> int:
        pomodoro = self.settings_state.get("pomodoro", {})
        minutes = {
            "work": int(pomodoro.get("work_minutes", 25)),
            "short_break": int(pomodoro.get("short_break_minutes", 5)),
            "long_break": int(pomodoro.get("long_break_minutes", 15)),
        }.get(mode, 25)
        return max(60, minutes * 60)

    def _select_mode(self, mode: str) -> None:
        self.mode = mode
        self._reset_mode(mode)

    def _reset_mode(self, mode: str) -> None:
        self.running = False
        self.mode = mode
        self.total_seconds = self._current_duration_seconds(mode)
        self.remaining_seconds = self.total_seconds
        self._update_timer_display()
        self._update_controls()

    def _toggle_running(self) -> None:
        self.running = not self.running
        self._update_controls()

    def _tick(self) -> None:
        if not self.running:
            return
        self.remaining_seconds = max(0, self.remaining_seconds - 1)
        self._update_timer_display()
        if self.remaining_seconds == 0:
            self.running = False
            self._handle_completion()
            self._update_controls()

    def _handle_completion(self) -> None:
        meta = MODE_META[self.mode]
        notify(meta["completion_title"], meta["completion_body"])
        pomodoro = self.settings_state.get("pomodoro", {})
        auto_start_breaks = bool(pomodoro.get("auto_start_breaks", False))
        auto_start_focus = bool(pomodoro.get("auto_start_focus", False))

        if self.mode == "work":
            self.completed_focus_sessions += 1
            long_break_every = max(2, int(pomodoro.get("long_break_every", 4)))
            next_mode = "long_break" if self.completed_focus_sessions % long_break_every == 0 else "short_break"
            self._reset_mode(next_mode)
            if auto_start_breaks:
                self.running = True
        else:
            self._reset_mode("work")
            if auto_start_focus:
                self.running = True
        self._update_controls()
        self._update_stats()

    def _update_timer_display(self) -> None:
        self.time_label.setText(format_duration(self.remaining_seconds))
        self.mode_label.setText(MODE_META[self.mode]["label"])
        progress = 1.0 - (self.remaining_seconds / self.total_seconds if self.total_seconds else 0.0)
        self.ring.set_progress(progress)
        self._update_stats()

    def _update_controls(self) -> None:
        self.start_pause_button.setText(material_icon("pause" if self.running else "play_arrow"))
        self.start_pause_button.setToolTip("Pause timer" if self.running else "Start timer")
        for key, button in self.mode_buttons.items():
            was_blocked = button.blockSignals(True)
            button.setChecked(key == self.mode)
            button.blockSignals(was_blocked)
        headline = MODE_META[self.mode]["headline"]
        self.subtitle.setText(f"{headline} • {self.completed_focus_sessions} completed")

    def _update_stats(self) -> None:
        self.completed_label.setText(f"{self.completed_focus_sessions} pomodoro(s) completed")
        long_break_every = max(2, int(self.settings_state.get("pomodoro", {}).get("long_break_every", 4)))
        completed_in_cycle = self.completed_focus_sessions % long_break_every
        remaining = long_break_every - completed_in_cycle if completed_in_cycle else long_break_every
        if self.completed_focus_sessions > 0 and completed_in_cycle == 0:
            self.next_long_break_label.setText(
                f"Cycle cleared. Next long break after {long_break_every} more focus session(s)."
            )
        else:
            self.next_long_break_label.setText(f"Next long break after {remaining} more focus session(s).")

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        try:
            command = entry_command(SETTINGS_PAGE_SCRIPT, "--page", "services", "--service-section", "pomodoro_widget")
            if not command:
                return
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    widget = PomodoroWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
