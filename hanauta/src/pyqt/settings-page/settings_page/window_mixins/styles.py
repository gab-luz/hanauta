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







class StylesMixin:
    """Extracted methods for styles."""

    def _apply_styles(self) -> None:
        theme = self.theme_palette
        accent = self.current_accent["accent"]
        soft = self.current_accent["soft"]
        shell_bg_end = (
            theme.background
            if self.settings_state["appearance"].get("transparency", True)
            else theme.surface
        )
        self.setStyleSheet(
            f"""
            QWidget#settingsWindow {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QLabel[mutedText="true"] {{
                color: {theme.text_muted};
                background: transparent;
            }}
            QFrame#shell {{
                background: {rgba(theme.surface_container, 0.94)};
                border-radius: 18px;
            }}
            QFrame#topHeader {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border-top-left-radius: 18px;
                border-top-right-radius: 18px;
            }}
            QFrame#sidebar {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border-radius: 18px;
            }}
            QFrame#headerLeadChip, QFrame#sidebarNavSection {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border-radius: 14px;
            }}
            QLabel#sidebarTitle {{
                color: {theme.text};
                font-family: "{self.title_font}";
            }}
            QLabel#sidebarSectionLabel {{
                color: {theme.text_muted};
                padding-left: 8px;
                letter-spacing: 0.7px;
                text-transform: uppercase;
                font-family: "{self.main_font}";
            }}
            QLabel#headerLeadIcon {{
                color: {accent};
                font-family: "{self.icon_font}";
            }}
            QLabel#headerLeadText {{
                color: {theme.text_muted};
            }}
            QLabel#headerTitle {{
                color: {theme.text};
            }}
            QLabel#headerSubtitle {{
                color: {theme.text_muted};
            }}
            QScrollArea#bodyScroll {{
                background: transparent;
            }}
            QWidget#content {{
                background: transparent;
            }}
            QPushButton[iconButton="true"] {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.icon};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
            }}
            QPushButton[iconButton="true"]:hover {{
                background: {theme.hover_bg};
                border-color: {rgba(theme.outline, 0.16)};
            }}
            QPushButton[iconButtonBorderless="true"] {{
                background: transparent;
                border: none;
            }}
            QPushButton[iconButtonBorderless="true"]:hover {{
                background: {theme.hover_bg};
                border: none;
            }}
            QFrame#contentCard {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
            }}
            QFrame#overviewHeroCard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {rgba(theme.primary_container, 0.92)},
                    stop:1 {rgba(theme.surface_container_high, 0.86)}
                );
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QLabel#overviewChip {{
                background: {rgba(theme.surface_container_high, 0.72)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                padding: 6px 10px;
                color: {theme.text};
            }}
            QFrame#appearanceCard {{
                background: {rgba(theme.surface_container, 0.92)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QFrame#dockCard {{
                background: {rgba(theme.surface_container, 0.92)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QLabel#appearanceTitle {{
                color: {theme.text};
            }}
            QLabel#appearanceSubtitle {{
                color: {theme.text_muted};
            }}
            QLabel#dockTitle {{
                color: {theme.text};
            }}
            QLabel#dockSubtitle {{
                color: {theme.text_muted};
            }}
            QFrame#appearanceHeroWrap {{
                background: {rgba(theme.surface_container_high, 0.86)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
            }}
            QFrame#appearanceActionColumn, QFrame#appearanceAccentFrame {{
                background: {rgba(theme.surface_container_high, 0.86)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
            }}
            QLabel#appearanceSectionLabel {{
                color: {theme.primary};
                letter-spacing: 1px;
            }}
            QLabel#settingsStatus {{
                color: {theme.text_muted};
            }}
            QProgressBar#settingsProgressBar {{
                min-height: 8px;
                max-height: 8px;
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                background: {rgba(theme.surface_container_high, 0.82)};
            }}
            QProgressBar#settingsProgressBar::chunk {{
                border-radius: 999px;
                background: {theme.primary};
            }}
            QFrame#previewCard {{
                background: transparent;
                border: none;
            }}
            QPushButton#navPill {{
                min-height: 44px;
                border: 1px solid transparent;
                border-radius: 14px;
                background: transparent;
                color: {theme.text};
                text-align: left;
                font-family: "{self.main_font}";
            }}
            QPushButton#navPill:hover {{
                background: {theme.hover_bg};
                border-color: {theme.chip_border};
            }}
            QPushButton#navPill:checked {{
                background: {soft};
                border-color: {theme.app_focused_border};
                color: {theme.text};
            }}
            QPushButton#navPill[compact="true"] {{
                min-height: 42px;
                max-width: 52px;
                padding: 0;
            }}
            QPushButton#navPill QLabel[iconRole="true"] {{
                font-family: "{self.icon_font}";
            }}
            QPushButton#navPill QLabel#navPillText {{
                background: transparent;
                color: {theme.text};
            }}
            QPushButton#actionCard {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 14px;
                color: {theme.text};
                text-align: left;
            }}
            QLabel#actionCardTitle {{
                color: {theme.text};
                background: transparent;
            }}
            QLabel#actionCardDetail {{
                color: {theme.text_muted};
                background: transparent;
            }}
            QPushButton#actionCard:hover {{
                background: {theme.hover_bg};
                border: 1px solid {theme.app_focused_border};
            }}
            QFrame#actionIconWrap, QFrame#rowIconWrap {{
                background: {theme.accent_soft};
                border: 1px solid {theme.app_focused_border};
                border-radius: 10px;
            }}
            QLabel[iconRole="true"] {{
                font-family: "{self.icon_font}";
                color: {theme.primary};
            }}
            QPushButton#segmentedChip {{
                padding: 0 14px;
                min-height: 32px;
                border-radius: 999px;
                border: 1px solid {rgba(theme.outline, 0.16)};
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.text};
            }}
            QPushButton#segmentedChip:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#segmentedChip:checked {{
                background: {accent};
                color: {theme.active_text};
                border-color: {theme.app_focused_border};
            }}
            QPushButton#themeModeCard {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
                color: {theme.text};
            }}
            QPushButton#themeModeCard:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#themeModeCard:checked {{
                background: {accent};
                color: {theme.active_text};
                border-color: rgba(255,255,255,0.0);
            }}
            QPushButton#themeModeCard:checked QLabel {{
                color: {theme.active_text};
            }}
            QPushButton#themeModeCard QLabel[iconRole="true"] {{
                font-family: "{self.icon_font}";
            }}
            QFrame#settingsRow {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QLabel#settingsRowTitle {{
                color: {theme.text};
                background: transparent;
            }}
            QLabel#settingsRowDetail {{
                color: {theme.text_muted};
                background: transparent;
            }}
            QFrame#serviceSection {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QPushButton#serviceHeaderButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
                text-align: left;
            }}
            QPushButton#serviceHeaderButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#serviceHeaderButton[serviceEnabled="false"] {{
                background: {theme.surface_container};
                border-color: {theme.chip_border};
            }}
            QLabel#serviceChevron {{
                color: {theme.icon};
                font-family: "{self.icon_font}";
            }}
            QLabel#serviceHeaderTitle {{
                color: {theme.text};
                background: transparent;
            }}
            QLabel#serviceHeaderDetail {{
                color: {theme.text_muted};
                background: transparent;
            }}
            QComboBox#settingsCombo {{
                min-height: 38px;
                padding: 0 12px;
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.text};
            }}
            QComboBox#settingsCombo::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox#settingsCombo QAbstractItemView {{
                background: {theme.surface};
                color: {theme.text};
                border: 1px solid {theme.panel_border};
                selection-background-color: {theme.accent_soft};
            }}
            QLineEdit {{
                background: {theme.surface_container};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
                color: {theme.text};
                padding: 10px 12px;
                selection-background-color: {theme.accent_soft};
            }}
            QLineEdit:focus {{
                border-color: {theme.app_focused_border};
            }}
            QFrame#marketplaceCatalogCard, QFrame#marketplaceDetailCard {{
                background: {rgba(theme.surface_container, 0.92)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                border-radius: 16px;
            }}
            QLabel#marketplacePanelTitle {{
                color: {theme.text};
                font-family: "{self.title_font}";
                font-size: 11px;
                letter-spacing: 0.4px;
            }}
            QLabel#marketplacePanelSubtitle {{
                color: {theme.text_muted};
                font-family: "{self.main_font}";
                font-size: 10px;
            }}
            QLabel#marketplaceDetailText {{
                color: {theme.text};
                font-family: "{self.main_font}";
                font-size: 10px;
                padding: 10px 12px;
                background: {rgba(theme.surface_container_high, 0.90)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                border-radius: 12px;
            }}
            QLabel#marketplaceStatusText {{
                color: {theme.text_muted};
                font-family: "{self.main_font}";
                font-size: 10px;
                padding: 10px 12px;
                background: {rgba(theme.surface_container_high, 0.80)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 12px;
            }}
            QListWidget#marketplacePluginList {{
                background: transparent;
                border: none;
                outline: none;
                padding: 2px 0;
            }}
            QListWidget#marketplacePluginList::item {{
                color: {theme.text};
                background: {rgba(theme.surface_container_high, 0.72)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 12px;
                margin: 3px 0;
                padding: 10px 11px;
            }}
            QListWidget#marketplacePluginList::item:hover {{
                background: {theme.hover_bg};
                border-color: {rgba(theme.outline, 0.22)};
            }}
            QListWidget#marketplacePluginList::item:selected {{
                background: {rgba(theme.primary, 0.20)};
                color: {theme.text};
                border-color: {theme.app_focused_border};
            }}
            QFrame#startupAppsListWrap {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
            }}
            QListWidget#startupAppsList {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget#startupAppsList::item {{
                color: {theme.text};
                background: {rgba(theme.surface_container_high, 0.70)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 12px;
                margin: 3px 0;
                padding: 9px 10px;
            }}
            QListWidget#startupAppsList::item:hover {{
                background: {theme.hover_bg};
                border-color: {rgba(theme.outline, 0.22)};
            }}
            QListWidget#startupAppsList::item:selected {{
                background: {rgba(theme.primary, 0.20)};
                border-color: {theme.app_focused_border};
            }}
            QPushButton#primaryButton, QPushButton#secondaryButton, QPushButton#dangerButton {{
                min-height: 38px;
                padding: 0 14px;
                border-radius: 14px;
                color: {theme.text};
            }}
            QPushButton#primaryButton {{
                background: {accent};
                color: {theme.active_text};
                border: none;
            }}
            QPushButton#secondaryButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
            }}
            QPushButton#dangerButton {{
                background: {theme.error};
                border: 1px solid {theme.error};
                color: {theme.on_error};
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {theme.app_running_border};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: {theme.text};
            }}
            QScrollBar:vertical {{
                width: 10px;
                background: transparent;
                margin: 8px 0 8px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {theme.app_running_border};
                border-radius: 5px;
                min-height: 42px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QFrame#searchOverlay {{
                background: {rgba(theme.surface_container, 0.98)};
                border: 1px solid {rgba(theme.outline, 0.24)};
                border-radius: 16px;
            }}
            QFrame#searchInputContainer {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border-bottom: 1px solid {rgba(theme.outline, 0.16)};
            }}
            QLineEdit#searchInputField {{
                background: transparent;
                border: none;
                color: {theme.text};
                font-size: 14px;
            }}
            QLineEdit#searchInputField::placeholder {{
                color: {theme.text_muted};
            }}
            QScrollArea#searchResultsContainer {{
                background: transparent;
                border: none;
            }}
            QWidget#searchResultsContent {{
                background: transparent;
            }}
            QFrame#searchResultCard {{
                background: {rgba(theme.surface_container_high, 0.78)};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 12px;
                margin-bottom: 8px;
            }}
            QFrame#searchResultCard:hover {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border-color: {rgba(accent, 0.48)};
            }}
            QPushButton#searchGoButton {{
                background: {rgba(accent, 0.18)};
                color: {accent};
                border: 1px solid {rgba(accent, 0.32)};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 500;
            }}
            QPushButton#searchGoButton:hover {{
                background: {rgba(accent, 0.28)};
            }}
            """
        )
        self._apply_theme_label_overrides()


    def _apply_theme_label_overrides(self) -> None:
        theme = self.theme_palette
        muted = f"color: {theme.text_muted};"
        primary = f"color: {theme.text};"

        muted_label_names = [
            "slideshow_interval_label",
            "display_status",
            "picom_status",
            "energy_status",
            "lockscreen_status",
            "energy_caffeine_note",
            "energy_battery_meta",
            "audio_status",
            "notifications_status",
            "input_status",
            "startup_preview_label",
            "startup_status",
            "privacy_status",
            "networking_status",
            "storage_status",
            "region_location_note",
            "region_status",
            "_services_loading_label",
            "mail_status",
            "ha_status",
            "kdeconnect_rules_status",
            "health_status_label",
            "weather_status",
            "cap_alerts_status",
            "calendar_status",
            "contacts_status",
            "reminders_status",
            "pomodoro_status",
            "rss_status",
            "obs_status",
            "crypto_status",
            "vps_status",
            "clock_status",
            "game_mode_availability",
            "game_mode_status",
            "virtualization_status",
            "study_tracker_status",
            "ntfy_selected_topics_label",
            "ntfy_status",
        ]
        for name in muted_label_names:
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setStyleSheet(muted)

        primary_label_names = [
            "christian_plugin_status",
        ]
        for name in primary_label_names:
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setStyleSheet(primary)

