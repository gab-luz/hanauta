#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Caps/Num lock OSD daemon for Hanauta (X11/i3)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette

ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_FILE = (
    Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
)

MATERIAL_ICONS = {
    "keyboard_capslock": "\ue318",
    "dialpad": "\ue0bc",
}


def run_text(cmd: list[str], timeout: float = 1.2) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def parse_lock_states(raw: str) -> tuple[bool | None, bool | None]:
    if not raw.strip():
        return None, None
    caps_match = re.search(r"Caps\s+Lock:\s*(on|off)", raw, flags=re.IGNORECASE)
    num_match = re.search(r"Num\s+Lock:\s*(on|off)", raw, flags=re.IGNORECASE)
    caps = None if caps_match is None else caps_match.group(1).lower() == "on"
    num = None if num_match is None else num_match.group(1).lower() == "on"
    return caps, num


def load_lock_osd_settings() -> tuple[bool, str]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    notifications = payload.get("notifications", {}) if isinstance(payload, dict) else {}
    enabled = (
        bool(notifications.get("lock_osd_enabled", True))
        if isinstance(notifications, dict)
        else True
    )
    value = (
        str(notifications.get("lock_osd_position", "bottom_center")).strip()
        if isinstance(notifications, dict)
        else "bottom_center"
    )
    allowed = {
        "top_left",
        "top_center",
        "top_right",
        "center_left",
        "center",
        "center_right",
        "bottom_left",
        "bottom_center",
        "bottom_right",
    }
    position = value if value in allowed else "bottom_center"
    return enabled, position


def load_fonts() -> tuple[str, str]:
    ui_family = "Sans Serif"
    icon_family = "Material Icons"

    ui_font_path = FONTS_DIR / "Rubik-VariableFont_wght.ttf"
    icon_font_path = FONTS_DIR / "MaterialIcons-Regular.ttf"

    if ui_font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(ui_font_path))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                ui_family = families[0]

    if icon_font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(icon_font_path))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                icon_family = families[0]

    return ui_family, icon_family


class LockOsd(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.ui_font, self.icon_font = load_fonts()
        self._build_ui()
        self._apply_styles()
        self.hide()

    def _build_ui(self) -> None:
        self.setObjectName("lockOsdWindow")
        self.setWindowTitle("Hanauta Lock OSD")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("lockOsdCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(10)

        self.icon_label = QLabel("?")
        self.icon_label.setObjectName("lockOsdIcon")
        self.icon_label.setFont(QFont(self.icon_font, 22))
        self.icon_label.setFixedWidth(28)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.title_label = QLabel("Caps Lock")
        self.title_label.setObjectName("lockOsdTitle")
        self.title_label.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))

        self.state_label = QLabel("On")
        self.state_label.setObjectName("lockOsdState")
        self.state_label.setFont(QFont(self.ui_font, 10))

        text_col.addWidget(self.title_label)
        text_col.addWidget(self.state_label)

        card_layout.addWidget(self.icon_label)
        card_layout.addLayout(text_col, 1)
        root.addWidget(card)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def _apply_styles(self) -> None:
        theme = load_theme_palette()
        bg = QColor(theme.surface_container)
        bg.setAlphaF(0.95)
        border = QColor(theme.outline)
        border.setAlphaF(0.35)

        self.setStyleSheet(
            f"""
            QWidget#lockOsdWindow {{
                background: transparent;
            }}
            QFrame#lockOsdCard {{
                background: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alphaF():.2f});
                border: 1px solid rgba({border.red()}, {border.green()}, {border.blue()}, {border.alphaF():.2f});
                border-radius: 16px;
            }}
            QLabel#lockOsdIcon {{
                color: {theme.primary};
                background: transparent;
                font-family: "{self.icon_font}";
            }}
            QLabel#lockOsdTitle {{
                color: {theme.on_surface};
                background: transparent;
                font-family: "{self.ui_font}";
            }}
            QLabel#lockOsdState {{
                color: {theme.on_surface_variant};
                background: transparent;
                font-family: "{self.ui_font}";
            }}
            """
        )

    def show_state(self, key: str, enabled: bool) -> None:
        lock_osd_enabled, position = load_lock_osd_settings()
        if not lock_osd_enabled:
            return
        if key == "caps":
            self.icon_label.setText(MATERIAL_ICONS["keyboard_capslock"])
            self.title_label.setText("Caps Lock")
        else:
            self.icon_label.setText(MATERIAL_ICONS["dialpad"])
            self.title_label.setText("Num Lock")
        self.state_label.setText("On" if enabled else "Off")

        self.adjustSize()
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            margin = 24
            if position.endswith("left"):
                x = geo.x() + margin
            elif position.endswith("right"):
                x = geo.x() + geo.width() - self.width() - margin
            else:
                x = geo.x() + (geo.width() - self.width()) // 2

            if position.startswith("top"):
                y = geo.y() + margin
            elif position.startswith("center"):
                y = geo.y() + (geo.height() - self.height()) // 2
            else:
                y = geo.y() + geo.height() - self.height() - margin
            self.move(max(geo.x(), x), max(geo.y(), y))

        self.show()
        self.raise_()
        self.hide_timer.start(1400)


class LockStateWatcher:
    def __init__(self, osd: LockOsd) -> None:
        self.osd = osd
        self.last_caps: bool | None = None
        self.last_num: bool | None = None

        self.timer = QTimer()
        self.timer.setInterval(140)
        self.timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._poll(initial=True)
        self.timer.start()

    def _poll(self, initial: bool = False) -> None:
        caps, num = parse_lock_states(run_text(["xset", "q"]))
        if caps is None and num is None:
            return

        if self.last_caps is None:
            self.last_caps = caps
        if self.last_num is None:
            self.last_num = num

        if not initial and caps is not None and caps != self.last_caps:
            self.last_caps = caps
            self.osd.show_state("caps", caps)

        if not initial and num is not None and num != self.last_num:
            self.last_num = num
            self.osd.show_state("num", num)

        if initial:
            self.last_caps = caps if caps is not None else self.last_caps
            self.last_num = num if num is not None else self.last_num


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    osd = LockOsd()
    watcher = LockStateWatcher(osd)
    watcher.start()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
