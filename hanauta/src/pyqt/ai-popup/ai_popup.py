#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import json
import os
import sqlite3
import subprocess
import sys
import time
from base64 import b64decode
from dataclasses import dataclass, field
from pathlib import Path
from urllib import request, error
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QThread, Qt, QTimer, QUrl, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
try:
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except Exception:
    QWebEngineSettings = object  # type: ignore[assignment]
    QWebEngineView = object  # type: ignore[assignment]
    WEBENGINE_AVAILABLE = False

APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime
from pyqt.shared.button_helpers import create_close_button

THEME = load_theme_palette()
AI_ASSETS_DIR = APP_DIR / "pyqt" / "ai-popup" / "assets"
BACKEND_ICONS_DIR = AI_ASSETS_DIR / "backend-icons"
AI_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "ai-popup"
BACKEND_SETTINGS_FILE = AI_STATE_DIR / "backend_settings.json"
SECURE_DB_FILE = AI_STATE_DIR / "secure_store.sqlite3"
SECURE_KEY_FILE = AI_STATE_DIR / "secure_store.key"
IMAGE_OUTPUT_DIR = AI_STATE_DIR / "generated-images"


def rgba(color: str, alpha: float) -> str:
    q = QColor(color)
    q.setAlphaF(max(0.0, min(1.0, alpha)))
    return q.name(QColor.NameFormat.HexArgb)


def mix(color_a: str, color_b: str, amount: float) -> str:
    a = QColor(color_a)
    b = QColor(color_b)
    t = max(0.0, min(1.0, amount))
    r = round(a.red() + (b.red() - a.red()) * t)
    g = round(a.green() + (b.green() - a.green()) * t)
    b_ = round(a.blue() + (b.blue() - a.blue()) * t)
    return QColor(r, g, b_).name()


def focused_workspace() -> dict[str, object] | None:
    try:
        output = subprocess.check_output(["i3-msg", "-t", "get_workspaces"], text=True)
        workspaces = json.loads(output)
    except Exception:
        return None
    if not isinstance(workspaces, list):
        return None
    for workspace in workspaces:
        if isinstance(workspace, dict) and workspace.get("focused"):
            return workspace
    return None


def apply_theme_globals() -> None:
    global THEME, PANEL_BG, PANEL_BG_DEEP, PANEL_BG_FLOAT
    global CARD_BG, CARD_BG_SOFT, CARD_BG_RAISED, CARD_BG_ALT
    global BORDER, BORDER_SOFT, BORDER_HARD, BORDER_ACCENT
    global TEXT, TEXT_MID, TEXT_DIM, TEXT_SOFT
    global ACCENT, ACCENT_SOFT, ACCENT_ALT, ACCENT_GLOW
    global USER_BG, ASSISTANT_BG, INPUT_BG, BOTTOM_BG
    global SHADOW, HOVER_BG, HERO_TOP, HERO_BOTTOM

    THEME = load_theme_palette()
    PANEL_BG = THEME.panel_bg
    PANEL_BG_DEEP = mix(THEME.panel_bg, "#000000", 0.18)
    PANEL_BG_FLOAT = rgba(THEME.panel_bg, 0.96)

    CARD_BG = THEME.app_running_bg
    CARD_BG_SOFT = THEME.chip_bg
    CARD_BG_RAISED = mix(THEME.app_running_bg, "#ffffff", 0.04)
    CARD_BG_ALT = rgba(THEME.surface_container, 0.88)

    BORDER = THEME.panel_border
    BORDER_SOFT = THEME.chip_border
    BORDER_HARD = rgba(THEME.panel_border, 0.92)
    BORDER_ACCENT = rgba(THEME.app_focused_border, 0.95)

    TEXT = THEME.text
    TEXT_MID = THEME.text_muted
    TEXT_DIM = THEME.inactive
    TEXT_SOFT = mix(THEME.text_muted, THEME.inactive, 0.40)

    ACCENT = THEME.primary
    ACCENT_SOFT = THEME.accent_soft
    ACCENT_ALT = THEME.tertiary
    ACCENT_GLOW = rgba(THEME.primary, 0.22)

    USER_BG = mix(THEME.media_active_start, THEME.panel_bg, 0.18)
    ASSISTANT_BG = mix(THEME.app_running_bg, THEME.panel_bg, 0.05)
    INPUT_BG = rgba(THEME.surface_container, 0.98)
    BOTTOM_BG = rgba(THEME.chip_bg, 0.90)

    SHADOW = rgba(THEME.primary, 0.16)
    HOVER_BG = rgba(THEME.hover_bg, 0.92)
    HERO_TOP = mix(THEME.panel_bg, THEME.primary, 0.16)
    HERO_BOTTOM = mix(THEME.app_running_bg, THEME.panel_bg, 0.24)


apply_theme_globals()


def load_ui_font() -> str:
    font_dir = APP_DIR.parents[1] / "assets" / "fonts"
    if QFont("Rubik").exactMatch():
        return "Rubik"
    for name in ("Rubik-VariableFont_wght.ttf", "Rubik-Italic-VariableFont_wght.ttf", "Inter-Regular.ttf", "Inter.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_dir / name))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    return "Rubik"


def load_material_icon_font() -> str:
    font_dir = APP_DIR.parents[1] / "assets" / "fonts"
    for name in (
        "MaterialIcons-Regular.ttf",
        "MaterialIconsOutlined-Regular.otf",
        "MaterialSymbolsOutlined.ttf",
        "MaterialSymbolsRounded.ttf",
    ):
        font_id = QFontDatabase.addApplicationFont(str(font_dir / name))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    return "Material Icons"


@dataclass
class BackendProfile:
    key: str
    label: str
    provider: str
    model: str
    host: str
    icon_name: str
    needs_api_key: bool = False
    launchable: bool = False


@dataclass
class SourceChipData:
    text: str


@dataclass
class ChatItemData:
    role: str
    title: str
    body: str
    meta: str = ""
    chips: list[SourceChipData] = field(default_factory=list)
    pending: bool = False


class SurfaceFrame(QFrame):
    def __init__(self, bg: str = CARD_BG, border: str = BORDER_SOFT, radius: int = 24, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {radius}px;
            }}
            QLabel {{
                color: {TEXT};
            }}
            """
        )


class FadeCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._offset = 0

    def get_offset(self) -> int:
        return self._offset

    def set_offset(self, value: int) -> None:
        self._offset = value
        self.setContentsMargins(0, value, 0, 0)

    yOffset = pyqtProperty(int, fget=get_offset, fset=set_offset)


class ChatInputEdit(QPlainTextEdit):
    send_requested = pyqtSignal()

    def __init__(self, ui_font: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._min_height = 48
        self._max_height = 122
        self.setFont(QFont(ui_font, 12))
        self.setPlaceholderText('Message the model...  Enter to send • Shift+Enter for newline')
        self.setTabChangesFocus(True)
        self.document().documentLayout().documentSizeChanged.connect(self._sync_height)
        self._sync_height()

    def _sync_height(self) -> None:
        doc_height = int(self.document().size().height())
        new_height = max(self._min_height, min(self._max_height, doc_height + 18))
        self.setFixedHeight(new_height)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
        QTimer.singleShot(0, self._sync_height)


class BackendPill(QPushButton):
    def __init__(self, profile: BackendProfile, ui_font: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 40)
        self.setFont(QFont(ui_font, 11, QFont.Weight.DemiBold))
        self.setIcon(_backend_icon(profile.icon_name))
        self.setIconSize(QPixmap(18, 18).size())
        self.setText("")
        self.setToolTip(profile.label)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {rgba(CARD_BG_SOFT, 0.90)};
                border: 1px solid {BORDER_SOFT};
                border-radius: 20px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {HOVER_BG};
                border: 1px solid {BORDER_ACCENT};
            }}
            QPushButton:checked {{
                background: {ACCENT_SOFT};
                border: 1px solid {BORDER_ACCENT};
            }}
            QPushButton:disabled {{
                background: {rgba(CARD_BG_SOFT, 0.45)};
                border: 1px solid {rgba(BORDER_SOFT, 0.50)};
            }}
            """
        )


