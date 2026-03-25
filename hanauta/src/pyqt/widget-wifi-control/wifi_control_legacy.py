#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compact PyQt6 Wi-Fi control popup.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import json
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QPainter, QPen
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
    QVBoxLayout,
    QWidget,
)


from pyqt.shared.runtime import fonts_root, scripts_root, source_root
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.button_helpers import create_close_button

APP_DIR = source_root()
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

SCRIPTS_DIR = scripts_root()
FONTS_DIR = fonts_root()
SERVICE_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
SERVICE_WIFI_CACHE = SERVICE_STATE_DIR / "wifi.json"

MATERIAL_ICONS = {
    "check_circle": "\ue86c",
    "close": "\ue5cd",
    "lock": "\ue897",
    "lock_open": "\ue898",
    "refresh": "\ue5d5",
    "router": "\ue328",
    "settings_ethernet": "\uf017",
    "signal_wifi_0_bar": "\ue1da",
    "signal_wifi_1_bar": "\ue1d9",
    "signal_wifi_2_bar": "\ue1d8",
    "signal_wifi_3_bar": "\ue1d7",
    "signal_wifi_4_bar": "\ue1d6",
    "wifi": "\ue63e",
    "wifi_find": "\uee67",
    "wifi_off": "\ue648",
}


def run_cmd(cmd: list[str], timeout: float = 6.0) -> str:
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


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "ui_sans_italic": FONTS_DIR / "Rubik-Italic-VariableFont_wght.ttf",
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


def apply_antialias_font(widget: QWidget) -> None:
    font = widget.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child_font = child.font()
        child_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        child.setFont(child_font)


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def signal_icon(signal: int) -> str:
    if signal >= 80:
        return "signal_wifi_4_bar"
    if signal >= 60:
        return "signal_wifi_3_bar"
    if signal >= 35:
        return "signal_wifi_2_bar"
    if signal > 0:
        return "signal_wifi_1_bar"
    return "signal_wifi_0_bar"


@dataclass
class WifiNetwork:
    ssid: str
    signal: int
    security: str
    in_use: bool

    @property
    def is_secure(self) -> bool:
        return bool(self.security and self.security != "--")


