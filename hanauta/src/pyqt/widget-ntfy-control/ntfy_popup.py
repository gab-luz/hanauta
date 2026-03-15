#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compact PyQt6 ntfy publish popup.
"""

from __future__ import annotations

import base64
import json
import signal
import sys
from pathlib import Path
from urllib import error, parse, request

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.button_helpers import create_close_button

FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

MATERIAL_ICONS = {
    "notifications": "\ue7f4",
    "send": "\ue163",
    "close": "\ue5cd",
}


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "material_symbols_outlined": FONTS_DIR / "MaterialSymbolsOutlined.ttf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
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


def load_ntfy_settings() -> dict[str, str | bool]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    ntfy = payload.get("ntfy", {}) if isinstance(payload, dict) else {}
    if not isinstance(ntfy, dict):
        ntfy = {}
    return {
        "enabled": bool(ntfy.get("enabled", False)),
        "server_url": str(ntfy.get("server_url", "https://ntfy.sh")).rstrip("/"),
        "topic": str(ntfy.get("topic", "")),
        "token": str(ntfy.get("token", "")),
        "username": str(ntfy.get("username", "")),
        "password": str(ntfy.get("password", "")),
    }


def send_ntfy_message(settings: dict[str, str | bool], title: str, message: str, topic_override: str = "") -> tuple[bool, str]:
    server_url = str(settings.get("server_url", "")).strip().rstrip("/")
    topic = (topic_override or str(settings.get("topic", ""))).strip()
    token = str(settings.get("token", ""))
    username = str(settings.get("username", ""))
    password = str(settings.get("password", ""))
    if not server_url:
        return False, "Server URL is required."
    if not topic:
        return False, "Topic is required."
    if not message.strip():
        return False, "Message is required."
    url = f"{server_url}/{parse.quote(topic)}"
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    if title.strip():
        headers["Title"] = title.strip()
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    req = request.Request(url, data=message.encode("utf-8"), headers=headers, method="POST")
    if username.strip() or password.strip():
        credentials = f"{username.strip()}:{password}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {encoded}")
    try:
        with request.urlopen(req, timeout=8) as response:
            response.read()
        return True, "Message sent."
    except error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            detail = ""
        return False, detail or f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


class NtfyPopup(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.material_font = detect_font(
            self.loaded_fonts.get("material_icons", ""),
            self.loaded_fonts.get("material_icons_outlined", ""),
            self.loaded_fonts.get("material_symbols_outlined", ""),
            self.loaded_fonts.get("material_symbols_rounded", ""),
            "Material Icons",
            "Material Icons Outlined",
            "Material Symbols Outlined",
            "Material Symbols Rounded",
        )
        self.ui_font = detect_font("Inter", "Noto Sans", "DejaVu Sans", "Sans Serif")
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.settings = load_ntfy_settings()
        self._fade: QPropertyAnimation | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(404, 388)
        self.setWindowTitle("ntfy Publisher")

        self._build_ui()
        self._apply_styles()
        self._apply_window_effects()
        self._place_window()
        self._animate_in()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("ntfy")
        title.setObjectName("titleLabel")
        title.setFont(QFont(self.ui_font, 20, QFont.Weight.DemiBold))
        icon = QLabel(material_icon("notifications"))
        icon.setObjectName("heroIcon")
        icon.setFont(QFont(self.material_font, 18))
        header.addWidget(title, 1)
        header.addWidget(icon)
        self.close_button = create_close_button(material_icon("close"), self.material_font)
        self.close_button.setProperty("iconButton", True)
        self.close_button.setFixedSize(36, 36)
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button)
        layout.addLayout(header)

        subtitle = QLabel("Publish a message to your configured ntfy topic.")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setFont(QFont(self.ui_font, 10))
        layout.addWidget(subtitle)

        self.topic_input = QLineEdit(str(self.settings.get("topic", "")))
        self.topic_input.setPlaceholderText("Topic")
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Title")
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Message")
        self.message_input.setMinimumHeight(140)
        layout.addWidget(self.topic_input)
        layout.addWidget(self.title_input)
        layout.addWidget(self.message_input)

        actions = QHBoxLayout()
        self.status_label = QLabel("" if self.settings.get("enabled", False) else "ntfy is disabled in settings.")
        self.status_label.setObjectName("statusLabel")
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primaryButton")
        self.send_button.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        self.send_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.send_button.clicked.connect(self._send)
        actions.addWidget(self.status_label, 1)
        actions.addWidget(self.send_button)
        layout.addLayout(actions)

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
            }}
            QFrame#panel {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 24px;
            }}
            QLabel#titleLabel {{
                color: {theme.text};
            }}
            QLabel#heroIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            QLabel#subtitleLabel, QLabel#statusLabel {{
                color: {theme.text_muted};
            }}
            QPushButton#iconButton {{
                background: transparent;
                border: none;
                border-radius: 999px;
                color: {theme.text_muted};
                font-family: "{self.material_font}";
            }}
            QPushButton#iconButton:hover {{
                background: {theme.hover_bg};
                color: {theme.text};
            }}
            QLineEdit, QTextEdit {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 16px;
                color: {theme.text};
                padding: 10px 12px;
                selection-background-color: {theme.hover_bg};
            }}
            QTextEdit {{
                padding-top: 12px;
            }}
            QPushButton#primaryButton {{
                background: {theme.primary};
                border: none;
                border-radius: 16px;
                color: {theme.active_text};
                padding: 0 16px;
                min-height: 36px;
            }}
            QPushButton#primaryButton:hover {{
                background: {theme.primary_container};
                color: {theme.on_primary_container};
            }}
            """
        )

    def _apply_window_effects(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 190))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.x() + rect.width() - self.width() - 18, rect.y() + 52)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()

    def _send(self) -> None:
        self.settings = load_ntfy_settings()
        if not self.settings.get("enabled", False):
            self.status_label.setText("Enable ntfy in settings first.")
            return
        ok, message = send_ntfy_message(
            self.settings,
            self.title_input.text(),
            self.message_input.toPlainText(),
            self.topic_input.text().strip(),
        )
        self.status_label.setText(message)
        if ok:
            self.message_input.clear()


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)
    popup = NtfyPopup()
    popup.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
