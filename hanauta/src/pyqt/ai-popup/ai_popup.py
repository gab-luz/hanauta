#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib import request

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, pyqtProperty, pyqtSignal
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
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
    for name in ("InterVariable.ttf", "Inter-Regular.ttf", "Inter.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_dir / name))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    return "Inter"


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
    placeholder = QPixmap(18, 18)
    placeholder.fill(Qt.GlobalColor.transparent)
    return QIcon(placeholder)


def load_backend_settings() -> dict[str, dict[str, object]]:
    try:
        return json.loads(BACKEND_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_backend_settings(settings: dict[str, dict[str, object]]) -> None:
    AI_STATE_DIR.mkdir(parents=True, exist_ok=True)
    BACKEND_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def validate_backend(profile: BackendProfile, payload: dict[str, object]) -> tuple[bool, str]:
    host = str(payload.get("host", "")).strip()
    model = str(payload.get("model", "")).strip()
    api_key = str(payload.get("api_key", "")).strip()
    if not model:
        return False, "Model is required."
    if profile.needs_api_key and not api_key:
        return False, "API key is required."
    if not profile.needs_api_key and not host:
        return False, "Host is required."

    if profile.provider == "openai_compat":
        url = host.rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        try:
            with request.urlopen(f"{url}/v1/models", timeout=2.5) as response:
                if response.status >= 400:
                    return False, f"HTTP {response.status}"
        except Exception:
            return False, "Host did not respond."
    elif profile.key == "ollama":
        url = host.rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
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
        self.resize(560, 430)
        self.setModal(True)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {PANEL_BG};
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
        root.setContentsMargins(18, 18, 18, 18)
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

        self._load_selected_backend()

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
                "api_key": self.api_key_input.text().strip(),
            }
        )
        return existing

    def _load_selected_backend(self) -> None:
        profile = self._selected_profile()
        payload = dict(self.settings.get(profile.key, {}))
        self.enabled_check.setChecked(bool(payload.get("enabled", True)))
        self.host_input.setText(str(payload.get("host", profile.host)))
        self.model_input.setText(str(payload.get("model", profile.model)))
        self.api_key_input.setText(str(payload.get("api_key", "")))
        self.api_key_input.setVisible(profile.needs_api_key)
        self.host_input.setVisible(not profile.needs_api_key)
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
        self.ui_font = ui_font
        self.icon_font = load_material_icon_font()
        self.profiles = [
            BackendProfile("gemini", "Gemini", "gemini", "gemini-2.0-flash", "Google", "gemini", True),
            BackendProfile("koboldcpp", "KoboldCpp", "openai_compat", "koboldcpp", "127.0.0.1:5001", "koboldcpp"),
            BackendProfile("lmstudio", "LM Studio", "openai_compat", "local-model", "127.0.0.1:1234", "lmstudio"),
            BackendProfile("ollama", "Ollama", "ollama", "llama3.2", "127.0.0.1:11434", "ollama"),
            BackendProfile("openai", "OpenAI", "openai", "gpt-4.1-mini", "api.openai.com", "openai", True),
            BackendProfile("mistral", "Mistral", "openai", "mistral-small", "api.mistral.ai", "mistral", True),
        ]
        self.profile_by_key = {profile.key: profile for profile in self.profiles}
        self.backend_settings = load_backend_settings()
        self.current_profile: BackendProfile | None = None
        self._card_animations: list[QPropertyAnimation] = []

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

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {rgba(CARD_BG_SOFT, 0.44)};
                width: 12px;
                margin: 6px 0 6px 10px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {rgba(ACCENT, 0.78)},
                    stop:1 {rgba(THEME.app_running_border, 0.98)}
                );
                border: 1px solid {rgba(BORDER_ACCENT, 0.72)};
                border-radius: 6px;
                min-height: 36px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
                border: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            """
        )

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(4, 4, 4, 8)
        self.content_layout.setSpacing(12)
        self.scroll.setWidget(self.content)
        convo_layout.addWidget(self.scroll, 1)

        root.addWidget(convo_shell, 1)

        self.composer = ComposerBar(ui_font)
        self.composer.send_requested.connect(self.add_user_message)
        root.addWidget(self.composer)

        self._clear_cards()
        self._refresh_available_backends()

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
            return
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

    def _clear_cards(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.content_layout.addStretch(1)

    def add_card(self, data: ChatItemData, animate: bool = True) -> None:
        card = MessageCard(data, self.ui_font)
        insert_at = max(0, self.content_layout.count() - 1)
        self.content_layout.insertWidget(insert_at, card)
        if animate:
            self._animate_card_in(card)

    def _animate_card_in(self, card: MessageCard) -> None:
        opacity_effect = QGraphicsOpacityEffect(card)
        opacity_effect.setOpacity(0.0)
        card.setGraphicsEffect(opacity_effect)

        fade = QPropertyAnimation(opacity_effect, b"opacity", self)
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        slide = QPropertyAnimation(card, b"yOffset", self)
        slide.setDuration(240)
        slide.setStartValue(12)
        slide.setEndValue(0)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._card_animations.extend([fade, slide])
        fade.finished.connect(lambda eff=opacity_effect, anim=fade: self._drop_animation(anim, eff))
        slide.finished.connect(lambda anim=slide: self._drop_animation(anim))
        fade.start()
        slide.start()

    def _drop_animation(self, animation: QPropertyAnimation, effect: QGraphicsOpacityEffect | None = None) -> None:
        if animation in self._card_animations:
            self._card_animations.remove(animation)
        if effect is not None and animation.state() == QPropertyAnimation.State.Stopped:
            parent = effect.parent()
            if isinstance(parent, QWidget):
                parent.setGraphicsEffect(None)
            effect.deleteLater()

    def add_user_message(self, text: str) -> None:
        if self.current_profile is None:
            return

        spacer = None
        if self.content_layout.count() and self.content_layout.itemAt(self.content_layout.count() - 1).spacerItem():
            spacer = self.content_layout.takeAt(self.content_layout.count() - 1)

        safe = html.escape(text).replace("\n", "<br>")
        self.add_card(ChatItemData(role="user", title="You", body=f"<p>{safe}</p>", meta="prompt"))
        self.add_card(
            ChatItemData(
                role="assistant",
                title=self.current_profile.label,
                meta=self.current_profile.model,
                body=(
                    "<p><b>Mock response:</b> a nova popup agora está mais densa, mais arredondada e com camadas visuais mais próximas de uma shell sidebar.</p>"
                    f"<p>Backend atual: <b>{html.escape(self.current_profile.label)}</b> em <b>{html.escape(self.current_profile.host)}</b>.</p>"
                    "<p>Próximo passo real: ligar este composer ao request layer e fazer streaming/token-by-token na mesma bubble.</p>"
                ),
                chips=[
                    SourceChipData(self.current_profile.provider),
                    SourceChipData(self.current_profile.model),
                ],
            )
        )

        if spacer is not None:
            self.content_layout.addItem(spacer)

        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        QGuiApplication.processEvents()
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())


class DemoWindow(QMainWindow):
    def __init__(self, ui_font: str) -> None:
        super().__init__()
        self.ui_font = ui_font
        self._theme_mtime = palette_mtime()
        self._slide_animation: QPropertyAnimation | None = None
        self._fade_animation: QPropertyAnimation | None = None
        self._drag_offset: QPoint | None = None

        self.setWindowTitle("Hanauta AI")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
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
        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            self.move(16, 44)
            return
        geo = screen.availableGeometry()
        self.move(16, geo.y() + 40)

    def _animate_in(self) -> None:
        start = self.pos() + QPoint(-28, 0)
        end = self.pos()
        self.move(start)
        self.setWindowOpacity(0.0)

        self._slide_animation = QPropertyAnimation(self, b"pos", self)
        self._slide_animation.setDuration(240)
        self._slide_animation.setStartValue(start)
        self._slide_animation.setEndValue(end)
        self._slide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide_animation.start()

        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setDuration(220)
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