class WifiBackend:
    @staticmethod
    def current_ssid() -> str:
        device_status = run_cmd(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"], timeout=4.0)
        for line in device_status.splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue
            if parts[1].strip() == "wifi" and parts[2].strip().startswith("connected"):
                connection = ":".join(parts[3:]).replace("\\:", ":").strip()
                if connection:
                    return connection
        output = run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
        for line in output.splitlines():
            if line.startswith("yes:"):
                return line.split(":", 1)[1].replace("\\:", ":").strip()
        script = SCRIPTS_DIR / "network.sh"
        if script.exists():
            return run_cmd([str(script), "ssid"])
        return ""

    @staticmethod
    def radio_enabled() -> bool:
        return run_cmd(["nmcli", "radio", "wifi"]).strip().lower() == "enabled"

    @staticmethod
    def list_networks() -> list[WifiNetwork]:
        output = run_cmd(
            ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "auto"],
            timeout=12.0,
        )
        rows: list[WifiNetwork] = []
        seen: set[str] = set()
        for line in output.splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue
            in_use = parts[0].strip() == "*"
            ssid = parts[1].replace("\\:", ":").strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try:
                signal = int(parts[2].strip() or "0")
            except ValueError:
                signal = 0
            security = ":".join(parts[3:]).replace("\\:", ":").strip() or "--"
            rows.append(WifiNetwork(ssid=ssid, signal=signal, security=security, in_use=in_use))
        rows.sort(key=lambda item: (not item.in_use, -item.signal, item.ssid.lower()))
        return rows

    @staticmethod
    def load_cached_snapshot() -> dict | None:
        try:
            payload = json.loads(SERVICE_WIFI_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        networks_raw = payload.get("networks", [])
        if not isinstance(networks_raw, list):
            return None
        networks: list[WifiNetwork] = []
        for item in networks_raw:
            if not isinstance(item, dict):
                continue
            try:
                ssid = str(item.get("ssid", "")).strip()
                if not ssid:
                    continue
                networks.append(
                    WifiNetwork(
                        ssid=ssid,
                        signal=int(item.get("signal", 0) or 0),
                        security=str(item.get("security", "--") or "--"),
                        in_use=bool(item.get("in_use", False)),
                    )
                )
            except Exception:
                continue
        return {
            "radio_enabled": str(payload.get("radio", "")).strip().lower() == "enabled",
            "current_ssid": str(payload.get("current_ssid", "")).strip(),
            "networks": sorted(networks, key=lambda item: (not item.in_use, -item.signal, item.ssid.lower())),
        }

    @staticmethod
    def connect(ssid: str, password: str) -> tuple[bool, str]:
        cmd = ["nmcli", "dev", "wifi", "connect", ssid]
        if password:
            cmd.extend(["password", password])
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return True, result.stdout.strip() or f"Connected to {ssid}"
        return False, result.stderr.strip() or result.stdout.strip() or "Connection failed."

    @staticmethod
    def disconnect() -> tuple[bool, str]:
        current = run_cmd(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"])
        wifi_name = ""
        for line in current.splitlines():
            if line.endswith(":802-11-wireless"):
                wifi_name = line.split(":", 1)[0]
                break
        if not wifi_name:
            return True, "Wi-Fi already disconnected."
        result = subprocess.run(
            ["nmcli", "connection", "down", "id", wifi_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, "Wi-Fi disconnected."
        return False, result.stderr.strip() or result.stdout.strip() or "Failed to disconnect."

    @staticmethod
    def set_radio(enabled: bool) -> tuple[bool, str]:
        state = "on" if enabled else "off"
        result = subprocess.run(
            ["nmcli", "radio", "wifi", state],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, f"Wi-Fi radio turned {state}."
        return False, result.stderr.strip() or result.stdout.strip() or "Failed to change Wi-Fi radio state."


class WifiScanWorker(QThread):
    loaded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            payload = {
                "radio_enabled": WifiBackend.radio_enabled(),
                "current_ssid": WifiBackend.current_ssid(),
                "networks": WifiBackend.list_networks(),
            }
            self.loaded.emit(payload)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))


class WifiActionWorker(QThread):
    finished_action = pyqtSignal(bool, str)

    def __init__(self, action: str, ssid: str = "", password: str = "", enabled: bool = True) -> None:
        super().__init__()
        self.action = action
        self.ssid = ssid
        self.password = password
        self.enabled = enabled

    def run(self) -> None:
        if self.action == "connect":
            ok, message = WifiBackend.connect(self.ssid, self.password)
        elif self.action == "disconnect":
            ok, message = WifiBackend.disconnect()
        elif self.action == "radio":
            ok, message = WifiBackend.set_radio(self.enabled)
        else:
            ok, message = False, "Unsupported Wi-Fi action."
        self.finished_action.emit(ok, message)


class WifiNetworkCard(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, network: WifiNetwork, material_font: str, ui_font: str, theme) -> None:
        super().__init__()
        self.network = network
        self.material_font = material_font
        self.ui_font = ui_font
        self.theme = theme
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("wifiCard")
        self.setMinimumHeight(74)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("wifiCardIconWrap")
        icon_wrap.setFixedSize(38, 38)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel(material_icon(signal_icon(network.signal) if network.signal else "wifi_find"))
        icon.setFont(QFont(material_font, 16))
        icon.setObjectName("wifiCardIcon")
        icon_layout.addWidget(icon)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        self.ssid_label = QLabel(network.ssid)
        self.ssid_label.setObjectName("wifiCardSsid")
        self.ssid_label.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        detail = "Connected" if network.in_use else f"{network.signal}% signal"
        if network.is_secure:
            detail = f"{detail} • secured"
        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("wifiCardDetail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setFont(QFont(ui_font, 8))
        text_layout.addWidget(self.ssid_label)
        text_layout.addWidget(self.detail_label)

        self.trail = QLabel(material_icon("check_circle" if network.in_use else ("lock" if network.is_secure else "lock_open")))
        self.trail.setObjectName("wifiCardTrail")
        self.trail.setFont(QFont(material_font, 14))

        layout.addWidget(icon_wrap)
        layout.addLayout(text_layout, 1)
        layout.addWidget(self.trail)

        self._render()

    def _render(self) -> None:
        theme = self.theme
        if self.network.in_use:
            bg = rgba(theme.primary, 0.12)
            border = rgba(theme.primary, 0.28)
            trail_color = theme.primary
        else:
            bg = theme.app_running_bg
            border = theme.app_running_border
            trail_color = theme.inactive
        self.setStyleSheet(
            f"""
            QFrame#wifiCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}
            QFrame#wifiCard:hover {{
                background: {theme.hover_bg};
            }}
            QFrame#wifiCardIconWrap {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 17px;
            }}
            QLabel#wifiCardIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            QLabel#wifiCardSsid {{
                color: {theme.text};
                letter-spacing: 0.2px;
            }}
            QLabel#wifiCardDetail {{
                color: {theme.text_muted};
                line-height: 1.3em;
            }}
            QLabel#wifiCardTrail {{
                color: {trail_color};
                font-family: "{self.material_font}";
            }}
            """
        )

    def update_theme(self, theme) -> None:
        self.theme = theme
        self._render()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.network)
            event.accept()
            return
        super().mousePressEvent(event)


class WifiControlPopup(QWidget):
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
        self.ui_font = detect_font(
            "Rubik",
            self.loaded_fonts.get("ui_sans", ""),
            self.loaded_fonts.get("ui_sans_italic", ""),
            "Inter",
            "Noto Sans",
            "DejaVu Sans",
            "Sans Serif",
        )
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.scan_worker: WifiScanWorker | None = None
        self.action_worker: WifiActionWorker | None = None
        self.networks: list[WifiNetwork] = []
        self.selected_network: WifiNetwork | None = None
        self._panel_animation: QPropertyAnimation | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(408, 624)
        self.setWindowTitle("Wi-Fi Control")

        self._build_ui()
        apply_antialias_font(self)
        self._apply_window_effects()
        self._place_window()
        self._animate_in()
        self._apply_cached_snapshot()
        self.refresh_networks()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _apply_cached_snapshot(self) -> None:
        payload = WifiBackend.load_cached_snapshot()
        if not payload:
            return
        self._handle_scan_loaded(payload)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(12)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)
        kicker = QLabel("Network")
        kicker.setObjectName("kickerLabel")
        kicker.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        title = QLabel("Wi-Fi")
        title.setObjectName("titleLabel")
        title.setFont(QFont(self.ui_font, 17, QFont.Weight.DemiBold))
        subtitle = QLabel("Secure switching, cleaner status, and quick reconnection.")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont(self.ui_font, 9, QFont.Weight.Medium))
        title_wrap.addWidget(kicker)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        head.addLayout(title_wrap, 1)

        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_networks)
        head.addWidget(self.refresh_button)
        self.close_button = create_close_button(material_icon("close"), self.material_font)
        self.close_button.clicked.connect(self.close)
        head.addWidget(self.close_button)
        layout.addLayout(head)

        self.hero = QFrame()
        self.hero.setObjectName("hero")
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(10)
        hero_kicker = QLabel("Current network")
        hero_kicker.setObjectName("sectionKicker")
        hero_kicker.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.connection_label = QLabel("Checking current network…")
        self.connection_label.setObjectName("connectionLabel")
        self.connection_label.setWordWrap(True)
        self.connection_label.setFont(QFont(self.ui_font, 12, QFont.Weight.DemiBold))
        self.connection_meta = QLabel("Scanning adapter state and active SSID.")
        self.connection_meta.setObjectName("connectionMeta")
        self.connection_meta.setWordWrap(True)
        self.connection_meta.setFont(QFont(self.ui_font, 8))
        self.connection_icon = QLabel(material_icon("wifi"))
        self.connection_icon.setObjectName("connectionIcon")
        self.connection_icon.setFont(QFont(self.material_font, 22))
        connection_top = QHBoxLayout()
        connection_text = QVBoxLayout()
        connection_text.setContentsMargins(0, 0, 0, 0)
        connection_text.setSpacing(4)
        connection_text.addWidget(hero_kicker)
        connection_text.addWidget(self.connection_label)
        connection_text.addWidget(self.connection_meta)
        connection_top.addLayout(connection_text, 1)
        connection_top.addWidget(self.connection_icon, 0, Qt.AlignmentFlag.AlignTop)
        hero_layout.addLayout(connection_top)
        hero_actions = QHBoxLayout()
        hero_actions.setSpacing(8)
        self.radio_button = QPushButton("Turn Wi-Fi Off")
        self.radio_button.setObjectName("accentButton")
        self.radio_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.radio_button.clicked.connect(self.toggle_radio)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("dangerButton")
        self.disconnect_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.disconnect_button.clicked.connect(self.disconnect_current)
        for button in (self.radio_button, self.disconnect_button):
            button.setMinimumHeight(38)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        hero_actions.addWidget(self.radio_button)
        hero_actions.addWidget(self.disconnect_button)
        hero_layout.addLayout(hero_actions)
        layout.addWidget(self.hero)

        self.password_frame = QFrame()
        self.password_frame.setObjectName("passwordFrame")
        password_layout = QVBoxLayout(self.password_frame)
        password_layout.setContentsMargins(14, 14, 14, 14)
        password_layout.setSpacing(10)
        selection_kicker = QLabel("Selected access point")
        selection_kicker.setObjectName("sectionKicker")
        selection_kicker.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.selection_label = QLabel("Select a network")
        self.selection_label.setObjectName("selectionLabel")
        self.selection_label.setWordWrap(True)
        self.selection_label.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        self.selection_hint = QLabel("Choose a Wi-Fi network below. Password is only needed for secured SSIDs.")
        self.selection_hint.setObjectName("selectionHint")
        self.selection_hint.setWordWrap(True)
        self.selection_hint.setFont(QFont(self.ui_font, 8))
        self.password_edit = QLineEdit()
        self.password_edit.setObjectName("passwordEdit")
        self.password_edit.setPlaceholderText("Password if required")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.hide()
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.connect_button.setMinimumHeight(36)
        self.connect_button.clicked.connect(self.connect_selected)
        actions.addWidget(self.connect_button)
        password_layout.addWidget(selection_kicker)
        password_layout.addWidget(self.selection_label)
        password_layout.addWidget(self.selection_hint)
        password_layout.addWidget(self.password_edit)
        password_layout.addLayout(actions)
        layout.addWidget(self.password_frame)

        self.status_label = QLabel("Scanning available networks…")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setFont(QFont(self.ui_font, 9, QFont.Weight.Medium))
        layout.addWidget(self.status_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setObjectName("networkScroll")
        self.list_host = QWidget()
        self.list_host.setObjectName("listHost")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(6, 6, 6, 6)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)
        self.scroll_area.setWidget(self.list_host)
        layout.addWidget(self.scroll_area, 1)

        self._apply_styles()

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#panel {{
                background: {rgba(theme.surface_container, 0.94)};
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 24px;
            }}
            QLabel#kickerLabel, QLabel#sectionKicker {{
                color: {theme.text_muted};
                letter-spacing: 1.2px;
                text-transform: uppercase;
            }}
            QLabel#titleLabel {{
                color: {theme.text};
            }}
            QLabel#subtitleLabel {{
                color: {theme.text_muted};
                line-height: 1.35em;
            }}
            QFrame#hero {{
                background: {rgba(theme.surface_container_high, 0.90)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 20px;
            }}
            QLabel#connectionLabel {{
                color: {theme.text};
            }}
            QLabel#connectionMeta {{
                color: {theme.text_muted};
                line-height: 1.35em;
            }}
            QLabel#connectionIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            QFrame#passwordFrame {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QLabel#selectionLabel {{
                color: {theme.text};
            }}
            QLabel#selectionHint {{
                color: {theme.text_muted};
                line-height: 1.35em;
            }}
            QLabel#statusLabel {{
                color: {theme.text_muted};
                padding-left: 2px;
                line-height: 1.35em;
            }}
            QLineEdit#passwordEdit {{
                background: {rgba(theme.surface_container, 0.76)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.text};
                padding: 10px 12px;
                selection-background-color: {theme.hover_bg};
                font-size: 10px;
            }}
            QLineEdit#passwordEdit:focus {{
                border: 1px solid {rgba(theme.primary, 0.24)};
            }}
            QPushButton#iconButton {{
                background: {rgba(theme.surface_container_high, 0.90)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.icon};
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
                font-family: "{self.material_font}";
            }}
            QPushButton#iconButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#primaryButton {{
                background: {theme.primary};
                border: none;
                border-radius: 999px;
                color: {theme.active_text};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.2px;
                padding: 0 16px;
            }}
            QPushButton#primaryButton:hover {{
                background: {theme.primary_container};
                color: {theme.on_primary_container};
            }}
            QPushButton#primaryButton:disabled {{
                background: {theme.app_running_bg};
                color: {theme.inactive};
            }}
            QPushButton#secondaryButton {{
                background: {rgba(theme.surface_container_high, 0.86)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.text};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.2px;
                padding: 0 14px;
            }}
            QPushButton#secondaryButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#secondaryButton:disabled {{
                color: {theme.inactive};
            }}
            QPushButton#accentButton {{
                background: {rgba(theme.primary_container, 0.92)};
                border: 1px solid {rgba(theme.primary, 0.22)};
                border-radius: 999px;
                color: {theme.on_primary_container};
                font-size: 11px;
                font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton#accentButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#accentButton:disabled {{
                color: {theme.inactive};
            }}
            QPushButton#dangerButton {{
                background: rgba(255, 180, 171, 0.16);
                border: 1px solid rgba(255, 180, 171, 0.30);
                border-radius: 999px;
                color: #FFB4AB;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton#dangerButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#dangerButton:disabled {{
                color: {theme.inactive};
            }}
            QScrollArea#networkScroll {{
                background: {rgba(theme.surface_container, 0.78)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 20px;
            }}
            QScrollArea#networkScroll > QWidget > QWidget,
            QWidget#listHost {{
                background: transparent;
                border-radius: 18px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 10px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {rgba(theme.primary, 0.30)};
                border-radius: 4px;
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
        self._rebuild_network_cards()

    def _icon_button(self, icon_name: str) -> QPushButton:
        button = QPushButton(material_icon(icon_name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 18))
        button.setFixedSize(36, 36)
        return button

    def _apply_window_effects(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 190))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.x() + rect.width() - self.width() - 18, rect.y() + 52)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._panel_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._panel_animation.setDuration(180)
        self._panel_animation.setStartValue(0.0)
        self._panel_animation.setEndValue(1.0)
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.start()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(rgba(self.theme.outline, 0.22)), 1))
        painter.setBrush(QColor(rgba(self.theme.surface_container, 0.96)))
        painter.drawRoundedRect(rect, 26, 26)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.scan_worker is not None and self.scan_worker.isRunning():
            self.scan_worker.quit()
            self.scan_worker.wait(250)
        if self.action_worker is not None and self.action_worker.isRunning():
            self.action_worker.quit()
            self.action_worker.wait(250)
        app = QApplication.instance()
        if app is not None:
            app.quit()
        super().closeEvent(event)

    def refresh_networks(self) -> None:
        if self.scan_worker is not None and self.scan_worker.isRunning():
            return
        self.status_label.setText("Refreshing Wi-Fi scan…")
        self.refresh_button.setDisabled(True)
        self.scan_worker = WifiScanWorker()
        self.scan_worker.loaded.connect(self._handle_scan_loaded)
        self.scan_worker.failed.connect(self._handle_scan_failed)
        self.scan_worker.finished.connect(self._scan_finished)
        self.scan_worker.start()

    def _handle_scan_loaded(self, payload: dict) -> None:
        self.networks = payload["networks"]
        current_ssid = payload["current_ssid"]
        radio_enabled = payload["radio_enabled"]
        self.connection_label.setText(
            f"Connected to {current_ssid}" if current_ssid and current_ssid != "Disconnected" else "Wi-Fi not connected"
        )
        self.connection_icon.setText(material_icon("wifi" if current_ssid and radio_enabled else "wifi_off"))
        self.radio_button.setText("Turn Wi-Fi Off" if radio_enabled else "Turn Wi-Fi On")
        self._rebuild_network_cards()
        if not self.selected_network and self.networks:
            current = next((item for item in self.networks if item.in_use), self.networks[0])
            self._select_network(current)
        self.status_label.setText(f"{len(self.networks)} network(s) available")

    def _handle_scan_failed(self, error_text: str) -> None:
        self.status_label.setText(error_text or "Failed to scan networks.")

    def _scan_finished(self) -> None:
        self.refresh_button.setDisabled(False)
        self.scan_worker = None

    def _rebuild_network_cards(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self.networks:
            empty = QLabel("No Wi-Fi networks were found. Try turning the radio on or refreshing the scan.")
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {self.theme.text_muted}; padding: 10px 8px; line-height: 1.35em;"
            )
            self.list_layout.insertWidget(0, empty)
            return
        for network in self.networks:
            card = WifiNetworkCard(network, self.material_font, self.ui_font, self.theme)
            card.clicked.connect(self._select_network)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def _select_network(self, network: WifiNetwork) -> None:
        self.selected_network = network
        self.selection_label.setText(network.ssid)
        if network.in_use:
            hint = "Currently connected. You can disconnect or reconnect."
        elif network.is_secure:
            hint = "Secured network. Enter the password to connect if this network is not saved yet."
        else:
            hint = "Open network. No password is required."
        self.selection_hint.setText(hint)
        self.password_edit.setVisible(network.is_secure and not network.in_use)
        self.password_edit.setEnabled(network.is_secure and not network.in_use)
        if network.is_secure and not network.in_use:
            self.password_edit.setFocus()
        else:
            self.password_edit.clear()
        self.connect_button.setText("Reconnect" if network.in_use else "Connect")

    def _run_action(self, action: str, ssid: str = "", password: str = "", enabled: bool = True) -> None:
        if self.action_worker is not None and self.action_worker.isRunning():
            return
        self.status_label.setText("Applying Wi-Fi change…")
        self.connect_button.setDisabled(True)
        self.disconnect_button.setDisabled(True)
        self.radio_button.setDisabled(True)
        self.action_worker = WifiActionWorker(action, ssid, password, enabled)
        self.action_worker.finished_action.connect(self._handle_action_done)
        self.action_worker.start()

    def connect_selected(self) -> None:
        if self.selected_network is None:
            self.status_label.setText("Select a network first.")
            return
        password = self.password_edit.text().strip()
        if self.selected_network.is_secure and not password and not self.selected_network.in_use:
            self.status_label.setText("Enter the Wi-Fi password for this secured network.")
            self.password_edit.setFocus()
            return
        self._run_action("connect", self.selected_network.ssid, password=password)

    def disconnect_current(self) -> None:
        self._run_action("disconnect")

    def toggle_radio(self) -> None:
        enabled = self.radio_button.text().endswith("On")
        self._run_action("radio", enabled=enabled)

    def _handle_action_done(self, ok: bool, message: str) -> None:
        self.connect_button.setDisabled(False)
        self.disconnect_button.setDisabled(False)
        self.radio_button.setDisabled(False)
        self.status_label.setText(message)
        self.action_worker = None
        if ok:
            QTimer.singleShot(400, self.refresh_networks)


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)
    popup = WifiControlPopup()
    popup.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
