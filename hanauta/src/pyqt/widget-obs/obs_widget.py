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
    QHBoxLayout,
    QLabel,
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
from PyQt6.QtCore import QUrl


MATERIAL_ICONS = {
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

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hanauta OBS")
        self.setFixedSize(504, 612)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self._sync_from_settings()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        if bool(self.settings_state.get("obs", {}).get("auto_connect", False)):
            QTimer.singleShot(150, self.connect_obs)

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
        eyebrow = QLabel("OBS CONTROL")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        title = QLabel("Go live beautifully")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 22, QFont.Weight.DemiBold))
        self.subtitle = QLabel("Scenes, recording, and stream state from OBS WebSocket.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_status)
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
        self.connection_label = QLabel("Disconnected")
        self.connection_label.setObjectName("heroTitle")
        self.connection_label.setFont(QFont(self.display_font, 17, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("OBS is ready when the WebSocket is listening.")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setWordWrap(True)
        hero_layout.addWidget(self.connection_label)
        hero_layout.addWidget(self.hero_detail)
        layout.addWidget(self.hero)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.stream_card = self._stat_card("Stream", "Offline")
        self.record_card = self._stat_card("Record", "Stopped")
        self.scene_card = self._stat_card("Scene", "None")
        stats.addWidget(self.stream_card)
        stats.addWidget(self.record_card)
        stats.addWidget(self.scene_card)
        layout.addLayout(stats)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.clicked.connect(self.connect_obs)
        self.stream_button = QPushButton(f"{material_icon('play_arrow')} Stream")
        self.stream_button.setObjectName("secondaryButton")
        self.stream_button.clicked.connect(self._toggle_stream)
        self.record_button = QPushButton(f"{material_icon('videocam')} Record")
        self.record_button.setObjectName("secondaryButton")
        self.record_button.clicked.connect(self._toggle_record)
        controls.addWidget(self.connect_button)
        controls.addWidget(self.stream_button)
        controls.addWidget(self.record_button)
        layout.addLayout(controls)

        scene_row = QHBoxLayout()
        scene_row.setSpacing(10)
        self.scene_combo = QComboBox()
        self.scene_combo.setObjectName("settingsCombo")
        self.scene_apply_button = QPushButton(f"{material_icon('sync')} Switch scene")
        self.scene_apply_button.setObjectName("secondaryButton")
        self.scene_apply_button.clicked.connect(self._apply_scene)
        scene_row.addWidget(self.scene_combo, 1)
        scene_row.addWidget(self.scene_apply_button)
        layout.addLayout(scene_row)

        self.status_label = QLabel("OBS widget is idle.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def _stat_card(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(3)
        title = QLabel(label.upper())
        title.setObjectName("eyebrow")
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        card_layout.addWidget(title)
        card_layout.addWidget(value_label)
        card._value_label = value_label  # type: ignore[attr-defined]
        return card

    def _set_stat_value(self, card: QFrame, value: str) -> None:
        label = getattr(card, "_value_label", None)
        if isinstance(label, QLabel):
            label.setText(value)

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
            QLabel#title, QLabel#heroTitle, QLabel#statValue {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#heroDetail, QLabel#statusLabel {{
                color: {theme.text_muted};
            }}
            QFrame#heroCard, QFrame#statCard {{
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
            QComboBox#settingsCombo {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                padding: 9px 12px;
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
        host = str(obs.get("host", "127.0.0.1"))
        port = int(obs.get("port", 4455) or 4455)
        self.status_label.setText(f"OBS target: ws://{host}:{port}")

    def connect_obs(self) -> None:
        self._sync_from_settings()
        if self.socket.state() in {QAbstractSocket.SocketState.ConnectedState, QAbstractSocket.SocketState.ConnectingState}:
            return
        obs = self.settings_state.get("obs", {})
        host = str(obs.get("host", "127.0.0.1"))
        port = int(obs.get("port", 4455) or 4455)
        self.connection_label.setText("Connecting…")
        self.hero_detail.setText(f"Waiting for OBS at ws://{host}:{port}")
        self.socket.open(QUrl(f"ws://{host}:{port}"))

    def _on_connected(self) -> None:
        self.status_label.setText("Socket connected. Waiting for OBS handshake…")

    def _on_disconnected(self) -> None:
        self.connected = False
        self.connection_label.setText("Disconnected")
        self.hero_detail.setText("OBS socket is closed.")
        self._set_stat_value(self.stream_card, "Offline")
        self._set_stat_value(self.record_card, "Stopped")

    def _on_error(self, _error) -> None:
        self.connected = False
        self.connection_label.setText("Connection failed")
        self.hero_detail.setText(self.socket.errorString())
        self.status_label.setText("Check OBS WebSocket host, port, or password.")

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
            self.status_label.setText("OBS handshake complete.")
            self.refresh_status()
            return
        if op == 5:
            event_type = str(data.get("eventType", ""))
            event_data = data.get("eventData", {}) if isinstance(data.get("eventData"), dict) else {}
            if event_type == "CurrentProgramSceneChanged":
                self._set_stat_value(self.scene_card, str(event_data.get("sceneName", "Unknown")))
            elif event_type == "StreamStateChanged":
                active = bool(event_data.get("outputActive", False))
                self._set_stat_value(self.stream_card, "Live" if active else "Offline")
            elif event_type == "RecordStateChanged":
                active = bool(event_data.get("outputActive", False))
                self._set_stat_value(self.record_card, "Recording" if active else "Stopped")
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
            self._set_stat_value(self.stream_card, "Live" if active else "Offline")
        elif request_type == "GetRecordStatus":
            active = bool(response.get("outputActive", False))
            self._set_stat_value(self.record_card, "Recording" if active else "Stopped")
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
        else:
            self.refresh_status()
        self.status_label.setText("OBS state refreshed.")

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        try:
            subprocess.Popen(
                [python_bin(), str(SETTINGS_PAGE_SCRIPT), "--page", "services", "--service-section", "obs_widget"],
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
