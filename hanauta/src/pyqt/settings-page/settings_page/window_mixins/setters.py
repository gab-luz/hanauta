#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hanauta Settings window implementation (extracted from settings.py).
"""

from __future__ import annotations

import argparse
import base64
import configparser
import hashlib
import importlib.util
import json
import os
import platform
import random
import re
import secrets
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib import error, request
from urllib import parse
import locale as pylocale
import zipfile

try:
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    Qt,
    QThread,
    QTimer,
    QStringListModel,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QImage,
    QIntValidator,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
try:
    from PyQt6.QtQuickWidgets import QQuickWidget
except Exception:  # pragma: no cover
    QQuickWidget = None
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QCompleter,
    QFrame,
    QFileDialog,
    QDialog,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QCheckBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

APP_DIR = Path(__file__).resolve().parents[3]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command, entry_patterns, python_executable
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family
from pyqt.shared.button_helpers import create_close_button
from pyqt.shared.plugin_bridge import (
    build_polkit_command,
    polkit_available,
    run_with_polkit,
    trigger_fullscreen_alert,
)
from pyqt.shared.plugin_runtime import resolve_plugin_script


ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
ASSETS_DIR = APP_DIR / "assets"
WALLS_DIR = ROOT / "hanauta" / "walls"
PLUGIN_INSTALL_STATE_DIR = (
    Path.home() / ".local" / "state" / "hanauta" / "plugins" / "install-state"
)
NOTIFICATION_RULES_FILE = (
    Path.home() / ".local" / "state" / "hanauta" / "notification-rules.ini"
)
WALLPAPER_SCRIPT = ROOT / "hanauta" / "scripts" / "set_wallpaper.sh"
MATUGEN_SCRIPT = ROOT / "hanauta" / "scripts" / "run_matugen.sh"
LOCK_SCRIPT = ROOT / "hanauta" / "scripts" / "lock"
CURRENT_WALLPAPER = Path.home() / ".wallpapers" / "wallpaper.png"
RENDERED_WALLPAPER_DIR = Path.home() / ".wallpapers" / "rendered"
WALLPAPER_SOURCE_CACHE_DIR = ROOT / "hanauta" / "vendor" / "wallpaper-sources"
COMMUNITY_WALLPAPER_DIR = ROOT / "hanauta" / "walls" / "community"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PICOM_CONFIG_FILE = ROOT / "picom.conf"
PICOM_RULES_DIR = ROOT / "hanauta" / "config" / "picom"
I3_CONFIG_FILE = ROOT / "config"
HOST_PLUGIN_API_VERSION = 1
BUILTIN_SERVICE_KEYS = {
    "kdeconnect",
    "weather",
    "desktop_clock_widget",
    "calendar_widget",
}

from settings_page.settings_store import (
    STATE_DIR,
    SETTINGS_FILE,
    _atomic_write_json_file,
    save_settings_state,
)
from settings_page.dock_settings import load_dock_settings_state
from settings_page.accent_palettes import accent_palette
from settings_page.fonts import load_app_fonts, detect_font, _button_qfont_weight, _button_css_weight, apply_antialias_font
from settings_page.home_assistant_client import fetch_home_assistant_json, normalize_ha_url
from settings_page.ntfy_client import (
    NTFY_USER_AGENT,
    normalize_ntfy_auth_mode,
    send_ntfy_message,
)
from settings_page.fs_utils import directory_size_bytes, filesystem_usage_bytes
from settings_page.formatting import format_bytes, format_uptime
from settings_page.display_utils import (
    build_display_command,
    normalize_display_orientation,
    resolution_area,
)
from settings_page.battery import read_battery_snapshot
from settings_page.system_probes import (
    default_audio_device,
    list_audio_devices,
    list_wifi_interfaces,
    list_wireguard_interfaces,
    startup_exec_lines,
)
from settings_page.picom_rules import (
    build_default_picom_config as build_default_picom_config_impl,
    ensure_picom_rule_files as ensure_picom_rule_files_impl,
    render_picom_rule_blocks as render_picom_rule_blocks_impl,
    sync_picom_rule_blocks as sync_picom_rule_blocks_impl,
)
from settings_page.wallpaper_sources import (
    recursive_wallpaper_candidates,
    sync_wallpaper_source_preset as sync_wallpaper_source_preset_impl,
)
from settings_page.workers import (
    WALLPAPER_SOURCE_CACHE_DIR,
    COMMUNITY_WALLPAPER_DIR,
    WallpaperSourceSyncWorker,
    GameModeSummaryWorker,
)
from settings_page.plugin_backends import (
    gamemode_summary,
    WeatherCity,
    configured_city,
    search_cities,
    entity_friendly_name,
    entity_icon_name,
    entity_secondary_text,
    prefetch_entity_icons,
)
from settings_page.ui_widgets import (
    SwitchButton,
    PreviewCard,
    ActionCard,
    SettingsRow,
    ExpandableServiceSection,
)
from settings_page.widgets import NavPillButton, IconLabel, ThemeModeCard, SegmentedChip
from settings_page.pages.overview import build_overview_page
from settings_page.pages.storage import build_storage_page
from settings_page.pages.display import build_display_page
from settings_page.pages.appearance import build_appearance_page, build_wallpaper_colors_card
from settings_page.pages.services import build_services_page, build_services_card
from settings_page.pages.audio import build_audio_page, build_audio_card
from settings_page.pages.metrics import build_metric_card
from settings_page.shell import (
    build_bar_placeholder as shell_build_bar_placeholder,
    build_header as shell_build_header,
    build_scroll_body as shell_build_scroll_body,
    build_search_overlay as shell_build_search_overlay,
    build_services_placeholder as shell_build_services_placeholder,
    build_sidebar as shell_build_sidebar,
)
from settings_page.i3_utils import fullscreen_window_active, sanitize_output_name
from settings_page.wallpaper_render import draw_wallpaper_mode, rounded_pixmap
from settings_page.theme_data import (
    THEME_LIBRARY,
    HANAUTA_DARK_PALETTE,
    HANAUTA_FONT_PROFILE,
    THEME_CHOICES,
    CUSTOM_THEME_KEYS,
)
from settings_page.theme_gtk import (
    selected_theme_key,
    write_pyqt_palette,
    write_default_pyqt_palette,
    apply_gtk_theme,
    sync_static_theme_from_settings,
    ensure_theme_installed,
)
from settings_page.settings_defaults import load_settings_state


def wallpaper_candidates(folder: Path) -> list[Path]:
    return recursive_wallpaper_candidates(folder, IMAGE_SUFFIXES)


def sync_wallpaper_source_preset(source_key: str) -> tuple[bool, str, Path | None]:
    from settings_page.wallpaper_presets import WALLPAPER_SOURCE_PRESETS
    return sync_wallpaper_source_preset_impl(
        source_key,
        presets=WALLPAPER_SOURCE_PRESETS,
        cache_root=WALLPAPER_SOURCE_CACHE_DIR,
        community_root=COMMUNITY_WALLPAPER_DIR,
        image_suffixes=IMAGE_SUFFIXES,
    )
from settings_page.xrandr import parse_xrandr_state
from settings_page.picom_config import (
    read_picom_text,
    parse_picom_settings,
    format_picom_value,
    update_picom_config,
    sync_picom_rule_blocks,
    build_default_picom_config,
    ensure_picom_rule_files,
    _picom_rule_files,
)

PICOM_SHADOW_EXCLUDE_FILE = PICOM_RULES_DIR / "shadow-exclude.rules"
PICOM_ROUNDED_EXCLUDE_FILE = PICOM_RULES_DIR / "rounded-corners-exclude.rules"
PICOM_OPACITY_RULE_FILE = PICOM_RULES_DIR / "opacity.rules"
PICOM_FADE_EXCLUDE_FILE = PICOM_RULES_DIR / "fade-exclude.rules"
PYQT_THEME_DIR = Path.home() / ".local" / "state" / "hanauta" / "theme"
PYQT_THEME_FILE = PYQT_THEME_DIR / "pyqt_palette.json"
BAR_ICON_CONFIG_DIR = Path.home() / ".config" / "hanauta"
BAR_ICON_CONFIG_FILE = BAR_ICON_CONFIG_DIR / "bar-icons.json"
BAR_ICON_EXAMPLE_FILE = ROOT / "hanauta" / "config" / "bar-icons.example.json"
HOME_ASSISTANT_LOGO = ROOT / "hanauta" / "src" / "assets" / "home-assistant-dark.svg"
DESKTOP_CLOCK_BINARY = ROOT / "bin" / "hanauta-clock"
PLUGIN_ENTRYPOINT = "hanauta_plugin.py"
PLUGIN_DEV_ROOT = Path.home() / "dev"
MAIL_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "email-client"
MAIL_DB_PATH = MAIL_STATE_DIR / "mail.sqlite3"
MAIL_DESKTOP_ID = "hanauta-mail.desktop"
MAIL_DESKTOP_SOURCE = ROOT / "hanauta" / "config" / "applications" / MAIL_DESKTOP_ID
MAIL_DESKTOP_LOCAL = Path.home() / ".local" / "share" / "applications" / MAIL_DESKTOP_ID
MAIL_DESKTOP_SYSTEM = Path("/usr/local/share/applications") / MAIL_DESKTOP_ID
MAIL_DESKTOP_INSTALL_SCRIPT = ROOT / "hanauta" / "scripts" / "install_mail_desktop.sh"
MAIL_DESKTOP_SYSTEM_INSTALL_SCRIPT = (
    ROOT / "hanauta" / "scripts" / "install_mail_desktop_system.sh"
)
SERVICE_CACHE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
BAR_SERVICE_CACHE_FILE = SERVICE_CACHE_DIR / "plugins" / "bar-services.json"
SERVICES_SECTION_CACHE_FILE = SERVICE_CACHE_DIR / "plugins" / "services-sections.json"
DOCK_CONFIG = APP_DIR / "pyqt" / "dock" / "dock.toml"
HANAUTA_CONFIG_DIR = Path.home() / ".config" / "hanauta"
HANAUTA_CONFIG_TOML = HANAUTA_CONFIG_DIR / "config.toml"


def load_email_client_api_key() -> str:
    if tomllib is None or not HANAUTA_CONFIG_TOML.exists():
        return ""
    try:
        payload = tomllib.loads(HANAUTA_CONFIG_TOML.read_text(encoding="utf-8"))
    except Exception:
        return ""
    current: object = payload
    for key in ("plugin", "email_client", "api_key"):
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def save_email_client_api_key(value: str) -> None:
    value = str(value or "").strip()
    HANAUTA_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = ""
    try:
        existing = HANAUTA_CONFIG_TOML.read_text(encoding="utf-8")
    except Exception:
        existing = ""
    lines = existing.splitlines()
    if not lines:
        HANAUTA_CONFIG_TOML.write_text(f"[plugin.email_client]\napi_key = {json.dumps(value)}\n", encoding="utf-8")
        return
    section_header = "[plugin.email_client]"
    start = -1
    for idx, line in enumerate(lines):
        if line.strip() == section_header:
            start = idx
            break
    if start == -1:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([section_header, f"api_key = {json.dumps(value)}"])
        HANAUTA_CONFIG_TOML.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("[") and lines[idx].strip().endswith("]"):
            end = idx
            break
    key_line = f"api_key = {json.dumps(value)}"
    for idx in range(start + 1, end):
        if lines[idx].lstrip().startswith("api_key"):
            lines[idx] = key_line
            break
    else:
        lines.insert(end, key_line)
    HANAUTA_CONFIG_TOML.write_text("\n".join(lines) + "\n", encoding="utf-8")
from settings_page.picom_presets import PICOM_DEFAULT_TEMPLATE, picom_rule_file_defaults
from settings_page.wallpaper_presets import WALLPAPER_SOURCE_PRESETS

PICOM_RULE_FILE_DEFAULTS: dict[Path, str] = picom_rule_file_defaults(
    PICOM_SHADOW_EXCLUDE_FILE,
    PICOM_ROUNDED_EXCLUDE_FILE,
    PICOM_OPACITY_RULE_FILE,
    PICOM_FADE_EXCLUDE_FILE,
)

from settings_page.bar_settings import (
    BAR_SERVICE_ICON_META,
    BAR_SERVICE_SWITCH_ATTRS,
    DEFAULT_BAR_SETTINGS,
    SERVICE_DISPLAY_SWITCH_NON_BAR_KEYS,
    merged_bar_settings,
)




from settings_page.service_settings import DEFAULT_SERVICE_SETTINGS, merged_service_settings

_SETTINGS_LANG_FILE = Path(__file__).resolve().parents[1] / "settings_languages.py"
try:
    from settings_languages import KEYBOARD_LAYOUT_PRESETS
except Exception:
    if _SETTINGS_LANG_FILE.exists():
        try:
            import importlib.util as _importlib_util

            _spec = _importlib_util.spec_from_file_location(
                "hanauta_settings_languages", _SETTINGS_LANG_FILE
            )
            _module = (
                _importlib_util.module_from_spec(_spec)
                if _spec is not None and _spec.loader is not None
                else None
            )
            if _module is not None:
                _spec.loader.exec_module(_module)
                KEYBOARD_LAYOUT_PRESETS = list(
                    getattr(_module, "KEYBOARD_LAYOUT_PRESETS", [])
                )
            else:
                KEYBOARD_LAYOUT_PRESETS = []
        except Exception:
            KEYBOARD_LAYOUT_PRESETS = []
    else:
        KEYBOARD_LAYOUT_PRESETS = []

from settings_page.material_icons import material_icon
from settings_page.presets import LOCALE_LANGUAGE_PRESETS, VOICE_LANGUAGE_PRESETS
from settings_page.notification_rules import (
    DEFAULT_NOTIFICATION_RULES,
    load_notification_rules_state_from_file,
)

from settings_page.startup import (
    restore_saved_wallpaper,
    restore_saved_vpn,
    restore_saved_displays,
)

from settings_page.services import (
    load_service_cache_json,
    resolve_desktop_clock_widget,
    resolve_email_client_app,
    resolve_qcal_wrapper,
    resolve_study_tracker_app,
    resolve_virtualization_daemon,
    run_bg,
    run_text,
)

from settings_page.marketplace import (
    build_marketplace_page,
    build_marketplace_card,
    marketplace_api_refresh_catalog_cache,
    marketplace_api_installed_plugins,
    marketplace_api_update_plugin,
    marketplace_api_update_all_plugins,
    _marketplace_sources_from_state,
    _marketplace_manifest_url_for_source_api,
    _marketplace_fetch_manifest_payload_api,
    _marketplace_normalize_shortcuts_field_api,
    _marketplace_normalize_catalog_api,
)

from settings_page.notification_state import (
    ensure_settings_state,
    load_notification_rules_state,
    save_notification_rules_state,
)







class SettersMixin:
    """Extracted methods for setters."""

    def _profile_state(self) -> dict:
        profile = self.settings_state.get("profile", {})
        if not isinstance(profile, dict):
            profile = {}
            self.settings_state["profile"] = profile
        profile.setdefault("first_name", "")
        profile.setdefault("nickname", "")
        pronunciations = profile.get("pronunciations", [])
        if not isinstance(pronunciations, list):
            pronunciations = []
            profile["pronunciations"] = pronunciations
        return profile


    def _save_profile_name_fields(self) -> None:
        profile = self._profile_state()
        first_name = str(getattr(self, "profile_first_name_input", QLineEdit()).text()).strip()
        nickname = str(getattr(self, "profile_nickname_input", QLineEdit()).text()).strip()
        profile["first_name"] = first_name
        profile["nickname"] = nickname
        save_settings_state(self.settings_state)


    def _add_profile_language_row(self) -> None:
        profile = self._profile_state()
        pronunciations = profile.get("pronunciations", [])
        if not isinstance(pronunciations, list):
            pronunciations = []
            profile["pronunciations"] = pronunciations
        pronunciations.append({"lang": "", "spoken_name": "", "new_email_phrase": ""})
        save_settings_state(self.settings_state)
        self._refresh_profile_language_rows()


    def _remove_profile_language_row(self, index: int) -> None:
        profile = self._profile_state()
        pronunciations = profile.get("pronunciations", [])
        if not isinstance(pronunciations, list):
            return
        if index < 0 or index >= len(pronunciations):
            return
        pronunciations.pop(index)
        save_settings_state(self.settings_state)
        self._refresh_profile_language_rows()


    def _update_profile_language_row(self, index: int, key: str, value: str) -> None:
        profile = self._profile_state()
        pronunciations = profile.get("pronunciations", [])
        if not isinstance(pronunciations, list):
            return
        if index < 0 or index >= len(pronunciations):
            return
        row = pronunciations[index]
        if not isinstance(row, dict):
            row = {}
            pronunciations[index] = row
        if key == "lang":
            row[key] = str(value or "").strip().replace("_", "-")
            save_settings_state(self.settings_state)
            self._refresh_profile_language_rows()
            return
        row[key] = str(value or "").strip()
        save_settings_state(self.settings_state)


    def _refresh_profile_language_rows(self) -> None:
        layout = getattr(self, "profile_languages_layout", None)
        if not isinstance(layout, QVBoxLayout):
            return
        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()

        profile = self._profile_state()
        pronunciations = profile.get("pronunciations", [])
        if not isinstance(pronunciations, list):
            pronunciations = []

        for index, row in enumerate(pronunciations):
            row_dict = row if isinstance(row, dict) else {}
            lang = str(row_dict.get("lang", "")).strip()
            spoken_name = str(row_dict.get("spoken_name", "")).strip()
            phrase = str(row_dict.get("new_email_phrase", "")).strip()
            label_map = {label: code for label, code in VOICE_LANGUAGE_PRESETS}
            code_map = {code: label for label, code in VOICE_LANGUAGE_PRESETS}
            lang_label = code_map.get(lang, lang).strip()

            card = QFrame()
            card.setObjectName("settingsRow")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(10)

            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            top.setSpacing(10)
            title = QLabel(f"Language: {lang_label or '...'}")
            title.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
            title.setStyleSheet("color: rgba(246,235,247,0.82);")

            remove_btn = QPushButton(material_icon("delete"))
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setFixedSize(32, 32)
            remove_btn.setFont(QFont(self.icon_font, 16))
            remove_btn.setProperty("iconButton", True)
            remove_btn.clicked.connect(
                lambda _checked=False, idx=index: self._remove_profile_language_row(idx)
            )

            top.addWidget(title, 1)
            top.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignRight)
            card_layout.addLayout(top)

            lang_combo = QComboBox()
            lang_combo.setObjectName("settingsCombo")
            lang_combo.setEditable(True)
            lang_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            labels = [label for label, _code in VOICE_LANGUAGE_PRESETS]
            lang_model = QStringListModel(labels, self)
            lang_completer = QCompleter(lang_model, self)
            lang_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            lang_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            lang_combo.setCompleter(lang_completer)
            for label, code in VOICE_LANGUAGE_PRESETS:
                lang_combo.addItem(label, code)
            existing_index = lang_combo.findData(lang)
            if existing_index >= 0:
                lang_combo.setCurrentIndex(existing_index)
            else:
                lang_combo.setCurrentText(lang)
            if lang_combo.lineEdit() is not None:
                lang_combo.lineEdit().setPlaceholderText("English (en), Português (Brasil) (pt-BR), ...")

            def _lang_code_for_text(text: str) -> str:
                raw = str(text or "").strip()
                if not raw:
                    return ""
                if raw in label_map:
                    return label_map[raw]
                return raw.replace("_", "-")

            lang_combo.activated.connect(
                lambda _=None, idx=index, w=lang_combo: self._update_profile_language_row(
                    idx, "lang", _lang_code_for_text(w.currentText())
                )
            )
            if lang_combo.lineEdit() is not None:
                lang_combo.lineEdit().editingFinished.connect(
                    lambda idx=index, w=lang_combo: self._update_profile_language_row(
                        idx, "lang", _lang_code_for_text(w.currentText())
                    )
                )
            card_layout.addWidget(
                SettingsRow(
                    material_icon("public"),
                    "Language",
                    "Pick a language name; Hanauta stores the BCP-47 tag (en, pt-BR, ...).",
                    self.icon_font,
                    self.ui_font,
                    lang_combo,
                )
            )

            spoken_input = QLineEdit(spoken_name)
            spoken_input.setPlaceholderText("What TTS should say (optional)")
            spoken_input.editingFinished.connect(
                lambda idx=index, w=spoken_input: self._update_profile_language_row(
                    idx, "spoken_name", w.text()
                )
            )
            card_layout.addWidget(
                SettingsRow(
                    material_icon("person"),
                    "Name pronunciation",
                    "Leave empty to use your nickname/first name as-is.",
                    self.icon_font,
                    self.ui_font,
                    spoken_input,
                )
            )

            phrase_input = QLineEdit(phrase)
            phrase_input.setPlaceholderText(
                "{user}, sorry to interrupt you — you got a new email."
            )
            phrase_input.editingFinished.connect(
                lambda idx=index, w=phrase_input: self._update_profile_language_row(
                    idx, "new_email_phrase", w.text()
                )
            )
            card_layout.addWidget(
                SettingsRow(
                    material_icon("mail"),
                    "New email voice phrase",
                    "Template supports {user}. Used by voice-mode interruptions.",
                    self.icon_font,
                    self.ui_font,
                    phrase_input,
                )
            )

            layout.addWidget(card)

        layout.addStretch(1)


    def _build_profile_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("person"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Profile")
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        title.setFont(QFont(self.display_font, 13))
        subtitle = QLabel("Your name and voice-mode phrases reused by plugins.")
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setWordWrap(True)
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        profile = self._profile_state()

        self.profile_first_name_input = QLineEdit(str(profile.get("first_name", "")))
        self.profile_first_name_input.setPlaceholderText("First name")
        self.profile_first_name_input.editingFinished.connect(self._save_profile_name_fields)
        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "First name",
                "Used as a fallback when nickname is empty.",
                self.icon_font,
                self.ui_font,
                self.profile_first_name_input,
            )
        )

        self.profile_nickname_input = QLineEdit(str(profile.get("nickname", "")))
        self.profile_nickname_input.setPlaceholderText("Nickname / preferred name")
        self.profile_nickname_input.editingFinished.connect(self._save_profile_name_fields)
        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "Nickname",
                "Preferred name used by voice mode and extensions.",
                self.icon_font,
                self.ui_font,
                self.profile_nickname_input,
            )
        )

        section_row = QHBoxLayout()
        section_label = QLabel("Voice phrases by language")
        section_label.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        section_label.setStyleSheet("color: rgba(246,235,247,0.72);")

        add_btn = QPushButton(material_icon("add"))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedSize(32, 32)
        add_btn.setFont(QFont(self.icon_font, 16))
        add_btn.setProperty("iconButton", True)
        add_btn.clicked.connect(self._add_profile_language_row)

        section_row.addWidget(section_label, 1)
        section_row.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(section_row)

        hint = QLabel(
            "Add rows with +. You can customize how TTS pronounces your name and templates like new-email interruptions."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: rgba(246,235,247,0.62);")
        hint.setFont(QFont(self.ui_font, 9))
        layout.addWidget(hint)

        list_wrap = QWidget()
        self.profile_languages_layout = QVBoxLayout(list_wrap)
        self.profile_languages_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_languages_layout.setSpacing(10)
        layout.addWidget(list_wrap)
        self._refresh_profile_language_rows()

        return card


    def _set_rss_status_message(self, message: str) -> None:
        if hasattr(self, "rss_status"):
            self.rss_status.setText(message)


    def _queue_game_mode_summary_refresh(self) -> None:
        worker = getattr(self, "_gamemode_summary_worker", None)
        if isinstance(worker, GameModeSummaryWorker) and worker.isRunning():
            return
        self._gamemode_summary_worker = GameModeSummaryWorker()
        self._gamemode_summary_worker.finished_summary.connect(
            self._apply_game_mode_summary
        )
        self._gamemode_summary_worker.finished.connect(
            self._gamemode_summary_worker.deleteLater
        )
        self._gamemode_summary_worker.start()


    def _apply_game_mode_summary(self, payload: object) -> None:
        current = payload if isinstance(payload, dict) else {}
        available = bool(current.get("available", False))
        availability = (
            "gamemoded detected and ready."
            if available
            else "gamemoded is not installed yet. Install the gamemode package to use this widget."
        )
        note = str(current.get("note", "Game Mode is idle."))
        if hasattr(self, "game_mode_availability"):
            self.game_mode_availability.setText(availability)
        if hasattr(self, "game_mode_status"):
            self.game_mode_status.setText(note)
        self._gamemode_summary_worker = None


    def _save_virtualization_settings(self) -> None:
        service = self.settings_state["services"].setdefault("virtualization", {})
        ide_actions = service.setdefault("ide_actions", {})
        if not isinstance(ide_actions, dict):
            ide_actions = {}
            service["ide_actions"] = ide_actions
        service["virtualbox_manager_to_next_workspace"] = bool(
            self.virtualbox_manager_switch.isChecked()
        )
        service["virtualbox_guest_keep_current_workspace"] = bool(
            self.virtualbox_guest_current_ws_switch.isChecked()
        )
        service["virtualbox_guest_fullscreen"] = bool(
            self.virtualbox_guest_fullscreen_switch.isChecked()
        )
        service["emulator_prompt_once_per_ide"] = bool(
            self.virtualization_prompt_once_switch.isChecked()
        )
        service["emulator_move_target"] = str(
            self.virtualization_move_target_combo.currentData() or "next_on_output"
        )
        ide_actions["vscode"] = str(
            self.virtualization_ide_vscode_combo.currentData() or "ask"
        )
        ide_actions["vscodium"] = str(
            self.virtualization_ide_vscodium_combo.currentData() or "ask"
        )
        ide_actions["android_studio"] = str(
            self.virtualization_ide_android_studio_combo.currentData() or "ask"
        )
        ide_actions["jetbrains"] = str(
            self.virtualization_ide_jetbrains_combo.currentData() or "ask"
        )
        save_settings_state(self.settings_state)
        if self._service_enabled("virtualization"):
            self._start_virtualization_daemon()
        if hasattr(self, "virtualization_status"):
            self.virtualization_status.setText("Virtualization settings saved.")


    def _reset_virtualization_ide_choices(self) -> None:
        for combo in (
            getattr(self, "virtualization_ide_vscode_combo", None),
            getattr(self, "virtualization_ide_vscodium_combo", None),
            getattr(self, "virtualization_ide_android_studio_combo", None),
            getattr(self, "virtualization_ide_jetbrains_combo", None),
        ):
            if isinstance(combo, QComboBox):
                index = combo.findData("ask")
                combo.setCurrentIndex(index if index >= 0 else 0)
        self._save_virtualization_settings()
        if hasattr(self, "virtualization_status"):
            self.virtualization_status.setText(
                "IDE virtualization choices reset to ask-on-launch."
            )


    def _ntfy_auth_mode(self) -> str:
        if not hasattr(self, "ntfy_auth_mode_combo"):
            return "token"
        raw = self.ntfy_auth_mode_combo.currentData() or "token"
        has_token = (
            bool(str(getattr(self, "ntfy_token_input", QLineEdit()).text()).strip())
            if hasattr(self, "ntfy_token_input")
            else False
        )
        return normalize_ntfy_auth_mode(raw, has_token=has_token)


    def _sync_ntfy_auth_inputs(self) -> None:
        mode = self._ntfy_auth_mode()
        if hasattr(self, "ntfy_token_row"):
            self.ntfy_token_row.setVisible(mode == "token")
            self.ntfy_token_input.setEnabled(mode == "token")
        if hasattr(self, "ntfy_username_row"):
            self.ntfy_username_row.setVisible(mode == "basic")
            self.ntfy_username_input.setEnabled(mode == "basic")
        if hasattr(self, "ntfy_password_row"):
            self.ntfy_password_row.setVisible(mode == "basic")
            self.ntfy_password_input.setEnabled(mode == "basic")


    def _populate_ntfy_topic_list(self, topics: list[str]) -> None:
        normalized: list[str] = []
        seen: set[str] = set()
        for topic in topics:
            text = str(topic).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        for topic in self.ntfy_selected_topics:
            if topic and topic not in seen:
                seen.add(topic)
                normalized.append(topic)
        normalized.sort()
        self.ntfy_available_topics = normalized
        self.ntfy_topics_model.setStringList(normalized)
        if not hasattr(self, "ntfy_topic_list"):
            return
        self.ntfy_topic_list.blockSignals(True)
        self.ntfy_topic_list.clear()
        for topic in normalized:
            item = QListWidgetItem(topic)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = (
                Qt.CheckState.Checked
                if topic in self.ntfy_selected_topics
                else Qt.CheckState.Unchecked
            )
            item.setCheckState(state)
            self.ntfy_topic_list.addItem(item)
        self.ntfy_topic_list.blockSignals(False)
        self._update_ntfy_selected_topics_label()


    def _update_ntfy_selected_topics(self, item: QListWidgetItem | None = None) -> None:
        if not hasattr(self, "ntfy_topic_list"):
            return
        selected: list[str] = []
        for index in range(self.ntfy_topic_list.count()):
            entry = self.ntfy_topic_list.item(index)
            if entry.checkState() == Qt.CheckState.Checked:
                selected.append(str(entry.text()))
        self.ntfy_selected_topics = selected
        self._update_ntfy_selected_topics_label()


    def _update_ntfy_selected_topics_label(self) -> None:
        if not hasattr(self, "ntfy_selected_topics_label"):
            return
        if (
            getattr(self, "ntfy_all_topics_checkbox", None)
            and self.ntfy_all_topics_checkbox.isChecked()
        ):
            text = "Receiving notifications from all topics."
        elif not self.ntfy_selected_topics:
            text = "No topics selected yet."
        else:
            text = "Selected topics: " + ", ".join(self.ntfy_selected_topics)
        self.ntfy_selected_topics_label.setText(text)


    def _filter_ntfy_topics(self, text: str) -> None:
        if not hasattr(self, "ntfy_topic_list"):
            return
        query = str(text).strip().lower()
        for index in range(self.ntfy_topic_list.count()):
            item = self.ntfy_topic_list.item(index)
            if not item:
                continue
            item.setHidden(bool(query) and query not in item.text().lower())


    def _add_ntfy_topic(self, topic: str) -> None:
        value = str(topic).strip()
        if not value:
            return
        if value not in self.ntfy_selected_topics:
            self.ntfy_selected_topics.append(value)
        if value not in self.ntfy_available_topics:
            self.ntfy_available_topics.append(value)
        self._populate_ntfy_topic_list(self.ntfy_available_topics)


    def _add_ntfy_topic_from_entry(self) -> None:
        if not hasattr(self, "ntfy_topic_entry_input"):
            return
        text = self.ntfy_topic_entry_input.text().strip()
        if not text:
            return
        self._add_ntfy_topic(text)
        self.ntfy_topic_entry_input.clear()


    def _sync_ntfy_topic_controls(self) -> None:
        all_topics = bool(
            getattr(self, "ntfy_all_topics_checkbox", None)
            and self.ntfy_all_topics_checkbox.isChecked()
        )
        for widget in (
            getattr(self, "ntfy_topic_entry_input", None),
            getattr(self, "ntfy_topic_filter_input", None),
            getattr(self, "ntfy_refresh_topics_button", None),
            getattr(self, "ntfy_topic_list", None),
        ):
            if widget is not None:
                widget.setEnabled(not all_topics)
        self._update_ntfy_selected_topics_label()


    def _fetch_ntfy_topics(self) -> None:
        server = str(self.ntfy_server_input.text()).strip().rstrip("/")
        if not server:
            if hasattr(self, "ntfy_status"):
                self.ntfy_status.setText("Server URL is required to fetch topics.")
            return
        url = f"{server}/topics"
        headers: dict[str, str] = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": NTFY_USER_AGENT,
        }
        if self._ntfy_auth_mode() == "token":
            token = self.ntfy_token_input.text().strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        else:
            username = self.ntfy_username_input.text().strip()
            password = self.ntfy_password_input.text()
            if username or password:
                credentials = f"{username}:{password}"
                encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
                headers["Authorization"] = f"Basic {encoded}"
        try:
            req = request.Request(url, headers=headers, method="GET")
            with request.urlopen(req, timeout=8) as response:
                payload_text = response.read().decode("utf-8", errors="ignore")
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                detail = ""
            if hasattr(self, "ntfy_status"):
                self.ntfy_status.setText(
                    detail or f"HTTP {exc.code} while fetching topics."
                )
            return
        except Exception as exc:
            if hasattr(self, "ntfy_status"):
                self.ntfy_status.setText(str(exc))
            return
        parsed: list[str] = []
        try:
            payload = json.loads(payload_text)
            if isinstance(payload, dict):
                parsed = [
                    str(item).strip()
                    for item in payload.get("topics", [])
                    if isinstance(item, str)
                ]
            elif isinstance(payload, list):
                parsed = [
                    str(item).strip() for item in payload if isinstance(item, str)
                ]
        except Exception:
            parsed = [
                line.strip() for line in payload_text.splitlines() if line.strip()
            ]
        parsed = [item for item in parsed if item]
        if parsed:
            self._populate_ntfy_topic_list(parsed)
        if hasattr(self, "ntfy_status"):
            self.ntfy_status.setText(f"Fetched {len(parsed)} topic(s).")


    def _resolve_ntfy_test_topic(self) -> str:
        if (
            getattr(self, "ntfy_all_topics_checkbox", None)
            and self.ntfy_all_topics_checkbox.isChecked()
        ):
            return ""
        if self.ntfy_selected_topics:
            return self.ntfy_selected_topics[0]
        return str(self.settings_state["ntfy"].get("topic", "")).strip()


    def _set_cap_alerts_test_mode(self, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault("cap_alerts", {})
        if not service.get("enabled", True) and enabled:
            return
        service["test_mode"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "cap_alerts_status"):
            if enabled:
                self.cap_alerts_status.setText(
                    "Demo alert chip is enabled. Hanauta will show sample alerts from random countries for testing, without using your real location."
                )
            else:
                self.cap_alerts_status.setText(
                    "Uses your saved shared location for live alerts. If you use a VPN, save your real region here so weather and alerts stay accurate. Hanauta does not send telemetry or your location anywhere."
                )


    def _open_study_tracker_app(self) -> None:
        study_tracker_script = resolve_study_tracker_app()
        if study_tracker_script is None:
            if hasattr(self, "study_tracker_status"):
                self.study_tracker_status.setText("Study Tracker app is unavailable.")
            return
        command = entry_command(study_tracker_script)
        if not command:
            if hasattr(self, "study_tracker_status"):
                self.study_tracker_status.setText(
                    "Study Tracker launch command is unavailable."
                )
            return
        run_bg(command)
        if hasattr(self, "study_tracker_status"):
            self.study_tracker_status.setText("Study Tracker launched.")


    def _start_virtualization_daemon(self) -> None:
        daemon_script = resolve_virtualization_daemon()
        if daemon_script is None:
            if hasattr(self, "virtualization_status"):
                self.virtualization_status.setText(
                    "Virtualization daemon script is missing."
                )
            return
        for pattern in entry_patterns(daemon_script):
            subprocess.run(
                ["pkill", "-f", pattern], capture_output=True, text=True, check=False
            )
        command = entry_command(daemon_script)
        if not command:
            if hasattr(self, "virtualization_status"):
                self.virtualization_status.setText(
                    "Virtualization daemon launch command is unavailable."
                )
            return
        run_bg(command)
        if hasattr(self, "virtualization_status"):
            self.virtualization_status.setText("Virtualization daemon started.")


    def _stop_virtualization_daemon(self) -> None:
        daemon_script = resolve_virtualization_daemon()
        if daemon_script is None:
            return
        for pattern in entry_patterns(daemon_script):
            subprocess.run(
                ["pkill", "-f", pattern], capture_output=True, text=True, check=False
            )
        if hasattr(self, "virtualization_status"):
            self.virtualization_status.setText("Virtualization daemon stopped.")


    def _set_christian_service_flag(self, flag: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault("christian_widget", {})
        if not service.get("enabled", True):
            return
        service[flag] = bool(enabled)
        save_settings_state(self.settings_state)


    def _set_health_provider(self, index: int) -> None:
        provider = "fitbit" if index == 1 else "manual"
        self.settings_state.setdefault("health", {})["provider"] = provider
        self._sync_health_inputs()
        save_settings_state(self.settings_state)


    def _sync_health_inputs(self) -> None:
        provider = (
            str(self.settings_state.get("health", {}).get("provider", "manual"))
            .strip()
            .lower()
        )
        fitbit_mode = provider == "fitbit"
        for widget in (
            getattr(self, "health_fitbit_client_id_input", None),
            getattr(self, "health_fitbit_client_secret_input", None),
            getattr(self, "health_fitbit_access_token_input", None),
            getattr(self, "health_fitbit_refresh_token_input", None),
            getattr(self, "health_sync_interval_input", None),
        ):
            if widget is not None:
                widget.setEnabled(fitbit_mode)
        if hasattr(self, "health_status_label"):
            self.health_status_label.setText(
                "Fitbit mode is active. Save your tokens here and the widget will reuse cached data between syncs."
                if fitbit_mode
                else "Manual mode is active. Use the widget buttons to track steps, water, active minutes, and calories yourself."
            )


    def _save_health_settings(self) -> None:
        health = self.settings_state.setdefault("health", {})
        health["provider"] = (
            "fitbit" if self.health_provider_combo.currentIndex() == 1 else "manual"
        )
        try:
            health["step_goal"] = max(
                1000,
                min(50000, int(self.health_step_goal_input.text().strip() or "10000")),
            )
        except Exception:
            health["step_goal"] = 10000
            self.health_step_goal_input.setText("10000")
        try:
            health["water_goal_ml"] = max(
                250,
                min(6000, int(self.health_water_goal_input.text().strip() or "2000")),
            )
        except Exception:
            health["water_goal_ml"] = 2000
            self.health_water_goal_input.setText("2000")
        try:
            health["sync_interval_minutes"] = max(
                5, min(360, int(self.health_sync_interval_input.text().strip() or "30"))
            )
        except Exception:
            health["sync_interval_minutes"] = 30
            self.health_sync_interval_input.setText("30")
        health["fitbit_client_id"] = self.health_fitbit_client_id_input.text().strip()
        health["fitbit_client_secret"] = (
            self.health_fitbit_client_secret_input.text().strip()
        )
        health["fitbit_access_token"] = (
            self.health_fitbit_access_token_input.text().strip()
        )
        health["fitbit_refresh_token"] = (
            self.health_fitbit_refresh_token_input.text().strip()
        )
        save_settings_state(self.settings_state)
        self._sync_health_inputs()
        if health["provider"] == "fitbit":
            self.health_status_label.setText(
                "Fitbit settings saved. If your access token expires, Hanauta can refresh it when client id, client secret, and refresh token are present."
            )
        else:
            self.health_status_label.setText(
                "Manual health settings saved. Open the bar widget to log progress."
            )


    def _set_health_service_flag(self, flag: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault("health_widget", {})
        if not service.get("enabled", True):
            return
        service[flag] = bool(enabled)
        save_settings_state(self.settings_state)


    def _set_vpn_service_flag(self, flag: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault("vpn_control", {})
        if not service.get("enabled", True):
            return
        service[flag] = bool(enabled)
        save_settings_state(self.settings_state)


    def _set_kdeconnect_low_battery_fullscreen_notification(
        self, enabled: bool
    ) -> None:
        service = self.settings_state["services"].setdefault("kdeconnect", {})
        if not service.get("enabled", True) and enabled:
            return
        service["low_battery_fullscreen_notification"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "kdeconnect_rules_status"):
            threshold = int(service.get("low_battery_threshold", 20))
            self.kdeconnect_rules_status.setText(
                f"Fullscreen low-battery alerts are enabled at {threshold}% for KDE Connect."
                if enabled
                else "KDE Connect low-battery fullscreen alerts are disabled."
            )


    def _set_kdeconnect_low_battery_threshold(self, value: int) -> None:
        threshold = max(1, min(100, int(value)))
        service = self.settings_state["services"].setdefault("kdeconnect", {})
        service["low_battery_threshold"] = threshold
        save_settings_state(self.settings_state)
        if hasattr(self, "kdeconnect_battery_threshold_label"):
            self.kdeconnect_battery_threshold_label.setText(f"{threshold}%")
        if hasattr(self, "kdeconnect_rules_status") and bool(
            service.get("low_battery_fullscreen_notification", False)
        ):
            self.kdeconnect_rules_status.setText(
                f"Fullscreen low-battery alerts are enabled at {threshold}% for KDE Connect."
            )


    def _set_disk_space_min_free_gb(self, value: int) -> None:
        threshold = max(1, min(1024, int(value)))
        service = self.settings_state["services"].setdefault("disk_space", {})
        service["min_free_gb"] = threshold
        save_settings_state(self.settings_state)
        if hasattr(self, "disk_space_min_free_label"):
            self.disk_space_min_free_label.setText(f"{min(1024, threshold)} GB")
        if hasattr(self, "disk_space_status"):
            self.disk_space_status.setText(
                f"Fullscreen alerts enabled at ≤ {threshold} GB free (cooldown ~30 min)."
            )


    def _set_calendar_show_week_numbers(self, enabled: bool) -> None:
        self.settings_state.setdefault("calendar", {})["show_week_numbers"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText("Calendar week numbers updated.")


    def _set_calendar_show_other_month_days(self, enabled: bool) -> None:
        self.settings_state.setdefault("calendar", {})["show_other_month_days"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText("Calendar adjacent-month visibility updated.")


    def _set_calendar_first_day(self, index: int) -> None:
        value = (
            self.calendar_first_day_combo.itemData(index)
            if hasattr(self, "calendar_first_day_combo")
            else "monday"
        )
        self.settings_state.setdefault("calendar", {})["first_day_of_week"] = str(
            value or "monday"
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText("Calendar first day updated.")

    def _set_calendar_background_sync_interval(self, index: int) -> None:
        value = (
            self.calendar_background_sync_combo.itemData(index)
            if hasattr(self, "calendar_background_sync_combo")
            else 5
        )
        self.settings_state.setdefault("calendar", {})["background_sync_interval_minutes"] = int(
            value or 5
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText("Calendar background sync interval updated.")


    def _calendar_accounts(self) -> list[dict[str, object]]:
        calendar = self.settings_state.setdefault("calendar", {})
        accounts = calendar.get("calendars", [])
        if not isinstance(accounts, list):
            accounts = []
            calendar["calendars"] = accounts
        return [row for row in accounts if isinstance(row, dict)]


    def _contact_accounts(self) -> list[dict[str, object]]:
        calendar = self.settings_state.setdefault("calendar", {})
        accounts = calendar.get("contacts", [])
        if not isinstance(accounts, list):
            accounts = []
            calendar["contacts"] = accounts
        return [row for row in accounts if isinstance(row, dict)]


    def _selected_calendar_account(self) -> dict[str, object] | None:
        calendar = self.settings_state.setdefault("calendar", {})
        selected_id = str(calendar.get("selected_calendar_id", "")).strip()
        accounts = self._calendar_accounts()
        if selected_id:
            for row in accounts:
                if str(row.get("id", "")).strip() == selected_id:
                    return row
        return accounts[0] if accounts else None


    def _selected_contact_account(self) -> dict[str, object] | None:
        calendar = self.settings_state.setdefault("calendar", {})
        selected_id = str(calendar.get("selected_contact_id", "")).strip()
        accounts = self._contact_accounts()
        if selected_id:
            for row in accounts:
                if str(row.get("id", "")).strip() == selected_id:
                    return row
        return accounts[0] if accounts else None


    def _new_account_id(self, prefix: str) -> str:
        suffix = int(time.time() * 1000) ^ random.randint(1000, 9999)
        return f"{prefix}-{suffix:x}"


    def _refresh_calendar_account_picker(self) -> None:
        if not hasattr(self, "calendar_account_combo"):
            return
        combo: QComboBox = self.calendar_account_combo
        combo.blockSignals(True)
        combo.clear()
        accounts = self._calendar_accounts()
        for row in accounts:
            account_id = str(row.get("id", "")).strip()
            if not account_id:
                continue
            label = str(row.get("label", "")).strip() or "Calendar"
            combo.addItem(label, account_id)
        combo.addItem("New calendar…", "__new__")
        calendar = self.settings_state.setdefault("calendar", {})
        selected_id = str(calendar.get("selected_calendar_id", "")).strip()
        if selected_id:
            idx = combo.findData(selected_id)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            combo.setCurrentIndex(0 if combo.count() else -1)
        combo.blockSignals(False)


    def _refresh_contact_account_picker(self) -> None:
        if not hasattr(self, "contacts_account_combo"):
            return
        combo: QComboBox = self.contacts_account_combo
        combo.blockSignals(True)
        combo.clear()
        accounts = self._contact_accounts()
        for row in accounts:
            account_id = str(row.get("id", "")).strip()
            if not account_id:
                continue
            label = str(row.get("label", "")).strip() or "Contacts"
            combo.addItem(label, account_id)
        combo.addItem("New CardDAV…", "__new__")
        calendar = self.settings_state.setdefault("calendar", {})
        selected_id = str(calendar.get("selected_contact_id", "")).strip()
        if selected_id:
            idx = combo.findData(selected_id)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            combo.setCurrentIndex(0 if combo.count() else -1)
        combo.blockSignals(False)


    def _load_selected_calendar_account(self, index: int) -> None:
        if not hasattr(self, "calendar_account_combo"):
            return
        account_id = str(self.calendar_account_combo.itemData(index) or "").strip()
        if account_id == "__new__":
            self._add_calendar_account()
            return
        calendar = self.settings_state.setdefault("calendar", {})
        calendar["selected_calendar_id"] = account_id
        save_settings_state(self.settings_state)
        row = self._selected_calendar_account()
        if row is None:
            return
        if hasattr(self, "calendar_account_enabled_switch"):
            self.calendar_account_enabled_switch.setChecked(bool(row.get("enabled", True)))
        if hasattr(self, "calendar_url_input"):
            self.calendar_url_input.setText(str(row.get("caldav_url", "")).strip())
        if hasattr(self, "calendar_user_input"):
            self.calendar_user_input.setText(str(row.get("caldav_username", "")).strip())
        if hasattr(self, "calendar_password_input"):
            self.calendar_password_input.setText(str(row.get("caldav_password", "")))
        if hasattr(self, "calendar_status"):
            status = str(row.get("last_sync_status", "")).strip()
            self.calendar_status.setText(status or "Calendar integration is idle.")


    def _load_selected_contact_account(self, index: int) -> None:
        if not hasattr(self, "contacts_account_combo"):
            return
        account_id = str(self.contacts_account_combo.itemData(index) or "").strip()
        if account_id == "__new__":
            self._add_contact_account()
            return
        calendar = self.settings_state.setdefault("calendar", {})
        calendar["selected_contact_id"] = account_id
        save_settings_state(self.settings_state)
        row = self._selected_contact_account()
        if row is None:
            return
        if hasattr(self, "contacts_account_enabled_switch"):
            self.contacts_account_enabled_switch.setChecked(bool(row.get("enabled", True)))
        if hasattr(self, "contacts_url_input"):
            self.contacts_url_input.setText(str(row.get("carddav_url", "")).strip())
        if hasattr(self, "contacts_user_input"):
            self.contacts_user_input.setText(str(row.get("carddav_username", "")).strip())
        if hasattr(self, "contacts_password_input"):
            self.contacts_password_input.setText(str(row.get("carddav_password", "")))
        if hasattr(self, "contacts_status"):
            status = str(row.get("last_sync_status", "")).strip()
            self.contacts_status.setText(
                status
                or "CardDAV credentials are stored. Contact syncing will be enabled by future widgets."
            )


    def _set_selected_calendar_account_enabled(self, enabled: bool) -> None:
        row = self._selected_calendar_account()
        if row is None:
            return
        row["enabled"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText(
                "Calendar enabled." if enabled else "Calendar disabled."
            )


    def _set_selected_contact_account_enabled(self, enabled: bool) -> None:
        row = self._selected_contact_account()
        if row is None:
            return
        row["enabled"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "contacts_status"):
            self.contacts_status.setText(
                "Contacts enabled." if enabled else "Contacts disabled."
            )


    def _add_calendar_account(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Calendar (CalDAV)")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        label_input = QLineEdit()
        label_input.setPlaceholderText("Work, Personal, Family…")
        url_input = QLineEdit()
        url_input.setPlaceholderText("https://dav.example.com/caldav/")
        user_input = QLineEdit()
        user_input.setPlaceholderText("username")
        pass_input = QLineEdit()
        pass_input.setPlaceholderText("Password or app password")
        pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addWidget(QLabel("Label"))
        layout.addWidget(label_input)
        layout.addWidget(QLabel("CalDAV URL"))
        layout.addWidget(url_input)
        layout.addWidget(QLabel("Username"))
        layout.addWidget(user_input)
        layout.addWidget(QLabel("Password"))
        layout.addWidget(pass_input)

        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(dialog.reject)
        add_btn = QPushButton("Add")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(dialog.accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(add_btn)
        layout.addLayout(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._refresh_calendar_account_picker()
            return
        account_id = self._new_account_id("caldav")
        label = label_input.text().strip() or "Calendar"
        account = {
            "id": account_id,
            "label": label,
            "enabled": True,
            "caldav_url": url_input.text().strip(),
            "caldav_username": user_input.text().strip(),
            "caldav_password": pass_input.text(),
            "connected": False,
            "last_sync_status": "",
        }
        calendar = self.settings_state.setdefault("calendar", {})
        calendar.setdefault("calendars", [])
        if isinstance(calendar["calendars"], list):
            calendar["calendars"].append(account)
        calendar["selected_calendar_id"] = account_id
        save_settings_state(self.settings_state)
        self._refresh_calendar_account_picker()
        self._load_selected_calendar_account(self.calendar_account_combo.currentIndex())


    def _remove_selected_calendar_account(self) -> None:
        row = self._selected_calendar_account()
        if row is None:
            return
        label = str(row.get("label", "Calendar")).strip() or "Calendar"
        reply = QMessageBox.question(
            self,
            "Remove calendar",
            f"Remove '{label}'? Credentials will be deleted from settings.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        calendar = self.settings_state.setdefault("calendar", {})
        accounts = calendar.get("calendars", [])
        if isinstance(accounts, list):
            accounts[:] = [
                item
                for item in accounts
                if not (
                    isinstance(item, dict)
                    and str(item.get("id", "")).strip() == str(row.get("id", "")).strip()
                )
            ]
        calendar["selected_calendar_id"] = ""
        save_settings_state(self.settings_state)
        self._refresh_calendar_account_picker()
        self._load_selected_calendar_account(self.calendar_account_combo.currentIndex())


    def _add_contact_account(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Contacts (CardDAV)")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        label_input = QLineEdit()
        label_input.setPlaceholderText("Work, Personal…")
        url_input = QLineEdit()
        url_input.setPlaceholderText("https://dav.example.com/carddav/")
        user_input = QLineEdit()
        user_input.setPlaceholderText("username")
        pass_input = QLineEdit()
        pass_input.setPlaceholderText("Password or app password")
        pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addWidget(QLabel("Label"))
        layout.addWidget(label_input)
        layout.addWidget(QLabel("CardDAV URL"))
        layout.addWidget(url_input)
        layout.addWidget(QLabel("Username"))
        layout.addWidget(user_input)
        layout.addWidget(QLabel("Password"))
        layout.addWidget(pass_input)

        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(dialog.reject)
        add_btn = QPushButton("Add")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(dialog.accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(add_btn)
        layout.addLayout(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._refresh_contact_account_picker()
            return
        account_id = self._new_account_id("carddav")
        label = label_input.text().strip() or "Contacts"
        account = {
            "id": account_id,
            "label": label,
            "enabled": True,
            "carddav_url": url_input.text().strip(),
            "carddav_username": user_input.text().strip(),
            "carddav_password": pass_input.text(),
            "connected": False,
            "last_sync_status": "",
        }
        calendar = self.settings_state.setdefault("calendar", {})
        calendar.setdefault("contacts", [])
        if isinstance(calendar["contacts"], list):
            calendar["contacts"].append(account)
        calendar["selected_contact_id"] = account_id
        save_settings_state(self.settings_state)
        self._refresh_contact_account_picker()
        self._load_selected_contact_account(self.contacts_account_combo.currentIndex())


    def _remove_selected_contact_account(self) -> None:
        row = self._selected_contact_account()
        if row is None:
            return
        label = str(row.get("label", "Contacts")).strip() or "Contacts"
        reply = QMessageBox.question(
            self,
            "Remove contacts",
            f"Remove '{label}'? Credentials will be deleted from settings.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        calendar = self.settings_state.setdefault("calendar", {})
        accounts = calendar.get("contacts", [])
        if isinstance(accounts, list):
            accounts[:] = [
                item
                for item in accounts
                if not (
                    isinstance(item, dict)
                    and str(item.get("id", "")).strip() == str(row.get("id", "")).strip()
                )
            ]
        calendar["selected_contact_id"] = ""
        save_settings_state(self.settings_state)
        self._refresh_contact_account_picker()
        self._load_selected_contact_account(self.contacts_account_combo.currentIndex())


    def _save_calendar_settings(self) -> None:
        calendar = self.settings_state.setdefault("calendar", {})
        row = self._selected_calendar_account()
        if row is None:
            account_id = "primary"
            row = {
                "id": account_id,
                "label": "Primary",
                "enabled": True,
                "caldav_url": "",
                "caldav_username": "",
                "caldav_password": "",
                "connected": False,
                "last_sync_status": "",
            }
            calendar.setdefault("calendars", [])
            if isinstance(calendar["calendars"], list):
                calendar["calendars"].append(row)
            calendar["selected_calendar_id"] = account_id
            self._refresh_calendar_account_picker()
        caldav_url = self.calendar_url_input.text().strip()
        if caldav_url and not caldav_url.endswith("/"):
            caldav_url += "/"
        row["caldav_url"] = caldav_url
        row["caldav_username"] = self.calendar_user_input.text().strip()
        row["caldav_password"] = self.calendar_password_input.text()
        calendar["caldav_url"] = str(row.get("caldav_url", "")).strip()
        calendar["caldav_username"] = str(row.get("caldav_username", "")).strip()
        calendar["caldav_password"] = str(row.get("caldav_password", ""))
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            label = str(row.get("label", "Calendar")).strip() or "Calendar"
            self.calendar_status.setText(f"Calendar credentials saved for {label}.")


    def _save_contact_settings(self) -> None:
        calendar = self.settings_state.setdefault("calendar", {})
        row = self._selected_contact_account()
        if row is None:
            account_id = "primary"
            row = {
                "id": account_id,
                "label": "Primary",
                "enabled": True,
                "carddav_url": "",
                "carddav_username": "",
                "carddav_password": "",
                "connected": False,
                "last_sync_status": "",
            }
            calendar.setdefault("contacts", [])
            if isinstance(calendar["contacts"], list):
                calendar["contacts"].append(row)
            calendar["selected_contact_id"] = account_id
            self._refresh_contact_account_picker()
        carddav_url = self.contacts_url_input.text().strip()
        if carddav_url and not carddav_url.endswith("/"):
            carddav_url += "/"
        row["carddav_url"] = carddav_url
        row["carddav_username"] = self.contacts_user_input.text().strip()
        row["carddav_password"] = self.contacts_password_input.text()
        save_settings_state(self.settings_state)
        if hasattr(self, "contacts_status"):
            label = str(row.get("label", "Contacts")).strip() or "Contacts"
            self.contacts_status.setText(f"CardDAV credentials saved for {label}.")


    def _discover_calendar_calendars(self) -> None:
        self._save_calendar_settings()
        calendar = self.settings_state.setdefault("calendar", {})
        row = self._selected_calendar_account() or {}
        url = str(row.get("caldav_url", "")).strip() or str(
            calendar.get("caldav_url", "")
        ).strip()
        username = str(row.get("caldav_username", "")).strip() or str(
            calendar.get("caldav_username", "")
        ).strip()
        password = str(row.get("caldav_password", "")) or str(
            calendar.get("caldav_password", "")
        )
        if not url or not username or not password:
            self.calendar_status.setText(
                "CalDAV URL, username, and password are required."
            )
            return
        qcal_wrapper = resolve_qcal_wrapper()
        if qcal_wrapper is None:
            self.calendar_status.setText("qcal wrapper is missing.")
            print("[qcal] qcal wrapper is missing -- discovery aborted", file=sys.stderr)
            return
        command = [python_executable(), str(qcal_wrapper), "discover", url, username, password]
        print(f"[qcal] running: {' '.join(command)}", file=sys.stderr)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"[qcal] returncode={result.returncode} stdout={result.stdout[:200] if result.stdout else ''} stderr={result.stderr[:200] if result.stderr else ''}", file=sys.stderr)
        try:
            payload = json.loads(result.stdout or "{}")
        except Exception:
            payload = {
                "success": False,
                "error": (result.stderr or "CalDAV discovery failed.").strip(),
            }
        success = bool(payload.get("success", False))
        if isinstance(row, dict):
            row["connected"] = success
        calendar["connected"] = success
        discovered_raw = payload.get("calendars", [])
        discovered_urls: list[dict[str, str]] = []
        names: list[str] = []
        if isinstance(discovered_raw, list):
            for item in discovered_raw:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip() or "Calendar"
                    url = str(item.get("url", "")).strip()
                    if not url:
                        continue
                    discovered_urls.append({"name": name, "url": url})
                    names.append(name)
                elif isinstance(item, str) and item.strip():
                    names.append(item.strip())
        if success:
            discovered_summary = ", ".join(str(name) for name in names[:3])
            suffix = "" if len(names) <= 3 else "..."
            status_text = (
                f"Connected to {len(names)} calendar(s): {discovered_summary}{suffix}"
            )
        else:
            status_text = str(
                payload.get("error", "Unable to discover calendars.")
            ).strip()
        if isinstance(row, dict):
            row["last_sync_status"] = status_text
            if discovered_urls:
                row["remote_calendars"] = discovered_urls
                calendar["selected_remote_calendar_url"] = str(
                    discovered_urls[0].get("url", "")
                )
        calendar["last_sync_status"] = status_text
        save_settings_state(self.settings_state)
        self.calendar_status.setText(
            calendar["last_sync_status"] or "Calendar integration updated."
        )


    def _set_reminder_default_intensity(self, index: int) -> None:
        value = (
            self.reminders_intensity_combo.itemData(index)
            if hasattr(self, "reminders_intensity_combo")
            else "discrete"
        )
        self.settings_state.setdefault("reminders", {})["default_intensity"] = str(
            value or "discrete"
        )
        save_settings_state(self.settings_state)
        self._refresh_reminders_status()


    def _set_reminder_default_lead_minutes(self, value: int) -> None:
        self.settings_state.setdefault("reminders", {})["default_lead_minutes"] = int(
            value
        )
        save_settings_state(self.settings_state)
        self._refresh_reminders_status()


    def _set_tea_default_minutes(self, value: int) -> None:
        self.settings_state.setdefault("reminders", {})["tea_minutes"] = int(value)
        save_settings_state(self.settings_state)
        self._refresh_reminders_status()


    def _set_pomodoro_work_minutes(self, value: int) -> None:
        self.settings_state.setdefault("pomodoro", {})["work_minutes"] = max(
            5, min(90, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(
                f"Work sessions set to {int(value)} minute(s)."
            )


    def _set_pomodoro_short_break_minutes(self, value: int) -> None:
        self.settings_state.setdefault("pomodoro", {})["short_break_minutes"] = max(
            1, min(30, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(f"Short breaks set to {int(value)} minute(s).")


    def _set_pomodoro_long_break_minutes(self, value: int) -> None:
        self.settings_state.setdefault("pomodoro", {})["long_break_minutes"] = max(
            5, min(60, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(f"Long breaks set to {int(value)} minute(s).")


    def _set_pomodoro_long_break_every(self, value: int) -> None:
        self.settings_state.setdefault("pomodoro", {})["long_break_every"] = max(
            2, min(8, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(
                f"Long break cadence set to every {int(value)} focus session(s)."
            )


    def _set_pomodoro_auto_start_breaks(self, enabled: bool) -> None:
        self.settings_state.setdefault("pomodoro", {})["auto_start_breaks"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(
                "Break timers will auto-start after work sessions."
                if enabled
                else "Break timers now wait for manual start."
            )


    def _set_pomodoro_auto_start_focus(self, enabled: bool) -> None:
        self.settings_state.setdefault("pomodoro", {})["auto_start_focus"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(
                "Focus sessions will auto-start after breaks."
                if enabled
                else "Focus sessions now wait for manual start."
            )


    def _set_rss_item_limit(self, value: int) -> None:
        self.settings_state.setdefault("rss", {})["item_limit"] = max(
            3, min(30, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "rss_status"):
            self.rss_status.setText(
                f"RSS item limit set to {int(value)} story entries."
            )


    def _set_rss_check_interval(self, value: int) -> None:
        self.settings_state.setdefault("rss", {})["check_interval_minutes"] = max(
            5, min(180, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "rss_status"):
            self.rss_status.setText(f"RSS checks now run every {int(value)} minute(s).")


    def _set_rss_notify_new_items(self, enabled: bool) -> None:
        self.settings_state.setdefault("rss", {})["notify_new_items"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "rss_status"):
            self.rss_status.setText(
                "RSS notifications are enabled."
                if enabled
                else "RSS notifications are paused."
            )


    def _save_rss_settings(self) -> None:
        save_settings_state(self.settings_state)
        if hasattr(self, "rss_status"):
            rss = self.settings_state.setdefault("rss", {})
            rss_mode = "structured feeds" if rss.get("feeds") else "manual feeds"
            if rss.get("opml_source"):
                rss_mode = "OPML sync"
            self.rss_status.setText(
                f"RSS sources saved for {rss_mode}. Notifications stay on a {int(rss.get('check_interval_minutes', 15) or 15)}-minute rhythm."
            )


    def _set_obs_auto_connect(self, enabled: bool) -> None:
        self.settings_state.setdefault("obs", {})["auto_connect"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "obs_status"):
            self.obs_status.setText(
                "OBS widget will connect immediately when opened."
                if enabled
                else "OBS widget now waits for a manual connect."
            )


    def _set_obs_debug_tooltips(self, enabled: bool) -> None:
        self.settings_state.setdefault("obs", {})["show_debug_tooltips"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "obs_status"):
            self.obs_status.setText(
                "OBS debug tooltips are enabled."
                if enabled
                else "OBS debug tooltips are disabled."
            )


    def _save_obs_settings(self) -> None:
        obs = self.settings_state.setdefault("obs", {})
        obs["host"] = self.obs_host_input.text().strip() or "127.0.0.1"
        try:
            obs["port"] = max(
                1, min(65535, int(self.obs_port_input.text().strip() or "4455"))
            )
        except Exception:
            obs["port"] = 4455
        obs["password"] = self.obs_password_input.text()
        obs["auto_connect"] = bool(self.obs_auto_connect_switch.isChecked())
        obs["show_debug_tooltips"] = bool(self.obs_debug_tooltips_switch.isChecked())
        save_settings_state(self.settings_state)
        if hasattr(self, "obs_status"):
            self.obs_status.setText(
                f"OBS connection saved for {obs['host']}:{obs['port']}."
            )


    def _set_crypto_check_interval(self, value: int) -> None:
        self.settings_state.setdefault("crypto", {})["check_interval_minutes"] = max(
            5, min(180, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(
                f"Crypto checks now run every {int(value)} minute(s)."
            )


    def _set_crypto_chart_days(self, value: int) -> None:
        self.settings_state.setdefault("crypto", {})["chart_days"] = max(
            1, min(90, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(
                f"Charts will open on the last {int(value)} day(s)."
            )


    def _set_crypto_notify_price_moves(self, enabled: bool) -> None:
        self.settings_state.setdefault("crypto", {})["notify_price_moves"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(
                "Crypto move notifications are enabled."
                if enabled
                else "Crypto move notifications are paused."
            )


    def _set_crypto_up_percent(self, value: int) -> None:
        self.settings_state.setdefault("crypto", {})["price_up_percent"] = float(
            max(1, min(20, int(value)))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(
                f"Up alerts will trigger at {int(value)}% or more."
            )


    def _set_crypto_down_percent(self, value: int) -> None:
        self.settings_state.setdefault("crypto", {})["price_down_percent"] = float(
            max(1, min(20, int(value)))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(
                f"Down alerts will trigger at {int(value)}% or more."
            )


    def _save_crypto_settings(self) -> None:
        crypto = self.settings_state.setdefault("crypto", {})
        crypto["api_provider"] = "coingecko"
        crypto["api_key"] = self.crypto_api_key_input.text().strip()
        crypto["tracked_coins"] = self.crypto_coins_input.text().strip()
        crypto["vs_currency"] = (
            self.crypto_currency_input.text().strip().lower() or "usd"
        )
        crypto["check_interval_minutes"] = int(self.crypto_interval_slider.value())
        crypto["chart_days"] = int(self.crypto_chart_days_slider.value())
        crypto["notify_price_moves"] = bool(self.crypto_alert_switch.isChecked())
        crypto["price_up_percent"] = float(int(self.crypto_up_slider.value()))
        crypto["price_down_percent"] = float(int(self.crypto_down_slider.value()))
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText("Crypto tracker settings saved for CoinGecko.")


    def _save_vps_settings(self) -> None:
        vps = self.settings_state.setdefault("vps", {})
        vps["host"] = self.vps_host_input.text().strip()
        try:
            vps["port"] = max(
                1, min(65535, int(self.vps_port_input.text().strip() or "22"))
            )
        except Exception:
            vps["port"] = 22
        vps["username"] = self.vps_username_input.text().strip()
        vps["identity_file"] = self.vps_identity_input.text().strip()
        vps["app_service"] = self.vps_service_input.text().strip()
        vps["health_command"] = (
            self.vps_health_input.text().strip() or "uptime && df -h /"
        )
        vps["update_command"] = (
            self.vps_update_input.text().strip()
            or "sudo apt update && sudo apt upgrade -y"
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "vps_status"):
            if vps["host"]:
                self.vps_status.setText(
                    f"VPS connection saved for {vps['username']}@{vps['host']}:{vps['port']}."
                )
            else:
                self.vps_status.setText(
                    "VPS settings saved. Add a host when you are ready."
                )


    def _set_clock_size(self, value: int) -> None:
        self.settings_state.setdefault("clock", {})["size"] = max(
            220, min(520, int(value))
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_status"):
            self.clock_status.setText(f"Desktop clock size set to {int(value)}px.")


    def _set_clock_show_seconds(self, enabled: bool) -> None:
        self.settings_state.setdefault("clock", {})["show_seconds"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_status"):
            self.clock_status.setText(
                "Seconds hand enabled." if enabled else "Seconds hand hidden."
            )


    def _set_clock_digital_line_spacing(self, value: int) -> None:
        clock = self.settings_state.setdefault("clock", {})
        clock["digital_line_spacing"] = max(8, min(64, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_status"):
            self.clock_status.setText(
                f"Digital line spacing set to {int(clock['digital_line_spacing'])}."
            )


    def _set_clock_position_x(self, value: int) -> None:
        clock = self.settings_state.setdefault("clock", {})
        clock["position_x"] = int(value)
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_status"):
            self.clock_status.setText(
                "Clock X position set to auto."
                if int(value) < 0
                else f"Clock X position set to {int(value)}px."
            )


    def _set_clock_position_y(self, value: int) -> None:
        clock = self.settings_state.setdefault("clock", {})
        clock["position_y"] = int(value)
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_status"):
            self.clock_status.setText(
                "Clock Y position set to auto."
                if int(value) < 0
                else f"Clock Y position set to {int(value)}px."
            )


    def _reset_clock_position(self) -> None:
        clock = self.settings_state.setdefault("clock", {})
        clock["position_x"] = -1
        clock["position_y"] = -1
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_position_x_spin"):
            self.clock_position_x_spin.blockSignals(True)
            self.clock_position_x_spin.setValue(-1)
            self.clock_position_x_spin.blockSignals(False)
        if hasattr(self, "clock_position_y_spin"):
            self.clock_position_y_spin.blockSignals(True)
            self.clock_position_y_spin.setValue(-1)
            self.clock_position_y_spin.blockSignals(False)
        if hasattr(self, "clock_status"):
            self.clock_status.setText("Desktop clock position reset.")


    def _desktop_clock_command(self) -> list[str]:
        desktop_clock_script = resolve_desktop_clock_widget()
        if desktop_clock_script is not None:
            return entry_command(desktop_clock_script)
        if DESKTOP_CLOCK_BINARY.exists():
            return [str(DESKTOP_CLOCK_BINARY)]
        return []


    def _launch_desktop_clock(self) -> None:
        command = self._desktop_clock_command()
        if not command:
            if hasattr(self, "clock_status"):
                self.clock_status.setText(
                    "No desktop clock executable was found. Build `hanauta/bin/hanauta-clock` or keep the PyQt fallback installed."
                )
            return
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            if hasattr(self, "clock_status"):
                self.clock_status.setText(
                    "Opened the native Qt clock."
                    if command[0] == str(DESKTOP_CLOCK_BINARY)
                    else "Opened the PyQt desktop clock fallback."
                )
        except Exception:
            if hasattr(self, "clock_status"):
                self.clock_status.setText("Desktop clock could not be launched.")


    def _save_reminders_settings(self) -> None:
        reminders = self.settings_state.setdefault("reminders", {})
        reminders["tea_label"] = self.tea_label_input.text().strip() or "Tea"
        reminders["default_intensity"] = str(
            self.reminders_intensity_combo.currentData() or "discrete"
        )
        reminders["default_lead_minutes"] = int(self.reminders_lead_slider.value())
        reminders["tea_minutes"] = int(self.tea_minutes_slider.value())
        save_settings_state(self.settings_state)
        self._refresh_reminders_status("Reminder defaults saved.")


    def _refresh_reminders_status(self, prefix: str = "") -> None:
        tracked_count = len(
            self.settings_state.get("reminders", {}).get("tracked_events", [])
        )
        detail = (
            f"{tracked_count} tracked reminder(s) • "
            f"{self.settings_state['reminders'].get('default_lead_minutes', 20)} min lead • "
            f"{self.settings_state['reminders'].get('default_intensity', 'discrete')}"
        )
        self.reminders_status.setText(f"{prefix} {detail}".strip())


    def _set_ntfy_enabled(self, enabled: bool) -> None:
        ntfy = self.settings_state.setdefault("ntfy", {})
        ntfy["enabled"] = bool(enabled)
        if not enabled:
            ntfy["show_in_bar"] = False
        save_settings_state(self.settings_state)
        if hasattr(self, "ntfy_bar_switch"):
            self.ntfy_bar_switch.setChecked(bool(ntfy.get("show_in_bar", False)))
            self.ntfy_bar_switch._apply_state()
        if hasattr(self, "_refresh_bar_service_icon_rows"):
            self._refresh_bar_service_icon_rows()
        if hasattr(self, "_refresh_service_widget_order"):
            self._refresh_service_widget_order()


    def _set_ntfy_show_in_bar(self, enabled: bool) -> None:
        ntfy = self.settings_state.setdefault("ntfy", {})
        if not ntfy.get("enabled", False):
            return
        ntfy["show_in_bar"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "ntfy_bar_switch"):
            target = bool(enabled)
            if bool(self.ntfy_bar_switch.isChecked()) != target:
                self.ntfy_bar_switch.setChecked(target)
                self.ntfy_bar_switch._apply_state()
        if hasattr(self, "_refresh_bar_service_icon_rows"):
            self._refresh_bar_service_icon_rows()


    def _set_ntfy_hide_notification_content(self, enabled: bool) -> None:
        self.settings_state.setdefault("ntfy", {})["hide_notification_content"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "ntfy_status"):
            self.ntfy_status.setText(
                "ntfy notifications will hide message content."
                if enabled
                else "ntfy notifications will show full message content."
            )


    def _set_weather_enabled(self, enabled: bool) -> None:
        weather = self.settings_state.setdefault("weather", {})
        weather["enabled"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "weather_status"):
            self.weather_status.setText(
                "Weather icon enabled on the bar."
                if enabled
                else "Weather icon disabled."
            )
        if hasattr(self, "_refresh_service_widget_order"):
            self._refresh_service_widget_order()


    def _set_weather_notify_climate_changes(self, enabled: bool) -> None:
        self._set_weather_notification_flag(
            "notify_climate_changes", enabled, "Climate change alerts"
        )


    def _set_weather_notify_rain_soon(self, enabled: bool) -> None:
        self._set_weather_notification_flag("notify_rain_soon", enabled, "Rain soon")


    def _set_weather_notify_sunset_soon(self, enabled: bool) -> None:
        self._set_weather_notification_flag(
            "notify_sunset_soon", enabled, "Sunset soon"
        )

    def _set_weather_language(self, index: int) -> None:
        value = (
            self.weather_language_combo.itemData(index)
            if hasattr(self, "weather_language_combo")
            else "en"
        )
        self.settings_state.setdefault("weather", {})["language"] = str(value or "en")
        save_settings_state(self.settings_state)
        if hasattr(self, "weather_status"):
            self.weather_status.setText("Weather language updated.")


    def _set_weather_notification_flag(
        self, key: str, enabled: bool, label: str = "Weather notifications"
    ) -> None:
        weather = self.settings_state.setdefault("weather", {})
        weather[str(key).strip()] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "weather_status"):
            self.weather_status.setText(
                f"{label} enabled." if enabled else f"{label} disabled."
            )


    def _queue_weather_city_search(self, text: str) -> None:
        self._selected_weather_city = None
        self._weather_search_query = text.strip()
        if len(text.strip()) < 2:
            if hasattr(self, "weather_city_model"):
                self.weather_city_model.setStringList([])
            if hasattr(self, "region_location_model"):
                self.region_location_model.setStringList([])
            return
        self._weather_search_timer.start(250)


    def _perform_weather_city_search(self) -> None:
        text = str(getattr(self, "_weather_search_query", "")).strip()
        if len(text) < 2:
            if hasattr(self, "weather_city_model"):
                self.weather_city_model.setStringList([])
            if hasattr(self, "region_location_model"):
                self.region_location_model.setStringList([])
            return
        matches = search_cities(text)
        self._weather_city_map = {city.label: city for city in matches}
        labels = list(self._weather_city_map.keys())
        if hasattr(self, "weather_city_model"):
            self.weather_city_model.setStringList(labels)
        if hasattr(self, "region_location_model"):
            self.region_location_model.setStringList(labels)
        if labels:
            if (
                hasattr(self, "weather_city_completer")
                and hasattr(self, "weather_city_input")
                and self.weather_city_input.hasFocus()
            ):
                self.weather_city_completer.complete()
            if (
                hasattr(self, "region_location_completer")
                and hasattr(self, "region_location_input")
                and self.region_location_input.hasFocus()
            ):
                self.region_location_completer.complete()


    def _select_weather_city(self, label: str) -> None:
        city = self._weather_city_map.get(label)
        if city is None:
            return
        self._selected_weather_city = city
        if hasattr(self, "weather_city_input"):
            self.weather_city_input.setText(label)
        if hasattr(self, "region_location_input"):
            self.region_location_input.setText(label)
        if hasattr(self, "weather_status"):
            self.weather_status.setText(f"Selected city: {label}")
        if hasattr(self, "region_status"):
            self.region_status.setText(f"Selected shared location: {label}")


    def _save_weather_settings(self) -> None:
        city = self._selected_weather_city
        current_text = (
            self.weather_city_input.text().strip()
            if hasattr(self, "weather_city_input")
            else ""
        )
        if city is None and current_text:
            city = self._weather_city_map.get(current_text)
        if city is None:
            if hasattr(self, "weather_status"):
                self.weather_status.setText(
                    "Pick a city from the autocomplete list first."
                )
            return
        weather = self.settings_state.setdefault("weather", {})
        weather.update(
            {
                "enabled": True,
                "name": city.name,
                "admin1": city.admin1,
                "country": city.country,
                "latitude": city.latitude,
                "longitude": city.longitude,
                "timezone": city.timezone,
            }
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "weather_section"):
            self.weather_section.set_enabled(True)
        if hasattr(self, "weather_status"):
            self.weather_status.setText(f"Weather city saved: {city.label}")
        if hasattr(self, "region_status"):
            self.region_status.setText(f"Shared location saved: {city.label}")

    def _save_weather_api_keys(self) -> None:
        weather = self.settings_state.setdefault("weather", {})
        if hasattr(self, "weather_owm_key_input"):
            weather["openweathermap_api_key"] = (
                self.weather_owm_key_input.text().strip()
            )
        save_settings_state(self.settings_state)
        if hasattr(self, "weather_status"):
            owm = str(weather.get("openweathermap_api_key", "")).strip()
            if owm:
                self.weather_status.setText(
                    "OpenWeatherMap API key saved. Weather will use OpenWeatherMap."
                )
            else:
                self.weather_status.setText(
                    "API key cleared. Weather will use free Open-Meteo (fallback: wttr.in)."
                )

    def _save_weather_poll_interval(self, value: int) -> None:
        weather = self.settings_state.setdefault("weather", {})
        weather["poll_interval_minutes"] = max(15, min(1440, int(value)))
        save_settings_state(self.settings_state)


    def _save_home_assistant_settings(self) -> None:
        self.settings_state["home_assistant"]["url"] = normalize_ha_url(
            self.ha_url_input.text()
        )
        self.settings_state["home_assistant"]["token"] = (
            self.ha_token_input.text().strip()
        )
        save_settings_state(self.settings_state)
        self.ha_status.setText("Home Assistant settings saved.")


    def _refresh_home_assistant_entities(self) -> None:
        payload, error_text = fetch_home_assistant_json(
            self.settings_state["home_assistant"].get("url", ""),
            self.settings_state["home_assistant"].get("token", ""),
            "/api/states",
        )
        if error_text or not isinstance(payload, list):
            self.ha_status.setText(error_text or "No entities available.")
            self._ha_entities = []
            self._ha_entity_map = {}
            self._rebuild_ha_entity_list()
            return
        self._ha_entities = sorted(
            [item for item in payload if isinstance(item, dict)],
            key=lambda item: str(item.get("entity_id", "")),
        )
        prefetch_entity_icons(self._ha_entities)
        self._ha_entity_map = {
            str(item.get("entity_id", "")): item for item in self._ha_entities
        }
        self.ha_status.setText(
            f"Fetched {len(self._ha_entities)} entities successfully."
        )
        self._rebuild_ha_entity_list()


    def _rebuild_ha_entity_list(self) -> None:
        while self.ha_entity_layout.count():
            item = self.ha_entity_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self._ha_entities:
            empty = QLabel(
                "No Home Assistant entities to display. Save credentials and fetch entities."
            )
            empty.setStyleSheet("color: rgba(246,235,247,0.62);")
            empty.setWordWrap(True)
            self.ha_entity_layout.addWidget(empty)
            self.ha_entity_layout.addStretch(1)
            return
        pinned = set(self.settings_state["home_assistant"].get("pinned_entities", []))
        for entity in self._ha_entities[:80]:
            entity_id = str(entity.get("entity_id", ""))
            state = str(entity.get("state", "unknown"))
            name = entity_friendly_name(entity)
            secondary = entity_secondary_text(entity)
            detail = f"{entity_id} • {state}"
            if secondary and secondary != entity_id:
                detail = f"{secondary} • {state}"
            pin_button = QPushButton(
                material_icon("push_pin")
                if entity_id in pinned
                else material_icon("push_pin_outline")
            )
            pin_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            pin_button.setProperty("iconRole", True)
            pin_button.setFont(QFont(self.icon_font, 18))
            pin_button.setMinimumSize(42, 42)
            pin_button.setObjectName("secondaryButton")
            pin_button.clicked.connect(
                lambda checked=False, current=entity_id: self._toggle_pin_entity(
                    current
                )
            )
            row = SettingsRow(
                material_icon(entity_icon_name(entity)),
                name,
                detail,
                self.icon_font,
                self.ui_font,
                pin_button,
            )
            self.ha_entity_layout.addWidget(row)
        self.ha_entity_layout.addStretch(1)


    def _toggle_pin_entity(self, entity_id: str) -> None:
        pinned = list(self.settings_state["home_assistant"].get("pinned_entities", []))
        if entity_id in pinned:
            pinned.remove(entity_id)
        else:
            if len(pinned) >= 5:
                self.ha_status.setText("You can pin up to five entities.")
                return
            pinned.append(entity_id)
        self.settings_state["home_assistant"]["pinned_entities"] = pinned
        save_settings_state(self.settings_state)
        self.ha_status.setText(f"{len(pinned)}/5 entities pinned.")
        self._rebuild_ha_entity_list()


    def _save_ntfy_settings(self) -> None:
        ntfy = self.settings_state.setdefault("ntfy", {})
        ntfy["server_url"] = self.ntfy_server_input.text().strip().rstrip("/")
        ntfy["token"] = self.ntfy_token_input.text().strip()
        ntfy["username"] = self.ntfy_username_input.text().strip()
        ntfy["password"] = self.ntfy_password_input.text()
        ntfy["auth_mode"] = self._ntfy_auth_mode()
        ntfy["topics"] = list(self.ntfy_selected_topics)
        ntfy["all_topics"] = bool(self.ntfy_all_topics_checkbox.isChecked())
        ntfy["hide_notification_content"] = bool(
            self.ntfy_hide_content_switch.isChecked()
        )
        existing_topic = str(ntfy.get("topic", "")).strip()
        primary_topic = (
            self.ntfy_selected_topics[0]
            if self.ntfy_selected_topics
            else existing_topic
        )
        ntfy["topic"] = primary_topic
        save_settings_state(self.settings_state)
        if hasattr(self, "ntfy_status"):
            self.ntfy_status.setText("ntfy settings saved.")


    def _send_ntfy_test(self) -> None:
        self._save_ntfy_settings()
        topic = self._resolve_ntfy_test_topic()
        if not topic:
            if hasattr(self, "ntfy_status"):
                self.ntfy_status.setText(
                    "Select a topic before sending a test message."
                )
            return
        ntfy = self.settings_state.get("ntfy", {})
        auth_mode = self._ntfy_auth_mode()
        ok, message = send_ntfy_message(
            str(ntfy.get("server_url", "")),
            topic,
            "Hanauta Test",
            "ntfy integration is working.",
            token=str(ntfy.get("token", "")),
            username=str(ntfy.get("username", "")),
            password=str(ntfy.get("password", "")),
            auth_mode=auth_mode,
        )
        if hasattr(self, "ntfy_status"):
            self.ntfy_status.setText(
                message
                if message
                else ("ntfy test sent." if ok else "ntfy test failed.")
            )
