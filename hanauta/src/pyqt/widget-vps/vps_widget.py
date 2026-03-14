#!/usr/bin/env python3
from __future__ import annotations

import shlex
import signal
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
import json


MATERIAL_ICONS = {
    "settings": "\ue8b8",
    "refresh": "\ue5d5",
    "storage": "\ue1db",
    "terminal": "\ue31c",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def python_bin() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def load_settings_state() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("vps", {})
    payload.setdefault("services", {})
    return payload


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for key, path in {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
    }.items():
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


class VpsWidget(QWidget):
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

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hanauta VPS")
        self.setFixedSize(548, 664)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self.refresh_health()

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
        eyebrow = QLabel("VPS CARE")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        title = QLabel("Keep the server healthy")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 22, QFont.Weight.DemiBold))
        self.subtitle = QLabel("Run health checks, updates, and service restarts over SSH.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_health)
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
        self.hero_title = QLabel("No VPS configured")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 18, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("Save an SSH target in Settings to start checking server health.")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setWordWrap(True)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_detail)
        layout.addWidget(self.hero)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.health_button = QPushButton("Health check")
        self.health_button.setObjectName("primaryButton")
        self.health_button.clicked.connect(self.refresh_health)
        self.update_button = QPushButton("Run updates")
        self.update_button.setObjectName("secondaryButton")
        self.update_button.clicked.connect(self.run_updates)
        self.restart_button = QPushButton("Restart service")
        self.restart_button.setObjectName("secondaryButton")
        self.restart_button.clicked.connect(self.restart_service)
        buttons.addWidget(self.health_button)
        buttons.addWidget(self.update_button)
        buttons.addWidget(self.restart_button)
        layout.addLayout(buttons)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("output")
        layout.addWidget(self.output, 1)

        self.status_label = QLabel("VPS widget is idle.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(38, 38)
        button.setFont(QFont(self.icon_font, 18))
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
        self.move(available.x() + available.width() - self.width() - 48, available.y() + 92)

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
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#panel {{
                background: {rgba(theme.surface_container, 0.94)};
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 28px;
            }}
            QLabel#eyebrow {{
                color: {theme.primary};
                letter-spacing: 1.3px;
            }}
            QLabel#title, QLabel#heroTitle {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#heroDetail, QLabel#statusLabel {{
                color: {theme.text_muted};
            }}
            QFrame#heroCard, QPlainTextEdit#output {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 22px;
            }}
            QFrame#heroCard {{
                background: {rgba(theme.surface_container_high, 0.90)};
            }}
            QPushButton#iconButton, QPushButton#secondaryButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                padding: 8px 12px;
            }}
            QPushButton#iconButton {{
                color: {theme.primary};
                font-family: "{self.icon_font}";
            }}
            QPushButton#primaryButton {{
                background: {theme.primary};
                color: {theme.on_primary_container};
                border: none;
                border-radius: 999px;
                padding: 10px 14px;
                font-weight: 600;
            }}
            QPlainTextEdit#output {{
                padding: 10px;
            }}
            """
        )

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()

    def _ssh_base(self) -> list[str]:
        self.settings_state = load_settings_state()
        vps = self.settings_state.get("vps", {})
        host = str(vps.get("host", "")).strip()
        username = str(vps.get("username", "")).strip()
        port = str(vps.get("port", 22) or 22)
        if not host:
            return []
        target = f"{username}@{host}" if username else host
        cmd = ["ssh", "-p", port]
        identity = str(vps.get("identity_file", "")).strip()
        if identity:
            cmd.extend(["-i", identity])
        cmd.append(target)
        return cmd

    def _run_remote(self, command: str) -> tuple[bool, str]:
        base = self._ssh_base()
        if not base:
            return False, "Configure your VPS host in Settings first."
        try:
            result = subprocess.run(
                [*base, command],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        except Exception as exc:
            return False, str(exc)
        text = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        return result.returncode == 0, text.strip() or "No output."

    def refresh_health(self) -> None:
        self.settings_state = load_settings_state()
        vps = self.settings_state.get("vps", {})
        host = str(vps.get("host", "")).strip()
        if not host:
            self.hero_title.setText("No VPS configured")
            self.hero_detail.setText("Save an SSH target in Settings to start checking server health.")
            self.output.setPlainText("No VPS host configured yet.")
            return
        username = str(vps.get("username", "")).strip()
        target = f"{username}@{host}" if username else host
        self.hero_title.setText(target)
        self.hero_detail.setText("Running remote health command…")
        success, output = self._run_remote(str(vps.get("health_command", "uptime && df -h /")))
        self.output.setPlainText(output)
        self.hero_detail.setText("Latest health check captured below." if success else "Health check failed.")
        self.status_label.setText("VPS health check complete." if success else "VPS health check failed.")

    def run_updates(self) -> None:
        self.settings_state = load_settings_state()
        command = str(self.settings_state.get("vps", {}).get("update_command", "sudo apt update && sudo apt upgrade -y"))
        success, output = self._run_remote(command)
        self.output.setPlainText(output)
        self.status_label.setText("Remote updates finished." if success else "Remote updates failed.")

    def restart_service(self) -> None:
        self.settings_state = load_settings_state()
        service = str(self.settings_state.get("vps", {}).get("app_service", "")).strip()
        if not service:
            self.status_label.setText("Save an app service in Settings first.")
            return
        success, output = self._run_remote(f"sudo systemctl restart {shlex.quote(service)} && systemctl status {shlex.quote(service)} --no-pager --lines=20")
        self.output.setPlainText(output)
        self.status_label.setText(f"{service} restarted." if success else f"Could not restart {service}.")

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        try:
            subprocess.Popen(
                [python_bin(), str(SETTINGS_PAGE_SCRIPT), "--page", "services", "--service-section", "vps_widget"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    widget = VpsWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
