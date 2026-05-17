#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
except Exception:  # pragma: no cover - optional runtime dependency
    QAudioOutput = None  # type: ignore[assignment]
    QMediaPlayer = None  # type: ignore[assignment]
    QUrl = None  # type: ignore[assignment]


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[2]
ROOT = HERE.parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"
DEFAULT_ALERT_SOUND = Path("/usr/share/sounds/freedesktop/stereo/complete.ogg")

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))

from pyqt.shared.runtime import entry_command
from pyqt.shared.theme import blend, load_theme_palette, rgba
from pyqt.shared.plugin_runtime import resolve_plugin_script


def _load_reminder_queue_helpers():
    queue_script = resolve_plugin_script("reminder_queue.py", ["reminders"], required=False)
    if queue_script is None or not queue_script.exists():
        return None, None
    try:
        import importlib.util
        import sys
        module_name = f"hanauta_reminder_queue_{hash(str(queue_script)) & 0xFFFFFFFF:x}"
        spec = importlib.util.spec_from_file_location(module_name, str(queue_script))
        if spec is None or spec.loader is None:
            return None, None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        enqueue = getattr(module, "enqueue_reminder", None)
        ensure = getattr(module, "ensure_daemon_running", None)
        if callable(enqueue) and callable(ensure):
            return enqueue, ensure
    except Exception:
        return None, None
    return None, None


_ENQUEUE_REMINDER, _ENSURE_DAEMON_RUNNING = _load_reminder_queue_helpers()


