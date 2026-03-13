#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt6 notification center rebuilt from idea.html.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from time import monotonic
from urllib import error, parse, request

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QPainter, QPainterPath, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime

SCRIPTS_DIR = APP_DIR / "eww" / "scripts"
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
FALLBACK_COVER = ROOT / "assets" / "fallback.webp"
ASSETS_DIR = APP_DIR / "assets"
BIN_DIR = ROOT / "bin"
HOME_ASSISTANT_ICON = ASSETS_DIR / "home-assistant-dark.svg"
KDECONNECT_ICON = ASSETS_DIR / "kdeconnect.svg"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SETTINGS_FILE = STATE_DIR / "settings.json"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
VPN_CONTROL_SCRIPT = APP_DIR / "pyqt" / "widget-vpn-control" / "vpn_control.py"
CHRISTIAN_WIDGET_SCRIPT = APP_DIR / "pyqt" / "widget-religion-christian" / "christian_widget.py"

MATERIAL_ICONS = {
    "airplanemode_active": "\ue195",
    "arrow_back": "\ue5c4",
    "bluetooth": "\ue1a7",
    "brightness_medium": "\ue1ae",
    "camera_alt": "\ue3b0",
    "check_circle": "\ue86c",
    "chevron_right": "\ue5cc",
    "content_paste": "\ue14f",
    "coffee": "\uefef",
    "do_not_disturb_on": "\ue644",
    "home": "\ue88a",
    "hub": "\uee20",
    "invert_colors": "\ue891",
    "lightbulb": "\ue0f0",
    "nightlight": "\uf03d",
    "pause": "\ue034",
    "person": "\ue7fd",
    "phone_android": "\ue324",
    "play_arrow": "\ue037",
    "power_settings_new": "\ue8ac",
    "smartphone": "\ue32c",
    "save": "\ue161",
    "settings": "\ue8b8",
    "skip_next": "\ue044",
    "skip_previous": "\ue045",
    "thermostat": "\ue1ff",
    "tune": "\ue429",
    "volume_up": "\ue050",
    "wifi": "\ue63e",
    "lock": "\ue897",
    "auto_awesome": "\ue65f",
}

DEFAULT_SERVICE_SETTINGS = {
    "home_assistant": {
        "enabled": True,
        "show_in_notification_center": True,
    },
    "vpn_control": {
        "enabled": True,
        "show_in_notification_center": False,
    },
    "christian_widget": {
        "enabled": False,
        "show_in_notification_center": False,
        "show_in_bar": False,
        "next_devotion_notifications": False,
        "hourly_verse_notifications": False,
    },
}


def run_cmd(cmd: list[str], timeout: float = 2.0) -> str:
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
    path = SCRIPTS_DIR / script_name
    if not path.exists():
        return ""
    return run_cmd([str(path), *args])


