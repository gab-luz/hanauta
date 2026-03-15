#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib import error, request

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
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


def apply_theme_globals() -> None:
    global THEME, PANEL_BG, CARD_BG, CARD_BG_SOFT, BORDER, BORDER_SOFT
    global TEXT, TEXT_MID, TEXT_DIM, ACCENT, ACCENT_SOFT, ACCENT_ALT
    global USER_BG, ASSISTANT_BG, INPUT_BG, BOTTOM_BG
    THEME = load_theme_palette()
    PANEL_BG = THEME.panel_bg
    CARD_BG = THEME.app_running_bg
    CARD_BG_SOFT = THEME.chip_bg
    BORDER = THEME.panel_border
    BORDER_SOFT = THEME.chip_border
    TEXT = THEME.text
    TEXT_MID = THEME.text_muted
    TEXT_DIM = THEME.inactive
    ACCENT = THEME.primary
    ACCENT_SOFT = THEME.accent_soft
    ACCENT_ALT = THEME.tertiary
    USER_BG = THEME.media_active_start
    ASSISTANT_BG = THEME.app_running_bg
    INPUT_BG = THEME.surface_container
    BOTTOM_BG = THEME.chip_bg


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


class FadeCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._offset = 0

    def get_offset(self) -> int:
        return self._offset

    def set_offset(self, value: int) -> None:
        self._offset = value
        self.updateGeometry()
        self.setContentsMargins(0, value, 0, 0)

    yOffset = pyqtProperty(int, fget=get_offset, fset=set_offset)


