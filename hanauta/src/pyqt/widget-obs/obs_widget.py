#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import signal
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication
from PyQt6.QtNetwork import QAbstractSocket
from PyQt6.QtWebSockets import QWebSocket
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command, python_executable
from pyqt.shared.theme import blend, load_theme_palette, palette_mtime, rgba
from PyQt6.QtCore import QUrl


MATERIAL_ICONS = {
    "close": "\ue5cd",
    "settings": "\ue8b8",
    "refresh": "\ue5d5",
    "videocam": "\ue04b",
    "play_arrow": "\ue037",
    "stop": "\ue047",
    "sync": "\ue627",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def python_bin() -> str:
    return python_executable()


def load_settings_state() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("obs", {})
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


def obs_auth(password: str, salt: str, challenge: str) -> str:
    secret = hashlib.sha256((password + salt).encode("utf-8")).digest()
    secret_b64 = base64.b64encode(secret).decode("utf-8")
    return base64.b64encode(hashlib.sha256((secret_b64 + challenge).encode("utf-8")).digest()).decode("utf-8")


class ObsWidget(QWidget):
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
        self.socket = QWebSocket()
        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.errorOccurred.connect(self._on_error)
        self.socket.textMessageReceived.connect(self._on_message)
        self.pending_requests: dict[str, str] = {}
        self.request_counter = 0
        self.connected = False
        self.scenes: list[str] = []
        self._stream_live = False
        self._record_live = False
        self._tooltips_enabled = bool(self.settings_state.get("obs", {}).get("show_debug_tooltips", False))

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hanauta OBS")
        self.setFixedSize(392, 760)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self._sync_from_settings()
        self._refresh_tooltips()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        if bool(self.settings_state.get("obs", {}).get("auto_connect", False)):
            QTimer.singleShot(150, self.connect_obs)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("popupScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        root.addWidget(scroll)

        scroll_body = QWidget()
        scroll_body.setObjectName("scrollBody")
        scroll.setWidget(scroll_body)

        scroll_layout = QVBoxLayout(scroll_body)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        scroll_layout.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)

        titles = QVBoxLayout()
        titles.setSpacing(2)

        eyebrow = QLabel("OBS CONTROL")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))

        self.subtitle = QLabel("Compact socket, stream, record, and scene control.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)

        titles.addWidget(eyebrow)
        titles.addWidget(self.subtitle)

        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        actions.setSpacing(6)

        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_status)

        self.settings_button = self._icon_button("settings")
        self.settings_button.clicked.connect(self._open_settings)

        self.close_button = self._icon_button("close")
        self.close_button.clicked.connect(self.close)

        actions.addWidget(self.refresh_button)
        actions.addWidget(self.settings_button)
        actions.addWidget(self.close_button)

        header.addLayout(actions, 0)
        layout.addLayout(header)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")

        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(10)

        hero_top = QHBoxLayout()
        hero_top.setSpacing(8)

        self.connection_badge = QLabel("SOCKET")
        self.connection_badge.setObjectName("metaChip")
        self.connection_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_badge.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))

        self.connection_hint = QLabel("Waiting for OBS")
        self.connection_hint.setObjectName("heroMeta")
        self.connection_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        hero_top.addWidget(self.connection_badge, 0)
        hero_top.addStretch(1)
        hero_top.addWidget(self.connection_hint, 0)

        self.connection_label = QLabel("Disconnected")
        self.connection_label.setObjectName("heroTitle")
        self.connection_label.setFont(QFont(self.display_font, 20, QFont.Weight.DemiBold))
        self.connection_label.setWordWrap(True)

        self.hero_detail = QLabel("The widget becomes live as soon as OBS WebSocket responds.")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setWordWrap(True)

        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)

        self.stream_pill = QLabel("Stream offline")
        self.stream_pill.setObjectName("statusPill")
        self.stream_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.record_pill = QLabel("Record stopped")
        self.record_pill.setObjectName("statusPill")
        self.record_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pills_row.addWidget(self.stream_pill, 1)
        pills_row.addWidget(self.record_pill, 1)

        hero_layout.addLayout(hero_top)
        hero_layout.addWidget(self.connection_label)
        hero_layout.addWidget(self.hero_detail)
        hero_layout.addLayout(pills_row)

        layout.addWidget(self.hero)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(10)
        stats_grid.setVerticalSpacing(10)

        self.stream_card = self._stat_card("Stream", "Offline", "Broadcast output")
        self.record_card = self._stat_card("Record", "Stopped", "Recording output")
        self.scene_card = self._stat_card("Scene", "None", "Program scene")

        stats_grid.addWidget(self.stream_card, 0, 0)
        stats_grid.addWidget(self.record_card, 0, 1)
        stats_grid.addWidget(self.scene_card, 1, 0, 1, 2)

        layout.addLayout(stats_grid)

        controls_card = QFrame()
        controls_card.setObjectName("sectionCard")

        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(16, 16, 16, 16)
        controls_layout.setSpacing(12)

        controls_title = QLabel("TRANSPORT")
        controls_title.setObjectName("eyebrow")
        controls_title.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        controls_layout.addWidget(controls_title)

        transport_grid = QGridLayout()
        transport_grid.setHorizontalSpacing(10)
        transport_grid.setVerticalSpacing(10)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.setMinimumHeight(48)
        self.connect_button.clicked.connect(self.connect_obs)

        self.stream_button = QPushButton("Start stream")
        self.stream_button.setObjectName("secondaryButton")
        self.stream_button.setMinimumHeight(46)
        self.stream_button.clicked.connect(self._toggle_stream)

        self.record_button = QPushButton("Start record")
        self.record_button.setObjectName("secondaryButton")
        self.record_button.setMinimumHeight(46)
        self.record_button.clicked.connect(self._toggle_record)

        transport_grid.addWidget(self.connect_button, 0, 0, 1, 2)
        transport_grid.addWidget(self.stream_button, 1, 0)
        transport_grid.addWidget(self.record_button, 1, 1)

        controls_layout.addLayout(transport_grid)
        layout.addWidget(controls_card)

        self.scene_section = QFrame()
        self.scene_section.setObjectName("sectionCard")

        scene_section_layout = QVBoxLayout(self.scene_section)
        scene_section_layout.setContentsMargins(16, 16, 16, 16)
        scene_section_layout.setSpacing(12)

        scene_header = QVBoxLayout()
        scene_header.setSpacing(4)

        scene_title = QLabel("SCENES")
        scene_title.setObjectName("eyebrow")
        scene_title.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))

        self.scene_detail = QLabel("Choose the active program scene.")
        self.scene_detail.setObjectName("sectionDetail")
        self.scene_detail.setWordWrap(True)

        scene_header.addWidget(scene_title)
        scene_header.addWidget(self.scene_detail)
        scene_section_layout.addLayout(scene_header)

        scene_row = QHBoxLayout()
        scene_row.setSpacing(10)

        self.scene_combo = QComboBox()
        self.scene_combo.setObjectName("settingsCombo")
        self.scene_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.scene_apply_button = QPushButton("Switch")
        self.scene_apply_button.setObjectName("secondaryButton")
        self.scene_apply_button.setMinimumHeight(46)
        self.scene_apply_button.setMinimumWidth(118)
        self.scene_apply_button.clicked.connect(self._apply_scene)

        scene_row.addWidget(self.scene_combo, 1)
        scene_row.addWidget(self.scene_apply_button, 0)

        scene_section_layout.addLayout(scene_row)
        layout.addWidget(self.scene_section)

        self.status_label = QLabel("OBS widget is idle.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(64)
        layout.addWidget(self.status_label)

    def _stat_card(self, label: str, value: str, note: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(4)

        title = QLabel(label.upper())
        title.setObjectName("eyebrow")

        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        value_label.setWordWrap(True)

        note_label = QLabel(note)
        note_label.setObjectName("statNote")
        note_label.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(value_label)
        card_layout.addWidget(note_label)

        card._value_label = value_label  # type: ignore[attr-defined]
        card._note_label = note_label  # type: ignore[attr-defined]
        return card

    def _set_stat_value(self, card: QFrame, value: str) -> None:
        label = getattr(card, "_value_label", None)
        if isinstance(label, QLabel):
            label.setText(value)
        self._refresh_tooltips()

    def _set_tooltip(self, widget: QWidget, text: str) -> None:
        widget.setToolTip(text if self._tooltips_enabled else "")

    def _refresh_tooltips(self) -> None:
        if not self._tooltips_enabled:
            for widget in self.findChildren(QWidget):
                widget.setToolTip("")
            return
        obs = self.settings_state.get("obs", {})
        host = str(obs.get("host", "127.0.0.1")).strip() or "127.0.0.1"
        port = int(obs.get("port", 4455) or 4455)
        current_scene = self.scene_combo.currentData() if hasattr(self, "scene_combo") else ""
        scene_text = self.scene_combo.currentText() if hasattr(self, "scene_combo") else ""
        current_scene_text = str(current_scene or scene_text).strip() or "None"
        self._set_tooltip(self.panel, "OBS popup panel")
        self._set_tooltip(self.refresh_button, "Refresh OBS socket, stream, record, and scene state")
        self._set_tooltip(self.settings_button, "Open OBS widget settings")
        self._set_tooltip(self.close_button, "Close OBS popup")
        self._set_tooltip(self.hero, "OBS connection summary")
        self._set_tooltip(self.connection_badge, "OBS WebSocket status badge")
        self._set_tooltip(self.connection_hint, f"Configured OBS socket target: ws://{host}:{port}")
        self._set_tooltip(self.connection_label, f"Current OBS connection state: {self.connection_label.text()}")
        self._set_tooltip(self.hero_detail, self.hero_detail.text())
        self._set_tooltip(self.stream_pill, f"Current stream indicator: {self.stream_pill.text()}")
        self._set_tooltip(self.record_pill, f"Current record indicator: {self.record_pill.text()}")
        self._set_tooltip(self.stream_card, f"Stream status row: {getattr(self.stream_card._value_label, 'text', lambda: 'Unknown')()}")
        self._set_tooltip(self.record_card, f"Record status row: {getattr(self.record_card._value_label, 'text', lambda: 'Unknown')()}")
        self._set_tooltip(self.scene_card, f"Scene status row: {getattr(self.scene_card._value_label, 'text', lambda: 'Unknown')()}")
        self._set_tooltip(self.connect_button, "Connect to the configured OBS WebSocket")
        self._set_tooltip(self.stream_button, "Start or stop the OBS stream output")
        self._set_tooltip(self.record_button, "Start or stop the OBS recording output")
        self._set_tooltip(self.scene_section, "Program scene controls")
        self._set_tooltip(self.scene_combo, f"Selected program scene: {current_scene_text}")
        self._set_tooltip(self.scene_apply_button, f"Apply the selected program scene: {current_scene_text}")
        self._set_tooltip(self.status_label, self.status_label.text())

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(36, 36)
        button.setFont(QFont(self.icon_font, 17))
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

            QScrollArea#popupScroll,
            QWidget#scrollBody {{
                background: transparent;
                border: none;
            }}

            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 8px 2px 8px 0;
            }}

            QScrollBar::handle:vertical {{
                background: {rgba(theme.outline, 0.36)};
                border-radius: 4px;
                min-height: 28px;
            }}

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0;
            }}

            QFrame#panel {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.surface_container_high, 0.97)},
                    stop: 0.50 {rgba(theme.surface_container, 0.94)},
                    stop: 1 {rgba(blend(theme.surface_container, theme.surface, 0.42), 0.90)}
                );
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 28px;
            }}

            QLabel#eyebrow {{
                color: {theme.primary};
                letter-spacing: 1.8px;
            }}

            QLabel#title,
            QLabel#heroTitle,
            QLabel#statValue {{
                color: {theme.text};
            }}

            QLabel#title {{
                font-weight: 700;
            }}

            QLabel#subtitle, QLabel#heroMeta {{
                color: {theme.text_muted};
            }}

            QLabel#heroTitle {{
                font-size: 20px;
                font-weight: 700;
            }}

            QLabel#heroDetail, QLabel#statNote, QLabel#sectionDetail {{
                color: {rgba(theme.text, 0.78)};
            }}

            QLabel#statValue {{
                font-size: 16px;
                font-weight: 700;
            }}

            QFrame#heroCard {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.primary_container, 0.42)},
                    stop: 0.45 {rgba(theme.secondary, 0.14)},
                    stop: 1 {rgba(theme.surface_container_high, 0.94)}
                );
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 24px;
            }}

            QFrame#statCard,
            QFrame#sectionCard {{
                background: {rgba(theme.surface_container_high, 0.84)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 22px;
            }}

            QFrame#statCard {{
                min-height: 88px;
            }}

            QPushButton#iconButton,
            QPushButton#secondaryButton {{
                background: {rgba(theme.surface_container_high, 0.90)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
                padding: 10px 12px;
                text-align: left;
            }}

            QPushButton#iconButton {{
                color: {theme.primary};
                font-family: "{self.icon_font}";
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
                padding: 0;
                border-radius: 18px;
                text-align: center;
            }}

            QPushButton#iconButton:hover,
            QPushButton#secondaryButton:hover {{
                background: {rgba(theme.primary, 0.10)};
                border: 1px solid {rgba(theme.primary, 0.24)};
            }}

            QPushButton#primaryButton {{
                background: {theme.primary};
                color: {theme.on_primary_container};
                border: none;
                border-radius: 16px;
                padding: 12px 14px;
                font-weight: 600;
                text-align: left;
            }}

            QPushButton#primaryButton:hover {{
                background: {rgba(theme.primary, 0.92)};
            }}

            QPushButton#primaryButton:disabled,
            QPushButton#secondaryButton:disabled {{
                background: {rgba(theme.surface_container_high, 0.55)};
                color: {rgba(theme.text, 0.45)};
                border: 1px solid {rgba(theme.outline, 0.10)};
            }}

            QLabel#metaChip,
            QLabel#statusPill {{
                border-radius: 999px;
                padding: 7px 12px;
            }}

            QLabel#metaChip {{
                background: {rgba(theme.primary, 0.12)};
                border: 1px solid {rgba(theme.primary, 0.18)};
                color: {theme.primary};
            }}

            QLabel#statusPill {{
                color: {theme.text};
                background: {rgba(theme.on_surface, 0.055)};
                border: 1px solid {rgba(theme.outline, 0.14)};
            }}

            QLabel#statusLabel {{
                background: {rgba(theme.on_surface, 0.035)};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 18px;
                padding: 12px 14px;
                color: {theme.text};
            }}

            QComboBox#settingsCombo {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
                min-height: 44px;
                padding: 10px 12px;
            }}

            QComboBox#settingsCombo:hover {{
                border: 1px solid {rgba(theme.primary, 0.24)};
            }}

            QComboBox#settingsCombo QAbstractItemView {{
                background: {rgba(theme.surface_container_high, 0.98)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.16)};
                selection-background-color: {rgba(theme.primary, 0.18)};
                selection-color: {theme.text};
                outline: 0;
            }}

            QComboBox#settingsCombo::drop-down {{
                border: none;
                width: 22px;
            }}

            QComboBox#settingsCombo::down-arrow {{
                image: none;
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

    def _sync_from_settings(self) -> None:
        self.settings_state = load_settings_state()
        obs = self.settings_state.get("obs", {})
        self._tooltips_enabled = bool(obs.get("show_debug_tooltips", False))
        host = str(obs.get("host", "127.0.0.1"))
        port = int(obs.get("port", 4455) or 4455)
        self.connection_hint.setText(f"ws://{host}:{port}")
        self.status_label.setText(f"OBS target: ws://{host}:{port}")
        self._refresh_tooltips()

    def connect_obs(self) -> None:
        self._sync_from_settings()
        if self.socket.state() in {QAbstractSocket.SocketState.ConnectedState, QAbstractSocket.SocketState.ConnectingState}:
            return
        obs = self.settings_state.get("obs", {})
        host = str(obs.get("host", "127.0.0.1"))
        port = int(obs.get("port", 4455) or 4455)
        self.connection_label.setText("Connecting…")
        self.hero_detail.setText(f"Waiting for OBS at ws://{host}:{port}")
        self.connection_hint.setText("Socket handshake")
        self.socket.open(QUrl(f"ws://{host}:{port}"))

    def _on_connected(self) -> None:
        self.status_label.setText("Socket connected. Waiting for OBS handshake…")
        self._refresh_tooltips()

    def _on_disconnected(self) -> None:
        self.connected = False
        self._stream_live = False
        self._record_live = False
        self.connection_label.setText("Disconnected")
        self.hero_detail.setText("OBS socket is closed.")
        self._set_stat_value(self.stream_card, "Offline")
        self._set_stat_value(self.record_card, "Stopped")
        self.stream_pill.setText("Stream offline")
        self.record_pill.setText("Record stopped")
        self._refresh_tooltips()

    def _on_error(self, _error) -> None:
        self.connected = False
        self.connection_label.setText("Connection failed")
        self.hero_detail.setText(self.socket.errorString())
        self.connection_hint.setText("OBS unavailable")
        self.status_label.setText("Check OBS WebSocket host, port, or password.")
        self._refresh_tooltips()

    def _send_request(self, request_type: str, request_data: dict | None = None) -> None:
        if not self.connected:
            return
        self.request_counter += 1
        request_id = f"hanauta-{self.request_counter}"
        self.pending_requests[request_id] = request_type
        payload = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": request_id,
                "requestData": request_data or {},
            },
        }
        self.socket.sendTextMessage(json.dumps(payload))

    def refresh_status(self) -> None:
        if not self.connected:
            self.connect_obs()
            return
        for name in ("GetStreamStatus", "GetRecordStatus", "GetSceneList"):
            self._send_request(name)

    def _toggle_stream(self) -> None:
        if "Live" in getattr(self.stream_card._value_label, "text", lambda: "")():
            self._send_request("StopStream")
        else:
            self._send_request("StartStream")

    def _toggle_record(self) -> None:
        if "Recording" in getattr(self.record_card._value_label, "text", lambda: "")():
            self._send_request("StopRecord")
        else:
            self._send_request("StartRecord")

    def _apply_scene(self) -> None:
        scene = self.scene_combo.currentData()
        if scene:
            self._send_request("SetCurrentProgramScene", {"sceneName": str(scene)})

    def _on_message(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except Exception:
            return
        op = int(payload.get("op", -1))
        data = payload.get("d", {}) if isinstance(payload.get("d"), dict) else {}
        if op == 0:
            auth = data.get("authentication")
            identify = {"rpcVersion": int(data.get("rpcVersion", 1) or 1)}
            if isinstance(auth, dict):
                password = str(self.settings_state.get("obs", {}).get("password", ""))
                if password:
                    identify["authentication"] = obs_auth(password, str(auth.get("salt", "")), str(auth.get("challenge", "")))
            self.socket.sendTextMessage(json.dumps({"op": 1, "d": identify}))
            return
        if op == 2:
            self.connected = True
            self.connection_label.setText("Connected")
            self.hero_detail.setText("OBS is ready for stream, record, and scene control.")
            self.connection_hint.setText("Live socket")
            self.status_label.setText("OBS handshake complete.")
            self._refresh_tooltips()
            self.refresh_status()
            return
        if op == 5:
            event_type = str(data.get("eventType", ""))
            event_data = data.get("eventData", {}) if isinstance(data.get("eventData"), dict) else {}
            if event_type == "CurrentProgramSceneChanged":
                self._set_stat_value(self.scene_card, str(event_data.get("sceneName", "Unknown")))
            elif event_type == "StreamStateChanged":
                active = bool(event_data.get("outputActive", False))
                self._stream_live = active
                self._set_stat_value(self.stream_card, "Live" if active else "Offline")
                self.stream_pill.setText("Stream live" if active else "Stream offline")
            elif event_type == "RecordStateChanged":
                active = bool(event_data.get("outputActive", False))
                self._record_live = active
                self._set_stat_value(self.record_card, "Recording" if active else "Stopped")
                self.record_pill.setText("Record running" if active else "Record stopped")
            self._refresh_tooltips()
            return
        if op != 7:
            return
        request_id = str(data.get("requestId", ""))
        request_type = self.pending_requests.pop(request_id, "")
        request_status = data.get("requestStatus", {}) if isinstance(data.get("requestStatus"), dict) else {}
        if not bool(request_status.get("result", False)):
            self.status_label.setText(str(request_status.get("comment", "OBS request failed.")))
            return
        response = data.get("responseData", {}) if isinstance(data.get("responseData"), dict) else {}
        if request_type == "GetStreamStatus":
            active = bool(response.get("outputActive", False))
            self._stream_live = active
            self._set_stat_value(self.stream_card, "Live" if active else "Offline")
            self.stream_pill.setText("Stream live" if active else "Stream offline")
        elif request_type == "GetRecordStatus":
            active = bool(response.get("outputActive", False))
            self._record_live = active
            self._set_stat_value(self.record_card, "Recording" if active else "Stopped")
            self.record_pill.setText("Record running" if active else "Record stopped")
        elif request_type == "GetSceneList":
            current = str(response.get("currentProgramSceneName", ""))
            scenes = response.get("scenes", [])
            self.scene_combo.clear()
            self.scenes = []
            if isinstance(scenes, list):
                for scene in scenes:
                    if not isinstance(scene, dict):
                        continue
                    name = str(scene.get("sceneName", "")).strip()
                    if not name:
                        continue
                    self.scenes.append(name)
                    self.scene_combo.addItem(name, name)
            index = self.scene_combo.findData(current)
            if index >= 0:
                self.scene_combo.setCurrentIndex(index)
            self._set_stat_value(self.scene_card, current or "Unknown")
            self.scene_detail.setText(f"{len(self.scenes)} scene(s) loaded")
        else:
            self.refresh_status()
        self.status_label.setText("OBS state refreshed.")
        self._refresh_tooltips()

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        try:
            command = entry_command(SETTINGS_PAGE_SCRIPT, "--page", "services", "--service-section", "obs_widget")
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
    widget = ObsWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