def run_script_bg(script_name: str, *args: str) -> None:
    path = SCRIPTS_DIR / script_name
    if not path.exists():
        return
    try:
        subprocess.Popen(
            [str(path), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def run_bg(cmd: list[str]) -> None:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def dunstctl_command(*args: str) -> list[str]:
    local = BIN_DIR / "dunstctl"
    if local.exists():
        return [str(local), *args]
    return ["dunstctl", *args]


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


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


def format_millis(ms: int) -> str:
    ms = max(0, ms)
    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def parse_bool_text(value: str) -> bool:
    return value.strip().lower() == "true"


def merged_service_settings(payload: object) -> dict[str, dict[str, bool]]:
    services = payload if isinstance(payload, dict) else {}
    merged: dict[str, dict[str, bool]] = {}
    for key, defaults in DEFAULT_SERVICE_SETTINGS.items():
        current = services.get(key, {}) if isinstance(services, dict) else {}
        if not isinstance(current, dict):
            current = {}
        merged[key] = {
            "enabled": bool(current.get("enabled", defaults["enabled"])),
            "show_in_notification_center": bool(
                current.get(
                    "show_in_notification_center",
                    defaults["show_in_notification_center"],
                )
            ),
        }
        if key == "christian_widget":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
            merged[key]["next_devotion_notifications"] = bool(
                current.get(
                    "next_devotion_notifications",
                    defaults.get("next_devotion_notifications", False),
                )
            )
            merged[key]["hourly_verse_notifications"] = bool(
                current.get(
                    "hourly_verse_notifications",
                    defaults.get("hourly_verse_notifications", False),
                )
            )
    return merged


def load_notification_settings() -> dict:
    default = {
        "appearance": {"accent": "orchid"},
        "home_assistant": {"url": "", "token": "", "pinned_entities": []},
        "services": merged_service_settings({}),
        "display": {"layout_mode": "extend", "primary": "", "outputs": []},
        "ntfy": {
            "enabled": False,
            "show_in_bar": False,
            "server_url": "https://ntfy.sh",
            "topic": "",
            "token": "",
            "username": "",
            "password": "",
        },
    }
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return default
    if not isinstance(payload, dict):
        payload = {}
    appearance = dict(payload.get("appearance", {}))
    appearance.setdefault("accent", "orchid")
    home_assistant = dict(payload.get("home_assistant", {}))
    home_assistant.setdefault("url", "")
    home_assistant.setdefault("token", "")
    pinned = [
        item for item in home_assistant.get("pinned_entities", []) if isinstance(item, str)
    ][:5]
    home_assistant["pinned_entities"] = pinned
    services = merged_service_settings(payload.get("services", {}))
    display = dict(payload.get("display", {}))
    display.setdefault("layout_mode", "extend")
    display.setdefault("primary", "")
    outputs = display.get("outputs", [])
    display["outputs"] = outputs if isinstance(outputs, list) else []
    ntfy = dict(payload.get("ntfy", {}))
    ntfy.setdefault("enabled", False)
    ntfy.setdefault("show_in_bar", False)
    ntfy.setdefault("server_url", "https://ntfy.sh")
    ntfy.setdefault("topic", "")
    ntfy.setdefault("token", "")
    ntfy.setdefault("username", "")
    ntfy.setdefault("password", "")
    payload["appearance"] = appearance
    payload["home_assistant"] = home_assistant
    payload["services"] = services
    payload["display"] = display
    payload["ntfy"] = ntfy
    return payload


def save_notification_settings(settings: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def tinted_svg_pixmap(path: Path, color: QColor, size: int = 18) -> QPixmap:
    if not path.exists():
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return pixmap


def render_svg_pixmap(path: Path, size: int = 18) -> QPixmap:
    if not path.exists():
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def accent_palette(name: str) -> dict[str, str]:
    palettes = {
        "orchid": {"accent": "#D0BCFF", "on_accent": "#381E72", "soft": "rgba(208,188,255,0.18)"},
        "mint": {"accent": "#8FE3CF", "on_accent": "#11352D", "soft": "rgba(143,227,207,0.18)"},
        "sunset": {"accent": "#FFB59E", "on_accent": "#4D2418", "soft": "rgba(255,181,158,0.18)"},
    }
    return palettes.get(name, palettes["orchid"])


def normalize_ha_url(url: str) -> str:
    return url.strip().rstrip("/")


def fetch_home_assistant_json(base_url: str, token: str, path: str) -> tuple[object | None, str]:
    if not base_url or not token:
        return None, "Home Assistant URL and token are required."
    try:
        req = request.Request(
            f"{normalize_ha_url(base_url)}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=3.5) as response:
            return json.loads(response.read().decode("utf-8")), ""
    except error.HTTPError as exc:
        return None, f"Home Assistant returned HTTP {exc.code}."
    except Exception:
        return None, "Unable to reach Home Assistant."


def post_home_assistant_json(base_url: str, token: str, path: str, payload: dict) -> tuple[object | None, str]:
    if not base_url or not token:
        return None, "Home Assistant URL and token are required."
    data = json.dumps(payload).encode("utf-8")
    try:
        req = request.Request(
            f"{normalize_ha_url(base_url)}{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=3.5) as response:
            body = response.read().decode("utf-8")
            return (json.loads(body) if body else None), ""
    except error.HTTPError as exc:
        return None, f"Home Assistant returned HTTP {exc.code}."
    except Exception:
        return None, "Unable to reach Home Assistant."


class QuickSettingButton(QFrame):
    def __init__(self, material_font: str, title: str, icon: str, callback):
        super().__init__()
        self.material_font = material_font
        self.title = title
        self.callback = callback
        self.theme = None
        self.accent = "#D0BCFF"
        self.on_accent = "#381E72"
        self.active = False
        self._icon_text = icon
        self._subtitle = "Off"
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("quickTile")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setFont(QFont(self.material_font, 18))
        self.icon_label.setObjectName("quickTileIcon")

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("quickTileTitle")
        self.subtitle_label = QLabel("Off")
        self.subtitle_label.setObjectName("quickTileSubtitle")
        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.subtitle_label)

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_wrap, 1)
        self._render()

    def apply_theme(self, theme, accent: str, on_accent: str) -> None:
        self.theme = theme
        self.accent = accent
        self.on_accent = on_accent
        self._render()

    def set_state(self, active: bool, icon: str, subtitle: str) -> None:
        self.active = active
        self._icon_text = icon
        self._subtitle = subtitle
        self._render()

    def _render(self) -> None:
        theme = self.theme
        if theme is not None:
            icon_color = self.on_accent if self.active else theme.icon
            title_color = self.on_accent if self.active else theme.text
            sub_color = theme.inactive if self.active else theme.text_muted
            bg = self.accent if self.active else theme.app_running_bg
            hover = theme.accent_soft if self.active else theme.hover_bg
        else:
            icon_color = "#381E72" if self.active else "rgba(255,255,255,0.82)"
            title_color = "#381E72" if self.active else "#ffffff"
            sub_color = "rgba(56,30,114,0.72)" if self.active else "rgba(255,255,255,0.54)"
            bg = "#D0BCFF" if self.active else "rgba(255,255,255,0.05)"
            hover = "#ddcbff" if self.active else "rgba(255,255,255,0.10)"
        self.setStyleSheet(
            f"""
            QFrame#quickTile {{
                background: {bg};
                border: none;
                border-radius: 18px;
            }}
            QFrame#quickTile:hover {{
                background: {hover};
            }}
            """
        )
        self.icon_label.setText(material_icon(self._icon_text))
        self.icon_label.setStyleSheet(f"color: {icon_color};")
        self.title_label.setText(self.title)
        self.title_label.setStyleSheet(f"color: {title_color}; font-weight: 700;")
        self.subtitle_label.setText(self._subtitle)
        self.subtitle_label.setStyleSheet(f"color: {sub_color}; font-size: 10px;")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback()
            event.accept()
            return
        super().mousePressEvent(event)


class SidebarItemButton(QPushButton):
    def __init__(self, material_font: str, key: str, title: str, icon: str) -> None:
        super().__init__()
        self.key = key
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("sidebarItem")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setObjectName("sidebarItemIcon")
        self.icon_label.setFont(QFont(material_font, 18))
        self.text_label = QLabel(title)
        self.text_label.setObjectName("sidebarItemText")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)
        self.apply_state(False, "#D0BCFF", "#381E72")

    def apply_state(self, active: bool, accent: str, on_accent: str, theme=None) -> None:
        self.setChecked(active)
        if active:
            self.setStyleSheet(
                f"""
                QPushButton#sidebarItem {{
                    background: {accent};
                    border: none;
                    border-radius: 16px;
                }}
                QLabel#sidebarItemIcon, QLabel#sidebarItemText {{
                    color: {on_accent};
                    font-weight: 700;
                }}
                """
            )
        else:
            inactive_bg = theme.app_running_bg if theme is not None else "rgba(255,255,255,0.04)"
            hover_bg = theme.hover_bg if theme is not None else "rgba(255,255,255,0.08)"
            icon_color = theme.icon if theme is not None else "rgba(255,255,255,0.80)"
            text_color = theme.text if theme is not None else "rgba(255,255,255,0.90)"
            self.setStyleSheet(
                f"""
                QPushButton#sidebarItem {{
                    background: {inactive_bg};
                    border: none;
                    border-radius: 16px;
                }}
                QPushButton#sidebarItem:hover {{
                    background: {hover_bg};
                }}
                QLabel#sidebarItemIcon {{
                    color: {icon_color};
                }}
                QLabel#sidebarItemText {{
                    color: {text_color};
                    font-weight: 600;
                }}
                """
            )


class ActionTile(QFrame):
    def __init__(self, material_font: str, title: str, icon: str, callback) -> None:
        super().__init__()
        self.callback = callback
        self.setObjectName("actionTile")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setObjectName("actionTileIcon")
        self.icon_label.setFont(QFont(material_font, 18))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("actionTileTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("actionTileSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

    def set_content(self, icon: str, title: str, subtitle: str) -> None:
        self.icon_label.setText(material_icon(icon))
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback()
            event.accept()
            return
        super().mousePressEvent(event)


class CompactIconAction(QPushButton):
    def __init__(self, material_font: str, icon: str) -> None:
        super().__init__(material_icon(icon))
        self.setObjectName("compactIconAction")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFont(QFont(material_font, 17))
        self.setFixedSize(34, 34)
        self.setProperty("active", False)

    def set_icon(self, icon: str) -> None:
        self.setText(material_icon(icon))

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class ServiceLauncherCard(QFrame):
    def __init__(
        self,
        material_font: str,
        title: str,
        detail: str,
        icon: str,
        action_label: str,
        callback,
    ) -> None:
        super().__init__()
        self.setObjectName("infoCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        icon_label = QLabel(material_icon(icon))
        icon_label.setObjectName("sectionIcon")
        icon_label.setFixedWidth(20)
        icon_label.setFont(QFont(material_font, 18))

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("metricValue")
        subtitle_label = QLabel(detail)
        subtitle_label.setObjectName("statusHint")
        subtitle_label.setWordWrap(True)
        text.addWidget(title_label)
        text.addWidget(subtitle_label)

        action = QPushButton(action_label)
        action.setObjectName("softButton")
        action.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        action.clicked.connect(callback)

        layout.addWidget(icon_label)
        layout.addLayout(text, 1)
        layout.addWidget(action)


class ElidedLabel(QLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self._full_text = text

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = text
        self._apply_elision()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_elision()

    def _apply_elision(self) -> None:
        metrics = self.fontMetrics()
        available = max(0, self.width() - 2)
        if available < 10:
            available = 100
        elided = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, available
        )
        super().setText(elided)


class NotificationCenter(QWidget):
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
        self.mono_font = detect_font(
            "JetBrains Mono", "JetBrainsMono Nerd Font", "DejaVu Sans Mono"
        )
        self._panel_animation: QPropertyAnimation | None = None
        self._syncing_sliders = False
        self._pending_brightness = 0
        self._pending_volume = 0
        self._media_player = ""
        self._media_duration_ms = 0
        self._media_position_ms = 0
        self._media_status = "Stopped"
        self._media_track_key = ""
        self._media_last_sync = monotonic()
        self.settings_state = load_notification_settings()
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.current_accent = accent_palette(
            self.settings_state["appearance"].get("accent", "orchid")
        )
        if self.theme_palette.use_matugen:
            self.current_accent = {
                "accent": self.theme_palette.primary,
                "on_accent": self.theme_palette.active_text,
                "soft": self.theme_palette.accent_soft,
            }
        self._ha_entities: list[dict] = []
        self._ha_entity_map: dict[str, dict] = {}
        self._ha_last_error = ""

        self._brightness_commit_timer = QTimer(self)
        self._brightness_commit_timer.setSingleShot(True)
        self._brightness_commit_timer.timeout.connect(self._commit_brightness)

        self._volume_commit_timer = QTimer(self)
        self._volume_commit_timer.setSingleShot(True)
        self._volume_commit_timer.timeout.connect(self._commit_volume)

        self._build_window()
        self._build_ui()
        self._apply_styles()
        self._apply_media_palette()
        self._start_polls()

    def _build_window(self) -> None:
        self.setWindowTitle("PyQt Notification Center")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.screen_geo = QApplication.primaryScreen().availableGeometry()
        self.compact_size = (350, min(820, self.screen_geo.height() - 80))
        self.settings_size = (min(864, self.screen_geo.width() - 72), self.compact_size[1])
        self._apply_window_mode("compact")

    def _apply_window_mode(self, mode: str) -> None:
        if mode == "settings":
            width, height = self.settings_size
        else:
            width, height = self.compact_size
        self.resize(width, height)
        self.move(self.screen_geo.center().x() - self.width() // 2, self.screen_geo.y() + 28)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        self.panel = QFrame()
        self.panel.setObjectName("glassPanel")
        self.panel_effect = QGraphicsOpacityEffect(self.panel)
        self.panel.setGraphicsEffect(self.panel_effect)
        self.panel_effect.setOpacity(0.0)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        panel_layout.setSpacing(0)
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.overview_page = self._build_overview_page()
        self.settings_page = self._build_settings_page()
        self.page_stack.addWidget(self.overview_page)
        self.page_stack.addWidget(self.settings_page)
        panel_layout.addWidget(self.page_stack)

        root.addWidget(self.panel)

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        section_spacing = 3
        sliders_to_media_spacing = 1

        layout.addLayout(self._build_header())
        layout.addSpacing(section_spacing)
        layout.addLayout(self._build_quick_settings())
        layout.addSpacing(section_spacing)
        layout.addLayout(self._build_sliders())
        layout.addSpacing(sliders_to_media_spacing)
        layout.addWidget(self._build_media_card())
        layout.addSpacing(10)
        layout.addWidget(self._build_phone_card())
        layout.addSpacing(10)
        layout.addWidget(self._build_home_assistant_card())
        layout.addSpacing(10)
        layout.addWidget(self._build_vpn_launcher_card())
        layout.addSpacing(10)
        layout.addWidget(self._build_christian_launcher_card())
        self._sync_service_card_visibility()
        return page

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left = QHBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(14)

        self.avatar = QLabel(material_icon("person"))
        self.avatar.setObjectName("avatar")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFixedSize(46, 46)
        self.avatar.setFont(QFont(self.material_font, 24))

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)
        self.user_label = QLabel("User")
        self.user_label.setObjectName("userLabel")
        self.uptime_label = QLabel("up 0 mins")
        self.uptime_label.setObjectName("uptimeLabel")
        self.uptime_label.setFont(QFont(self.mono_font, 9))
        text_wrap.addWidget(self.user_label)
        text_wrap.addWidget(self.uptime_label)

        left.addWidget(self.avatar)
        left.addLayout(text_wrap)

        right = QHBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)
        self.settings_btn = self._circle_icon_button("settings")
        self.settings_btn.clicked.connect(self._open_settings)
        self.power_btn = self._circle_icon_button("power_settings_new", accent="power")
        self.power_btn.clicked.connect(self.close)
        right.addWidget(self.settings_btn)
        right.addWidget(self.power_btn)

        layout.addLayout(left)
        layout.addStretch(1)
        layout.addLayout(right)
        return layout

    def _build_quick_settings(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.quick_buttons: dict[str, QuickSettingButton] = {
            "wifi": QuickSettingButton(
                self.material_font, "Wi-Fi", "wifi", self._toggle_wifi
            ),
            "bluetooth": QuickSettingButton(
                self.material_font, "Bluetooth", "bluetooth", self._toggle_bluetooth
            ),
            "dnd": QuickSettingButton(
                self.material_font, "DND", "do_not_disturb_on", self._toggle_dnd
            ),
            "airplane": QuickSettingButton(
                self.material_font,
                "Airplane",
                "airplanemode_active",
                self._toggle_airplane,
            ),
            "night": QuickSettingButton(
                self.material_font, "Night Light", "nightlight", self._toggle_night
            ),
            "caffeine": QuickSettingButton(
                self.material_font, "Caffeine", "coffee", self._toggle_caffeine
            ),
        }
        positions = [
            ("wifi", 0, 0),
            ("bluetooth", 0, 1),
            ("dnd", 1, 0),
            ("airplane", 1, 1),
            ("night", 2, 0),
            ("caffeine", 2, 1),
        ]
        for key, row, col in positions:
            grid.addWidget(self.quick_buttons[key], row, col)
        return grid

    def _build_sliders(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # Adjust this value to change the gap between brightness and volume sliders.
        # Lower = tighter (e.g. 4), Higher = more space (e.g. 12).
        slider_row_spacing = 4
        layout.setSpacing(slider_row_spacing)
        self.brightness_slider = self._slider_row("brightness_medium", "brightness")
        self.volume_slider = self._slider_row("volume_up", "volume")
        layout.addWidget(self.brightness_slider["wrap"])
        layout.addWidget(self.volume_slider["wrap"])
        return layout

    def _slider_row(self, icon: str, kind: str) -> dict[str, QWidget | QSlider]:
        wrap = QFrame()
        wrap.setObjectName("sliderWrap")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(10)

        icon_label = QLabel(material_icon(icon))
        icon_label.setObjectName("sliderIcon")
        icon_label.setFont(QFont(self.material_font, 18))
        icon_label.setFixedWidth(24)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setObjectName("wideSlider")
        slider.valueChanged.connect(
            lambda value, mode=kind: self._queue_slider_commit(mode, value)
        )

        row.addWidget(icon_label)
        row.addWidget(slider, 1)
        return {"wrap": wrap, "slider": slider}

    def _build_media_card(self) -> QFrame:
        self.media_card = QFrame()
        self.media_card.setObjectName("mediaCard")
        self.media_card.setMinimumHeight(152)
        self.media_base = QFrame(self.media_card)
        self.media_base.setObjectName("mediaBase")
        self.media_scrim = QFrame(self.media_card)
        self.media_scrim.setObjectName("mediaScrim")
        self.media_scrim.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.media_content = QWidget(self.media_card)
        self.media_content.setObjectName("mediaContent")

        layout = QVBoxLayout(self.media_content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(14)

        self.cover = QLabel()
        self.cover.setObjectName("cover")
        self.cover.setFixedSize(62, 62)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_wrap = QWidget()
        text_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text = QVBoxLayout(text_wrap)
        text.setContentsMargins(0, 2, 0, 0)
        text.setSpacing(2)
        self.media_title = QLabel("Press Start")
        self.media_title.setObjectName("mediaTitle")
        self.media_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.media_title.setMinimumWidth(1)
        self.media_title.setWordWrap(False)
        self.media_artist = QLabel("No artist")
        self.media_artist.setObjectName("mediaArtist")
        self.media_artist.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.media_artist.setMinimumWidth(1)
        self.media_artist.setWordWrap(False)
        text.addWidget(self.media_title)
        text.addWidget(self.media_artist)
        text.addStretch(1)

        top.addWidget(self.cover)
        top.addWidget(text_wrap, 1)
        layout.addLayout(top)

        self.progress_track = QFrame()
        self.progress_track.setObjectName("progressTrack")
        self.progress_fill = QFrame(self.progress_track)
        self.progress_fill.setObjectName("progressFill")
        self.progress_fill.setGeometry(0, 0, 0, 4)
        self.progress_track.setFixedHeight(4)
        layout.addWidget(self.progress_track)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        self.elapsed = QLabel("0:00")
        self.elapsed.setObjectName("timeCode")
        self.elapsed.setFont(QFont(self.mono_font, 9))
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(10)
        self.prev_btn = self._plain_icon_button("skip_previous")
        self.prev_btn.clicked.connect(lambda: self._trigger_media_action("--previous"))
        self.play_btn = self._circle_icon_button("pause", accent="play")
        self.play_btn.clicked.connect(lambda: self._trigger_media_action("--toggle"))
        self.next_btn = self._plain_icon_button("skip_next")
        self.next_btn.clicked.connect(lambda: self._trigger_media_action("--next"))
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.next_btn)
        self.total = QLabel("0:00")
        self.total.setObjectName("timeCode")
        self.total.setFont(QFont(self.mono_font, 9))

        bottom.addWidget(self.elapsed)
        bottom.addStretch(1)
        bottom.addLayout(controls)
        bottom.addStretch(1)
        bottom.addWidget(self.total)
        layout.addLayout(bottom)
        self._sync_media_card_layers()
        return self.media_card

    def _build_phone_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("infoCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        icon = QLabel()
        icon.setObjectName("sectionIcon")
        icon.setFixedWidth(20)
        icon.setPixmap(render_svg_pixmap(KDECONNECT_ICON, 18))
        self.phone_status_dot = QLabel("●")
        self.phone_status_dot.setObjectName("phoneStatusDot")
        self.phone_switch_btn = CompactIconAction(self.material_font, "chevron_right")
        self.phone_switch_btn.clicked.connect(lambda: run_script_bg("phone_info.sh", "--next"))
        self.phone_clipboard_btn = CompactIconAction(self.material_font, "content_paste")
        self.phone_clipboard_btn.clicked.connect(lambda: run_script_bg("phone_info.sh", "--toggle-clip"))
        self.phone_name_value = QLabel("Disconnected")
        self.phone_state_value = QLabel("Offline")
        self.phone_battery_value = QLabel("0%")
        for label in (self.phone_name_value, self.phone_state_value, self.phone_battery_value):
            label.setObjectName("metricValue")
        self.phone_name_value.setObjectName("inlineMetricPrimary")
        self.phone_state_value.setObjectName("inlineMetric")
        self.phone_battery_value.setObjectName("inlineMetric")
        self.phone_name_value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout.addWidget(icon)
        layout.addWidget(self.phone_name_value, 1)
        layout.addWidget(self.phone_state_value)
        layout.addWidget(self.phone_battery_value)
        layout.addWidget(self.phone_status_dot)
        layout.addWidget(self.phone_clipboard_btn)
        layout.addWidget(self.phone_switch_btn)
        return card

    def _build_home_assistant_card(self) -> QFrame:
        self.ha_card = QFrame()
        self.ha_card.setObjectName("infoCard")
        layout = QHBoxLayout(self.ha_card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        icon = QLabel()
        icon.setObjectName("sectionIcon")
        icon.setFixedWidth(20)
        icon.setPixmap(tinted_svg_pixmap(HOME_ASSISTANT_ICON, QColor(self.current_accent["accent"]), 18))
        self.ha_summary_label = QLabel("")
        self.ha_summary_label.setObjectName("statusHint")
        self.ha_open_settings_btn = CompactIconAction(self.material_font, "settings")
        self.ha_open_settings_btn.clicked.connect(self._open_settings_homeassistant)

        tile_row = QHBoxLayout()
        tile_row.setContentsMargins(0, 0, 0, 0)
        tile_row.setSpacing(6)
        self.ha_action_tiles: list[ActionTile] = []
        for index in range(5):
            tile = ActionTile(
                self.material_font,
                f"Slot {index + 1}",
                "hub",
                lambda checked=False, i=index: self._activate_ha_tile(i),
            )
            tile.setMinimumSize(64, 70)
            tile.setMaximumSize(64, 70)
            self.ha_action_tiles.append(tile)
            tile_row.addWidget(tile)

        self.ha_status_label = QLabel("No entities pinned yet.")
        self.ha_status_label.setObjectName("statusHint")
        self.ha_status_label.hide()
        layout.addWidget(icon)
        layout.addLayout(tile_row, 1)
        layout.addWidget(self.ha_open_settings_btn)
        return self.ha_card

    def _build_vpn_launcher_card(self) -> QFrame:
        self.vpn_launcher_card = ServiceLauncherCard(
            self.material_font,
            "VPN Control",
            "Open the WireGuard popup from the notification center.",
            "lock",
            "Open",
            self._open_vpn_widget,
        )
        return self.vpn_launcher_card

    def _build_christian_launcher_card(self) -> QFrame:
        self.christian_launcher_card = ServiceLauncherCard(
            self.material_font,
            "Christian Widget",
            "Open the devotion widget from the notification center.",
            "auto_awesome",
            "Open",
            self._open_christian_widget,
        )
        return self.christian_launcher_card

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        back_button = self._circle_icon_button("arrow_back")
        back_button.clicked.connect(self._show_overview_page)
        top.addWidget(back_button)
        title = QLabel("Settings")
        title.setObjectName("settingsTitle")
        top.addWidget(title)
        top.addStretch(1)
        sidebar_layout.addLayout(top)

        self.settings_nav_group = QButtonGroup(self)
        self.settings_nav_group.setExclusive(True)
        self.settings_nav_buttons: dict[str, SidebarItemButton] = {}
        for key, title_text, icon in (
            ("overview", "Overview", "hub"),
            ("appearance", "Appearance", "invert_colors"),
            ("homeassistant", "Home Assistant", "home"),
        ):
            button = SidebarItemButton(self.material_font, key, title_text, icon)
            button.clicked.connect(lambda checked=False, current=key: self._show_settings_section(current))
            self.settings_nav_group.addButton(button)
            self.settings_nav_buttons[key] = button
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch(1)

        content_wrap = QFrame()
        content_wrap.setObjectName("settingsContentWrap")
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self.settings_stack = QStackedWidget()
        self.settings_pages: dict[str, QWidget] = {
            "overview": self._build_settings_overview_page(),
            "appearance": self._build_settings_appearance_page(),
            "homeassistant": self._build_settings_homeassistant_page(),
        }
        for key in ("overview", "appearance", "homeassistant"):
            self.settings_stack.addWidget(self.settings_pages[key])
        content_layout.addWidget(self.settings_stack)

        layout.addWidget(sidebar, 0)
        layout.addWidget(content_wrap, 1)
        self._show_settings_section("overview")
        return page

    def _build_settings_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel("System Overview")
        header.setObjectName("settingsSectionTitle")
        sub = QLabel("Quick telemetry for this session and shell environment.")
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)
        self.system_overview_grid = QGridLayout()
        self.system_overview_grid.setContentsMargins(0, 8, 0, 0)
        self.system_overview_grid.setHorizontalSpacing(12)
        self.system_overview_grid.setVerticalSpacing(12)
        self.system_overview_labels: dict[str, QLabel] = {}
        for index, key in enumerate(("Host", "Kernel", "Session", "Python", "Uptime", "Screen")):
            label = QLabel("...")
            label.setObjectName("metricValue")
            self.system_overview_labels[key] = label
            self.system_overview_grid.addWidget(self._metric_block(key, label), index // 2, index % 2)
        layout.addLayout(self.system_overview_grid)
        layout.addStretch(1)
        return page

    def _build_settings_appearance_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel("Appearance")
        header.setObjectName("settingsSectionTitle")
        sub = QLabel("Pick an accent preset for the notification center.")
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)
        self.appearance_status = QLabel("")
        self.appearance_status.setObjectName("statusHint")
        layout.addWidget(self.appearance_status)

        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 0)
        row.setSpacing(10)
        self.appearance_buttons: dict[str, QPushButton] = {}
        for key in ("orchid", "mint", "sunset"):
            button = QPushButton(key.title())
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.setObjectName("appearancePreset")
            button.clicked.connect(lambda checked=False, current=key: self._set_accent(current))
            self.appearance_buttons[key] = button
            row.addWidget(button)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _build_settings_homeassistant_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel("Home Assistant")
        header.setObjectName("settingsSectionTitle")
        sub = QLabel("Connect to your instance, browse entities, and pin up to five controls.")
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)

        self.ha_url_input = QLineEdit(self.settings_state["home_assistant"].get("url", ""))
        self.ha_url_input.setPlaceholderText("https://homeassistant.local:8123")
        self.ha_url_input.setObjectName("settingsInput")
        self.ha_token_input = QLineEdit(self.settings_state["home_assistant"].get("token", ""))
        self.ha_token_input.setPlaceholderText("Long-lived access token")
        self.ha_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ha_token_input.setObjectName("settingsInput")
        layout.addWidget(self._settings_field("Server URL", self.ha_url_input))
        layout.addWidget(self._settings_field("Long-Lived Token", self.ha_token_input))

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        self.ha_save_btn = self._soft_button("Save")
        self.ha_save_btn.clicked.connect(self._save_home_assistant_settings)
        self.ha_refresh_btn = self._soft_button("Fetch Entities")
        self.ha_refresh_btn.clicked.connect(self._refresh_home_assistant_entities)
        buttons.addWidget(self.ha_save_btn)
        buttons.addWidget(self.ha_refresh_btn)
        layout.addLayout(buttons)

        self.ha_settings_status = QLabel("Pin up to five entities.")
        self.ha_settings_status.setObjectName("statusHint")
        layout.addWidget(self.ha_settings_status)

        scroll = QScrollArea()
        scroll.setObjectName("entityScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.ha_entity_container = QWidget()
        self.ha_entity_layout = QVBoxLayout(self.ha_entity_container)
        self.ha_entity_layout.setContentsMargins(0, 0, 0, 0)
        self.ha_entity_layout.setSpacing(8)
        self.ha_entity_layout.addStretch(1)
        scroll.setWidget(self.ha_entity_container)
        layout.addWidget(scroll, 1)
        return page

    def _settings_field(self, label_text: str, widget: QWidget) -> QWidget:
        wrap = QWidget()
        row = QVBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        row.addWidget(label)
        row.addWidget(widget)
        return wrap

    def _metric_block(self, title: str, value_label: QLabel) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("metricCard")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("metricLabel")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return wrap

    def _soft_button(self, title: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("softButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        return button

    def _service_enabled(self, key: str) -> bool:
        return bool(self.settings_state.get("services", {}).get(key, {}).get("enabled", True))

    def _service_visible_in_notification_center(self, key: str) -> bool:
        service = self.settings_state.get("services", {}).get(key, {})
        return bool(service.get("enabled", True) and service.get("show_in_notification_center", False))

    def _sync_service_card_visibility(self) -> None:
        if hasattr(self, "ha_card"):
            self.ha_card.setVisible(self._service_visible_in_notification_center("home_assistant"))
        if hasattr(self, "vpn_launcher_card"):
            self.vpn_launcher_card.setVisible(self._service_visible_in_notification_center("vpn_control"))
        if hasattr(self, "christian_launcher_card"):
            self.christian_launcher_card.setVisible(
                self._service_visible_in_notification_center("christian_widget")
            )

    def _open_vpn_widget(self) -> None:
        if not self._service_enabled("vpn_control") or not VPN_CONTROL_SCRIPT.exists():
            return
        run_bg([sys.executable, str(VPN_CONTROL_SCRIPT)])

    def _open_christian_widget(self) -> None:
        if not self._service_enabled("christian_widget") or not CHRISTIAN_WIDGET_SCRIPT.exists():
            return
        run_bg([sys.executable, str(CHRISTIAN_WIDGET_SCRIPT)])

    def _circle_icon_button(self, icon: str, accent: str = "default") -> QPushButton:
        button = QPushButton(material_icon(icon))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 18))
        button.setProperty("accent", accent)
        button.setObjectName("circleIconButton")
        button.setFixedSize(40, 40)
        return button

    def _plain_icon_button(self, icon: str) -> QPushButton:
        button = QPushButton(material_icon(icon))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 20))
        button.setObjectName("plainIconButton")
        button.setFixedSize(28, 28)
        return button

    def _apply_styles(self) -> None:
        theme = self.theme_palette
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
            }}
            #glassPanel {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 26px;
            }}
            #pageStack {{
                background: transparent;
            }}
            #avatar {{
                background: qlineargradient(x1:0, y1:1, x2:1, y2:0, stop:0 {theme.primary}, stop:1 {theme.tertiary});
                color: {theme.active_text};
                font-family: "{self.material_font}";
                border-radius: 23px;
            }}
            #userLabel {{
                font-size: 17px;
                font-weight: 700;
                color: {theme.text};
            }}
            #uptimeLabel {{
                color: {theme.text_muted};
            }}
            #circleIconButton {{
                background: {theme.app_running_bg};
                border: none;
                border-radius: 20px;
                color: {theme.icon};
                font-family: "{self.material_font}";
            }}
            #circleIconButton:hover {{
                background: {theme.hover_bg};
            }}
            #circleIconButton[accent="power"] {{
                background: {theme.error};
                color: {theme.on_error};
            }}
            #circleIconButton[accent="power"]:hover {{
                background: {theme.error};
            }}
            #sliderWrap {{
                background: transparent;
            }}
            #infoCard, #settingsContentWrap, #sidebar {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 20px;
            }}
            #sectionIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #sectionTitle, #settingsTitle, #settingsSectionTitle {{
                font-size: 14px;
                font-weight: 700;
                color: {theme.text};
            }}
            #sectionSubtitle, #settingsSectionSubtitle, #statusHint {{
                color: {theme.text_muted};
                font-size: 10px;
            }}
            #metricCard {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
            }}
            #metricLabel {{
                color: {theme.inactive};
                font-size: 10px;
                text-transform: uppercase;
            }}
            #metricValue {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 700;
            }}
            #inlineMetricPrimary {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 700;
            }}
            #inlineMetric {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 600;
            }}
            #softButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
                color: {theme.text};
                padding: 10px 14px;
                font-weight: 600;
            }}
            #softButton:hover {{
                background: {theme.hover_bg};
            }}
            #actionTile {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 16px;
            }}
            #actionTile:hover {{
                background: {theme.hover_bg};
            }}
            #actionTileIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #actionTileTitle {{
                color: {theme.text};
                font-size: 10px;
                font-weight: 700;
            }}
            #actionTileSubtitle {{
                color: {theme.text_muted};
                font-size: 9px;
            }}
            #compactIconAction {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 17px;
                color: {theme.icon};
                font-family: "{self.material_font}";
            }}
            #compactIconAction:hover {{
                background: {theme.hover_bg};
            }}
            #compactIconAction[active="true"] {{
                background: {theme.accent_soft};
                border: 1px solid {theme.app_focused_border};
                color: {theme.primary};
            }}
            #settingsInput {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
                color: {theme.text};
                padding: 12px 14px;
            }}
            #fieldLabel {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 600;
            }}
            #entityScroll {{
                background: transparent;
            }}
            #phoneStatusDot {{
                color: {theme.primary};
                font-size: 16px;
            }}
            #appearancePreset {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 16px;
                color: {theme.text};
                padding: 16px 18px;
                font-weight: 700;
            }}
            #appearancePreset:hover {{
                background: {theme.hover_bg};
            }}
            #sliderIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #wideSlider::groove:horizontal {{
                background: {theme.app_running_bg};
                height: 42px;
                border-radius: 21px;
            }}
            #wideSlider::sub-page:horizontal {{
                background: {theme.primary};
                border-radius: 21px;
            }}
            #wideSlider::add-page:horizontal {{
                background: {theme.app_running_bg};
                border-radius: 21px;
            }}
            #wideSlider::handle:horizontal {{
                background: transparent;
                width: 0px;
                margin: 0;
            }}
            #mediaCard {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 20px;
            }}
            #cover {{
                background: {theme.surface_container_high};
                border: 1px solid {theme.chip_border};
                border-radius: 16px;
            }}
            #mediaTitle {{
                font-size: 14px;
                font-weight: 700;
                color: {theme.text};
            }}
            #mediaArtist {{
                font-size: 12px;
                color: {theme.primary};
            }}
            #progressTrack {{
                background: {theme.app_running_border};
                border-radius: 2px;
            }}
            #progressFill {{
                background: {theme.primary};
                border-radius: 2px;
            }}
            #plainIconButton {{
                background: transparent;
                border: none;
                color: {theme.text_muted};
                font-family: "{self.material_font}";
            }}
            #plainIconButton:hover {{
                color: {theme.primary};
            }}
            #quickTileIcon {{
                font-family: "{self.material_font}";
            }}
            #timeCode {{
                color: {theme.inactive};
                font-size: 10px;
            }}
            """
        )
        for quick_button in getattr(self, "quick_buttons", {}).values():
            quick_button.apply_theme(theme, self.current_accent["accent"], self.current_accent["on_accent"])
        for button_key, button in getattr(self, "settings_nav_buttons", {}).items():
            current_index = self.settings_stack.currentIndex() if hasattr(self, "settings_stack") else 0
            key_to_index = {"overview": 0, "appearance": 1, "homeassistant": 2}
            button.apply_state(
                key_to_index.get(button_key, -1) == current_index,
                self.current_accent["accent"],
                self.current_accent["on_accent"],
                theme,
            )

    def _apply_media_palette(
        self,
        start: str | None = None,
        end: str | None = None,
        border: str | None = None,
        accent: str | None = None,
    ) -> None:
        theme = self.theme_palette
        start = start or theme.media_active_start
        end = end or theme.media_active_end
        border = border or theme.media_active_border
        accent = accent or self.current_accent["accent"]
        self.media_base.setStyleSheet(
            f"""
            background: qradialgradient(
                cx: 0.36, cy: 0.26, radius: 0.95, fx: 0.36, fy: 0.26,
                stop: 0 {start},
                stop: 0.38 {end},
                stop: 1 {theme.panel_bg}
            );
            border-radius: 20px;
            """
        )
        self.media_card.setStyleSheet(
            f"""
            QFrame#mediaCard {{
                border: 1px solid {border};
                border-radius: 20px;
            }}
            """
        )
        self.media_scrim.setStyleSheet(
            """
            background: qradialgradient(
                cx: 0.5, cy: 0.36, radius: 1.05, fx: 0.5, fy: 0.34,
                stop: 0 rgba(0, 0, 0, 0.25),
                stop: 0.48 rgba(0, 0, 0, 0.58),
                stop: 1 rgba(0, 0, 0, 1.0)
            );
            border-radius: 20px;
            """
        )
        self.progress_fill.setStyleSheet(f"background: {accent}; border-radius: 2px;")
        self.media_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text};")
        self.media_artist.setStyleSheet(f"font-size: 12px; color: {accent};")
        self.play_btn.setStyleSheet(
            f"""
            background: {accent};
            border: none;
            border-radius: 20px;
            color: {theme.active_text};
            font-family: "{self.material_font}";
            """
        )

    def _sync_media_card_layers(self) -> None:
        media_rect = self.media_card.rect()
        self.media_base.setGeometry(media_rect)
        self.media_scrim.setGeometry(media_rect)
        self.media_content.setGeometry(media_rect)

    def _start_polls(self) -> None:
        self._poll_all()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_all)
        self.timer.start(3500)

        self.ha_timer = QTimer(self)
        self.ha_timer.timeout.connect(self._refresh_home_assistant_entities)
        self.ha_timer.start(15000)

        self.media_progress_timer = QTimer(self)
        self.media_progress_timer.timeout.connect(self._poll_media_progress)
        self.media_progress_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        QTimer.singleShot(80, self._animate_in)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme_palette = load_theme_palette()
        if self.theme_palette.use_matugen:
            self.current_accent = {
                "accent": self.theme_palette.primary,
                "on_accent": self.theme_palette.active_text,
                "soft": self.theme_palette.accent_soft,
            }
        self._apply_styles()
        self._apply_media_palette()
        self._render_home_assistant_tiles()

    def _animate_in(self) -> None:
        self._panel_animation = QPropertyAnimation(self.panel_effect, b"opacity", self)
        self._panel_animation.setDuration(260)
        self._panel_animation.setStartValue(0.0)
        self._panel_animation.setEndValue(1.0)
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.start()

    def _poll_all(self) -> None:
        self._poll_header()
        self._poll_quick_settings()
        self._poll_sliders()
        self._poll_media_metadata()
        self._poll_media_progress()
        self._poll_phone()
        self._refresh_system_overview()
        self._render_home_assistant_tiles()

    def _poll_header(self) -> None:
        self.user_label.setText(os.environ.get("USER", "User"))
        uptime = run_cmd(["uptime", "-p"]).removeprefix(
            "up "
        ).strip() or datetime.now().strftime("%H:%M")
        self.uptime_label.setText(f"up {uptime}")

    def _poll_phone(self) -> None:
        raw = run_script("phone_info.sh")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}
        name = str(payload.get("name", "Disconnected"))
        battery = str(payload.get("battery", "0"))
        status = str(payload.get("status", "Offline"))
        clipboard = str(payload.get("clipboard", "off"))
        has_device = bool(payload.get("id")) and name != "Disconnected"
        if has_device:
            self.phone_name_value.setText(name)
            self.phone_state_value.setText(status)
            self.phone_battery_value.setText(f"{battery}%")
        else:
            self.phone_name_value.setText("No devices connected")
            self.phone_state_value.setText("")
            self.phone_battery_value.setText("")
        self.phone_status_dot.setStyleSheet(
            f"color: {self.theme_palette.primary if has_device and status.lower() != 'offline' else self.theme_palette.workspace_empty};"
        )
        self.phone_clipboard_btn.set_active(has_device and clipboard == "on")
        self.phone_clipboard_btn.setEnabled(has_device)
        self.phone_switch_btn.setEnabled(has_device)

    def _refresh_system_overview(self) -> None:
        metrics = {
            "Host": run_cmd(["hostname"]) or "Unknown",
            "Kernel": run_cmd(["uname", "-r"]) or "Unknown",
            "Session": os.environ.get("XDG_SESSION_DESKTOP", "i3"),
            "Python": sys.version.split()[0],
            "Uptime": self.uptime_label.text(),
            "Screen": f"{self.width()}x{self.height()}",
        }
        for key, value in metrics.items():
            label = self.system_overview_labels.get(key)
            if label is not None:
                label.setText(value)

    def _poll_quick_settings(self) -> None:
        wifi_on = run_script("network.sh", "status") == "Connected"
        wifi_ssid = run_script("network.sh", "ssid") or "Disconnected"
        self.quick_buttons["wifi"].set_state(wifi_on, "wifi", wifi_ssid)

        bt_on = run_script("bluetooth", "state") == "on"
        self.quick_buttons["bluetooth"].set_state(
            bt_on, "bluetooth", "Connected" if bt_on else "Off"
        )

        dnd_on = parse_bool_text(run_cmd(dunstctl_command("is-paused")))
        self.quick_buttons["dnd"].set_state(
            dnd_on, "do_not_disturb_on", "On" if dnd_on else "Off"
        )

        airplane_on = run_script("network.sh", "radio-status") == "off"
        self.quick_buttons["airplane"].set_state(
            airplane_on, "airplanemode_active", "On" if airplane_on else "Off"
        )

        night_on = run_script("redshift", "state") == "on"
        self.quick_buttons["night"].set_state(
            night_on, "nightlight", "On" if night_on else "Off"
        )

        caffeine_on = run_script("caffeine.sh", "status") == "on"
        self.quick_buttons["caffeine"].set_state(
            caffeine_on, "coffee", "On" if caffeine_on else "Off"
        )

    def _poll_sliders(self) -> None:
        self._syncing_sliders = True
        try:
            self.brightness_slider["slider"].setValue(
                int(run_script("brightness.sh", "br") or "67")
            )
        except Exception:
            self.brightness_slider["slider"].setValue(67)
        try:
            self.volume_slider["slider"].setValue(
                int(run_script("volume.sh", "vol") or "82")
            )
        except Exception:
            self.volume_slider["slider"].setValue(82)
        self._syncing_sliders = False

    def _poll_media_metadata(self) -> None:
        title = run_script("mpris.sh", "title") or "Press Start"
        artist = run_script("mpris.sh", "artist") or "No artist"
        status = run_script("mpris.sh", "status") or "Stopped"
        player = run_script("mpris.sh", "player")
        art = run_script("mpris.sh", "coverloc")

        self._media_player = player
        self._media_status = status
        self._media_last_sync = monotonic()
        self.media_title.setText(title)
        self.media_artist.setText(artist)
        self.media_title.setVisible(True)
        self.media_artist.setVisible(True)
        self.media_title.updateGeometry()
        self.media_artist.updateGeometry()
        self.media_title.repaint()
        self.media_artist.repaint()
        self.play_btn.setText(
            material_icon("pause" if status == "Playing" else "play_arrow")
        )

        track_key = f"{title}|{artist}"
        if track_key != self._media_track_key:
            self._media_track_key = track_key
            cover_path = Path(art) if art else FALLBACK_COVER
            if not cover_path.exists():
                cover_path = FALLBACK_COVER
            self._set_cover_art(cover_path)
            self._update_media_palette_from_cover(cover_path)

    def _trigger_media_action(self, action: str) -> None:
        run_script_bg("mpris.sh", action)
        self._schedule_media_refresh()

    def _schedule_media_refresh(self) -> None:
        self._poll_media_metadata()
        self._poll_media_progress()
        for delay in (150, 450, 900):
            QTimer.singleShot(delay, self._poll_media_metadata)
            QTimer.singleShot(delay, self._poll_media_progress)

    def _poll_media_progress(self) -> None:
        player = self._media_player or run_script("mpris.sh", "player")
        if not player:
            self._media_position_ms = 0
            self._media_duration_ms = 0
            self._render_media_progress()
            return

        now = monotonic()
        elapsed_since_sync = max(0.0, now - self._media_last_sync)
        self._media_last_sync = now

        status_raw = (
            run_cmd(["playerctl", f"--player={player}", "status"]) or self._media_status
        )
        position_raw = run_cmd(["playerctl", f"--player={player}", "position"])
        length_raw = run_cmd(
            [
                "playerctl",
                f"--player={player}",
                "metadata",
                "--format",
                "{{mpris:length}}",
            ]
        )

        try:
            self._media_position_ms = int(float(position_raw) * 1000)
        except Exception:
            if status_raw == "Playing" and self._media_duration_ms > 0:
                self._media_position_ms = min(
                    self._media_duration_ms,
                    self._media_position_ms + int(elapsed_since_sync * 1000),
                )
            else:
                self._media_position_ms = max(0, self._media_position_ms)

        try:
            self._media_duration_ms = int(int(length_raw) / 1000)
        except Exception:
            self._media_duration_ms = 0

        self._media_status = status_raw

        self._render_media_progress()

    def _render_media_progress(self) -> None:
        self.elapsed.setText(format_millis(self._media_position_ms))
        self.total.setText(format_millis(self._media_duration_ms))

        track_width = self.progress_track.width() or 180
        if self._media_duration_ms > 0:
            ratio = max(
                0.0, min(1.0, self._media_position_ms / self._media_duration_ms)
            )
        else:
            ratio = 0.0
        fill_width = max(0, int(track_width * ratio))
        self.progress_fill.setGeometry(0, 0, fill_width, 4)

    def _queue_slider_commit(self, kind: str, value: int) -> None:
        if self._syncing_sliders:
            return
        if kind == "brightness":
            self._pending_brightness = value
            self._brightness_commit_timer.start(90)
        else:
            self._pending_volume = value
            self._volume_commit_timer.start(90)

    def _commit_brightness(self) -> None:
        run_script_bg("brightness.sh", "set", str(self._pending_brightness))

    def _commit_volume(self) -> None:
        run_script_bg("volume.sh", "set", str(self._pending_volume))

    def _set_cover_art(self, cover_path: Path) -> None:
        pixmap = QPixmap(str(cover_path))
        if pixmap.isNull():
            self.cover.setPixmap(QPixmap())
            return
        scaled = pixmap.scaled(
            self.cover.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - self.cover.width()) // 2)
        y = max(0, (scaled.height() - self.cover.height()) // 2)
        cropped = scaled.copy(x, y, self.cover.width(), self.cover.height())

        rounded = QPixmap(self.cover.size())
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0, float(self.cover.width()), float(self.cover.height()), 16.0, 16.0
        )
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.cover.setPixmap(rounded)

    def _update_media_palette_from_cover(self, cover_path: Path) -> None:
        palette = self._extract_cover_palette(cover_path)
        if palette is None:
            self._apply_media_palette()
            return
        self._apply_media_palette(*palette)

    def _extract_cover_palette(
        self, cover_path: Path
    ) -> tuple[str, str, str, str] | None:
        colors_raw = run_script("cover_colors.sh", "colors")
        colors = [color for color in colors_raw.split() if color.startswith("#")][:6]
        if len(colors) < 3:
            return None
        center = self._hex_to_rgba(colors[0], 0.26)
        mid = self._hex_to_rgba(colors[min(2, len(colors) - 1)], 0.58)
        border = self._darken_hex(colors[1], 0.12)
        accent = colors[min(4, len(colors) - 1)]
        return center, mid, border, accent

    def _hex_to_rgba(self, color: str, alpha: float) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return f"rgba(208, 188, 255, {alpha:.2f})"
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
        return f"rgba({red}, {green}, {blue}, {alpha:.2f})"

    def _darken_hex(self, color: str, amount: float) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return "#4d4458"
        red = max(0, min(255, int(int(color[0:2], 16) * (1.0 - amount))))
        green = max(0, min(255, int(int(color[2:4], 16) * (1.0 - amount))))
        blue = max(0, min(255, int(int(color[4:6], 16) * (1.0 - amount))))
        return f"#{red:02X}{green:02X}{blue:02X}"

    def _open_settings(self) -> None:
        self._launch_settings_page("overview")

    def _show_overview_page(self) -> None:
        self._apply_window_mode("compact")
        self.page_stack.setCurrentWidget(self.overview_page)

    def _show_settings_section(self, key: str) -> None:
        order = {"overview": 0, "appearance": 1, "homeassistant": 2}
        self.settings_stack.setCurrentIndex(order.get(key, 0))
        for button_key, button in self.settings_nav_buttons.items():
            button.apply_state(
                button_key == key,
                self.current_accent["accent"],
                self.current_accent["on_accent"],
                self.theme_palette,
            )

    def _open_settings_homeassistant(self) -> None:
        self._launch_settings_page("services")

    def _launch_settings_page(self, page: str) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        run_bg([sys.executable, str(SETTINGS_PAGE_SCRIPT), "--page", page])
        self.hide()

    def _set_accent(self, key: str) -> None:
        self.settings_state["appearance"]["accent"] = key
        self.current_accent = accent_palette(key)
        save_notification_settings(self.settings_state)
        self.appearance_status.setText(f"Accent updated to {key.title()}.")
        self._apply_styles()
        self._apply_media_palette()
        self._show_settings_section("appearance")

    def _save_home_assistant_settings(self) -> None:
        self.settings_state["home_assistant"]["url"] = normalize_ha_url(self.ha_url_input.text())
        self.settings_state["home_assistant"]["token"] = self.ha_token_input.text().strip()
        save_notification_settings(self.settings_state)
        self.ha_settings_status.setText("Home Assistant settings saved.")
        self._refresh_home_assistant_entities()

    def _refresh_home_assistant_entities(self) -> None:
        if not self._service_visible_in_notification_center("home_assistant"):
            self._ha_entities = []
            self._ha_entity_map = {}
            self._render_home_assistant_tiles()
            return
        base_url = normalize_ha_url(self.settings_state["home_assistant"].get("url", ""))
        token = self.settings_state["home_assistant"].get("token", "")
        payload, error_text = fetch_home_assistant_json(base_url, token, "/api/states")
        self._ha_last_error = error_text
        if error_text or not isinstance(payload, list):
            self.ha_summary_label.setText("")
            self.ha_status_label.setText(error_text or "No entities available.")
            self.ha_settings_status.setText(error_text or "Unable to fetch entities.")
            self._ha_entities = []
            self._ha_entity_map = {}
            self._rebuild_ha_entity_list()
            self._render_home_assistant_tiles()
            return
        self._ha_entities = sorted(
            [item for item in payload if isinstance(item, dict)],
            key=lambda item: str(item.get("entity_id", "")),
        )
        self._ha_entity_map = {str(item.get("entity_id", "")): item for item in self._ha_entities}
        self.ha_summary_label.setText("")
        self.ha_status_label.setText("Pinned entity controls are live.")
        self.ha_settings_status.setText("Entities loaded successfully.")
        self._rebuild_ha_entity_list()
        self._render_home_assistant_tiles()

    def _rebuild_ha_entity_list(self) -> None:
        while self.ha_entity_layout.count():
            item = self.ha_entity_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        pinned = set(self.settings_state["home_assistant"].get("pinned_entities", []))
        if not self._ha_entities:
            empty = QLabel("No Home Assistant entities to display.")
            empty.setObjectName("statusHint")
            self.ha_entity_layout.addWidget(empty)
            self.ha_entity_layout.addStretch(1)
            return
        for entity in self._ha_entities[:80]:
            entity_id = str(entity.get("entity_id", ""))
            state = str(entity.get("state", "unknown"))
            attrs = entity.get("attributes", {}) or {}
            name = str(attrs.get("friendly_name", entity_id))
            row = QFrame()
            row.setObjectName("metricCard")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(2)
            title = QLabel(name)
            title.setObjectName("metricValue")
            subtitle = QLabel(f"{entity_id} • {state}")
            subtitle.setObjectName("statusHint")
            text.addWidget(title)
            text.addWidget(subtitle)
            layout.addLayout(text, 1)
            pin_button = self._soft_button("Unpin" if entity_id in pinned else "Pin")
            pin_button.clicked.connect(lambda checked=False, current=entity_id: self._toggle_pin_entity(current))
            layout.addWidget(pin_button)
            self.ha_entity_layout.addWidget(row)
        self.ha_entity_layout.addStretch(1)

    def _toggle_pin_entity(self, entity_id: str) -> None:
        pinned = list(self.settings_state["home_assistant"].get("pinned_entities", []))
        if entity_id in pinned:
            pinned.remove(entity_id)
        else:
            if len(pinned) >= 5:
                self.ha_settings_status.setText("You can pin up to five entities.")
                return
            pinned.append(entity_id)
        self.settings_state["home_assistant"]["pinned_entities"] = pinned
        save_notification_settings(self.settings_state)
        self.ha_settings_status.setText(f"{len(pinned)}/5 entities pinned.")
        self._rebuild_ha_entity_list()
        self._render_home_assistant_tiles()

    def _render_home_assistant_tiles(self) -> None:
        self._sync_service_card_visibility()
        if not self._service_visible_in_notification_center("home_assistant"):
            return
        pinned = self.settings_state["home_assistant"].get("pinned_entities", [])
        for index, tile in enumerate(self.ha_action_tiles):
            if index >= len(pinned):
                tile.set_content("hub", "", "")
                tile.setProperty("entity_id", "")
                tile.setEnabled(False)
                continue
            entity_id = pinned[index]
            entity = self._ha_entity_map.get(entity_id, {})
            attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
            name = str(attrs.get("friendly_name", entity_id))
            state = str(entity.get("state", "Unavailable")) if isinstance(entity, dict) else "Unavailable"
            domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
            icon_name = {
                "light": "lightbulb",
                "switch": "tune",
                "climate": "thermostat",
                "camera": "camera_alt",
            }.get(domain, "home")
            tile.set_content(icon_name, name[:12], state[:12])
            tile.setEnabled(True)
            tile.setProperty("entity_id", entity_id)
        self.ha_card.setVisible(True)

    def _activate_ha_tile(self, index: int) -> None:
        pinned = self.settings_state["home_assistant"].get("pinned_entities", [])
        if index >= len(pinned):
            self._open_settings_homeassistant()
            return
        entity_id = pinned[index]
        entity = self._ha_entity_map.get(entity_id)
        if not entity:
            self.ha_status_label.setText("Entity state is not loaded yet.")
            return
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        state = str(entity.get("state", ""))
        service_domain = domain
        service = ""
        payload = {"entity_id": entity_id}
        if domain in {"light", "switch", "input_boolean"}:
            service = "turn_off" if state == "on" else "turn_on"
        elif domain == "scene":
            service = "turn_on"
            service_domain = "scene"
        elif domain == "script":
            service = "turn_on"
            service_domain = "script"
        else:
            self.ha_status_label.setText(f"{entity_id} is view-only right now.")
            return
        _, error_text = post_home_assistant_json(
            self.settings_state["home_assistant"].get("url", ""),
            self.settings_state["home_assistant"].get("token", ""),
            f"/api/services/{service_domain}/{service}",
            payload,
        )
        self.ha_status_label.setText(error_text or f"Triggered {service} for {entity_id}.")
        QTimer.singleShot(900, self._refresh_home_assistant_entities)

    def _toggle_wifi(self) -> None:
        run_script_bg("network.sh", "toggle")
        QTimer.singleShot(300, self._poll_quick_settings)

    def _toggle_bluetooth(self) -> None:
        run_script_bg("bluetooth", "toggle")
        QTimer.singleShot(300, self._poll_quick_settings)

    def _toggle_airplane(self) -> None:
        run_script_bg("network.sh", "toggle-radio")
        QTimer.singleShot(300, self._poll_quick_settings)

    def _toggle_night(self) -> None:
        run_script_bg("redshift", "toggle")
        QTimer.singleShot(300, self._poll_quick_settings)

    def _toggle_caffeine(self) -> None:
        run_script_bg("caffeine.sh", "toggle")
        QTimer.singleShot(300, self._poll_quick_settings)

    def _toggle_dnd(self) -> None:
        dnd_on = parse_bool_text(run_cmd(dunstctl_command("is-paused")))
        if dnd_on:
            run_cmd(dunstctl_command("set-paused", "false"))
            run_bg(
                [
                    "notify-send",
                    "Notifications",
                    "Notifications are now globally enabled",
                ]
            )
            QTimer.singleShot(150, self._poll_quick_settings)
            return

        run_bg(
            [
                "notify-send",
                "Do Not Disturb",
                "This is the last desktop notification. Notifications will now be globally disabled.",
            ]
        )
        QTimer.singleShot(350, self._enable_dnd_after_warning)

    def _enable_dnd_after_warning(self) -> None:
        run_cmd(dunstctl_command("set-paused", "true"))
        self._poll_quick_settings()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_media_card_layers()
        self._render_media_progress()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._sync_media_card_layers()
        self._render_media_progress()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PyQt Notification Center")
    window = NotificationCenter()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