def _backend_icon_path(icon_name: str) -> Path | None:
    path = BACKEND_ICONS_DIR / f"{icon_name}.png"
    return path if path.exists() else None


def _backend_icon(icon_name: str) -> QIcon:
    path = _backend_icon_path(icon_name)
    if path is not None:
        return QIcon(str(path))
    placeholder = QPixmap(22, 22)
    placeholder.fill(Qt.GlobalColor.transparent)
    painter = QPainter(placeholder)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = placeholder.rect().adjusted(1, 1, -1, -1)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(rgba(ACCENT_SOFT, 0.92)))
    painter.drawRoundedRect(rect, 7, 7)
    painter.setPen(QColor(ACCENT))
    painter.setFont(QFont(load_ui_font(), 9, QFont.Weight.Black))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, icon_name[:2].upper())
    painter.end()
    return QIcon(placeholder)


def _path_text(value: object) -> str:
    return str(value).strip()


def _existing_path(value: object) -> Path | None:
    text = _path_text(value)
    if not text:
        return None
    path = Path(text).expanduser()
    return path if path.exists() else None


def _openai_compat_alive(host: str) -> bool:
    try:
        with request.urlopen(f"{_normalize_host_url(host)}/v1/models", timeout=1.2) as response:
            return response.status < 400
    except Exception:
        return False


def _apply_antialias_font(widget: QWidget) -> None:
    font = widget.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child_font = child.font()
        child_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        child.setFont(child_font)


def load_backend_settings() -> dict[str, dict[str, object]]:
    try:
        return json.loads(BACKEND_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_backend_settings(settings: dict[str, dict[str, object]]) -> None:
    AI_STATE_DIR.mkdir(parents=True, exist_ok=True)
    BACKEND_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _chmod_private(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _cipher() -> Fernet:
    AI_STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not SECURE_KEY_FILE.exists():
        SECURE_KEY_FILE.write_bytes(Fernet.generate_key())
        _chmod_private(SECURE_KEY_FILE)
    key = SECURE_KEY_FILE.read_bytes()
    _chmod_private(SECURE_KEY_FILE)
    return Fernet(key)


def _secure_db() -> sqlite3.Connection:
    AI_STATE_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(SECURE_DB_FILE)
    connection.execute("CREATE TABLE IF NOT EXISTS secrets (name TEXT PRIMARY KEY, payload BLOB NOT NULL)")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, payload BLOB NOT NULL, created_at REAL NOT NULL)"
    )
    connection.commit()
    _chmod_private(SECURE_DB_FILE)
    return connection


def _encrypt_payload(payload: dict[str, object]) -> bytes:
    return _cipher().encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _decrypt_payload(blob: bytes) -> dict[str, object]:
    data = _cipher().decrypt(blob)
    value = json.loads(data.decode("utf-8"))
    return value if isinstance(value, dict) else {}


def secure_store_secret(name: str, value: str) -> None:
    connection = _secure_db()
    try:
        if value.strip():
            connection.execute(
                "INSERT INTO secrets(name, payload) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload",
                (name, _encrypt_payload({"value": value})),
            )
        else:
            connection.execute("DELETE FROM secrets WHERE name = ?", (name,))
        connection.commit()
    finally:
        connection.close()


def secure_load_secret(name: str) -> str:
    connection = _secure_db()
    try:
        row = connection.execute("SELECT payload FROM secrets WHERE name = ?", (name,)).fetchone()
    finally:
        connection.close()
    if row is None:
        return ""
    try:
        payload = _decrypt_payload(row[0])
        return str(payload.get("value", ""))
    except (InvalidToken, json.JSONDecodeError, TypeError, ValueError):
        return ""


