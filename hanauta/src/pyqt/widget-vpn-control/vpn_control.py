#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compact PyQt6 WireGuard control popup.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


ROOT = Path(__file__).resolve().parents[4]
APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba

SCRIPTS_DIR = APP_DIR / "eww" / "scripts"
FONTS_DIR = ROOT / "assets" / "fonts"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SETTINGS_FILE = STATE_DIR / "settings.json"

MATERIAL_ICONS = {
    "close": "\ue5cd",
    "lock": "\ue897",
    "lock_open": "\ue898",
    "refresh": "\ue5d5",
    "shield": "\ue9e0",
    "tune": "\ue429",
}


def service_enabled() -> bool:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return True
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return True
    current = services.get("vpn_control", {})
    if not isinstance(current, dict):
        return True
    return bool(current.get("enabled", True))


def run_cmd(cmd: list[str], timeout: float = 3.0) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def run_script(script_name: str, *args: str) -> str:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return ""
    return run_cmd([str(script_path), *args])


def run_script_bg(script_name: str, *args: str) -> None:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return
    try:
        subprocess.Popen(
            [str(script_path), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


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


class VpnToggleWorker(QThread):
    completed = pyqtSignal(bool, str)

    def __init__(self, interface: str) -> None:
        super().__init__()
        self.interface = interface

    def run(self) -> None:
        script_path = SCRIPTS_DIR / "vpn.sh"
        if not script_path.exists():
            self.completed.emit(False, "Missing vpn.sh helper.")
            return

        try:
            result = subprocess.run(
                [str(script_path), "--toggle-wg", self.interface],
                capture_output=True,
                text=True,
                timeout=45.0,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.completed.emit(False, "Timed out waiting for WireGuard.")
            return
        except Exception as exc:
            self.completed.emit(False, f"WireGuard toggle failed: {exc}")
            return

        payload = {}
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if stdout:
            try:
                payload = json.loads(stdout)
            except Exception:
                payload = {}

        if payload:
            ok = bool(payload.get("ok", result.returncode == 0))
            message = str(payload.get("message", "")).strip()
        else:
            ok = result.returncode == 0
            message = stdout or stderr

        if not message:
            message = "WireGuard updated." if ok else "WireGuard command failed."

        self.completed.emit(ok, message)


class VpnControlPopup(QWidget):
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
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._building_combo = False
        self._toggle_worker: VpnToggleWorker | None = None
        self._setup_window()
        self._build_ui()
        self._apply_styles()
        self.refresh_state()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_state)
        self.poll_timer.start(5000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _setup_window(self) -> None:
        self.setWindowTitle("WireGuard")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(360, 248)

        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.move(geo.x() + geo.width() - self.width() - 14, geo.y() + 50)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        icon = QLabel(material_icon("shield"))
        icon.setObjectName("headerIcon")
        icon.setFont(QFont(self.material_font, 20))
        header_text = QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(2)
        title = QLabel("WireGuard")
        title.setObjectName("title")
        subtitle = QLabel("Select a tunnel and bring it up or down.")
        subtitle.setObjectName("subtitle")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(header_text, 1)

        self.close_button = QPushButton(material_icon("close"))
        self.close_button.setObjectName("iconButton")
        self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_button.setFont(QFont(self.material_font, 18))
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.state_chip = QFrame()
        self.state_chip.setObjectName("stateChip")
        chip_layout = QHBoxLayout(self.state_chip)
        chip_layout.setContentsMargins(12, 12, 12, 12)
        chip_layout.setSpacing(10)

        self.state_icon = QLabel(material_icon("lock_open"))
        self.state_icon.setObjectName("stateIcon")
        self.state_icon.setFont(QFont(self.material_font, 18))
        chip_text = QVBoxLayout()
        chip_text.setContentsMargins(0, 0, 0, 0)
        chip_text.setSpacing(2)
        self.state_label = QLabel("Checking tunnel state…")
        self.state_label.setObjectName("stateLabel")
        self.detail_label = QLabel("No interface selected")
        self.detail_label.setObjectName("detailLabel")
        chip_text.addWidget(self.state_label)
        chip_text.addWidget(self.detail_label)
        chip_layout.addWidget(self.state_icon)
        chip_layout.addLayout(chip_text, 1)
        layout.addWidget(self.state_chip)

        combo_row = QHBoxLayout()
        combo_row.setContentsMargins(0, 0, 0, 0)
        combo_row.setSpacing(8)
        combo_icon = QLabel(material_icon("tune"))
        combo_icon.setObjectName("rowIcon")
        combo_icon.setFont(QFont(self.material_font, 18))
        self.interface_combo = QComboBox()
        self.interface_combo.setObjectName("interfaceCombo")
        self.interface_combo.setView(QListView())
        self.interface_combo.currentTextChanged.connect(self._set_interface)
        combo_row.addWidget(combo_icon)
        combo_row.addWidget(self.interface_combo, 1)
        layout.addLayout(combo_row)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self.refresh_button = QPushButton(material_icon("refresh"))
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_button.setFont(QFont(self.material_font, 18))
        self.refresh_button.clicked.connect(self.refresh_state)

        self.toggle_button = QPushButton("Enable")
        self.toggle_button.setObjectName("primaryButton")
        self.toggle_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_button.clicked.connect(self._toggle_selected)

        actions.addWidget(self.refresh_button)
        actions.addWidget(self.toggle_button, 1)
        layout.addLayout(actions)

        self.footer_label = QLabel("Available configurations update automatically.")
        self.footer_label.setObjectName("footerLabel")
        self.footer_label.setWordWrap(True)
        layout.addWidget(self.footer_label)

        root.addWidget(card)

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
                font-size: 12px;
            }}
            QFrame#card {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 24px;
            }}
            QLabel#headerIcon, QLabel#rowIcon, QLabel#stateIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            QLabel#title {{
                color: {theme.text};
                font-size: 14px;
                font-weight: 700;
            }}
            QLabel#subtitle, QLabel#detailLabel, QLabel#footerLabel {{
                color: {theme.text_muted};
                font-size: 10px;
            }}
            QLabel#stateLabel {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 700;
            }}
            QFrame#stateChip {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 20px;
            }}
            QComboBox#interfaceCombo {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                padding: 10px 12px;
                min-height: 20px;
                color: {theme.text};
                selection-background-color: {theme.hover_bg};
            }}
            QComboBox#interfaceCombo::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox#interfaceCombo::down-arrow {{
                image: none;
                width: 0;
                height: 0;
            }}
            QComboBox#interfaceCombo QAbstractItemView {{
                background: {theme.surface_container_high};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                outline: none;
                padding: 6px;
                selection-background-color: {theme.hover_bg};
                selection-color: {theme.text};
            }}
            QPushButton#iconButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
                color: {theme.icon};
                font-family: "{self.material_font}";
                min-width: 42px;
                max-width: 42px;
                min-height: 42px;
                max-height: 42px;
            }}
            QPushButton#iconButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#primaryButton {{
                background: {theme.primary};
                border: none;
                border-radius: 14px;
                color: {theme.active_text};
                font-size: 12px;
                font-weight: 700;
                min-height: 42px;
                padding: 0 18px;
            }}
            QPushButton#primaryButton:hover {{
                background: {theme.primary_container};
                color: {theme.on_primary_container};
            }}
            QPushButton#primaryButton:disabled, QPushButton#iconButton:disabled {{
                background: {theme.app_running_bg};
                color: {theme.inactive};
                border: 1px solid {theme.app_running_border};
            }}
            QFrame#stateChip[state="active"] {{
                background: {rgba(theme.primary_container, 0.74)};
                border: 1px solid {rgba(theme.primary, 0.36)};
            }}
            QFrame#stateChip[state="error"] {{
                background: {rgba(theme.error, 0.16)};
                border: 1px solid {rgba(theme.error, 0.30)};
            }}
            """
        )
        self.style().unpolish(self.state_chip)
        self.style().polish(self.state_chip)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()

    def _load_status(self) -> dict[str, str]:
        raw = run_script("vpn.sh", "--status")
        if not raw:
            return {"wireguard": "off", "wg_selected": ""}
        try:
            payload = json.loads(raw)
        except Exception:
            return {"wireguard": "off", "wg_selected": ""}
        return {
            "wireguard": str(payload.get("wireguard", "off")),
            "wg_selected": str(payload.get("wg_selected", "")),
        }

    def _load_interfaces(self) -> list[str]:
        raw = run_script("vpn.sh", "--interfaces")
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def refresh_state(self) -> None:
        if self._toggle_worker is not None and self._toggle_worker.isRunning():
            return
        status = self._load_status()
        interfaces = self._load_interfaces()
        selected = status.get("wg_selected", "")
        active = status.get("wireguard") == "on"

        if selected and selected not in interfaces:
            interfaces.insert(0, selected)

        self._building_combo = True
        self.interface_combo.clear()
        self.interface_combo.addItems(interfaces)
        if selected:
            index = self.interface_combo.findText(selected)
            if index >= 0:
                self.interface_combo.setCurrentIndex(index)
        self.interface_combo.setEnabled(bool(interfaces))
        self._building_combo = False

        if not interfaces:
            self.state_icon.setText(material_icon("lock_open"))
            self.state_label.setText("No WireGuard configs found")
            self.detail_label.setText("Expected `.conf` files in /etc/wireguard.")
            self.state_chip.setProperty("state", "inactive")
            self.toggle_button.setEnabled(False)
            self.toggle_button.setText("Enable")
            return

        self.state_icon.setText(material_icon("lock" if active else "lock_open"))
        self.state_label.setText("Tunnel active" if active else "Tunnel inactive")
        self.detail_label.setText(f"Selected interface: {selected or interfaces[0]}")
        self.state_chip.setProperty("state", "active" if active else "inactive")
        self.toggle_button.setEnabled(True)
        self.toggle_button.setText("Disable" if active else "Enable")
        self.style().unpolish(self.state_chip)
        self.style().polish(self.state_chip)

    def _set_interface(self, iface: str) -> None:
        if self._building_combo or not iface:
            return
        run_script_bg("vpn.sh", "--set-wg", iface)
        QTimer.singleShot(250, self.refresh_state)

    def _toggle_selected(self) -> None:
        iface = self.interface_combo.currentText().strip()
        if not iface or (self._toggle_worker is not None and self._toggle_worker.isRunning()):
            return
        self.toggle_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.interface_combo.setEnabled(False)
        self.state_chip.setProperty("state", "inactive")
        self.state_icon.setText(material_icon("refresh"))
        self.state_label.setText("Waiting for authentication…")
        self.detail_label.setText(f"Applying changes for {iface}")
        self.footer_label.setText("Authenticate in the polkit dialog if prompted.")
        self.style().unpolish(self.state_chip)
        self.style().polish(self.state_chip)

        self._toggle_worker = VpnToggleWorker(iface)
        self._toggle_worker.completed.connect(self._handle_toggle_finished)
        self._toggle_worker.start()

    def _handle_toggle_finished(self, ok: bool, message: str) -> None:
        self._toggle_worker = None
        self.refresh_button.setEnabled(True)
        self.footer_label.setText(message)
        self.refresh_state()
        self.interface_combo.setEnabled(bool(self.interface_combo.count()))
        if not ok:
            self.state_chip.setProperty("state", "error")
            self.state_icon.setText(material_icon("lock_open"))
            self.state_label.setText("WireGuard command failed")
            self.detail_label.setText(message)
            self.style().unpolish(self.state_chip)
            self.style().polish(self.state_chip)
        self.toggle_button.setEnabled(bool(self.interface_combo.count()))


def main() -> int:
    if not service_enabled():
        return 0
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    app.setPalette(palette)

    popup = VpnControlPopup()
    popup.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