class BackendPill(QPushButton):
    def __init__(self, profile: BackendProfile, ui_font: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(34, 34)
        self.setFont(QFont(ui_font, 11, QFont.Weight.DemiBold))
        self.setIcon(_backend_icon(profile.icon_name))
        self.setIconSize(QPixmap(14, 14).size())
        self.setText("")
        self.setToolTip(profile.label)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {CARD_BG_SOFT};
                color: {TEXT_MID};
                border: 1px solid {BORDER_SOFT};
                border-radius: 999px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {THEME.hover_bg};
                color: {TEXT};
            }}
            QPushButton:checked {{
                background: {ACCENT_SOFT};
                color: {ACCENT};
                border: 1px solid {THEME.app_focused_border};
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
    placeholder = QPixmap(14, 14)
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
        self.resize(520, 420)
        self.setModal(True)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {THEME.surface_container};
                color: {TEXT};
            }}
            QLabel {{
                color: {TEXT};
            }}
            QLineEdit, QComboBox {{
                background: {INPUT_BG};
                color: {TEXT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 999px;
                padding: 8px 10px;
            }}
            QComboBox QAbstractItemView {{
                background: {THEME.surface};
                color: {TEXT};
                selection-background-color: {ACCENT_SOFT};
            }}
            QCheckBox {{
                color: {TEXT};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 1px solid {BORDER_SOFT};
                background: {CARD_BG};
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border: 1px solid {ACCENT};
            }}
            QPushButton {{
                min-height: 34px;
                background: {CARD_BG_SOFT};
                color: {TEXT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 999px;
                padding: 0 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {THEME.hover_bg};
                border: 1px solid {THEME.app_focused_border};
            }}
            QPushButton:pressed {{
                background: {THEME.hover_bg};
            }}
            QDialogButtonBox QPushButton {{
                min-width: 96px;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Backend Settings")
        title.setFont(QFont(ui_font, 13, QFont.Weight.DemiBold))
        root.addWidget(title)

        self.backend_combo = QComboBox()
        for profile in profiles:
            self.backend_combo.addItem(profile.label, profile.key)
        self.backend_combo.currentIndexChanged.connect(self._load_selected_backend)
        root.addWidget(self.backend_combo)

        self.enabled_check = QCheckBox("Enable backend icon after successful test")
        root.addWidget(self.enabled_check)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Host")
        root.addWidget(self.host_input)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Model")
        root.addWidget(self.model_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        root.addWidget(self.api_key_input)

        self.status_label = QLabel("Configure a backend and run Test.")
        self.status_label.setStyleSheet(f"color: {TEXT_MID};")
        root.addWidget(self.status_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.test_button = QPushButton("Test")
        self.test_button.clicked.connect(self._test_current_backend)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_current_backend)
        self.test_button.setStyleSheet(
            f"QPushButton {{ background: {CARD_BG_SOFT}; color: {TEXT}; border: 1px solid {BORDER_SOFT}; border-radius: 999px; }}"
            f"QPushButton:hover {{ background: {THEME.hover_bg}; color: {TEXT}; }}"
        )
        self.save_button.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: {THEME.active_text}; border: 1px solid {ACCENT}; border-radius: 999px; }}"
            f"QPushButton:hover {{ background: {THEME.secondary}; color: {THEME.active_text}; }}"
        )
        actions.addWidget(self.test_button)
        actions.addWidget(self.save_button)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        root.addWidget(buttons)

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
        last_status = str(payload.get("last_status", "Configure a backend and run Test."))
        self.status_label.setText(last_status if last_status else "Configure a backend and run Test.")
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
        bg = ACCENT_SOFT if accent else CARD_BG
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


class ActionIcon(QToolButton):
    def __init__(self, text: str, tooltip: str, ui_font: str) -> None:
        super().__init__()
        self.setText(text)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(28, 28)
        self.setFont(QFont(ui_font, 11, QFont.Weight.Bold))
        self.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                color: {TEXT_DIM};
                border: none;
                border-radius: 999px;
            }}
            QToolButton:hover {{
                background: {THEME.hover_bg};
                color: {TEXT};
            }}
            """
        )


class MessageCard(FadeCard):
    def __init__(self, item: ChatItemData, ui_font: str) -> None:
        super().__init__()
        self.browser: QTextBrowser | None = None
        bubble_bg = USER_BG if item.role == "user" else ASSISTANT_BG
        bubble_border = THEME.app_focused_border if item.role == "user" else BORDER_SOFT
        title_color = ACCENT_ALT if item.role == "user" else ACCENT
        self.setObjectName("messageCard")
        self.setStyleSheet(
            f"""
            QFrame#messageCard {{
                background: {bubble_bg};
                border: 1px solid {bubble_border};
                border-radius: 20px;
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

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)

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
            meta.setFont(QFont(ui_font, 10))
            meta.setStyleSheet(f"color: {TEXT_DIM};")
            header.addWidget(meta, 0, Qt.AlignmentFlag.AlignVCenter)

        header.addStretch(1)
        header.addWidget(ActionIcon("⧉", "Copy", ui_font))
        header.addWidget(ActionIcon("⋯", "More", ui_font))
        root.addLayout(header)

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
                line-height: 1.45;
            }}
            """
        )
        browser.document().setDefaultStyleSheet(
            f"""
            body {{
                color: {TEXT};
                font-size: 12px;
                line-height: 1.45;
                margin: 0;
            }}
            b {{ color: {THEME.on_surface}; }}
            code, pre {{
                background: {CARD_BG_SOFT};
                border-radius: 12px;
                color: {TEXT};
            }}
            a {{ color: {ACCENT}; }}
            """
        )
        browser.setHtml(item.body)
        browser.document().contentsChanged.connect(lambda b=browser: self._fit_browser_height(b))
        self.browser = browser
        self._fit_browser_height(browser)
        QTimer.singleShot(0, lambda b=browser: self._fit_browser_height(b))
        root.addWidget(browser)

        if item.chips:
            chips_wrap = QWidget()
            chips_layout = QHBoxLayout(chips_wrap)
            chips_layout.setContentsMargins(0, 0, 0, 0)
            chips_layout.setSpacing(8)
            for chip in item.chips:
                chips_layout.addWidget(self._chip(chip.text, ui_font))
            chips_layout.addStretch(1)
            root.addWidget(chips_wrap)

    def _chip(self, text: str, ui_font: str) -> QPushButton:
        chip = QPushButton(text)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setFont(QFont(ui_font, 10))
        chip.setStyleSheet(
            f"""
            QPushButton {{
                background: {CARD_BG_SOFT};
                color: {TEXT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 999px;
                padding: 7px 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {THEME.hover_bg};
            }}
            """
        )
        return chip

    def _fit_browser_height(self, browser: QTextBrowser) -> None:
        viewport_width = max(0, browser.viewport().width())
        if viewport_width > 0:
            browser.document().setTextWidth(viewport_width)
        height = int(browser.document().documentLayout().documentSize().height() + 12)
        browser.setFixedHeight(max(28, height))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
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
                border: 1px solid {BORDER_SOFT};
                border-radius: 20px;
            }}
            QLineEdit {{
                background: {INPUT_BG};
                color: {TEXT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 999px;
                font-size: 12px;
                padding: 0 14px;
            }}
            QLabel {{
                color: {TEXT_DIM};
            }}
            QPushButton {{
                background: {ACCENT};
                color: {THEME.active_text};
                border: none;
                border-radius: 999px;
                padding: 0 16px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {THEME.secondary};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.entry = QLineEdit()
        self.entry.setMinimumHeight(46)
        self.entry.setPlaceholderText('Message the model... "/" for commands')
        self.entry.setFont(QFont(ui_font, 12))
        self.entry.returnPressed.connect(self._emit_send)
        layout.addWidget(self.entry)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(10)

        self.provider_label.setFont(QFont(ui_font, 10))
        self.provider_label.setStyleSheet(f"color: {TEXT_MID};")
        footer.addWidget(self.provider_label)

        footer.addStretch(1)

        hint = QLabel("/clear")
        hint.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        hint.setStyleSheet(f"color: {TEXT};")
        footer.addWidget(hint)

        send_button = QPushButton("Send")
        send_button.setMinimumHeight(32)
        send_button.clicked.connect(self._emit_send)
        footer.addWidget(send_button)
        layout.addLayout(footer)

    def set_profile(self, profile: BackendProfile) -> None:
        self.provider_label.setText(f"{profile.label}    {profile.model}")

    def _emit_send(self) -> None:
        text = self.entry.text().strip()
        if text:
            self.send_requested.emit(text)
            self.entry.clear()


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
        self.backend_settings = load_backend_settings()
        self.profile_by_key = {profile.key: profile for profile in self.profiles}
        self.current_profile: BackendProfile | None = None
        self._card_animations: list[QPropertyAnimation] = []

        self.setObjectName("sidebarPanel")
        self.setFixedWidth(430)
        self.setStyleSheet(
            f"""
            QFrame#sidebarPanel {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 30px;
            }}
            """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 14)
        glow = QColor(THEME.primary)
        glow.setAlpha(120)
        shadow.setColor(glow)
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addWidget(self._build_hero())
        root.addWidget(self._build_backend_strip())

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
                background: transparent;
                width: 8px;
                margin: 8px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {THEME.app_running_border};
                border-radius: 4px;
                min-height: 24px;
            }}
            """
        )

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 4, 0, 8)
        self.content_layout.setSpacing(14)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)

        self.composer = ComposerBar(ui_font)
        self.composer.send_requested.connect(self.add_user_message)
        root.addWidget(self.composer)

        self.populate_demo()
        self._refresh_available_backends()

    def _build_hero(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"""
            QFrame {{
                background: {CARD_BG};
                border: 1px solid {BORDER_SOFT};
                border-radius: 20px;
            }}
            QLabel {{
                color: {TEXT};
            }}
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)

        title = QLabel("Hanauta AI")
        title.setFont(QFont(self.ui_font, 15, QFont.Weight.DemiBold))
        subtitle = QLabel("Backend-aware native chat sidebar.")
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet(f"color: {TEXT_DIM};")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
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
                border-radius: 999px;
            }}
            QPushButton:hover {{
                background: {THEME.hover_bg};
                color: {TEXT};
            }}
            """
        )
        close_button.clicked.connect(self.window().close)
        top.addWidget(close_button)
        layout.addLayout(top)

        self.header_status = QLabel("Configure backends with the gear icon.")
        self.header_status.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        self.header_status.setStyleSheet(f"color: {TEXT_MID};")
        layout.addWidget(self.header_status)
        return frame

    def _build_backend_strip(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"""
            QFrame {{
                background: {CARD_BG_SOFT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 20px;
            }}
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        label = QLabel("Backends")
        label.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        label.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(label)

        pills = QWidget()
        pills_layout = QHBoxLayout(pills)
        pills_layout.setContentsMargins(0, 0, 0, 0)
        pills_layout.setSpacing(8)
        self.backend_buttons: dict[str, BackendPill] = {}
        for profile in self.profiles:
            button = BackendPill(profile, self.ui_font)
            button.clicked.connect(lambda checked=False, p=profile, b=button: self._select_backend(p, b))
            self.backend_buttons[profile.key] = button
            pills_layout.addWidget(button)
        pills_layout.addStretch(1)
        layout.addWidget(pills)

        self.backend_hint = QLabel()
        self.backend_hint.setFont(QFont(self.ui_font, 10))
        self.backend_hint.setStyleSheet(f"color: {TEXT_DIM};")
        self._refresh_backend_hint()
        layout.addWidget(self.backend_hint)
        return frame

    def _refresh_backend_hint(self) -> None:
        if self.current_profile is None:
            self.backend_hint.setText("No backend enabled yet. Open the gear icon and test one first.")
            self.header_status.setText("No active backend.")
            return
        self.backend_hint.setText(
            f"{self.current_profile.provider}  •  {self.current_profile.model}  •  {self.current_profile.host}"
        )
        self.header_status.setText(f"Active backend: {self.current_profile.label}")

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
            visible = bool(payload.get("enabled", True) and payload.get("tested", False))
            if button is not None:
                button.setVisible(visible)
                button.setChecked(False)
            if visible:
                available.append(profile)
        self.current_profile = available[0] if available else None
        if self.current_profile is not None:
            active = self.backend_buttons.get(self.current_profile.key)
            if active is not None:
                active.setChecked(True)
            self.composer.set_profile(self.current_profile)
            self.composer.entry.setEnabled(True)
            self.composer.entry.setPlaceholderText('Message the model... "/" for commands')
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

    def populate_demo(self) -> None:
        self._clear_cards()
        self.add_card(
            ChatItemData(
                role="user",
                title="You",
                body="<p>Give me a compact comparison between KoboldCpp, LM Studio, and Ollama for local inference.</p>",
                meta="prompt",
            ),
            animate=False,
        )
        self.add_card(
            ChatItemData(
                role="assistant",
                title="Gemini",
                meta="draft answer",
                body=(
                    "<p><b>Quick split:</b></p>"
                    "<p><b>KoboldCpp</b> is best when you want a lightweight local server focused on text-generation workflows and GGUF models.</p>"
                    "<p><b>LM Studio</b> is better when you want a polished desktop experience with a built-in model browser and an OpenAI-compatible local API.</p>"
                    "<p><b>Ollama</b> is strongest when you want a CLI-first runtime with simple model management and scripting.</p>"
                    "<p><b>Practical choice:</b> LM Studio for UI, Ollama for scripting, KoboldCpp for hobbyist tuning and roleplay-oriented setups.</p>"
                ),
                chips=[
                    SourceChipData("koboldcpp"),
                    SourceChipData("lm studio"),
                    SourceChipData("ollama"),
                ],
            ),
            animate=False,
        )
        self.content_layout.addStretch(1)

    def _clear_cards(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_card(self, data: ChatItemData, animate: bool = True) -> None:
        card = MessageCard(data, self.ui_font)
        insert_at = max(0, self.content_layout.count() - 1)
        self.content_layout.insertWidget(insert_at, card)
        if animate:
            self._animate_card_in(card)

    def _animate_card_in(self, card: MessageCard) -> None:
        opacity = card.windowOpacity()
        card.setWindowOpacity(0.0)
        anim = QPropertyAnimation(card, b"windowOpacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(max(1.0, opacity))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        slide = QPropertyAnimation(card, b"yOffset", self)
        slide.setDuration(240)
        slide.setStartValue(14)
        slide.setEndValue(0)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._card_animations.extend([anim, slide])
        anim.finished.connect(lambda: self._drop_animation(anim))
        slide.finished.connect(lambda: self._drop_animation(slide))
        anim.start()
        slide.start()

    def _drop_animation(self, animation: QPropertyAnimation) -> None:
        if animation in self._card_animations:
            self._card_animations.remove(animation)

    def add_user_message(self, text: str) -> None:
        if self.current_profile is None:
            return
        spacer = None
        if self.content_layout.count() and self.content_layout.itemAt(self.content_layout.count() - 1).spacerItem():
            spacer = self.content_layout.takeAt(self.content_layout.count() - 1)

        self.add_card(ChatItemData(role="user", title="You", body=f"<p>{text}</p>", meta="prompt"))
        self.add_card(
            ChatItemData(
                role="assistant",
                title=self.current_profile.label if self.current_profile is not None else "Assistant",
                meta=self.current_profile.model if self.current_profile is not None else "unconfigured",
                body=(
                    "<p><b>Mock response:</b> this recreated popup is now using the Hanauta palette and a denser sidebar layout.</p>"
                    f"<p>Active backend: <b>{self.current_profile.label if self.current_profile is not None else 'None'}</b> on <b>{self.current_profile.host if self.current_profile is not None else 'n/a'}</b>.</p>"
                    "<p>The next step is wiring this send handler back into the actual backend request layer if you want live completions instead of a mock UI.</p>"
                ),
                chips=[
                    SourceChipData(self.current_profile.provider if self.current_profile is not None else "no-backend"),
                    SourceChipData(self.current_profile.model if self.current_profile is not None else "setup-required"),
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

        self.resize(430, 900)
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
        screen = QApplication.primaryScreen()
        if screen is None:
            self.move(12, 42)
            return
        geo = screen.availableGeometry()
        self.move(14, geo.y() + 44)

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

        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start()

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