def secure_append_chat(item: ChatItemData) -> None:
    connection = _secure_db()
    try:
        connection.execute(
            "INSERT INTO chat_history(payload, created_at) VALUES(?, ?)",
            (
                _encrypt_payload(
                    {
                        "role": item.role,
                        "title": item.title,
                        "body": item.body,
                        "meta": item.meta,
                        "chips": [chip.text for chip in item.chips],
                    }
                ),
                time.time(),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def secure_load_chat_history() -> list[ChatItemData]:
    connection = _secure_db()
    try:
        rows = connection.execute("SELECT payload FROM chat_history ORDER BY id ASC").fetchall()
    finally:
        connection.close()
    history: list[ChatItemData] = []
    for row in rows:
        try:
            payload = _decrypt_payload(row[0])
        except (InvalidToken, json.JSONDecodeError, TypeError, ValueError):
            continue
        chips_raw = payload.get("chips", [])
        chips = [SourceChipData(str(chip)) for chip in chips_raw if str(chip).strip()] if isinstance(chips_raw, list) else []
        history.append(
            ChatItemData(
                role=str(payload.get("role", "assistant")),
                title=str(payload.get("title", "")),
                body=str(payload.get("body", "")),
                meta=str(payload.get("meta", "")),
                chips=chips,
            )
        )
    return history


def secure_clear_chat_history() -> None:
    connection = _secure_db()
    try:
        connection.execute("DELETE FROM chat_history")
        connection.commit()
    finally:
        connection.close()


def send_desktop_notification(title: str, body: str) -> None:
    try:
        import subprocess

        subprocess.Popen(
            ["notify-send", "-a", "Hanauta AI", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def _normalize_host_url(host: str) -> str:
    value = host.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value


def _http_json(url: str, timeout: float = 10.0) -> dict[str, object] | list[object]:
    req = request.Request(url, headers={"User-Agent": "Hanauta AI/1.0"})
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict[str, object], timeout: float = 180.0) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"User-Agent": "Hanauta AI/1.0", "Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def validate_backend(profile: BackendProfile, payload: dict[str, object]) -> tuple[bool, str]:
    host = str(payload.get("host", "")).strip()
    model = str(payload.get("model", "")).strip()
    api_key = secure_load_secret(f"{profile.key}:api_key")
    binary_path = _existing_path(payload.get("binary_path"))
    gguf_path = _existing_path(payload.get("gguf_path"))
    if not model:
        return False, "Model is required."
    if profile.needs_api_key and not api_key:
        return False, "API key is required."
    if not profile.needs_api_key and not host and not profile.launchable:
        return False, "Host is required."

    if profile.key == "koboldcpp":
        if binary_path is None:
            return False, "KoboldCpp binary path is required."
        if gguf_path is None:
            return False, "Select a GGUF model for KoboldCpp."
        if host and _openai_compat_alive(host):
            return True, "KoboldCpp is reachable."
        return True, "Launch config saved. Click the KoboldCpp icon to start it."

    if profile.provider == "tts_local":
        if binary_path is not None:
            return True, "Local TTS launch config looks valid."
        if host:
            return True, "Remote TTS endpoint saved."
        return False, "Set a host or a local binary path."

    if profile.provider == "sdwebui":
        url = _normalize_host_url(host)
        try:
            response = _http_json(f"{url}/sdapi/v1/samplers", timeout=3.0)
            if not isinstance(response, list):
                return False, "SD WebUI did not return samplers."
        except Exception:
            return False, "SD WebUI host did not respond."
        return True, "SD WebUI connection looks valid."

    if profile.provider == "openai_compat":
        url = _normalize_host_url(host)
        try:
            with request.urlopen(f"{url}/v1/models", timeout=2.5) as response:
                if response.status >= 400:
                    return False, f"HTTP {response.status}"
        except Exception:
            return False, "Host did not respond."
    elif profile.key == "ollama":
        url = _normalize_host_url(host)
        try:
            with request.urlopen(f"{url}/api/tags", timeout=2.5) as response:
                if response.status >= 400:
                    return False, f"HTTP {response.status}"
        except Exception:
            return False, "Host did not respond."

    return True, "Connection settings look valid."


class BackendSettingsDialog(QDialog):
    def __init__(
        self,
        profiles: list[BackendProfile],
        settings: dict[str, dict[str, object]],
        ui_font: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.profiles = profiles
        self.profile_map = {profile.key: profile for profile in profiles}
        self.settings = json.loads(json.dumps(settings))
        self.ui_font = ui_font

        self.setWindowTitle("AI Backend Settings")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(620, 760)
        self.setModal(True)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: transparent;
                color: {TEXT};
            }}
            QLabel {{
                color: {TEXT};
            }}
            QLineEdit, QComboBox {{
                background: {INPUT_BG};
                color: {TEXT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 18px;
                padding: 10px 12px;
                selection-background-color: {ACCENT_SOFT};
            }}
            QComboBox QAbstractItemView {{
                background: {CARD_BG};
                color: {TEXT};
                selection-background-color: {ACCENT_SOFT};
                border: 1px solid {BORDER_SOFT};
            }}
            QCheckBox {{
                color: {TEXT};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 1px solid {BORDER_SOFT};
                background: {CARD_BG};
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border: 1px solid {ACCENT};
            }}
            QPushButton {{
                min-height: 36px;
                background: {CARD_BG_SOFT};
                color: {TEXT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 18px;
                padding: 0 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {HOVER_BG};
                border: 1px solid {BORDER_ACCENT};
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        shell = SurfaceFrame(bg=rgba(CARD_BG, 0.92), border=BORDER_SOFT, radius=28)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(18, 18, 18, 18)
        shell_layout.setSpacing(12)
        root.addWidget(shell)

        title = QLabel("Backend settings")
        title.setFont(QFont(ui_font, 14, QFont.Weight.DemiBold))
        shell_layout.addWidget(title)

        subtitle = QLabel("Teste e habilite os providers antes de expor os ícones na sidebar.")
        subtitle.setFont(QFont(ui_font, 10))
        subtitle.setStyleSheet(f"color: {TEXT_DIM};")
        shell_layout.addWidget(subtitle)

        self.backend_combo = QComboBox()
        for profile in profiles:
            self.backend_combo.addItem(profile.label, profile.key)
        self.backend_combo.currentIndexChanged.connect(self._load_selected_backend)
        shell_layout.addWidget(self.backend_combo)

        self.enabled_check = QCheckBox("Mostrar backend na barra após teste bem-sucedido")
        shell_layout.addWidget(self.enabled_check)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Host")
        shell_layout.addWidget(self.host_input)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Model")
        shell_layout.addWidget(self.model_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        shell_layout.addWidget(self.api_key_input)

        self.binary_path_input = QLineEdit()
        self.binary_path_input.setPlaceholderText("Local binary path")
        shell_layout.addWidget(self.binary_path_input)

        self.gguf_path_input = QLineEdit()
        self.gguf_path_input.setPlaceholderText("GGUF model path")
        shell_layout.addWidget(self.gguf_path_input)

        self.text_model_path_input = QLineEdit()
        self.text_model_path_input.setPlaceholderText("Optional text model path for JoyCaption-style setups")
        shell_layout.addWidget(self.text_model_path_input)

        self.mmproj_path_input = QLineEdit()
        self.mmproj_path_input.setPlaceholderText("Optional mmproj path")
        shell_layout.addWidget(self.mmproj_path_input)

        self.device_combo = QComboBox()
        self.device_combo.addItem("CPU", "cpu")
        self.device_combo.addItem("GPU", "gpu")
        self.device_combo.setToolTip("Execution device")
        shell_layout.addWidget(self.device_combo)

        self.negative_prompt_input = QLineEdit()
        self.negative_prompt_input.setPlaceholderText("Default negative prompt")
        shell_layout.addWidget(self.negative_prompt_input)

        self.sampler_input = QLineEdit()
        self.sampler_input.setPlaceholderText("Sampler")
        shell_layout.addWidget(self.sampler_input)

        self.steps_input = QLineEdit()
        self.steps_input.setPlaceholderText("Steps")
        shell_layout.addWidget(self.steps_input)

        self.cfg_scale_input = QLineEdit()
        self.cfg_scale_input.setPlaceholderText("CFG scale")
        shell_layout.addWidget(self.cfg_scale_input)

        self.width_input = QLineEdit()
        self.width_input.setPlaceholderText("Width")
        shell_layout.addWidget(self.width_input)

        self.height_input = QLineEdit()
        self.height_input.setPlaceholderText("Height")
        shell_layout.addWidget(self.height_input)

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("SD output folder for monitor notifications")
        shell_layout.addWidget(self.output_dir_input)

        self.monitor_check = QCheckBox("Notify when new SD images appear in the output folder")
        shell_layout.addWidget(self.monitor_check)

        self.status_label = QLabel("Configure um backend e clique em Test.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {TEXT_MID};")
        shell_layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self.test_button = QPushButton("Test")
        self.test_button.clicked.connect(self._test_current_backend)
        actions.addWidget(self.test_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_current_backend)
        self.save_button.setStyleSheet(
            f"""
            QPushButton {{
                min-height: 36px;
                background: {ACCENT};
                color: {THEME.active_text};
                border: 1px solid {ACCENT};
                border-radius: 18px;
                padding: 0 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {mix(ACCENT, '#ffffff', 0.08)};
                border: 1px solid {ACCENT};
            }}
            """
        )
        actions.addWidget(self.save_button)
        actions.addStretch(1)
        shell_layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Close")
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        shell_layout.addWidget(buttons)

        _apply_antialias_font(self)
        self._load_selected_backend()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(QPen(QColor(rgba(BORDER_HARD, 0.92)), 1))
        painter.setBrush(QColor(rgba(PANEL_BG, 0.96)))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 30, 30)

    def _selected_profile(self) -> BackendProfile:
        key = str(self.backend_combo.currentData())
        return self.profile_map[key]

    def _current_payload(self) -> dict[str, object]:
        profile = self._selected_profile()
        existing = dict(self.settings.get(profile.key, {}))
        existing.update(
            {
                "enabled": bool(self.enabled_check.isChecked()),
                "host": self.host_input.text().strip(),
                "model": self.model_input.text().strip(),
                "binary_path": self.binary_path_input.text().strip(),
                "gguf_path": self.gguf_path_input.text().strip(),
                "text_model_path": self.text_model_path_input.text().strip(),
                "mmproj_path": self.mmproj_path_input.text().strip(),
                "device": str(self.device_combo.currentData()),
                "negative_prompt": self.negative_prompt_input.text().strip(),
                "sampler_name": self.sampler_input.text().strip(),
                "steps": self.steps_input.text().strip(),
                "cfg_scale": self.cfg_scale_input.text().strip(),
                "width": self.width_input.text().strip(),
                "height": self.height_input.text().strip(),
                "output_dir": self.output_dir_input.text().strip(),
                "monitor_enabled": bool(self.monitor_check.isChecked()),
            }
        )
        return existing

    def _load_selected_backend(self) -> None:
        profile = self._selected_profile()
        payload = dict(self.settings.get(profile.key, {}))
        self.enabled_check.setChecked(bool(payload.get("enabled", True)))
        self.host_input.setText(str(payload.get("host", profile.host)))
        self.model_input.setText(str(payload.get("model", profile.model)))
        self.api_key_input.setText(secure_load_secret(f"{profile.key}:api_key"))
        self.binary_path_input.setText(str(payload.get("binary_path", "")))
        self.gguf_path_input.setText(str(payload.get("gguf_path", "")))
        self.text_model_path_input.setText(str(payload.get("text_model_path", "")))
        self.mmproj_path_input.setText(str(payload.get("mmproj_path", "")))
        device = str(payload.get("device", "cpu")).lower()
        self.device_combo.setCurrentIndex(1 if device == "gpu" else 0)
        self.negative_prompt_input.setText(str(payload.get("negative_prompt", "")))
        self.sampler_input.setText(str(payload.get("sampler_name", "Euler a")))
        self.steps_input.setText(str(payload.get("steps", "28")))
        self.cfg_scale_input.setText(str(payload.get("cfg_scale", "7.0")))
        self.width_input.setText(str(payload.get("width", "1024")))
        self.height_input.setText(str(payload.get("height", "1024")))
        self.output_dir_input.setText(str(payload.get("output_dir", "")))
        self.monitor_check.setChecked(bool(payload.get("monitor_enabled", False)))
        self.api_key_input.setVisible(profile.needs_api_key)
        show_host = (not profile.needs_api_key) or profile.provider in {"sdwebui", "tts_local"}
        self.host_input.setVisible(show_host)
        is_sd = profile.provider == "sdwebui"
        is_kobold = profile.key == "koboldcpp"
        is_tts = profile.provider == "tts_local"
        device_enabled = is_kobold or is_tts
        self.binary_path_input.setVisible(is_kobold or is_tts)
        self.gguf_path_input.setVisible(is_kobold)
        self.text_model_path_input.setVisible(is_kobold)
        self.mmproj_path_input.setVisible(is_kobold)
        self.device_combo.setVisible(device_enabled)
        self.negative_prompt_input.setVisible(is_sd)
        self.sampler_input.setVisible(is_sd)
        self.steps_input.setVisible(is_sd)
        self.cfg_scale_input.setVisible(is_sd)
        self.width_input.setVisible(is_sd)
        self.height_input.setVisible(is_sd)
        self.output_dir_input.setVisible(is_sd)
        self.monitor_check.setVisible(is_sd)
        if is_sd:
            self.model_input.setPlaceholderText("Checkpoint / model")
        elif is_tts:
            self.model_input.setPlaceholderText("Voice / model")
        else:
            self.model_input.setPlaceholderText("Model")
        tested = bool(payload.get("tested", False))
        last_status = str(payload.get("last_status", "Configure um backend e clique em Test."))
        self.status_label.setText(last_status if last_status else "Configure um backend e clique em Test.")
        self.status_label.setStyleSheet(f"color: {ACCENT if tested else TEXT_MID};")

    def _test_current_backend(self) -> None:
        profile = self._selected_profile()
        payload = self._current_payload()
        ok, message = validate_backend(profile, payload)
        payload["tested"] = ok
        payload["last_status"] = message
        self.settings[profile.key] = payload
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {ACCENT if ok else ACCENT_ALT};")

    def _save_current_backend(self) -> None:
        profile = self._selected_profile()
        payload = self._current_payload()
        existing = self.settings.get(profile.key, {})
        secure_store_secret(f"{profile.key}:api_key", self.api_key_input.text().strip())
        payload["tested"] = bool(existing.get("tested", False))
        payload["last_status"] = existing.get("last_status", "Saved.")
        self.settings[profile.key] = payload
        save_backend_settings(self.settings)
        self.status_label.setText("Saved.")
        self.status_label.setStyleSheet(f"color: {TEXT_MID};")


class HeaderBadge(QFrame):
    def __init__(self, text: str, ui_font: str, accent: bool = False) -> None:
        super().__init__()
        bg = ACCENT_SOFT if accent else rgba(CARD_BG_SOFT, 0.92)
        fg = ACCENT if accent else TEXT_MID
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(0)
        label = QLabel(text)
        label.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        layout.addWidget(label)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {bg};
                border: 1px solid {BORDER_SOFT};
                border-radius: 999px;
            }}
            QLabel {{
                color: {fg};
            }}
            """
        )


class AntiAliasButton(QPushButton):
    def __init__(self, text: str, ui_font: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._ui_font = ui_font
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)
        self.setMinimumWidth(88)
        self.setFont(QFont(ui_font, 11, QFont.Weight.Black))
        self.setFlat(True)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2.0

        fill = QColor(ACCENT)
        if self.isDown():
            fill = QColor(mix(ACCENT, "#000000", 0.12))
        elif self.underMouse():
            fill = QColor(mix(ACCENT, "#ffffff", 0.08))

        border = QColor(rgba(BORDER_ACCENT, 0.58))
        painter.setPen(QPen(border, 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)

        painter.setPen(QColor(THEME.active_text))
        painter.setFont(QFont(self._ui_font, 11, QFont.Weight.Black))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())


class ActionIcon(QToolButton):
    def __init__(self, text: str, tooltip: str, ui_font: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(30, 30)
        self.setFont(QFont(ui_font, 11, QFont.Weight.Bold))
        self.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                color: {TEXT_DIM};
                border: none;
                border-radius: 15px;
            }}
            QToolButton:hover {{
                background: {HOVER_BG};
                color: {TEXT};
            }}
            """
        )


class AvatarBadge(QLabel):
    def __init__(self, text: str, bg: str, fg: str, ui_font: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(30, 30)
        self.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                color: {fg};
                border: 1px solid {rgba(fg, 0.18)};
                border-radius: 15px;
            }}
            """
        )


def render_chat_html(history: list[ChatItemData]) -> str:
    blocks: list[str] = []
    for item in history:
        is_user = item.role == "user"
        bubble_bg = USER_BG if is_user else ASSISTANT_BG
        bubble_border = BORDER_ACCENT if is_user else rgba(BORDER_SOFT, 0.95)
        title_color = ACCENT_ALT if is_user else ACCENT
        pending_class = " pending" if item.pending else ""
        chips = "".join(
            f'<span class="chip">{html.escape(chip.text)}</span>'
            for chip in item.chips
        )
        chips_html = f'<div class="chips">{chips}</div>' if chips else ""
        blocks.append(
            f"""
            <article class="message {'user' if is_user else 'assistant'}{pending_class}">
              <div class="avatar">{'Y' if is_user else 'AI'}</div>
              <div class="bubble" style="background:{bubble_bg}; border:1px solid {bubble_border};">
                <div class="header">
                  <span class="dot" style="color:{title_color};">●</span>
                  <span class="title" style="color:{title_color};">{html.escape(item.title)}</span>
                  <span class="meta">{html.escape(item.meta)}</span>
                </div>
                <div class="body">{item.body}</div>
                {chips_html}
              </div>
            </article>
            """
        )

    if not blocks:
        blocks.append(
            f"""
            <section class="empty-state">
              <div class="empty-title">No conversation yet</div>
              <div class="empty-copy">Pick a backend and start typing. Use <code>/image your prompt</code> with an SD backend to generate images.</div>
            </section>
            """
        )

    return f"""
    <html>
      <head>
        <style>
        html, body {{
            margin: 0;
            padding: 0;
            background: {rgba(CARD_BG, 0.72)};
            color: {TEXT};
            font-family: system-ui, sans-serif;
        }}
          body {{
            padding: 8px 6px 14px 6px;
          }}
          ::-webkit-scrollbar {{
            width: 12px;
          }}
          ::-webkit-scrollbar-track {{
            background: {rgba(CARD_BG_SOFT, 0.44)};
            border-radius: 6px;
          }}
          ::-webkit-scrollbar-thumb {{
            background: linear-gradient({rgba(ACCENT, 0.78)}, {rgba(THEME.app_running_border, 0.98)});
            border: 1px solid {rgba(BORDER_ACCENT, 0.72)};
            border-radius: 6px;
          }}
          .message {{
            display: flex;
            gap: 10px;
            margin: 0 0 12px 0;
            align-items: flex-start;
          }}
          .message.user {{
            flex-direction: row-reverse;
          }}
          .avatar {{
            width: 30px;
            min-width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 15px;
            font-size: 11px;
            font-weight: 700;
            background: {rgba(CARD_BG_SOFT, 0.96)};
            color: {ACCENT};
            border: 1px solid {rgba(ACCENT, 0.18)};
          }}
          .message.user .avatar {{
            background: {ACCENT_SOFT};
            color: {ACCENT_ALT};
            border-color: {rgba(ACCENT_ALT, 0.18)};
          }}
          .bubble {{
            flex: 1;
            max-width: calc(100% - 48px);
            border-radius: 24px;
            padding: 14px 16px 16px 16px;
            box-sizing: border-box;
          }}
          .message.pending .bubble {{
            box-shadow: 0 0 0 1px {rgba(ACCENT, 0.08)} inset;
          }}
          .header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
          }}
          .title {{
            font-weight: 700;
            font-size: 13px;
          }}
          .meta {{
            color: {TEXT_DIM};
            font-size: 11px;
          }}
          .body {{
            color: {TEXT};
            font-size: 13px;
            line-height: 1.55;
          }}
          .body p {{
            margin: 0 0 8px 0;
          }}
          .body code {{
            background: {rgba(CARD_BG_SOFT, 0.94)};
            padding: 2px 6px;
            border-radius: 10px;
          }}
          .body pre {{
            background: {rgba(CARD_BG_SOFT, 0.96)};
            border: 1px solid {rgba(BORDER_SOFT, 0.95)};
            padding: 10px 12px;
            border-radius: 16px;
            white-space: pre-wrap;
          }}
          .body img {{
            margin-top: 10px;
            max-width: 100%;
            border-radius: 18px;
            border: 1px solid {rgba(BORDER_SOFT, 0.95)};
          }}
          .loading-row {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
            color: {TEXT};
          }}
          .loading-ring {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            border: 2px solid {rgba(ACCENT, 0.22)};
            border-top-color: {ACCENT};
            animation: spin 0.9s linear infinite;
            box-sizing: border-box;
          }}
          @keyframes spin {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
          }}
          .chips {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
          }}
          .chip {{
            padding: 7px 12px;
            border-radius: 999px;
            background: {rgba(CARD_BG_SOFT, 0.92)};
            border: 1px solid {BORDER_SOFT};
            color: {TEXT};
            font-size: 11px;
          }}
          .empty-state {{
            padding: 28px 18px;
            border-radius: 24px;
            border: 1px dashed {rgba(BORDER_SOFT, 0.9)};
            background: {rgba(CARD_BG_SOFT, 0.18)};
          }}
          .empty-title {{
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 8px;
            color: {TEXT};
          }}
          .empty-copy {{
            font-size: 13px;
            line-height: 1.55;
            color: {TEXT_DIM};
          }}
          a {{
            color: {ACCENT};
            text-decoration: none;
          }}
        </style>
      </head>
      <body>{''.join(blocks)}</body>
    </html>
    """


class ChatWebView(QWebEngineView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setStyleSheet(f"background: {rgba(CARD_BG, 0.72)}; border: none;")
        self.page().setBackgroundColor(QColor(CARD_BG))

    def set_history(self, history: list[ChatItemData]) -> None:
        self.setHtml(render_chat_html(history), QUrl.fromLocalFile(str(AI_STATE_DIR) + "/"))
        self.loadFinished.connect(self._scroll_bottom_once)

    def _scroll_bottom_once(self, _ok: bool) -> None:
        try:
            self.loadFinished.disconnect(self._scroll_bottom_once)
        except Exception:
            pass
        self.page().runJavaScript("window.scrollTo(0, document.body.scrollHeight);")


class SdImageWorker(QThread):
    finished_ok = pyqtSignal(str, str, str)
    failed = pyqtSignal(str)

    def __init__(self, profile: BackendProfile, settings: dict[str, object], prompt: str) -> None:
        super().__init__()
        self.profile = profile
        self.settings = settings
        self.prompt = prompt

    def run(self) -> None:
        try:
            path = self._generate()
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(str(path), self.prompt, self.profile.label)

    def _generate(self) -> Path:
        url = _normalize_host_url(str(self.settings.get("host", self.profile.host)))
        IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        request_payload: dict[str, object] = {
            "prompt": self.prompt,
            "negative_prompt": str(self.settings.get("negative_prompt", "")),
            "sampler_name": str(self.settings.get("sampler_name", "Euler a")),
            "steps": int(float(str(self.settings.get("steps", "28")) or 28)),
            "cfg_scale": float(str(self.settings.get("cfg_scale", "7.0")) or 7.0),
            "width": int(float(str(self.settings.get("width", "1024")) or 1024)),
            "height": int(float(str(self.settings.get("height", "1024")) or 1024)),
        }
        checkpoint = str(self.settings.get("model", self.profile.model)).strip()
        if checkpoint:
            request_payload["override_settings"] = {"sd_model_checkpoint": checkpoint}
        response = _http_post_json(f"{url}/sdapi/v1/txt2img", request_payload, timeout=300.0)
        images = response.get("images", [])
        if not isinstance(images, list) or not images:
            raise RuntimeError("SD WebUI returned no images.")
        raw = str(images[0]).split(",", 1)[-1]
        file_path = IMAGE_OUTPUT_DIR / f"hanauta-ai-{int(time.time())}.png"
        file_path.write_bytes(b64decode(raw))
        return file_path


class MessageCard(FadeCard):
    def __init__(self, item: ChatItemData, ui_font: str) -> None:
        super().__init__()
        self.item = item
        self.browser: QTextBrowser | None = None
        self.bubble: QFrame | None = None

        self.setStyleSheet("background: transparent; border: none;")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        is_user = item.role == "user"
        bubble_bg = USER_BG if is_user else ASSISTANT_BG
        bubble_border = BORDER_ACCENT if is_user else rgba(BORDER_SOFT, 0.95)
        title_color = ACCENT_ALT if is_user else ACCENT

        avatar = AvatarBadge(
            "Y" if is_user else "AI",
            bg=ACCENT_SOFT if is_user else rgba(CARD_BG_SOFT, 0.96),
            fg=ACCENT_ALT if is_user else ACCENT,
            ui_font=ui_font,
        )

        bubble = QFrame()
        bubble.setObjectName("messageBubble")
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        bubble.setStyleSheet(
            f"""
            QFrame#messageBubble {{
                background: {bubble_bg};
                border: 1px solid {bubble_border};
                border-radius: 24px;
            }}
            QLabel {{
                color: {TEXT};
            }}
            QTextBrowser {{
                background: transparent;
                border: none;
                color: {TEXT};
                font-size: 12px;
            }}
            """
        )
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 14, 16, 16)
        bubble_layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {title_color}; font-size: 8px;")
        header.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        title = QLabel(item.title)
        title.setFont(QFont(ui_font, 11, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {title_color};")
        header.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)

        if item.meta:
            meta = QLabel(item.meta)
            meta.setFont(QFont(ui_font, 9))
            meta.setStyleSheet(f"color: {TEXT_DIM};")
            header.addWidget(meta, 0, Qt.AlignmentFlag.AlignVCenter)

        header.addStretch(1)
        copy_button = ActionIcon("⧉", "Copy response", ui_font)
        copy_button.clicked.connect(self._copy_body)
        header.addWidget(copy_button)
        header.addWidget(ActionIcon("⋯", "More", ui_font))
        bubble_layout.addLayout(header)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setFrameShape(QFrame.Shape.NoFrame)
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        browser.document().setDocumentMargin(0)
        browser.setStyleSheet(
            f"""
            QTextBrowser {{
                color: {TEXT};
                background: transparent;
                border: none;
                font-size: 12px;
                line-height: 1.50;
            }}
            """
        )
        browser.document().setDefaultStyleSheet(
            f"""
            body {{
                color: {TEXT};
                font-size: 12px;
                line-height: 1.50;
                margin: 0;
            }}
            p {{
                margin-top: 0;
                margin-bottom: 8px;
            }}
            b {{
                color: {TEXT};
                font-weight: 700;
            }}
            code {{
                background: {rgba(CARD_BG_SOFT, 0.94)};
                padding: 2px 6px;
                border-radius: 10px;
                color: {TEXT};
            }}
            pre {{
                background: {rgba(CARD_BG_SOFT, 0.96)};
                border: 1px solid {rgba(BORDER_SOFT, 0.95)};
                padding: 10px 12px;
                border-radius: 16px;
                color: {TEXT};
                white-space: pre-wrap;
            }}
            a {{
                color: {ACCENT};
                text-decoration: none;
            }}
            ul {{
                margin: 6px 0 8px 18px;
            }}
            """
        )
        browser.setHtml(item.body)
        browser.document().contentsChanged.connect(lambda b=browser: self._fit_browser_height(b))
        bubble_layout.addWidget(browser)

        if item.chips:
            chips_wrap = QWidget()
            chips_layout = QHBoxLayout(chips_wrap)
            chips_layout.setContentsMargins(0, 0, 0, 0)
            chips_layout.setSpacing(8)
            for chip in item.chips:
                chips_layout.addWidget(self._chip(chip.text, ui_font))
            chips_layout.addStretch(1)
            bubble_layout.addWidget(chips_wrap)

        self.browser = browser
        self.bubble = bubble
        self._fit_browser_height(browser)

        if is_user:
            root.addStretch(1)
            root.addWidget(bubble, 0)
            root.addWidget(avatar, 0, Qt.AlignmentFlag.AlignBottom)
        else:
            root.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            root.addWidget(bubble, 0)
            root.addStretch(1)

    def _copy_body(self) -> None:
        QApplication.clipboard().setText(self.browser.toPlainText() if self.browser else "")

    def _chip(self, text: str, ui_font: str) -> QPushButton:
        chip = QPushButton(text)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setFont(QFont(ui_font, 10))
        chip.setStyleSheet(
            f"""
            QPushButton {{
                background: {rgba(CARD_BG_SOFT, 0.92)};
                color: {TEXT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 999px;
                padding: 7px 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {HOVER_BG};
                border: 1px solid {BORDER_ACCENT};
            }}
            """
        )
        return chip

    def _fit_browser_height(self, browser: QTextBrowser) -> None:
        viewport_width = max(0, browser.viewport().width())
        if viewport_width > 0:
            browser.document().setTextWidth(viewport_width)
        height = int(browser.document().documentLayout().documentSize().height() + 8)
        browser.setFixedHeight(max(28, height))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self.bubble is not None:
            self.bubble.setMaximumWidth(max(280, int(self.width() * 0.80)))
        if self.browser is not None:
            self._fit_browser_height(self.browser)


class ComposerBar(QFrame):
    send_requested = pyqtSignal(str)

    def __init__(self, ui_font: str) -> None:
        super().__init__()
        self._ui_font = ui_font
        self.provider_label = QLabel("")
        self.setObjectName("composerBar")
        self.setStyleSheet(
            f"""
            QFrame#composerBar {{
                background: {BOTTOM_BG};
                border: 1px solid {rgba(BORDER_SOFT, 0.95)};
                border-radius: 24px;
            }}
            QLabel {{
                color: {TEXT_DIM};
            }}
            QPlainTextEdit {{
                background: {INPUT_BG};
                color: {TEXT};
                border: 1px solid {rgba(BORDER_SOFT, 0.98)};
                border-radius: 20px;
                font-size: 12px;
                padding: 10px 12px;
                selection-background-color: {ACCENT_SOFT};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.entry = ChatInputEdit(ui_font)
        self.entry.send_requested.connect(self._emit_send)
        layout.addWidget(self.entry)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(10)

        self.provider_label.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        self.provider_label.setStyleSheet(f"color: {TEXT_MID};")
        footer.addWidget(self.provider_label)

        footer.addStretch(1)

        clear_hint = QLabel("/clear")
        clear_hint.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        clear_hint.setStyleSheet(
            f"color: {TEXT_DIM}; background: {rgba(CARD_BG_SOFT, 0.22)}; border: none; padding: 6px 10px;"
        )
        footer.addWidget(clear_hint)

        send_button = AntiAliasButton("Send", ui_font)
        send_button.clicked.connect(self._emit_send)
        footer.addWidget(send_button)
        layout.addLayout(footer)

    def set_profile(self, profile: BackendProfile) -> None:
        self.provider_label.setText(f"{profile.label}  •  {profile.model}")

    def _emit_send(self) -> None:
        text = self.entry.toPlainText().strip()
        if text:
            self.send_requested.emit(text)
            self.entry.clear()
            self.entry._sync_height()


class SidebarPanel(QFrame):
    def __init__(self, ui_font: str) -> None:
        super().__init__()
        if not WEBENGINE_AVAILABLE:
            raise RuntimeError("QtWebEngine is required for Hanauta AI.")
        self.ui_font = ui_font
        self.icon_font = load_material_icon_font()
        self.profiles = [
            BackendProfile("gemini", "Gemini", "gemini", "gemini-2.0-flash", "Google", "gemini", True),
            BackendProfile("koboldcpp", "KoboldCpp", "openai_compat", "koboldcpp", "127.0.0.1:5001", "koboldcpp", False, True),
            BackendProfile("lmstudio", "LM Studio", "openai_compat", "local-model", "127.0.0.1:1234", "lmstudio"),
            BackendProfile("ollama", "Ollama", "ollama", "llama3.2", "127.0.0.1:11434", "ollama"),
            BackendProfile("openai", "OpenAI", "openai", "gpt-4.1-mini", "api.openai.com", "openai", True),
            BackendProfile("mistral", "Mistral", "openai", "mistral-small", "api.mistral.ai", "mistral", True),
            BackendProfile("sdwebui", "SD WebUI", "sdwebui", "sdxl", "127.0.0.1:7860", "sdwebui"),
            BackendProfile("sdreforge", "SD ReForge", "sdwebui", "sdxl", "127.0.0.1:7861", "sdreforge"),
            BackendProfile("kokorotts", "KokoroTTS", "tts_local", "kokoro", "127.0.0.1:8880", "kokorotts", False, True),
            BackendProfile("pockettts", "PocketTTS", "tts_local", "pocket", "127.0.0.1:8890", "pockettts", False, True),
        ]
        self.profile_by_key = {profile.key: profile for profile in self.profiles}
        self.backend_settings = load_backend_settings()
        self.current_profile: BackendProfile | None = None
        self._card_animations: list[QPropertyAnimation] = []
        self.chat_history = secure_load_chat_history()
        self._sd_seen_outputs: dict[str, tuple[str, float]] = {}
        self._image_worker: SdImageWorker | None = None
        self._local_backend_processes: dict[str, subprocess.Popen[str]] = {}
        self._pending_item: ChatItemData | None = None
        self._text_response_timer = QTimer(self)
        self._text_response_timer.setSingleShot(True)
        self._text_response_timer.timeout.connect(self._finish_mock_text_response)

        self.setObjectName("sidebarPanel")
        self.setFixedWidth(452)
        self.setStyleSheet(
            f"""
            QFrame#sidebarPanel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {PANEL_BG_FLOAT},
                    stop:0.55 {rgba(HERO_BOTTOM, 0.97)},
                    stop:1 {rgba(PANEL_BG_DEEP, 0.99)});
                border: 1px solid {BORDER_HARD};
                border-radius: 34px;
            }}
            QToolTip {{
                background: {rgba(CARD_BG, 0.98)};
                color: {TEXT};
                border: 1px solid {rgba(BORDER_ACCENT, 0.92)};
                border-radius: 10px;
                padding: 7px 10px;
            }}
            """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(54)
        shadow.setOffset(0, 18)
        glow = QColor(SHADOW)
        shadow.setColor(glow)
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        root.addWidget(self._build_hero())
        root.addWidget(self._build_backend_strip())

        convo_shell = SurfaceFrame(bg=rgba(CARD_BG, 0.72), border=rgba(BORDER_SOFT, 0.85), radius=28)
        convo_layout = QVBoxLayout(convo_shell)
        convo_layout.setContentsMargins(10, 10, 10, 10)
        convo_layout.setSpacing(8)

        convo_label = QLabel("Conversation")
        convo_label.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        convo_label.setStyleSheet(f"color: {TEXT}; padding-left: 4px;")
        convo_layout.addWidget(convo_label)

        self.chat_view = ChatWebView()
        convo_layout.addWidget(self.chat_view, 1)

        root.addWidget(convo_shell, 1)

        self.composer = ComposerBar(ui_font)
        self.composer.send_requested.connect(self.add_user_message)
        root.addWidget(self.composer)

        self._render_chat_history()
        self._refresh_available_backends()
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._poll_sd_output_monitors)
        self.monitor_timer.start(8000)

    def _build_hero(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("heroCard")
        frame.setStyleSheet(
            f"""
            QFrame#heroCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {rgba(HERO_TOP, 0.98)},
                    stop:1 {rgba(HERO_BOTTOM, 0.94)});
                border: 1px solid {rgba(BORDER_SOFT, 0.95)};
                border-radius: 26px;
            }}
            QLabel {{
                color: {TEXT};
            }}
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)

        orb = QLabel("◉")
        orb.setFont(QFont(self.ui_font, 13, QFont.Weight.Bold))
        orb.setStyleSheet(f"color: {ACCENT};")
        top.addWidget(orb, 0, Qt.AlignmentFlag.AlignTop)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(0)

        title = QLabel("Hanauta AI")
        title.setFont(QFont(self.ui_font, 16, QFont.Weight.DemiBold))
        title_wrap.addWidget(title)
        top.addLayout(title_wrap, 1)

        settings_button = ActionIcon("⚙", "Backend settings", self.ui_font)
        settings_button.clicked.connect(self._open_backend_settings)
        top.addWidget(settings_button)

        close_button = create_close_button("\ue5cd", self.icon_font)
        close_button.setToolTip("Close")
        close_button.setProperty("iconButton", True)
        close_button.setFixedSize(34, 34)
        close_button.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_DIM};
                border: none;
                border-radius: 17px;
            }}
            QPushButton:hover {{
                background: {HOVER_BG};
                color: {TEXT};
            }}
            """
        )
        close_button.clicked.connect(self.window().close)
        top.addWidget(close_button)
        layout.addLayout(top)

        status_shell = SurfaceFrame(bg=rgba(CARD_BG_SOFT, 0.64), border=rgba(BORDER_SOFT, 0.90), radius=18)
        status_layout = QVBoxLayout(status_shell)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(0)

        self.header_status = QLabel("Configure backends with the gear icon.")
        self.header_status.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        self.header_status.setStyleSheet(f"color: {TEXT};")
        status_layout.addWidget(self.header_status)
        layout.addWidget(status_shell)

        return frame

    def _build_backend_strip(self) -> QFrame:
        self.backend_buttons: dict[str, BackendPill] = {}

        frame = SurfaceFrame(bg=rgba(CARD_BG, 0.82), border=rgba(BORDER_SOFT, 0.88), radius=26)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        label = QLabel("Backends")
        label.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        label.setStyleSheet(f"color: {TEXT};")
        label.setMinimumWidth(92)
        row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)

        icon_row = QHBoxLayout()
        icon_row.setContentsMargins(0, 0, 0, 0)
        icon_row.setSpacing(8)
        for profile in self.profiles:
            button = BackendPill(profile, self.ui_font)
            button.clicked.connect(lambda checked=False, p=profile, b=button: self._select_backend(p, b))
            self.backend_buttons[profile.key] = button
            icon_row.addWidget(button)
        icon_row.addStretch(1)

        row.addLayout(icon_row, 1)
        layout.addLayout(row)
        return frame

    def _refresh_backend_hint(self) -> None:
        if self.current_profile is None:
            self.header_status.setText("No active backend.")
            return
        payload = self.backend_settings.get(self.current_profile.key, {})
        host = str(payload.get("host", self.current_profile.host))
        model = str(payload.get("model", self.current_profile.model))
        self.header_status.setText(f"{self.current_profile.label}  •  {model}  •  {host}")

    def _select_backend(self, profile: BackendProfile, active_button: BackendPill) -> None:
        settings = self.backend_settings.get(profile.key, {})
        if not settings.get("tested") or not settings.get("enabled", True):
            if profile.key != "koboldcpp" or not self._maybe_launch_koboldcpp(profile):
                return
            settings = self.backend_settings.get(profile.key, {})
        elif profile.key == "koboldcpp":
            self._maybe_launch_koboldcpp(profile)
        self.current_profile = profile
        for button in self.backend_buttons.values():
            if button is not active_button:
                button.setChecked(False)
        active_button.setChecked(True)
        self._refresh_backend_hint()
        self.composer.set_profile(profile)

    def _refresh_available_backends(self) -> None:
        available: list[BackendProfile] = []
        for profile in self.profiles:
            payload = self.backend_settings.get(profile.key, {})
            button = self.backend_buttons.get(profile.key)
            ready = bool(payload.get("enabled", True) and payload.get("tested", False))
            if button is not None:
                button.setEnabled(ready)
                button.setChecked(False)
                button.setToolTip(f"{profile.label} — {'ready' if ready else 'not tested'}")
            if ready:
                available.append(profile)

        self.current_profile = available[0] if available else None
        if self.current_profile is not None:
            active = self.backend_buttons.get(self.current_profile.key)
            if active is not None:
                active.setChecked(True)
            self.composer.set_profile(self.current_profile)
            self.composer.entry.setEnabled(True)
            self.composer.entry.setPlaceholderText('Message the model...  Enter to send • Shift+Enter for newline')
        else:
            self.composer.provider_label.setText("No tested backend configured")
            self.composer.entry.setEnabled(False)
            self.composer.entry.setPlaceholderText("Open backend settings to configure a provider")
        self._refresh_backend_hint()

    def _open_backend_settings(self) -> None:
        dialog = BackendSettingsDialog(self.profiles, self.backend_settings, self.ui_font, self)
        dialog.exec()
        self.backend_settings = load_backend_settings()
        self._refresh_available_backends()

    def _render_chat_history(self) -> None:
        history = list(self.chat_history)
        if self._pending_item is not None:
            history.append(self._pending_item)
        self.chat_view.set_history(history)

    def _maybe_launch_koboldcpp(self, profile: BackendProfile) -> bool:
        payload = dict(self.backend_settings.get(profile.key, {}))
        host = str(payload.get("host", profile.host)).strip()
        if host and _openai_compat_alive(host):
            return True
        process = self._local_backend_processes.get(profile.key)
        if process is not None and process.poll() is None:
            return True
        binary_path = _existing_path(payload.get("binary_path"))
        gguf_path = _existing_path(payload.get("gguf_path"))
        if binary_path is None or gguf_path is None:
            return False
        answer = QMessageBox.question(
            self,
            "Start KoboldCpp",
            "KoboldCpp is not responding. Start it now with the configured GGUF model?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        ok, message = self._launch_koboldcpp_process(profile, payload)
        self.add_card(
            ChatItemData(
                role="assistant",
                title="Hanauta AI",
                meta="runtime launch" if ok else "runtime launch failed",
                body=f"<p>{html.escape(message)}</p>",
            )
        )
        return ok

    def _launch_koboldcpp_process(self, profile: BackendProfile, payload: dict[str, object]) -> tuple[bool, str]:
        binary_path = _existing_path(payload.get("binary_path"))
        gguf_path = _existing_path(payload.get("gguf_path"))
        if binary_path is None or gguf_path is None:
            return False, "Configure both the KoboldCpp binary path and GGUF model first."
        command = [str(binary_path), "--model", str(gguf_path)]
        mmproj_path = _existing_path(payload.get("mmproj_path"))
        if mmproj_path is not None:
            command.extend(["--mmproj", str(mmproj_path)])
        host = str(payload.get("host", profile.host)).strip()
        if host:
            parsed = urlparse(_normalize_host_url(host))
            if parsed.port:
                command.extend(["--port", str(parsed.port)])
        if str(payload.get("device", "cpu")).lower() == "gpu":
            command.append("--usecublas")
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            return False, f"Unable to start KoboldCpp: {exc}"
        self._local_backend_processes[profile.key] = process
        send_desktop_notification("KoboldCpp starting", f"{profile.label} is starting with {gguf_path.name}.")
        return True, f"Starting KoboldCpp with {gguf_path.name}."

    def _clear_cards(self) -> None:
        self.chat_history = []
        self._pending_item = None
        self._text_response_timer.stop()
        secure_clear_chat_history()
        self._render_chat_history()

    def add_card(self, data: ChatItemData, animate: bool = True) -> None:
        del animate
        self.chat_history.append(data)
        secure_append_chat(data)
        self._render_chat_history()

    def _set_pending_state(self, profile_label: str, message: str, meta: str) -> None:
        self._pending_item = ChatItemData(
            role="assistant",
            title=profile_label,
            meta=meta,
            body=(
                f'<div class="loading-row"><span class="loading-ring"></span>'
                f"<span>{html.escape(message)}</span></div>"
            ),
            pending=True,
        )
        self.composer.entry.setEnabled(False)
        self._render_chat_history()

    def _clear_pending_state(self) -> None:
        self._pending_item = None
        self.composer.entry.setEnabled(self.current_profile is not None)
        self._render_chat_history()

    def _build_image_response(self, image_path: Path, prompt: str) -> str:
        image_url = image_path.resolve().as_uri()
        return (
            f"<p><b>Image generated.</b> Prompt: {html.escape(prompt)}</p>"
            f'<p><img src="{image_url}" alt="Generated image"/></p>'
            f"<p><a href=\"{image_url}\">Open image</a></p>"
        )

    def _poll_sd_output_monitors(self) -> None:
        for profile in self.profiles:
            if profile.provider != "sdwebui":
                continue
            payload = self.backend_settings.get(profile.key, {})
            if not bool(payload.get("monitor_enabled", False)):
                continue
            output_dir = Path(str(payload.get("output_dir", "")).strip()).expanduser()
            if not output_dir.exists() or not output_dir.is_dir():
                continue
            candidates = [
                path for path in output_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            ]
            if not candidates:
                continue
            latest = max(candidates, key=lambda item: item.stat().st_mtime)
            latest_state = (str(latest), latest.stat().st_mtime)
            previous = self._sd_seen_outputs.get(profile.key)
            self._sd_seen_outputs[profile.key] = latest_state
            if previous is None:
                continue
            if latest_state != previous:
                send_desktop_notification("SD image detected", f"New image found for {profile.label}: {latest.name}")

    def _start_image_generation(self, profile: BackendProfile, prompt: str) -> None:
        if self._image_worker is not None and self._image_worker.isRunning():
            self.add_card(
                ChatItemData(
                    role="assistant",
                    title="Hanauta AI",
                    meta="image generation busy",
                    body="<p>An image is already being generated. Please wait for it to finish.</p>",
                )
            )
            return
        self._set_pending_state(profile.label, "Response is being generated", "image generation")
        self._image_worker = SdImageWorker(profile, dict(self.backend_settings.get(profile.key, {})), prompt)
        self._image_worker.finished_ok.connect(self._handle_image_generated)
        self._image_worker.failed.connect(self._handle_image_failed)
        self._image_worker.finished.connect(self._finish_image_worker)
        self._image_worker.start()

    def _handle_image_generated(self, image_path_text: str, prompt: str, profile_label: str) -> None:
        image_path = Path(image_path_text)
        self._clear_pending_state()
        self.add_card(
            ChatItemData(
                role="assistant",
                title=profile_label,
                meta="image generated",
                body=self._build_image_response(image_path, prompt),
                chips=[SourceChipData("sd image"), SourceChipData(image_path.name)],
            )
        )
        send_desktop_notification("Image generated", f"{profile_label} finished a new image.")

    def _handle_image_failed(self, message: str) -> None:
        self._clear_pending_state()
        self.add_card(
            ChatItemData(
                role="assistant",
                title="Hanauta AI",
                meta="image generation failed",
                body=f"<p>Unable to generate image: {html.escape(message)}</p>",
            )
        )

    def _finish_image_worker(self) -> None:
        self._image_worker = None

    def _finish_mock_text_response(self) -> None:
        self._clear_pending_state()
        if self.current_profile is None:
            return
        self.add_card(
            ChatItemData(
                role="assistant",
                title=self.current_profile.label,
                meta=self.current_profile.model,
                body=(
                    "<p><b>Mock response:</b> text backends are still using the current placeholder response layer.</p>"
                    f"<p>Active backend: <b>{html.escape(self.current_profile.label)}</b> at <b>{html.escape(self.current_profile.host)}</b>.</p>"
                    "<p>The chat history and secure backend secrets are now stored outside the project in Hanauta state.</p>"
                ),
                chips=[SourceChipData(self.current_profile.provider), SourceChipData(self.current_profile.model)],
            )
        )

    def add_user_message(self, text: str) -> None:
        command = text.strip()
        if command == "/clear":
            self._clear_cards()
            return
        if self.current_profile is None:
            return

        safe = html.escape(text).replace("\n", "<br>")
        self.add_card(ChatItemData(role="user", title="You", body=f"<p>{safe}</p>", meta="prompt"))

        if command.startswith("/image "):
            prompt = command[len("/image "):].strip()
            if self.current_profile.provider != "sdwebui":
                self.add_card(
                    ChatItemData(
                        role="assistant",
                        title="Hanauta AI",
                        body="<p>Select an SD WebUI or SD ReForge backend before using <code>/image</code>.</p>",
                        meta="image command",
                    )
                )
                return
            if not prompt:
                self.add_card(
                    ChatItemData(role="assistant", title="Hanauta AI", body="<p>Usage: <code>/image your prompt</code></p>", meta="image command")
                )
                return
            self._start_image_generation(self.current_profile, prompt)
            return

        self._set_pending_state(self.current_profile.label, "Response is being generated", "text generation")
        self._text_response_timer.start(1350)


class DemoWindow(QMainWindow):
    def __init__(self, ui_font: str) -> None:
        super().__init__()
        self.ui_font = ui_font
        self._theme_mtime = palette_mtime()
        self._slide_animation: QPropertyAnimation | None = None
        self._fade_animation: QPropertyAnimation | None = None
        self._drag_offset: QPoint | None = None
        self._screen_fix_applied = False

        self.setWindowTitle("Hanauta AI")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        root = QWidget()
        root.setStyleSheet("background: transparent;")
        self.setCentralWidget(root)
        self.root = root

        self.layout = QVBoxLayout(root)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self._build_panel()

        self.resize(452, 930)
        self._place_window()
        QTimer.singleShot(40, self._animate_in)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _build_panel(self) -> None:
        if hasattr(self, "panel") and self.panel is not None:
            self.layout.removeWidget(self.panel)
            self.panel.deleteLater()
        self.panel = SidebarPanel(self.ui_font)
        self.layout.addWidget(self.panel)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        apply_theme_globals()
        self._build_panel()

    def _place_window(self) -> None:
        workspace = focused_workspace()
        if isinstance(workspace, dict):
            rect = workspace.get("rect")
            if isinstance(rect, dict):
                try:
                    self.move(int(rect.get("x", 0)) + 16, int(rect.get("y", 0)) + 40)
                    return
                except Exception:
                    pass
        screen = QApplication.primaryScreen()
        if screen is None:
            self.move(16, 44)
            return
        geo = screen.availableGeometry()
        self.move(geo.x() + 16, geo.y() + 40)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._screen_fix_applied:
            return
        self._screen_fix_applied = True
        QTimer.singleShot(0, self._force_primary_screen)

    def _force_primary_screen(self) -> None:
        workspace = focused_workspace()
        screen = None
        if isinstance(workspace, dict):
            rect = workspace.get("rect")
            if isinstance(rect, dict):
                try:
                    screen = QGuiApplication.screenAt(
                        QPoint(int(rect.get("x", 0)) + 48, int(rect.get("y", 0)) + 48)
                    )
                except Exception:
                    screen = None
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            handle = self.windowHandle()
            if handle is not None:
                handle.setScreen(screen)
        self._place_window()

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._slide_animation = None

        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setDuration(260)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.start()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 110:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ui_font = load_ui_font()
    app.setFont(QFont(ui_font, 10))
    window = DemoWindow(ui_font)
    window.show()
    sys.exit(app.exec())