MATERIAL_ICONS = {
    "alarm": "\ue855",
    "check": "\ue5ca",
    "snooze": "\ue046",
    "notifications_active": "\ue7f7",
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


class ReminderAlert(QWidget):
    def __init__(self, title: str, body: str, severity: str, mode: str = "reminder") -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.theme = load_theme_palette()
        self.title_text = title.strip() or "Reminder"
        self.body_text = body.strip() or "Time is up."
        self.severity = (severity or "discrete").strip().lower()
        self.mode = (mode or "reminder").strip().lower()
        if self.mode not in {"reminder", "confirm"}:
            self.mode = "reminder"
        self._fade: QPropertyAnimation | None = None
        self._audio_player = None
        self._audio_output = None
        self._audio_fade_timer: QTimer | None = None
        self._audio_process: subprocess.Popen[str] | None = None
        self._i3_rules_applied = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
        self.setWindowFlags(flags)
        self.setWindowTitle("Hanauta Reminder")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._register_shortcuts()
        self._animate_in()
        self._start_sound()
        self._position_overlay()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._i3_rules_applied:
            return
        self._i3_rules_applied = True
        QTimer.singleShot(0, self._set_window_identity)
        QTimer.singleShot(120, self._apply_i3_window_rules)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        backdrop = QFrame()
        backdrop.setObjectName("backdrop")
        root_wrap = QVBoxLayout(backdrop)
        root_wrap.setContentsMargins(40, 40, 40, 40)
        root_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setMaximumWidth(620)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(18)

        icon_label = QLabel(material_icon("notifications_active"))
        icon_label.setObjectName("heroIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(78, 78)
        icon_label.setFont(QFont(self.icon_font, 38))
        card_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        overline = QLabel("FULLSCREEN REMINDER")
        overline.setObjectName("overline")
        overline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overline.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        card_layout.addWidget(overline)

        title = QLabel(self.title_text)
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        title.setFont(QFont(self.display_font, 28, QFont.Weight.DemiBold))
        card_layout.addWidget(title)

        detail = QLabel(self.body_text)
        detail.setObjectName("detail")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setWordWrap(True)
        detail.setFont(QFont(self.ui_font, 12))
        card_layout.addWidget(detail)

        severity = QLabel(self.severity.capitalize())
        severity.setObjectName("severity")
        severity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        severity.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        severity.setMinimumWidth(120)
        card_layout.addWidget(severity, 0, Qt.AlignmentFlag.AlignHCenter)

        hint_text = (
            "Choose Yes, No, or Cancel."
            if self.mode == "confirm"
            else "Choose an action so Hanauta knows whether to clear it or remind you again."
        )
        hint = QLabel(hint_text)
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        hint.setFont(QFont(self.ui_font, 10))
        card_layout.addWidget(hint)

        self.actions_wrap = QFrame()
        self.actions_wrap.setObjectName("actionsWrap")
        actions = QHBoxLayout(self.actions_wrap)
        actions.setContentsMargins(10, 10, 10, 10)
        actions.setSpacing(12)

        if self.mode == "confirm":
            yes_btn = self._action_button("Yes", material_icon("check"), primary=True)
            yes_btn.clicked.connect(self.close)
            actions.addWidget(yes_btn)

            no_btn = self._action_button("No", material_icon("close"))
            no_btn.clicked.connect(self.close)
            actions.addWidget(no_btn)

            cancel_btn = self._action_button("Cancel", material_icon("close"))
            cancel_btn.clicked.connect(self.close)
            actions.addWidget(cancel_btn)
        else:
            dismiss_button = self._action_button("Done", material_icon("check"), primary=True)
            dismiss_button.clicked.connect(self.close)
            actions.addWidget(dismiss_button)

            snooze_short = self._action_button("Snooze 5 min", material_icon("snooze"))
            snooze_short.clicked.connect(lambda: self._snooze(5))
            actions.addWidget(snooze_short)

            snooze_long = self._action_button("Snooze 15 min", material_icon("alarm"))
            snooze_long.clicked.connect(lambda: self._snooze(15))
            actions.addWidget(snooze_long)

        card_layout.addWidget(self.actions_wrap)
        root_wrap.addWidget(self.card, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(backdrop)

    def _action_button(self, label: str, icon_text: str, *, primary: bool = False) -> QPushButton:
        button = QPushButton(f"{icon_text}  {label}")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setMinimumHeight(48)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        button.setObjectName("primaryButton" if primary else "secondaryButton")
        return button

    def _apply_styles(self) -> None:
        theme = self.theme
        accent = theme.primary if self.severity != "disturbing" else theme.error
        accent_soft = rgba(accent, 0.22)
        card_bg = rgba(theme.surface_container, 0.88)
        card_border = rgba(accent, 0.30)
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#backdrop {{
                background: rgba(10, 12, 18, 0.92);
            }}
            QFrame#card {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.surface_container_high, 0.97)},
                    stop: 1 {card_bg}
                );
                border: 1px solid {card_border};
                border-radius: 34px;
            }}
            QLabel#heroIcon {{
                background: {accent_soft};
                border: 1px solid {rgba(accent, 0.36)};
                border-radius: 39px;
                color: {accent};
                font-family: "{self.icon_font}";
            }}
            QLabel#overline {{
                color: {accent};
                letter-spacing: 2px;
            }}
            QLabel#title {{
                color: {theme.text};
            }}
            QLabel#detail, QLabel#hint {{
                color: {theme.text_muted};
            }}
            QLabel#severity {{
                background: {rgba(theme.on_surface, 0.06)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                border-radius: 15px;
                color: {accent};
                padding: 6px 14px;
            }}
            QFrame#actionsWrap {{
                background: {rgba(theme.on_surface, 0.035)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 24px;
            }}
            QPushButton#primaryButton, QPushButton#secondaryButton {{
                border-radius: 18px;
                padding: 0 18px;
            }}
            QPushButton#primaryButton {{
                background: {accent};
                border: none;
                color: {theme.active_text if self.severity != "disturbing" else theme.on_error};
            }}
            QPushButton#primaryButton:hover {{
                background: {blend(accent, theme.primary_container, 0.32)};
            }}
            QPushButton#secondaryButton {{
                background: {rgba(theme.on_surface, 0.05)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                color: {theme.text};
            }}
            QPushButton#secondaryButton:hover {{
                background: {rgba(accent, 0.12)};
                border: 1px solid {rgba(accent, 0.28)};
            }}
            """
        )

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(72)
        shadow.setOffset(0, 24)
        shadow.setColor(QColor(0, 0, 0, 210))
        self.card.setGraphicsEffect(shadow)

    def _register_shortcuts(self) -> None:
        QShortcut(QKeySequence("Escape"), self, activated=self.close)
        QShortcut(QKeySequence("Return"), self, activated=self.close)
        QShortcut(QKeySequence("Enter"), self, activated=self.close)
        QShortcut(QKeySequence("1"), self, activated=self.close)
        if self.mode == "reminder":
            QShortcut(QKeySequence("2"), self, activated=lambda: self._snooze(5))
            QShortcut(QKeySequence("3"), self, activated=lambda: self._snooze(15))

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(220)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _position_overlay(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.geometry()
        self.setGeometry(geometry)

    def _set_window_identity(self) -> None:
        try:
            wid = int(self.winId())
            subprocess.run(
                ["xprop", "-id", hex(wid), "-f", "_NET_WM_NAME", "8t", "-set", "_NET_WM_NAME", self.windowTitle()],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            subprocess.run(
                ["xprop", "-id", hex(wid), "-f", "WM_CLASS", "8s", "-set", "WM_CLASS", "HanautaReminder"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def _apply_i3_window_rules(self) -> None:
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="Hanauta Reminder"]',
                    "floating enable, sticky enable, border pixel 0, move position 0 0",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass
        self._position_overlay()

    def _start_sound(self) -> None:
        if DEFAULT_ALERT_SOUND.exists() and QMediaPlayer is not None and QAudioOutput is not None and QUrl is not None:
            try:
                self._audio_player = QMediaPlayer(self)
                self._audio_output = QAudioOutput(self)
                self._audio_output.setVolume(0.02)
                self._audio_player.setAudioOutput(self._audio_output)
                self._audio_player.setSource(QUrl.fromLocalFile(str(DEFAULT_ALERT_SOUND)))
                self._audio_player.play()
                self._audio_fade_timer = QTimer(self)
                self._audio_fade_timer.setInterval(180)
                self._audio_fade_timer.timeout.connect(self._step_audio_volume)
                self._audio_fade_timer.start()
                return
            except Exception:
                self._audio_player = None
                self._audio_output = None
                self._audio_fade_timer = None

        if DEFAULT_ALERT_SOUND.exists() and shutil.which("paplay"):
            try:
                self._audio_process = subprocess.Popen(
                    ["paplay", "--volume=16000", str(DEFAULT_ALERT_SOUND)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    text=True,
                )
            except Exception:
                self._audio_process = None

    def _step_audio_volume(self) -> None:
        if self._audio_output is None or self._audio_fade_timer is None:
            return
        next_volume = min(0.24, self._audio_output.volume() + 0.03)
        self._audio_output.setVolume(next_volume)
        if next_volume >= 0.24:
            self._audio_fade_timer.stop()

    def _snooze(self, minutes: int) -> None:
        if _ENQUEUE_REMINDER is not None and _ENSURE_DAEMON_RUNNING is not None:
            _ENQUEUE_REMINDER(
                self.title_text,
                self.body_text,
                self.severity,
                delay_seconds=max(1, minutes) * 60,
            )
            daemon_script = resolve_plugin_script("reminder_daemon.py", ["reminders"], required=False)
            if daemon_script is not None and daemon_script.exists():
                _ENSURE_DAEMON_RUNNING(entry_command(daemon_script))
        self.close()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._audio_fade_timer is not None:
            self._audio_fade_timer.stop()
        if self._audio_player is not None:
            self._audio_player.stop()
        super().closeEvent(event)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fullscreen reminder alert")
    parser.add_argument("--title", default="Reminder")
    parser.add_argument("--body", default="Time is up.")
    parser.add_argument("--severity", default="discrete")
    parser.add_argument("--mode", default="reminder", choices=["reminder", "confirm"])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta Fullscreen Alert")
    window = ReminderAlert(args.title, args.body, args.severity, args.mode)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
