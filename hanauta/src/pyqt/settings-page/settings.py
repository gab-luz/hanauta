#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone PyQt6 settings screen inspired by the Hanauta settings mock.
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

APP_DIR = Path(__file__).resolve().parents[2]
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
    "mail",
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
from settings_page.xdg_mail import (
    current_favorite_mail_handler,
    current_mailto_handler,
    hanauta_mail_desktop_installed,
)
from settings_page.picom_rules import (
    build_default_picom_config as build_default_picom_config_impl,
    ensure_picom_rule_files as ensure_picom_rule_files_impl,
    render_picom_rule_blocks as render_picom_rule_blocks_impl,
    sync_picom_rule_blocks as sync_picom_rule_blocks_impl,
)
from settings_page.wallpaper_sources import (
    recursive_wallpaper_candidates,
    sync_wallpaper_source_preset,
)
from settings_page.workers import (
    WALLPAPER_SOURCE_CACHE_DIR,
    COMMUNITY_WALLPAPER_DIR,
    WallpaperSourceSyncWorker,
    MailIntegrationProbeWorker,
    GameModeSummaryWorker,
)
from settings_page.xdg_mail import current_favorite_mail_handler, current_mailto_handler
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


def wallpaper_candidates(folder: Path) -> list[Path]:
    return recursive_wallpaper_candidates(folder, IMAGE_SUFFIXES)


def sync_wallpaper_source_preset(source_key: str) -> tuple[bool, str, Path | None]:
    from settings_page.wallpaper_presets import WALLPAPER_SOURCE_PRESETS
    return sync_wallpaper_source_preset(
        source_key,
        presets=WALLPAPER_SOURCE_PRESETS,
        cache_root=WALLPAPER_SOURCE_CACHE_DIR,
        community_root=COMMUNITY_WALLPAPER_DIR,
        image_suffixes=IMAGE_SUFFIXES,
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
from settings_page.mail_store import MailAccountStore, load_mail_storage_config
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

_SETTINGS_LANG_FILE = Path(__file__).parent / "settings_languages.py"
if _SETTINGS_LANG_FILE.exists():
    from settings_languages import KEYBOARD_LAYOUT_PRESETS
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

from settings_page.services import load_service_cache_json, run_bg, run_text

from settings_page.marketplace import (
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






class SettingsWindow(QWidget):
    def __init__(
        self, initial_page: str = "appearance", initial_service_section: str = ""
    ) -> None:
        super().__init__()
        self.fonts = load_app_fonts()
        self.main_font = detect_font(
            "Google Sans Flex",
            "Google Sans",
            self.fonts.get("ui_sans_medium", ""),
            self.fonts.get("ui_sans", ""),
            "Inter",
            "Noto Sans",
        )
        self.title_font = detect_font(
            "Space Grotesk",
            "Google Sans Flex",
            "Google Sans",
            self.fonts.get("ui_display_medium", ""),
            self.fonts.get("ui_display", ""),
            "Rubik",
        )
        self.expressive_font = detect_font(
            "Space Grotesk",
            "Google Sans Flex",
            "Rubik",
            "Inter",
        )
        self.ui_font = self.main_font
        self.display_font = self.title_font
        self.icon_font = detect_font(
            self.fonts.get("material_icons", ""),
            self.fonts.get("material_icons_outlined", ""),
            "Material Icons",
        )

        self.settings_state = load_settings_state()
        self.plugin_service_builders: dict[str, dict[str, object]] = {}
        self._plugin_builders_loaded = False
        self._plugin_dir_scan_in_progress = False
        self._plugin_dirs_to_scan: list[Path] = []
        self.mail_account_store = MailAccountStore(
            Path(load_mail_storage_config()["db_path"]).expanduser()
        )
        self.notification_rules_state = load_notification_rules_state()
        self._weather_city_map: dict[str, WeatherCity] = {}
        self._selected_weather_city: WeatherCity | None = configured_city()
        self._weather_search_timer = QTimer(self)
        self._weather_search_timer.setSingleShot(True)
        self._weather_search_timer.timeout.connect(self._perform_weather_city_search)
        if not self.settings_state["appearance"].get("use_matugen_palette", False):
            sync_static_theme_from_settings(self.settings_state, apply_gtk=False)
        elif not PYQT_THEME_FILE.exists():
            write_default_pyqt_palette(use_matugen=False)
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.current_accent = accent_palette(
            self.settings_state["appearance"].get("accent", "orchid")
        )
        self._refresh_current_accent()
        self.initial_page = initial_page
        self.initial_service_section = initial_service_section
        self._window_animation: QParallelAnimationGroup | None = None
        self._wallpaper_sync_worker: WallpaperSourceSyncWorker | None = None
        self._mail_integration_probe_worker: MailIntegrationProbeWorker | None = None
        self._gamemode_summary_worker: GameModeSummaryWorker | None = None
        self._system_theme_install_declined: set[str] = set()
        self._theme_refresh_restart_pending = False
        self._sidebar_collapsed = False
        self._last_page_index = 0
        self._slideshow_timer = QTimer(self)
        self._slideshow_timer.timeout.connect(self._advance_slideshow)
        self._slideshow_index = 0
        self._ha_entities: list[dict] = []
        self._ha_entity_map: dict[str, dict] = {}
        self._battery_snapshot = read_battery_snapshot()
        self._battery_present = self._battery_snapshot is not None
        self._energy_battery_expanded = self._battery_present
        self.display_state = parse_xrandr_state()
        self.dock_settings_state = load_dock_settings_state()
        self.display_controls: dict[str, dict[str, QWidget]] = {}
        self.picom_state = parse_picom_settings(read_picom_text())
        self.wallpaper = self._pick_wallpaper()
        self.setWindowTitle("Hanauta Settings")
        self.setObjectName("settingsWindow")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(1180, 720)
        self.setWindowOpacity(0.0)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(8, 5, 10, 150))
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(18)

        shell = QFrame()
        shell.setObjectName("shell")
        outer.addWidget(shell)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(16)

        shell_layout.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(18, 18, 18, 18)
        body.setSpacing(18)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)

        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_scroll_body(), 1)

        shell_layout.addLayout(body, 1)

        self._apply_styles()
        apply_antialias_font(self)
        self._theme_font_signature = self._current_theme_font_signature()
        self._sync_wallpaper_controls()
        self._sync_accent_controls()
        self._refresh_system_overview()
        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)
        self._slideshow_timer.setInterval(
            max(5, int(self.settings_state["appearance"].get("slideshow_interval", 30)))
            * 1000
        )
        if self.settings_state["appearance"].get("slideshow_enabled"):
            self._slideshow_timer.start()
        self._show_page(self.initial_page)

    def _pick_wallpaper(self) -> Path:
        configured = Path(
            self.settings_state["appearance"].get("wallpaper_path", "")
        ).expanduser()
        if configured.exists() and configured.is_file():
            return configured
        if CURRENT_WALLPAPER.exists():
            return CURRENT_WALLPAPER
        preferred = [
            WALLS_DIR / "ryan-3.png",
            WALLS_DIR / "ryan-4.png",
            WALLS_DIR / "ryan-8.png",
        ]
        for candidate in preferred:
            if candidate.exists():
                return candidate
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            matches = sorted(WALLS_DIR.glob(pattern))
            if matches:
                return matches[0]
        return WALLS_DIR

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("topHeader")
        header.setFixedHeight(54)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)

        lead_chip = QFrame()
        lead_chip.setObjectName("headerLeadChip")
        lead_layout = QHBoxLayout(lead_chip)
        lead_layout.setContentsMargins(12, 8, 12, 8)
        lead_layout.setSpacing(8)
        lead_icon = QLabel("♪")
        lead_icon.setProperty("iconRole", True)
        lead_icon.setObjectName("headerLeadIcon")
        lead_icon.setFont(QFont(self.icon_font, 14))
        lead_text = QLabel("hanauta")
        lead_text.setObjectName("headerLeadText")
        lead_text.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        lead_layout.addWidget(lead_icon)
        lead_layout.addWidget(lead_text)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(1)
        title = QLabel("Settings")
        title.setObjectName("headerTitle")
        title.setFont(QFont(self.display_font, 12))
        subtitle = QLabel("Wallpaper, accents, and shell behavior")
        subtitle.setObjectName("headerSubtitle")
        subtitle.setFont(QFont(self.ui_font, 8))
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        close_button = create_close_button(
            material_icon("close"),
            self.icon_font,
            font_size=16,
        )
        close_button.setFixedSize(32, 32)
        close_button.setProperty("iconButton", True)
        close_button.clicked.connect(self.close)

        layout.addWidget(
            lead_chip, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addLayout(title_wrap, 1)
        layout.addWidget(
            close_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return header

    def _build_sidebar(self) -> QWidget:
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(244)

        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.sidebar_title = QLabel("Settings")
        self.sidebar_title.setObjectName("sidebarTitle")
        self.sidebar_title.setFont(QFont(self.display_font, 12, QFont.Weight.DemiBold))

        self.sidebar_menu_button = QPushButton(material_icon("menu"))
        self.sidebar_menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_menu_button.setFixedSize(38, 36)
        self.sidebar_menu_button.setFont(QFont(self.icon_font, 16))
        self.sidebar_menu_button.setProperty("iconButton", True)
        self.sidebar_menu_button.setProperty("iconButtonBorderless", True)
        self.sidebar_menu_button.clicked.connect(self._toggle_sidebar)

        self.search_button = QPushButton(material_icon("search"))
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.setFixedSize(38, 36)
        self.search_button.setFont(QFont(self.icon_font, 16))
        self.search_button.setProperty("iconButton", True)
        self.search_button.setProperty("iconButtonBorderless", True)
        self.search_button.clicked.connect(self._toggle_search)

        top_row.addWidget(self.sidebar_title, 1)
        top_row.addWidget(self.search_button, 0, Qt.AlignmentFlag.AlignRight)
        top_row.addWidget(self.sidebar_menu_button, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(top_row)

        nav_section = QFrame()
        nav_section.setObjectName("sidebarNavSection")
        nav_layout = QVBoxLayout(nav_section)
        nav_layout.setContentsMargins(6, 8, 6, 8)
        nav_layout.setSpacing(6)

        self.sidebar_section_label = QLabel("Workspace")
        self.sidebar_section_label.setObjectName("sidebarSectionLabel")
        self.sidebar_section_label.setFont(
            QFont(self.ui_font, 8, QFont.Weight.DemiBold)
        )
        nav_layout.addWidget(self.sidebar_section_label)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, NavPillButton] = {}

        items = [
            ("overview", material_icon("grid_view"), "Overview", False),
            ("appearance", material_icon("palette"), "Looks", True),
            ("marketplace", material_icon("storefront"), "Marketplace", False),
            ("display", material_icon("desktop_windows"), "Display", False),
            ("energy", material_icon("bolt"), "Energy", False),
            ("audio", material_icon("music_note"), "Audio", False),
            ("notifications", material_icon("notifications"), "Notifications", False),
            ("input", material_icon("language"), "Input", False),
            ("startup", material_icon("restart_alt"), "Startup", False),
            ("privacy", material_icon("shield"), "Privacy", False),
            ("networking", material_icon("hub"), "Networking", False),
            ("storage", material_icon("storage"), "Storage", False),
            ("region", material_icon("public"), "Region", False),
            ("bar", material_icon("crop_square"), "Bar", False),
            ("services", material_icon("widgets"), "Services", False),
        ]

        for key, glyph, label, checked in items:
            button = NavPillButton(glyph, label, self.icon_font, self.ui_font)
            button.setChecked(checked)
            button.clicked.connect(
                lambda checked=False, current=key: self._show_page(current)
            )
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            nav_layout.addWidget(button)

        layout.addWidget(nav_section)
        layout.addStretch(1)
        return self.sidebar

    def _build_scroll_body(self) -> QWidget:
        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self._build_overview_page())
        self.page_stack.addWidget(self._build_appearance_page())
        self.page_stack.addWidget(self._build_marketplace_page())
        self.page_stack.addWidget(self._build_display_page())
        self.page_stack.addWidget(self._build_energy_page())
        self.page_stack.addWidget(self._build_audio_page())
        self.page_stack.addWidget(self._build_notifications_page())
        self.page_stack.addWidget(self._build_input_page())
        self.page_stack.addWidget(self._build_startup_page())
        self.page_stack.addWidget(self._build_privacy_page())
        self.page_stack.addWidget(self._build_networking_page())
        self.page_stack.addWidget(self._build_storage_page())
        self.page_stack.addWidget(self._build_region_page())
        self.bar_page_index = self.page_stack.count()
        self._bar_page_ready = False
        self._bar_page_building = False
        self.page_stack.addWidget(self._build_bar_placeholder())
        self.services_page_index = self.page_stack.count()
        self._services_page_ready = False
        self._services_page_building = False
        self.page_stack.addWidget(self._build_services_placeholder())
        self._show_page(self.initial_page)

        self._build_search_overlay()

        return self.page_stack

    def _build_bar_placeholder(self) -> QWidget:
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        loading = QLabel("Bar page is loaded on demand for faster startup.")
        loading.setWordWrap(True)
        loading.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(loading)
        layout.addStretch(1)
        return placeholder

    def _build_search_overlay(self) -> None:
        self.search_container = QFrame(self.page_stack)
        self.search_container.setObjectName("searchOverlay")
        self.search_container.setVisible(False)
        search_layout = QVBoxLayout(self.search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        search_input_container = QFrame()
        search_input_container.setObjectName("searchInputContainer")
        input_layout = QHBoxLayout(search_input_container)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(12)

        search_icon = QLabel(material_icon("search"))
        search_icon.setFont(QFont(self.icon_font, 18))
        search_icon.setStyleSheet("color: rgba(246,235,247,0.56);")
        input_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search settings...")
        self.search_input.setObjectName("searchInputField")
        self.search_input.setFont(QFont(self.ui_font, 14))
        self.search_input.textChanged.connect(self._on_search_changed)
        input_layout.addWidget(self.search_input, 1)

        close_search_btn = QPushButton(material_icon("close"))
        close_search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_search_btn.setFixedSize(32, 32)
        close_search_btn.setFont(QFont(self.icon_font, 16))
        close_search_btn.setProperty("iconButton", True)
        close_search_btn.clicked.connect(self._toggle_search)
        input_layout.addWidget(close_search_btn)

        search_layout.addWidget(search_input_container)

        self.search_results_container = QScrollArea()
        self.search_results_container.setObjectName("searchResultsContainer")
        self.search_results_container.setWidgetResizable(True)
        self.search_results_container.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.search_results_layout = QVBoxLayout()
        self.search_results_layout.setContentsMargins(16, 8, 16, 16)
        self.search_results_layout.setSpacing(8)
        self.search_results_layout.addStretch(1)

        results_widget = QWidget()
        results_widget.setObjectName("searchResultsContent")
        results_widget.setLayout(self.search_results_layout)
        self.search_results_container.setWidget(results_widget)

        search_layout.addWidget(self.search_results_container, 1)

        self.search_overlay_index = self.page_stack.count()
        self.page_stack.addWidget(self.search_container)

    def _build_services_placeholder(self) -> QWidget:
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        loading = QLabel("Services page is loaded on demand for faster startup.")
        loading.setWordWrap(True)
        loading.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(loading)
        layout.addStretch(1)
        return placeholder

    def _ensure_services_page_ready(self) -> None:
        if getattr(self, "_services_page_ready", False):
            return
        if bool(getattr(self, "_services_page_building", False)):
            return
        self._services_page_building = True

        def _build() -> None:
            try:
                services_page = self._build_services_page()
                index = int(getattr(self, "services_page_index", 14))
                old_widget = self.page_stack.widget(index)
                if old_widget is not None:
                    self.page_stack.removeWidget(old_widget)
                    old_widget.deleteLater()
                self.page_stack.insertWidget(index, services_page)
                self._services_page_ready = True
                if str(getattr(self, "current_page", "")) == "services":
                    self.page_stack.setCurrentIndex(index)
            finally:
                self._services_page_building = False

        QTimer.singleShot(0, _build)

    def _ensure_bar_page_ready(self) -> None:
        if getattr(self, "_bar_page_ready", False):
            return
        if bool(getattr(self, "_bar_page_building", False)):
            return
        self._bar_page_building = True

        def _build() -> None:
            try:
                bar_page = self._build_bar_page()
                index = int(getattr(self, "bar_page_index", 13))
                old_widget = self.page_stack.widget(index)
                if old_widget is not None:
                    self.page_stack.removeWidget(old_widget)
                    old_widget.deleteLater()
                self.page_stack.insertWidget(index, bar_page)
                self._bar_page_ready = True
                if str(getattr(self, "current_page", "")) == "bar":
                    self.page_stack.setCurrentIndex(index)
            finally:
                self._bar_page_building = False

        QTimer.singleShot(0, _build)

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        if hasattr(self, "sidebar"):
            self.sidebar.setFixedWidth(84 if self._sidebar_collapsed else 244)
        if hasattr(self, "sidebar_title"):
            self.sidebar_title.setVisible(not self._sidebar_collapsed)
        if hasattr(self, "sidebar_section_label"):
            self.sidebar_section_label.setVisible(not self._sidebar_collapsed)
        for button in getattr(self, "nav_buttons", {}).values():
            button.set_compact(self._sidebar_collapsed)

    SETTINGS_SEARCH_INDEX = {
        "profile name": ("overview", "First name"),
        "nickname": ("overview", "Nickname"),
        "voice phrases": ("overview", "Voice phrases by language"),
        "spoken name": ("overview", "Name pronunciation"),
        "new email phrase": ("overview", "New email voice phrase"),
        "wallpaper": ("appearance", "Wallpaper"),
        "theme": ("appearance", "Theme"),
        "colors": ("appearance", "Colors"),
        "accent": ("appearance", "Accent Color"),
        "transparency": ("appearance", "Transparency"),
        "notification center opacity": ("appearance", "Notification Center Opacity"),
        "control center opacity": ("appearance", "Control Center Opacity"),
        "card opacity": ("appearance", "Card Opacity"),
        "toast max width": ("appearance", "Toast Max Width"),
        "toast max height": ("appearance", "Toast Max Height"),
        "matugen": ("appearance", "Matugen Palette"),
        "display": ("display", "Display"),
        "monitor": ("display", "Monitor"),
        "screen": ("display", "Screen"),
        "xrandr": ("display", "Xrandr"),
        "resolution": ("display", "Resolution"),
        "refresh rate": ("display", "Refresh Rate"),
        "picom": ("display", "Picom"),
        "compositor": ("display", "Compositor"),
        "shadows": ("display", "Shadows"),
        "shadow radius": ("display", "Shadow Radius"),
        "shadow opacity": ("display", "Shadow Opacity"),
        "shadow offset": ("display", "Shadow Offset"),
        "opacity": ("display", "Opacity"),
        "active opacity": ("display", "Active Opacity"),
        "inactive opacity": ("display", "Inactive Opacity"),
        "corners": ("display", "Rounded Corners"),
        "corner radius": ("display", "Corner Radius"),
        "backend": ("display", "Picom Backend"),
        "vsync": ("display", "VSync"),
        "damage": ("display", "Use Damage"),
        "fading": ("display", "Fading"),
        "transparent clipping": ("display", "Transparent Clipping"),
        "energy": ("energy", "Energy"),
        "power": ("energy", "Power"),
        "battery": ("energy", "Battery"),
        "brightness": ("energy", "Brightness"),
        "sleep": ("energy", "Sleep"),
        "suspend": ("energy", "Suspend"),
        "lock": ("energy", "Lock"),
        "autolock": ("energy", "Auto Lock"),
        "idle": ("energy", "Idle"),
        "audio": ("audio", "Audio"),
        "sound": ("audio", "Sound"),
        "volume": ("audio", "Volume"),
        "speaker": ("audio", "Speaker"),
        "microphone": ("audio", "Microphone"),
        "mute": ("audio", "Mute"),
        "default sink": ("audio", "Default Sink"),
        "default source": ("audio", "Default Source"),
        "alert sounds": ("audio", "Alert Sounds"),
        "notifications": ("notifications", "Notifications"),
        "dnd": ("notifications", "Do Not Disturb"),
        "alerts": ("notifications", "Alerts"),
        "urgency": ("notifications", "Urgency"),
        "history": ("notifications", "History"),
        "history limit": ("notifications", "History Limit"),
        "pause while sharing": ("notifications", "Pause While Sharing"),
        "per app rules": ("notifications", "Per-App Rules"),
        "keyboard": ("input", "Keyboard"),
        "mouse": ("input", "Mouse"),
        "touchpad": ("input", "Touchpad"),
        "tap to click": ("input", "Tap to Click"),
        "natural scroll": ("input", "Natural Scroll"),
        "mouse acceleration": ("input", "Mouse Acceleration"),
        "layout": ("input", "Keyboard Layout"),
        "language": ("input", "Language"),
        "repeat delay": ("input", "Repeat Delay"),
        "repeat rate": ("input", "Repeat Rate"),
        "startup": ("startup", "Startup"),
        "launch": ("startup", "Launch"),
        "autostart": ("startup", "Autostart"),
        "apps": ("startup", "Startup Apps"),
        "launch bar": ("startup", "Launch Bar"),
        "launch dock": ("startup", "Launch Dock"),
        "restore wallpaper": ("startup", "Restore Wallpaper"),
        "restore displays": ("startup", "Restore Displays"),
        "restore vpn": ("startup", "Restore VPN"),
        "delay": ("startup", "Startup Delay"),
        "restart hooks": ("startup", "Restart Hooks"),
        "watchdogs": ("startup", "Watchdogs"),
        "privacy": ("privacy", "Privacy"),
        "lockscreen": ("privacy", "Lockscreen"),
        "blur": ("privacy", "Blur"),
        "blur screenshot": ("privacy", "Blur Screenshot"),
        "screenshot guard": ("privacy", "Screenshot Guard"),
        "screen share guard": ("privacy", "Screen Share Guard"),
        "lock on suspend": ("privacy", "Lock on Suspend"),
        "hide content": ("privacy", "Hide Notification Content"),
        "network": ("networking", "Network"),
        "wifi": ("networking", "Wi-Fi"),
        "ethernet": ("networking", "Ethernet"),
        "vpn": ("networking", "VPN"),
        "wireguard": ("networking", "WireGuard"),
        "split tunnel": ("networking", "Split Tunnel Apps"),
        "storage": ("storage", "Storage"),
        "disk": ("storage", "Disk"),
        "locale": ("region", "Locale"),
        "region": ("region", "Region"),
        "timezone": ("region", "Timezone"),
        "clock": ("region", "Clock"),
        "date": ("region", "Date"),
        "date format": ("region", "Date Format"),
        "time format": ("region", "Time Format"),
        "calendar": ("region", "Calendar"),
        "week numbers": ("region", "Show Week Numbers"),
        "first day": ("region", "First Day of Week"),
        "caldav": ("region", "Caldav"),
        "bar": ("bar", "Bar"),
        "polybar": ("bar", "Polybar"),
        "polybar widgets": ("bar", "Polybar Widgets"),
        "tray": ("bar", "System Tray"),
        "workspaces": ("bar", "Workspaces"),
        "workspace count": ("bar", "Workspace Count"),
        "workspace label": ("bar", "Show Workspace Label"),
        "bar height": ("bar", "Bar Height"),
        "bar monitor": ("bar", "Monitor Mode"),
        "launcher offset": ("bar", "Launcher Offset"),
        "datetime offset": ("bar", "DateTime Offset"),
        "media offset": ("bar", "Media Offset"),
        "status offset": ("bar", "Status Offset"),
        "tray offset": ("bar", "Tray Offset"),
        "icon overrides": ("bar", "Bar Icon Overrides"),
        "services": ("services", "Services"),
        "kdeconnect": ("services", "KDE Connect"),
        "home assistant": ("services", "Home Assistant"),
        "weather": ("services", "Weather"),
        "calendar widget": ("services", "Calendar Widget"),
        "reminders": ("services", "Reminders"),
        "pomodoro": ("services", "Pomodoro"),
        "rss": ("services", "RSS"),
        "obs": ("services", "OBS"),
        "crypto": ("services", "Crypto"),
        "vps": ("services", "VPS"),
        "game mode": ("services", "Game Mode"),
        "virtualization": ("services", "Virtualization"),
        "icon": ("bar", "Bar Icons"),
        "services": ("services", "Services"),
        "kdeconnect": ("services", "KDE Connect"),
        "home assistant": ("services", "Home Assistant"),
        "weather": ("services", "Weather"),
    }

    def _toggle_search(self) -> None:
        if not hasattr(self, "search_container"):
            return
        is_visible = self.search_container.isVisible()
        if is_visible:
            self.search_container.setVisible(False)
            self.search_input.clear()
            self._clear_search_results()
            self.page_stack.setCurrentIndex(self._last_page_index)
        else:
            self._last_page_index = self.page_stack.currentIndex()
            self.page_stack.setCurrentIndex(self.search_overlay_index)
            self.search_container.setVisible(True)
            self.search_input.setFocus()

    def _clear_search_results(self) -> None:
        while self.search_results_layout.count() > 1:
            item = self.search_results_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _on_search_changed(self, text: str) -> None:
        self._clear_search_results()
        if not text:
            return
        query = text.lower().strip()
        matches = []
        for keyword, (page, setting_name) in self.SETTINGS_SEARCH_INDEX.items():
            if query in keyword:
                matches.append((keyword, page, setting_name))
        if not matches:
            no_results = QLabel("No matching settings found")
            no_results.setStyleSheet("color: rgba(246,235,247,0.56); padding: 16px;")
            self.search_results_layout.insertWidget(0, no_results)
            return
        for keyword, page, setting_name in matches:
            result_card = self._create_search_result_card(keyword, page, setting_name)
            self.search_results_layout.insertWidget(
                self.search_results_layout.count() - 1, result_card
            )

    def _derive_section(self, keyword: str, page: str) -> str:
        keyword_lower = keyword.lower()
        if page == "appearance":
            if "opacity" in keyword_lower or "toast" in keyword_lower:
                return "Transparency"
            if "matugen" in keyword_lower:
                return "Matugen"
            if "wallpaper" in keyword_lower:
                return "Wallpaper"
            if (
                "theme" in keyword_lower
                or "color" in keyword_lower
                or "accent" in keyword_lower
            ):
                return "Theme"
        elif page == "display":
            if (
                "picom" in keyword_lower
                or "shadow" in keyword_lower
                or "opacity" in keyword_lower
                or "corner" in keyword_lower
                or "vsync" in keyword_lower
                or "fading" in keyword_lower
            ):
                return "Picom"
            return "Monitors"
        elif page == "input":
            if (
                "keyboard" in keyword_lower
                or "layout" in keyword_lower
                or "language" in keyword_lower
                or "repeat" in keyword_lower
            ):
                return "Keyboard"
            return "Mouse"
        elif page == "startup":
            if "app" in keyword_lower:
                return "Startup Apps"
            if "launch" in keyword_lower:
                return "Launch Bar"
        elif page == "bar":
            if "tray" in keyword_lower:
                return "System Tray"
            if "workspace" in keyword_lower:
                return "Workspaces"
            if "offset" in keyword_lower:
                return "Offsets"
            if "polybar" in keyword_lower or "widget" in keyword_lower:
                return "Polybar"
        return page.title()

    def _create_search_result_card(
        self, keyword: str, page: str, setting_name: str
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("searchResultCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        icon_label = QLabel(material_icon("settings"))
        icon_label.setFont(QFont(self.icon_font, 18))
        icon_label.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        setting_label = QLabel(setting_name)
        setting_label.setFont(QFont(self.ui_font, 12, QFont.Weight.Medium))
        setting_label.setStyleSheet("color: rgba(246,235,247,0.92);")
        text_layout.addWidget(setting_label)

        section = self._derive_section(keyword, page)
        page_label = QLabel(f"{section} → {page.title()}")
        page_label.setFont(QFont(self.ui_font, 10))
        page_label.setStyleSheet("color: rgba(246,235,247,0.56);")
        text_layout.addWidget(page_label)
        layout.addLayout(text_layout, 1)

        go_button = QPushButton("Go")
        go_button.setObjectName("searchGoButton")
        go_button.setCursor(Qt.CursorShape.PointingHandCursor)
        go_button.clicked.connect(
            lambda _=None, p=page, s=setting_name: self._navigate_to_setting(p, s)
        )
        layout.addWidget(go_button)

        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda e, p=page, s=setting_name: (
            self._navigate_to_setting(p, s)
        )
        return card

    def _navigate_to_setting(self, page: str, setting_name: str) -> None:
        self._show_page(page)
        self.search_input.clear()
        self._clear_search_results()
        if hasattr(self, "search_container"):
            self.search_container.setVisible(False)
        QTimer.singleShot(50, lambda: self._scroll_to_setting(page, setting_name))

    def _scroll_to_setting(self, page: str, setting_name: str) -> None:
        order = {
            "overview": 0,
            "appearance": 1,
            "marketplace": 2,
            "display": 3,
            "energy": 4,
            "audio": 5,
            "notifications": 6,
            "input": 7,
            "startup": 8,
            "privacy": 9,
            "networking": 10,
            "storage": 11,
            "region": 12,
            "bar": 13,
            "services": 14,
        }
        page_index = order.get(page, 1)
        if page_index >= self.page_stack.count():
            return
        scroll_area = self.page_stack.widget(page_index)
        if scroll_area is None:
            return
        scroll_area = scroll_area.findChild(QScrollArea)
        if scroll_area is None:
            return
        scroll = scroll_area.verticalScrollBar()

        setting_lower = setting_name.lower()
        y_position = 0

        if page == "display":
            if (
                "picom" in setting_lower
                or "shadow" in setting_lower
                or "opacity" in setting_lower
                or "corner" in setting_lower
                or "vsync" in setting_lower
                or "fading" in setting_lower
                or "backend" in setting_lower
            ):
                y_position = 400
            else:
                y_position = 0
        elif page == "appearance":
            if "wallpaper" in setting_lower:
                y_position = 0
            elif (
                "theme" in setting_lower
                or "color" in setting_lower
                or "accent" in setting_lower
            ):
                y_position = 200
            elif (
                "transparency" in setting_lower
                or "opacity" in setting_lower
                or "toast" in setting_lower
                or "matugen" in setting_lower
            ):
                y_position = 400
        elif page == "input":
            if (
                "keyboard" in setting_lower
                or "layout" in setting_lower
                or "language" in setting_lower
                or "repeat" in setting_lower
            ):
                y_position = 0
            else:
                y_position = 300
        elif page == "startup":
            if "app" in setting_lower:
                y_position = 200
            elif "launch" in setting_lower:
                y_position = 400
            else:
                y_position = 0
        elif page == "bar":
            if "tray" in setting_lower:
                y_position = 600
            elif "workspace" in setting_lower:
                y_position = 300
            elif (
                "offset" in setting_lower
                or "polybar" in setting_lower
                or "widget" in setting_lower
            ):
                y_position = 400
            else:
                y_position = 0

        scroll.setValue(min(y_position, scroll.maximum()))

    def _scroll_page(self, *widgets: QWidget) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("bodyScroll")

        content = QWidget()
        content.setObjectName("content")
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(10)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return scroll

    def _build_overview_page(self) -> QWidget:
        return self._scroll_page(self._build_system_overview_card(), self._build_profile_card())

    def _build_appearance_page(self) -> QWidget:
        return self._scroll_page(self._build_wallpaper_colors_card())

    def _build_bar_page(self) -> QWidget:
        return self._scroll_page(self._build_bar_screen_card())

    def _build_marketplace_page(self) -> QWidget:
        return self._scroll_page(self._build_marketplace_card())

    def _build_energy_page(self) -> QWidget:
        return self._scroll_page(self._build_energy_card())

    def _build_audio_page(self) -> QWidget:
        return self._scroll_page(self._build_audio_card())

    def _build_notifications_page(self) -> QWidget:
        return self._scroll_page(self._build_notifications_card())

    def _build_input_page(self) -> QWidget:
        return self._scroll_page(self._build_input_card())

    def _build_startup_page(self) -> QWidget:
        return self._scroll_page(self._build_startup_card())

    def _build_privacy_page(self) -> QWidget:
        return self._scroll_page(self._build_privacy_card())

    def _build_networking_page(self) -> QWidget:
        return self._scroll_page(self._build_networking_card())

    def _build_storage_page(self) -> QWidget:
        return self._scroll_page(self._build_storage_card())

    def _build_region_page(self) -> QWidget:
        return self._scroll_page(self._build_region_card())

    def _build_services_page(self) -> QWidget:
        return self._scroll_page(self._build_services_card())

    def _build_display_page(self) -> QWidget:
        return self._scroll_page(self._build_display_card(), self._build_picom_card())

    def _build_picom_page(self) -> QWidget:
        return self._scroll_page(self._build_picom_card())

    def _show_page(self, key: str) -> None:
        order = {
            "overview": 0,
            "appearance": 1,
            "marketplace": 2,
            "display": 3,
            "energy": 4,
            "audio": 5,
            "notifications": 6,
            "input": 7,
            "startup": 8,
            "privacy": 9,
            "networking": 10,
            "storage": 11,
            "region": 12,
            "bar": 13,
            "services": 14,
        }
        resolved = key if key in order else "appearance"
        if resolved == "bar":
            self._ensure_bar_page_ready()
        if resolved == "services":
            self._ensure_services_page_ready()
        self.current_page = resolved
        self.page_stack.setCurrentIndex(order[resolved])
        for button_key, button in getattr(self, "nav_buttons", {}).items():
            button.setChecked(button_key == resolved)
        if resolved == "services" and self.initial_service_section:
            QTimer.singleShot(
                0, lambda: self._focus_service_section(self.initial_service_section)
            )

    def _build_system_overview_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("grid_view"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("System Overview")
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        title.setFont(QFont(self.display_font, 13))
        subtitle = QLabel("Quick info for this session and shell environment.")
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle.setFont(QFont(self.ui_font, 9))
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.system_overview_labels: dict[str, QLabel] = {}
        for index, key in enumerate(
            ("Host", "Kernel", "Session", "Python", "Uptime", "Screen")
        ):
            label = QLabel("...")
            label.setFont(QFont(self.ui_font, 10))
            label.setStyleSheet("color: #FFFFFF;")
            self.system_overview_labels[key] = label
            grid.addWidget(self._metric_card(key, label), index // 2, index % 2)
        layout.addLayout(grid)
        return card

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

    def _metric_card(self, title: str, value_label: QLabel) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsRow")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setFont(QFont(self.ui_font, 8))
        title_label.setStyleSheet("color: rgba(246,235,247,0.62);")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card

    def _format_slideshow_interval_text(self, value: int) -> str:
        seconds = max(5, int(value))
        if seconds < 60:
            return f"{seconds} sec"
        if seconds < 3600:
            minutes = seconds // 60
            remainder = seconds % 60
            if remainder == 0:
                return f"{minutes} min"
            return f"{minutes} min {remainder} sec"
        if seconds < 86400:
            hours = seconds // 3600
            remainder = seconds % 3600
            minutes = remainder // 60
            if minutes == 0:
                return f"{hours} hr"
            return f"{hours} hr {minutes} min"
        days = seconds // 86400
        remainder = seconds % 86400
        hours = remainder // 3600
        if hours == 0:
            return f"{days} day"
        return f"{days} day {hours} hr"

    def _build_wallpaper_colors_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("appearanceCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(8)

        icon = IconLabel(material_icon("palette"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        icon.setObjectName("appearanceHeaderIcon")
        title = QLabel("Wallpaper & Colors")
        title.setObjectName("appearanceTitle")
        title.setFont(QFont(self.display_font, 13))
        subtitle = QLabel(
            "Pick, import, and rotate wallpapers without disturbing Matugen theming."
        )
        subtitle.setObjectName("appearanceSubtitle")
        subtitle.setFont(QFont(self.ui_font, 9))

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)

        layout.addLayout(header)

        hero_wrap = QFrame()
        hero_wrap.setObjectName("appearanceHeroWrap")
        hero = QHBoxLayout(hero_wrap)
        hero.setContentsMargins(14, 14, 14, 14)
        hero.setSpacing(12)
        self.preview_card = PreviewCard(self.wallpaper, self.ui_font, self.display_font)
        hero.addWidget(self.preview_card, 11)

        actions_wrap = QFrame()
        actions_wrap.setObjectName("appearanceActionColumn")
        actions = QVBoxLayout(actions_wrap)
        actions.setContentsMargins(14, 14, 14, 14)
        actions.setSpacing(8)
        self.random_wall_button = ActionCard(
            material_icon("auto_awesome"),
            "Random Wallpaper",
            "Pick a random image from your slideshow folder",
            self.icon_font,
            self.ui_font,
        )
        self.choose_picture_button = ActionCard(
            material_icon("photo_library"),
            "Choose picture",
            "Select and apply a wallpaper image",
            self.icon_font,
            self.ui_font,
        )
        self.choose_folder_button = ActionCard(
            material_icon("folder_open"),
            "Choose folder",
            "Use a folder as a slideshow source",
            self.icon_font,
            self.ui_font,
        )
        self.random_wall_button.clicked.connect(self._apply_random_wallpaper)
        self.choose_picture_button.clicked.connect(self._choose_wallpaper_file)
        self.choose_folder_button.clicked.connect(self._choose_wallpaper_folder)
        actions.addWidget(self.random_wall_button)
        actions.addWidget(self.choose_picture_button)
        actions.addWidget(self.choose_folder_button)

        mode_heading = QLabel("Theme mode")
        mode_heading.setObjectName("appearanceSectionLabel")
        mode_heading.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        actions.addWidget(mode_heading)

        modes = QGridLayout()
        modes.setContentsMargins(0, 0, 0, 0)
        modes.setHorizontalSpacing(8)
        modes.setVerticalSpacing(8)
        light = ThemeModeCard(
            material_icon("light_mode"), "Light", self.icon_font, self.ui_font
        )
        dark = ThemeModeCard(
            material_icon("dark_mode"), "Dark", self.icon_font, self.ui_font
        )
        custom = ThemeModeCard(
            material_icon("palette"), "Custom", self.icon_font, self.ui_font
        )
        wallpaper_aware = ThemeModeCard(
            material_icon("auto_awesome"),
            "Wallpaper Aware (matugen)",
            self.icon_font,
            self.ui_font,
        )
        self.theme_buttons = {
            "light": light,
            "dark": dark,
            "custom": custom,
            "wallpaper_aware": wallpaper_aware,
        }
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for key, button in self.theme_buttons.items():
            self.mode_group.addButton(button)
            button.clicked.connect(
                lambda checked=False, current=key: self._set_theme_choice(current)
            )
        modes.addWidget(light, 0, 0)
        modes.addWidget(dark, 0, 1)
        modes.addWidget(custom, 1, 0)
        modes.addWidget(wallpaper_aware, 1, 1)

        actions.addLayout(modes)
        self.custom_theme_heading = QLabel("Custom theme")
        self.custom_theme_heading.setObjectName("appearanceSectionLabel")
        self.custom_theme_heading.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        actions.addWidget(self.custom_theme_heading)

        self.custom_theme_wrap = QFrame()
        self.custom_theme_wrap.setObjectName("appearanceAccentFrame")
        custom_theme_layout = QGridLayout(self.custom_theme_wrap)
        custom_theme_layout.setContentsMargins(10, 10, 10, 10)
        custom_theme_layout.setHorizontalSpacing(8)
        custom_theme_layout.setVerticalSpacing(8)
        retrowave = ThemeModeCard(
            material_icon("bolt"), "Retrowave", self.icon_font, self.ui_font
        )
        dracula = ThemeModeCard(
            material_icon("dark_mode"), "Dracula", self.icon_font, self.ui_font
        )
        caelestia = ThemeModeCard(
            material_icon("auto_awesome"), "Caelestia", self.icon_font, self.ui_font
        )
        self.custom_theme_buttons = {
            "retrowave": retrowave,
            "dracula": dracula,
            "caelestia": caelestia,
        }
        self.custom_theme_group = QButtonGroup(self)
        self.custom_theme_group.setExclusive(True)
        for key, button in self.custom_theme_buttons.items():
            self.custom_theme_group.addButton(button)
            button.clicked.connect(
                lambda checked=False, current=key: self._set_custom_theme(current)
            )
        custom_theme_layout.addWidget(retrowave, 0, 0)
        custom_theme_layout.addWidget(dracula, 0, 1)
        custom_theme_layout.addWidget(caelestia, 1, 0)
        actions.addWidget(self.custom_theme_wrap)
        self.custom_theme_hint = QLabel(
            "Custom themes drive both Hanauta colors and the matching GTK theme."
        )
        self.custom_theme_hint.setObjectName("settingsStatus")
        self.custom_theme_hint.setFont(QFont(self.ui_font, 8))
        actions.addWidget(self.custom_theme_hint)
        actions.addStretch(1)
        hero.addWidget(actions_wrap, 8)
        layout.addWidget(hero_wrap)

        self.appearance_status = QLabel(
            "Built-in wallpaper import can pull from your Caelestia and End-4 wallpaper folders, including nested downloads."
        )
        self.appearance_status.setObjectName("settingsStatus")
        self.appearance_status.setFont(QFont(self.ui_font, 9))
        layout.addWidget(self.appearance_status)
        self.wallpaper_sync_progress = QProgressBar()
        self.wallpaper_sync_progress.setObjectName("settingsProgressBar")
        self.wallpaper_sync_progress.setRange(0, 0)
        self.wallpaper_sync_progress.setTextVisible(False)
        self.wallpaper_sync_progress.hide()
        layout.addWidget(self.wallpaper_sync_progress)

        self.slideshow_interval = QSlider(Qt.Orientation.Horizontal)
        self.slideshow_interval.setRange(5, 86400)
        self.slideshow_interval.setValue(
            int(self.settings_state["appearance"].get("slideshow_interval", 30))
        )
        self.slideshow_interval.setFixedWidth(164)
        self.slideshow_interval.valueChanged.connect(self._set_slideshow_interval)
        self.slideshow_interval_label = QLabel(
            self._format_slideshow_interval_text(
                int(self.settings_state["appearance"].get("slideshow_interval", 30))
            )
        )
        self.slideshow_interval_label.setFixedWidth(108)
        self.slideshow_interval_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.slideshow_interval_label.setStyleSheet("color: rgba(246,235,247,0.78);")
        slideshow_interval_wrap = QWidget()
        slideshow_interval_layout = QHBoxLayout(slideshow_interval_wrap)
        slideshow_interval_layout.setContentsMargins(0, 0, 0, 0)
        slideshow_interval_layout.setSpacing(10)
        slideshow_interval_layout.addWidget(self.slideshow_interval)
        slideshow_interval_layout.addWidget(self.slideshow_interval_label)

        transparency = SettingsRow(
            material_icon("opacity"),
            "Transparency",
            "Keep glass surfaces active across the shell.",
            self.icon_font,
            self.ui_font,
            self._make_transparency_switch(),
        )
        layout.addWidget(transparency)
        layout.addWidget(
            self._slider_settings_row(
                "Control center shell opacity",
                "Adjust the overall transparency of the notification center panel.",
                35,
                100,
                int(
                    self.settings_state["appearance"].get(
                        "notification_center_panel_opacity", 84
                    )
                ),
                material_icon("opacity"),
                "notification_center_panel_opacity",
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Control center widget opacity",
                "Control cards, sliders, quick actions, media, KDE Connect, and Home Assistant stay denser than the shell.",
                35,
                100,
                int(
                    self.settings_state["appearance"].get(
                        "notification_center_card_opacity", 92
                    )
                ),
                material_icon("widgets"),
                "notification_center_card_opacity",
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Notification max width",
                "Limit how wide desktop notifications can grow on screen.",
                260,
                640,
                int(
                    self.settings_state["appearance"].get(
                        "notification_toast_max_width", 356
                    )
                ),
                material_icon("crop_square"),
                "notification_toast_max_width",
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Notification max height",
                "Limit how tall desktop notifications can grow before content is clipped.",
                160,
                640,
                int(
                    self.settings_state["appearance"].get(
                        "notification_toast_max_height", 280
                    )
                ),
                material_icon("crop_square"),
                "notification_toast_max_height",
            )
        )
        interval = SettingsRow(
            material_icon("image"),
            "Slideshow interval",
            "Set how often folder slideshow rotates the wallpaper.",
            self.icon_font,
            self.ui_font,
            slideshow_interval_wrap,
        )
        matugen_button = QPushButton("Refresh palette")
        matugen_button.setObjectName("secondaryButton")
        matugen_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        matugen_button.clicked.connect(lambda: self._apply_matugen_palette(force=True))
        matugen = SettingsRow(
            material_icon("auto_awesome"),
            "Wallpaper-driven colors",
            "Use Matugen to generate a shared palette file for the dock and bar.",
            self.icon_font,
            self.ui_font,
            matugen_button,
        )
        self.matugen_notifications_switch = SwitchButton(
            bool(
                self.settings_state["appearance"].get(
                    "matugen_notifications_enabled", False
                )
            )
        )
        self.matugen_notifications_switch.toggledValue.connect(
            self._set_matugen_notifications_enabled
        )
        matugen_notifications = SettingsRow(
            material_icon("notifications_active"),
            "Matugen notifications",
            "Show a desktop notification when wallpaper-driven colors are refreshed.",
            self.icon_font,
            self.ui_font,
            self.matugen_notifications_switch,
        )
        self.wallpaper_change_notifications_switch = SwitchButton(
            bool(
                self.settings_state["appearance"].get(
                    "wallpaper_change_notifications_enabled", False
                )
            )
        )
        self.wallpaper_change_notifications_switch.toggledValue.connect(
            self._set_wallpaper_change_notifications_enabled
        )
        wallpaper_change_notifications = SettingsRow(
            material_icon("image"),
            "Wallpaper change notifications",
            "Show a desktop notification when Hanauta applies a new wallpaper.",
            self.icon_font,
            self.ui_font,
            self.wallpaper_change_notifications_switch,
        )
        layout.addWidget(interval)
        layout.addWidget(matugen)
        layout.addWidget(matugen_notifications)
        layout.addWidget(wallpaper_change_notifications)
        return card

    def _build_display_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(
            material_icon("desktop_windows"), self.icon_font, 15, "#F4EAF7"
        )
        icon.setFixedSize(22, 22)
        title = QLabel("Displays")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Primary monitor, extend or duplicate mode, resolution, refresh rate, and rotation."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        refresh_button.clicked.connect(self._refresh_display_state)
        apply_button = QPushButton("Apply displays")
        apply_button.setObjectName("primaryButton")
        apply_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        apply_button.clicked.connect(self._apply_display_settings)
        actions.addWidget(refresh_button)
        actions.addWidget(apply_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.display_status = QLabel("")
        self.display_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.display_status.setWordWrap(True)
        layout.addWidget(self.display_status)

        if not self.display_state:
            self.display_status.setText("No displays detected through xrandr.")
            return card

        connected_count = len(self.display_state)
        if connected_count > 1:
            layout.addWidget(self._build_display_global_card())
        else:
            self.display_status.setText(
                "Single display detected. Primary and mirror controls are hidden."
            )

        self.display_outputs_container = QVBoxLayout()
        self.display_outputs_container.setContentsMargins(0, 0, 0, 0)
        self.display_outputs_container.setSpacing(10)
        layout.addLayout(self.display_outputs_container)
        self._rebuild_display_output_cards()
        return card

    def _build_display_global_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsRow")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Multi-monitor layout")
        title.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        title.setStyleSheet("color: #FFFFFF;")
        detail = QLabel(
            "Choose the primary display and whether active outputs extend left-to-right or mirror the primary."
        )
        detail.setFont(QFont(self.ui_font, 8))
        detail.setStyleSheet("color: rgba(246,235,247,0.72);")
        detail.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(detail)

        row = QHBoxLayout()
        row.setSpacing(10)
        primary_label = QLabel("Primary")
        primary_label.setFont(QFont(self.ui_font, 9))
        primary_label.setStyleSheet("color: rgba(246,235,247,0.78);")
        self.primary_display_combo = QComboBox()
        self.primary_display_combo.setObjectName("settingsCombo")
        for display in self.display_state:
            self.primary_display_combo.addItem(display["name"])
        primary_name = next(
            (
                display["name"]
                for display in self.display_state
                if display.get("primary")
            ),
            self.display_state[0]["name"],
        )
        self.primary_display_combo.setCurrentText(primary_name)
        row.addWidget(primary_label)
        row.addWidget(self.primary_display_combo, 1)
        layout.addLayout(row)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.display_layout_buttons: dict[str, SegmentedChip] = {}
        self.display_layout_group = QButtonGroup(self)
        self.display_layout_group.setExclusive(True)
        for key, label in (("extend", "Extend"), ("duplicate", "Duplicate")):
            chip = SegmentedChip(label, checked=(key == "extend"))
            chip.clicked.connect(
                lambda checked=False, current=key: self._set_display_layout_mode(
                    current
                )
            )
            self.display_layout_group.addButton(chip)
            self.display_layout_buttons[key] = chip
            mode_row.addWidget(chip)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)
        self.display_layout_mode = "extend"
        self._set_display_layout_mode("extend")
        return card

    def _rebuild_display_output_cards(self) -> None:
        while self.display_outputs_container.count():
            item = self.display_outputs_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.display_controls = {}
        multi = len(self.display_state) > 1
        for display in self.display_state:
            card = QFrame()
            card.setObjectName("settingsRow")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            title_row = QHBoxLayout()
            title = QLabel(display["name"])
            title.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
            title.setStyleSheet("color: #FFFFFF;")
            desc_bits = []
            if display.get("primary"):
                desc_bits.append("Primary")
            desc_bits.append(
                "Active" if display.get("enabled") else "Connected but inactive"
            )
            subtitle = QLabel(" • ".join(desc_bits))
            subtitle.setFont(QFont(self.ui_font, 8))
            subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
            title_wrap = QVBoxLayout()
            title_wrap.setContentsMargins(0, 0, 0, 0)
            title_wrap.setSpacing(2)
            title_wrap.addWidget(title)
            title_wrap.addWidget(subtitle)
            title_row.addLayout(title_wrap)
            title_row.addStretch(1)
            layout.addLayout(title_row)

            control_grid = QGridLayout()
            control_grid.setContentsMargins(0, 0, 0, 0)
            control_grid.setHorizontalSpacing(10)
            control_grid.setVerticalSpacing(10)

            enabled_switch = SwitchButton(bool(display.get("enabled", True)))
            enabled_switch.setEnabled(multi)

            resolution_combo = QComboBox()
            resolution_combo.setObjectName("settingsCombo")
            for mode in display.get("modes", []):
                resolution_combo.addItem(mode)
            if display.get("current_mode"):
                resolution_combo.setCurrentText(display["current_mode"])

            refresh_combo = QComboBox()
            refresh_combo.setObjectName("settingsCombo")

            orientation_combo = QComboBox()
            orientation_combo.setObjectName("settingsCombo")
            for option in ("normal", "left", "right", "inverted"):
                orientation_combo.addItem(option)
            orientation_combo.setCurrentText(display.get("orientation", "normal"))

            wallpaper_combo = QComboBox()
            wallpaper_combo.setObjectName("settingsCombo")
            wallpaper_combo.blockSignals(True)
            for option in ("fill", "fit", "center", "stretch", "tile"):
                wallpaper_combo.addItem(option.title(), option)
            saved_mode = str(
                self.settings_state["appearance"]
                .get("wallpaper_fit_modes", {})
                .get(display["name"], "fill")
            )
            wallpaper_combo.setCurrentText(saved_mode.title())
            wallpaper_combo.blockSignals(False)
            wallpaper_combo.currentTextChanged.connect(
                lambda _text, current=display["name"], combo=wallpaper_combo: (
                    self._set_display_wallpaper_mode(
                        current,
                        str(combo.currentData() or combo.currentText().lower()),
                    )
                )
            )

            resolution_combo.currentTextChanged.connect(
                lambda mode, current=display["name"]: (
                    self._sync_refresh_rates_for_output(current, mode)
                )
            )
            self.display_controls[display["name"]] = {
                "enabled": enabled_switch,
                "resolution": resolution_combo,
                "refresh": refresh_combo,
                "orientation": orientation_combo,
                "wallpaper": wallpaper_combo,
            }
            self._sync_refresh_rates_for_output(
                display["name"], resolution_combo.currentText()
            )

            control_grid.addWidget(
                self._settings_labeled_field("Enabled", enabled_switch), 0, 0
            )
            control_grid.addWidget(
                self._settings_labeled_field("Resolution", resolution_combo), 0, 1
            )
            control_grid.addWidget(
                self._settings_labeled_field("Refresh", refresh_combo), 1, 0
            )
            control_grid.addWidget(
                self._settings_labeled_field("Orientation", orientation_combo), 1, 1
            )
            control_grid.addWidget(
                self._settings_labeled_field("Wallpaper", wallpaper_combo), 2, 0, 1, 2
            )
            layout.addLayout(control_grid)
            self.display_outputs_container.addWidget(card)

    def _settings_labeled_field(self, label_text: str, widget: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setFont(QFont(self.ui_font, 8))
        label.setStyleSheet("color: rgba(246,235,247,0.62);")
        layout.addWidget(label)
        layout.addWidget(widget)
        return wrap

    def _sync_refresh_rates_for_output(self, output_name: str, mode: str) -> None:
        controls = self.display_controls.get(output_name, {})
        refresh_combo = controls.get("refresh")
        if not isinstance(refresh_combo, QComboBox):
            return
        display = next(
            (item for item in self.display_state if item["name"] == output_name), None
        )
        if display is None:
            return
        refresh_combo.blockSignals(True)
        refresh_combo.clear()
        rates = list(display.get("refresh_rates", {}).get(mode, []))
        if not rates:
            refresh_combo.addItem("Auto")
        else:
            refresh_combo.addItem("Auto")
            for rate in rates:
                refresh_combo.addItem(rate)
            current_refresh = str(display.get("current_refresh", ""))
            if current_refresh and current_refresh in rates:
                refresh_combo.setCurrentText(current_refresh)
        refresh_combo.blockSignals(False)

    def _set_display_layout_mode(self, mode: str) -> None:
        self.display_layout_mode = mode
        for key, chip in getattr(self, "display_layout_buttons", {}).items():
            chip.setChecked(key == mode)

    def _set_display_wallpaper_mode(self, output_name: str, mode: str) -> None:
        fit_modes = self.settings_state["appearance"].setdefault(
            "wallpaper_fit_modes", {}
        )
        fit_modes[output_name] = mode
        save_settings_state(self.settings_state)
        self._apply_current_wallpaper_layout()

    def _monitor_choice_entries(self) -> list[tuple[str, str, str]]:
        entries: list[tuple[str, str, str]] = [
            ("Primary monitor", "primary", ""),
            ("Follow mouse", "follow_mouse", ""),
        ]
        names: list[str] = []
        for display in self.display_state:
            name = str(display.get("name", "")).strip()
            if name and name not in names:
                names.append(name)
        if not names:
            for screen in QGuiApplication.screens():
                name = screen.name().strip()
                if name and name not in names:
                    names.append(name)
        primary_name = next(
            (
                str(display.get("name", "")).strip()
                for display in self.display_state
                if display.get("primary")
            ),
            "",
        )
        for name in names:
            label = f"{name} (primary)" if name == primary_name else name
            entries.append((label, "named", name))
        return entries

    def _populate_monitor_target_combo(
        self, combo: QComboBox, mode: str, name: str
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        entries = self._monitor_choice_entries()
        target_index = 0
        normalized_mode = (
            mode if mode in {"primary", "follow_mouse", "named"} else "primary"
        )
        normalized_name = name.strip()
        for index, (label, entry_mode, entry_name) in enumerate(entries):
            combo.addItem(label, {"mode": entry_mode, "name": entry_name})
            if normalized_mode == entry_mode and normalized_name == entry_name:
                target_index = index
        if normalized_mode == "named" and normalized_name:
            for index in range(combo.count()):
                payload = combo.itemData(index)
                if (
                    isinstance(payload, dict)
                    and payload.get("mode") == "named"
                    and payload.get("name") == normalized_name
                ):
                    target_index = index
                    break
        combo.setCurrentIndex(target_index)
        combo.blockSignals(False)

    def _refresh_display_state(self) -> None:
        self.display_state = parse_xrandr_state()
        self.display_status.setText(
            "Display state refreshed from xrandr."
            if self.display_state
            else "No displays detected through xrandr."
        )
        if hasattr(self, "primary_display_combo"):
            self.primary_display_combo.clear()
            for display in self.display_state:
                self.primary_display_combo.addItem(display["name"])
            if self.display_state:
                saved_primary = str(
                    self.settings_state.get("display", {}).get("primary", "")
                )
                available_names = {display["name"] for display in self.display_state}
                if saved_primary in available_names:
                    primary_name = saved_primary
                else:
                    primary_name = next(
                        (
                            display["name"]
                            for display in self.display_state
                            if display.get("primary")
                        ),
                        self.display_state[0]["name"],
                    )
                self.primary_display_combo.setCurrentText(primary_name)
        saved_layout = str(
            self.settings_state.get("display", {}).get("layout_mode", "extend")
        )
        if saved_layout in {"extend", "duplicate"}:
            self._set_display_layout_mode(saved_layout)
        if hasattr(self, "bar_monitor_target_combo"):
            bar_settings = self.settings_state.get("bar", {})
            self._populate_monitor_target_combo(
                self.bar_monitor_target_combo,
                str(bar_settings.get("monitor_mode", "primary")).strip().lower(),
                str(bar_settings.get("monitor_name", "")).strip(),
            )
        if hasattr(self, "dock_monitor_target_combo"):
            dock_settings = self.dock_settings_state.get("dock", {})
            self._populate_monitor_target_combo(
                self.dock_monitor_target_combo,
                str(dock_settings.get("monitor_mode", "primary")).strip().lower(),
                str(dock_settings.get("monitor_name", "")).strip(),
            )
        self._rebuild_display_output_cards()

    def _collect_display_form_state(self) -> list[dict]:
        collected: list[dict] = []
        saved_outputs = {
            str(item.get("name", "")): item
            for item in self.settings_state.get("display", {}).get("outputs", [])
            if isinstance(item, dict)
        }
        for display in self.display_state:
            controls = self.display_controls.get(display["name"], {})
            enabled_widget = controls.get("enabled")
            resolution_widget = controls.get("resolution")
            refresh_widget = controls.get("refresh")
            orientation_widget = controls.get("orientation")
            saved = saved_outputs.get(display["name"], {})
            collected.append(
                {
                    "name": display["name"],
                    "enabled": bool(enabled_widget.isChecked())
                    if isinstance(enabled_widget, SwitchButton)
                    else bool(saved.get("enabled", display.get("enabled"))),
                    "resolution": resolution_widget.currentText()
                    if isinstance(resolution_widget, QComboBox)
                    else str(saved.get("resolution", display.get("current_mode", ""))),
                    "refresh": refresh_widget.currentText()
                    if isinstance(refresh_widget, QComboBox)
                    else str(saved.get("refresh", "Auto")),
                    "orientation": orientation_widget.currentText()
                    if isinstance(orientation_widget, QComboBox)
                    else str(
                        saved.get("orientation", display.get("orientation", "normal"))
                    ),
                    "modes": list(display.get("modes", [])),
                }
            )
        return collected

    def _apply_display_settings(self) -> None:
        displays = self._collect_display_form_state()
        enabled = [display for display in displays if display["enabled"]]
        if not enabled:
            self.display_status.setText("At least one display must stay enabled.")
            return

        primary_name = enabled[0]["name"]
        if len(self.display_state) > 1 and hasattr(self, "primary_display_combo"):
            primary_name = (
                self.primary_display_combo.currentText() or enabled[0]["name"]
            )
            if primary_name not in {display["name"] for display in enabled}:
                primary_name = enabled[0]["name"]

        if self.display_layout_mode == "duplicate" and len(enabled) > 1:
            common_modes = set(enabled[0]["modes"])
            for display in enabled[1:]:
                common_modes &= set(display["modes"])
            if not common_modes:
                self.display_status.setText(
                    "No shared resolution is available across enabled displays for duplicate mode."
                )
                return
            primary_display = next(
                display for display in enabled if display["name"] == primary_name
            )
            if primary_display["resolution"] not in common_modes:
                primary_display["resolution"] = sorted(
                    common_modes, key=resolution_area, reverse=True
                )[0]
            for display in enabled:
                display["resolution"] = primary_display["resolution"]
                if display["name"] != primary_name:
                    display["refresh"] = "Auto"

        cmd = build_display_command(displays, primary_name, self.display_layout_mode)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.display_status.setText(
                (
                    result.stderr
                    or result.stdout
                    or "Failed to apply display settings."
                ).strip()
            )
            return
        self.settings_state["display"] = {
            "layout_mode": self.display_layout_mode,
            "primary": primary_name,
            "outputs": [
                {
                    "name": display["name"],
                    "enabled": bool(display["enabled"]),
                    "resolution": str(display["resolution"]),
                    "refresh": str(display["refresh"]),
                    "orientation": str(display["orientation"]),
                }
                for display in displays
            ],
        }
        save_settings_state(self.settings_state)
        self.display_status.setText("Display layout applied.")
        self._refresh_display_state()
        self._apply_current_wallpaper_layout()

    def _build_picom_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("shadow"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Picom")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Core compositor behavior, shadows, opacity, and corners from picom.conf."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        apply_button = QPushButton("Apply picom")
        apply_button.setObjectName("primaryButton")
        apply_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        apply_button.clicked.connect(self._apply_picom_settings)
        restart_button = QPushButton("Restart picom")
        restart_button.setObjectName("secondaryButton")
        restart_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        restart_button.clicked.connect(self._restart_picom)
        rules_button = QPushButton("Open rule files")
        rules_button.setObjectName("secondaryButton")
        rules_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rules_button.clicked.connect(self._open_picom_rule_dir)
        reset_button = QPushButton("Reset defaults")
        reset_button.setObjectName("dangerButton")
        reset_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reset_button.clicked.connect(self._reset_picom_defaults)
        actions.addWidget(apply_button)
        actions.addWidget(restart_button)
        actions.addWidget(rules_button)
        actions.addWidget(reset_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.picom_status = QLabel("")
        self.picom_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.picom_status.setWordWrap(True)
        layout.addWidget(self.picom_status)

        self.picom_backend_combo = QComboBox()
        self.picom_backend_combo.setObjectName("settingsCombo")
        self.picom_backend_combo.addItems(["glx", "xrender"])
        self.picom_backend_combo.setCurrentText(
            str(self.picom_state.get("backend", "glx"))
        )

        self.picom_vsync_switch = SwitchButton(
            bool(self.picom_state.get("vsync", True))
        )
        self.picom_damage_switch = SwitchButton(
            bool(self.picom_state.get("use-damage", True))
        )
        self.picom_shadow_switch = SwitchButton(
            bool(self.picom_state.get("shadow", True))
        )
        self.picom_fading_switch = SwitchButton(
            bool(self.picom_state.get("fading", False))
        )
        self.picom_clip_switch = SwitchButton(
            bool(self.picom_state.get("transparent-clipping", False))
        )
        self.picom_rounded_switch = SwitchButton(
            bool(self.picom_state.get("detect-rounded-corners", True))
        )

        layout.addWidget(
            SettingsRow(
                material_icon("tune"),
                "Backend",
                "Choose the renderer used by picom.",
                self.icon_font,
                self.ui_font,
                self.picom_backend_combo,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("sync"),
                "VSync",
                "Reduce tearing by syncing frames.",
                self.icon_font,
                self.ui_font,
                self.picom_vsync_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Use damage",
                "Only redraw changed regions where possible.",
                self.icon_font,
                self.ui_font,
                self.picom_damage_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("shadow"),
                "Shadows",
                "Enable shadow rendering around windows.",
                self.icon_font,
                self.ui_font,
                self.picom_shadow_switch,
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Shadow radius",
                "Blur radius for shadows.",
                0,
                60,
                int(self.picom_state.get("shadow-radius", 18)),
                material_icon("shadow"),
                "picom_shadow_radius",
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Shadow opacity",
                "Overall shadow strength.",
                0,
                100,
                int(float(self.picom_state.get("shadow-opacity", 0.18)) * 100),
                material_icon("opacity"),
                "picom_shadow_opacity",
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Shadow offset X",
                "Horizontal shadow offset.",
                -40,
                40,
                int(self.picom_state.get("shadow-offset-x", -12)),
                material_icon("tune"),
                "picom_shadow_offset_x",
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Shadow offset Y",
                "Vertical shadow offset.",
                -40,
                40,
                int(self.picom_state.get("shadow-offset-y", -12)),
                material_icon("tune"),
                "picom_shadow_offset_y",
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("auto_awesome"),
                "Fading",
                "Fade transitions for mapped and unmapped windows.",
                self.icon_font,
                self.ui_font,
                self.picom_fading_switch,
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Active opacity",
                "Opacity for focused windows.",
                50,
                100,
                int(float(self.picom_state.get("active-opacity", 1.0)) * 100),
                material_icon("opacity"),
                "picom_active_opacity",
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Inactive opacity",
                "Opacity for unfocused windows.",
                50,
                100,
                int(float(self.picom_state.get("inactive-opacity", 1.0)) * 100),
                material_icon("opacity"),
                "picom_inactive_opacity",
            )
        )
        layout.addWidget(
            self._slider_settings_row(
                "Corner radius",
                "Rounded corner radius in pixels.",
                0,
                40,
                int(self.picom_state.get("corner-radius", 18)),
                material_icon("flip"),
                "picom_corner_radius",
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Transparent clipping",
                "Clip transparent pixels before drawing.",
                self.icon_font,
                self.ui_font,
                self.picom_clip_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Detect rounded corners",
                "Respect client-side rounded corners when available.",
                self.icon_font,
                self.ui_font,
                self.picom_rounded_switch,
            )
        )
        return card

    def _slider_settings_row(
        self,
        title: str,
        detail: str,
        minimum: int,
        maximum: int,
        value: int,
        icon: str,
        attr_prefix: str,
    ) -> QWidget:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setFixedWidth(180)
        label = QLabel(str(value))
        label.setFixedWidth(36)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("color: rgba(246,235,247,0.78);")
        slider.valueChanged.connect(
            lambda current, target=label: target.setText(str(current))
        )
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(slider)
        row.addWidget(label)
        setattr(self, f"{attr_prefix}_slider", slider)
        setattr(self, f"{attr_prefix}_label", label)
        return SettingsRow(icon, title, detail, self.icon_font, self.ui_font, wrap)

    def _build_bar_screen_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("dock_to_left"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Bar & screen")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        self.bar_launcher_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_launcher_offset_slider.setRange(-8, 8)
        self.bar_launcher_offset_slider.setValue(
            int(self.settings_state["bar"].get("launcher_offset", 0))
        )
        self.bar_launcher_offset_slider.setFixedWidth(164)
        self.bar_launcher_offset_slider.valueChanged.connect(
            self._set_bar_launcher_offset
        )

        self.bar_workspace_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_workspace_offset_slider.setRange(-8, 8)
        self.bar_workspace_offset_slider.setValue(
            int(self.settings_state["bar"].get("workspace_offset", 0))
        )
        self.bar_workspace_offset_slider.setFixedWidth(164)
        self.bar_workspace_offset_slider.valueChanged.connect(
            self._set_bar_workspace_offset
        )

        self.bar_workspace_count_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_workspace_count_slider.setRange(1, 10)
        self.bar_workspace_count_slider.setValue(
            int(self.settings_state["bar"].get("workspace_count", 5))
        )
        self.bar_workspace_count_slider.setFixedWidth(164)
        self.bar_workspace_count_slider.valueChanged.connect(
            self._set_bar_workspace_count
        )

        self.bar_workspace_label_switch = SwitchButton(
            bool(self.settings_state["bar"].get("show_workspace_label", False))
        )
        self.bar_workspace_label_switch.toggledValue.connect(
            self._set_bar_show_workspace_label
        )

        self.bar_datetime_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_datetime_offset_slider.setRange(-8, 8)
        self.bar_datetime_offset_slider.setValue(
            int(self.settings_state["bar"].get("datetime_offset", 0))
        )
        self.bar_datetime_offset_slider.setFixedWidth(164)
        self.bar_datetime_offset_slider.valueChanged.connect(
            self._set_bar_datetime_offset
        )

        self.bar_media_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_media_offset_slider.setRange(-8, 8)
        self.bar_media_offset_slider.setValue(
            int(self.settings_state["bar"].get("media_offset", 0))
        )
        self.bar_media_offset_slider.setFixedWidth(164)
        self.bar_media_offset_slider.valueChanged.connect(self._set_bar_media_offset)

        self.bar_status_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_status_offset_slider.setRange(-8, 8)
        self.bar_status_offset_slider.setValue(
            int(self.settings_state["bar"].get("status_offset", 0))
        )
        self.bar_status_offset_slider.setFixedWidth(164)
        self.bar_status_offset_slider.valueChanged.connect(self._set_bar_status_offset)

        self.bar_tray_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_tray_offset_slider.setRange(-8, 8)
        self.bar_tray_offset_slider.setValue(
            int(self.settings_state["bar"].get("tray_offset", 0))
        )
        self.bar_tray_offset_slider.setFixedWidth(164)
        self.bar_tray_offset_slider.valueChanged.connect(self._set_bar_tray_offset)

        self.bar_status_icon_limit_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_status_icon_limit_slider.setRange(4, 48)
        self.bar_status_icon_limit_slider.setValue(
            int(self.settings_state["bar"].get("status_icon_limit", 14))
        )
        self.bar_status_icon_limit_slider.setFixedWidth(164)
        self.bar_status_icon_limit_slider.valueChanged.connect(
            self._set_bar_status_icon_limit
        )

        self.bar_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_height_slider.setRange(32, 72)
        self.bar_height_slider.setValue(
            int(self.settings_state["bar"].get("bar_height", 40))
        )
        self.bar_height_slider.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.bar_height_slider.setInvertedAppearance(False)
        self.bar_height_slider.setInvertedControls(False)
        self.bar_height_slider.setFixedWidth(164)
        self.bar_height_slider.valueChanged.connect(self._set_bar_height)

        self.bar_chip_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_chip_radius_slider.setRange(0, 32)
        self.bar_chip_radius_slider.setValue(
            int(self.settings_state["bar"].get("chip_radius", 0))
        )
        self.bar_chip_radius_slider.setFixedWidth(164)
        self.bar_chip_radius_slider.valueChanged.connect(self._set_bar_chip_radius)

        self.bar_full_merge_switch = SwitchButton(
            bool(self.settings_state["bar"].get("merge_all_chips", False))
        )
        self.bar_full_merge_switch.toggledValue.connect(self._set_bar_merge_all_chips)

        self.bar_tray_tint_switch = SwitchButton(
            bool(self.settings_state["bar"].get("tray_tint_with_matugen", True))
        )
        self.bar_tray_tint_switch.toggledValue.connect(
            self._set_bar_tray_tint_with_matugen
        )
        self.bar_color_widget_icons_switch = SwitchButton(
            bool(self.settings_state["bar"].get("use_color_widget_icons", False))
        )
        self.bar_color_widget_icons_switch.toggledValue.connect(
            self._set_bar_use_color_widget_icons
        )
        self.bar_debug_tooltips_switch = SwitchButton(
            bool(self.settings_state["bar"].get("debug_tooltips", False))
        )
        self.bar_debug_tooltips_switch.toggledValue.connect(
            self._set_bar_debug_tooltips
        )

        self.bar_monitor_target_combo = QComboBox()
        self.bar_monitor_target_combo.setFixedWidth(220)
        self._populate_monitor_target_combo(
            self.bar_monitor_target_combo,
            str(self.settings_state["bar"].get("monitor_mode", "primary"))
            .strip()
            .lower(),
            str(self.settings_state["bar"].get("monitor_name", "")).strip(),
        )
        self.bar_monitor_target_combo.currentIndexChanged.connect(
            self._set_bar_monitor_target
        )
        self.bar_orientation_combo = QComboBox()
        self.bar_orientation_combo.setFixedWidth(220)
        self.bar_orientation_combo.setObjectName("settingsCombo")
        orientation_items = [
            ("Horizontal (Top)", "horizontal_top"),
            ("Vertical (Left)", "vertical_left"),
            ("Vertical (Right)", "vertical_right"),
        ]
        for label, value in orientation_items:
            self.bar_orientation_combo.addItem(label, value)
        current_orientation = str(
            self.settings_state["bar"].get("orientation_mode", "horizontal_top")
        ).strip().lower()
        selected_index = 0
        for idx, (_label, value) in enumerate(orientation_items):
            if value == current_orientation:
                selected_index = idx
                break
        self.bar_orientation_combo.setCurrentIndex(selected_index)
        self.bar_orientation_combo.currentIndexChanged.connect(
            self._set_bar_orientation_mode
        )

        self.dock_monitor_target_combo = QComboBox()
        self.dock_monitor_target_combo.setFixedWidth(220)
        dock_monitor_settings = self.dock_settings_state.get("dock", {})
        self._populate_monitor_target_combo(
            self.dock_monitor_target_combo,
            str(dock_monitor_settings.get("monitor_mode", "primary")).strip().lower(),
            str(dock_monitor_settings.get("monitor_name", "")).strip(),
        )
        self.dock_monitor_target_combo.currentIndexChanged.connect(
            self._set_dock_monitor_target
        )

        self.bar_full_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_full_radius_slider.setRange(0, 32)
        self.bar_full_radius_slider.setValue(
            int(self.settings_state["bar"].get("full_bar_radius", 18))
        )
        self.bar_full_radius_slider.setFixedWidth(164)
        self.bar_full_radius_slider.valueChanged.connect(self._set_bar_full_radius)

        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Launcher / AI offset",
                "Move the AI icon and launcher block up or down without changing their internal alignment.",
                self.icon_font,
                self.ui_font,
                self.bar_launcher_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Workspace offset",
                "Move the workspace block up or down as a whole.",
                self.icon_font,
                self.ui_font,
                self.bar_workspace_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("window"),
                "Workspace count",
                "Choose how many workspace dots the bar should show, from 1 up to 10.",
                self.icon_font,
                self.ui_font,
                self.bar_workspace_count_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("toggle_on"),
                "Show workspace label",
                "Show or hide the text label like Workspace 1 before the workspace dots.",
                self.icon_font,
                self.ui_font,
                self.bar_workspace_label_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Date/time offset",
                "Move the clock and date block up or down as a whole.",
                self.icon_font,
                self.ui_font,
                self.bar_datetime_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Media offset",
                "Move the now playing block up or down as a whole.",
                self.icon_font,
                self.ui_font,
                self.bar_media_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Status offset",
                "Move the network, battery, tray, and power block up or down as a whole.",
                self.icon_font,
                self.ui_font,
                self.bar_status_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Tray offset",
                "Nudge only the tray icons up or down to line them up with the rest of the status icons.",
                self.icon_font,
                self.ui_font,
                self.bar_tray_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("palette"),
                "Tint tray icons",
                "Tint tray icons with the current Matugen primary color when the Matugen palette is enabled.",
                self.icon_font,
                self.ui_font,
                self.bar_tray_tint_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("palette"),
                "Use color widget icons",
                "When enabled, bar widgets prefer icon_color.svg.\n"
                "When disabled, Hanauta prefers icon.svg and tints it like control-center icons.",
                self.icon_font,
                self.ui_font,
                self.bar_color_widget_icons_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("toggle_on"),
                "Debug icon tooltips",
                "Show internal debug labels on bar icons and chips to help inspect widget identity and placement.",
                self.icon_font,
                self.ui_font,
                self.bar_debug_tooltips_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Visible status icon limit",
                "How many status/tray widgets stay on the bar before extra icons move into the overflow dropdown.",
                self.icon_font,
                self.ui_font,
                self.bar_status_icon_limit_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("dock_to_left"),
                "Bar height",
                "Increase or reduce the overall bar height whether you use separate chips or the merged full bar.",
                self.icon_font,
                self.ui_font,
                self.bar_height_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Chip corner radius",
                "Adjust how square or rounded the bar chips should be.",
                self.icon_font,
                self.ui_font,
                self.bar_chip_radius_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("dock_to_left"),
                "Merge chips into full bar",
                "Blend the separate chips into one continuous bar surface.",
                self.icon_font,
                self.ui_font,
                self.bar_full_merge_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Bar orientation",
                "Choose top horizontal bar or vertical sidebar docked on the left/right. Vertical mode starts with the AI launcher section at the top.",
                self.icon_font,
                self.ui_font,
                self.bar_orientation_combo,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Bar monitor",
                "Choose whether the bar should stay on the primary monitor, follow the mouse, or lock to one output.",
                self.icon_font,
                self.ui_font,
                self.bar_monitor_target_combo,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("desktop_windows"),
                "Dock monitor",
                "Choose where the PyQt dock should appear when it starts and when it repositions itself.",
                self.icon_font,
                self.ui_font,
                self.dock_monitor_target_combo,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Full bar corner radius",
                "When full bar mode is enabled, choose how rounded the overall bar should be.",
                self.icon_font,
                self.ui_font,
                self.bar_full_radius_slider,
            )
        )

        rice_button = QPushButton("Open icon config")
        rice_button.setObjectName("secondaryButton")
        rice_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rice_button.clicked.connect(self._open_bar_icon_config)
        layout.addWidget(
            SettingsRow(
                material_icon("sports_esports"),
                "Bar icon overrides",
                "Rice the bar by editing ~/.config/hanauta/bar-icons.json.\n"
                "Hanauta reloads the file automatically.",
                self.icon_font,
                self.ui_font,
                rice_button,
            )
        )
        layout.addWidget(self._build_bar_service_icons_section())

        polybar_header = QHBoxLayout()
        polybar_icon = IconLabel(
            material_icon("widgets"), self.icon_font, 13, "#F4EAF7"
        )
        polybar_icon.setFixedSize(18, 18)
        polybar_title = QLabel("Polybar Widgets")
        polybar_title.setFont(QFont(self.ui_font, 10, QFont.Weight.Bold))
        polybar_title.setStyleSheet("color: rgba(246,235,247,0.85);")
        polybar_header.addWidget(polybar_icon)
        polybar_header.addWidget(polybar_title)
        polybar_header.addStretch(1)
        layout.addLayout(polybar_header)

        polybar_subtitle = QLabel(
            "Add polybar-compatible custom widgets to hanauta bar."
        )
        polybar_subtitle.setFont(QFont(self.ui_font, 9))
        polybar_subtitle.setStyleSheet("color: rgba(246,235,247,0.56);")
        layout.addWidget(polybar_subtitle)

        self.polybar_widgets_list = QListWidget()
        self.polybar_widgets_list.setObjectName("settingsList")
        polybar_widgets = self.settings_state["bar"].get("polybar_widgets", [])
        for widget in polybar_widgets:
            item = QListWidgetItem(str(widget))
            self.polybar_widgets_list.addItem(item)
        layout.addWidget(self.polybar_widgets_list)

        polybar_buttons = QHBoxLayout()
        polybar_buttons.setSpacing(8)
        add_widget_button = QPushButton("Add Widget")
        add_widget_button.setObjectName("secondaryButton")
        add_widget_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_widget_button.clicked.connect(self._add_polybar_widget)
        remove_widget_button = QPushButton("Remove")
        remove_widget_button.setObjectName("dangerButton")
        remove_widget_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        remove_widget_button.clicked.connect(self._remove_polybar_widget)
        polybar_buttons.addWidget(add_widget_button)
        polybar_buttons.addWidget(remove_widget_button)
        polybar_buttons.addStretch(1)
        layout.addLayout(polybar_buttons)

        return card

    def _read_bar_service_rows_cache(self) -> list[dict[str, object]]:
        payload = load_service_cache_json("plugins/bar-services.json")
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return []
        normalized: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key", "")).strip()
            if not key:
                continue
            if not bool(row.get("supports_show_in_bar", False)):
                continue
            normalized.append(
                {
                    "key": key,
                    "label": str(row.get("label", key.replace("_", " ").title())).strip()
                    or key.replace("_", " ").title(),
                    "icon": str(row.get("icon", "widgets")).strip() or "widgets",
                    "source": "service",
                }
            )
        deduped: dict[str, dict[str, object]] = {}
        for row in normalized:
            key = str(row.get("key", "")).strip()
            if key and key not in deduped:
                deduped[key] = row
        return [deduped[key] for key in sorted(deduped.keys())]

    def _queue_bar_service_cache_refresh(self) -> None:
        if bool(getattr(self, "_bar_service_cache_refresh_queued", False)):
            return
        script = ROOT / "hanauta" / "scripts" / "cache_bar_services.py"
        if not script.exists():
            return
        self._bar_service_cache_refresh_queued = True
        python_bin = python_executable()

        def _run_refresh() -> None:
            try:
                run_bg([python_bin, str(script)])
            finally:
                self._bar_service_cache_refresh_queued = False

        QTimer.singleShot(0, _run_refresh)

    def _read_services_section_rows_cache(self) -> list[dict[str, object]]:
        payload = load_service_cache_json("plugins/services-sections.json")
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return []
        deduped: dict[str, dict[str, object]] = {}
        normalized: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key", "")).strip()
            plugin_dir = str(row.get("plugin_dir", "")).strip()
            if not key or not plugin_dir:
                continue
            deduped[key] = {
                "key": key,
                "label": str(row.get("label", "")).strip()
                or key.replace("_", " ").title(),
                "plugin_dir": plugin_dir,
                "plugin_id": str(row.get("plugin_id", "")).strip(),
                "plugin_name": str(row.get("plugin_name", "")).strip(),
            }
        for key in sorted(deduped.keys()):
            normalized.append(deduped[key])
        return normalized

    def _queue_services_section_cache_refresh(self) -> None:
        if bool(getattr(self, "_services_section_cache_refresh_queued", False)):
            return
        script = ROOT / "hanauta" / "scripts" / "cache_services_sections.py"
        if not script.exists():
            return
        self._services_section_cache_refresh_queued = True
        python_bin = python_executable()

        def _run_refresh() -> None:
            try:
                run_bg([python_bin, str(script)])
            finally:
                self._services_section_cache_refresh_queued = False

        QTimer.singleShot(0, _run_refresh)

    def _cached_service_plugin_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        seen: set[str] = set()
        for row in self._read_services_section_rows_cache():
            plugin_dir_raw = str(row.get("plugin_dir", "")).strip()
            if not plugin_dir_raw:
                continue
            plugin_dir = Path(plugin_dir_raw).expanduser()
            if not plugin_dir.exists():
                continue
            resolved = str(plugin_dir.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            dirs.append(plugin_dir)
        return dirs

    def _plugin_bar_service_rows(self) -> list[dict[str, object]]:
        rows = self._read_bar_service_rows_cache()
        if rows:
            return rows
        self._queue_bar_service_cache_refresh()
        return []

    def _bar_service_icon_candidates(self) -> list[dict[str, object]]:
        entries: dict[str, dict[str, object]] = {}
        services = self.settings_state.setdefault("services", {})
        if not isinstance(services, dict):
            services = {}
            self.settings_state["services"] = services

        for key, (label, icon_name) in BAR_SERVICE_ICON_META.items():
            entries[key] = {
                "key": key,
                "label": label,
                "icon": icon_name,
                "source": "service",
            }

        for row in self._plugin_bar_service_rows():
            key = str(row.get("key", "")).strip()
            if not key or key in entries:
                continue
            entries[key] = dict(row)

        # Fallback for plugin services that already exist in settings but are not
        # present in cache yet.
        for key, service in services.items():
            if key in entries:
                continue
            if not isinstance(service, dict):
                continue
            if "show_in_bar" not in service:
                continue
            entries[key] = {
                "key": key,
                "label": key.replace("_", " ").strip().title(),
                "icon": "widgets",
                "source": "service",
            }

        entries["ntfy"] = {
            "key": "ntfy",
            "label": "ntfy",
            "icon": "notifications",
            "source": "ntfy",
        }
        return list(entries.values())

    def _bar_service_icon_enabled(self, key: str, source: str) -> bool:
        if source == "ntfy":
            ntfy = self.settings_state.setdefault("ntfy", {})
            if not isinstance(ntfy, dict):
                return False
            return bool(ntfy.get("enabled", False) and ntfy.get("show_in_bar", False))
        service = self.settings_state.setdefault("services", {}).get(key, {})
        if not isinstance(service, dict):
            return False
        return bool(service.get("enabled", True) and service.get("show_in_bar", False))

    def _normalized_bar_service_icon_order(
        self, candidate_keys: list[str]
    ) -> list[str]:
        bar = self.settings_state.setdefault("bar", {})
        if not isinstance(bar, dict):
            bar = {}
            self.settings_state["bar"] = bar
        raw_order = bar.get("service_icon_order", [])
        normalized: list[str] = []
        if isinstance(raw_order, list):
            for item in raw_order:
                key = str(item).strip()
                if key and key in candidate_keys and key not in normalized:
                    normalized.append(key)
        for key in candidate_keys:
            if key not in normalized:
                normalized.append(key)
        return normalized

    def _save_bar_service_icon_order(self, order: list[str]) -> None:
        bar = self.settings_state.setdefault("bar", {})
        if not isinstance(bar, dict):
            bar = {}
            self.settings_state["bar"] = bar
        bar["service_icon_order"] = [str(item).strip() for item in order if str(item).strip()]
        save_settings_state(self.settings_state)

    def _build_bar_service_icons_section(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsRow")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Service icons on bar")
        title.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        title.setStyleSheet("color: #FFFFFF;")
        subtitle = QLabel(
            "Manage bar-visible service icons. Move items one-by-one and toggle visibility. This stays synced with each service's Show on bar switch."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self._bar_service_icon_rows_host = QFrame()
        self._bar_service_icon_rows_host.setObjectName("settingsRow")
        host_layout = QVBoxLayout(self._bar_service_icon_rows_host)
        host_layout.setContentsMargins(8, 8, 8, 8)
        host_layout.setSpacing(6)
        self._bar_service_icon_rows_layout = host_layout
        layout.addWidget(self._bar_service_icon_rows_host)

        self._bar_service_icon_syncing = False
        self._bar_service_icon_rows: dict[str, dict[str, object]] = {}
        self._refresh_bar_service_icon_rows()
        QTimer.singleShot(1200, self._refresh_bar_service_icon_rows)
        return card

    def _refresh_bar_service_icon_rows(self) -> None:
        rows_layout = getattr(self, "_bar_service_icon_rows_layout", None)
        if not isinstance(rows_layout, QVBoxLayout):
            return
        while rows_layout.count():
            item = rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        candidates = self._bar_service_icon_candidates()
        candidate_map = {
            str(row.get("key", "")).strip(): row
            for row in candidates
            if str(row.get("key", "")).strip()
        }
        order = self._normalized_bar_service_icon_order(list(candidate_map.keys()))
        self._save_bar_service_icon_order(order)

        ordered_rows = [candidate_map[key] for key in order if key in candidate_map]
        self._bar_service_icon_rows = {}

        for index, row in enumerate(ordered_rows):
            key = str(row.get("key", "")).strip()
            label = str(row.get("label", key)).strip() or key
            icon_name = str(row.get("icon", "widgets")).strip() or "widgets"
            source = str(row.get("source", "service")).strip() or "service"
            enabled = self._bar_service_icon_enabled(key, source)

            line = QFrame()
            line.setObjectName("settingsRow")
            line_layout = QHBoxLayout(line)
            line_layout.setContentsMargins(8, 6, 8, 6)
            line_layout.setSpacing(8)

            icon = IconLabel(material_icon(icon_name), self.icon_font, 14, "#F4EAF7")
            icon.setFixedSize(20, 20)
            line_layout.addWidget(icon)

            text = QLabel(label)
            text.setStyleSheet("color: rgba(246,235,247,0.88);")
            line_layout.addWidget(text, 1)

            up_btn = QPushButton("Up")
            up_btn.setObjectName("secondaryButton")
            up_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            up_btn.setEnabled(index > 0)
            up_btn.clicked.connect(
                lambda _checked=False, current=key: self._move_bar_service_icon(
                    current, -1
                )
            )
            line_layout.addWidget(up_btn)

            down_btn = QPushButton("Down")
            down_btn.setObjectName("secondaryButton")
            down_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            down_btn.setEnabled(index < len(ordered_rows) - 1)
            down_btn.clicked.connect(
                lambda _checked=False, current=key: self._move_bar_service_icon(
                    current, 1
                )
            )
            line_layout.addWidget(down_btn)

            toggle = SwitchButton(enabled)
            toggle.toggledValue.connect(
                lambda value, current=key: self._set_bar_service_icon_visibility_from_manager(
                    current, value
                )
            )
            line_layout.addWidget(toggle)

            rows_layout.addWidget(line)
            self._bar_service_icon_rows[key] = {
                "switch": toggle,
                "up": up_btn,
                "down": down_btn,
            }

    def _move_bar_service_icon(self, key: str, delta: int) -> None:
        candidates = self._bar_service_icon_candidates()
        keys = [str(row.get("key", "")).strip() for row in candidates if str(row.get("key", "")).strip()]
        order = self._normalized_bar_service_icon_order(keys)
        if key not in order:
            return
        current_index = order.index(key)
        target_index = max(0, min(len(order) - 1, current_index + int(delta)))
        if current_index == target_index:
            return
        order[current_index], order[target_index] = order[target_index], order[current_index]
        self._save_bar_service_icon_order(order)
        self._refresh_bar_service_icon_rows()

    def _set_bar_service_icon_visibility_from_manager(
        self, key: str, enabled: bool
    ) -> None:
        if bool(getattr(self, "_bar_service_icon_syncing", False)):
            return
        self._bar_service_icon_syncing = True
        try:
            if key == "ntfy":
                self._set_ntfy_show_in_bar(enabled)
            else:
                self._set_service_bar_visibility(key, enabled)
        finally:
            self._bar_service_icon_syncing = False
        self._refresh_bar_service_icon_rows()

    def _build_energy_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("bolt"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Energy & power")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Idle locking, power actions, brightness, and battery health in one place."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.energy_refresh_button = QPushButton("Refresh energy")
        self.energy_refresh_button.setObjectName("secondaryButton")
        self.energy_refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.energy_refresh_button.clicked.connect(self._refresh_energy_state)
        actions.addWidget(self.energy_refresh_button)

        self.energy_lock_button = QPushButton("Lock now")
        self.energy_lock_button.setObjectName("secondaryButton")
        self.energy_lock_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.energy_lock_button.clicked.connect(self._lock_now)
        actions.addWidget(self.energy_lock_button)

        self.energy_suspend_button = QPushButton("Suspend")
        self.energy_suspend_button.setObjectName("secondaryButton")
        self.energy_suspend_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.energy_suspend_button.clicked.connect(self._suspend_now)
        actions.addWidget(self.energy_suspend_button)

        self.energy_hibernate_button = QPushButton("Hibernate")
        self.energy_hibernate_button.setObjectName("secondaryButton")
        self.energy_hibernate_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.energy_hibernate_button.clicked.connect(self._hibernate_now)
        self.energy_hibernate_button.setEnabled(shutil.which("systemctl") is not None)
        actions.addWidget(self.energy_hibernate_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.energy_status = QLabel("Energy controls are ready.")
        self.energy_status.setWordWrap(True)
        self.energy_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.energy_status)

        self.autolock_enabled_switch = SwitchButton(
            bool(self.settings_state.get("autolock", {}).get("enabled", True))
        )
        self.autolock_enabled_switch.toggledValue.connect(self._set_autolock_enabled)
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Auto lock",
                "Lock the PC after the chosen idle time. Turning on caffeine in the notification center pauses this until caffeine is disabled.",
                self.icon_font,
                self.ui_font,
                self.autolock_enabled_switch,
            )
        )

        self.autolock_timeout_input = QLineEdit(
            str(int(self.settings_state.get("autolock", {}).get("timeout_minutes", 2)))
        )
        self.autolock_timeout_input.setValidator(QIntValidator(1, 60, self))
        self.autolock_timeout_input.setFixedWidth(88)
        self.autolock_timeout_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.autolock_timeout_input.editingFinished.connect(
            self._set_autolock_timeout_minutes_from_input
        )
        self.autolock_timeout_input.setEnabled(
            bool(self.settings_state.get("autolock", {}).get("enabled", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("timer"),
                "Auto lock timeout",
                "How many idle minutes Hanauta waits before locking the session.",
                self.icon_font,
                self.ui_font,
                self.autolock_timeout_input,
            )
        )

        lockscreen = self.settings_state.get("lockscreen", {})
        self.lockscreen_blur_switch = SwitchButton(
            bool(lockscreen.get("blur_screenshot", False))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("photo_library"),
                "Blur screenshot background",
                "Capture the current screen and blur it before locking. Disable for faster lock entry.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_blur_switch,
            )
        )

        self.lockscreen_pause_media_switch = SwitchButton(
            bool(lockscreen.get("pause_media_on_lock", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("music_note"),
                "Pause media on lock",
                "Pause active media players before the lock screen appears.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_pause_media_switch,
            )
        )

        self.lockscreen_slow_fade_switch = SwitchButton(
            bool(lockscreen.get("use_slow_fade", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("opacity"),
                "Use compositor slow fade",
                "Temporarily slow compositor fade in/out while locking.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_slow_fade_switch,
            )
        )

        self.lockscreen_prefer_color_switch = SwitchButton(
            bool(lockscreen.get("prefer_i3lock_color", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("palette"),
                "Prefer i3lock-color",
                "Use i3lock-color first when available; fall back to plain i3lock otherwise.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_prefer_color_switch,
            )
        )

        self.lockscreen_show_clock_switch = SwitchButton(
            bool(lockscreen.get("show_clock", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Show lock clock",
                "Render time/date on the lockscreen.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_show_clock_switch,
            )
        )

        self.lockscreen_show_indicator_switch = SwitchButton(
            bool(lockscreen.get("show_indicator", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Show lock indicator ring",
                "Show the circular indicator for typing/verifying state.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_show_indicator_switch,
            )
        )

        self.lockscreen_pass_media_switch = SwitchButton(
            bool(lockscreen.get("pass_media_keys", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("music_note"),
                "Pass media keys",
                "Allow media keys (play/pause/next/prev) while locked.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_pass_media_switch,
            )
        )

        self.lockscreen_pass_volume_switch = SwitchButton(
            bool(lockscreen.get("pass_volume_keys", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("tune"),
                "Pass volume keys",
                "Allow volume keys while locked.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_pass_volume_switch,
            )
        )

        self.lockscreen_refresh_input = QLineEdit(
            str(int(lockscreen.get("refresh_rate", 1)))
        )
        self.lockscreen_refresh_input.setValidator(QIntValidator(0, 30, self))
        self.lockscreen_refresh_input.setFixedWidth(88)
        self.lockscreen_refresh_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Refresh rate",
                "i3lock refresh rate. Lower values are lighter; 0 disables periodic refresh.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_refresh_input,
            )
        )

        self.lockscreen_ring_radius_input = QLineEdit(
            str(int(lockscreen.get("ring_radius", 28)))
        )
        self.lockscreen_ring_radius_input.setValidator(QIntValidator(8, 80, self))
        self.lockscreen_ring_radius_input.setFixedWidth(88)
        self.lockscreen_ring_radius_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Ring radius",
                "Indicator ring radius in pixels.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_ring_radius_input,
            )
        )

        self.lockscreen_ring_width_input = QLineEdit(
            str(int(lockscreen.get("ring_width", 6)))
        )
        self.lockscreen_ring_width_input.setValidator(QIntValidator(1, 24, self))
        self.lockscreen_ring_width_input.setFixedWidth(88)
        self.lockscreen_ring_width_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Ring width",
                "Indicator ring thickness in pixels.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_ring_width_input,
            )
        )

        self.lockscreen_time_format_input = QLineEdit(
            str(lockscreen.get("time_format", "%H:%M"))
        )
        self.lockscreen_time_format_input.setPlaceholderText("%H:%M")
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Time format",
                "strftime format string for lockscreen time.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_time_format_input,
            )
        )

        self.lockscreen_date_format_input = QLineEdit(
            str(lockscreen.get("date_format", "%A, %d %B %Y"))
        )
        self.lockscreen_date_format_input.setPlaceholderText("%A, %d %B %Y")
        layout.addWidget(
            SettingsRow(
                material_icon("calendar_month"),
                "Date format",
                "strftime format string for lockscreen date.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_date_format_input,
            )
        )

        self.lockscreen_greeter_text_input = QLineEdit(
            str(
                lockscreen.get(
                    "greeter_text", "Hanauta locked • Type your password to unlock"
                )
            )
        )
        self.lockscreen_greeter_text_input.setPlaceholderText(
            "Hanauta locked • Type your password to unlock"
        )
        layout.addWidget(
            SettingsRow(
                material_icon("description"),
                "Greeter text",
                "Main lockscreen message shown before typing.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_greeter_text_input,
            )
        )

        self.lockscreen_verifying_text_input = QLineEdit(
            str(lockscreen.get("verifying_text", "Verifying..."))
        )
        self.lockscreen_verifying_text_input.setPlaceholderText("Verifying...")
        layout.addWidget(
            SettingsRow(
                material_icon("description"),
                "Verifying text",
                "Message shown while password verification is in progress.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_verifying_text_input,
            )
        )

        self.lockscreen_wrong_text_input = QLineEdit(
            str(lockscreen.get("wrong_text", "Wrong password"))
        )
        self.lockscreen_wrong_text_input.setPlaceholderText("Wrong password")
        layout.addWidget(
            SettingsRow(
                material_icon("description"),
                "Wrong password text",
                "Message shown after an incorrect password.",
                self.icon_font,
                self.ui_font,
                self.lockscreen_wrong_text_input,
            )
        )

        self.lockscreen_status = QLabel("Lockscreen options are ready.")
        self.lockscreen_status.setWordWrap(True)
        self.lockscreen_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.lockscreen_status)

        self.lockscreen_save_button = QPushButton("Save lockscreen settings")
        self.lockscreen_save_button.setObjectName("primaryButton")
        self.lockscreen_save_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.lockscreen_save_button.clicked.connect(self._save_lockscreen_settings)
        layout.addWidget(self.lockscreen_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        brightness_wrap = QWidget()
        brightness_row = QHBoxLayout(brightness_wrap)
        brightness_row.setContentsMargins(0, 0, 0, 0)
        brightness_row.setSpacing(8)
        self.energy_brightness_input = QLineEdit("0")
        self.energy_brightness_input.setValidator(QIntValidator(1, 100, self))
        self.energy_brightness_input.setFixedWidth(88)
        self.energy_brightness_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.energy_brightness_input.editingFinished.connect(
            self._apply_energy_brightness
        )
        self.energy_brightness_apply_button = QPushButton("Apply")
        self.energy_brightness_apply_button.setObjectName("secondaryButton")
        self.energy_brightness_apply_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.energy_brightness_apply_button.clicked.connect(
            self._apply_energy_brightness
        )
        brightness_row.addWidget(self.energy_brightness_input)
        brightness_row.addWidget(self.energy_brightness_apply_button)
        layout.addWidget(
            SettingsRow(
                material_icon("lightbulb"),
                "Brightness",
                "Quick display brightness override in percent using Hanauta's shared brightness script.",
                self.icon_font,
                self.ui_font,
                brightness_wrap,
            )
        )

        self.energy_caffeine_note = QLabel(
            "Caffeine wins over auto lock. If you need the PC to stay awake temporarily, use the notification center caffeine toggle instead of disabling auto lock permanently."
        )
        self.energy_caffeine_note.setWordWrap(True)
        self.energy_caffeine_note.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.energy_caffeine_note)

        self.energy_battery_section = QFrame()
        self.energy_battery_section.setObjectName("serviceSection")
        battery_layout = QVBoxLayout(self.energy_battery_section)
        battery_layout.setContentsMargins(12, 12, 12, 12)
        battery_layout.setSpacing(10)

        self.energy_battery_header = QPushButton()
        self.energy_battery_header.setObjectName("serviceHeaderButton")
        self.energy_battery_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.energy_battery_header.setMinimumHeight(84)
        self.energy_battery_header.clicked.connect(self._toggle_energy_battery_section)
        battery_header = QHBoxLayout(self.energy_battery_header)
        battery_header.setContentsMargins(14, 14, 14, 14)
        battery_header.setSpacing(12)

        battery_icon_wrap = QFrame()
        battery_icon_wrap.setObjectName("rowIconWrap")
        battery_icon_wrap.setFixedSize(32, 32)
        battery_icon_layout = QVBoxLayout(battery_icon_wrap)
        battery_icon_layout.setContentsMargins(0, 0, 0, 0)
        self.energy_battery_icon = QLabel(material_icon("monitor_heart"))
        self.energy_battery_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.energy_battery_icon.setFont(QFont(self.icon_font, 16))
        self.energy_battery_icon.setProperty("iconRole", True)
        battery_icon_layout.addWidget(self.energy_battery_icon)

        battery_text_wrap = QVBoxLayout()
        battery_text_wrap.setContentsMargins(0, 0, 0, 0)
        battery_text_wrap.setSpacing(5)
        self.energy_battery_title = QLabel("Battery")
        self.energy_battery_title.setWordWrap(True)
        self.energy_battery_title.setFont(
            QFont(self.ui_font, 12, QFont.Weight.DemiBold)
        )
        self.energy_battery_title.setStyleSheet(
            "color: #FFFFFF; background: transparent;"
        )
        self.energy_battery_summary = QLabel("")
        self.energy_battery_summary.setWordWrap(True)
        self.energy_battery_summary.setFont(QFont(self.ui_font, 9))
        self.energy_battery_summary.setStyleSheet(
            "color: rgba(255,255,255,0.80); background: transparent;"
        )
        battery_text_wrap.addWidget(self.energy_battery_title)
        battery_text_wrap.addWidget(self.energy_battery_summary)

        battery_trailing = QHBoxLayout()
        battery_trailing.setContentsMargins(0, 0, 0, 0)
        battery_trailing.setSpacing(8)
        self.energy_battery_chevron = QLabel(material_icon("expand_more"))
        self.energy_battery_chevron.setObjectName("serviceChevron")
        self.energy_battery_chevron.setFont(QFont(self.icon_font, 18))
        self.energy_battery_chevron.setProperty("iconRole", True)
        battery_trailing.addWidget(self.energy_battery_chevron)

        battery_header.addWidget(battery_icon_wrap)
        battery_header.addLayout(battery_text_wrap, 1)
        battery_header.addLayout(battery_trailing)
        battery_layout.addWidget(self.energy_battery_header)

        self.energy_battery_content = QWidget()
        battery_content_layout = QVBoxLayout(self.energy_battery_content)
        battery_content_layout.setContentsMargins(0, 0, 0, 0)
        battery_content_layout.setSpacing(10)

        battery_grid = QGridLayout()
        battery_grid.setContentsMargins(0, 0, 0, 0)
        battery_grid.setHorizontalSpacing(10)
        battery_grid.setVerticalSpacing(10)
        self.energy_battery_labels: dict[str, QLabel] = {}
        for index, key in enumerate(("Charge", "State", "Health", "Cycles")):
            label = QLabel("...")
            label.setFont(QFont(self.ui_font, 10))
            label.setStyleSheet("color: #FFFFFF;")
            self.energy_battery_labels[key] = label
            battery_grid.addWidget(self._metric_card(key, label), index // 2, index % 2)
        battery_content_layout.addLayout(battery_grid)

        self.energy_battery_meta = QLabel("")
        self.energy_battery_meta.setWordWrap(True)
        self.energy_battery_meta.setStyleSheet("color: rgba(246,235,247,0.72);")
        battery_content_layout.addWidget(self.energy_battery_meta)

        battery_layout.addWidget(self.energy_battery_content)
        layout.addWidget(self.energy_battery_section)

        self._refresh_energy_state()
        return card

    def _build_audio_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("music_note"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Audio")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Default output, mic input, alert sounds, and how Hanauta should behave when audio focus changes."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        self.audio_sink_combo = QComboBox()
        self.audio_sink_combo.setObjectName("settingsCombo")
        layout.addWidget(
            SettingsRow(
                material_icon("music_note"),
                "Default sink",
                "Choose the default playback device for new apps.",
                self.icon_font,
                self.ui_font,
                self.audio_sink_combo,
            )
        )

        self.audio_source_combo = QComboBox()
        self.audio_source_combo.setObjectName("settingsCombo")
        layout.addWidget(
            SettingsRow(
                material_icon("monitor_heart"),
                "Microphone source",
                "Choose the default capture device for voice apps and recordings.",
                self.icon_font,
                self.ui_font,
                self.audio_source_combo,
            )
        )

        self.audio_alert_sounds_switch = SwitchButton(
            bool(self.settings_state["audio"].get("alert_sounds_enabled", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications"),
                "Alert sounds",
                "Allow notification and reminder sounds when supported by the widget or daemon.",
                self.icon_font,
                self.ui_font,
                self.audio_alert_sounds_switch,
            )
        )

        self.audio_route_switch = SwitchButton(
            bool(
                self.settings_state["audio"].get("route_new_apps_to_default_sink", True)
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("hub"),
                "Route new apps to default sink",
                "Prefer the selected sink for fresh app launches instead of leaving routing entirely to PulseAudio defaults.",
                self.icon_font,
                self.ui_font,
                self.audio_route_switch,
            )
        )

        self.audio_mute_behavior_combo = QComboBox()
        self.audio_mute_behavior_combo.setObjectName("settingsCombo")
        self.audio_mute_behavior_combo.addItem("Leave as is", "leave_as_is")
        self.audio_mute_behavior_combo.addItem("Mute on lock", "mute_on_lock")
        self.audio_mute_behavior_combo.addItem("Mute on suspend", "mute_on_suspend")
        mute_behavior = str(
            self.settings_state["audio"].get("mute_behavior", "leave_as_is")
        )
        mute_index = self.audio_mute_behavior_combo.findData(mute_behavior)
        self.audio_mute_behavior_combo.setCurrentIndex(max(0, mute_index))
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Mute behavior",
                "What Hanauta should prefer to do when you lock or suspend the session.",
                self.icon_font,
                self.ui_font,
                self.audio_mute_behavior_combo,
            )
        )

        self.audio_status = QLabel("Audio routing is ready.")
        self.audio_status.setWordWrap(True)
        self.audio_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.audio_status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.audio_refresh_button = QPushButton("Refresh devices")
        self.audio_refresh_button.setObjectName("secondaryButton")
        self.audio_refresh_button.clicked.connect(self._refresh_audio_devices)
        self.audio_save_button = QPushButton("Apply audio settings")
        self.audio_save_button.setObjectName("primaryButton")
        self.audio_save_button.clicked.connect(self._save_audio_settings)
        for button in (self.audio_refresh_button, self.audio_save_button):
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        buttons.addWidget(self.audio_refresh_button)
        buttons.addWidget(self.audio_save_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self._refresh_audio_devices()
        return card

    def _build_notifications_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("notifications"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Notifications")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Global toast behavior, history sizing, urgency preferences, and per-app rule entry points."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        self.notifications_history_limit_input = QLineEdit(
            str(int(self.settings_state["notifications"].get("history_limit", 150)))
        )
        self.notifications_history_limit_input.setValidator(
            QIntValidator(10, 1000, self)
        )
        self.notifications_history_limit_input.setFixedWidth(96)
        self.notifications_history_limit_input.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(
            SettingsRow(
                material_icon("storage"),
                "History limit",
                "How many notifications Hanauta should aim to keep in recent history views.",
                self.icon_font,
                self.ui_font,
                self.notifications_history_limit_input,
            )
        )

        self.notifications_urgency_combo = QComboBox()
        self.notifications_urgency_combo.setObjectName("settingsCombo")
        self.notifications_urgency_combo.addItem("All", "all")
        self.notifications_urgency_combo.addItem("Normal and critical", "normal")
        self.notifications_urgency_combo.addItem("Critical only", "critical_only")
        urgency = str(
            self.settings_state["notifications"].get("urgency_policy", "normal")
        )
        urgency_index = self.notifications_urgency_combo.findData(urgency)
        self.notifications_urgency_combo.setCurrentIndex(max(0, urgency_index))
        layout.addWidget(
            SettingsRow(
                material_icon("warning"),
                "Urgency policy",
                "A policy note for which notifications should interrupt you most aggressively.",
                self.icon_font,
                self.ui_font,
                self.notifications_urgency_combo,
            )
        )

        self.notifications_pause_share_switch = SwitchButton(
            bool(self.settings_state["notifications"].get("pause_while_sharing", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("videocam"),
                "Pause while sharing",
                "Prefer quieter notifications while you are screen sharing or presenting.",
                self.icon_font,
                self.ui_font,
                self.notifications_pause_share_switch,
            )
        )

        self.notifications_rules_switch = SwitchButton(
            bool(
                self.settings_state["notifications"].get("per_app_rules_enabled", True)
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("settings"),
                "Per-app overrides",
                "Keep app-specific notification rules enabled through Hanauta's shared rules file.",
                self.icon_font,
                self.ui_font,
                self.notifications_rules_switch,
            )
        )

        self.notifications_default_duration_input = QLineEdit(
            str(
                int(
                    self.settings_state["notifications"].get(
                        "default_duration_ms", 10000
                    )
                )
            )
        )
        self.notifications_default_duration_input.setValidator(
            QIntValidator(2000, 120000, self)
        )
        self.notifications_default_duration_input.setFixedWidth(96)
        self.notifications_default_duration_input.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Default toast duration (ms)",
                "Minimum time desktop notifications stay visible before auto-dismiss.",
                self.icon_font,
                self.ui_font,
                self.notifications_default_duration_input,
            )
        )

        self.notifications_lock_osd_position_combo = QComboBox()
        self.notifications_lock_osd_position_combo.setObjectName("settingsCombo")
        self.notifications_lock_osd_position_combo.addItem("Top left", "top_left")
        self.notifications_lock_osd_position_combo.addItem("Top center", "top_center")
        self.notifications_lock_osd_position_combo.addItem("Top right", "top_right")
        self.notifications_lock_osd_position_combo.addItem(
            "Center left", "center_left"
        )
        self.notifications_lock_osd_position_combo.addItem("Center", "center")
        self.notifications_lock_osd_position_combo.addItem(
            "Center right", "center_right"
        )
        self.notifications_lock_osd_position_combo.addItem(
            "Bottom left", "bottom_left"
        )
        self.notifications_lock_osd_position_combo.addItem(
            "Bottom center", "bottom_center"
        )
        self.notifications_lock_osd_position_combo.addItem(
            "Bottom right", "bottom_right"
        )
        lock_osd_position = str(
            self.settings_state["notifications"].get(
                "lock_osd_position", "bottom_center"
            )
        )
        lock_osd_index = self.notifications_lock_osd_position_combo.findData(
            lock_osd_position
        )
        self.notifications_lock_osd_position_combo.setCurrentIndex(
            max(0, lock_osd_index)
        )
        self.notifications_lock_osd_enabled_switch = SwitchButton(
            bool(
                self.settings_state["notifications"].get("lock_osd_enabled", True)
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("toggle_on"),
                "Caps/Num lock OSD",
                "Enable lock-state on-screen popups for Caps Lock and Num Lock.",
                self.icon_font,
                self.ui_font,
                self.notifications_lock_osd_enabled_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Caps/Num OSD position",
                "Choose where lock-state popups appear on screen.",
                self.icon_font,
                self.ui_font,
                self.notifications_lock_osd_position_combo,
            )
        )

        self.notifications_toast_width_input = QLineEdit(
            str(
                int(
                    self.settings_state["appearance"].get(
                        "notification_toast_max_width", 356
                    )
                )
            )
        )
        self.notifications_toast_width_input.setValidator(QIntValidator(260, 640, self))
        self.notifications_toast_width_input.setFixedWidth(96)
        self.notifications_toast_width_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Toast max width",
                "Limit how wide desktop notifications are allowed to grow.",
                self.icon_font,
                self.ui_font,
                self.notifications_toast_width_input,
            )
        )

        self.notifications_toast_height_input = QLineEdit(
            str(
                int(
                    self.settings_state["appearance"].get(
                        "notification_toast_max_height", 280
                    )
                )
            )
        )
        self.notifications_toast_height_input.setValidator(
            QIntValidator(160, 640, self)
        )
        self.notifications_toast_height_input.setFixedWidth(96)
        self.notifications_toast_height_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Toast max height",
                "Limit how tall desktop notifications can grow before clipping.",
                self.icon_font,
                self.ui_font,
                self.notifications_toast_height_input,
            )
        )

        rules_row = QWidget()
        rules_layout = QHBoxLayout(rules_row)
        rules_layout.setContentsMargins(0, 0, 0, 0)
        rules_layout.setSpacing(8)
        rules_path_label = QLabel(str(NOTIFICATION_RULES_FILE))
        rules_path_label.setWordWrap(True)
        rules_path_label.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.notifications_open_rules_button = QPushButton("Open rules")
        self.notifications_open_rules_button.setObjectName("secondaryButton")
        self.notifications_open_rules_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.notifications_open_rules_button.clicked.connect(
            lambda: run_bg(["xdg-open", str(NOTIFICATION_RULES_FILE)])
        )
        rules_layout.addWidget(rules_path_label, 1)
        rules_layout.addWidget(self.notifications_open_rules_button)
        layout.addWidget(
            SettingsRow(
                material_icon("settings"),
                "Rules file",
                "Direct path to Hanauta's per-app notification overrides.",
                self.icon_font,
                self.ui_font,
                rules_row,
            )
        )

        self.notifications_status = QLabel("Notification routing is ready.")
        self.notifications_status.setWordWrap(True)
        self.notifications_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.notifications_status)

        save_button = QPushButton("Save notification settings")
        save_button.setObjectName("primaryButton")
        save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_button.clicked.connect(self._save_notifications_page_settings)
        layout.addWidget(save_button, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _normalize_keyboard_layout_value(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "us"
        text = " ".join(part for part in text.split() if part)
        return text or "us"

    def _resolve_keyboard_layout_value(self) -> str:
        combo = getattr(self, "input_keyboard_layout_combo", None)
        if not isinstance(combo, QComboBox):
            return "us"
        text = combo.currentText().strip()
        if hasattr(self, "_keyboard_layout_label_to_value"):
            label_map = getattr(self, "_keyboard_layout_label_to_value", {})
            if isinstance(label_map, dict):
                mapped = label_map.get(text)
                if isinstance(mapped, str) and mapped.strip():
                    return self._normalize_keyboard_layout_value(mapped)
        if text:
            lowered = text.casefold()
            for _label, layout_value in KEYBOARD_LAYOUT_PRESETS:
                if lowered == layout_value.casefold():
                    return self._normalize_keyboard_layout_value(layout_value)
            if " - " in text:
                suffix = text.rsplit(" - ", 1)[-1].strip()
                if suffix:
                    return self._normalize_keyboard_layout_value(suffix)
            return self._normalize_keyboard_layout_value(text)
        data = combo.currentData()
        if isinstance(data, str) and data.strip():
            return self._normalize_keyboard_layout_value(data)
        return "us"

    def _resolve_region_keyboard_layout_value(self) -> str:
        combo = getattr(self, "region_keyboard_layout_combo", None)
        if not isinstance(combo, QComboBox):
            return self._normalize_keyboard_layout_value(
                str(self.settings_state.get("region", {}).get("keyboard_layout", "us"))
            )
        text = combo.currentText().strip()
        if hasattr(self, "_region_keyboard_layout_label_to_value"):
            label_map = getattr(self, "_region_keyboard_layout_label_to_value", {})
            if isinstance(label_map, dict):
                mapped = label_map.get(text)
                if isinstance(mapped, str) and mapped.strip():
                    return self._normalize_keyboard_layout_value(mapped)
        if text:
            lowered = text.casefold()
            for _label, layout_value in KEYBOARD_LAYOUT_PRESETS:
                if lowered == layout_value.casefold():
                    return self._normalize_keyboard_layout_value(layout_value)
            if " - " in text:
                suffix = text.rsplit(" - ", 1)[-1].strip()
                if suffix:
                    return self._normalize_keyboard_layout_value(suffix)
            return self._normalize_keyboard_layout_value(text)
        data = combo.currentData()
        if isinstance(data, str) and data.strip():
            return self._normalize_keyboard_layout_value(data)
        return self._normalize_keyboard_layout_value(
            str(self.settings_state.get("region", {}).get("keyboard_layout", "us"))
        )

    def _apply_keyboard_layout(self, value: str) -> None:
        if shutil.which("setxkbmap") is None:
            return
        normalized = self._normalize_keyboard_layout_value(value)
        parts = normalized.split(maxsplit=1)
        command = ["setxkbmap", parts[0]]
        if len(parts) > 1 and parts[1].strip():
            command.extend(["-variant", parts[1].strip()])
        run_bg(command)

    def _build_input_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("language"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Input")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Keyboard repeat, layout switching, touchpad preferences, and mouse feel."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        self.input_keyboard_layout_combo = QComboBox()
        self.input_keyboard_layout_combo.setObjectName("settingsCombo")
        self.input_keyboard_layout_combo.setEditable(True)
        self.input_keyboard_layout_combo.setInsertPolicy(
            QComboBox.InsertPolicy.NoInsert
        )
        self._keyboard_layout_label_to_value: dict[str, str] = {}
        labels: list[str] = []
        for label, layout_value in KEYBOARD_LAYOUT_PRESETS:
            self.input_keyboard_layout_combo.addItem(label, layout_value)
            self._keyboard_layout_label_to_value[label] = layout_value
            labels.append(label)
        completer_model = QStringListModel(labels, self)
        self.input_keyboard_layout_completer = QCompleter(completer_model, self)
        self.input_keyboard_layout_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.input_keyboard_layout_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.input_keyboard_layout_combo.setCompleter(
            self.input_keyboard_layout_completer
        )
        current_layout = self._normalize_keyboard_layout_value(
            str(self.settings_state["input"].get("keyboard_layout", "us"))
        )
        current_index = self.input_keyboard_layout_combo.findData(current_layout)
        if current_index >= 0:
            self.input_keyboard_layout_combo.setCurrentIndex(current_index)
        else:
            self.input_keyboard_layout_combo.setCurrentText(current_layout)
        layout.addWidget(
            SettingsRow(
                material_icon("language"),
                "Keyboard language",
                "Choose a layout by language name. Hanauta saves and applies it to the current i3 session.",
                self.icon_font,
                self.ui_font,
                self.input_keyboard_layout_combo,
            )
        )

        self.input_repeat_delay_input = QLineEdit(
            str(int(self.settings_state["input"].get("repeat_delay_ms", 300)))
        )
        self.input_repeat_delay_input.setValidator(QIntValidator(150, 1200, self))
        self.input_repeat_delay_input.setFixedWidth(96)
        self.input_repeat_delay_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("timer"),
                "Repeat delay (ms)",
                "How long the keyboard waits before repeating a held key.",
                self.icon_font,
                self.ui_font,
                self.input_repeat_delay_input,
            )
        )

        self.input_repeat_rate_input = QLineEdit(
            str(int(self.settings_state["input"].get("repeat_rate", 30)))
        )
        self.input_repeat_rate_input.setValidator(QIntValidator(10, 60, self))
        self.input_repeat_rate_input.setFixedWidth(96)
        self.input_repeat_rate_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("timer"),
                "Repeat rate",
                "Approximate repeat rate used with xset for keyboard repeats.",
                self.icon_font,
                self.ui_font,
                self.input_repeat_rate_input,
            )
        )

        self.input_tap_to_click_switch = SwitchButton(
            bool(self.settings_state["input"].get("tap_to_click", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Touchpad tap to click",
                "Save whether touchpad taps should act as left clicks.",
                self.icon_font,
                self.ui_font,
                self.input_tap_to_click_switch,
            )
        )

        self.input_natural_scroll_switch = SwitchButton(
            bool(self.settings_state["input"].get("natural_scroll", False))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Natural scroll",
                "Prefer content-following scroll direction for touchpads and mice where supported.",
                self.icon_font,
                self.ui_font,
                self.input_natural_scroll_switch,
            )
        )

        self.input_mouse_accel_input = QLineEdit(
            str(int(self.settings_state["input"].get("mouse_accel", 0)))
        )
        self.input_mouse_accel_input.setValidator(QIntValidator(-10, 10, self))
        self.input_mouse_accel_input.setFixedWidth(96)
        self.input_mouse_accel_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("tune"),
                "Mouse acceleration",
                "Signed adjustment placeholder for your preferred mouse feel.",
                self.icon_font,
                self.ui_font,
                self.input_mouse_accel_input,
            )
        )

        self.input_status = QLabel("Input preferences are ready.")
        self.input_status.setWordWrap(True)
        self.input_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.input_status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        apply_button = QPushButton("Apply now")
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self._save_input_settings)
        buttons.addWidget(apply_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return card

    def _build_startup_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("restart_alt"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Startup")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "What the session should restore, how long it should wait, and whether extra hooks should watch the shell."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        startup_settings = self.settings_state["startup"]
        self.startup_bar_switch = SwitchButton(
            bool(startup_settings.get("launch_bar", True))
        )
        self.startup_dock_switch = SwitchButton(
            bool(startup_settings.get("launch_dock", True))
        )
        self.startup_wallpaper_switch = SwitchButton(
            bool(startup_settings.get("restore_wallpaper", True))
        )
        self.startup_displays_switch = SwitchButton(
            bool(startup_settings.get("restore_displays", True))
        )
        self.startup_vpn_switch = SwitchButton(
            bool(startup_settings.get("restore_vpn", True))
        )
        self.startup_restart_hooks_switch = SwitchButton(
            bool(startup_settings.get("restart_hooks_enabled", True))
        )
        self.startup_watchdog_switch = SwitchButton(
            bool(startup_settings.get("watchdog_enabled", False))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Launch bar",
                "Remember that the PyQt bar should start with the session.",
                self.icon_font,
                self.ui_font,
                self.startup_bar_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("dock_to_left"),
                "Launch dock",
                "Remember that the PyQt dock should start with the session.",
                self.icon_font,
                self.ui_font,
                self.startup_dock_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("image"),
                "Restore wallpaper",
                "Reapply the saved wallpaper layout at startup.",
                self.icon_font,
                self.ui_font,
                self.startup_wallpaper_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("desktop_windows"),
                "Restore displays",
                "Reapply the saved display layout at startup.",
                self.icon_font,
                self.ui_font,
                self.startup_displays_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Restore VPN",
                "Reconnect the preferred WireGuard tunnel when allowed.",
                self.icon_font,
                self.ui_font,
                self.startup_vpn_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Restart hooks",
                "Persist whether restart-time helper hooks should be treated as enabled.",
                self.icon_font,
                self.ui_font,
                self.startup_restart_hooks_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("warning"),
                "Watchdogs",
                "Persist whether watchdog-style startup checks should be considered enabled.",
                self.icon_font,
                self.ui_font,
                self.startup_watchdog_switch,
            )
        )

        self.startup_delay_input = QLineEdit(
            str(int(startup_settings.get("startup_delay_seconds", 0)))
        )
        self.startup_delay_input.setValidator(QIntValidator(0, 120, self))
        self.startup_delay_input.setFixedWidth(96)
        self.startup_delay_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("timer"),
                "Startup delay (sec)",
                "Optional delay before heavyweight startup work kicks in.",
                self.icon_font,
                self.ui_font,
                self.startup_delay_input,
            )
        )

        startup_lines = startup_exec_lines(ROOT)
        startup_preview = (
            "\n".join(startup_lines[:8])
            if startup_lines
            else "No startup commands were detected."
        )
        self.startup_preview_label = QLabel(startup_preview)
        self.startup_preview_label.setWordWrap(True)
        self.startup_preview_label.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.startup_preview_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        open_button = QPushButton("Open startup.sh")
        open_button.setObjectName("secondaryButton")
        open_button.clicked.connect(
            lambda: run_bg(["xdg-open", str(ROOT / "startup.sh")])
        )
        save_button = QPushButton("Save startup settings")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save_startup_settings)
        for button in (open_button, save_button):
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        buttons.addWidget(open_button)
        buttons.addWidget(save_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        startup_apps_header = QHBoxLayout()
        startup_apps_icon = IconLabel(
            material_icon("apps"), self.icon_font, 13, "#F4EAF7"
        )
        startup_apps_icon.setFixedSize(18, 18)
        startup_apps_title = QLabel("Startup Apps")
        startup_apps_title.setFont(QFont(self.ui_font, 10, QFont.Weight.Bold))
        startup_apps_title.setStyleSheet("color: rgba(246,235,247,0.85);")
        startup_apps_header.addWidget(startup_apps_icon)
        startup_apps_header.addWidget(startup_apps_title)
        startup_apps_header.addStretch(1)
        layout.addLayout(startup_apps_header)

        startup_apps_subtitle = QLabel(
            "Add apps or commands to run when i3/hyprland starts."
        )
        startup_apps_subtitle.setFont(QFont(self.ui_font, 9))
        startup_apps_subtitle.setStyleSheet("color: rgba(246,235,247,0.56);")
        layout.addWidget(startup_apps_subtitle)

        self.startup_apps_list = QListWidget()
        self.startup_apps_list.setObjectName("startupAppsList")
        self.startup_apps_list.setFrameShape(QFrame.Shape.NoFrame)
        startup_apps = startup_settings.get("startup_apps", [])
        for app in startup_apps:
            item = QListWidgetItem(str(app))
            self.startup_apps_list.addItem(item)

        startup_list_wrap = QFrame()
        startup_list_wrap.setObjectName("startupAppsListWrap")
        startup_list_layout = QVBoxLayout(startup_list_wrap)
        startup_list_layout.setContentsMargins(8, 8, 8, 8)
        startup_list_layout.setSpacing(0)
        startup_list_layout.addWidget(self.startup_apps_list)
        layout.addWidget(startup_list_wrap)

        startup_apps_buttons = QHBoxLayout()
        startup_apps_buttons.setSpacing(8)
        add_app_button = QPushButton("Add App/Command")
        add_app_button.setObjectName("secondaryButton")
        add_app_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_app_button.clicked.connect(self._add_startup_app)
        remove_app_button = QPushButton("Remove")
        remove_app_button.setObjectName("dangerButton")
        remove_app_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        remove_app_button.clicked.connect(self._remove_startup_app)
        startup_apps_buttons.addWidget(add_app_button)
        startup_apps_buttons.addWidget(remove_app_button)
        startup_apps_buttons.addStretch(1)
        layout.addLayout(startup_apps_buttons)

        self.startup_status = QLabel("Startup preferences are ready.")
        self.startup_status.setWordWrap(True)
        self.startup_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.startup_status)
        return card

    def _build_privacy_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("shield"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Privacy")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Hide sensitive content, lock more aggressively, and soften what leaks during screenshots or screen sharing."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        privacy = self.settings_state["privacy"]
        self.privacy_lock_suspend_switch = SwitchButton(
            bool(privacy.get("lock_on_suspend", True))
        )
        self.privacy_hide_content_switch = SwitchButton(
            bool(privacy.get("hide_notification_content_global", False))
        )
        self.privacy_pause_share_switch = SwitchButton(
            bool(privacy.get("pause_notifications_while_sharing", True))
        )
        self.privacy_screenshot_guard_switch = SwitchButton(
            bool(privacy.get("screenshot_guard_enabled", False))
        )
        self.privacy_screen_share_guard_switch = SwitchButton(
            bool(privacy.get("screen_share_guard_enabled", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Lock on suspend",
                "Remember that suspending the PC should be treated as a privacy boundary.",
                self.icon_font,
                self.ui_font,
                self.privacy_lock_suspend_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("visibility_off"),
                "Hide notification content globally",
                "Apply a privacy-first notification preference across Hanauta-owned alerts.",
                self.icon_font,
                self.ui_font,
                self.privacy_hide_content_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("videocam"),
                "Pause while sharing",
                "Prefer muting or softening notifications while screen sharing.",
                self.icon_font,
                self.ui_font,
                self.privacy_pause_share_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("photo_library"),
                "Screenshot guard",
                "Remember a preference to hide or reduce sensitive surfaces during screenshots.",
                self.icon_font,
                self.ui_font,
                self.privacy_screenshot_guard_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("shield"),
                "Screen-share safeguard",
                "Keep the stronger privacy preference when screen-sharing tools are active.",
                self.icon_font,
                self.ui_font,
                self.privacy_screen_share_guard_switch,
            )
        )

        self.privacy_status = QLabel("Privacy preferences are ready.")
        self.privacy_status.setWordWrap(True)
        self.privacy_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.privacy_status)

        save_button = QPushButton("Save privacy settings")
        save_button.setObjectName("primaryButton")
        save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_button.clicked.connect(self._save_privacy_settings)
        layout.addWidget(save_button, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_networking_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("hub"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Networking")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Preferred Wi-Fi and VPN interfaces, reconnect behavior, and split-tunnel notes."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        self.networking_wifi_combo = QComboBox()
        self.networking_wifi_combo.setObjectName("settingsCombo")
        self.networking_wifi_combo.addItem("Automatic", "")
        for iface in list_wifi_interfaces():
            self.networking_wifi_combo.addItem(iface, iface)
        wifi_pref = str(
            self.settings_state["networking"].get("preferred_wifi_interface", "")
        )
        wifi_idx = self.networking_wifi_combo.findData(wifi_pref)
        self.networking_wifi_combo.setCurrentIndex(max(0, wifi_idx))
        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "Preferred Wi-Fi interface",
                "Prefer one wireless interface when multiple are available.",
                self.icon_font,
                self.ui_font,
                self.networking_wifi_combo,
            )
        )

        self.networking_wifi_autoconnect_switch = SwitchButton(
            bool(self.settings_state["networking"].get("wifi_autoconnect", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Wi-Fi autoconnect",
                "Remember whether Wi-Fi should reconnect automatically when possible.",
                self.icon_font,
                self.ui_font,
                self.networking_wifi_autoconnect_switch,
            )
        )

        self.networking_wg_combo = QComboBox()
        self.networking_wg_combo.setObjectName("settingsCombo")
        self.networking_wg_combo.addItem("Automatic", "")
        for iface in list_wireguard_interfaces(ROOT):
            self.networking_wg_combo.addItem(iface, iface)
        wg_pref = str(
            self.settings_state["networking"].get(
                "preferred_wireguard_interface",
                self.settings_state["services"]
                .get("vpn_control", {})
                .get("preferred_interface", ""),
            )
        )
        wg_idx = self.networking_wg_combo.findData(wg_pref)
        self.networking_wg_combo.setCurrentIndex(max(0, wg_idx))
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Preferred WireGuard interface",
                "Keep one tunnel selected for reconnect actions and the VPN widget.",
                self.icon_font,
                self.ui_font,
                self.networking_wg_combo,
            )
        )

        vpn_reconnect = bool(
            self.settings_state["networking"].get(
                "vpn_reconnect_on_login",
                self.settings_state["services"]
                .get("vpn_control", {})
                .get("reconnect_on_login", False),
            )
        )
        self.networking_vpn_reconnect_switch = SwitchButton(vpn_reconnect)
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Reconnect VPN on login",
                "Restore the preferred WireGuard tunnel at session start when enabled.",
                self.icon_font,
                self.ui_font,
                self.networking_vpn_reconnect_switch,
            )
        )

        split_tunnel = self.settings_state["networking"].get(
            "split_tunnel_apps",
            self.settings_state["services"]
            .get("vpn_control", {})
            .get("split_tunnel_apps", []),
        )
        split_tunnel_text = ", ".join(
            [str(item).strip() for item in split_tunnel if str(item).strip()]
        )
        self.networking_split_tunnel_input = QLineEdit(split_tunnel_text)
        self.networking_split_tunnel_input.setPlaceholderText("discord, steam, firefox")
        layout.addWidget(
            SettingsRow(
                material_icon("hub"),
                "Split-tunnel apps",
                "Comma-separated app names or desktop ids to remember for future VPN routing work.",
                self.icon_font,
                self.ui_font,
                self.networking_split_tunnel_input,
            )
        )

        self.networking_status = QLabel("Networking preferences are ready.")
        self.networking_status.setWordWrap(True)
        self.networking_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.networking_status)

        save_button = QPushButton("Save networking settings")
        save_button.setObjectName("primaryButton")
        save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_button.clicked.connect(self._save_networking_settings)
        layout.addWidget(save_button, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_storage_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("storage"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Storage")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Cache sizes, cleanup policies, wallpaper source data, and temporary Hanauta state."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        self.storage_cache_cleanup_days_input = QLineEdit(
            str(
                int(
                    self.settings_state["storage"].get(
                        "wallpaper_cache_cleanup_days", 30
                    )
                )
            )
        )
        self.storage_cache_cleanup_days_input.setValidator(QIntValidator(1, 365, self))
        self.storage_cache_cleanup_days_input.setFixedWidth(96)
        self.storage_cache_cleanup_days_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("image"),
                "Wallpaper cache cleanup days",
                "Preferred retention window for wallpaper source caches and rendered wallpaper assets.",
                self.icon_font,
                self.ui_font,
                self.storage_cache_cleanup_days_input,
            )
        )

        self.storage_log_retention_days_input = QLineEdit(
            str(int(self.settings_state["storage"].get("log_retention_days", 14)))
        )
        self.storage_log_retention_days_input.setValidator(QIntValidator(1, 365, self))
        self.storage_log_retention_days_input.setFixedWidth(96)
        self.storage_log_retention_days_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Log retention days",
                "Preferred retention window for Hanauta logs and debugging traces.",
                self.icon_font,
                self.ui_font,
                self.storage_log_retention_days_input,
            )
        )

        self.storage_clean_temp_switch = SwitchButton(
            bool(
                self.settings_state["storage"].get("clean_temp_state_on_startup", False)
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Clean temp state on startup",
                "Remember whether short-lived cache and temp state should be cleaned when the session boots.",
                self.icon_font,
                self.ui_font,
                self.storage_clean_temp_switch,
            )
        )

        self.storage_metrics: dict[str, QLabel] = {}
        metrics_grid = QGridLayout()
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        metrics_grid.setHorizontalSpacing(10)
        metrics_grid.setVerticalSpacing(10)
        for index, key in enumerate(
            (
                "Wallpaper Source Cache",
                "Rendered Wallpapers",
                "Mail Attachments",
                "State Root",
                "Filesystem Total",
                "Filesystem Free",
            )
        ):
            label = QLabel("...")
            label.setFont(QFont(self.ui_font, 10))
            label.setStyleSheet("color: #FFFFFF;")
            self.storage_metrics[key] = label
            metrics_grid.addWidget(self._metric_card(key, label), index // 2, index % 2)
        layout.addLayout(metrics_grid)

        self.storage_status = QLabel("Storage tools are ready.")
        self.storage_status.setWordWrap(True)
        self.storage_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.storage_status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        refresh_button = QPushButton("Refresh sizes")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self._refresh_storage_metrics)
        clear_wallpaper_button = QPushButton("Clear wallpaper cache")
        clear_wallpaper_button.setObjectName("secondaryButton")
        clear_wallpaper_button.clicked.connect(self._clear_wallpaper_cache)
        clear_temp_button = QPushButton("Clean temp state")
        clear_temp_button.setObjectName("secondaryButton")
        clear_temp_button.clicked.connect(self._clear_temp_state)
        save_button = QPushButton("Save storage settings")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save_storage_settings)
        for button in (
            refresh_button,
            clear_wallpaper_button,
            clear_temp_button,
            save_button,
        ):
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        buttons.addWidget(refresh_button)
        buttons.addWidget(clear_wallpaper_button)
        buttons.addWidget(clear_temp_button)
        buttons.addWidget(save_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self._refresh_storage_metrics()
        return card

    def _build_region_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("public"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Region & locale")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        detected_locale = ""
        try:
            current_locale = pylocale.setlocale(pylocale.LC_TIME, None)
            if current_locale and current_locale.upper() != "C":
                detected_locale = current_locale
        except Exception:
            detected_locale = ""
        if not detected_locale:
            try:
                locale_pair = pylocale.getlocale()
            except Exception:
                locale_pair = (None, None)
            if locale_pair and locale_pair[0]:
                detected_locale = locale_pair[0]
                try:
                    encoding = pylocale.getencoding()
                except Exception:
                    encoding = ""
                if encoding and "." not in detected_locale:
                    detected_locale = f"{detected_locale}.{encoding}"
        self.region_locale_combo = QComboBox()
        self.region_locale_combo.setObjectName("settingsCombo")
        self.region_locale_combo.setEditable(True)
        self.region_locale_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._region_locale_label_to_value: dict[str, str] = {}
        locale_labels: list[str] = []
        for label, locale_code in LOCALE_LANGUAGE_PRESETS:
            self.region_locale_combo.addItem(label, locale_code)
            self._region_locale_label_to_value[label] = locale_code
            locale_labels.append(label)
        locale_model = QStringListModel(locale_labels, self)
        self.region_locale_completer = QCompleter(locale_model, self)
        self.region_locale_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.region_locale_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.region_locale_combo.setCompleter(self.region_locale_completer)

        current_locale_code = str(
            self.settings_state["region"].get("locale_code", detected_locale)
        ).strip()
        current_index = self.region_locale_combo.findData(current_locale_code)
        if current_index >= 0:
            self.region_locale_combo.setCurrentIndex(current_index)
        else:
            self.region_locale_combo.setCurrentText(current_locale_code)
        if self.region_locale_combo.lineEdit() is not None:
            self.region_locale_combo.lineEdit().setPlaceholderText(
                detected_locale or "en_US.UTF-8"
            )
        layout.addWidget(
            SettingsRow(
                material_icon("language"),
                "Locale language",
                "Autocomplete Linux locale used by Hanauta for formatting. You can also type a custom locale like en_US.UTF-8.",
                self.icon_font,
                self.ui_font,
                self.region_locale_combo,
            )
        )

        self.region_keyboard_layout_combo = QComboBox()
        self.region_keyboard_layout_combo.setObjectName("settingsCombo")
        self.region_keyboard_layout_combo.setEditable(True)
        self.region_keyboard_layout_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._region_keyboard_layout_label_to_value: dict[str, str] = {}
        region_labels: list[str] = []
        for label, layout_value in KEYBOARD_LAYOUT_PRESETS:
            self.region_keyboard_layout_combo.addItem(label, layout_value)
            self._region_keyboard_layout_label_to_value[label] = layout_value
            region_labels.append(label)
        region_model = QStringListModel(region_labels, self)
        self.region_keyboard_layout_completer = QCompleter(region_model, self)
        self.region_keyboard_layout_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.region_keyboard_layout_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.region_keyboard_layout_combo.setCompleter(self.region_keyboard_layout_completer)
        current_region_layout = self._normalize_keyboard_layout_value(
            str(
                self.settings_state["region"].get(
                    "keyboard_layout",
                    self.settings_state.get("input", {}).get("keyboard_layout", "us"),
                )
            )
        )
        current_region_layout_index = self.region_keyboard_layout_combo.findData(current_region_layout)
        if current_region_layout_index >= 0:
            self.region_keyboard_layout_combo.setCurrentIndex(current_region_layout_index)
        else:
            self.region_keyboard_layout_combo.setCurrentText(current_region_layout)
        layout.addWidget(
            SettingsRow(
                material_icon("keyboard"),
                "Keyboard language",
                "Autocomplete keyboard layout used by the current session (setxkbmap). Example: us, br, br abnt2.",
                self.icon_font,
                self.ui_font,
                self.region_keyboard_layout_combo,
                str(ASSETS_DIR / "keyboard.svg"),
            )
        )

        self.region_24h_switch = SwitchButton(
            bool(self.settings_state["region"].get("use_24_hour", False))
        )
        self.region_24h_switch.toggledValue.connect(self._set_region_use_24_hour)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "24-hour clock",
                "Use 24-hour time in the bar instead of AM/PM.",
                self.icon_font,
                self.ui_font,
                self.region_24h_switch,
            )
        )

        self.region_date_style_combo = QComboBox()
        self.region_date_style_combo.setObjectName("settingsCombo")
        self.region_date_style_combo.addItem("US", "us")
        self.region_date_style_combo.addItem("ISO", "iso")
        self.region_date_style_combo.addItem("European", "eu")
        current_date_style = str(self.settings_state["region"].get("date_style", "us"))
        date_style_index = self.region_date_style_combo.findData(current_date_style)
        self.region_date_style_combo.setCurrentIndex(max(0, date_style_index))
        self.region_date_style_combo.currentIndexChanged.connect(
            self._set_region_date_style
        )
        layout.addWidget(
            SettingsRow(
                material_icon("calendar_month"),
                "Date style",
                "Controls how the bar renders the date label.",
                self.icon_font,
                self.ui_font,
                self.region_date_style_combo,
            )
        )

        self.region_temperature_combo = QComboBox()
        self.region_temperature_combo.setObjectName("settingsCombo")
        self.region_temperature_combo.addItem("Celsius", "c")
        self.region_temperature_combo.addItem("Fahrenheit", "f")
        current_temp_style = str(
            self.settings_state["region"].get("temperature_unit", "c")
        )
        temp_style_index = self.region_temperature_combo.findData(current_temp_style)
        self.region_temperature_combo.setCurrentIndex(max(0, temp_style_index))
        self.region_temperature_combo.currentIndexChanged.connect(
            self._set_region_temperature_unit
        )
        layout.addWidget(
            SettingsRow(
                material_icon("partly_cloudy_day"),
                "Temperature unit",
                "Used by Hanauta weather surfaces when a converted regional unit is needed.",
                self.icon_font,
                self.ui_font,
                self.region_temperature_combo,
                str(ASSETS_DIR / "thermostat.svg"),
            )
        )

        self.region_location_input = QLineEdit(
            self.settings_state["weather"].get("name", "")
        )
        if self._selected_weather_city is not None:
            self.region_location_input.setText(self._selected_weather_city.label)
        self.region_location_input.setPlaceholderText("Type a city, region, or country")
        self.region_location_input.textEdited.connect(self._queue_weather_city_search)
        self.region_location_model = QStringListModel(self)
        self.region_location_completer = QCompleter(self.region_location_model, self)
        self.region_location_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.region_location_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.region_location_completer.activated[str].connect(self._select_weather_city)
        self.region_location_input.setCompleter(self.region_location_completer)
        layout.addWidget(
            SettingsRow(
                material_icon("location_on"),
                "Shared location",
                "Used to match CAP alerts to your area and reused by the Weather widget.",
                self.icon_font,
                self.ui_font,
                self.region_location_input,
            )
        )

        self.region_location_note = QLabel(
            "If you use a VPN, the detected network region can be wrong for weather and alerts. Save your real location here instead. Hanauta does not send telemetry or your location anywhere."
        )
        self.region_location_note.setWordWrap(True)
        self.region_location_note.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.region_location_note)

        self.region_status = QLabel("Regional formatting is ready.")
        self.region_status.setWordWrap(True)
        self.region_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.region_status)

        self.region_location_button = QPushButton("Save shared location")
        self.region_location_button.setObjectName("primaryButton")
        self.region_location_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.region_location_button.clicked.connect(self._save_weather_settings)
        layout.addWidget(self.region_location_button, 0, Qt.AlignmentFlag.AlignLeft)

        save_button = QPushButton("Save region settings")
        save_button.setObjectName("primaryButton")
        save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_button.clicked.connect(self._save_region_settings)
        layout.addWidget(save_button, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_marketplace_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("storefront"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Marketplace")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Discover modular Hanauta services from one or more GitHub catalogs, or install private plugins from local ZIP bundles."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
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

        marketplace = self.settings_state.setdefault("marketplace", {})
        self.marketplace_repo_input = QLineEdit(
            str(
                marketplace.get(
                    "catalog_repo_url", "https://github.com/gab-luz/hanauta-plugins"
                )
            )
        )
        self.marketplace_repo_input.setPlaceholderText(
            "https://github.com/gab-luz/hanauta-plugins"
        )
        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "Catalog repo URL",
                "GitHub repository that hosts your plugin catalog manifest and plugin repositories.",
                self.icon_font,
                self.ui_font,
                self.marketplace_repo_input,
            )
        )

        self.marketplace_branch_input = QLineEdit(
            str(marketplace.get("catalog_branch", "main"))
        )
        self.marketplace_branch_input.setPlaceholderText("main")
        layout.addWidget(
            SettingsRow(
                material_icon("settings"),
                "Catalog branch",
                "Branch used when fetching the marketplace catalog.",
                self.icon_font,
                self.ui_font,
                self.marketplace_branch_input,
            )
        )

        self.marketplace_manifest_input = QLineEdit(
            str(marketplace.get("catalog_manifest_path", "plugins.json"))
        )
        self.marketplace_manifest_input.setPlaceholderText("plugins.json")
        layout.addWidget(
            SettingsRow(
                material_icon("description"),
                "Manifest path",
                "Path in the repo that returns plugin metadata as JSON.",
                self.icon_font,
                self.ui_font,
                self.marketplace_manifest_input,
            )
        )

        sources = marketplace.get("catalog_sources", [])
        source_lines: list[str] = []
        if isinstance(sources, list):
            for row in sources:
                if not isinstance(row, dict):
                    continue
                repo_url = str(row.get("repo_url", "")).strip()
                if not repo_url:
                    continue
                branch = str(row.get("branch", "main")).strip() or "main"
                manifest_path = (
                    str(row.get("manifest_path", "plugins.json")).strip().lstrip("/")
                    or "plugins.json"
                )
                source_lines.append(f"{repo_url} | {branch} | {manifest_path}")
        self.marketplace_sources_input = QPlainTextEdit("\n".join(source_lines))
        self.marketplace_sources_input.setPlaceholderText(
            "One source per line: https://github.com/owner/repo | main | plugins.json"
        )
        self.marketplace_sources_input.setFixedHeight(86)
        layout.addWidget(
            SettingsRow(
                material_icon("hub"),
                "Catalog sources",
                "Optional multi-source format: repo URL | branch | manifest path (one per line).",
                self.icon_font,
                self.ui_font,
                self.marketplace_sources_input,
            )
        )

        self.marketplace_install_dir_input = QLineEdit(
            str(marketplace.get("install_dir", str(ROOT / "hanauta" / "plugins")))
        )
        self.marketplace_install_dir_input.setPlaceholderText(
            str(ROOT / "hanauta" / "plugins")
        )
        install_dir_row = QWidget()
        install_dir_layout = QHBoxLayout(install_dir_row)
        install_dir_layout.setContentsMargins(0, 0, 0, 0)
        install_dir_layout.setSpacing(8)
        install_dir_layout.addWidget(self.marketplace_install_dir_input, 1)
        self.marketplace_choose_dir_button = QPushButton("Choose")
        self.marketplace_choose_dir_button.setObjectName("secondaryButton")
        self.marketplace_choose_dir_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.marketplace_choose_dir_button.clicked.connect(
            self._marketplace_choose_install_dir
        )
        install_dir_layout.addWidget(self.marketplace_choose_dir_button)
        layout.addWidget(
            SettingsRow(
                material_icon("folder_open"),
                "Install directory",
                "Plugins are cloned here and can be wired into Hanauta services.",
                self.icon_font,
                self.ui_font,
                install_dir_row,
            )
        )

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.marketplace_save_button = QPushButton("Save marketplace config")
        self.marketplace_save_button.setObjectName("primaryButton")
        self.marketplace_refresh_button = QPushButton("Refresh catalog")
        self.marketplace_refresh_button.setObjectName("secondaryButton")
        self.marketplace_install_button = QPushButton("Install selected")
        self.marketplace_install_button.setObjectName("secondaryButton")
        self.marketplace_install_zip_button = QPushButton("Install ZIP")
        self.marketplace_install_zip_button.setObjectName("secondaryButton")
        self.marketplace_open_dir_button = QPushButton("Open plugin folder")
        self.marketplace_open_dir_button.setObjectName("secondaryButton")
        for button in (
            self.marketplace_save_button,
            self.marketplace_refresh_button,
            self.marketplace_install_button,
            self.marketplace_install_zip_button,
            self.marketplace_open_dir_button,
        ):
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.marketplace_save_button.clicked.connect(self._marketplace_save_settings)
        self.marketplace_refresh_button.clicked.connect(
            self._marketplace_refresh_catalog
        )
        self.marketplace_install_button.clicked.connect(
            self._marketplace_install_selected
        )
        self.marketplace_install_zip_button.clicked.connect(
            self._marketplace_install_zip
        )
        self.marketplace_open_dir_button.clicked.connect(
            self._marketplace_open_install_dir
        )
        actions.addWidget(self.marketplace_save_button)
        actions.addWidget(self.marketplace_refresh_button)
        actions.addWidget(self.marketplace_install_button)
        actions.addWidget(self.marketplace_install_zip_button)
        actions.addWidget(self.marketplace_open_dir_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        marketplace_body = QHBoxLayout()
        marketplace_body.setSpacing(10)

        catalog_card = QFrame()
        catalog_card.setObjectName("marketplaceCatalogCard")
        catalog_layout = QVBoxLayout(catalog_card)
        catalog_layout.setContentsMargins(12, 12, 12, 12)
        catalog_layout.setSpacing(8)
        catalog_title = QLabel("Plugin catalog")
        catalog_title.setObjectName("marketplacePanelTitle")
        catalog_subtitle = QLabel("Install only the modules each user actually wants.")
        catalog_subtitle.setObjectName("marketplacePanelSubtitle")
        catalog_subtitle.setWordWrap(True)
        catalog_layout.addWidget(catalog_title)
        catalog_layout.addWidget(catalog_subtitle)
        self.marketplace_search_input = QLineEdit()
        self.marketplace_search_input.setPlaceholderText(
            "Search plugins by name, id, or description"
        )
        self.marketplace_search_input.textChanged.connect(
            self._marketplace_filter_catalog
        )
        catalog_layout.addWidget(self.marketplace_search_input)

        self.marketplace_plugin_list = QListWidget()
        self.marketplace_plugin_list.setObjectName("marketplacePluginList")
        self.marketplace_plugin_list.currentItemChanged.connect(
            self._marketplace_update_details
        )
        self.marketplace_plugin_list.setMinimumHeight(250)
        self.marketplace_plugin_list.setAlternatingRowColors(False)
        self.marketplace_plugin_list.setUniformItemSizes(False)
        catalog_layout.addWidget(self.marketplace_plugin_list, 1)
        marketplace_body.addWidget(catalog_card, 3)

        detail_card = QFrame()
        detail_card.setObjectName("marketplaceDetailCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(8)
        detail_title = QLabel("Plugin details")
        detail_title.setObjectName("marketplacePanelTitle")
        detail_layout.addWidget(detail_title)

        self.marketplace_detail_label = QLabel(
            "Select a plugin from the catalog to inspect installation details."
        )
        self.marketplace_detail_label.setObjectName("marketplaceDetailText")
        self.marketplace_detail_label.setWordWrap(True)
        detail_layout.addWidget(self.marketplace_detail_label)

        status_title = QLabel("Marketplace status")
        status_title.setObjectName("marketplacePanelTitle")
        detail_layout.addWidget(status_title)

        self.marketplace_status = QLabel("Marketplace is ready.")
        self.marketplace_status.setObjectName("marketplaceStatusText")
        self.marketplace_status.setWordWrap(True)
        detail_layout.addWidget(self.marketplace_status)
        detail_layout.addStretch(1)
        marketplace_body.addWidget(detail_card, 2)
        layout.addLayout(marketplace_body)

        self._marketplace_populate_catalog(list(marketplace.get("catalog_cache", [])))
        return card

    def _plugin_api_versions_from_row(self, row: dict[str, object]) -> tuple[int, int]:
        try:
            api_min = int(row.get("api_min_version", 1) or 1)
        except Exception:
            api_min = 1
        try:
            api_target = int(row.get("api_target_version", 1) or 1)
        except Exception:
            api_target = 1
        return max(1, api_min), max(1, api_target)

    def _plugin_permissions_warning(self, row: dict[str, object]) -> str:
        warnings: list[str] = []
        permissions = row.get("permissions", {})
        if isinstance(permissions, dict) and permissions:
            warnings.append(
                "Declared permissions: "
                + ", ".join(
                    sorted(
                        str(key).strip()
                        for key in permissions.keys()
                        if str(key).strip()
                    )
                )
            )
        capabilities = row.get("capabilities", [])
        capability_list: list[str] = []
        if isinstance(capabilities, dict):
            capability_list = [
                str(key).strip()
                for key, enabled in capabilities.items()
                if str(key).strip() and bool(enabled)
            ]
        elif isinstance(capabilities, list):
            capability_list = [
                str(value).strip() for value in capabilities if str(value).strip()
            ]
        if "polkit" in capability_list:
            warnings.append(
                "This plugin may request elevated privileges through Polkit (pkexec)."
            )
        if (
            "fullscreen_alert" in capability_list
            or "fullscreen_overlay" in capability_list
        ):
            warnings.append("This plugin may show fullscreen alerts/overlays.")
        requirements = row.get("requirements", [])
        if isinstance(requirements, list):
            req_list = [
                str(value).strip() for value in requirements if str(value).strip()
            ]
            if req_list:
                warnings.append("Runtime requirements: " + ", ".join(req_list))
        return "\n".join(warnings).strip()

    def _permission_icon_for_key(self, key: str) -> str:
        normalized = key.strip().lower()
        if normalized in {"polkit", "privileged", "root", "systemd"}:
            return material_icon("shield")
        if normalized in {"hosts", "fs_hosts", "filesystem", "files"}:
            return material_icon("folder_open")
        if normalized in {"network", "vpn", "dns"}:
            return material_icon("public")
        if normalized in {"notifications", "alerts"}:
            return material_icon("notifications")
        if normalized in {"i3", "i3_config", "window_rules"}:
            return material_icon("dashboard")
        if normalized in {"desktop", "desktop_files", "desktop_entry"}:
            return material_icon("desktop_windows")
        return material_icon("settings")

    def _permission_icon_asset_for_key(self, key: str) -> Path | None:
        normalized = key.strip().lower()
        candidates: list[str] = []
        if normalized in {"polkit", "privileged", "root", "systemd"}:
            candidates.extend(
                [
                    "permission-polkit.svg",
                    "permission-systemd.svg",
                    "permission-privileged.svg",
                ]
            )
        elif normalized in {"hosts", "fs_hosts", "filesystem", "files"}:
            candidates.extend(["permission-fs-hosts.svg", "permission-filesystem.svg"])
        elif normalized in {"network", "vpn", "dns"}:
            candidates.extend(["permission-network.svg"])
        elif normalized in {"notifications", "alerts"}:
            candidates.extend(["permission-notifications.svg"])
        elif normalized in {"i3", "i3_config", "window_rules"}:
            candidates.extend(["permission-i3-config.svg"])
        elif normalized in {"desktop", "desktop_files", "desktop_entry"}:
            candidates.extend(["permission-desktop-files.svg"])
        else:
            candidates.extend([f"permission-{normalized.replace('_', '-')}.svg"])
        candidates.append("permission-placeholder.svg")
        for name in candidates:
            path = ASSETS_DIR / name
            if path.exists():
                return path
        return None

    def _marketplace_permission_items(
        self, plugin: dict[str, object], manifest: dict[str, object] | None = None
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        permissions = plugin.get("permissions", {})
        if isinstance(permissions, dict):
            for key, value in permissions.items():
                if not bool(value):
                    continue
                items.append(
                    {
                        "key": str(key),
                        "label": str(key).replace("_", " ").strip().title() or str(key),
                        "description": "Requested by plugin metadata.",
                    }
                )
        capabilities = plugin.get("capabilities", [])
        capability_list: list[str] = []
        if isinstance(capabilities, dict):
            capability_list = [
                str(key).strip()
                for key, enabled in capabilities.items()
                if str(key).strip() and bool(enabled)
            ]
        elif isinstance(capabilities, list):
            capability_list = [
                str(value).strip() for value in capabilities if str(value).strip()
            ]
        for capability in capability_list:
            if capability in {"polkit", "fullscreen_alert", "fullscreen_overlay"}:
                description = (
                    "May request elevated privileges via Polkit."
                    if capability == "polkit"
                    else "Can present strong fullscreen alerts."
                )
                items.append(
                    {
                        "key": capability,
                        "label": capability.replace("_", " ").title(),
                        "description": description,
                    }
                )
        if isinstance(manifest, dict):
            explicit_permissions = manifest.get("permissions", [])
            if isinstance(explicit_permissions, list):
                for row in explicit_permissions:
                    if not isinstance(row, dict):
                        continue
                    key = str(row.get("key", "")).strip()
                    label = str(row.get("label", "")).strip()
                    description = str(row.get("description", "")).strip()
                    if not key:
                        continue
                    items.append(
                        {
                            "key": key,
                            "label": label or key.replace("_", " ").title(),
                            "description": description
                            or "Requested by plugin install manifest.",
                        }
                    )
            i3_changes = manifest.get("i3_changes", [])
            if isinstance(i3_changes, list) and i3_changes:
                for change in i3_changes:
                    text = str(change).strip()
                    if not text:
                        continue
                    items.append(
                        {
                            "key": "i3_config",
                            "label": "i3 Configuration Change",
                            "description": text,
                        }
                    )
            if bool(manifest.get("requires_privileged_install", False)):
                items.append(
                    {
                        "key": "privileged",
                        "label": "Privileged Install",
                        "description": "Installs system-level components and may create/enable systemd services.",
                    }
                )
            desktop_entries = manifest.get("desktop_entries", [])
            if isinstance(desktop_entries, list) and desktop_entries:
                items.append(
                    {
                        "key": "desktop_files",
                        "label": "Desktop Entry Files",
                        "description": "Creates or updates .desktop launcher entries in ~/.local/share/applications.",
                    }
                )
        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in items:
            signature = f"{item.get('key', '')}|{item.get('label', '')}|{item.get('description', '')}"
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(item)
        return deduped

    def _marketplace_show_permission_dialog(
        self,
        *,
        plugin_name: str,
        intro_text: str,
        permission_items: list[dict[str, str]],
        confirm_label: str = "Install",
    ) -> bool:
        dialog = QDialog(self)
        dialog.setObjectName("pluginPermissionDialog")
        dialog.setWindowTitle("Plugin Permissions")
        dialog.setModal(True)
        dialog.setMinimumWidth(560)
        dialog.setStyleSheet(
            """
            QDialog#pluginPermissionDialog {
                background-color: rgba(14, 18, 26, 0.98);
                border: 1px solid rgba(145, 160, 185, 0.34);
                border-radius: 14px;
            }
            QDialog#pluginPermissionDialog QLabel {
                color: rgba(246, 235, 247, 0.90);
            }
            QDialog#pluginPermissionDialog QFrame#permissionListCard {
                background-color: rgba(26, 32, 43, 0.94);
                border: 1px solid rgba(145, 160, 185, 0.30);
                border-radius: 12px;
            }
            QDialog#pluginPermissionDialog QPushButton#permissionCancelButton {
                background-color: rgba(96, 112, 136, 0.42);
                color: rgba(246, 235, 247, 0.98);
                border: 1px solid rgba(196, 208, 228, 0.62);
                border-radius: 10px;
                padding: 8px 14px;
                min-width: 90px;
            }
            QDialog#pluginPermissionDialog QPushButton#permissionCancelButton:hover {
                background-color: rgba(110, 126, 150, 0.56);
            }
            """
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"Review permissions for {plugin_name}")
        title.setFont(QFont(self.display_font, 12, QFont.Weight.DemiBold))
        title.setStyleSheet("color: rgba(246,235,247,0.92);")
        layout.addWidget(title)

        body = QLabel(
            intro_text.strip() or "This plugin requests runtime/system permissions."
        )
        body.setWordWrap(True)
        body.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(body)

        card = QFrame()
        card.setObjectName("permissionListCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        if permission_items:
            for item in permission_items:
                row = QHBoxLayout()
                row.setSpacing(10)
                icon_label = QLabel()
                icon_label.setFixedSize(24, 24)
                icon_label.setFixedWidth(24)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
                icon_path = self._permission_icon_asset_for_key(
                    str(item.get("key", ""))
                )
                icon_pixmap = (
                    QPixmap(str(icon_path)) if icon_path is not None else QPixmap()
                )
                if not icon_pixmap.isNull():
                    icon_label.setPixmap(
                        icon_pixmap.scaled(
                            20,
                            20,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    icon_label.setText(
                        self._permission_icon_for_key(str(item.get("key", "")))
                    )
                    icon_label.setFont(QFont(self.icon_font, 14))
                text = QLabel(
                    f"{str(item.get('label', 'Permission'))}\n{str(item.get('description', '')).strip() or 'Requested by plugin.'}"
                )
                text.setWordWrap(True)
                text.setStyleSheet("color: rgba(246,235,247,0.82);")
                row.addWidget(icon_label, 0)
                row.addWidget(text, 1)
                card_layout.addLayout(row)
        else:
            empty = QLabel("No extra permissions declared.")
            empty.setStyleSheet("color: rgba(246,235,247,0.72);")
            card_layout.addWidget(empty)
        layout.addWidget(card)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("permissionCancelButton")
        confirm_btn = QPushButton(confirm_label)
        confirm_btn.setObjectName("primaryButton")
        cancel_btn.clicked.connect(dialog.reject)
        confirm_btn.clicked.connect(dialog.accept)
        actions.addWidget(cancel_btn)
        actions.addWidget(confirm_btn)
        layout.addLayout(actions)

        return dialog.exec() == int(QDialog.DialogCode.Accepted)

    def _load_plugin_install_manifest(self, plugin_dir: Path) -> dict[str, object]:
        manifest_path = plugin_dir / "hanauta-install.json"
        if not manifest_path.exists():
            return {}
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _plugin_install_receipt_file(self, plugin_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", plugin_id.strip()) or "plugin"
        return PLUGIN_INSTALL_STATE_DIR / safe_id / "install-receipt.json"

    def _load_plugin_install_receipt(self, plugin_id: str) -> dict[str, object]:
        receipt_path = self._plugin_install_receipt_file(plugin_id)
        if not receipt_path.exists():
            return {}
        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_plugin_install_receipt(
        self, plugin_id: str, payload: dict[str, object]
    ) -> None:
        receipt_path = self._plugin_install_receipt_file(plugin_id)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json_file(receipt_path, payload)

    def _clear_plugin_install_receipt(self, plugin_id: str) -> None:
        receipt_path = self._plugin_install_receipt_file(plugin_id)
        if receipt_path.exists():
            try:
                receipt_path.unlink()
            except Exception:
                pass
        try:
            if receipt_path.parent.exists():
                shutil.rmtree(receipt_path.parent)
        except Exception:
            pass

    def _render_desktop_entry(
        self, entry: dict[str, object], plugin_dir: Path
    ) -> tuple[str, str]:
        desktop_id = str(entry.get("id", "")).strip()
        if not desktop_id:
            desktop_id = f"{plugin_dir.name}.desktop"
        if not desktop_id.endswith(".desktop"):
            desktop_id = f"{desktop_id}.desktop"
        name = str(entry.get("name", plugin_dir.name)).strip() or plugin_dir.name
        comment = str(entry.get("comment", "")).strip()
        terminal = "true" if bool(entry.get("terminal", False)) else "false"
        categories = entry.get("categories", ["Utility"])
        if not isinstance(categories, list):
            categories = ["Utility"]
        categories_str = ";".join(
            str(value).strip() for value in categories if str(value).strip()
        )
        if categories_str and not categories_str.endswith(";"):
            categories_str += ";"
        exec_value = ""
        raw_exec = entry.get("exec", [])
        if isinstance(raw_exec, list):
            parts = [
                str(value).replace("${PLUGIN_DIR}", str(plugin_dir)).strip()
                for value in raw_exec
                if str(value).strip()
            ]
            exec_value = " ".join(parts)
        elif isinstance(raw_exec, str):
            exec_value = raw_exec.replace("${PLUGIN_DIR}", str(plugin_dir)).strip()
        if not exec_value:
            exec_value = f"{python_executable()} {plugin_dir / 'hanauta_plugin.py'}"
        icon = (
            str(entry.get("icon", "")).replace("${PLUGIN_DIR}", str(plugin_dir)).strip()
        )
        body = [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={name}",
            f"Comment={comment}" if comment else "Comment=Hanauta plugin launcher",
            f"Exec={exec_value}",
            f"Terminal={terminal}",
            f"Categories={categories_str or 'Utility;'}",
        ]
        if icon:
            body.append(f"Icon={icon}")
        body.append("")
        return desktop_id, "\n".join(body)

    def _apply_plugin_desktop_entries(
        self, plugin_id: str, plugin_dir: Path, manifest: dict[str, object]
    ) -> list[dict[str, object]]:
        actions: list[dict[str, object]] = []
        desktop_entries = manifest.get("desktop_entries", [])
        if not isinstance(desktop_entries, list) or not desktop_entries:
            return actions
        target_dir = Path.home() / ".local" / "share" / "applications"
        target_dir.mkdir(parents=True, exist_ok=True)
        receipt_root = self._plugin_install_receipt_file(plugin_id).parent
        backups_dir = receipt_root / "desktop-backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        for row in desktop_entries:
            if not isinstance(row, dict):
                continue
            desktop_id, content = self._render_desktop_entry(row, plugin_dir)
            target_path = target_dir / desktop_id
            existed_before = target_path.exists()
            backup_path = ""
            if existed_before:
                try:
                    old_content = target_path.read_text(encoding="utf-8")
                except Exception:
                    old_content = ""
                if old_content != content:
                    backup_file = backups_dir / f"{desktop_id}.bak"
                    backup_file.write_text(old_content, encoding="utf-8")
                    backup_path = str(backup_file)
            target_path.write_text(content, encoding="utf-8")
            actions.append(
                {
                    "path": str(target_path),
                    "desktop_id": desktop_id,
                    "existed_before": existed_before,
                    "backup_path": backup_path,
                }
            )
        return actions

    def _resolve_privileged_install_command(
        self, plugin_dir: Path, manifest: dict[str, object]
    ) -> list[str]:
        install = manifest.get("privileged_install", {})
        if isinstance(install, dict):
            command = install.get("command", [])
            if isinstance(command, list):
                resolved = [
                    str(part).replace("${PLUGIN_DIR}", str(plugin_dir))
                    for part in command
                    if str(part).strip()
                ]
                if resolved:
                    return resolved
        fallback = plugin_dir / "bin" / "install_root_service.sh"
        if fallback.exists():
            return ["bash", str(fallback)]
        return []

    def _resolve_privileged_uninstall_command(
        self, plugin_dir: Path, manifest: dict[str, object]
    ) -> list[str]:
        uninstall = manifest.get("privileged_uninstall", {})
        if isinstance(uninstall, dict):
            command = uninstall.get("command", [])
            if isinstance(command, list):
                resolved = [
                    str(part).replace("${PLUGIN_DIR}", str(plugin_dir))
                    for part in command
                    if str(part).strip()
                ]
                if resolved:
                    return resolved
        fallback = plugin_dir / "bin" / "uninstall_root_service.sh"
        if fallback.exists():
            return ["bash", str(fallback)]
        return []

    def _revert_plugin_desktop_entries(
        self, plugin_id: str, receipt: dict[str, object]
    ) -> None:
        entries = receipt.get("desktop_entries", [])
        if not isinstance(entries, list):
            return
        for row in entries:
            if not isinstance(row, dict):
                continue
            path_value = str(row.get("path", "")).strip()
            if not path_value:
                continue
            target_path = Path(path_value).expanduser()
            backup_path = str(row.get("backup_path", "")).strip()
            if backup_path:
                backup_file = Path(backup_path).expanduser()
                if backup_file.exists():
                    try:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup_file, target_path)
                        continue
                    except Exception:
                        pass
            try:
                if target_path.exists():
                    target_path.unlink()
            except Exception:
                continue

    def _run_plugin_post_install_steps(
        self, plugin: dict[str, object], target_dir: Path
    ) -> bool:
        plugin_id = str(plugin.get("id", target_dir.name)).strip() or target_dir.name
        manifest = self._load_plugin_install_manifest(target_dir)
        permission_items = self._marketplace_permission_items(
            plugin, manifest if manifest else None
        )
        if permission_items:
            accepted = self._marketplace_show_permission_dialog(
                plugin_name=str(plugin.get("name", plugin.get("id", "Plugin"))),
                intro_text="This plugin declares runtime/system permissions. Review and confirm before finalizing installation.",
                permission_items=permission_items,
                confirm_label="Proceed",
            )
            if not accepted:
                self.marketplace_status.setText(
                    "Install paused: permission review was not approved."
                )
                return False

        desktop_actions: list[dict[str, object]] = []
        if manifest:
            desktop_actions = self._apply_plugin_desktop_entries(
                plugin_id, target_dir, manifest
            )
        shortcut_actions = self._marketplace_apply_plugin_shortcuts(plugin, plugin_id)

        requires_privileged = bool(manifest.get("requires_privileged_install", False))
        has_systemd_unit = bool(list((target_dir / "systemd").glob("*.service")))
        if not requires_privileged and not has_systemd_unit:
            self._save_plugin_install_receipt(
                plugin_id,
                {
                    "plugin_id": plugin_id,
                    "plugin_dir": str(target_dir),
                    "desktop_entries": desktop_actions,
                    "shortcuts": shortcut_actions,
                    "manifest": manifest if isinstance(manifest, dict) else {},
                    "installed_at_epoch": int(time.time()),
                },
            )
            return True

        command = self._resolve_privileged_install_command(target_dir, manifest)
        if not command:
            self.marketplace_status.setText(
                "Plugin install completed, but no privileged install command was found."
            )
            self._save_plugin_install_receipt(
                plugin_id,
                {
                    "plugin_id": plugin_id,
                    "plugin_dir": str(target_dir),
                    "desktop_entries": desktop_actions,
                    "shortcuts": shortcut_actions,
                    "manifest": manifest if isinstance(manifest, dict) else {},
                    "installed_at_epoch": int(time.time()),
                    "privileged_install_skipped": True,
                },
            )
            return True
        if not polkit_available():
            self.marketplace_status.setText(
                "Plugin install completed. Privileged setup requires pkexec, which is not currently available."
            )
            self._save_plugin_install_receipt(
                plugin_id,
                {
                    "plugin_id": plugin_id,
                    "plugin_dir": str(target_dir),
                    "desktop_entries": desktop_actions,
                    "shortcuts": shortcut_actions,
                    "manifest": manifest if isinstance(manifest, dict) else {},
                    "installed_at_epoch": int(time.time()),
                    "privileged_install_skipped": True,
                },
            )
            return True

        accepted = self._marketplace_show_permission_dialog(
            plugin_name=str(plugin.get("name", plugin.get("id", "Plugin"))),
            intro_text=(
                "This plugin needs privileged setup to install or update systemd services and protected files. "
                "Continuing will show a Polkit authentication prompt."
            ),
            permission_items=permission_items
            or [
                {
                    "key": "privileged",
                    "label": "Privileged Install",
                    "description": "Installs system service files and root-managed policy files.",
                }
            ],
            confirm_label="Continue to Polkit",
        )
        if not accepted:
            self.marketplace_status.setText(
                "Plugin installed. Privileged setup was skipped."
            )
            return True

        ok = run_with_polkit(command, detached=False, timeout=180)
        self._save_plugin_install_receipt(
            plugin_id,
            {
                "plugin_id": plugin_id,
                "plugin_dir": str(target_dir),
                "desktop_entries": desktop_actions,
                "shortcuts": shortcut_actions,
                "manifest": manifest if isinstance(manifest, dict) else {},
                "installed_at_epoch": int(time.time()),
                "privileged_install_attempted": True,
                "privileged_install_ok": bool(ok),
            },
        )
        if ok:
            self.marketplace_status.setText(
                "Plugin installed and privileged setup completed successfully."
            )
            return True
        self.marketplace_status.setText(
            "Plugin installed, but privileged setup failed or was cancelled in Polkit."
        )
        return True

    def _installed_plugin_entry_by_id(self, plugin_id: str) -> dict[str, object] | None:
        installed = self.settings_state.get("marketplace", {}).get(
            "installed_plugins", []
        )
        if not isinstance(installed, list):
            return None
        for row in installed:
            if not isinstance(row, dict):
                continue
            if str(row.get("id", "")).strip() == plugin_id:
                return row
        return None

    def _installed_plugin_rows(self) -> list[dict[str, object]]:
        installed = self.settings_state.get("marketplace", {}).get(
            "installed_plugins", []
        )
        if not isinstance(installed, list):
            return []
        rows: list[dict[str, object]] = []
        for row in installed:
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def _service_plugin_token(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())

    def _resolve_uninstall_target(
        self,
        *,
        plugin_id: str = "",
        service_key: str = "",
        plugin_dir: Path | None = None,
    ) -> tuple[str, str] | None:
        normalized_id = str(plugin_id).strip()
        if normalized_id:
            direct = self._installed_plugin_entry_by_id(normalized_id)
            if isinstance(direct, dict):
                resolved_name = (
                    str(direct.get("name", normalized_id)).strip() or normalized_id
                )
                return normalized_id, resolved_name

        normalized_key = str(service_key).strip()
        if normalized_key:
            by_key = self._installed_plugin_for_service_key(normalized_key)
            if by_key is not None:
                return by_key

        target_dir_resolved = ""
        if isinstance(plugin_dir, Path):
            try:
                target_dir_resolved = str(plugin_dir.expanduser().resolve())
            except Exception:
                target_dir_resolved = str(plugin_dir.expanduser())

        target_token = self._service_plugin_token(normalized_id)
        for row in self._installed_plugin_rows():
            row_id = str(row.get("id", "")).strip()
            if not row_id:
                continue
            row_name = str(row.get("name", row_id)).strip() or row_id
            install_path_raw = str(row.get("install_path", "")).strip()
            install_token = ""
            install_resolved = ""
            if install_path_raw:
                install_path = Path(install_path_raw).expanduser()
                install_token = self._service_plugin_token(install_path.name)
                try:
                    install_resolved = str(install_path.resolve())
                except Exception:
                    install_resolved = str(install_path)
            if target_dir_resolved and install_resolved == target_dir_resolved:
                return row_id, row_name
            if target_token:
                row_token = self._service_plugin_token(row_id)
                if target_token == row_token or target_token == install_token:
                    return row_id, row_name
        return None

    def _installed_plugin_for_service_key(
        self, service_key: str
    ) -> tuple[str, str] | None:
        key = str(service_key).strip()
        if not key:
            return None
        if key in BUILTIN_SERVICE_KEYS:
            return None
        installed_index = getattr(self, "_installed_service_key_index", {})
        if isinstance(installed_index, dict):
            indexed = installed_index.get(key)
            if (
                isinstance(indexed, tuple)
                and len(indexed) == 2
                and str(indexed[0]).strip()
            ):
                plugin_id = str(indexed[0]).strip()
                plugin_name = str(indexed[1]).strip() or plugin_id
                return plugin_id, plugin_name
        marketplace = self.settings_state.get("marketplace", {})
        installed = (
            marketplace.get("installed_plugins", []) if isinstance(marketplace, dict) else []
        )
        if not isinstance(installed, list):
            return None

        # First pass: ask each installed plugin which service keys it exposes.
        for row in installed:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if not plugin_id:
                continue
            install_path_raw = str(row.get("install_path", "")).strip()
            plugin_name = (
                str(row.get("name", plugin_id)).strip() or plugin_id
            )
            install_path = Path(install_path_raw).expanduser() if install_path_raw else Path()
            if install_path_raw and install_path.exists() and install_path.is_dir():
                try:
                    services = self._marketplace_collect_plugin_services(install_path)
                except Exception:
                    services = []
                for service_row in services:
                    if not isinstance(service_row, dict):
                        continue
                    if str(service_row.get("key", "")).strip() == key:
                        return plugin_id, plugin_name

        # Fallback: heuristic match against plugin id or install directory name.
        key_token = self._service_plugin_token(key)
        for row in installed:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if not plugin_id:
                continue
            plugin_name = (
                str(row.get("name", plugin_id)).strip() or plugin_id
            )
            install_path_raw = str(row.get("install_path", "")).strip()
            install_name = ""
            if install_path_raw:
                try:
                    install_name = Path(install_path_raw).expanduser().name
                except Exception:
                    install_name = ""
            candidates = {
                self._service_plugin_token(plugin_id),
                self._service_plugin_token(install_name),
            }
            candidates = {item for item in candidates if item}
            if key_token in candidates:
                return plugin_id, plugin_name
        return None

    def _refresh_installed_service_key_index(self) -> None:
        index: dict[str, tuple[str, str]] = {}
        marketplace = self.settings_state.get("marketplace", {})
        installed = (
            marketplace.get("installed_plugins", []) if isinstance(marketplace, dict) else []
        )
        if not isinstance(installed, list):
            installed = []
        for row in installed:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if not plugin_id:
                continue
            plugin_name = str(row.get("name", plugin_id)).strip() or plugin_id
            install_path_raw = str(row.get("install_path", "")).strip()
            if not install_path_raw:
                continue
            install_path = Path(install_path_raw).expanduser()
            if not install_path.exists() or not install_path.is_dir():
                continue
            try:
                service_rows = self._marketplace_collect_plugin_services(install_path)
            except Exception:
                service_rows = []
            for service_row in service_rows:
                if not isinstance(service_row, dict):
                    continue
                key = str(service_row.get("key", "")).strip()
                if not key or key in index or key in BUILTIN_SERVICE_KEYS:
                    continue
                index[key] = (plugin_id, plugin_name)
        for row in self._read_services_section_rows_cache():
            if not isinstance(row, dict):
                continue
            key = str(row.get("key", "")).strip()
            plugin_id = str(row.get("plugin_id", "")).strip()
            if not key or not plugin_id or key in index or key in BUILTIN_SERVICE_KEYS:
                continue
            plugin_name = str(row.get("plugin_name", plugin_id)).strip() or plugin_id
            index[key] = (plugin_id, plugin_name)
        self._installed_service_key_index = index

    def _service_enabled_for_sort(self, key: str) -> bool:
        service_key = str(key).strip()
        if service_key == "weather":
            weather = self.settings_state.get("weather", {})
            return bool(weather.get("enabled", False)) if isinstance(weather, dict) else False
        if service_key == "ntfy":
            ntfy = self.settings_state.get("ntfy", {})
            return bool(ntfy.get("enabled", False)) if isinstance(ntfy, dict) else False
        return self._service_enabled(service_key)

    def _service_group_for_sort(self, key: str, is_installed: bool) -> int:
        enabled = self._service_enabled_for_sort(key)
        if not is_installed and enabled:
            return 0
        if is_installed and enabled:
            return 1
        if not is_installed and not enabled:
            return 2
        return 3

    def _service_label_for_widget(self, widget: QWidget, key: str) -> str:
        if isinstance(widget, ExpandableServiceSection):
            try:
                return str(widget.title_label.text()).strip() or key.replace("_", " ").title()
            except Exception:
                return key.replace("_", " ").title()
        section_child = widget.findChild(ExpandableServiceSection)
        if isinstance(section_child, ExpandableServiceSection):
            try:
                return str(section_child.title_label.text()).strip() or key.replace("_", " ").title()
            except Exception:
                return key.replace("_", " ").title()
        return key.replace("_", " ").title()

    def _toggle_services_sort_order(self) -> None:
        self._services_sort_desc = not bool(getattr(self, "_services_sort_desc", False))
        if hasattr(self, "services_sort_button"):
            self.services_sort_button.setText("Z→A" if self._services_sort_desc else "A→Z")
        self._refresh_service_widget_order()

    def _cycle_services_visibility_mode(self) -> None:
        current = str(getattr(self, "_services_visibility_mode", "all"))
        mode_order = ["all", "hide_disabled", "hide_enabled"]
        try:
            idx = mode_order.index(current)
        except ValueError:
            idx = 0
        next_mode = mode_order[(idx + 1) % len(mode_order)]
        self._services_visibility_mode = next_mode
        if hasattr(self, "services_visibility_button"):
            label = {
                "all": "All",
                "hide_disabled": "Hide Disabled",
                "hide_enabled": "Hide Enabled",
            }.get(next_mode, "All")
            self.services_visibility_button.setText(label)
        self._refresh_service_widget_order()

    def _services_filter_changed(self, value: str) -> None:
        self._services_filter_query = str(value or "").strip().lower()
        self._refresh_service_widget_order()

    def _refresh_service_widget_order(self) -> None:
        layout = getattr(self, "_services_build_layout", None)
        if not isinstance(layout, QVBoxLayout):
            return
        widgets = list(getattr(self, "_services_section_widgets", []))
        if not widgets:
            return
        for widget in widgets:
            layout.removeWidget(widget)
        widgets.sort(
            key=lambda widget: (
                self._service_label_for_widget(
                    widget, str(widget.property("service_key") or "")
                ).lower(),
                int(widget.property("service_insert_order") or 0),
            ),
            reverse=bool(getattr(self, "_services_sort_desc", False)),
        )
        widgets.sort(
            key=lambda widget: self._service_group_for_sort(
                str(widget.property("service_key") or ""),
                bool(widget.property("service_is_installed")),
            )
        )
        loading_label = getattr(self, "_services_loading_label", None)
        base_index = 1
        if isinstance(loading_label, QLabel):
            try:
                loading_index = layout.indexOf(loading_label)
            except RuntimeError:
                loading_index = -1
                self._services_loading_label = None
            if loading_index >= 0:
                base_index = loading_index + 1
        visibility_mode = str(getattr(self, "_services_visibility_mode", "all"))
        query = str(getattr(self, "_services_filter_query", "")).strip().lower()
        visible_widgets: list[QWidget] = []
        for widget in widgets:
            key = str(widget.property("service_key") or "").strip()
            label = self._service_label_for_widget(widget, key)
            enabled = self._service_enabled_for_sort(key)
            if visibility_mode == "hide_disabled" and not enabled:
                widget.setVisible(False)
                continue
            if visibility_mode == "hide_enabled" and enabled:
                widget.setVisible(False)
                continue
            haystack = f"{key} {label}".lower()
            if query and query not in haystack:
                widget.setVisible(False)
                continue
            widget.setVisible(True)
            visible_widgets.append(widget)
        for index, widget in enumerate(visible_widgets):
            layout.insertWidget(base_index + index, widget)
        self._services_section_widgets = widgets

    def _insert_service_section_widget(
        self, key: str, widget: QWidget, *, is_installed: bool
    ) -> None:
        if not isinstance(widget, QWidget):
            return
        widgets = getattr(self, "_services_section_widgets", [])
        for existing in list(widgets):
            if existing is widget:
                continue
            if str(existing.property("service_key") or "").strip() != str(key).strip():
                continue
            widgets.remove(existing)
            layout = getattr(self, "_services_build_layout", None)
            if isinstance(layout, QVBoxLayout):
                layout.removeWidget(existing)
            existing.deleteLater()
        if widget not in widgets:
            insert_order = int(getattr(self, "_services_widget_insert_counter", 0))
            self._services_widget_insert_counter = insert_order + 1
            widget.setProperty("service_insert_order", insert_order)
            widgets.append(widget)
            self._services_section_widgets = widgets
        widget.setProperty("service_key", str(key).strip())
        widget.setProperty("service_is_installed", bool(is_installed))
        widget.setProperty(
            "service_label", self._service_label_for_widget(widget, str(key).strip())
        )
        self._refresh_service_widget_order()

    def _wrap_service_widget_with_uninstall_action(
        self,
        widget: QWidget,
        plugin_id: str,
        plugin_name: str,
        *,
        service_key: str = "",
        plugin_dir: Path | None = None,
    ) -> QWidget:
        resolved = self._resolve_uninstall_target(
            plugin_id=plugin_id,
            service_key=service_key,
            plugin_dir=plugin_dir,
        )
        if resolved is None:
            return widget
        plugin_id, resolved_name = resolved
        plugin_name = str(resolved_name).strip() or plugin_id
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(8)
        wrapper_layout.addWidget(widget)
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        uninstall_button = QPushButton("Uninstall plugin")
        uninstall_button.setObjectName("secondaryButton")
        uninstall_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        uninstall_button.clicked.connect(
            lambda _checked=False, pid=plugin_id, pname=plugin_name: (
                self._uninstall_plugin_from_services(pid, pname)
            )
        )
        action_row.addWidget(uninstall_button)
        wrapper_layout.addLayout(action_row)
        self._plugin_service_wrappers[plugin_id] = wrapper
        return wrapper

    def _uninstall_plugin_from_services(self, plugin_id: str, plugin_name: str) -> None:
        row = self._installed_plugin_entry_by_id(plugin_id)
        if row is None:
            QMessageBox.information(
                self,
                "Plugin Not Installed",
                f"{plugin_name} is not tracked as an installed plugin.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Uninstall Plugin",
            f"Uninstall {plugin_name} ({plugin_id})?\n\nThis removes the plugin directory and clears marketplace install metadata.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        install_path = Path(str(row.get("install_path", "")).strip()).expanduser()
        receipt = self._load_plugin_install_receipt(plugin_id)
        manifest = (
            self._load_plugin_install_manifest(install_path)
            if install_path.exists()
            else {}
        )
        if not manifest and isinstance(receipt.get("manifest", {}), dict):
            manifest = receipt.get("manifest", {})

        permission_items = self._marketplace_permission_items(
            row, manifest if isinstance(manifest, dict) else None
        )
        uninstall_command = self._resolve_privileged_uninstall_command(
            install_path, manifest if isinstance(manifest, dict) else {}
        )
        if uninstall_command:
            accepted = self._marketplace_show_permission_dialog(
                plugin_name=plugin_name,
                intro_text=(
                    "Uninstall may revert privileged changes performed during installation. "
                    "Continuing can open a Polkit authentication prompt."
                ),
                permission_items=permission_items
                or [
                    {
                        "key": "privileged",
                        "label": "Privileged Uninstall",
                        "description": "Reverts system-level files/services created during install.",
                    }
                ],
                confirm_label="Continue to Uninstall",
            )
            if not accepted:
                return
            if not polkit_available():
                QMessageBox.warning(
                    self,
                    "Uninstall Blocked",
                    "Privileged uninstall requires pkexec, but it is unavailable.",
                )
                return
            ok = run_with_polkit(uninstall_command, detached=False, timeout=180)
            if not ok:
                QMessageBox.warning(
                    self,
                    "Uninstall Failed",
                    "Privileged uninstall failed or was cancelled.",
                )
                return

        self._revert_plugin_desktop_entries(plugin_id, receipt)
        self._remove_plugin_shortcuts_from_i3_config(plugin_id)

        if install_path.exists() and install_path.is_dir():
            try:
                shutil.rmtree(install_path)
            except Exception as exc:
                QMessageBox.warning(
                    self, "Uninstall Failed", f"Unable to remove plugin folder:\n{exc}"
                )
                return
        marketplace = self.settings_state.setdefault("marketplace", {})
        installed = marketplace.get("installed_plugins", [])
        if not isinstance(installed, list):
            installed = []
        installed = [
            entry
            for entry in installed
            if not (
                isinstance(entry, dict)
                and str(entry.get("id", "")).strip() == plugin_id
            )
        ]
        marketplace["installed_plugins"] = installed
        save_settings_state(self.settings_state)
        self._refresh_installed_service_key_index()
        self._clear_plugin_install_receipt(plugin_id)
        wrapper = getattr(self, "_plugin_service_wrappers", {}).get(plugin_id)
        if isinstance(wrapper, QWidget):
            wrapper.setVisible(False)
        QMessageBox.information(
            self,
            "Plugin Uninstalled",
            f"{plugin_name} was uninstalled.\n\nReopen Settings to refresh service sections.",
        )

    def _marketplace_choose_install_dir(self) -> None:
        initial = self.marketplace_install_dir_input.text().strip() or str(
            ROOT / "hanauta" / "plugins"
        )
        selected = QFileDialog.getExistingDirectory(
            self, "Choose plugin install directory", initial
        )
        if selected:
            self.marketplace_install_dir_input.setText(selected)

    def _marketplace_catalog_sources_from_ui(self) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        primary_repo = self.marketplace_repo_input.text().strip()
        primary_branch = self.marketplace_branch_input.text().strip() or "main"
        primary_manifest = (
            self.marketplace_manifest_input.text().strip().lstrip("/") or "plugins.json"
        )
        if primary_repo:
            sources.append(
                {
                    "repo_url": primary_repo,
                    "branch": primary_branch,
                    "manifest_path": primary_manifest,
                }
            )
        lines = self.marketplace_sources_input.toPlainText().splitlines()
        for line in lines:
            raw = line.strip()
            if not raw:
                continue
            if "|" in raw:
                parts = [part.strip() for part in raw.split("|", 2)]
                repo_url = parts[0] if len(parts) >= 1 else ""
                branch = parts[1] if len(parts) >= 2 else "main"
                manifest_path = parts[2] if len(parts) >= 3 else "plugins.json"
            else:
                repo_url = raw
                branch = "main"
                manifest_path = "plugins.json"
            repo_url = str(repo_url).strip()
            if not repo_url:
                continue
            source = {
                "repo_url": repo_url,
                "branch": str(branch).strip() or "main",
                "manifest_path": str(manifest_path).strip().lstrip("/")
                or "plugins.json",
            }
            if any(
                source["repo_url"] == existing["repo_url"]
                and source["branch"] == existing["branch"]
                and source["manifest_path"] == existing["manifest_path"]
                for existing in sources
            ):
                continue
            sources.append(source)
        return sources

    def _marketplace_save_settings(self) -> None:
        marketplace = self.settings_state.setdefault("marketplace", {})
        sources = self._marketplace_catalog_sources_from_ui()
        primary = (
            sources[0]
            if sources
            else {
                "repo_url": self.marketplace_repo_input.text().strip(),
                "branch": self.marketplace_branch_input.text().strip() or "main",
                "manifest_path": self.marketplace_manifest_input.text()
                .strip()
                .lstrip("/")
                or "plugins.json",
            }
        )
        marketplace["catalog_repo_url"] = str(primary.get("repo_url", "")).strip()
        marketplace["catalog_branch"] = (
            str(primary.get("branch", "main")).strip() or "main"
        )
        marketplace["catalog_manifest_path"] = (
            str(primary.get("manifest_path", "plugins.json")).strip().lstrip("/")
            or "plugins.json"
        )
        marketplace["catalog_sources"] = sources
        marketplace["install_dir"] = (
            self.marketplace_install_dir_input.text().strip()
            or str(ROOT / "hanauta" / "plugins")
        )
        save_settings_state(self.settings_state)
        self.marketplace_status.setText("Marketplace configuration saved.")

    def _marketplace_manifest_url_for_source(
        self, repo_url: str, branch: str, manifest_path: str
    ) -> str:
        parsed = parse.urlparse(repo_url)
        if parsed.netloc.lower() == "github.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].removesuffix(".git")
                return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{manifest_path}"
        return repo_url.rstrip("/") + "/" + manifest_path

    def _marketplace_fetch_manifest_payload(
        self, repo_url: str, branch: str, manifest_path: str
    ) -> object:
        parsed = parse.urlparse(repo_url)
        if parsed.netloc.lower() == "github.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].removesuffix(".git")
                api_url = (
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{manifest_path}"
                    f"?ref={branch}"
                )
                try:
                    req = request.Request(
                        api_url,
                        headers={
                            "User-Agent": "HanautaSettings/Marketplace",
                            "Accept": "application/vnd.github+json",
                        },
                    )
                    with request.urlopen(req, timeout=10) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                    if isinstance(payload, dict):
                        content = str(payload.get("content", "")).strip()
                        if content:
                            content = content.replace("\n", "")
                            decoded = base64.b64decode(content).decode("utf-8")
                            return json.loads(decoded)
                except Exception:
                    pass

        manifest_url = self._marketplace_manifest_url_for_source(
            repo_url, branch, manifest_path
        )
        req = request.Request(
            manifest_url, headers={"User-Agent": "HanautaSettings/Marketplace"}
        )
        with request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _marketplace_normalize_catalog(
        self, payload: object
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        plugins: object = payload
        if isinstance(payload, dict):
            plugins = payload.get("plugins", [])
        if not isinstance(plugins, list):
            return rows
        for item in plugins:
            if not isinstance(item, dict):
                continue
            plugin_id = str(item.get("id", "")).strip() or str(
                item.get("name", "")
            ).strip().lower().replace(" ", "_")
            repo = (
                str(item.get("repo", "")).strip()
                or str(item.get("repository", "")).strip()
            )
            if not plugin_id or not repo:
                continue
            capabilities_raw = item.get("capabilities", [])
            capabilities: list[str] = []
            if isinstance(capabilities_raw, dict):
                capabilities = [
                    str(key).strip()
                    for key, enabled in capabilities_raw.items()
                    if str(key).strip() and bool(enabled)
                ]
            elif isinstance(capabilities_raw, list):
                capabilities = [
                    str(value).strip()
                    for value in capabilities_raw
                    if str(value).strip()
                ]
            requirements_raw = item.get("requirements", [])
            requirements: list[str] = []
            if isinstance(requirements_raw, list):
                requirements = [
                    str(value).strip()
                    for value in requirements_raw
                    if str(value).strip()
                ]
            try:
                api_min_version = int(item.get("api_min_version", 1) or 1)
            except Exception:
                api_min_version = 1
            try:
                api_target_version = int(item.get("api_target_version", 1) or 1)
            except Exception:
                api_target_version = 1
            rows.append(
                {
                    "id": plugin_id,
                    "name": str(item.get("name", plugin_id)).strip() or plugin_id,
                    "description": str(item.get("description", "")).strip(),
                    "repo": repo,
                    "branch": str(item.get("branch", "main")).strip() or "main",
                    "path": str(item.get("path", "")).strip(),
                    "entrypoint": str(item.get("entrypoint", "")).strip(),
                    "capabilities": capabilities,
                    "requirements": requirements,
                    "api_min_version": max(1, api_min_version),
                    "api_target_version": max(1, api_target_version),
                    "permissions": item.get("permissions", {})
                    if isinstance(item.get("permissions", {}), dict)
                    else {},
                    "shortcuts": self._marketplace_normalize_shortcuts_field(
                        item.get("shortcuts", [])
                    ),
                }
            )
        return rows

    def _marketplace_refresh_catalog(self) -> None:
        self._marketplace_save_settings()
        sources = self._marketplace_catalog_sources_from_ui()
        if not sources:
            self.marketplace_status.setText(
                "Add at least one catalog source before refreshing."
            )
            return
        merged: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        source_errors: list[str] = []
        for source in sources:
            repo_url = str(source.get("repo_url", "")).strip()
            branch = str(source.get("branch", "main")).strip() or "main"
            manifest_path = (
                str(source.get("manifest_path", "plugins.json")).strip().lstrip("/")
                or "plugins.json"
            )
            if not repo_url:
                continue
            try:
                payload = self._marketplace_fetch_manifest_payload(
                    repo_url, branch, manifest_path
                )
            except Exception as exc:
                source_errors.append(f"{repo_url} ({branch}/{manifest_path}): {exc}")
                continue
            catalog = self._marketplace_normalize_catalog(payload)
            for plugin in catalog:
                plugin_id = str(plugin.get("id", "")).strip()
                if not plugin_id or plugin_id in seen_ids:
                    continue
                seen_ids.add(plugin_id)
                plugin["catalog_source"] = repo_url
                merged.append(plugin)
        if not merged:
            if source_errors:
                self.marketplace_status.setText(
                    "Failed to refresh catalogs: " + " | ".join(source_errors[:2])
                )
            else:
                self.marketplace_status.setText(
                    "Catalog loaded but no valid plugins were found in the configured sources."
                )
            return
        marketplace = self.settings_state.setdefault("marketplace", {})
        marketplace["catalog_cache"] = merged
        save_settings_state(self.settings_state)
        self._marketplace_populate_catalog(merged)
        if source_errors:
            self.marketplace_status.setText(
                f"Catalog refreshed: {len(merged)} plugin(s) from {len(sources) - len(source_errors)}/{len(sources)} source(s)."
            )
        else:
            self.marketplace_status.setText(
                f"Catalog refreshed: {len(merged)} plugin(s) from {len(sources)} source(s)."
            )

    def _marketplace_populate_catalog(self, catalog: list[dict[str, object]]) -> None:
        installed_ids = {
            str(entry.get("id", "")).strip()
            for entry in self.settings_state.get("marketplace", {}).get(
                "installed_plugins", []
            )
            if isinstance(entry, dict)
        }
        self.marketplace_plugin_list.clear()
        for plugin in catalog:
            name = (
                str(plugin.get("name", "")).strip()
                or str(plugin.get("id", "plugin")).strip()
            )
            description = str(plugin.get("description", "")).strip()
            plugin_id = str(plugin.get("id", "")).strip()
            badge = "Installed • " if plugin_id in installed_ids else ""
            secondary = description or f"Plugin id: {plugin_id}"
            label = f"{name}\n{badge}{secondary}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, plugin)
            source_hint = str(plugin.get("catalog_source", "")).strip()
            item.setData(
                Qt.ItemDataRole.UserRole + 1,
                f"{name} {plugin_id} {description} {source_hint}".lower(),
            )
            item.setToolTip(str(plugin.get("repo", "")).strip())
            self.marketplace_plugin_list.addItem(item)
        if self.marketplace_plugin_list.count() > 0:
            self.marketplace_plugin_list.setCurrentRow(0)
        else:
            self.marketplace_detail_label.setText(
                "No plugins in the cached catalog yet. Use Refresh catalog."
            )

    def _marketplace_filter_catalog(self, value: str) -> None:
        needle = value.strip().lower()
        for index in range(self.marketplace_plugin_list.count()):
            item = self.marketplace_plugin_list.item(index)
            haystack = str(item.data(Qt.ItemDataRole.UserRole + 1) or "").lower()
            item.setHidden(bool(needle) and needle not in haystack)

    def _marketplace_update_details(self) -> None:
        item = self.marketplace_plugin_list.currentItem()
        if item is None:
            self.marketplace_detail_label.setText(
                "Select a plugin from the catalog to inspect installation details."
            )
            return
        plugin = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(plugin, dict):
            self.marketplace_detail_label.setText(
                "Plugin metadata is unavailable for this row."
            )
            return
        details = [
            f"Name: {str(plugin.get('name', plugin.get('id', 'plugin')))}",
            f"Repo: {str(plugin.get('repo', ''))}",
            f"Branch: {str(plugin.get('branch', 'main'))}",
        ]
        catalog_source = str(plugin.get("catalog_source", "")).strip()
        if catalog_source:
            details.append(f"Catalog source: {catalog_source}")
        rel_path = str(plugin.get("path", "")).strip()
        if rel_path:
            details.append(f"Path: {rel_path}")
        entrypoint = str(plugin.get("entrypoint", "")).strip()
        if entrypoint:
            details.append(f"Entrypoint: {entrypoint}")
        description = str(plugin.get("description", "")).strip()
        if description:
            details.append(f"Description: {description}")
        capabilities = plugin.get("capabilities", [])
        if isinstance(capabilities, list):
            cap_list = [
                str(value).strip() for value in capabilities if str(value).strip()
            ]
            if cap_list:
                details.append("Capabilities: " + ", ".join(cap_list))
        requirements = plugin.get("requirements", [])
        if isinstance(requirements, list):
            req_list = [
                str(value).strip() for value in requirements if str(value).strip()
            ]
            if req_list:
                details.append("Requirements: " + ", ".join(req_list))
        details.append(f"API min: {int(plugin.get('api_min_version', 1) or 1)}")
        details.append(f"API target: {int(plugin.get('api_target_version', 1) or 1)}")
        permissions = plugin.get("permissions", {})
        if isinstance(permissions, dict) and permissions:
            details.append(
                "Permissions: "
                + ", ".join(
                    sorted(
                        str(key).strip()
                        for key in permissions.keys()
                        if str(key).strip()
                    )
                )
            )
        shortcuts = self._marketplace_normalize_shortcuts_field(
            plugin.get("shortcuts", [])
        )
        if shortcuts:
            details.append(
                "Shortcuts: "
                + ", ".join(
                    f"{str(row.get('combo', '')).strip()}"
                    for row in shortcuts
                    if str(row.get("combo", "")).strip()
                )
            )
        self.marketplace_detail_label.setText("\n".join(details))

    def _marketplace_sanitize_plugin_id(self, value: str) -> str:
        sanitized = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower())
        sanitized = sanitized.strip("-_")
        return sanitized or f"plugin_{int(time.time())}"

    def _marketplace_show_overwrite_dialog(
        self, plugin_id: str, target_dir: Path, *, allow_update: bool
    ) -> str:
        dialog = QDialog(self)
        dialog.setObjectName("pluginOverwriteDialog")
        dialog.setWindowTitle("Plugin Already Installed")
        dialog.setModal(True)
        dialog.setMinimumWidth(560)
        dialog.setStyleSheet(
            """
            QDialog#pluginOverwriteDialog {
                background-color: rgba(14, 18, 26, 0.98);
                border: 1px solid rgba(145, 160, 185, 0.34);
                border-radius: 14px;
            }
            QDialog#pluginOverwriteDialog QLabel {
                color: rgba(246, 235, 247, 0.90);
            }
            QDialog#pluginOverwriteDialog QFrame#overwriteCard {
                background-color: rgba(26, 32, 43, 0.94);
                border: 1px solid rgba(145, 160, 185, 0.30);
                border-radius: 12px;
            }
            QDialog#pluginOverwriteDialog QPushButton#overwriteCancelButton {
                background-color: rgba(96, 112, 136, 0.42);
                color: rgba(246, 235, 247, 0.98);
                border: 1px solid rgba(196, 208, 228, 0.62);
                border-radius: 10px;
                padding: 8px 14px;
                min-width: 90px;
            }
            QDialog#pluginOverwriteDialog QPushButton#overwriteCancelButton:hover {
                background-color: rgba(110, 126, 150, 0.56);
            }
            """
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"{plugin_id} already exists")
        title.setFont(QFont(self.display_font, 12, QFont.Weight.DemiBold))
        layout.addWidget(title)

        body = QLabel(
            (
                f"Current location:\n{target_dir}\n\n"
                "Choose how to continue with this extension."
            )
        )
        body.setWordWrap(True)
        body.setStyleSheet("color: rgba(246,235,247,0.74);")
        layout.addWidget(body)

        card = QFrame()
        card.setObjectName("overwriteCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        if allow_update:
            mode_text = (
                "Overwrite: delete and reinstall from scratch.\n"
                "Update: keep files and run git pull --ff-only."
            )
        else:
            mode_text = "Overwrite: replace the existing extension with the ZIP package."
        hint = QLabel(mode_text)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: rgba(246,235,247,0.80);")
        card_layout.addWidget(hint)
        layout.addWidget(card)

        choice = {"mode": "cancel"}
        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("overwriteCancelButton")
        actions.addWidget(cancel_btn)
        if allow_update:
            update_btn = QPushButton("Update")
            update_btn.setObjectName("secondaryButton")
            actions.addWidget(update_btn)
        overwrite_btn = QPushButton("Overwrite")
        overwrite_btn.setObjectName("primaryButton")
        actions.addWidget(overwrite_btn)
        layout.addLayout(actions)

        cancel_btn.clicked.connect(dialog.reject)
        if allow_update:
            update_btn.clicked.connect(
                lambda: (choice.__setitem__("mode", "update"), dialog.accept())
            )
        overwrite_btn.clicked.connect(
            lambda: (choice.__setitem__("mode", "overwrite"), dialog.accept())
        )

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return "cancel"
        return str(choice.get("mode", "cancel"))

    def _marketplace_show_install_result_dialog(
        self, plugin_label: str, success: bool, detail: str
    ) -> None:
        box = QMessageBox(self)
        box.setObjectName("pluginInstallResultDialog")
        box.setWindowTitle(
            "Extension Installation Successful"
            if success
            else "Extension Installation Failed"
        )
        box.setIcon(
            QMessageBox.Icon.Information if success else QMessageBox.Icon.Warning
        )
        box.setText(plugin_label)
        box.setInformativeText(detail)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet(
            """
            QMessageBox#pluginInstallResultDialog {
                background-color: rgba(14, 18, 26, 0.98);
            }
            QMessageBox#pluginInstallResultDialog QLabel {
                color: rgba(246, 235, 247, 0.90);
                min-width: 360px;
            }
            QMessageBox#pluginInstallResultDialog QPushButton {
                min-height: 34px;
                min-width: 90px;
                border-radius: 10px;
                padding: 0 12px;
                background: rgba(74, 110, 245, 0.78);
                color: rgba(247, 247, 255, 0.98);
                border: 1px solid rgba(164, 186, 255, 0.72);
            }
            QMessageBox#pluginInstallResultDialog QPushButton:hover {
                background: rgba(93, 127, 255, 0.86);
            }
            """
        )
        box.exec()

    def _marketplace_normalize_shortcuts_field(
        self, raw_shortcuts: object
    ) -> list[dict[str, str]]:
        if not isinstance(raw_shortcuts, list):
            return []
        rows: list[dict[str, str]] = []
        for row in raw_shortcuts:
            if not isinstance(row, dict):
                continue
            combo_raw = str(
                row.get("keys", row.get("shortcut", row.get("combo", "")))
            ).strip()
            command = str(row.get("command", row.get("i3_command", ""))).strip()
            description = str(
                row.get("description", row.get("label", row.get("action", "")))
            ).strip()
            combo = self._shortcut_combo_to_i3(combo_raw)
            if not combo or not command:
                continue
            rows.append(
                {
                    "keys": combo_raw or combo,
                    "combo": combo,
                    "command": command,
                    "description": description
                    or f"Trigger {str(row.get('name', 'plugin action')).strip() or 'plugin action'}",
                }
            )
        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in rows:
            signature = (
                f"{row.get('combo', '').strip().lower()}|"
                f"{row.get('command', '').strip().lower()}"
            )
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(row)
        return deduped

    def _shortcut_combo_to_i3(self, combo: str) -> str:
        raw = str(combo).strip()
        if not raw:
            return ""
        parts = [token.strip() for token in re.split(r"[+\s]+", raw) if token.strip()]
        if not parts:
            return ""
        modifier_map = {
            "super": "Mod4",
            "win": "Mod4",
            "windows": "Mod4",
            "mod4": "Mod4",
            "$mod": "Mod4",
            "meta": "Mod4",
            "alt": "Mod1",
            "mod1": "Mod1",
            "control": "Ctrl",
            "ctrl": "Ctrl",
            "shift": "Shift",
        }
        ordered_modifiers = ["Mod4", "Mod1", "Ctrl", "Shift"]
        modifiers: list[str] = []
        key_token = ""
        for token in parts:
            normalized = modifier_map.get(token.lower())
            if normalized is not None:
                if normalized not in modifiers:
                    modifiers.append(normalized)
                continue
            key_token = token
        if not key_token and parts:
            key_token = parts[-1]
        if not key_token:
            return ""
        if key_token.startswith("$"):
            normalized_key = key_token
        elif len(key_token) == 1:
            normalized_key = key_token.lower()
        elif key_token.lower().startswith("xf86"):
            normalized_key = key_token
        else:
            normalized_key = key_token
        sorted_modifiers = [name for name in ordered_modifiers if name in modifiers]
        if sorted_modifiers:
            return "+".join(sorted_modifiers + [normalized_key])
        return normalized_key

    def _canonical_shortcut_combo(
        self, combo: str, variables: dict[str, str] | None = None
    ) -> str:
        raw = str(combo).strip()
        if not raw:
            return ""
        variables = variables or {}
        parts = [token.strip() for token in re.split(r"[+\s]+", raw) if token.strip()]
        if not parts:
            return ""
        expanded_parts: list[str] = []
        for token in parts:
            lowered = token.lower()
            if lowered.startswith("$"):
                resolved = str(variables.get(lowered, "")).strip()
                if resolved:
                    expanded_parts.extend(
                        [
                            part.strip()
                            for part in re.split(r"[+\s]+", resolved)
                            if part.strip()
                        ]
                    )
                    continue
            expanded_parts.append(token)
        modifier_map = {
            "super": "mod4",
            "win": "mod4",
            "windows": "mod4",
            "mod4": "mod4",
            "$mod": "mod4",
            "meta": "mod4",
            "alt": "mod1",
            "mod1": "mod1",
            "control": "ctrl",
            "ctrl": "ctrl",
            "shift": "shift",
        }
        ordered_modifiers = ["mod4", "mod1", "ctrl", "shift"]
        modifiers: set[str] = set()
        keys: list[str] = []
        for token in expanded_parts:
            lowered = token.lower()
            normalized = modifier_map.get(lowered)
            if normalized is not None:
                modifiers.add(normalized)
            else:
                keys.append(lowered)
        if not keys:
            return ""
        prefix = [name for name in ordered_modifiers if name in modifiers]
        return "+".join(prefix + [keys[-1]])

    def _parse_i3_set_variables(self, lines: list[str]) -> dict[str, str]:
        variables: dict[str, str] = {}
        for raw_line in lines:
            line = str(raw_line).strip()
            if not line or line.startswith("#"):
                continue
            active = line.split("#", 1)[0].strip()
            if not active:
                continue
            try:
                tokens = shlex.split(active, posix=True)
            except Exception:
                tokens = active.split()
            if len(tokens) < 3 or tokens[0] != "set":
                continue
            key = str(tokens[1]).strip().lower()
            if not key.startswith("$"):
                continue
            variables[key] = str(tokens[2]).strip()
        return variables

    def _parse_i3_bindsym_line(self, line: str) -> tuple[str, str] | None:
        raw = str(line).strip()
        if not raw or raw.startswith("#"):
            return None
        active = raw.split("#", 1)[0].strip()
        if not active:
            return None
        try:
            tokens = shlex.split(active, posix=True)
        except Exception:
            tokens = active.split()
        if not tokens or tokens[0] != "bindsym":
            return None
        index = 1
        while index < len(tokens) and tokens[index].startswith("--"):
            index += 1
        if index >= len(tokens):
            return None
        combo = str(tokens[index]).strip()
        command = " ".join(tokens[index + 1 :]).strip()
        return combo, command

    def _marketplace_read_i3_config_lines(self) -> list[str]:
        try:
            return I3_CONFIG_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
        except Exception:
            return []

    def _marketplace_write_i3_config_lines(self, lines: list[str]) -> bool:
        try:
            content = "".join(lines)
            I3_CONFIG_FILE.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    def _remove_plugin_shortcut_lines_from_config(
        self, lines: list[str], plugin_id: str
    ) -> list[str]:
        marker_prefix = f"# hanauta-plugin-shortcut:{plugin_id}:"
        section_header = f"# Hanauta marketplace shortcuts for {plugin_id}"
        cleaned: list[str] = []
        skip_next_bindsym = False
        for line in lines:
            stripped = str(line).strip()
            if skip_next_bindsym:
                if stripped.startswith("bindsym "):
                    skip_next_bindsym = False
                    continue
                skip_next_bindsym = False
            if stripped.startswith(marker_prefix):
                skip_next_bindsym = True
                continue
            if stripped == section_header:
                continue
            cleaned.append(line)
        return cleaned

    def _marketplace_show_shortcut_dialog(
        self,
        *,
        title_text: str,
        intro_text: str,
        entries: list[str],
        confirm_label: str,
    ) -> bool:
        dialog = QDialog(self)
        dialog.setObjectName("pluginShortcutDialog")
        dialog.setWindowTitle("Plugin Shortcuts")
        dialog.setModal(True)
        dialog.setMinimumWidth(580)
        dialog.setStyleSheet(
            """
            QDialog#pluginShortcutDialog {
                background-color: rgba(14, 18, 26, 0.98);
                border: 1px solid rgba(145, 160, 185, 0.34);
                border-radius: 14px;
            }
            QDialog#pluginShortcutDialog QLabel {
                color: rgba(246, 235, 247, 0.90);
            }
            QDialog#pluginShortcutDialog QFrame#shortcutListCard {
                background-color: rgba(26, 32, 43, 0.94);
                border: 1px solid rgba(145, 160, 185, 0.30);
                border-radius: 12px;
            }
            QDialog#pluginShortcutDialog QPushButton#shortcutCancelButton {
                background-color: rgba(96, 112, 136, 0.42);
                color: rgba(246, 235, 247, 0.98);
                border: 1px solid rgba(196, 208, 228, 0.62);
                border-radius: 10px;
                padding: 8px 14px;
                min-width: 90px;
            }
            QDialog#pluginShortcutDialog QPushButton#shortcutCancelButton:hover {
                background-color: rgba(110, 126, 150, 0.56);
            }
            """
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(title_text)
        title.setFont(QFont(self.display_font, 12, QFont.Weight.DemiBold))
        layout.addWidget(title)

        body = QLabel(intro_text.strip())
        body.setWordWrap(True)
        body.setStyleSheet("color: rgba(246,235,247,0.74);")
        layout.addWidget(body)

        card = QFrame()
        card.setObjectName("shortcutListCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        if entries:
            for entry in entries:
                row = QLabel(f"• {entry}")
                row.setWordWrap(True)
                row.setStyleSheet("color: rgba(246,235,247,0.84);")
                card_layout.addWidget(row)
        else:
            empty = QLabel("No shortcut details were provided.")
            empty.setStyleSheet("color: rgba(246,235,247,0.70);")
            card_layout.addWidget(empty)
        layout.addWidget(card)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("shortcutCancelButton")
        confirm_btn = QPushButton(confirm_label)
        confirm_btn.setObjectName("primaryButton")
        cancel_btn.clicked.connect(dialog.reject)
        confirm_btn.clicked.connect(dialog.accept)
        actions.addWidget(cancel_btn)
        actions.addWidget(confirm_btn)
        layout.addLayout(actions)
        return dialog.exec() == int(QDialog.DialogCode.Accepted)

    def _reload_i3_keybindings(self) -> bool:
        commands: list[list[str]] = [["i3-msg", "reload"]]
        try:
            sock = subprocess.run(
                ["i3", "--get-socketpath"],
                capture_output=True,
                text=True,
                check=False,
            )
            socket_path = (sock.stdout or "").strip()
            if socket_path:
                commands.append(["i3-msg", "-s", socket_path, "reload"])
        except Exception:
            pass
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception:
                continue
            if result.returncode == 0:
                return True
        return False

    def _marketplace_apply_plugin_shortcuts(
        self, plugin: dict[str, object], plugin_id: str
    ) -> list[str]:
        shortcut_rows = self._marketplace_normalize_shortcuts_field(
            plugin.get("shortcuts", [])
        )
        if not shortcut_rows:
            return []
        plugin_label = str(plugin.get("name", plugin_id)).strip() or plugin_id
        entry_labels = [
            (
                f"{row.get('combo', '')} -> "
                f"{row.get('description', '').strip() or row.get('command', '').strip()}"
            )
            for row in shortcut_rows
        ]
        accepted = self._marketplace_show_shortcut_dialog(
            title_text=f"Apply shortcuts for {plugin_label}?",
            intro_text=(
                "This plugin proposes keyboard shortcuts. "
                "Apply them to your i3 config now?"
            ),
            entries=entry_labels,
            confirm_label="Apply Shortcuts",
        )
        if not accepted:
            return []
        if not I3_CONFIG_FILE.exists():
            QMessageBox.warning(
                self,
                "Shortcut Setup Skipped",
                f"Could not find i3 config file:\n{I3_CONFIG_FILE}",
            )
            return []

        lines = self._marketplace_read_i3_config_lines()
        if not lines:
            QMessageBox.warning(
                self,
                "Shortcut Setup Skipped",
                f"Could not read i3 config file:\n{I3_CONFIG_FILE}",
            )
            return []
        lines = self._remove_plugin_shortcut_lines_from_config(lines, plugin_id)
        variables = self._parse_i3_set_variables(lines)
        binding_index: dict[str, list[tuple[int, str, str]]] = {}
        for idx, line in enumerate(lines):
            parsed = self._parse_i3_bindsym_line(line)
            if parsed is None:
                continue
            combo, command = parsed
            canonical = self._canonical_shortcut_combo(combo, variables)
            if not canonical:
                continue
            bucket = binding_index.setdefault(canonical, [])
            bucket.append((idx, combo, command))

        conflicting: list[dict[str, object]] = []
        for row in shortcut_rows:
            canonical = self._canonical_shortcut_combo(str(row.get("combo", "")), {})
            if not canonical:
                continue
            existing = binding_index.get(canonical, [])
            if existing:
                conflicting.append({"shortcut": row, "existing": existing})

        replace_conflicts = False
        if conflicting:
            conflict_rows: list[str] = []
            for row in conflicting:
                shortcut = row.get("shortcut", {})
                existing = row.get("existing", [])
                if not isinstance(shortcut, dict) or not isinstance(existing, list):
                    continue
                target_combo = str(shortcut.get("combo", "")).strip()
                for _idx, combo, command in existing:
                    conflict_rows.append(
                        f"{target_combo} is already bound to: {combo} {command}"
                    )
            replace_conflicts = self._marketplace_show_shortcut_dialog(
                title_text="Shortcut conflicts detected",
                intro_text=(
                    "Some requested shortcuts are already in use. "
                    "Replace conflicting bindings with the plugin actions?"
                ),
                entries=conflict_rows,
                confirm_label="Replace Conflicts",
            )

        lines_to_remove: set[int] = set()
        skipped_conflicts: set[str] = set()
        if conflicting:
            for row in conflicting:
                shortcut = row.get("shortcut", {})
                existing = row.get("existing", [])
                if not isinstance(shortcut, dict) or not isinstance(existing, list):
                    continue
                combo_label = str(shortcut.get("combo", "")).strip()
                if replace_conflicts:
                    for idx, _combo, _command in existing:
                        lines_to_remove.add(int(idx))
                else:
                    skipped_conflicts.add(combo_label)

        if lines_to_remove:
            lines = [line for idx, line in enumerate(lines) if idx not in lines_to_remove]

        managed_rows: list[str] = []
        applied_entries: list[str] = []
        for row in shortcut_rows:
            combo = str(row.get("combo", "")).strip()
            command = str(row.get("command", "")).strip()
            description = str(row.get("description", "")).strip()
            if not combo or not command:
                continue
            if combo in skipped_conflicts:
                continue
            managed_rows.append(f"# hanauta-plugin-shortcut:{plugin_id}:{combo}\n")
            managed_rows.append(f"bindsym {combo} {command}\n")
            applied_entries.append(
                f"{combo} -> {description or command}"
            )
        if not managed_rows:
            return []
        if lines and not str(lines[-1]).endswith("\n"):
            lines[-1] = f"{lines[-1]}\n"
        if lines:
            lines.append("\n")
        lines.append(f"# Hanauta marketplace shortcuts for {plugin_id}\n")
        lines.extend(managed_rows)
        if not self._marketplace_write_i3_config_lines(lines):
            QMessageBox.warning(
                self,
                "Shortcut Setup Failed",
                f"Failed to write i3 config file:\n{I3_CONFIG_FILE}",
            )
            return []
        if not self._reload_i3_keybindings():
            QMessageBox.warning(
                self,
                "i3 Reload Needed",
                "Shortcuts were saved, but i3 did not reload automatically. Please run i3-msg reload once.",
            )
        return applied_entries

    def _remove_plugin_shortcuts_from_i3_config(self, plugin_id: str) -> None:
        if not I3_CONFIG_FILE.exists():
            return
        lines = self._marketplace_read_i3_config_lines()
        if not lines:
            return
        cleaned = self._remove_plugin_shortcut_lines_from_config(lines, plugin_id)
        if cleaned == lines:
            return
        if self._marketplace_write_i3_config_lines(cleaned):
            self._reload_i3_keybindings()

    def _marketplace_collect_plugin_services(
        self, plugin_dir: Path
    ) -> list[dict[str, object]]:
        entrypoint = plugin_dir / PLUGIN_ENTRYPOINT
        if not entrypoint.exists():
            return []
        plugin_path = str(plugin_dir)
        path_added = False
        try:
            if plugin_path and plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
                path_added = True
            module_name = f"hanauta_plugin_install_{hash(str(entrypoint)) & 0xFFFFFFFF:x}"
            spec = importlib.util.spec_from_file_location(module_name, str(entrypoint))
            if spec is None or spec.loader is None:
                return []
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register_hanauta_plugin", None)
            if not callable(register):
                return []
            payload = register()
        except Exception:
            return []
        finally:
            if path_added:
                try:
                    sys.path.remove(plugin_path)
                except ValueError:
                    pass
        if not isinstance(payload, dict):
            return []
        sections = payload.get("service_sections", [])
        if not isinstance(sections, list):
            return []
        service_rows: list[dict[str, object]] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            key = str(section.get("key", "")).strip()
            if not key:
                continue
            supports_show_in_bar = bool(section.get("supports_show_on_bar", False))
            service_rows.append(
                {
                    "key": key,
                    "supports_show_in_bar": supports_show_in_bar,
                }
            )
        deduped: dict[str, dict[str, object]] = {}
        for row in service_rows:
            key = str(row.get("key", "")).strip()
            if not key:
                continue
            if key not in deduped:
                deduped[key] = dict(row)
                continue
            if bool(row.get("supports_show_in_bar", False)):
                deduped[key]["supports_show_in_bar"] = True
        return [deduped[key] for key in sorted(deduped.keys())]

    def _marketplace_prompt_service_choices(
        self,
        plugin_label: str,
        service_rows: list[dict[str, object]],
    ) -> tuple[list[str], list[str]]:
        if not service_rows:
            return [], []
        keys = [
            str(row.get("key", "")).strip()
            for row in service_rows
            if str(row.get("key", "")).strip()
        ]
        if not keys:
            return [], []
        services_text = ", ".join(keys)
        enable_choice = QMessageBox.question(
            self,
            "Enable Service",
            f"{plugin_label} installed successfully.\n\nEnable service(s) now?\n{services_text}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        enable_services = enable_choice == QMessageBox.StandardButton.Yes
        for key in keys:
            self._set_service_enabled(key, enable_services)

        bar_supported_keys = [
            str(row.get("key", "")).strip()
            for row in service_rows
            if bool(row.get("supports_show_in_bar", False))
            and str(row.get("key", "")).strip()
        ]
        shown_on_bar: list[str] = []
        if enable_services and bar_supported_keys:
            bar_text = ", ".join(sorted(set(bar_supported_keys)))
            bar_choice = QMessageBox.question(
                self,
                "Show on Bar",
                f"This extension supports bar visibility.\n\nShow on bar now?\n{bar_text}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            show_on_bar = bar_choice == QMessageBox.StandardButton.Yes
            for key in sorted(set(bar_supported_keys)):
                self._set_service_bar_visibility(key, show_on_bar)
            if show_on_bar:
                shown_on_bar = sorted(set(bar_supported_keys))

        enabled_keys = sorted(set(keys)) if enable_services else []
        return enabled_keys, shown_on_bar

    def _marketplace_install_selected(self) -> None:
        item = self.marketplace_plugin_list.currentItem()
        if item is None:
            self.marketplace_status.setText(
                "Select a plugin from the catalog before installing."
            )
            return
        plugin = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(plugin, dict):
            self.marketplace_status.setText("Plugin metadata is invalid.")
            return
        repo = str(plugin.get("repo", "")).strip()
        plugin_id = str(plugin.get("id", "")).strip()
        branch = str(plugin.get("branch", "main")).strip() or "main"
        if not repo or not plugin_id:
            self.marketplace_status.setText(
                "Plugin entry is missing a valid id or repo URL."
            )
            return
        api_min_version, api_target_version = self._plugin_api_versions_from_row(plugin)
        if api_min_version > HOST_PLUGIN_API_VERSION:
            self.marketplace_status.setText(
                f"{plugin_id} requires plugin API v{api_min_version}, but this Hanauta build supports v{HOST_PLUGIN_API_VERSION}."
            )
            return
        permission_items = self._marketplace_permission_items(plugin)
        if permission_items:
            accepted = self._marketplace_show_permission_dialog(
                plugin_name=str(plugin.get("name", plugin_id)),
                intro_text="Review requested permissions before installing this plugin.",
                permission_items=permission_items,
                confirm_label="Install",
            )
            if not accepted:
                self.marketplace_status.setText(
                    f"Installation cancelled for {plugin_id}."
                )
                return
        if shutil.which("git") is None:
            self.marketplace_status.setText(
                "git is required to install marketplace plugins."
            )
            return

        install_root = Path(
            self.marketplace_install_dir_input.text().strip()
            or str(ROOT / "hanauta" / "plugins")
        ).expanduser()
        install_root.mkdir(parents=True, exist_ok=True)
        target_dir = install_root / plugin_id
        install_mode = "clone"
        if target_dir.exists():
            install_mode = self._marketplace_show_overwrite_dialog(
                plugin_id, target_dir, allow_update=False
            )
            if install_mode == "cancel":
                self.marketplace_status.setText(
                    f"Installation cancelled for {plugin_id}."
                )
                return
            if install_mode == "overwrite":
                try:
                    shutil.rmtree(target_dir)
                except Exception as exc:
                    self.marketplace_status.setText(
                        f"Cannot overwrite {plugin_id}: {exc}"
                    )
                    self._marketplace_show_install_result_dialog(
                        f"{plugin.get('name', plugin_id)} ({plugin_id})",
                        False,
                        f"Could not overwrite the existing extension folder.\n\n{exc}",
                    )
                    return
                install_mode = "clone"
            else:
                self.marketplace_status.setText(
                    f"Installation cancelled for {plugin_id}."
                )
                return

        try:
            result = subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    branch,
                    repo,
                    str(target_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            self.marketplace_status.setText(f"Failed to install {plugin_id}: {exc}")
            self._marketplace_show_install_result_dialog(
                f"{plugin.get('name', plugin_id)} ({plugin_id})",
                False,
                f"Install failed while running git.\n\n{exc}",
            )
            return

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            self.marketplace_status.setText(
                f"Install failed for {plugin_id}: {stderr or 'git returned an error.'}"
            )
            self._marketplace_show_install_result_dialog(
                f"{plugin.get('name', plugin_id)} ({plugin_id})",
                False,
                stderr or "Git returned an error while installing/updating the extension.",
            )
            return

        marketplace = self.settings_state.setdefault("marketplace", {})
        installed = marketplace.setdefault("installed_plugins", [])
        if not isinstance(installed, list):
            installed = []
            marketplace["installed_plugins"] = installed
        record = {
            "id": plugin_id,
            "name": str(plugin.get("name", plugin_id)),
            "repo": repo,
            "branch": branch,
            "install_path": str(target_dir),
            "capabilities": plugin.get("capabilities", []),
            "requirements": plugin.get("requirements", []),
            "api_min_version": api_min_version,
            "api_target_version": api_target_version,
            "permissions": plugin.get("permissions", {})
            if isinstance(plugin.get("permissions", {}), dict)
            else {},
            "shortcuts": self._marketplace_normalize_shortcuts_field(
                plugin.get("shortcuts", [])
            ),
            "catalog_source": str(plugin.get("catalog_source", "")).strip(),
            "installed_at_epoch": int(time.time()),
        }
        installed = [
            entry
            for entry in installed
            if not (isinstance(entry, dict) and str(entry.get("id", "")) == plugin_id)
        ]
        installed.append(record)
        marketplace["installed_plugins"] = installed
        marketplace["install_dir"] = str(install_root)
        service_rows = self._marketplace_collect_plugin_services(target_dir)
        enabled_keys, bar_keys = self._marketplace_prompt_service_choices(
            str(plugin.get("name", plugin_id)),
            service_rows,
        )
        post_install_ok = self._run_plugin_post_install_steps(plugin, target_dir)
        save_settings_state(self.settings_state)
        if post_install_ok:
            status = f"Installed {plugin_id} into {target_dir}."
            if enabled_keys:
                status += f" Enabled: {', '.join(enabled_keys)}."
            if bar_keys:
                status += f" Showing on bar: {', '.join(bar_keys)}."
            self.marketplace_status.setText(status)
            self._marketplace_show_install_result_dialog(
                f"{plugin.get('name', plugin_id)} ({plugin_id})",
                True,
                status,
            )
        else:
            status = (
                f"Installed {plugin_id}, but post-install setup was cancelled or failed."
            )
            if enabled_keys:
                status += f" Service enablement applied: {', '.join(enabled_keys)}."
            if bar_keys:
                status += f" Showing on bar: {', '.join(bar_keys)}."
            self.marketplace_status.setText(status)
            self._marketplace_show_install_result_dialog(
                f"{plugin.get('name', plugin_id)} ({plugin_id})",
                False,
                status,
            )

    def _marketplace_install_zip(self) -> None:
        install_root = Path(
            self.marketplace_install_dir_input.text().strip()
            or str(ROOT / "hanauta" / "plugins")
        ).expanduser()
        install_root.mkdir(parents=True, exist_ok=True)
        archive_path_str, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Select plugin ZIP",
            str(Path.home()),
            "ZIP files (*.zip)",
        )
        if not archive_path_str:
            return
        archive_path = Path(archive_path_str).expanduser()
        if not archive_path.exists():
            self.marketplace_status.setText("Selected ZIP file does not exist.")
            return
        try:
            with tempfile.TemporaryDirectory(
                prefix="hanauta-plugin-zip-"
            ) as temp_dir_str:
                temp_dir = Path(temp_dir_str)
                with zipfile.ZipFile(archive_path) as bundle:
                    bundle.extractall(temp_dir)
                candidates = [path.parent for path in temp_dir.rglob(PLUGIN_ENTRYPOINT)]
                if not candidates:
                    self.marketplace_status.setText(
                        "ZIP does not contain a plugin entrypoint (hanauta_plugin.py)."
                    )
                    return
                source_dir = sorted(candidates, key=lambda path: len(path.parts))[0]
                raw_plugin_id = (
                    source_dir.name if source_dir.name else archive_path.stem
                )
                plugin_id = self._marketplace_sanitize_plugin_id(
                    raw_plugin_id or archive_path.stem
                )
                target_dir = install_root / plugin_id
                plugin_meta: dict[str, object] = {
                    "id": plugin_id,
                    "name": plugin_id,
                    "repo": f"zip://{archive_path.name}",
                }
                plugin_manifest_path = source_dir / "hanauta_plugin.py"
                if plugin_manifest_path.exists():
                    plugin_meta["entrypoint"] = "hanauta_plugin.py"
                if target_dir.exists():
                    decision = self._marketplace_show_overwrite_dialog(
                        plugin_id, target_dir, allow_update=False
                    )
                    if decision != "overwrite":
                        self.marketplace_status.setText(
                            f"ZIP install cancelled for {plugin_id}."
                        )
                        return
                    shutil.rmtree(target_dir)
                shutil.copytree(source_dir, target_dir)
        except zipfile.BadZipFile:
            self.marketplace_status.setText(
                "The selected file is not a valid ZIP archive."
            )
            self._marketplace_show_install_result_dialog(
                archive_path.name,
                False,
                "The selected extension file is not a valid ZIP archive.",
            )
            return
        except Exception as exc:
            self.marketplace_status.setText(f"ZIP install failed: {exc}")
            self._marketplace_show_install_result_dialog(
                archive_path.name,
                False,
                f"ZIP install failed.\n\n{exc}",
            )
            return

        marketplace = self.settings_state.setdefault("marketplace", {})
        installed = marketplace.setdefault("installed_plugins", [])
        if not isinstance(installed, list):
            installed = []
            marketplace["installed_plugins"] = installed
        record = {
            "id": plugin_id,
            "name": plugin_id,
            "repo": f"zip://{archive_path.name}",
            "branch": "local-zip",
            "install_path": str(target_dir),
            "capabilities": [],
            "requirements": [],
            "api_min_version": 1,
            "api_target_version": HOST_PLUGIN_API_VERSION,
            "permissions": {},
            "shortcuts": [],
            "installed_at_epoch": int(time.time()),
        }
        installed = [
            entry
            for entry in installed
            if not (isinstance(entry, dict) and str(entry.get("id", "")) == plugin_id)
        ]
        installed.append(record)
        marketplace["installed_plugins"] = installed
        marketplace["install_dir"] = str(install_root)
        service_rows = self._marketplace_collect_plugin_services(target_dir)
        enabled_keys, bar_keys = self._marketplace_prompt_service_choices(
            str(plugin_meta.get("name", plugin_id)),
            service_rows,
        )
        post_install_ok = self._run_plugin_post_install_steps(plugin_meta, target_dir)
        save_settings_state(self.settings_state)
        if post_install_ok:
            status = f"Installed ZIP plugin {plugin_id} into {target_dir}."
            if enabled_keys:
                status += f" Enabled: {', '.join(enabled_keys)}."
            if bar_keys:
                status += f" Showing on bar: {', '.join(bar_keys)}."
            self.marketplace_status.setText(status)
            self._marketplace_show_install_result_dialog(
                f"{plugin_id} (ZIP)",
                True,
                status,
            )
        else:
            status = (
                f"Installed ZIP plugin {plugin_id}, but post-install setup was cancelled or failed."
            )
            if enabled_keys:
                status += f" Service enablement applied: {', '.join(enabled_keys)}."
            if bar_keys:
                status += f" Showing on bar: {', '.join(bar_keys)}."
            self.marketplace_status.setText(status)
            self._marketplace_show_install_result_dialog(
                f"{plugin_id} (ZIP)",
                False,
                status,
            )

    def _marketplace_open_install_dir(self) -> None:
        install_dir = Path(
            self.marketplace_install_dir_input.text().strip()
            or str(ROOT / "hanauta" / "plugins")
        ).expanduser()
        install_dir.mkdir(parents=True, exist_ok=True)
        run_bg(["xdg-open", str(install_dir)])

    def _plugin_search_roots(self) -> list[Path]:
        marketplace = self.settings_state.get("marketplace", {})
        configured_root = Path(
            str(marketplace.get("install_dir", str(ROOT / "hanauta" / "plugins")))
        ).expanduser()
        candidates = [
            configured_root,
            ROOT / "hanauta" / "plugins",
        ]
        roots: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = (
                str(candidate.resolve())
                if candidate.exists()
                else str(candidate.expanduser())
            )
            if key in seen:
                continue
            seen.add(key)
            roots.append(candidate)
        return roots

    def _discover_plugin_dirs(self) -> list[Path]:
        marketplace = self.settings_state.get("marketplace", {})
        installed_entries = marketplace.get("installed_plugins", [])
        dirs: list[Path] = []
        seen: set[str] = set()

        if isinstance(installed_entries, list):
            for row in installed_entries:
                if not isinstance(row, dict):
                    continue
                api_min_version, _api_target_version = (
                    self._plugin_api_versions_from_row(row)
                )
                if api_min_version > HOST_PLUGIN_API_VERSION:
                    continue
                plugin_id = str(row.get("id", "")).strip()
                install_path = str(row.get("install_path", "")).strip()
                if not install_path:
                    continue
                plugin_dir = Path(install_path).expanduser()
                if not plugin_dir.exists():
                    continue
                preferred = plugin_dir
                candidate_names: list[str] = []
                if plugin_id:
                    candidate_names.append(plugin_id)
                candidate_names.append(plugin_dir.name)
                repo_url = str(row.get("repo", "")).strip()
                if repo_url:
                    repo_name = Path(parse.urlparse(repo_url).path).name
                    if repo_name.endswith(".git"):
                        repo_name = repo_name[:-4]
                    if repo_name:
                        candidate_names.append(repo_name)
                for candidate_name in candidate_names:
                    dev_dir = (PLUGIN_DEV_ROOT / candidate_name).expanduser()
                    if (dev_dir / PLUGIN_ENTRYPOINT).exists():
                        preferred = dev_dir
                        break
                resolved = str(preferred.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                dirs.append(preferred)

        cached_dirs = self._cached_service_plugin_dirs()
        for cached_dir in cached_dirs:
            resolved = str(cached_dir.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            dirs.append(cached_dir)
        if cached_dirs:
            self._queue_services_section_cache_refresh()
            return dirs

        for root in self._plugin_search_roots():
            if not root.exists() or not root.is_dir():
                continue
            try:
                children = sorted(root.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir():
                    continue
                if not (child / PLUGIN_ENTRYPOINT).exists():
                    continue
                resolved = str(child.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                dirs.append(child)
        if PLUGIN_DEV_ROOT.exists() and PLUGIN_DEV_ROOT.is_dir():
            try:
                dev_children = sorted(PLUGIN_DEV_ROOT.iterdir())
            except OSError:
                dev_children = []
            for child in dev_children:
                if not child.is_dir():
                    continue
                if not child.name.startswith("hanauta-plugin-"):
                    continue
                if not (child / PLUGIN_ENTRYPOINT).exists():
                    continue
                resolved = str(child.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                dirs.append(child)
        self._queue_services_section_cache_refresh()
        return dirs

    def _plugin_root_icon_path(self, plugin_dir: Path | None) -> str:
        if plugin_dir is None:
            return ""
        for name in ("icon.svg", "icon.png"):
            candidate = plugin_dir / name
            if candidate.exists():
                return str(candidate)
        return ""

    def _plugin_api(self, plugin_dir: Path | None = None) -> dict[str, object]:
        return {
            "SettingsRow": SettingsRow,
            "SwitchButton": SwitchButton,
            "ExpandableServiceSection": ExpandableServiceSection,
            "material_icon": material_icon,
            "entry_command": entry_command,
            "run_bg": run_bg,
            "plugin_icon_path": self._plugin_root_icon_path(plugin_dir),
            "icon_font": self.icon_font,
            "ui_font": self.ui_font,
            "polkit_available": polkit_available,
            "build_polkit_command": build_polkit_command,
            "run_with_polkit": run_with_polkit,
            "trigger_fullscreen_alert": trigger_fullscreen_alert,
        }

    def _collect_plugin_builders_from_dir(
        self, plugin_dir: Path
    ) -> dict[str, dict[str, object]]:
        builders: dict[str, dict[str, object]] = {}
        entrypoint = plugin_dir / PLUGIN_ENTRYPOINT
        if not entrypoint.exists():
            return builders
        module_name = f"hanauta_plugin_{hash(str(entrypoint)) & 0xFFFFFFFF:x}"
        plugin_path = str(plugin_dir)
        path_added = False
        try:
            if plugin_path and plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
                path_added = True
            spec = importlib.util.spec_from_file_location(module_name, str(entrypoint))
            if spec is None or spec.loader is None:
                return builders
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register_hanauta_plugin", None)
            if not callable(register):
                return builders
            payload = register()
        except Exception:
            return builders
        finally:
            if path_added:
                try:
                    sys.path.remove(plugin_path)
                except ValueError:
                    pass
        if not isinstance(payload, dict):
            return builders
        plugin_id = str(payload.get("id", "")).strip()
        plugin_name = str(
            payload.get("name", plugin_id or plugin_dir.name)
        ).strip() or (plugin_id or plugin_dir.name)
        api_min_version, _api_target_version = self._plugin_api_versions_from_row(payload)
        if api_min_version > HOST_PLUGIN_API_VERSION:
            return builders
        sections = payload.get("service_sections", [])
        if not isinstance(sections, list):
            return builders
        for section in sections:
            if not isinstance(section, dict):
                continue
            key = str(section.get("key", "")).strip()
            builder = section.get("builder")
            if not key or not callable(builder):
                continue
            builders[key] = {
                "builder": builder,
                "plugin_dir": plugin_dir,
                "plugin_id": plugin_id,
                "plugin_name": plugin_name,
            }
        return builders

    def _queue_plugin_builders(self) -> None:
        plugin_queue: list[dict[str, object]] = []
        for key in sorted(self.plugin_service_builders.keys()):
            if key in BUILTIN_SERVICE_KEYS:
                continue
            section_meta = self.plugin_service_builders.get(key, {})
            if not isinstance(section_meta, dict):
                continue
            section_meta = dict(section_meta)
            section_meta["_key"] = key
            plugin_queue.append(section_meta)
        self._services_plugin_queue = plugin_queue

    def _process_next_plugin_dir(self) -> None:
        if not getattr(self, "_plugin_dirs_to_scan", []):
            self._plugin_dir_scan_in_progress = False
            self._plugin_builders_loaded = True
            self._queue_plugin_builders()
            QTimer.singleShot(18, self._build_next_services_section)
            return
        plugin_dir = self._plugin_dirs_to_scan.pop(0)
        builders = self._collect_plugin_builders_from_dir(plugin_dir)
        if builders:
            self.plugin_service_builders.update(builders)
        QTimer.singleShot(16, self._process_next_plugin_dir)

    def _start_plugin_dir_scan(self) -> None:
        if bool(getattr(self, "_plugin_dir_scan_in_progress", False)):
            return
        if bool(getattr(self, "_plugin_builders_loaded", False)):
            return
        self._plugin_dir_scan_scheduled = False
        self._plugin_dirs_to_scan = self._discover_plugin_dirs()
        self.plugin_service_builders = {}
        self._services_plugin_queue = []
        self._plugin_dir_scan_in_progress = True
        QTimer.singleShot(16, self._process_next_plugin_dir)

    def _build_services_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("settings"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Services")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        header.addWidget(icon)
        header.addWidget(title)
        self._services_filter_query = ""
        self._services_sort_desc = False
        self._services_visibility_mode = "all"
        self.services_search_input = QLineEdit()
        self.services_search_input.setPlaceholderText("Search services/plugins")
        self.services_search_input.setObjectName("settingsInput")
        self.services_search_input.setMinimumWidth(220)
        self.services_search_input.textChanged.connect(self._services_filter_changed)
        self.services_sort_button = QPushButton("A→Z")
        self.services_sort_button.setObjectName("secondaryButton")
        self.services_sort_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.services_sort_button.clicked.connect(self._toggle_services_sort_order)
        self.services_visibility_button = QPushButton("All")
        self.services_visibility_button.setObjectName("secondaryButton")
        self.services_visibility_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.services_visibility_button.clicked.connect(
            self._cycle_services_visibility_mode
        )
        header.addWidget(self.services_search_input)
        header.addWidget(self.services_sort_button)
        header.addWidget(self.services_visibility_button)
        header.addStretch(1)
        layout.addLayout(header)

        self.service_sections: dict[str, ExpandableServiceSection] = {}
        self.service_display_switches: dict[str, SwitchButton] = {}
        self._plugin_service_wrappers: dict[str, QWidget] = {}
        self._services_section_widgets: list[QWidget] = []
        self._services_widget_insert_counter = 0
        self._refresh_installed_service_key_index()
        self._services_build_layout = layout
        self._services_build_finished = False
        self._services_core_queue = [
            ("mail", self._build_mail_service_section),
            ("kdeconnect", self._build_kdeconnect_service_section),
            ("weather", self._build_weather_section),
            ("calendar_widget", self._build_calendar_service_section),
            ("desktop_clock_widget", self._build_desktop_clock_service_section),
        ]
        self._services_plugin_queue: list[dict[str, object]] = []
        self._services_cached_plugin_queue = self._read_services_section_rows_cache()
        self._services_cached_plugins_used = bool(self._services_cached_plugin_queue)
        self._services_loading_label = QLabel("Loading service sections...")
        self._services_loading_label.setWordWrap(True)
        self._services_loading_label.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self._services_loading_label)
        self._services_sections_built = 0
        self._plugin_dir_scan_scheduled = False
        # Let Qt paint the tab immediately, then progressively add sections.
        QTimer.singleShot(25, self._build_next_services_section)
        return card

    def _add_plugin_service_widget(
        self,
        key: str,
        widget: QWidget,
        plugin_id: str,
        plugin_name: str,
        plugin_dir: Path | None = None,
    ) -> None:
        self._insert_service_section_widget(
            key,
            self._wrap_service_widget_with_uninstall_action(
                widget,
                plugin_id,
                plugin_name,
                service_key=key,
                plugin_dir=plugin_dir,
            ),
            is_installed=True,
        )

    def _replace_service_section_widget(
        self, key: str, new_widget: QWidget, expand_after_replace: bool = False
    ) -> None:
        layout = getattr(self, "_services_build_layout", None)
        if not isinstance(layout, QVBoxLayout):
            return
        old_widget = self.service_sections.get(key)
        widgets = getattr(self, "_services_section_widgets", [])
        removable = old_widget if old_widget in widgets else None
        if removable is None:
            for candidate in widgets:
                if str(candidate.property("service_key") or "").strip() == str(key).strip():
                    removable = candidate
                    break
        if removable is not None and removable in widgets:
            widgets.remove(removable)
            self._services_section_widgets = widgets
            layout.removeWidget(removable)
            removable.deleteLater()
        if isinstance(new_widget, ExpandableServiceSection):
            self.service_sections[key] = new_widget
            if expand_after_replace:
                new_widget.set_expanded(True)
        self._insert_service_section_widget(
            key,
            new_widget,
            is_installed=bool(new_widget.property("service_is_installed")),
        )

    def _build_cached_plugin_service_stub(self, row: dict[str, object]) -> QWidget:
        key = str(row.get("key", "")).strip()
        label = str(row.get("label", key.replace("_", " ").title())).strip() or key
        icon_name = str(row.get("icon", "widgets")).strip() or "widgets"
        plugin_dir = str(row.get("plugin_dir", "")).strip()
        plugin_id = str(row.get("plugin_id", "")).strip()
        plugin_name = (
            str(row.get("plugin_name", plugin_id)).strip() or plugin_id
        )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        status_label = QLabel(
            "Loaded from hanauta-service cache. Advanced plugin settings are lazy-loaded on demand."
        )
        status_label.setWordWrap(True)
        status_label.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(status_label)

        load_button = QPushButton("Load advanced settings")
        load_button.setObjectName("secondaryButton")
        load_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Plugin settings",
                "Load full plugin-defined settings UI only when needed.",
                self.icon_font,
                self.ui_font,
                load_button,
            )
        )
        load_button.clicked.connect(
            lambda _checked=False, section_key=key, section_dir=plugin_dir, status=status_label: self._load_cached_plugin_section_on_demand(
                section_key, section_dir, status
            )
        )

        section = ExpandableServiceSection(
            key,
            label,
            "Plugin service section (cache-backed).",
            material_icon(icon_name),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled(key),
            lambda enabled, current_key=key: self._set_service_enabled(
                current_key, enabled
            ),
        )
        self.service_sections[key] = section
        if not plugin_id:
            plugin_meta = self._installed_plugin_for_service_key(key)
            if plugin_meta is not None:
                plugin_id, plugin_name = plugin_meta
        return self._wrap_service_widget_with_uninstall_action(
            section,
            plugin_id,
            plugin_name,
            service_key=key,
            plugin_dir=Path(plugin_dir).expanduser() if plugin_dir else None,
        )

    def _load_cached_plugin_section_on_demand(
        self, key: str, plugin_dir_raw: str, status_label: QLabel
    ) -> None:
        plugin_dir = Path(plugin_dir_raw).expanduser()
        if not plugin_dir.exists():
            status_label.setText("Plugin directory is missing, so advanced settings cannot be loaded.")
            return
        status_label.setText("Loading advanced settings...")
        QApplication.processEvents()

        def _load() -> None:
            builders = self._collect_plugin_builders_from_dir(plugin_dir)
            section_meta = builders.get(key, {}) if isinstance(builders, dict) else {}
            builder = section_meta.get("builder") if isinstance(section_meta, dict) else None
            plugin_id = str(section_meta.get("plugin_id", "")).strip() if isinstance(section_meta, dict) else ""
            plugin_name = (
                str(section_meta.get("plugin_name", plugin_id)).strip() if isinstance(section_meta, dict) else ""
            ) or plugin_id
            if not callable(builder):
                status_label.setText("This plugin does not expose advanced settings for this section.")
                return
            try:
                widget = builder(self, self._plugin_api(plugin_dir))
            except Exception:
                status_label.setText("Failed to load advanced plugin settings.")
                return
            if not isinstance(widget, QWidget):
                status_label.setText("Plugin returned invalid settings content.")
                return

            if not plugin_id:
                plugin_meta = self._installed_plugin_for_service_key(key)
                if plugin_meta is not None:
                    plugin_id, plugin_name = plugin_meta
            target_widget = widget
            target_widget = self._wrap_service_widget_with_uninstall_action(
                target_widget,
                plugin_id,
                plugin_name,
                service_key=key,
                plugin_dir=plugin_dir,
            )
            target_widget.setProperty("service_is_installed", True)
            self._replace_service_section_widget(key, target_widget, expand_after_replace=True)

        QTimer.singleShot(0, _load)

    def _build_next_services_section(self) -> None:
        layout = getattr(self, "_services_build_layout", None)
        if not isinstance(layout, QVBoxLayout):
            return

        core_queue = getattr(self, "_services_core_queue", [])
        if core_queue:
            key, builder = core_queue.pop(0)
            if self._installed_plugin_for_service_key(key) is not None:
                QTimer.singleShot(0, self._build_next_services_section)
                return
            try:
                widget = builder()
            except Exception:
                widget = None
            if isinstance(widget, QWidget):
                self._insert_service_section_widget(key, widget, is_installed=False)
            self._services_sections_built = int(
                getattr(self, "_services_sections_built", 0)
            ) + 1
            if str(getattr(self, "initial_service_section", "")).strip() == str(key):
                QTimer.singleShot(
                    0,
                    lambda current_key=str(key): self._focus_service_section(
                        current_key
                    ),
                )
            delay_ms = 0 if self._services_sections_built <= 2 else 18
            QTimer.singleShot(delay_ms, self._build_next_services_section)
            return

        cached_plugin_queue = getattr(self, "_services_cached_plugin_queue", [])
        if cached_plugin_queue:
            row = cached_plugin_queue.pop(0)
            if isinstance(row, dict):
                row_key = str(row.get("key", "")).strip()
                if row_key in BUILTIN_SERVICE_KEYS:
                    QTimer.singleShot(0, self._build_next_services_section)
                    return
                try:
                    widget = self._build_cached_plugin_service_stub(row)
                except Exception:
                    widget = None
                if isinstance(widget, QWidget):
                    self._insert_service_section_widget(
                        row_key,
                        widget,
                        is_installed=True,
                    )
            QTimer.singleShot(12, self._build_next_services_section)
            return

        if not getattr(self, "_plugin_builders_loaded", False):
            if not getattr(self, "_plugin_dir_scan_in_progress", False):
                if not bool(getattr(self, "_plugin_dir_scan_scheduled", False)):
                    self._plugin_dir_scan_scheduled = True
                    QTimer.singleShot(120, self._start_plugin_dir_scan)
            return

        plugin_queue = getattr(self, "_services_plugin_queue", [])
        if plugin_queue:
            section_meta = plugin_queue.pop(0)
            key = str(section_meta.get("_key", "")).strip()
            builder = section_meta.get("builder")
            plugin_dir = section_meta.get("plugin_dir")
            plugin_id = str(section_meta.get("plugin_id", "")).strip()
            plugin_name = (
                str(section_meta.get("plugin_name", plugin_id)).strip() or plugin_id
            )
            if callable(builder):
                try:
                    widget = builder(
                        self,
                        self._plugin_api(
                            plugin_dir if isinstance(plugin_dir, Path) else None
                        ),
                    )
                except Exception:
                    widget = None
                if isinstance(widget, QWidget):
                    if key in getattr(self, "service_sections", {}):
                        replacement = self._wrap_service_widget_with_uninstall_action(
                            widget,
                            plugin_id,
                            plugin_name,
                            service_key=key,
                            plugin_dir=plugin_dir if isinstance(plugin_dir, Path) else None,
                        )
                        replacement.setProperty("service_is_installed", True)
                        self._replace_service_section_widget(
                            key, replacement, expand_after_replace=False
                        )
                    else:
                        self._add_plugin_service_widget(
                            key,
                            widget,
                            plugin_id,
                            plugin_name,
                            plugin_dir if isinstance(plugin_dir, Path) else None,
                        )
                    if str(getattr(self, "initial_service_section", "")).strip() == key:
                        QTimer.singleShot(
                            0,
                            lambda current_key=key: self._focus_service_section(
                                current_key
                            ),
                        )
            QTimer.singleShot(22, self._build_next_services_section)
            return

        if not getattr(self, "_services_build_finished", False):
            self._services_build_finished = True
            if isinstance(getattr(self, "_services_loading_label", None), QLabel):
                loading_label = self._services_loading_label
                loading_label.setText("Services ready.")
                QTimer.singleShot(700, loading_label.deleteLater)
                self._services_loading_label = None
            layout.addStretch(1)
            if str(getattr(self, "initial_service_section", "")).strip():
                QTimer.singleShot(
                    0, lambda: self._focus_service_section(self.initial_service_section)
                )

    def _focus_service_section(self, key: str) -> None:
        section = getattr(self, "service_sections", {}).get(key)
        if section is None:
            return
        if section.enabled_switch.isChecked():
            section.set_expanded(True)
            section.header_button.setFocus()
        self.initial_service_section = ""

    def _build_mail_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.mail_account_picker = QComboBox()
        self.mail_account_picker.setObjectName("settingsCombo")
        self.mail_account_picker.currentIndexChanged.connect(
            self._load_selected_mail_account
        )
        layout.addWidget(
            SettingsRow(
                material_icon("mail"),
                "Saved account",
                "Pick an existing IMAP/SMTP account or start a fresh one.",
                self.icon_font,
                self.ui_font,
                self.mail_account_picker,
            )
        )

        self.mail_label_input = QLineEdit()
        self.mail_label_input.setPlaceholderText("Personal")
        self.mail_display_name_input = QLineEdit()
        self.mail_display_name_input.setPlaceholderText("Your name")
        self.mail_email_input = QLineEdit()
        self.mail_email_input.setPlaceholderText("you@example.com")
        self.mail_username_input = QLineEdit()
        self.mail_username_input.setPlaceholderText("IMAP/SMTP login")
        self.mail_password_input = QLineEdit()
        self.mail_password_input.setPlaceholderText("App password")
        self.mail_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.mail_imap_host_input = QLineEdit()
        self.mail_imap_host_input.setPlaceholderText("imap.example.com")
        self.mail_imap_port_input = QLineEdit("993")
        self.mail_smtp_host_input = QLineEdit()
        self.mail_smtp_host_input.setPlaceholderText("smtp.example.com")
        self.mail_smtp_port_input = QLineEdit("587")
        self.mail_signature_input = QLineEdit()
        self.mail_signature_input.setPlaceholderText("Sent from Hanauta Mail")
        self.mail_poll_interval_input = QLineEdit("90")
        self.mail_avatar_path_input = QLineEdit()
        self.mail_avatar_path_input.setPlaceholderText(
            "Optional profile image for this account"
        )
        self.mail_storage_path_input = QLineEdit(load_mail_storage_config()["db_path"])
        self.mail_storage_path_input.setPlaceholderText(str(MAIL_DB_PATH))

        layout.addWidget(
            SettingsRow(
                material_icon("settings"),
                "Label",
                "Friendly account label shown in Hanauta Mail.",
                self.icon_font,
                self.ui_font,
                self.mail_label_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "Display name",
                "Used for outgoing mail sender formatting.",
                self.icon_font,
                self.ui_font,
                self.mail_display_name_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("mail"),
                "Email address",
                "Primary mailbox address.",
                self.icon_font,
                self.ui_font,
                self.mail_email_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "Username",
                "Login used by both IMAP and SMTP on most providers.",
                self.icon_font,
                self.ui_font,
                self.mail_username_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Password",
                "Use an app password when your provider requires one.",
                self.icon_font,
                self.ui_font,
                self.mail_password_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("settings"),
                "IMAP host",
                "Incoming mail server, such as imap.gmail.com.",
                self.icon_font,
                self.ui_font,
                self.mail_imap_host_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "IMAP port",
                "Usually 993 with SSL enabled.",
                self.icon_font,
                self.ui_font,
                self.mail_imap_port_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("settings"),
                "SMTP host",
                "Outgoing mail server, such as smtp.gmail.com.",
                self.icon_font,
                self.ui_font,
                self.mail_smtp_host_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "SMTP port",
                "Usually 587 with STARTTLS or 465 with SSL.",
                self.icon_font,
                self.ui_font,
                self.mail_smtp_port_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("mail"),
                "Signature",
                "Appended to new messages and replies.",
                self.icon_font,
                self.ui_font,
                self.mail_signature_input,
            )
        )
        avatar_row = QWidget()
        avatar_layout = QHBoxLayout(avatar_row)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setSpacing(8)
        avatar_layout.addWidget(self.mail_avatar_path_input, 1)
        self.mail_choose_avatar_button = QPushButton("Choose")
        self.mail_choose_avatar_button.setObjectName("secondaryButton")
        self.mail_choose_avatar_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.mail_choose_avatar_button.clicked.connect(self._choose_mail_avatar)
        avatar_layout.addWidget(self.mail_choose_avatar_button)
        layout.addWidget(
            SettingsRow(
                material_icon("mail"),
                "Account avatar",
                "Shown in Hanauta Mail next to the server status chip.",
                self.icon_font,
                self.ui_font,
                avatar_row,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Sync interval (sec)",
                "Background refresh cadence for this account.",
                self.icon_font,
                self.ui_font,
                self.mail_poll_interval_input,
            )
        )
        storage_row = QWidget()
        storage_layout = QHBoxLayout(storage_row)
        storage_layout.setContentsMargins(0, 0, 0, 0)
        storage_layout.setSpacing(8)
        storage_layout.addWidget(self.mail_storage_path_input, 1)
        self.mail_choose_storage_button = QPushButton("Choose")
        self.mail_choose_storage_button.setObjectName("secondaryButton")
        self.mail_choose_storage_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.mail_choose_storage_button.clicked.connect(self._choose_mail_storage_path)
        storage_layout.addWidget(self.mail_choose_storage_button)
        layout.addWidget(
            SettingsRow(
                material_icon("storage"),
                "Encrypted mail store",
                "Choose where Hanauta Mail keeps its encrypted local database under local state.",
                self.icon_font,
                self.ui_font,
                storage_row,
            )
        )

        self.mail_imap_ssl_switch = SwitchButton(True)
        self.mail_smtp_starttls_switch = SwitchButton(True)
        self.mail_smtp_ssl_switch = SwitchButton(False)
        self.mail_notify_switch = SwitchButton(True)
        mail_settings = self.settings_state.setdefault("mail", {})
        self.mail_global_notify_switch = SwitchButton(
            bool(mail_settings.get("notify_new_messages", True))
        )
        self.mail_sound_notify_switch = SwitchButton(
            bool(mail_settings.get("play_notification_sound", False))
        )
        self.mail_hide_content_switch = SwitchButton(
            bool(mail_settings.get("hide_notification_content", False))
        )
        self.mail_global_notify_switch.toggledValue.connect(
            self._set_mail_notifications_enabled
        )
        self.mail_sound_notify_switch.toggledValue.connect(
            self._set_mail_notification_sound_enabled
        )
        self.mail_hide_content_switch.toggledValue.connect(
            self._set_mail_hide_notification_content
        )
        layout.addWidget(
            SettingsRow(
                material_icon("shield"),
                "IMAP SSL",
                "Keep this enabled for almost every modern provider.",
                self.icon_font,
                self.ui_font,
                self.mail_imap_ssl_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("mail"),
                "SMTP STARTTLS",
                "Use STARTTLS when your SMTP port is 587.",
                self.icon_font,
                self.ui_font,
                self.mail_smtp_starttls_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("shield"),
                "SMTP SSL",
                "Use this instead of STARTTLS when your provider wants port 465.",
                self.icon_font,
                self.ui_font,
                self.mail_smtp_ssl_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_active"),
                "Desktop notifications",
                "Allow this mailbox to send new mail notifications.",
                self.icon_font,
                self.ui_font,
                self.mail_notify_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_active"),
                "Notify on new mail",
                "Show desktop notifications when new messages arrive.",
                self.icon_font,
                self.ui_font,
                self.mail_global_notify_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications"),
                "Notification sound",
                "Play a sound when a new mail toast is shown.",
                self.icon_font,
                self.ui_font,
                self.mail_sound_notify_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("shield"),
                "Hide notification content",
                "Use a privacy-friendly notification message without subject or preview text.",
                self.icon_font,
                self.ui_font,
                self.mail_hide_content_switch,
            )
        )

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.mail_new_button = QPushButton("New account")
        self.mail_new_button.setObjectName("secondaryButton")
        self.mail_save_button = QPushButton("Save account")
        self.mail_save_button.setObjectName("primaryButton")
        self.mail_delete_button = QPushButton("Delete account")
        self.mail_delete_button.setObjectName("secondaryButton")
        self.mail_open_button = QPushButton("Open Hanauta Mail")
        self.mail_open_button.setObjectName("secondaryButton")
        for button in (
            self.mail_new_button,
            self.mail_save_button,
            self.mail_delete_button,
            self.mail_open_button,
        ):
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.mail_new_button.clicked.connect(self._clear_mail_account_form)
        self.mail_save_button.clicked.connect(self._save_mail_account_settings)
        self.mail_delete_button.clicked.connect(self._delete_mail_account_settings)
        self.mail_open_button.clicked.connect(self._launch_mail_client)
        actions.addWidget(self.mail_new_button)
        actions.addWidget(self.mail_save_button)
        actions.addWidget(self.mail_delete_button)
        actions.addWidget(self.mail_open_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        integration_actions = QHBoxLayout()
        integration_actions.setSpacing(8)
        self.mail_favorite_button = QPushButton("Set Favorite Mail Client")
        self.mail_favorite_button.setObjectName("secondaryButton")
        self.mail_mailto_button = QPushButton("Handle mailto Links")
        self.mail_mailto_button.setObjectName("secondaryButton")
        for button in (self.mail_favorite_button, self.mail_mailto_button):
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.mail_favorite_button.clicked.connect(
            self._set_hanauta_mail_favorite_client
        )
        self.mail_mailto_button.clicked.connect(self._set_hanauta_mailto_handler)
        integration_actions.addWidget(self.mail_favorite_button)
        integration_actions.addWidget(self.mail_mailto_button)
        integration_actions.addStretch(1)
        layout.addLayout(integration_actions)

        self.mail_status = QLabel(
            "Mail accounts are stored in Hanauta Mail's shared database."
        )
        self.mail_status.setWordWrap(True)
        self.mail_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.mail_status)

        section = ExpandableServiceSection(
            "mail",
            "Mail",
            "Configure multiple IMAP/SMTP accounts for Hanauta Mail and jump straight into the client.",
            material_icon("mail"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("mail"),
            lambda enabled: self._set_service_enabled("mail", enabled),
        )
        self.service_sections["mail"] = section
        self._reload_mail_accounts()
        QTimer.singleShot(0, self._queue_mail_integration_button_sync)
        return section

    def _reload_mail_accounts(self, selected_account_id: int = 0) -> None:
        accounts = self.mail_account_store.list_accounts()
        self.mail_accounts = accounts
        self.mail_account_picker.blockSignals(True)
        self.mail_account_picker.clear()
        self.mail_account_picker.addItem("New account", 0)
        target_index = 0
        for index, account in enumerate(accounts, start=1):
            self.mail_account_picker.addItem(
                f"{account.get('label') or account.get('email_address')} · {account.get('email_address', '')}",
                int(account.get("id", 0)),
            )
            if int(account.get("id", 0)) == int(selected_account_id):
                target_index = index
        self.mail_account_picker.setCurrentIndex(target_index)
        self.mail_account_picker.blockSignals(False)
        self._load_selected_mail_account(target_index)

    def _load_selected_mail_account(self, index: int) -> None:
        account_id = (
            int(self.mail_account_picker.itemData(index) or 0)
            if hasattr(self, "mail_account_picker")
            else 0
        )
        account = (
            self.mail_account_store.get_account(account_id) if account_id > 0 else None
        )
        if not account:
            self._clear_mail_account_form(update_picker=False)
            self.mail_delete_button.setEnabled(False)
            return
        self.mail_label_input.setText(str(account.get("label", "")))
        self.mail_display_name_input.setText(str(account.get("display_name", "")))
        self.mail_email_input.setText(str(account.get("email_address", "")))
        self.mail_username_input.setText(str(account.get("username", "")))
        self.mail_password_input.setText(str(account.get("password", "")))
        self.mail_imap_host_input.setText(str(account.get("imap_host", "")))
        self.mail_imap_port_input.setText(str(account.get("imap_port", 993)))
        self.mail_smtp_host_input.setText(str(account.get("smtp_host", "")))
        self.mail_smtp_port_input.setText(str(account.get("smtp_port", 587)))
        self.mail_signature_input.setText(str(account.get("signature", "")))
        self.mail_avatar_path_input.setText(str(account.get("avatar_path", "")))
        self.mail_poll_interval_input.setText(
            str(account.get("poll_interval_seconds", 90))
        )
        self.mail_imap_ssl_switch.setChecked(bool(account.get("imap_ssl", True)))
        self.mail_imap_ssl_switch._apply_state()
        self.mail_smtp_starttls_switch.setChecked(
            bool(account.get("smtp_starttls", True))
        )
        self.mail_smtp_starttls_switch._apply_state()
        self.mail_smtp_ssl_switch.setChecked(bool(account.get("smtp_ssl", False)))
        self.mail_smtp_ssl_switch._apply_state()
        self.mail_notify_switch.setChecked(bool(account.get("notify_enabled", True)))
        self.mail_notify_switch._apply_state()
        self.mail_delete_button.setEnabled(True)
        self.mail_status.setText(
            f"Editing {account.get('email_address', 'mail account')}."
        )

    def _clear_mail_account_form(
        self, checked: bool = False, *, update_picker: bool = True
    ) -> None:
        del checked
        if update_picker and hasattr(self, "mail_account_picker"):
            self.mail_account_picker.blockSignals(True)
            self.mail_account_picker.setCurrentIndex(0)
            self.mail_account_picker.blockSignals(False)
        for widget in (
            self.mail_label_input,
            self.mail_display_name_input,
            self.mail_email_input,
            self.mail_username_input,
            self.mail_password_input,
            self.mail_imap_host_input,
            self.mail_smtp_host_input,
            self.mail_signature_input,
            self.mail_avatar_path_input,
        ):
            widget.clear()
        self.mail_imap_port_input.setText("993")
        self.mail_smtp_port_input.setText("587")
        self.mail_poll_interval_input.setText("90")
        self.mail_imap_ssl_switch.setChecked(True)
        self.mail_imap_ssl_switch._apply_state()
        self.mail_smtp_starttls_switch.setChecked(True)
        self.mail_smtp_starttls_switch._apply_state()
        self.mail_smtp_ssl_switch.setChecked(False)
        self.mail_smtp_ssl_switch._apply_state()
        self.mail_notify_switch.setChecked(True)
        self.mail_notify_switch._apply_state()
        self.mail_delete_button.setEnabled(False)
        self.mail_status.setText("Create a new IMAP/SMTP account for Hanauta Mail.")

    def _save_mail_account_settings(self) -> None:
        current_index = (
            self.mail_account_picker.currentIndex()
            if hasattr(self, "mail_account_picker")
            else 0
        )
        account_id = (
            int(self.mail_account_picker.itemData(current_index) or 0)
            if hasattr(self, "mail_account_picker")
            else 0
        )
        required = {
            "email address": self.mail_email_input.text().strip(),
            "username": self.mail_username_input.text().strip(),
            "password": self.mail_password_input.text(),
            "IMAP host": self.mail_imap_host_input.text().strip(),
            "SMTP host": self.mail_smtp_host_input.text().strip(),
        }
        missing = [label for label, value in required.items() if not value]
        if missing:
            self.mail_status.setText(f"Missing mail fields: {', '.join(missing)}.")
            return
        try:
            imap_port = int(self.mail_imap_port_input.text().strip() or "993")
            smtp_port = int(self.mail_smtp_port_input.text().strip() or "587")
            poll_interval = int(self.mail_poll_interval_input.text().strip() or "90")
        except Exception:
            self.mail_status.setText(
                "Mail ports and sync interval must be valid numbers."
            )
            return
        payload = {
            "id": account_id,
            "label": self.mail_label_input.text().strip(),
            "display_name": self.mail_display_name_input.text().strip(),
            "email_address": self.mail_email_input.text().strip(),
            "username": self.mail_username_input.text().strip(),
            "password": self.mail_password_input.text(),
            "imap_host": self.mail_imap_host_input.text().strip(),
            "imap_port": imap_port,
            "imap_ssl": bool(self.mail_imap_ssl_switch.isChecked()),
            "smtp_host": self.mail_smtp_host_input.text().strip(),
            "smtp_port": smtp_port,
            "smtp_starttls": bool(self.mail_smtp_starttls_switch.isChecked()),
            "smtp_ssl": bool(self.mail_smtp_ssl_switch.isChecked()),
            "signature": self.mail_signature_input.text().strip(),
            "avatar_path": self.mail_avatar_path_input.text().strip(),
            "notify_enabled": bool(self.mail_notify_switch.isChecked()),
            "poll_interval_seconds": poll_interval,
            "folders_json": "[]",
            "folder_state_json": "{}",
        }
        desired_path = Path(
            self.mail_storage_path_input.text().strip() or str(MAIL_DB_PATH)
        ).expanduser()
        current_path = self.mail_account_store.path.expanduser()
        if desired_path != current_path:
            desired_path.parent.mkdir(parents=True, exist_ok=True)
            if current_path.exists() and not desired_path.exists():
                shutil.copy2(current_path, desired_path)
            self.mail_account_store = MailAccountStore(desired_path)
        save_mail_storage_config(
            {
                "db_path": str(desired_path),
                "attachments_dir": str(MAIL_STATE_DIR / "cache"),
            }
        )
        try:
            saved_account_id = self.mail_account_store.save_account(payload)
        except Exception as exc:
            self.mail_status.setText(f"Failed to save mail account: {exc}")
            return
        self._reload_mail_accounts(saved_account_id)
        self.mail_status.setText(f"Mail account saved for {payload['email_address']}.")

    def _delete_mail_account_settings(self) -> None:
        current_index = (
            self.mail_account_picker.currentIndex()
            if hasattr(self, "mail_account_picker")
            else 0
        )
        account_id = (
            int(self.mail_account_picker.itemData(current_index) or 0)
            if hasattr(self, "mail_account_picker")
            else 0
        )
        if account_id <= 0:
            self.mail_status.setText("Select a saved account before deleting it.")
            return
        try:
            self.mail_account_store.delete_account(account_id)
        except Exception as exc:
            self.mail_status.setText(f"Failed to delete mail account: {exc}")
            return
        self._reload_mail_accounts(0)
        self.mail_status.setText("Mail account deleted.")

    def _launch_mail_client(self) -> None:
        email_client_script = resolve_email_client_app()
        command = entry_command(email_client_script) if email_client_script else []
        if not command:
            self.mail_status.setText("Hanauta Mail launch script is unavailable.")
            return
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            self.mail_status.setText(f"Failed to open Hanauta Mail: {exc}")
            return
        self.mail_status.setText("Opened Hanauta Mail.")

    def _sync_mail_integration_buttons(self) -> None:
        favorite_enabled = current_favorite_mail_handler() == MAIL_DESKTOP_ID
        mailto_enabled = current_mailto_handler() == MAIL_DESKTOP_ID
        self.mail_favorite_button.setText(
            "Favorite Mail Client Enabled"
            if favorite_enabled
            else "Set Favorite Mail Client"
        )
        self.mail_mailto_button.setText(
            "mailto Links Enabled" if mailto_enabled else "Handle mailto Links"
        )

    def _queue_mail_integration_button_sync(self) -> None:
        worker = getattr(self, "_mail_integration_probe_worker", None)
        if isinstance(worker, MailIntegrationProbeWorker) and worker.isRunning():
            return
        self._mail_integration_probe_worker = MailIntegrationProbeWorker()
        self._mail_integration_probe_worker.finished_probe.connect(
            self._apply_mail_integration_probe_result
        )
        self._mail_integration_probe_worker.finished.connect(
            self._mail_integration_probe_worker.deleteLater
        )
        self._mail_integration_probe_worker.start()

    def _apply_mail_integration_probe_result(
        self, favorite_handler: str, mailto_handler: str
    ) -> None:
        favorite_enabled = str(favorite_handler).strip() == MAIL_DESKTOP_ID
        mailto_enabled = str(mailto_handler).strip() == MAIL_DESKTOP_ID
        if hasattr(self, "mail_favorite_button"):
            self.mail_favorite_button.setText(
                "Favorite Mail Client Enabled"
                if favorite_enabled
                else "Set Favorite Mail Client"
            )
        if hasattr(self, "mail_mailto_button"):
            self.mail_mailto_button.setText(
                "mailto Links Enabled" if mailto_enabled else "Handle mailto Links"
            )
        self._mail_integration_probe_worker = None

    def _ensure_hanauta_mail_desktop_entry(self) -> bool:
        if hanauta_mail_desktop_installed(MAIL_DESKTOP_LOCAL, MAIL_DESKTOP_SYSTEM):
            return True
        if not MAIL_DESKTOP_INSTALL_SCRIPT.exists():
            self.mail_status.setText(
                "The Hanauta Mail desktop install helper is missing."
            )
            return False
        result = subprocess.run(
            ["bash", str(MAIL_DESKTOP_INSTALL_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and hanauta_mail_desktop_installed(MAIL_DESKTOP_LOCAL, MAIL_DESKTOP_SYSTEM):
            return True
        if not MAIL_DESKTOP_SYSTEM_INSTALL_SCRIPT.exists():
            self.mail_status.setText(
                "Unable to register the Hanauta Mail desktop entry."
            )
            return False
        if shutil.which("pkexec") is None:
            self.mail_status.setText(
                "Unable to register Hanauta Mail system-wide because pkexec is unavailable."
            )
            return False
        self.mail_status.setText(
            "Installing the Hanauta Mail desktop entry system-wide. A polkit dialog may appear."
        )
        system_result = subprocess.run(
            ["pkexec", "bash", str(MAIL_DESKTOP_SYSTEM_INSTALL_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        if system_result.returncode == 0 and hanauta_mail_desktop_installed(MAIL_DESKTOP_LOCAL, MAIL_DESKTOP_SYSTEM):
            return True
        self.mail_status.setText("Unable to register the Hanauta Mail desktop entry.")
        return False

    def _set_hanauta_mail_favorite_client(self) -> None:
        if not self._ensure_hanauta_mail_desktop_entry():
            return
        if shutil.which("xdg-settings") is None:
            self.mail_status.setText(
                "xdg-settings is unavailable, so Hanauta Mail could not be set as the favorite mail client."
            )
            return
        result = subprocess.run(
            [
                "xdg-settings",
                "set",
                "default-url-scheme-handler",
                "mailto",
                MAIL_DESKTOP_ID,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.mail_status.setText(
                "Failed to set Hanauta Mail as the favorite mail client."
            )
            return
        self._sync_mail_integration_buttons()
        self.mail_status.setText(
            "Hanauta Mail is now the favorite mail client for mailto links."
        )

    def _set_hanauta_mailto_handler(self) -> None:
        if not self._ensure_hanauta_mail_desktop_entry():
            return
        if shutil.which("xdg-mime") is None:
            self.mail_status.setText(
                "xdg-mime is unavailable, so mailto handling could not be enabled."
            )
            return
        result = subprocess.run(
            ["xdg-mime", "default", MAIL_DESKTOP_ID, "x-scheme-handler/mailto"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.mail_status.setText(
                "Failed to enable mailto link handling for Hanauta Mail."
            )
            return
        self._sync_mail_integration_buttons()
        self.mail_status.setText("Hanauta Mail will now handle mailto links.")

    def _set_mail_notifications_enabled(self, enabled: bool) -> None:
        self.settings_state.setdefault("mail", {})["notify_new_messages"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)

    def _set_mail_notification_sound_enabled(self, enabled: bool) -> None:
        self.settings_state.setdefault("mail", {})["play_notification_sound"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)

    def _set_mail_hide_notification_content(self, enabled: bool) -> None:
        self.settings_state.setdefault("mail", {})["hide_notification_content"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)

    def _choose_mail_avatar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose mail avatar",
            str(Path.home() / "Pictures"),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if path:
            self.mail_avatar_path_input.setText(path)

    def _choose_mail_storage_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Hanauta Mail database",
            self.mail_storage_path_input.text().strip() or str(MAIL_DB_PATH),
            "SQLite database (*.sqlite3 *.db)",
        )
        if path:
            self.mail_storage_path_input.setText(path)

    def _build_home_assistant_section(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("contentCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(12, 12, 12, 12)
        hero_layout.setSpacing(10)
        hero_logo = QLabel()
        hero_logo.setFixedSize(28, 28)
        hero_logo.setScaledContents(True)
        hero_logo.setPixmap(
            QPixmap(str(HOME_ASSISTANT_LOGO)).scaled(
                28,
                28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        hero_text_wrap = QVBoxLayout()
        hero_text_wrap.setContentsMargins(0, 0, 0, 0)
        hero_text_wrap.setSpacing(2)
        hero_title = QLabel("Home Assistant")
        hero_title.setFont(QFont(self.display_font, 12))
        hero_hint = QLabel(
            "Connect your server, pin entities, and optionally expose the popup on the bar."
        )
        hero_hint.setWordWrap(True)
        hero_hint.setStyleSheet("color: rgba(246,235,247,0.72);")
        hero_text_wrap.addWidget(hero_title)
        hero_text_wrap.addWidget(hero_hint)
        hero_layout.addWidget(hero_logo, 0, Qt.AlignmentFlag.AlignTop)
        hero_layout.addLayout(hero_text_wrap, 1)
        content_layout.addWidget(hero)

        self.ha_url_input = QLineEdit(
            self.settings_state["home_assistant"].get("url", "")
        )
        self.ha_url_input.setPlaceholderText("https://homeassistant.local:8123")
        self.ha_token_input = QLineEdit(
            self.settings_state["home_assistant"].get("token", "")
        )
        self.ha_token_input.setPlaceholderText("Long-lived access token")
        self.ha_token_input.setEchoMode(QLineEdit.EchoMode.Password)

        url_row = SettingsRow(
            material_icon("web_asset"),
            "Server URL",
            "Home Assistant base URL.",
            self.icon_font,
            self.ui_font,
            self.ha_url_input,
        )
        token_row = SettingsRow(
            material_icon("bolt"),
            "Access token",
            "Used to fetch and pin entities.",
            self.icon_font,
            self.ui_font,
            self.ha_token_input,
        )
        content_layout.addWidget(url_row)
        content_layout.addWidget(token_row)

        self.ha_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["home_assistant"].get(
                    "show_in_notification_center",
                    True,
                )
            )
        )
        self.ha_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "home_assistant", enabled
            )
        )
        self.service_display_switches["home_assistant"] = self.ha_display_switch
        content_layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Display the Home Assistant widget in the notification center overview.",
                self.icon_font,
                self.ui_font,
                self.ha_display_switch,
            )
        )

        self.ha_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["home_assistant"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        self.ha_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("home_assistant", enabled)
        )
        content_layout.addWidget(
            SettingsRow(
                material_icon("home"),
                "Show on bar",
                "Adds a Home Assistant icon to the bar so the popup can be opened directly.",
                self.icon_font,
                self.ui_font,
                self.ha_bar_switch,
            )
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.ha_save_button = QPushButton("Save")
        self.ha_save_button.setObjectName("primaryButton")
        self.ha_refresh_button = QPushButton("Fetch Entities")
        self.ha_refresh_button.setObjectName("secondaryButton")
        self.ha_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ha_refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ha_save_button.setMinimumHeight(42)
        self.ha_refresh_button.setMinimumHeight(42)
        self.ha_save_button.setMinimumWidth(144)
        self.ha_refresh_button.setMinimumWidth(160)
        self.ha_save_button.clicked.connect(self._save_home_assistant_settings)
        self.ha_refresh_button.clicked.connect(self._refresh_home_assistant_entities)
        buttons.addWidget(self.ha_save_button)
        buttons.addWidget(self.ha_refresh_button)
        content_layout.addLayout(buttons)

        ha_cache = load_service_cache_json("home_assistant.json")
        cached_entities = (
            ha_cache.get("entities", []) if isinstance(ha_cache, dict) else []
        )
        if isinstance(cached_entities, list) and cached_entities:
            status_text = f"Using hanauta-service cache: {len(cached_entities)} entity snapshot(s) available."
        else:
            status_text = "Home Assistant is idle."
        self.ha_status = QLabel(status_text)
        self.ha_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        content_layout.addWidget(self.ha_status)

        self.ha_entity_scroll = QScrollArea()
        self.ha_entity_scroll.setWidgetResizable(True)
        self.ha_entity_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.ha_entity_scroll.setObjectName("bodyScroll")
        self.ha_entity_container = QWidget()
        self.ha_entity_layout = QVBoxLayout(self.ha_entity_container)
        self.ha_entity_layout.setContentsMargins(0, 0, 0, 0)
        self.ha_entity_layout.setSpacing(8)
        self.ha_entity_scroll.setWidget(self.ha_entity_container)
        content_layout.addWidget(self.ha_entity_scroll, 1)

        self._rebuild_ha_entity_list()
        section = ExpandableServiceSection(
            "home_assistant",
            "Home Assistant",
            "Credentials, pinned entities, and notification center visibility.",
            material_icon("home"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("home_assistant"),
            lambda enabled: self._set_service_enabled("home_assistant", enabled),
        )
        self.service_sections["home_assistant"] = section
        return section

    def _build_kdeconnect_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        rule_id = "kdeconnect_ignore_whatsapp_when_desktop_client_active"
        rule = self.notification_rules_state["rules"].get(
            rule_id,
            DEFAULT_NOTIFICATION_RULES["rules"][rule_id],
        )

        self.kdeconnect_whatsapp_ignore_switch = SwitchButton(
            bool(rule.get("enabled", False))
        )
        self.kdeconnect_whatsapp_ignore_switch.toggledValue.connect(
            lambda enabled: self._set_notification_rule_enabled(rule_id, enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_off"),
                "Ignore WhatsApp while desktop client is active",
                "If Ferdium or WhatsApp Desktop is running, Hanauta will ignore matching KDE Connect WhatsApp notifications.",
                self.icon_font,
                self.ui_font,
                self.kdeconnect_whatsapp_ignore_switch,
            )
        )

        service = self.settings_state["services"].setdefault("kdeconnect", {})

        self.kdeconnect_low_battery_switch = SwitchButton(
            bool(service.get("low_battery_fullscreen_notification", False))
        )
        self.kdeconnect_low_battery_switch.toggledValue.connect(
            self._set_kdeconnect_low_battery_fullscreen_notification
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_active"),
                "Fullscreen low-battery alert",
                "Show a fullscreen Hanauta reminder-style alert when your paired phone battery drops below the threshold.",
                self.icon_font,
                self.ui_font,
                self.kdeconnect_low_battery_switch,
            )
        )

        self.kdeconnect_battery_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.kdeconnect_battery_threshold_slider.setRange(1, 100)
        self.kdeconnect_battery_threshold_slider.setValue(
            int(service.get("low_battery_threshold", 20))
        )
        self.kdeconnect_battery_threshold_slider.valueChanged.connect(
            self._set_kdeconnect_low_battery_threshold
        )
        self.kdeconnect_battery_threshold_label = QLabel(
            f"{int(service.get('low_battery_threshold', 20))}%"
        )
        self.kdeconnect_battery_threshold_label.setFixedWidth(48)
        self.kdeconnect_battery_threshold_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.kdeconnect_battery_threshold_label.setStyleSheet(
            "color: rgba(246,235,247,0.78);"
        )
        threshold_wrap = QWidget()
        threshold_layout = QHBoxLayout(threshold_wrap)
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        threshold_layout.setSpacing(10)
        threshold_layout.addWidget(self.kdeconnect_battery_threshold_slider)
        threshold_layout.addWidget(self.kdeconnect_battery_threshold_label)
        layout.addWidget(
            SettingsRow(
                material_icon("phone_android"),
                "Battery threshold",
                "Trigger the fullscreen KDE Connect alert when the current phone battery percentage is at or below this value.",
                self.icon_font,
                self.ui_font,
                threshold_wrap,
            )
        )

        rules_path_label = QLabel(str(NOTIFICATION_RULES_FILE))
        rules_path_label.setWordWrap(True)
        rules_path_label.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(
            SettingsRow(
                material_icon("description"),
                "Rules file",
                "Rules live in a shared INI file with [rule.<id>] sections and keys like enabled, source_app, summary_contains, body_contains, processes, and action.",
                self.icon_font,
                self.ui_font,
                rules_path_label,
            )
        )

        self.kdeconnect_rules_status = QLabel(
            "KDE Connect notification rules are idle."
        )
        self.kdeconnect_rules_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.kdeconnect_rules_status.setWordWrap(True)
        layout.addWidget(self.kdeconnect_rules_status)

        section = ExpandableServiceSection(
            "kdeconnect",
            "KDE Connect",
            "Notification-routing rules for mirrored phone notifications.",
            material_icon("phone_android"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("kdeconnect"),
            lambda enabled: self._set_service_enabled("kdeconnect", enabled),
        )
        self.service_sections["kdeconnect"] = section
        return section

    def _build_vpn_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["vpn_control"].get(
                    "show_in_notification_center",
                    False,
                )
            )
        )
        display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "vpn_control", enabled
            )
        )
        self.service_display_switches["vpn_control"] = display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a compact launcher card for the VPN control popup.",
                self.icon_font,
                self.ui_font,
                display_switch,
            )
        )
        reconnect_switch = SwitchButton(
            bool(
                self.settings_state["services"]["vpn_control"].get(
                    "reconnect_on_login",
                    False,
                )
            )
        )
        reconnect_switch.toggledValue.connect(
            lambda enabled: self._set_vpn_service_flag("reconnect_on_login", enabled)
        )
        self.vpn_reconnect_switch = reconnect_switch
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Reconnect on session start",
                "Bring the selected WireGuard tunnel back when this desktop session starts.",
                self.icon_font,
                self.ui_font,
                reconnect_switch,
            )
        )
        section = ExpandableServiceSection(
            "vpn_control",
            "VPN Control",
            "Enable the WireGuard popup, keep a preferred tunnel remembered, and optionally reopen it on session start.",
            material_icon("lock"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("vpn_control"),
            lambda enabled: self._set_service_enabled("vpn_control", enabled),
        )
        self.service_sections["vpn_control"] = section
        return section

    def _build_christian_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["christian_widget"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        display_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility(
                "christian_widget", enabled
            )
        )
        self.service_display_switches["christian_widget"] = display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show on bar",
                "Display a tinted Christian devotion launcher icon on the bar.",
                self.icon_font,
                self.ui_font,
                display_switch,
            )
        )
        next_devotion_switch = SwitchButton(
            bool(
                self.settings_state["services"]["christian_widget"].get(
                    "next_devotion_notifications",
                    False,
                )
            )
        )
        next_devotion_switch.toggledValue.connect(
            lambda enabled: self._set_christian_service_flag(
                "next_devotion_notifications", enabled
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Next devotion notifications",
                "Send a desktop notification when the next devotion time begins.",
                self.icon_font,
                self.ui_font,
                next_devotion_switch,
            )
        )
        hourly_verse_switch = SwitchButton(
            bool(
                self.settings_state["services"]["christian_widget"].get(
                    "hourly_verse_notifications",
                    False,
                )
            )
        )
        hourly_verse_switch.toggledValue.connect(
            lambda enabled: self._set_christian_service_flag(
                "hourly_verse_notifications", enabled
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("auto_awesome"),
                "Hourly random verse",
                "Show a random Bible verse notification once every hour.",
                self.icon_font,
                self.ui_font,
                hourly_verse_switch,
            )
        )
        self.christian_next_devotion_switch = next_devotion_switch
        self.christian_hourly_verse_switch = hourly_verse_switch
        section = ExpandableServiceSection(
            "christian_widget",
            "Christian Widget",
            "Enable the devotion widget, surface it on the bar, and control its desktop notifications.",
            material_icon("auto_awesome"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("christian_widget"),
            lambda enabled: self._set_service_enabled("christian_widget", enabled),
        )
        self.service_sections["christian_widget"] = section
        return section

    def _build_health_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["health_widget"].get(
                    "show_in_bar",
                    True,
                )
            )
        )
        bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("health_widget", enabled)
        )
        self.service_display_switches["health_widget"] = bar_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show on bar",
                "Displays a compact health launcher next to the updates indicator.",
                self.icon_font,
                self.ui_font,
                bar_switch,
            )
        )

        self.health_provider_combo = QComboBox()
        self.health_provider_combo.addItems(["Manual", "Fitbit"])
        provider_index = (
            1
            if self.settings_state["health"].get("provider", "manual") == "fitbit"
            else 0
        )
        self.health_provider_combo.setCurrentIndex(provider_index)
        self.health_provider_combo.currentIndexChanged.connect(
            self._set_health_provider
        )
        layout.addWidget(
            SettingsRow(
                material_icon("favorite"),
                "Provider",
                "Manual mode works immediately. Fitbit is the easiest sync path for a desktop widget right now.",
                self.icon_font,
                self.ui_font,
                self.health_provider_combo,
            )
        )

        self.health_step_goal_input = QLineEdit(
            str(self.settings_state["health"].get("step_goal", 10000))
        )
        self.health_step_goal_input.setPlaceholderText("10000")
        layout.addWidget(
            SettingsRow(
                material_icon("favorite"),
                "Daily step goal",
                "Used by the widget progress ring and bar tooltip.",
                self.icon_font,
                self.ui_font,
                self.health_step_goal_input,
            )
        )

        self.health_water_goal_input = QLineEdit(
            str(self.settings_state["health"].get("water_goal_ml", 2000))
        )
        self.health_water_goal_input.setPlaceholderText("2000")
        layout.addWidget(
            SettingsRow(
                material_icon("water_drop"),
                "Hydration goal (ml)",
                "Manual mode tracks this in the widget.",
                self.icon_font,
                self.ui_font,
                self.health_water_goal_input,
            )
        )

        self.health_sync_interval_input = QLineEdit(
            str(self.settings_state["health"].get("sync_interval_minutes", 30))
        )
        self.health_sync_interval_input.setPlaceholderText("30")
        layout.addWidget(
            SettingsRow(
                material_icon("sync"),
                "Sync interval (minutes)",
                "Used by the bar and widget when Fitbit sync is enabled.",
                self.icon_font,
                self.ui_font,
                self.health_sync_interval_input,
            )
        )

        water_reminder_switch = SwitchButton(
            bool(
                self.settings_state["services"]["health_widget"].get(
                    "water_reminder_notifications",
                    False,
                )
            )
        )
        water_reminder_switch.toggledValue.connect(
            lambda enabled: self._set_health_service_flag(
                "water_reminder_notifications", enabled
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("water_drop"),
                "Remember to take water",
                "Disabled by default. Sends realistic hydration nudges during the day.",
                self.icon_font,
                self.ui_font,
                water_reminder_switch,
            )
        )

        stand_reminder_switch = SwitchButton(
            bool(
                self.settings_state["services"]["health_widget"].get(
                    "stand_up_reminder_notifications",
                    False,
                )
            )
        )
        stand_reminder_switch.toggledValue.connect(
            lambda enabled: self._set_health_service_flag(
                "stand_up_reminder_notifications", enabled
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Remember to stand up",
                "Disabled by default. Sends posture and stretch reminders while you are working.",
                self.icon_font,
                self.ui_font,
                stand_reminder_switch,
            )
        )

        movement_reminder_switch = SwitchButton(
            bool(
                self.settings_state["services"]["health_widget"].get(
                    "movement_reminder_notifications",
                    False,
                )
            )
        )
        movement_reminder_switch.toggledValue.connect(
            lambda enabled: self._set_health_service_flag(
                "movement_reminder_notifications", enabled
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("favorite"),
                "Remember to move",
                "Disabled by default. Sends an empowering reminder to walk, work out, or do something active.",
                self.icon_font,
                self.ui_font,
                movement_reminder_switch,
            )
        )
        self.health_water_reminder_switch = water_reminder_switch
        self.health_stand_reminder_switch = stand_reminder_switch
        self.health_movement_reminder_switch = movement_reminder_switch

        self.health_fitbit_client_id_input = QLineEdit(
            self.settings_state["health"].get("fitbit_client_id", "")
        )
        self.health_fitbit_client_id_input.setPlaceholderText("Fitbit client id")
        self.health_fitbit_client_secret_input = QLineEdit(
            self.settings_state["health"].get("fitbit_client_secret", "")
        )
        self.health_fitbit_client_secret_input.setPlaceholderText(
            "Fitbit client secret"
        )
        self.health_fitbit_client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.health_fitbit_access_token_input = QLineEdit(
            self.settings_state["health"].get("fitbit_access_token", "")
        )
        self.health_fitbit_access_token_input.setPlaceholderText("Fitbit access token")
        self.health_fitbit_access_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.health_fitbit_refresh_token_input = QLineEdit(
            self.settings_state["health"].get("fitbit_refresh_token", "")
        )
        self.health_fitbit_refresh_token_input.setPlaceholderText(
            "Fitbit refresh token"
        )
        self.health_fitbit_refresh_token_input.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "Fitbit client id",
                "Needed only if you want Hanauta to refresh Fitbit tokens automatically.",
                self.icon_font,
                self.ui_font,
                self.health_fitbit_client_id_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Fitbit client secret",
                "Stored locally and used only for Fitbit token refresh.",
                self.icon_font,
                self.ui_font,
                self.health_fitbit_client_secret_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("bolt"),
                "Fitbit access token",
                "Paste a current read token if you want a simple manual setup.",
                self.icon_font,
                self.ui_font,
                self.health_fitbit_access_token_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Fitbit refresh token",
                "Optional, but recommended if you want Hanauta to keep syncing after the access token expires.",
                self.icon_font,
                self.ui_font,
                self.health_fitbit_refresh_token_input,
            )
        )

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.health_save_button = QPushButton("Save Health Settings")
        self.health_save_button.setObjectName("primaryButton")
        self.health_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.health_save_button.setMinimumHeight(42)
        self.health_save_button.clicked.connect(self._save_health_settings)
        button_row.addWidget(self.health_save_button)
        layout.addLayout(button_row)

        self.health_status_label = QLabel(
            "Manual mode works immediately. Switch to Fitbit when you have tokens ready."
        )
        self.health_status_label.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.health_status_label.setWordWrap(True)
        layout.addWidget(self.health_status_label)

        self._sync_health_inputs()
        section = ExpandableServiceSection(
            "health_widget",
            "Health Widget",
            "A compact health dashboard with manual tracking today and Fitbit sync when configured.",
            material_icon("favorite"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("health_widget"),
            lambda enabled: self._set_service_enabled("health_widget", enabled),
        )
        self.service_sections["health_widget"] = section
        return section

    def _build_weather_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.weather_city_input = QLineEdit(
            self.settings_state["weather"].get("name", "")
        )
        if self._selected_weather_city is not None:
            self.weather_city_input.setText(self._selected_weather_city.label)
        self.weather_city_input.setPlaceholderText("Type a city, region, or country")
        self.weather_city_input.textEdited.connect(self._queue_weather_city_search)

        self.weather_city_model = QStringListModel(self)
        self.weather_city_completer = QCompleter(self.weather_city_model, self)
        self.weather_city_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.weather_city_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.weather_city_completer.activated[str].connect(self._select_weather_city)
        self.weather_city_input.setCompleter(self.weather_city_completer)

        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "Shared location",
                "Autocomplete search powered by Open-Meteo geocoding. This location is reused by Weather and CAP alerts.",
                self.icon_font,
                self.ui_font,
                self.weather_city_input,
            )
        )

        weather_settings = self.settings_state.setdefault("weather", {})
        if not isinstance(weather_settings, dict):
            weather_settings = {}
            self.settings_state["weather"] = weather_settings

        notifications_title = QLabel("Notifications")
        notifications_title.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        notifications_title.setStyleSheet("color: rgba(246,235,247,0.86);")
        layout.addWidget(notifications_title)

        self.weather_notify_changes_switch = SwitchButton(
            bool(weather_settings.get("notify_climate_changes", True))
        )
        self.weather_notify_changes_switch.toggledValue.connect(
            self._set_weather_notify_climate_changes
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_active"),
                "Climate change alerts",
                "Enable proactive weather alerts like rain soon and sunset reminders.",
                self.icon_font,
                self.ui_font,
                self.weather_notify_changes_switch,
            )
        )

        self.weather_notify_rain_switch = SwitchButton(
            bool(weather_settings.get("notify_rain_soon", True))
        )
        self.weather_notify_rain_switch.toggledValue.connect(
            self._set_weather_notify_rain_soon
        )
        layout.addWidget(
            SettingsRow(
                material_icon("rainy"),
                "Rain soon",
                "Notify when rain is forecast within the next configured lead time.",
                self.icon_font,
                self.ui_font,
                self.weather_notify_rain_switch,
            )
        )

        self.weather_notify_sunset_switch = SwitchButton(
            bool(weather_settings.get("notify_sunset_soon", True))
        )
        self.weather_notify_sunset_switch.toggledValue.connect(
            self._set_weather_notify_sunset_soon
        )
        layout.addWidget(
            SettingsRow(
                material_icon("wb_twilight"),
                "Sunset soon",
                "Notify before sunset for your selected weather location.",
                self.icon_font,
                self.ui_font,
                self.weather_notify_sunset_switch,
            )
        )
        weather_notification_rows = [
            (
                "thermometer",
                "Temperature drop soon",
                "Alert when temperature is forecast to drop quickly in the next hours.",
                "notify_temperature_drop_soon",
            ),
            (
                "wb_sunny",
                "Rapid heat rise",
                "Alert when temperature rises quickly in the next hours.",
                "notify_temperature_rise_soon",
            ),
            (
                "ac_unit",
                "Freezing risk tonight",
                "Alert when temperatures are forecast near or below freezing overnight.",
                "notify_freezing_risk_tonight",
            ),
            (
                "sunny",
                "High UV window",
                "Alert when UV index enters a high-risk period.",
                "notify_high_uv_window",
            ),
            (
                "air",
                "Strong wind incoming",
                "Alert when strong gusts are expected soon.",
                "notify_strong_wind_incoming",
            ),
            (
                "thunderstorm",
                "Thunderstorm likelihood",
                "Alert when storm conditions are likely soon.",
                "notify_thunderstorm_likelihood",
            ),
            (
                "weather_snowy",
                "Snow or ice start soon",
                "Alert before snow, sleet, or freezing rain begins.",
                "notify_snow_ice_start",
            ),
            (
                "foggy",
                "Fog / low visibility",
                "Alert when visibility is forecast to drop significantly.",
                "notify_fog_low_visibility",
            ),
            (
                "airwave",
                "Air quality worsening",
                "Alert when AQI shifts into a worse category.",
                "notify_air_quality_worsening",
            ),
            (
                "grass",
                "Pollen high alert",
                "Alert when pollen levels are high for your area.",
                "notify_pollen_high",
            ),
            (
                "commute",
                "Morning commute rain",
                "Alert for rain risk during your configured morning commute window.",
                "notify_morning_commute_rain",
            ),
            (
                "commute",
                "Evening commute weather risk",
                "Alert for rain, snow, or strong wind during evening commute.",
                "notify_evening_commute_risk",
            ),
            (
                "emergency_heat",
                "Feels-like extreme",
                "Alert when apparent temperature reaches dangerous levels.",
                "notify_feels_like_extreme",
            ),
            (
                "wb_twilight",
                "Sunrise soon",
                "Alert shortly before sunrise.",
                "notify_sunrise_soon",
            ),
            (
                "water_drop",
                "Dry window ending",
                "Alert when a dry stretch is about to end with precipitation.",
                "notify_dry_window_ending",
            ),
        ]
        self.weather_notification_switches = {}
        for icon_name, label, description, key_name in weather_notification_rows:
            toggle = SwitchButton(bool(weather_settings.get(key_name, True)))
            toggle.toggledValue.connect(
                lambda enabled, key=key_name, title=label: self._set_weather_notification_flag(
                    key, enabled, title
                )
            )
            self.weather_notification_switches[key_name] = toggle
            layout.addWidget(
                SettingsRow(
                    material_icon(icon_name),
                    label,
                    description,
                    self.icon_font,
                    self.ui_font,
                    toggle,
                )
            )

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.weather_apply_button = QPushButton("Apply city")
        self.weather_apply_button.setObjectName("primaryButton")
        self.weather_apply_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.weather_apply_button.clicked.connect(self._save_weather_settings)
        buttons.addWidget(self.weather_apply_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.weather_status = QLabel("Weather popup is idle.")
        self.weather_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.weather_status.setWordWrap(True)
        layout.addWidget(self.weather_status)

        section = ExpandableServiceSection(
            "weather",
            "Weather",
            "Use one saved location for the weather popup, bar weather icon, and official CAP alerts.",
            material_icon("partly_cloudy_day"),
            self.icon_font,
            self.ui_font,
            content,
            bool(self.settings_state["weather"].get("enabled", False)),
            self._set_weather_enabled,
        )
        self.weather_section = section
        return section

    def _build_cap_alerts_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.cap_alerts_bar_switch = SwitchButton(
            bool(self.settings_state["services"]["cap_alerts"].get("show_in_bar", True))
        )
        self.cap_alerts_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("cap_alerts", enabled)
        )
        self.service_display_switches["cap_alerts"] = self.cap_alerts_bar_switch
        layout.addWidget(
            SettingsRow(
                material_icon("warning"),
                "Show alert chip on bar",
                "Displays a yellow warning chip between media and status icons when active official alerts affect your saved location.",
                self.icon_font,
                self.ui_font,
                self.cap_alerts_bar_switch,
            )
        )

        self.cap_alerts_test_mode_switch = SwitchButton(
            bool(self.settings_state["services"]["cap_alerts"].get("test_mode", False))
        )
        self.cap_alerts_test_mode_switch.toggledValue.connect(
            self._set_cap_alerts_test_mode
        )
        layout.addWidget(
            SettingsRow(
                material_icon("science"),
                "Demo alert chip",
                "Forces sample alert data from random countries so you can test the yellow bar chip and popup without waiting for a real alert.",
                self.icon_font,
                self.ui_font,
                self.cap_alerts_test_mode_switch,
            )
        )

        self.cap_alerts_status = QLabel(
            "Uses your saved shared location for live alerts. If you use a VPN, save your real region here so weather and alerts stay accurate. Hanauta does not send telemetry or your location anywhere."
        )
        self.cap_alerts_status.setWordWrap(True)
        self.cap_alerts_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.cap_alerts_status)

        section = ExpandableServiceSection(
            "cap_alerts",
            "CAP Alerts",
            "Official active local alerts surfaced as a warning chip on the bar, with a detailed help popup on click.",
            material_icon("warning"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("cap_alerts"),
            lambda enabled: self._set_service_enabled("cap_alerts", enabled),
        )
        self.service_sections["cap_alerts"] = section
        return section

    def _build_calendar_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        calendar_state = self.settings_state.setdefault("calendar", {})
        calendars = calendar_state.get("calendars", [])
        if not isinstance(calendars, list):
            calendars = []
            calendar_state["calendars"] = calendars
        contacts = calendar_state.get("contacts", [])
        if not isinstance(contacts, list):
            contacts = []
            calendar_state["contacts"] = contacts

        self.calendar_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["calendar_widget"].get(
                    "show_in_notification_center",
                    False,
                )
            )
        )
        self.calendar_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "calendar_widget", enabled
            )
        )
        self.service_display_switches["calendar_widget"] = self.calendar_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a calendar launcher card in the notification center overview.",
                self.icon_font,
                self.ui_font,
                self.calendar_display_switch,
            )
        )

        self.calendar_week_numbers_switch = SwitchButton(
            bool(self.settings_state["calendar"].get("show_week_numbers", False))
        )
        self.calendar_week_numbers_switch.toggledValue.connect(
            self._set_calendar_show_week_numbers
        )
        layout.addWidget(
            SettingsRow(
                material_icon("calendar_month"),
                "Show week numbers",
                "Adds ISO week numbers to the stylized calendar grid.",
                self.icon_font,
                self.ui_font,
                self.calendar_week_numbers_switch,
            )
        )

        self.calendar_other_month_switch = SwitchButton(
            bool(self.settings_state["calendar"].get("show_other_month_days", True))
        )
        self.calendar_other_month_switch.toggledValue.connect(
            self._set_calendar_show_other_month_days
        )
        layout.addWidget(
            SettingsRow(
                material_icon("event_upcoming"),
                "Show adjacent month days",
                "Keep leading and trailing days visible for a fuller month view.",
                self.icon_font,
                self.ui_font,
                self.calendar_other_month_switch,
            )
        )

        self.calendar_first_day_combo = QComboBox()
        self.calendar_first_day_combo.setObjectName("settingsCombo")
        self.calendar_first_day_combo.addItem("Monday", "monday")
        self.calendar_first_day_combo.addItem("Sunday", "sunday")
        current_first_day = str(
            self.settings_state["calendar"].get("first_day_of_week", "monday")
        )
        index = self.calendar_first_day_combo.findData(current_first_day)
        self.calendar_first_day_combo.setCurrentIndex(max(0, index))
        self.calendar_first_day_combo.currentIndexChanged.connect(
            self._set_calendar_first_day
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "First day of week",
                "Choose how the popup month grid should begin.",
                self.icon_font,
                self.ui_font,
                self.calendar_first_day_combo,
            )
        )

        calendars_heading = QLabel("Calendars")
        calendars_heading.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        calendars_heading.setStyleSheet("color: rgba(246,235,247,0.86);")
        layout.addWidget(calendars_heading)

        self.calendar_account_combo = QComboBox()
        self.calendar_account_combo.setObjectName("settingsCombo")
        self.calendar_account_combo.currentIndexChanged.connect(
            self._load_selected_calendar_account
        )
        layout.addWidget(
            SettingsRow(
                material_icon("calendar_month"),
                "Saved calendar",
                "Pick a CalDAV calendar connection or create a new one.",
                self.icon_font,
                self.ui_font,
                self.calendar_account_combo,
            )
        )

        calendar_actions = QWidget()
        calendar_actions_layout = QHBoxLayout(calendar_actions)
        calendar_actions_layout.setContentsMargins(0, 0, 0, 0)
        calendar_actions_layout.setSpacing(8)
        self.calendar_add_account_button = QPushButton("Add calendar")
        self.calendar_add_account_button.setObjectName("secondaryButton")
        self.calendar_add_account_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.calendar_add_account_button.clicked.connect(self._add_calendar_account)
        self.calendar_remove_account_button = QPushButton("Remove")
        self.calendar_remove_account_button.setObjectName("dangerButton")
        self.calendar_remove_account_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.calendar_remove_account_button.clicked.connect(
            self._remove_selected_calendar_account
        )
        calendar_actions_layout.addWidget(self.calendar_add_account_button)
        calendar_actions_layout.addWidget(self.calendar_remove_account_button)
        calendar_actions_layout.addStretch(1)
        layout.addWidget(
            SettingsRow(
                material_icon("apps"),
                "Manage calendars",
                "Add multiple CalDAV providers (work, personal, shared).",
                self.icon_font,
                self.ui_font,
                calendar_actions,
            )
        )

        selected_calendar = self._selected_calendar_account()
        self.calendar_account_enabled_switch = SwitchButton(
            bool(selected_calendar.get("enabled", True)) if selected_calendar else True
        )
        self.calendar_account_enabled_switch.toggledValue.connect(
            self._set_selected_calendar_account_enabled
        )
        layout.addWidget(
            SettingsRow(
                material_icon("toggle_on"),
                "Enable this calendar",
                "Disabled calendars stay saved but are ignored during sync.",
                self.icon_font,
                self.ui_font,
                self.calendar_account_enabled_switch,
            )
        )

        self.calendar_url_input = QLineEdit(
            str(selected_calendar.get("caldav_url", "")).strip()
            if selected_calendar
            else self.settings_state["calendar"].get("caldav_url", "")
        )
        self.calendar_url_input.setPlaceholderText("https://dav.example.com/caldav/")
        self.calendar_user_input = QLineEdit(
            str(selected_calendar.get("caldav_username", "")).strip()
            if selected_calendar
            else self.settings_state["calendar"].get("caldav_username", "")
        )
        self.calendar_user_input.setPlaceholderText("username")
        self.calendar_password_input = QLineEdit(
            str(selected_calendar.get("caldav_password", ""))
            if selected_calendar
            else self.settings_state["calendar"].get("caldav_password", "")
        )
        self.calendar_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.calendar_password_input.setPlaceholderText("Password or app password")
        layout.addWidget(
            SettingsRow(
                material_icon("web_asset"),
                "CalDAV URL",
                "Used to discover and sync remote calendars into qcal.",
                self.icon_font,
                self.ui_font,
                self.calendar_url_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "CalDAV username",
                "Account used for CalDAV discovery.",
                self.icon_font,
                self.ui_font,
                self.calendar_user_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "CalDAV password",
                "Stored so qcal can keep your event list wired up.",
                self.icon_font,
                self.ui_font,
                self.calendar_password_input,
            )
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.calendar_save_button = QPushButton("Save credentials")
        self.calendar_save_button.setObjectName("secondaryButton")
        self.calendar_discover_button = QPushButton("Discover calendars")
        self.calendar_discover_button.setObjectName("primaryButton")
        self.calendar_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.calendar_discover_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.calendar_save_button.clicked.connect(self._save_calendar_settings)
        self.calendar_discover_button.clicked.connect(self._discover_calendar_calendars)
        buttons.addWidget(self.calendar_save_button)
        buttons.addWidget(self.calendar_discover_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.calendar_status = QLabel(
            str(
                (selected_calendar or {}).get("last_sync_status", "")
                or self.settings_state["calendar"].get("last_sync_status", "")
            ).strip()
            or "Calendar integration is idle."
        )
        self.calendar_status.setWordWrap(True)
        self.calendar_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.calendar_status)

        contacts_heading = QLabel("Contacts")
        contacts_heading.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        contacts_heading.setStyleSheet("color: rgba(246,235,247,0.86);")
        layout.addWidget(contacts_heading)

        self.contacts_account_combo = QComboBox()
        self.contacts_account_combo.setObjectName("settingsCombo")
        self.contacts_account_combo.currentIndexChanged.connect(
            self._load_selected_contact_account
        )
        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "Saved contacts",
                "Add CardDAV accounts so Hanauta can reuse contacts later (callers, mail, quick share).",
                self.icon_font,
                self.ui_font,
                self.contacts_account_combo,
            )
        )

        contacts_actions = QWidget()
        contacts_actions_layout = QHBoxLayout(contacts_actions)
        contacts_actions_layout.setContentsMargins(0, 0, 0, 0)
        contacts_actions_layout.setSpacing(8)
        self.contacts_add_account_button = QPushButton("Add CardDAV")
        self.contacts_add_account_button.setObjectName("secondaryButton")
        self.contacts_add_account_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.contacts_add_account_button.clicked.connect(self._add_contact_account)
        self.contacts_remove_account_button = QPushButton("Remove")
        self.contacts_remove_account_button.setObjectName("dangerButton")
        self.contacts_remove_account_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.contacts_remove_account_button.clicked.connect(
            self._remove_selected_contact_account
        )
        contacts_actions_layout.addWidget(self.contacts_add_account_button)
        contacts_actions_layout.addWidget(self.contacts_remove_account_button)
        contacts_actions_layout.addStretch(1)
        layout.addWidget(
            SettingsRow(
                material_icon("apps"),
                "Manage contacts",
                "CardDAV support is stored here so other widgets can consume it.",
                self.icon_font,
                self.ui_font,
                contacts_actions,
            )
        )

        selected_contact = self._selected_contact_account()
        self.contacts_account_enabled_switch = SwitchButton(
            bool(selected_contact.get("enabled", True)) if selected_contact else True
        )
        self.contacts_account_enabled_switch.toggledValue.connect(
            self._set_selected_contact_account_enabled
        )
        layout.addWidget(
            SettingsRow(
                material_icon("toggle_on"),
                "Enable this contact source",
                "Disabled CardDAV accounts stay saved but are ignored.",
                self.icon_font,
                self.ui_font,
                self.contacts_account_enabled_switch,
            )
        )

        self.contacts_url_input = QLineEdit(
            str(selected_contact.get("carddav_url", "")).strip()
            if selected_contact
            else ""
        )
        self.contacts_url_input.setPlaceholderText("https://dav.example.com/carddav/")
        self.contacts_user_input = QLineEdit(
            str(selected_contact.get("carddav_username", "")).strip()
            if selected_contact
            else ""
        )
        self.contacts_user_input.setPlaceholderText("username")
        self.contacts_password_input = QLineEdit(
            str(selected_contact.get("carddav_password", "")) if selected_contact else ""
        )
        self.contacts_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.contacts_password_input.setPlaceholderText("Password or app password")
        layout.addWidget(
            SettingsRow(
                material_icon("web_asset"),
                "CardDAV URL",
                "Credentials are saved so future Hanauta widgets can reuse contacts.",
                self.icon_font,
                self.ui_font,
                self.contacts_url_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "CardDAV username",
                "Account used for CardDAV discovery.",
                self.icon_font,
                self.ui_font,
                self.contacts_user_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "CardDAV password",
                "Stored locally so contact sync can be enabled later.",
                self.icon_font,
                self.ui_font,
                self.contacts_password_input,
            )
        )

        self.contacts_save_button = QPushButton("Save contacts credentials")
        self.contacts_save_button.setObjectName("primaryButton")
        self.contacts_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.contacts_save_button.clicked.connect(self._save_contact_settings)
        layout.addWidget(self.contacts_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.contacts_status = QLabel(
            str((selected_contact or {}).get("last_sync_status", "")).strip()
            or "CardDAV credentials are stored. Contact syncing will be enabled by future widgets."
        )
        self.contacts_status.setWordWrap(True)
        self.contacts_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.contacts_status)

        self._refresh_calendar_account_picker()
        self._refresh_contact_account_picker()

        section = ExpandableServiceSection(
            "calendar_widget",
            "Calendar",
            "Style the calendar popup and connect CalDAV calendars for live events.",
            material_icon("calendar_month"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("calendar_widget"),
            lambda enabled: self._set_service_enabled("calendar_widget", enabled),
        )
        self.service_sections["calendar_widget"] = section
        return section

    def _build_reminders_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.reminders_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["reminders_widget"].get(
                    "show_in_notification_center",
                    False,
                )
            )
        )
        self.reminders_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "reminders_widget", enabled
            )
        )
        self.service_display_switches["reminders_widget"] = (
            self.reminders_display_switch
        )
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a reminders launcher card beside the other overview widgets.",
                self.icon_font,
                self.ui_font,
                self.reminders_display_switch,
            )
        )

        self.reminders_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["reminders_widget"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        self.reminders_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility(
                "reminders_widget", enabled
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications"),
                "Show on bar",
                "Adds a reminders icon to the bar so the widget can be opened directly.",
                self.icon_font,
                self.ui_font,
                self.reminders_bar_switch,
            )
        )

        self.reminders_intensity_combo = QComboBox()
        self.reminders_intensity_combo.setObjectName("settingsCombo")
        self.reminders_intensity_combo.addItem("Quiet", "quiet")
        self.reminders_intensity_combo.addItem("Discrete", "discrete")
        self.reminders_intensity_combo.addItem("Very disturbing", "disturbing")
        current_intensity = str(
            self.settings_state["reminders"].get("default_intensity", "discrete")
        )
        intensity_index = self.reminders_intensity_combo.findData(current_intensity)
        self.reminders_intensity_combo.setCurrentIndex(max(0, intensity_index))
        self.reminders_intensity_combo.currentIndexChanged.connect(
            self._set_reminder_default_intensity
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_active"),
                "Default reminder style",
                "Quiet is subtle, discrete is standard, and very disturbing repeats aggressively.",
                self.icon_font,
                self.ui_font,
                self.reminders_intensity_combo,
            )
        )

        self.reminders_lead_slider = QSlider(Qt.Orientation.Horizontal)
        self.reminders_lead_slider.setRange(0, 120)
        self.reminders_lead_slider.setValue(
            int(self.settings_state["reminders"].get("default_lead_minutes", 20))
        )
        self.reminders_lead_slider.valueChanged.connect(
            self._set_reminder_default_lead_minutes
        )
        layout.addWidget(
            SettingsRow(
                material_icon("alarm"),
                "Lead time",
                "How many minutes before a tracked CalDAV event the reminders widget should surface it.",
                self.icon_font,
                self.ui_font,
                self.reminders_lead_slider,
            )
        )

        self.tea_label_input = QLineEdit(
            self.settings_state["reminders"].get("tea_label", "Tea")
        )
        self.tea_label_input.setPlaceholderText("Tea, eggs, rice, pasta...")
        layout.addWidget(
            SettingsRow(
                material_icon("coffee"),
                "Tea reminder label",
                "Default label for the quick kitchen timer inside the reminders widget.",
                self.icon_font,
                self.ui_font,
                self.tea_label_input,
            )
        )

        self.tea_minutes_slider = QSlider(Qt.Orientation.Horizontal)
        self.tea_minutes_slider.setRange(1, 30)
        self.tea_minutes_slider.setValue(
            int(self.settings_state["reminders"].get("tea_minutes", 5))
        )
        self.tea_minutes_slider.valueChanged.connect(self._set_tea_default_minutes)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Tea reminder minutes",
                "Sets the default duration for tea, eggs, or any quick custom timer.",
                self.icon_font,
                self.ui_font,
                self.tea_minutes_slider,
            )
        )

        self.reminders_status = QLabel(
            f"{len(self.settings_state['reminders'].get('tracked_events', []))} tracked CalDAV reminder(s) saved."
        )
        self.reminders_status.setWordWrap(True)
        self.reminders_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.reminders_status)

        self.reminders_save_button = QPushButton("Save reminder defaults")
        self.reminders_save_button.setObjectName("primaryButton")
        self.reminders_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.reminders_save_button.clicked.connect(self._save_reminders_settings)
        layout.addWidget(self.reminders_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "reminders_widget",
            "Reminders",
            "Surface tracked CalDAV event reminders and configure how noisy they should be.",
            material_icon("alarm"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("reminders_widget"),
            lambda enabled: self._set_service_enabled("reminders_widget", enabled),
        )
        self.service_sections["reminders_widget"] = section
        return section

    def _build_pomodoro_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.pomodoro_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["pomodoro_widget"].get(
                    "show_in_notification_center",
                    True,
                )
            )
        )
        self.pomodoro_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "pomodoro_widget", enabled
            )
        )
        self.service_display_switches["pomodoro_widget"] = self.pomodoro_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a Pomodoro launcher card in the overview page.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_display_switch,
            )
        )

        self.pomodoro_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["pomodoro_widget"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        self.pomodoro_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("pomodoro_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("timer"),
                "Show on bar",
                "Adds a Pomodoro icon to the bar so the timer can be opened directly.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_bar_switch,
            )
        )

        self.pomodoro_work_slider = QSlider(Qt.Orientation.Horizontal)
        self.pomodoro_work_slider.setRange(5, 90)
        self.pomodoro_work_slider.setValue(
            int(self.settings_state["pomodoro"].get("work_minutes", 25))
        )
        self.pomodoro_work_slider.valueChanged.connect(self._set_pomodoro_work_minutes)
        layout.addWidget(
            SettingsRow(
                material_icon("timer"),
                "Work minutes",
                "Length of each focus session before a break begins.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_work_slider,
            )
        )

        self.pomodoro_short_break_slider = QSlider(Qt.Orientation.Horizontal)
        self.pomodoro_short_break_slider.setRange(1, 30)
        self.pomodoro_short_break_slider.setValue(
            int(self.settings_state["pomodoro"].get("short_break_minutes", 5))
        )
        self.pomodoro_short_break_slider.valueChanged.connect(
            self._set_pomodoro_short_break_minutes
        )
        layout.addWidget(
            SettingsRow(
                material_icon("coffee"),
                "Short break minutes",
                "Quick reset break used between most work sessions.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_short_break_slider,
            )
        )

        self.pomodoro_long_break_slider = QSlider(Qt.Orientation.Horizontal)
        self.pomodoro_long_break_slider.setRange(5, 60)
        self.pomodoro_long_break_slider.setValue(
            int(self.settings_state["pomodoro"].get("long_break_minutes", 15))
        )
        self.pomodoro_long_break_slider.valueChanged.connect(
            self._set_pomodoro_long_break_minutes
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Long break minutes",
                "Recovery break used after a full Pomodoro cycle.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_long_break_slider,
            )
        )

        self.pomodoro_cycle_slider = QSlider(Qt.Orientation.Horizontal)
        self.pomodoro_cycle_slider.setRange(2, 8)
        self.pomodoro_cycle_slider.setValue(
            int(self.settings_state["pomodoro"].get("long_break_every", 4))
        )
        self.pomodoro_cycle_slider.valueChanged.connect(
            self._set_pomodoro_long_break_every
        )
        layout.addWidget(
            SettingsRow(
                material_icon("alarm"),
                "Long break every",
                "How many completed focus sessions should happen before the long break.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_cycle_slider,
            )
        )

        self.pomodoro_auto_breaks_switch = SwitchButton(
            bool(self.settings_state["pomodoro"].get("auto_start_breaks", False))
        )
        self.pomodoro_auto_breaks_switch.toggledValue.connect(
            self._set_pomodoro_auto_start_breaks
        )
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Auto-start breaks",
                "Start short and long break timers automatically when work ends.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_auto_breaks_switch,
            )
        )

        self.pomodoro_auto_focus_switch = SwitchButton(
            bool(self.settings_state["pomodoro"].get("auto_start_focus", False))
        )
        self.pomodoro_auto_focus_switch.toggledValue.connect(
            self._set_pomodoro_auto_start_focus
        )
        layout.addWidget(
            SettingsRow(
                material_icon("auto_awesome"),
                "Auto-start focus",
                "Begin the next work session automatically after a break ends.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_auto_focus_switch,
            )
        )

        self.pomodoro_status = QLabel("Pomodoro widget defaults are ready.")
        self.pomodoro_status.setWordWrap(True)
        self.pomodoro_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.pomodoro_status)

        section = ExpandableServiceSection(
            "pomodoro_widget",
            "Pomodoro",
            "Run a focused work timer with quick breaks, a progress ring, and Matugen-aware styling.",
            material_icon("timer"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("pomodoro_widget"),
            lambda enabled: self._set_service_enabled("pomodoro_widget", enabled),
        )
        self.service_sections["pomodoro_widget"] = section
        return section

    def _build_rss_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.rss_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["rss_widget"].get(
                    "show_in_notification_center",
                    True,
                )
            )
        )
        self.rss_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "rss_widget", enabled
            )
        )
        self.service_display_switches["rss_widget"] = self.rss_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose an RSS launcher card in the overview page.",
                self.icon_font,
                self.ui_font,
                self.rss_display_switch,
            )
        )

        self.rss_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["rss_widget"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        self.rss_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("rss_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "Show on bar",
                "Adds an RSS icon to the bar so the feed reader can be opened directly.",
                self.icon_font,
                self.ui_font,
                self.rss_bar_switch,
            )
        )

        self.rss_status = QLabel("RSS widget sources are ready.")
        self.rss_status.setWordWrap(True)
        self.rss_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.rss_status)

        self.rss_settings_qml, self.rss_settings_bridge = create_rss_settings_widget(
            content,
            self.settings_state,
            self._save_rss_settings,
            self._set_rss_status_message,
        )
        layout.addWidget(self.rss_settings_qml)

        section = ExpandableServiceSection(
            "rss_widget",
            "RSS",
            "Read headlines from manual feeds or OPML exports, including self-hosted reader exports.",
            material_icon("web_asset"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("rss_widget"),
            lambda enabled: self._set_service_enabled("rss_widget", enabled),
        )
        self.service_sections["rss_widget"] = section
        return section

    def _set_rss_status_message(self, message: str) -> None:
        if hasattr(self, "rss_status"):
            self.rss_status.setText(message)

    def _build_obs_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.obs_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["obs_widget"].get(
                    "show_in_notification_center", True
                )
            )
        )
        self.obs_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "obs_widget", enabled
            )
        )
        self.service_display_switches["obs_widget"] = self.obs_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose the OBS control surface in the overview page.",
                self.icon_font,
                self.ui_font,
                self.obs_display_switch,
            )
        )

        self.obs_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["obs_widget"].get("show_in_bar", False)
            )
        )
        self.obs_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("obs_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("videocam"),
                "Show on bar",
                "Adds an OBS icon to the bar so streaming controls are one click away.",
                self.icon_font,
                self.ui_font,
                self.obs_bar_switch,
            )
        )

        self.obs_host_input = QLineEdit(
            self.settings_state["obs"].get("host", "127.0.0.1")
        )
        self.obs_port_input = QLineEdit(
            str(self.settings_state["obs"].get("port", 4455))
        )
        self.obs_password_input = QLineEdit(
            self.settings_state["obs"].get("password", "")
        )
        self.obs_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.obs_auto_connect_switch = SwitchButton(
            bool(self.settings_state["obs"].get("auto_connect", False))
        )
        self.obs_auto_connect_switch.toggledValue.connect(self._set_obs_auto_connect)
        self.obs_debug_tooltips_switch = SwitchButton(
            bool(self.settings_state["obs"].get("show_debug_tooltips", False))
        )
        self.obs_debug_tooltips_switch.toggledValue.connect(
            self._set_obs_debug_tooltips
        )
        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "OBS host",
                "OBS WebSocket host, usually 127.0.0.1.",
                self.icon_font,
                self.ui_font,
                self.obs_host_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("sensors"),
                "OBS port",
                "OBS WebSocket port. OBS 30+ defaults to 4455.",
                self.icon_font,
                self.ui_font,
                self.obs_port_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "OBS password",
                "Optional OBS WebSocket password.",
                self.icon_font,
                self.ui_font,
                self.obs_password_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Connect when opened",
                "Try connecting to OBS as soon as the widget opens.",
                self.icon_font,
                self.ui_font,
                self.obs_auto_connect_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("tune"),
                "Show debug tooltips",
                "Adds inspection tooltips to OBS popup elements so we can identify what still needs polishing.",
                self.icon_font,
                self.ui_font,
                self.obs_debug_tooltips_switch,
            )
        )

        self.obs_status = QLabel("OBS widget is ready for local WebSocket control.")
        self.obs_status.setWordWrap(True)
        self.obs_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.obs_status)

        self.obs_save_button = QPushButton("Save OBS settings")
        self.obs_save_button.setObjectName("primaryButton")
        self.obs_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.obs_save_button.clicked.connect(self._save_obs_settings)
        layout.addWidget(self.obs_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "obs_widget",
            "OBS",
            "Livestreaming and recording controls powered by OBS WebSocket, with scene awareness and stream toggles.",
            material_icon("videocam"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("obs_widget"),
            lambda enabled: self._set_service_enabled("obs_widget", enabled),
        )
        self.service_sections["obs_widget"] = section
        return section

    def _build_crypto_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.crypto_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["crypto_widget"].get(
                    "show_in_notification_center", True
                )
            )
        )
        self.crypto_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "crypto_widget", enabled
            )
        )
        self.service_display_switches["crypto_widget"] = self.crypto_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose the crypto tracker card in the overview page.",
                self.icon_font,
                self.ui_font,
                self.crypto_display_switch,
            )
        )

        self.crypto_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["crypto_widget"].get(
                    "show_in_bar", False
                )
            )
        )
        self.crypto_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("crypto_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("show_chart"),
                "Show on bar",
                "Adds a crypto icon to the bar so you can open the tracker quickly.",
                self.icon_font,
                self.ui_font,
                self.crypto_bar_switch,
            )
        )

        self.crypto_coins_input = QLineEdit(
            self.settings_state["crypto"].get("tracked_coins", "bitcoin,ethereum")
        )
        self.crypto_coins_input.setPlaceholderText("bitcoin,ethereum,solana")
        self.crypto_currency_input = QLineEdit(
            self.settings_state["crypto"].get("vs_currency", "usd")
        )
        self.crypto_currency_input.setPlaceholderText("usd")
        self.crypto_api_key_input = QLineEdit(
            self.settings_state["crypto"].get("api_key", "")
        )
        self.crypto_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.crypto_api_key_input.setPlaceholderText("Optional CoinGecko Demo API key")
        layout.addWidget(
            SettingsRow(
                material_icon("show_chart"),
                "Tracked coins",
                "Comma-separated CoinGecko coin ids like bitcoin, ethereum, solana.",
                self.icon_font,
                self.ui_font,
                self.crypto_coins_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "Quote currency",
                "The currency used for pricing, such as usd or brl.",
                self.icon_font,
                self.ui_font,
                self.crypto_currency_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "CoinGecko Demo key",
                "Optional free demo key for higher limits. Hanauta uses CoinGecko for price and chart data.",
                self.icon_font,
                self.ui_font,
                self.crypto_api_key_input,
            )
        )

        self.crypto_interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.crypto_interval_slider.setRange(5, 180)
        self.crypto_interval_slider.setValue(
            int(self.settings_state["crypto"].get("check_interval_minutes", 15))
        )
        self.crypto_interval_slider.valueChanged.connect(
            self._set_crypto_check_interval
        )
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Check interval",
                "How often Hanauta checks tracked coins for fresh prices and alert-worthy moves.",
                self.icon_font,
                self.ui_font,
                self.crypto_interval_slider,
            )
        )

        self.crypto_chart_days_slider = QSlider(Qt.Orientation.Horizontal)
        self.crypto_chart_days_slider.setRange(1, 90)
        self.crypto_chart_days_slider.setValue(
            int(self.settings_state["crypto"].get("chart_days", 7))
        )
        self.crypto_chart_days_slider.valueChanged.connect(self._set_crypto_chart_days)
        layout.addWidget(
            SettingsRow(
                material_icon("calendar_month"),
                "Chart days",
                "How many recent days the high-resolution chart should cover by default.",
                self.icon_font,
                self.ui_font,
                self.crypto_chart_days_slider,
            )
        )

        self.crypto_alert_switch = SwitchButton(
            bool(self.settings_state["crypto"].get("notify_price_moves", True))
        )
        self.crypto_alert_switch.toggledValue.connect(
            self._set_crypto_notify_price_moves
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_active"),
                "Price alerts",
                "Send notifications when tracked coins move beyond your up/down thresholds.",
                self.icon_font,
                self.ui_font,
                self.crypto_alert_switch,
            )
        )

        self.crypto_up_slider = QSlider(Qt.Orientation.Horizontal)
        self.crypto_up_slider.setRange(1, 20)
        self.crypto_up_slider.setValue(
            int(
                round(float(self.settings_state["crypto"].get("price_up_percent", 3.0)))
            )
        )
        self.crypto_up_slider.valueChanged.connect(self._set_crypto_up_percent)
        layout.addWidget(
            SettingsRow(
                material_icon("bolt"),
                "Up alert threshold",
                "Notify when a tracked coin rises by at least this percent since the previous check.",
                self.icon_font,
                self.ui_font,
                self.crypto_up_slider,
            )
        )

        self.crypto_down_slider = QSlider(Qt.Orientation.Horizontal)
        self.crypto_down_slider.setRange(1, 20)
        self.crypto_down_slider.setValue(
            int(
                round(
                    float(self.settings_state["crypto"].get("price_down_percent", 3.0))
                )
            )
        )
        self.crypto_down_slider.valueChanged.connect(self._set_crypto_down_percent)
        layout.addWidget(
            SettingsRow(
                material_icon("bolt"),
                "Down alert threshold",
                "Notify when a tracked coin falls by at least this percent since the previous check.",
                self.icon_font,
                self.ui_font,
                self.crypto_down_slider,
            )
        )

        crypto_cache = load_service_cache_json("crypto.json")
        if isinstance(crypto_cache, dict) and crypto_cache.get("updated_at"):
            status_text = "Using hanauta-service cache for initial crypto snapshot."
        else:
            status_text = "Crypto tracker is set to CoinGecko pricing."
        self.crypto_status = QLabel(status_text)
        self.crypto_status.setWordWrap(True)
        self.crypto_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.crypto_status)

        self.crypto_save_button = QPushButton("Save crypto settings")
        self.crypto_save_button.setObjectName("primaryButton")
        self.crypto_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.crypto_save_button.clicked.connect(self._save_crypto_settings)
        layout.addWidget(self.crypto_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "crypto_widget",
            "Crypto Tracker",
            "Track several coins, view a high-resolution chart, and get alerts when prices move.",
            material_icon("show_chart"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("crypto_widget"),
            lambda enabled: self._set_service_enabled("crypto_widget", enabled),
        )
        self.service_sections["crypto_widget"] = section
        return section

    def _build_vps_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.vps_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["vps_widget"].get(
                    "show_in_notification_center", True
                )
            )
        )
        self.vps_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "vps_widget", enabled
            )
        )
        self.service_display_switches["vps_widget"] = self.vps_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a VPS operations card in the overview page.",
                self.icon_font,
                self.ui_font,
                self.vps_display_switch,
            )
        )

        self.vps_host_input = QLineEdit(self.settings_state["vps"].get("host", ""))
        self.vps_port_input = QLineEdit(str(self.settings_state["vps"].get("port", 22)))
        self.vps_username_input = QLineEdit(
            self.settings_state["vps"].get("username", "")
        )
        self.vps_identity_input = QLineEdit(
            self.settings_state["vps"].get("identity_file", "")
        )
        self.vps_service_input = QLineEdit(
            self.settings_state["vps"].get("app_service", "")
        )
        self.vps_health_input = QLineEdit(
            self.settings_state["vps"].get("health_command", "uptime && df -h /")
        )
        self.vps_update_input = QLineEdit(
            self.settings_state["vps"].get(
                "update_command", "sudo apt update && sudo apt upgrade -y"
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "Host",
                "Server host or IP for SSH connections.",
                self.icon_font,
                self.ui_font,
                self.vps_host_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("sensors"),
                "Port",
                "SSH port for the VPS.",
                self.icon_font,
                self.ui_font,
                self.vps_port_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("person"),
                "Username",
                "SSH username.",
                self.icon_font,
                self.ui_font,
                self.vps_username_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("lock"),
                "Identity file",
                "Optional SSH private key path if you do not want to rely on your default agent.",
                self.icon_font,
                self.ui_font,
                self.vps_identity_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("hub"),
                "App service",
                "Optional systemd service to restart or check quickly, like caddy or myapp.service.",
                self.icon_font,
                self.ui_font,
                self.vps_service_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("terminal"),
                "Health command",
                "Command used by the widget to collect uptime, disk, and service health.",
                self.icon_font,
                self.ui_font,
                self.vps_health_input,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Update command",
                "Command used when you want Hanauta to run package updates over SSH.",
                self.icon_font,
                self.ui_font,
                self.vps_update_input,
            )
        )

        self.vps_status = QLabel(
            "VPS widget can run SSH health checks and maintenance commands."
        )
        self.vps_status.setWordWrap(True)
        self.vps_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.vps_status)

        self.vps_save_button = QPushButton("Save VPS settings")
        self.vps_save_button.setObjectName("primaryButton")
        self.vps_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.vps_save_button.clicked.connect(self._save_vps_settings)
        layout.addWidget(self.vps_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "vps_widget",
            "VPS Care",
            "SSH into your VPS health workflow for checks, package updates, and service restarts.",
            material_icon("storage"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("vps_widget"),
            lambda enabled: self._set_service_enabled("vps_widget", enabled),
        )
        self.service_sections["vps_widget"] = section
        return section

    def _build_desktop_clock_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        native_clock = DESKTOP_CLOCK_BINARY.exists()

        self.clock_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["desktop_clock_widget"].get(
                    "show_in_notification_center", True
                )
            )
        )
        self.clock_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "desktop_clock_widget", enabled
            )
        )
        self.service_display_switches["desktop_clock_widget"] = (
            self.clock_display_switch
        )
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose the desktop clock launcher in the overview page.",
                self.icon_font,
                self.ui_font,
                self.clock_display_switch,
            )
        )

        self.clock_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.clock_size_slider.setRange(220, 520)
        self.clock_size_slider.setValue(
            int(self.settings_state["clock"].get("size", 320))
        )
        self.clock_size_slider.valueChanged.connect(self._set_clock_size)
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Clock size",
                "Resize the desktop clock without changing its design language.",
                self.icon_font,
                self.ui_font,
                self.clock_size_slider,
            )
        )

        self.clock_seconds_switch = SwitchButton(
            bool(self.settings_state["clock"].get("show_seconds", True))
        )
        self.clock_seconds_switch.toggledValue.connect(self._set_clock_show_seconds)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Show seconds hand",
                "Display the slim moving seconds hand on the analog clock face.",
                self.icon_font,
                self.ui_font,
                self.clock_seconds_switch,
            )
        )

        self.clock_digital_spacing_slider = QSlider(Qt.Orientation.Horizontal)
        self.clock_digital_spacing_slider.setRange(8, 64)
        self.clock_digital_spacing_slider.setValue(
            int(self.settings_state["clock"].get("digital_line_spacing", 14))
        )
        self.clock_digital_spacing_slider.valueChanged.connect(
            self._set_clock_digital_line_spacing
        )
        layout.addWidget(
            SettingsRow(
                material_icon("swap_vert"),
                "Digital line spacing",
                "Adjust spacing between the stacked digital hour and minute text.",
                self.icon_font,
                self.ui_font,
                self.clock_digital_spacing_slider,
            )
        )

        self.clock_position_x_spin = QSpinBox()
        self.clock_position_x_spin.setRange(-1, 10000)
        self.clock_position_x_spin.setSpecialValueText("Auto")
        self.clock_position_x_spin.setValue(
            int(self.settings_state["clock"].get("position_x", -1))
        )
        self.clock_position_x_spin.valueChanged.connect(self._set_clock_position_x)
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Clock X position",
                "Set a fixed horizontal position in pixels. Use Auto to keep centered.",
                self.icon_font,
                self.ui_font,
                self.clock_position_x_spin,
            )
        )

        self.clock_position_y_spin = QSpinBox()
        self.clock_position_y_spin.setRange(-1, 10000)
        self.clock_position_y_spin.setSpecialValueText("Auto")
        self.clock_position_y_spin.setValue(
            int(self.settings_state["clock"].get("position_y", -1))
        )
        self.clock_position_y_spin.valueChanged.connect(self._set_clock_position_y)
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Clock Y position",
                "Set a fixed vertical position in pixels. Use Auto to follow bar-aware placement.",
                self.icon_font,
                self.ui_font,
                self.clock_position_y_spin,
            )
        )

        if native_clock:
            clock_status_text = "Desktop clock service is built in and ready."
        else:
            clock_status_text = "Desktop clock service is enabled, but `hanauta/bin/hanauta-clock` is missing."
        self.clock_status = QLabel(clock_status_text)
        self.clock_status.setWordWrap(True)
        self.clock_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.clock_status)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(10)

        self.clock_open_button = QPushButton("Open clock now")
        self.clock_open_button.setObjectName("primaryButton")
        self.clock_open_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clock_open_button.clicked.connect(self._launch_desktop_clock)
        actions_row.addWidget(self.clock_open_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.clock_reset_button = QPushButton("Reset clock position")
        self.clock_reset_button.setObjectName("secondaryButton")
        self.clock_reset_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clock_reset_button.clicked.connect(self._reset_clock_position)
        actions_row.addWidget(self.clock_reset_button, 0, Qt.AlignmentFlag.AlignLeft)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        section = ExpandableServiceSection(
            "desktop_clock_widget",
            "Desktop Clock",
            "A Hanauta-native analog and digital desktop clock with a sculpted face, Matugen colors, and a native Qt clock binary by default.",
            material_icon("watch"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("desktop_clock_widget"),
            lambda enabled: self._set_service_enabled("desktop_clock_widget", enabled),
        )
        self.service_sections["desktop_clock_widget"] = section
        return section

    def _build_game_mode_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.game_mode_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["game_mode"].get(
                    "show_in_notification_center", True
                )
            )
        )
        self.game_mode_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility(
                "game_mode", enabled
            )
        )
        self.service_display_switches["game_mode"] = self.game_mode_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose the Game Mode launcher in the notification center overview.",
                self.icon_font,
                self.ui_font,
                self.game_mode_display_switch,
            )
        )

        self.game_mode_bar_switch = SwitchButton(
            bool(self.settings_state["services"]["game_mode"].get("show_in_bar", False))
        )
        self.game_mode_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("game_mode", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("sports_esports"),
                "Show on bar",
                "Adds a Game Mode icon to the bar so the gamemoded popup is always one click away.",
                self.icon_font,
                self.ui_font,
                self.game_mode_bar_switch,
            )
        )

        self.game_mode_availability = QLabel("Checking gamemoded availability...")
        self.game_mode_availability.setWordWrap(True)
        self.game_mode_availability.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.game_mode_availability)

        self.game_mode_status = QLabel("Game Mode status is loading...")
        self.game_mode_status.setWordWrap(True)
        self.game_mode_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.game_mode_status)

        section = ExpandableServiceSection(
            "game_mode",
            "Game Mode",
            "Launch a compact popup that manages the gamemoded user service and keeps the gaming toggle close at hand.",
            material_icon("sports_esports"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("game_mode"),
            lambda enabled: self._set_service_enabled("game_mode", enabled),
        )
        self.service_sections["game_mode"] = section
        QTimer.singleShot(0, self._queue_game_mode_summary_refresh)
        return section

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

    def _build_virtualization_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        virtualization = self.settings_state["services"].setdefault(
            "virtualization", {}
        )
        ide_actions = virtualization.get("ide_actions", {})
        if not isinstance(ide_actions, dict):
            ide_actions = {}
            virtualization["ide_actions"] = ide_actions

        self.virtualbox_manager_switch = SwitchButton(
            bool(virtualization.get("virtualbox_manager_to_next_workspace", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("keyboard_tab"),
                "Move VirtualBox Manager away",
                "When a VM window launches, move the manager window to the next workspace so the guest VM keeps this workspace.",
                self.icon_font,
                self.ui_font,
                self.virtualbox_manager_switch,
            )
        )

        self.virtualbox_guest_current_ws_switch = SwitchButton(
            bool(virtualization.get("virtualbox_guest_keep_current_workspace", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("keep"),
                "Keep VM on current workspace",
                "Pins VirtualBox guest windows to the workspace where you launched them.",
                self.icon_font,
                self.ui_font,
                self.virtualbox_guest_current_ws_switch,
            )
        )

        self.virtualbox_guest_fullscreen_switch = SwitchButton(
            bool(virtualization.get("virtualbox_guest_fullscreen", False))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("fullscreen"),
                "Auto-fullscreen guest VM",
                "Automatically fullscreen VirtualBox guest windows when they open.",
                self.icon_font,
                self.ui_font,
                self.virtualbox_guest_fullscreen_switch,
            )
        )

        self.virtualization_prompt_once_switch = SwitchButton(
            bool(virtualization.get("emulator_prompt_once_per_ide", True))
        )
        layout.addWidget(
            SettingsRow(
                material_icon("help"),
                "Prompt once per IDE",
                "Show the emulator layout decision dialog only once per IDE and remember the choice.",
                self.icon_font,
                self.ui_font,
                self.virtualization_prompt_once_switch,
            )
        )

        self.virtualization_move_target_combo = QComboBox()
        self.virtualization_move_target_combo.setObjectName("settingsCombo")
        self.virtualization_move_target_combo.addItem(
            "Next workspace on current output", "next_on_output"
        )
        self.virtualization_move_target_combo.addItem("Next workspace", "next")
        target_value = (
            str(virtualization.get("emulator_move_target", "next_on_output"))
            .strip()
            .lower()
        )
        target_index = self.virtualization_move_target_combo.findData(
            target_value
            if target_value in {"next", "next_on_output"}
            else "next_on_output"
        )
        self.virtualization_move_target_combo.setCurrentIndex(
            target_index if target_index >= 0 else 0
        )
        layout.addWidget(
            SettingsRow(
                material_icon("move_up"),
                "Emulator move target",
                "Default destination when emulator layout is set to move to another workspace.",
                self.icon_font,
                self.ui_font,
                self.virtualization_move_target_combo,
            )
        )

        def ide_combo(saved: str) -> QComboBox:
            combo = QComboBox()
            combo.setObjectName("settingsCombo")
            combo.addItem("Ask on launch", "ask")
            combo.addItem("Split current workspace", "split")
            combo.addItem("Move emulator to another workspace", "move_workspace")
            index = combo.findData(
                saved if saved in {"ask", "split", "move_workspace"} else "ask"
            )
            combo.setCurrentIndex(index if index >= 0 else 0)
            return combo

        self.virtualization_ide_vscode_combo = ide_combo(
            str(ide_actions.get("vscode", "ask")).strip().lower()
        )
        layout.addWidget(
            SettingsRow(
                material_icon("code"),
                "VSCode emulator behavior",
                "Choose how Hanauta places Android Emulator when launched from VSCode.",
                self.icon_font,
                self.ui_font,
                self.virtualization_ide_vscode_combo,
            )
        )

        self.virtualization_ide_vscodium_combo = ide_combo(
            str(ide_actions.get("vscodium", "ask")).strip().lower()
        )
        layout.addWidget(
            SettingsRow(
                material_icon("code"),
                "VSCodium emulator behavior",
                "Choose how Hanauta places Android Emulator when launched from VSCodium.",
                self.icon_font,
                self.ui_font,
                self.virtualization_ide_vscodium_combo,
            )
        )

        self.virtualization_ide_android_studio_combo = ide_combo(
            str(ide_actions.get("android_studio", "ask")).strip().lower()
        )
        layout.addWidget(
            SettingsRow(
                material_icon("android"),
                "Android Studio emulator behavior",
                "Choose how Hanauta places Android Emulator when launched from Android Studio.",
                self.icon_font,
                self.ui_font,
                self.virtualization_ide_android_studio_combo,
            )
        )

        self.virtualization_ide_jetbrains_combo = ide_combo(
            str(ide_actions.get("jetbrains", "ask")).strip().lower()
        )
        layout.addWidget(
            SettingsRow(
                material_icon("memory"),
                "JetBrains IDE emulator behavior",
                "Choose how Hanauta places Android Emulator for IntelliJ/Android Studio-family IDEs.",
                self.icon_font,
                self.ui_font,
                self.virtualization_ide_jetbrains_combo,
            )
        )

        reset_button = QPushButton("Reset learned IDE choices")
        reset_button.setObjectName("secondaryButton")
        reset_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reset_button.clicked.connect(self._reset_virtualization_ide_choices)

        save_button = QPushButton("Save virtualization settings")
        save_button.setObjectName("primaryButton")
        save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_button.clicked.connect(self._save_virtualization_settings)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addWidget(reset_button)
        button_row.addWidget(save_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.virtualization_status = QLabel(
            "Virtualization daemon listens for i3 window events and applies VM/emulator routing policy."
        )
        self.virtualization_status.setWordWrap(True)
        self.virtualization_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.virtualization_status)

        section = ExpandableServiceSection(
            "virtualization",
            "Virtualization",
            "Manage VirtualBox manager routing, guest VM placement, and emulator layout behavior per IDE.",
            material_icon("developer_board"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("virtualization"),
            lambda enabled: self._set_service_enabled("virtualization", enabled),
        )
        self.service_sections["virtualization"] = section
        return section

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

    def _build_study_tracker_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.study_tracker_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["study_tracker_widget"].get(
                    "show_in_bar", False
                )
            )
        )
        self.study_tracker_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility(
                "study_tracker_widget", enabled
            )
        )
        self.service_display_switches["study_tracker_widget"] = (
            self.study_tracker_bar_switch
        )
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show on bar",
                "Display a Study Tracker icon in the bar that opens a live progress popup.",
                self.icon_font,
                self.ui_font,
                self.study_tracker_bar_switch,
            )
        )

        open_button = QPushButton("Open Study Tracker")
        open_button.setObjectName("secondaryButton")
        open_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_button.clicked.connect(self._open_study_tracker_app)
        layout.addWidget(
            SettingsRow(
                material_icon("open_in_new"),
                "Open full app",
                "Launches the full Study Tracker app to manage tasks, resources, schedules, and sessions.",
                self.icon_font,
                self.ui_font,
                open_button,
            )
        )

        self.study_tracker_status = QLabel(
            "Disabled by default. Enable this service to add a realistic Study Tracker stats popup to the bar."
        )
        self.study_tracker_status.setWordWrap(True)
        self.study_tracker_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.study_tracker_status)

        section = ExpandableServiceSection(
            "study_tracker_widget",
            "Study Tracker",
            "Shows today minutes, streak, task completion, active focus target, and upcoming study blocks in a compact popup.",
            material_icon("school"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("study_tracker_widget"),
            lambda enabled: self._set_service_enabled("study_tracker_widget", enabled),
        )
        self.service_sections["study_tracker_widget"] = section
        return section

    def _build_ntfy_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.ntfy_server_input = QLineEdit(
            self.settings_state["ntfy"].get("server_url", "https://ntfy.sh")
        )
        self.ntfy_server_input.setPlaceholderText("https://ntfy.sh")
        layout.addWidget(
            SettingsRow(
                material_icon("web_asset"),
                "Server URL",
                "Custom ntfy instance URL.",
                self.icon_font,
                self.ui_font,
                self.ntfy_server_input,
            )
        )

        self.ntfy_auth_mode_combo = QComboBox()
        self.ntfy_auth_mode_combo.setObjectName("settingsCombo")
        self.ntfy_auth_mode_combo.addItem("Access token", "token")
        self.ntfy_auth_mode_combo.addItem("Username & password", "basic")
        auth_mode = str(self.settings_state["ntfy"].get("auth_mode", "token"))
        auth_index = self.ntfy_auth_mode_combo.findData(auth_mode)
        self.ntfy_auth_mode_combo.setCurrentIndex(auth_index if auth_index >= 0 else 0)
        self.ntfy_auth_mode_combo.currentIndexChanged.connect(
            self._sync_ntfy_auth_inputs
        )
        layout.addWidget(
            SettingsRow(
                material_icon("shield"),
                "Authentication method",
                "Choose whether to authenticate via bearer token or basic auth.",
                self.icon_font,
                self.ui_font,
                self.ntfy_auth_mode_combo,
            )
        )

        self.ntfy_token_input = QLineEdit(self.settings_state["ntfy"].get("token", ""))
        self.ntfy_token_input.setPlaceholderText("Access token")
        self.ntfy_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ntfy_token_row = SettingsRow(
            material_icon("bolt"),
            "Access token",
            "Bearer token for ntfy authentication if required.",
            self.icon_font,
            self.ui_font,
            self.ntfy_token_input,
        )
        layout.addWidget(self.ntfy_token_row)

        self.ntfy_username_input = QLineEdit(
            self.settings_state["ntfy"].get("username", "")
        )
        self.ntfy_username_input.setPlaceholderText("Username")
        self.ntfy_password_input = QLineEdit(
            self.settings_state["ntfy"].get("password", "")
        )
        self.ntfy_password_input.setPlaceholderText("Password")
        self.ntfy_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ntfy_username_row = SettingsRow(
            material_icon("person"),
            "Username",
            "Basic auth username.",
            self.icon_font,
            self.ui_font,
            self.ntfy_username_input,
        )
        self.ntfy_password_row = SettingsRow(
            material_icon("lock"),
            "Password",
            "Basic auth password.",
            self.icon_font,
            self.ui_font,
            self.ntfy_password_input,
        )
        layout.addWidget(self.ntfy_username_row)
        layout.addWidget(self.ntfy_password_row)

        self.ntfy_topics_model = QStringListModel(self)
        self.ntfy_topic_entry_input = QLineEdit()
        self.ntfy_topic_entry_input.setPlaceholderText(
            "Add or pick a topic and press Enter"
        )
        self.ntfy_topic_entry_input_completer = QCompleter(self.ntfy_topics_model, self)
        self.ntfy_topic_entry_input_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.ntfy_topic_entry_input_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.ntfy_topic_entry_input.setCompleter(self.ntfy_topic_entry_input_completer)
        self.ntfy_topic_entry_input.returnPressed.connect(
            self._add_ntfy_topic_from_entry
        )
        self.ntfy_topic_entry_input_completer.activated[str].connect(
            self._add_ntfy_topic
        )

        self.ntfy_topic_filter_input = QLineEdit()
        self.ntfy_topic_filter_input.setPlaceholderText("Filter available topics")
        self.ntfy_topic_filter_input.textChanged.connect(self._filter_ntfy_topics)

        self.ntfy_refresh_topics_button = QPushButton("Refresh topics")
        self.ntfy_refresh_topics_button.setObjectName("secondaryButton")
        self.ntfy_refresh_topics_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.ntfy_refresh_topics_button.clicked.connect(self._fetch_ntfy_topics)

        self.ntfy_topic_list = QListWidget()
        self.ntfy_topic_list.setAlternatingRowColors(True)
        self.ntfy_topic_list.setMinimumHeight(150)
        self.ntfy_topic_list.itemChanged.connect(self._update_ntfy_selected_topics)

        self.ntfy_selected_topics_label = QLabel("No topics selected yet.")
        self.ntfy_selected_topics_label.setWordWrap(True)
        self.ntfy_selected_topics_label.setStyleSheet("color: rgba(246,235,247,0.72);")

        self.ntfy_all_topics_checkbox = QCheckBox(
            "Receive notifications from all topics"
        )
        self.ntfy_all_topics_checkbox.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.ntfy_all_topics_checkbox.stateChanged.connect(
            self._sync_ntfy_topic_controls
        )

        topic_controls = QWidget()
        topic_layout = QVBoxLayout(topic_controls)
        topic_layout.setContentsMargins(0, 0, 0, 0)
        topic_layout.setSpacing(6)
        topic_layout.addWidget(self.ntfy_topic_entry_input)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        filter_row.addWidget(self.ntfy_topic_filter_input)
        filter_row.addWidget(self.ntfy_refresh_topics_button)
        topic_layout.addLayout(filter_row)
        topic_layout.addWidget(self.ntfy_topic_list)
        topic_layout.addWidget(self.ntfy_selected_topics_label)
        topic_layout.addWidget(self.ntfy_all_topics_checkbox)

        layout.addWidget(
            SettingsRow(
                material_icon("notifications"),
                "Topics",
                "Select one or more topics to publish to and optionally fetch them from the server.",
                self.icon_font,
                self.ui_font,
                topic_controls,
            )
        )

        self.ntfy_bar_switch = SwitchButton(
            bool(self.settings_state["ntfy"].get("show_in_bar", False))
        )
        self.ntfy_bar_switch.toggledValue.connect(self._set_ntfy_show_in_bar)
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show on bar",
                "Display an ntfy publish icon on the bar.",
                self.icon_font,
                self.ui_font,
                self.ntfy_bar_switch,
            )
        )

        self.ntfy_hide_content_switch = SwitchButton(
            bool(self.settings_state["ntfy"].get("hide_notification_content", False))
        )
        self.ntfy_hide_content_switch.toggledValue.connect(
            self._set_ntfy_hide_notification_content
        )
        layout.addWidget(
            SettingsRow(
                material_icon("visibility_off"),
                "Hide notification content",
                "Show a privacy-friendly ntfy alert without the original title, message text, or action buttons.",
                self.icon_font,
                self.ui_font,
                self.ntfy_hide_content_switch,
            )
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.ntfy_save_button = QPushButton("Save")
        self.ntfy_save_button.setObjectName("primaryButton")
        self.ntfy_test_button = QPushButton("Send Test")
        self.ntfy_test_button.setObjectName("secondaryButton")
        for button in (self.ntfy_save_button, self.ntfy_test_button):
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ntfy_save_button.clicked.connect(self._save_ntfy_settings)
        self.ntfy_test_button.clicked.connect(self._send_ntfy_test)
        buttons.addWidget(self.ntfy_save_button)
        buttons.addWidget(self.ntfy_test_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.ntfy_status = QLabel("ntfy integration is idle.")
        self.ntfy_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.ntfy_status.setWordWrap(True)
        layout.addWidget(self.ntfy_status)

        saved_topics = [
            str(item).strip()
            for item in self.settings_state["ntfy"].get("topics", [])
            if isinstance(item, str) and str(item).strip()
        ]
        legacy_topic = str(self.settings_state["ntfy"].get("topic", "")).strip()
        if legacy_topic and legacy_topic not in saved_topics:
            saved_topics.insert(0, legacy_topic)
        self.ntfy_selected_topics = []
        for topic in saved_topics:
            if topic and topic not in self.ntfy_selected_topics:
                self.ntfy_selected_topics.append(topic)
        self.ntfy_available_topics = list(self.ntfy_selected_topics)
        self._populate_ntfy_topic_list(self.ntfy_available_topics)
        self.ntfy_all_topics_checkbox.setChecked(
            bool(self.settings_state["ntfy"].get("all_topics", False))
        )
        self._sync_ntfy_auth_inputs()
        self._sync_ntfy_topic_controls()

        section = ExpandableServiceSection(
            "ntfy",
            "ntfy",
            "Custom ntfy server, topics, credentials, and an optional bar publisher icon.",
            material_icon("notifications"),
            self.icon_font,
            self.ui_font,
            content,
            bool(self.settings_state["ntfy"].get("enabled", False)),
            self._set_ntfy_enabled,
        )
        self.ntfy_section = section
        return section

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

    def _service_enabled(self, key: str) -> bool:
        return bool(self.settings_state["services"].get(key, {}).get("enabled", True))

    def _set_service_enabled(self, key: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault(key, {})
        service["enabled"] = bool(enabled)
        if not enabled:
            service["show_in_notification_center"] = False
            if key == "kdeconnect":
                self._set_notification_rule_enabled(
                    "kdeconnect_ignore_whatsapp_when_desktop_client_active",
                    False,
                    persist=True,
                )
            if key == "vpn_control":
                service["reconnect_on_login"] = False
            if key == "christian_widget":
                service["show_in_bar"] = False
                service["next_devotion_notifications"] = False
                service["hourly_verse_notifications"] = False
            if key == "health_widget":
                service["show_in_bar"] = False
                service["water_reminder_notifications"] = False
                service["stand_up_reminder_notifications"] = False
                service["movement_reminder_notifications"] = False
            if key in {
                "home_assistant",
                "reminders_widget",
                "pomodoro_widget",
                "rss_widget",
                "obs_widget",
                "crypto_widget",
                "game_mode",
                "cap_alerts",
                "study_tracker_widget",
            }:
                service["show_in_bar"] = False
        save_settings_state(self.settings_state)
        section = getattr(self, "service_sections", {}).get(key)
        if section is not None:
            section.set_enabled(enabled)
        display_switch = getattr(self, "service_display_switches", {}).get(key)
        if display_switch is not None:
            if key == "christian_widget":
                display_switch.setChecked(bool(service.get("show_in_bar", False)))
            else:
                display_switch.setChecked(
                    bool(service.get("show_in_notification_center", False))
                )
            display_switch._apply_state()
        if key == "christian_widget":
            for attr_name, setting_key in (
                ("christian_next_devotion_switch", "next_devotion_notifications"),
                ("christian_hourly_verse_switch", "hourly_verse_notifications"),
            ):
                switch = getattr(self, attr_name, None)
                if switch is not None:
                    switch.setChecked(bool(service.get(setting_key, False)))
                    switch._apply_state()
        if key == "health_widget":
            switch = getattr(self, "service_display_switches", {}).get(key)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", True)))
                switch._apply_state()
            for attr_name, setting_key in (
                ("health_water_reminder_switch", "water_reminder_notifications"),
                ("health_stand_reminder_switch", "stand_up_reminder_notifications"),
                ("health_movement_reminder_switch", "movement_reminder_notifications"),
            ):
                reminder_switch = getattr(self, attr_name, None)
                if reminder_switch is not None:
                    reminder_switch.setChecked(bool(service.get(setting_key, False)))
                    reminder_switch._apply_state()
        if key in {
            "calendar_widget",
            "reminders_widget",
            "pomodoro_widget",
            "obs_widget",
            "crypto_widget",
            "vps_widget",
            "desktop_clock_widget",
            "game_mode",
            "cap_alerts",
        }:
            display_switch = getattr(self, "service_display_switches", {}).get(key)
            if display_switch is not None:
                display_switch.setChecked(
                    bool(service.get("show_in_notification_center", False))
                )
                display_switch._apply_state()
        if key == "vpn_control":
            switch = getattr(self, "vpn_reconnect_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("reconnect_on_login", False)))
                switch._apply_state()
        if key == "kdeconnect":
            switch = getattr(self, "kdeconnect_whatsapp_ignore_switch", None)
            if switch is not None:
                rule = self.notification_rules_state["rules"].get(
                    "kdeconnect_ignore_whatsapp_when_desktop_client_active",
                    DEFAULT_NOTIFICATION_RULES["rules"][
                        "kdeconnect_ignore_whatsapp_when_desktop_client_active"
                    ],
                )
                switch.setChecked(bool(rule.get("enabled", False) and enabled))
                switch._apply_state()
            low_battery_switch = getattr(self, "kdeconnect_low_battery_switch", None)
            if low_battery_switch is not None:
                low_battery_switch.setChecked(
                    bool(
                        service.get("low_battery_fullscreen_notification", False)
                        and enabled
                    )
                )
                low_battery_switch._apply_state()
            threshold_slider = getattr(
                self, "kdeconnect_battery_threshold_slider", None
            )
            threshold_label = getattr(self, "kdeconnect_battery_threshold_label", None)
            if threshold_slider is not None:
                threshold_slider.setValue(int(service.get("low_battery_threshold", 20)))
            if threshold_label is not None:
                threshold_label.setText(
                    f"{int(service.get('low_battery_threshold', 20))}%"
                )
        if key == "reminders_widget":
            switch = getattr(self, "reminders_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "home_assistant":
            switch = getattr(self, "ha_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "pomodoro_widget":
            switch = getattr(self, "pomodoro_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "rss_widget":
            switch = getattr(self, "rss_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "obs_widget":
            switch = getattr(self, "obs_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "crypto_widget":
            switch = getattr(self, "crypto_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "game_mode":
            switch = getattr(self, "game_mode_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "cap_alerts":
            switch = getattr(self, "cap_alerts_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
            test_switch = getattr(self, "cap_alerts_test_mode_switch", None)
            if test_switch is not None:
                test_switch.setChecked(bool(service.get("test_mode", False)))
                test_switch._apply_state()
        if key == "study_tracker_widget":
            switch = getattr(self, "study_tracker_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "virtualization":
            if enabled:
                self._start_virtualization_daemon()
            else:
                self._stop_virtualization_daemon()
        if hasattr(self, "_refresh_service_widget_order"):
            self._refresh_service_widget_order()

    def _set_service_notification_visibility(self, key: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault(key, {})
        if not service.get("enabled", True):
            return
        service["show_in_notification_center"] = bool(enabled)
        save_settings_state(self.settings_state)

    def _set_service_bar_visibility(self, key: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault(key, {})
        if not service.get("enabled", True):
            return
        service["show_in_bar"] = bool(enabled)
        save_settings_state(self.settings_state)
        target = bool(enabled)
        attr_name = BAR_SERVICE_SWITCH_ATTRS.get(key, "")
        if attr_name:
            switch = getattr(self, attr_name, None)
            if isinstance(switch, SwitchButton) and bool(switch.isChecked()) != target:
                switch.setChecked(target)
                switch._apply_state()
        if key not in SERVICE_DISPLAY_SWITCH_NON_BAR_KEYS:
            switch = getattr(self, "service_display_switches", {}).get(key)
            if isinstance(switch, SwitchButton) and bool(switch.isChecked()) != target:
                switch.setChecked(target)
                switch._apply_state()
        if hasattr(self, "_refresh_bar_service_icon_rows"):
            self._refresh_bar_service_icon_rows()

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

    def _open_bar_icon_config(self) -> None:
        try:
            BAR_ICON_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if not BAR_ICON_CONFIG_FILE.exists() and BAR_ICON_EXAMPLE_FILE.exists():
                BAR_ICON_CONFIG_FILE.write_text(
                    BAR_ICON_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8"
                )
        except OSError:
            return
        run_bg(["xdg-open", str(BAR_ICON_CONFIG_FILE)])

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

    def _refresh_audio_devices(self) -> None:
        sinks = list_audio_devices("sinks")
        sources = list_audio_devices("sources")
        saved_audio = self.settings_state.get("audio", {})
        selected_sink = str(
            saved_audio.get("default_sink", "")
        ).strip() or default_audio_device("sink")
        selected_source = str(
            saved_audio.get("default_source", "")
        ).strip() or default_audio_device("source")
        if hasattr(self, "audio_sink_combo"):
            self.audio_sink_combo.blockSignals(True)
            self.audio_sink_combo.clear()
            self.audio_sink_combo.addItem("System default", "")
            for label, value in sinks:
                self.audio_sink_combo.addItem(label, value)
            sink_index = self.audio_sink_combo.findData(selected_sink)
            self.audio_sink_combo.setCurrentIndex(max(0, sink_index))
            self.audio_sink_combo.blockSignals(False)
        if hasattr(self, "audio_source_combo"):
            self.audio_source_combo.blockSignals(True)
            self.audio_source_combo.clear()
            self.audio_source_combo.addItem("System default", "")
            for label, value in sources:
                self.audio_source_combo.addItem(label, value)
            source_index = self.audio_source_combo.findData(selected_source)
            self.audio_source_combo.setCurrentIndex(max(0, source_index))
            self.audio_source_combo.blockSignals(False)
        if hasattr(self, "audio_status"):
            self.audio_status.setText(
                f"Detected {len(sinks)} sink(s) and {len(sources)} source(s)."
            )

    def _save_lockscreen_settings(self) -> None:
        lockscreen = self.settings_state.setdefault("lockscreen", {})
        lockscreen["blur_screenshot"] = bool(self.lockscreen_blur_switch.isChecked())
        lockscreen["pause_media_on_lock"] = bool(
            self.lockscreen_pause_media_switch.isChecked()
        )
        lockscreen["use_slow_fade"] = bool(self.lockscreen_slow_fade_switch.isChecked())
        lockscreen["prefer_i3lock_color"] = bool(
            self.lockscreen_prefer_color_switch.isChecked()
        )
        lockscreen["show_clock"] = bool(self.lockscreen_show_clock_switch.isChecked())
        lockscreen["show_indicator"] = bool(
            self.lockscreen_show_indicator_switch.isChecked()
        )
        lockscreen["pass_media_keys"] = bool(
            self.lockscreen_pass_media_switch.isChecked()
        )
        lockscreen["pass_volume_keys"] = bool(
            self.lockscreen_pass_volume_switch.isChecked()
        )
        try:
            lockscreen["refresh_rate"] = max(
                0, min(30, int(self.lockscreen_refresh_input.text().strip() or "1"))
            )
        except Exception:
            lockscreen["refresh_rate"] = 1
            self.lockscreen_refresh_input.setText("1")
        try:
            lockscreen["ring_radius"] = max(
                8,
                min(80, int(self.lockscreen_ring_radius_input.text().strip() or "28")),
            )
        except Exception:
            lockscreen["ring_radius"] = 28
            self.lockscreen_ring_radius_input.setText("28")
        try:
            lockscreen["ring_width"] = max(
                1, min(24, int(self.lockscreen_ring_width_input.text().strip() or "6"))
            )
        except Exception:
            lockscreen["ring_width"] = 6
            self.lockscreen_ring_width_input.setText("6")
        lockscreen["time_format"] = (
            self.lockscreen_time_format_input.text().strip() or "%H:%M"
        )
        lockscreen["date_format"] = (
            self.lockscreen_date_format_input.text().strip() or "%A, %d %B %Y"
        )
        lockscreen["greeter_text"] = (
            self.lockscreen_greeter_text_input.text().strip()
            or "Hanauta locked • Type your password to unlock"
        )
        lockscreen["verifying_text"] = (
            self.lockscreen_verifying_text_input.text().strip() or "Verifying..."
        )
        lockscreen["wrong_text"] = (
            self.lockscreen_wrong_text_input.text().strip() or "Wrong password"
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "lockscreen_status"):
            blur_text = "enabled" if lockscreen["blur_screenshot"] else "disabled"
            self.lockscreen_status.setText(
                f"Lockscreen settings saved. Blur is {blur_text}."
            )

    def _save_audio_settings(self) -> None:
        audio = self.settings_state.setdefault("audio", {})
        sink = (
            str(self.audio_sink_combo.currentData() or "").strip()
            if hasattr(self, "audio_sink_combo")
            else ""
        )
        source = (
            str(self.audio_source_combo.currentData() or "").strip()
            if hasattr(self, "audio_source_combo")
            else ""
        )
        audio["default_sink"] = sink
        audio["default_source"] = source
        audio["alert_sounds_enabled"] = (
            bool(self.audio_alert_sounds_switch.isChecked())
            if hasattr(self, "audio_alert_sounds_switch")
            else True
        )
        audio["route_new_apps_to_default_sink"] = (
            bool(self.audio_route_switch.isChecked())
            if hasattr(self, "audio_route_switch")
            else True
        )
        audio["mute_behavior"] = (
            str(self.audio_mute_behavior_combo.currentData() or "leave_as_is")
            if hasattr(self, "audio_mute_behavior_combo")
            else "leave_as_is"
        )
        save_settings_state(self.settings_state)
        if shutil.which("pactl"):
            if sink:
                subprocess.run(
                    ["pactl", "set-default-sink", sink],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            if source:
                subprocess.run(
                    ["pactl", "set-default-source", source],
                    capture_output=True,
                    text=True,
                    check=False,
                )
        if hasattr(self, "audio_status"):
            self.audio_status.setText("Audio settings saved.")

    def _save_notifications_page_settings(self) -> None:
        notifications = self.settings_state.setdefault("notifications", {})
        try:
            notifications["history_limit"] = max(
                10,
                min(
                    1000,
                    int(self.notifications_history_limit_input.text().strip() or "150"),
                ),
            )
        except Exception:
            notifications["history_limit"] = 150
            self.notifications_history_limit_input.setText("150")
        notifications["urgency_policy"] = str(
            self.notifications_urgency_combo.currentData() or "normal"
        )
        notifications["pause_while_sharing"] = bool(
            self.notifications_pause_share_switch.isChecked()
        )
        notifications["per_app_rules_enabled"] = bool(
            self.notifications_rules_switch.isChecked()
        )
        try:
            notifications["default_duration_ms"] = max(
                2000,
                min(
                    120000,
                    int(
                        self.notifications_default_duration_input.text().strip()
                        or "10000"
                    ),
                ),
            )
        except Exception:
            notifications["default_duration_ms"] = 10000
            self.notifications_default_duration_input.setText("10000")
        notifications["lock_osd_position"] = str(
            self.notifications_lock_osd_position_combo.currentData()
            or "bottom_center"
        )
        notifications["lock_osd_enabled"] = bool(
            self.notifications_lock_osd_enabled_switch.isChecked()
        )
        try:
            self.settings_state["appearance"]["notification_toast_max_width"] = max(
                260,
                min(
                    640,
                    int(self.notifications_toast_width_input.text().strip() or "356"),
                ),
            )
        except Exception:
            self.settings_state["appearance"]["notification_toast_max_width"] = 356
            self.notifications_toast_width_input.setText("356")
        try:
            self.settings_state["appearance"]["notification_toast_max_height"] = max(
                160,
                min(
                    640,
                    int(self.notifications_toast_height_input.text().strip() or "280"),
                ),
            )
        except Exception:
            self.settings_state["appearance"]["notification_toast_max_height"] = 280
            self.notifications_toast_height_input.setText("280")
        save_settings_state(self.settings_state)
        if hasattr(self, "notifications_status"):
            self.notifications_status.setText("Notification settings saved.")

    def _save_input_settings(self) -> None:
        input_settings = self.settings_state.setdefault("input", {})
        input_settings["keyboard_layout"] = self._resolve_keyboard_layout_value()
        region_settings = self.settings_state.setdefault("region", {})
        region_settings["keyboard_layout"] = str(
            input_settings.get("keyboard_layout", "us")
        ).strip() or "us"
        try:
            input_settings["repeat_delay_ms"] = max(
                150,
                min(1200, int(self.input_repeat_delay_input.text().strip() or "300")),
            )
        except Exception:
            input_settings["repeat_delay_ms"] = 300
            self.input_repeat_delay_input.setText("300")
        try:
            input_settings["repeat_rate"] = max(
                10, min(60, int(self.input_repeat_rate_input.text().strip() or "30"))
            )
        except Exception:
            input_settings["repeat_rate"] = 30
            self.input_repeat_rate_input.setText("30")
        input_settings["tap_to_click"] = bool(
            self.input_tap_to_click_switch.isChecked()
        )
        input_settings["natural_scroll"] = bool(
            self.input_natural_scroll_switch.isChecked()
        )
        try:
            input_settings["mouse_accel"] = max(
                -10, min(10, int(self.input_mouse_accel_input.text().strip() or "0"))
            )
        except Exception:
            input_settings["mouse_accel"] = 0
            self.input_mouse_accel_input.setText("0")
        save_settings_state(self.settings_state)
        self._apply_keyboard_layout(str(input_settings.get("keyboard_layout", "us")))
        if shutil.which("xset"):
            run_bg(
                [
                    "xset",
                    "r",
                    "rate",
                    str(input_settings["repeat_delay_ms"]),
                    str(input_settings["repeat_rate"]),
                ]
            )
        if hasattr(self, "input_status"):
            self.input_status.setText(
                "Input settings saved. Keyboard language and repeat settings were applied for this session."
            )

    def _save_startup_settings(self) -> None:
        startup = self.settings_state.setdefault("startup", {})
        startup["launch_bar"] = bool(self.startup_bar_switch.isChecked())
        startup["launch_dock"] = bool(self.startup_dock_switch.isChecked())
        startup["restore_wallpaper"] = bool(self.startup_wallpaper_switch.isChecked())
        startup["restore_displays"] = bool(self.startup_displays_switch.isChecked())
        startup["restore_vpn"] = bool(self.startup_vpn_switch.isChecked())
        startup["restart_hooks_enabled"] = bool(
            self.startup_restart_hooks_switch.isChecked()
        )
        startup["watchdog_enabled"] = bool(self.startup_watchdog_switch.isChecked())
        try:
            startup["startup_delay_seconds"] = max(
                0, min(120, int(self.startup_delay_input.text().strip() or "0"))
            )
        except Exception:
            startup["startup_delay_seconds"] = 0
            self.startup_delay_input.setText("0")
        startup_apps = []
        for i in range(self.startup_apps_list.count()):
            item = self.startup_apps_list.item(i)
            if item:
                text = item.text().strip()
                if text:
                    startup_apps.append(text)
        startup["startup_apps"] = startup_apps
        save_settings_state(self.settings_state)
        if hasattr(self, "startup_status"):
            self.startup_status.setText(
                "Startup settings saved. They are stored for launch and restore workflows."
            )

    def _add_startup_app(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Startup App/Command")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        input_field = QLineEdit()
        input_field.setPlaceholderText(
            "e.g., firefox, ~/.config/autostart.sh, discord --start-minimized"
        )
        layout.addWidget(input_field)
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
            text = input_field.text().strip()
            if text:
                item = QListWidgetItem(text)
                self.startup_apps_list.addItem(item)

    def _remove_startup_app(self) -> None:
        current_row = self.startup_apps_list.currentRow()
        if current_row >= 0:
            self.startup_apps_list.takeItem(current_row)

    def _save_privacy_settings(self) -> None:
        privacy = self.settings_state.setdefault("privacy", {})
        privacy["lock_on_suspend"] = bool(self.privacy_lock_suspend_switch.isChecked())
        privacy["hide_notification_content_global"] = bool(
            self.privacy_hide_content_switch.isChecked()
        )
        privacy["pause_notifications_while_sharing"] = bool(
            self.privacy_pause_share_switch.isChecked()
        )
        privacy["screenshot_guard_enabled"] = bool(
            self.privacy_screenshot_guard_switch.isChecked()
        )
        privacy["screen_share_guard_enabled"] = bool(
            self.privacy_screen_share_guard_switch.isChecked()
        )
        if privacy["hide_notification_content_global"]:
            self.settings_state.setdefault("mail", {})["hide_notification_content"] = (
                True
            )
            self.settings_state.setdefault("ntfy", {})["hide_notification_content"] = (
                True
            )
        save_settings_state(self.settings_state)
        if hasattr(self, "privacy_status"):
            self.privacy_status.setText("Privacy settings saved.")

    def _save_networking_settings(self) -> None:
        networking = self.settings_state.setdefault("networking", {})
        vpn_service = self.settings_state.setdefault("services", {}).setdefault(
            "vpn_control", {}
        )
        networking["preferred_wifi_interface"] = str(
            self.networking_wifi_combo.currentData() or ""
        ).strip()
        networking["wifi_autoconnect"] = bool(
            self.networking_wifi_autoconnect_switch.isChecked()
        )
        preferred_wg = str(self.networking_wg_combo.currentData() or "").strip()
        networking["preferred_wireguard_interface"] = preferred_wg
        networking["vpn_reconnect_on_login"] = bool(
            self.networking_vpn_reconnect_switch.isChecked()
        )
        split_tunnel_apps = [
            item.strip()
            for item in self.networking_split_tunnel_input.text().split(",")
            if item.strip()
        ]
        networking["split_tunnel_apps"] = split_tunnel_apps
        vpn_service["preferred_interface"] = preferred_wg
        vpn_service["reconnect_on_login"] = bool(
            self.networking_vpn_reconnect_switch.isChecked()
        )
        vpn_service["split_tunnel_apps"] = split_tunnel_apps
        save_settings_state(self.settings_state)
        if hasattr(self, "networking_status"):
            self.networking_status.setText("Networking settings saved.")

    def _refresh_storage_metrics(self) -> None:
        fs_total, _fs_used, fs_free = filesystem_usage_bytes(STATE_DIR)
        metrics = {
            "Wallpaper Source Cache": format_bytes(
                directory_size_bytes(WALLPAPER_SOURCE_CACHE_DIR)
            ),
            "Rendered Wallpapers": format_bytes(
                directory_size_bytes(RENDERED_WALLPAPER_DIR)
            ),
            "Mail Attachments": format_bytes(
                directory_size_bytes(MAIL_STATE_DIR / "cache")
            ),
            "State Root": format_bytes(directory_size_bytes(STATE_DIR.parent)),
            "Filesystem Total": format_bytes(fs_total),
            "Filesystem Free": format_bytes(fs_free),
        }
        for key, label in getattr(self, "storage_metrics", {}).items():
            label.setText(metrics.get(key, "0 B"))
        if hasattr(self, "storage_status"):
            self.storage_status.setText("Storage sizes refreshed.")

    def _clear_wallpaper_cache(self) -> None:
        removed = 0
        for path in (WALLPAPER_SOURCE_CACHE_DIR, RENDERED_WALLPAPER_DIR):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        if hasattr(self, "storage_status"):
            self.storage_status.setText(
                f"Cleared {removed} wallpaper cache location(s)."
            )
        self._refresh_storage_metrics()

    def _clear_temp_state(self) -> None:
        state_root = STATE_DIR.parent
        removed = 0
        if state_root.exists():
            for path in state_root.rglob("*"):
                try:
                    if path.is_dir() and path.name == "__pycache__":
                        shutil.rmtree(path, ignore_errors=True)
                        removed += 1
                    elif path.is_file() and path.suffix in {".tmp", ".temp"}:
                        path.unlink(missing_ok=True)
                        removed += 1
                except Exception:
                    continue
        if hasattr(self, "storage_status"):
            self.storage_status.setText(f"Cleaned {removed} temporary state item(s).")
        self._refresh_storage_metrics()

    def _save_storage_settings(self) -> None:
        storage = self.settings_state.setdefault("storage", {})
        try:
            storage["wallpaper_cache_cleanup_days"] = max(
                1,
                min(
                    365,
                    int(self.storage_cache_cleanup_days_input.text().strip() or "30"),
                ),
            )
        except Exception:
            storage["wallpaper_cache_cleanup_days"] = 30
            self.storage_cache_cleanup_days_input.setText("30")
        try:
            storage["log_retention_days"] = max(
                1,
                min(
                    365,
                    int(self.storage_log_retention_days_input.text().strip() or "14"),
                ),
            )
        except Exception:
            storage["log_retention_days"] = 14
            self.storage_log_retention_days_input.setText("14")
        storage["clean_temp_state_on_startup"] = bool(
            self.storage_clean_temp_switch.isChecked()
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "storage_status"):
            self.storage_status.setText("Storage settings saved.")
        self._refresh_storage_metrics()

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

    def _set_notification_rule_enabled(
        self, rule_id: str, enabled: bool, persist: bool = True
    ) -> None:
        rule = self.notification_rules_state["rules"].setdefault(
            rule_id,
            dict(DEFAULT_NOTIFICATION_RULES["rules"].get(rule_id, {})),
        )
        if not self._service_enabled("kdeconnect") and enabled:
            return
        rule["enabled"] = bool(enabled)
        if persist:
            save_notification_rules_state(self.notification_rules_state)
        if hasattr(self, "kdeconnect_rules_status"):
            self.kdeconnect_rules_status.setText(
                "KDE Connect WhatsApp ignore rule enabled."
                if enabled
                else "KDE Connect WhatsApp ignore rule disabled."
            )

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
            return
        command = [python_executable(), str(qcal_wrapper), "discover", url, username, password]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
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

    def _toggle_energy_battery_section(self) -> None:
        if not getattr(self, "_battery_present", False):
            return
        self._set_energy_battery_section_expanded(
            not getattr(self, "_energy_battery_expanded", False)
        )

    def _set_energy_battery_section_expanded(self, expanded: bool) -> None:
        active = bool(getattr(self, "_battery_present", False))
        self._energy_battery_expanded = bool(expanded) and active
        if hasattr(self, "energy_battery_content"):
            self.energy_battery_content.setVisible(self._energy_battery_expanded)
        if hasattr(self, "energy_battery_header"):
            self.energy_battery_header.setEnabled(active)
        if hasattr(self, "energy_battery_chevron"):
            self.energy_battery_chevron.setVisible(active)
            self.energy_battery_chevron.setStyleSheet(
                "color: #F2E7F4; background: transparent;"
                + (
                    "transform: rotate(180deg);"
                    if self._energy_battery_expanded
                    else ""
                )
            )

    def _refresh_energy_state(self) -> None:
        self._battery_snapshot = read_battery_snapshot()
        self._battery_present = self._battery_snapshot is not None
        autolock = self.settings_state.get("autolock", {})
        autolock_enabled = bool(autolock.get("enabled", True))
        autolock_minutes = max(1, min(60, int(autolock.get("timeout_minutes", 2) or 2)))

        if hasattr(self, "autolock_timeout_input"):
            self.autolock_timeout_input.setText(str(autolock_minutes))
            self.autolock_timeout_input.setEnabled(autolock_enabled)

        brightness = run_text(
            [str(ROOT / "hanauta" / "scripts" / "brightness.sh"), "br"]
        )
        try:
            brightness_value = max(1, min(100, int(brightness or "0")))
        except Exception:
            brightness_value = 0
        if hasattr(self, "energy_brightness_input") and brightness_value > 0:
            self.energy_brightness_input.setText(str(brightness_value))

        if hasattr(self, "energy_status"):
            battery_text = (
                "battery detected" if self._battery_present else "no battery detected"
            )
            lock_text = (
                f"auto lock in {autolock_minutes} min"
                if autolock_enabled
                else "auto lock disabled"
            )
            brightness_text = (
                f"brightness {brightness_value}%"
                if brightness_value > 0
                else "brightness unavailable"
            )
            self.energy_status.setText(
                f"{lock_text} • {brightness_text} • {battery_text}."
            )

        if not hasattr(self, "energy_battery_summary"):
            return
        if not self._battery_present:
            self.energy_battery_summary.setText(
                "No battery detected on this PC. Battery controls stay collapsed and inactive."
            )
            self.energy_battery_meta.setText(
                "Connect a laptop battery or UPS-backed battery source if you want battery-specific details here."
            )
            for label in getattr(self, "energy_battery_labels", {}).values():
                label.setText("Unavailable")
            self._set_energy_battery_section_expanded(False)
            return

        snapshot = self._battery_snapshot or {}
        capacity = int(snapshot.get("capacity", 0) or 0)
        status = str(snapshot.get("status", "Unknown") or "Unknown")
        technology = str(snapshot.get("technology", "Unknown") or "Unknown")
        cycle_count = snapshot.get("cycle_count")
        health_percent = snapshot.get("health_percent")
        model_name = str(snapshot.get("model_name", "") or "").strip()
        manufacturer = str(snapshot.get("manufacturer", "") or "").strip()
        self.energy_battery_summary.setText(f"{capacity}% • {status} • {technology}")
        self.energy_battery_labels["Charge"].setText(f"{capacity}%")
        self.energy_battery_labels["State"].setText(status)
        self.energy_battery_labels["Health"].setText(
            f"{health_percent}%" if health_percent is not None else "Unknown"
        )
        self.energy_battery_labels["Cycles"].setText(
            str(cycle_count) if cycle_count is not None else "Unknown"
        )
        meta_parts = [
            part
            for part in (
                manufacturer,
                model_name,
                str(snapshot.get("path", "") or "").strip(),
            )
            if part
        ]
        self.energy_battery_meta.setText(
            " • ".join(meta_parts) if meta_parts else "Battery details are available."
        )
        self._set_energy_battery_section_expanded(
            getattr(self, "_energy_battery_expanded", True)
        )

    def _lock_now(self) -> None:
        if LOCK_SCRIPT.exists():
            run_bg([str(LOCK_SCRIPT)])
            if hasattr(self, "energy_status"):
                self.energy_status.setText("Lock command sent.")
            return
        if hasattr(self, "energy_status"):
            self.energy_status.setText("Lock script is unavailable.")

    def _suspend_now(self) -> None:
        run_bg(["systemctl", "suspend"])
        if hasattr(self, "energy_status"):
            self.energy_status.setText("Suspend command sent.")

    def _hibernate_now(self) -> None:
        run_bg(["systemctl", "hibernate"])
        if hasattr(self, "energy_status"):
            self.energy_status.setText("Hibernate command sent.")

    def _apply_energy_brightness(self) -> None:
        if not hasattr(self, "energy_brightness_input"):
            return
        text = self.energy_brightness_input.text().strip() or "0"
        try:
            value = max(1, min(100, int(text)))
        except Exception:
            value = 50
        self.energy_brightness_input.setText(str(value))
        run_bg([str(ROOT / "hanauta" / "scripts" / "brightness.sh"), "set", str(value)])
        if hasattr(self, "energy_status"):
            self.energy_status.setText(f"Brightness set to {value}%.")

    def _set_region_use_24_hour(self, enabled: bool) -> None:
        self.settings_state.setdefault("region", {})["use_24_hour"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "region_status"):
            self.region_status.setText("Clock format updated.")

    def _set_autolock_enabled(self, enabled: bool) -> None:
        autolock = self.settings_state.setdefault("autolock", {})
        autolock["enabled"] = bool(enabled)
        autolock["timeout_minutes"] = max(
            1, min(60, int(autolock.get("timeout_minutes", 2) or 2))
        )
        if hasattr(self, "autolock_timeout_input"):
            self.autolock_timeout_input.setEnabled(bool(enabled))
        save_settings_state(self.settings_state)
        if hasattr(self, "energy_status"):
            if enabled:
                minutes = int(autolock["timeout_minutes"])
                label = "minute" if minutes == 1 else "minutes"
                self.energy_status.setText(
                    f"Auto lock enabled after {minutes} {label} of idle time unless caffeine is on."
                )
            else:
                self.energy_status.setText("Auto lock disabled.")

    def _set_autolock_timeout_minutes(self, value: int) -> None:
        autolock = self.settings_state.setdefault("autolock", {})
        minutes = max(1, min(60, int(value)))
        autolock["timeout_minutes"] = minutes
        save_settings_state(self.settings_state)
        if hasattr(self, "autolock_timeout_input"):
            self.autolock_timeout_input.setText(str(minutes))
        if hasattr(self, "energy_status"):
            label = "minute" if minutes == 1 else "minutes"
            self.energy_status.setText(f"Auto lock timeout set to {minutes} {label}.")

    def _set_autolock_timeout_minutes_from_input(self) -> None:
        if not hasattr(self, "autolock_timeout_input"):
            return
        text = self.autolock_timeout_input.text().strip() or "2"
        try:
            value = int(text)
        except Exception:
            value = 2
        self._set_autolock_timeout_minutes(value)

    def _set_region_date_style(self, index: int) -> None:
        value = (
            self.region_date_style_combo.itemData(index)
            if hasattr(self, "region_date_style_combo")
            else "us"
        )
        self.settings_state.setdefault("region", {})["date_style"] = str(value or "us")
        save_settings_state(self.settings_state)
        if hasattr(self, "region_status"):
            self.region_status.setText("Date style updated.")

    def _set_region_temperature_unit(self, index: int) -> None:
        value = (
            self.region_temperature_combo.itemData(index)
            if hasattr(self, "region_temperature_combo")
            else "c"
        )
        self.settings_state.setdefault("region", {})["temperature_unit"] = str(
            value or "c"
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "region_status"):
            self.region_status.setText("Temperature unit updated.")

    def _resolve_region_locale_code(self) -> str:
        if hasattr(self, "region_locale_combo"):
            text = str(self.region_locale_combo.currentText()).strip()
            label_map = getattr(self, "_region_locale_label_to_value", {})
            if isinstance(label_map, dict) and text in label_map:
                return str(label_map[text]).strip()
            return text
        return str(getattr(self, "region_locale_input", QLineEdit()).text()).strip()

    def _save_region_settings(self) -> None:
        region = self.settings_state.setdefault("region", {})
        region["locale_code"] = self._resolve_region_locale_code()
        region["keyboard_layout"] = self._resolve_region_keyboard_layout_value()
        input_settings = self.settings_state.setdefault("input", {})
        input_settings["keyboard_layout"] = str(
            region.get("keyboard_layout", "us")
        ).strip() or "us"
        region["use_24_hour"] = bool(self.region_24h_switch.isChecked())
        region["date_style"] = str(self.region_date_style_combo.currentData() or "us")
        region["temperature_unit"] = str(
            self.region_temperature_combo.currentData() or "c"
        )
        save_settings_state(self.settings_state)
        self._apply_keyboard_layout(str(region.get("keyboard_layout", "us")))
        if hasattr(self, "region_status"):
            locale_label = region["locale_code"] or "system default"
            keyboard_label = str(region.get("keyboard_layout", "us")).strip() or "us"
            self.region_status.setText(
                f"Region settings saved for {locale_label} • keyboard {keyboard_label}."
            )

    def _save_bar_settings(self) -> None:
        bar = merged_bar_settings(self.settings_state.get("bar", {}))
        polybar_widgets = []
        for i in range(self.polybar_widgets_list.count()):
            item = self.polybar_widgets_list.item(i)
            if item:
                text = item.text().strip()
                if text:
                    polybar_widgets.append(text)
        bar["polybar_widgets"] = polybar_widgets
        self.settings_state["bar"] = bar
        save_settings_state(self.settings_state)

    def _add_polybar_widget(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Polybar Widget")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        name_input = QLineEdit()
        name_input.setPlaceholderText("Widget name (e.g., my-weather)")
        layout.addWidget(name_input)
        command_input = QLineEdit()
        command_input.setPlaceholderText(
            "Command (e.g., ~/.config/polybar/scripts/weather.sh)"
        )
        layout.addWidget(command_input)
        interval_input = QLineEdit()
        interval_input.setPlaceholderText("Update interval in seconds (default: 30)")
        layout.addWidget(interval_input)
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            command = command_input.text().strip()
            interval = interval_input.text().strip() or "30"
            if name and command:
                widget_str = f"{name}|{command}|{interval}"
                item = QListWidgetItem(widget_str)
                self.polybar_widgets_list.addItem(item)
                self._save_bar_settings()

    def _remove_polybar_widget(self) -> None:
        current_row = self.polybar_widgets_list.currentRow()
        if current_row >= 0:
            self.polybar_widgets_list.takeItem(current_row)
            self._save_bar_settings()

    def _set_bar_launcher_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["launcher_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_workspace_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["workspace_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_datetime_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["datetime_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_workspace_count(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["workspace_count"] = int(value)
        self._save_bar_settings()

    def _set_bar_show_workspace_label(self, enabled: bool) -> None:
        self.settings_state.setdefault("bar", {})["show_workspace_label"] = bool(
            enabled
        )
        self._save_bar_settings()

    def _set_bar_media_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["media_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_status_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["status_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_tray_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["tray_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_status_icon_limit(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["status_icon_limit"] = int(value)
        self._save_bar_settings()

    def _set_bar_height(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["bar_height"] = int(value)
        self._save_bar_settings()

    def _set_bar_chip_radius(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["chip_radius"] = int(value)
        self._save_bar_settings()

    def _set_bar_merge_all_chips(self, enabled: bool) -> None:
        self.settings_state.setdefault("bar", {})["merge_all_chips"] = bool(enabled)
        self._save_bar_settings()

    def _set_bar_tray_tint_with_matugen(self, enabled: bool) -> None:
        self.settings_state.setdefault("bar", {})["tray_tint_with_matugen"] = bool(
            enabled
        )
        self._save_bar_settings()

    def _set_bar_use_color_widget_icons(self, enabled: bool) -> None:
        self.settings_state.setdefault("bar", {})["use_color_widget_icons"] = bool(
            enabled
        )
        self._save_bar_settings()

    def _set_bar_debug_tooltips(self, enabled: bool) -> None:
        self.settings_state.setdefault("bar", {})["debug_tooltips"] = bool(enabled)
        self._save_bar_settings()

    def _set_bar_orientation_mode(self, index: int) -> None:
        if not hasattr(self, "bar_orientation_combo"):
            return
        value = str(self.bar_orientation_combo.itemData(index) or "").strip().lower()
        if value not in {"horizontal_top", "vertical_left", "vertical_right"}:
            value = "horizontal_top"
        self.settings_state.setdefault("bar", {})["orientation_mode"] = value
        self._save_bar_settings()

    def _set_bar_monitor_target(self, index: int) -> None:
        if not hasattr(self, "bar_monitor_target_combo"):
            return
        payload = self.bar_monitor_target_combo.itemData(index)
        if not isinstance(payload, dict):
            return
        bar_settings = self.settings_state.setdefault("bar", {})
        bar_settings["monitor_mode"] = str(payload.get("mode", "primary")).strip()
        bar_settings["monitor_name"] = str(payload.get("name", "")).strip()
        self._save_bar_settings()

    def _set_dock_monitor_target(self, index: int) -> None:
        if not hasattr(self, "dock_monitor_target_combo"):
            return
        payload = self.dock_monitor_target_combo.itemData(index)
        if not isinstance(payload, dict):
            return
        dock_settings = self.dock_settings_state.setdefault("dock", {})
        dock_settings["monitor_mode"] = str(payload.get("mode", "primary")).strip()
        dock_settings["monitor_name"] = str(payload.get("name", "")).strip()
        save_dock_settings_state(self.dock_settings_state)

    def _set_bar_full_radius(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["full_bar_radius"] = int(value)
        self._save_bar_settings()

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

    def _make_transparency_switch(self) -> SwitchButton:
        switch = SwitchButton(
            bool(self.settings_state["appearance"].get("transparency", True))
        )
        switch.toggledValue.connect(self._set_transparency)
        return switch

    def _make_matugen_switch(self) -> SwitchButton:
        switch = SwitchButton(
            bool(self.settings_state["appearance"].get("use_matugen_palette", False))
        )
        switch.toggledValue.connect(self._set_use_matugen_palette)
        self.matugen_palette_switch = switch
        return switch

    def _set_transparency(self, enabled: bool) -> None:
        self.settings_state["appearance"]["transparency"] = bool(enabled)
        save_settings_state(self.settings_state)
        self._apply_styles()

    def _set_notification_center_panel_opacity(self, value: int) -> None:
        panel_opacity = max(35, min(100, int(value)))
        appearance = self.settings_state["appearance"]
        appearance["notification_center_panel_opacity"] = panel_opacity
        current_card = int(appearance.get("notification_center_card_opacity", 92))
        if current_card < panel_opacity:
            appearance["notification_center_card_opacity"] = panel_opacity
            if hasattr(self, "notification_center_card_opacity_slider"):
                self.notification_center_card_opacity_slider.blockSignals(True)
                self.notification_center_card_opacity_slider.setValue(panel_opacity)
                self.notification_center_card_opacity_slider.blockSignals(False)
            if hasattr(self, "notification_center_card_opacity_label"):
                self.notification_center_card_opacity_label.setText(str(panel_opacity))
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                f"Control center shell opacity set to {panel_opacity}%."
            )

    def _set_notification_center_card_opacity(self, value: int) -> None:
        panel_opacity = int(
            self.settings_state["appearance"].get(
                "notification_center_panel_opacity", 84
            )
        )
        card_opacity = max(panel_opacity, min(100, int(value)))
        self.settings_state["appearance"]["notification_center_card_opacity"] = (
            card_opacity
        )
        if card_opacity != int(value):
            if hasattr(self, "notification_center_card_opacity_slider"):
                self.notification_center_card_opacity_slider.blockSignals(True)
                self.notification_center_card_opacity_slider.setValue(card_opacity)
                self.notification_center_card_opacity_slider.blockSignals(False)
            if hasattr(self, "notification_center_card_opacity_label"):
                self.notification_center_card_opacity_label.setText(str(card_opacity))
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                f"Control center widget opacity set to {card_opacity}%."
            )

    def _set_notification_toast_max_width(self, value: int) -> None:
        toast_width = max(260, min(640, int(value)))
        self.settings_state["appearance"]["notification_toast_max_width"] = toast_width
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                f"Notification width limit set to {toast_width}px."
            )

    def _set_notification_toast_max_height(self, value: int) -> None:
        toast_height = max(160, min(640, int(value)))
        self.settings_state["appearance"]["notification_toast_max_height"] = (
            toast_height
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                f"Notification height limit set to {toast_height}px."
            )

    def _set_use_matugen_palette(self, enabled: bool) -> None:
        self.settings_state["appearance"]["use_matugen_palette"] = bool(enabled)
        if enabled:
            self.settings_state["appearance"]["theme_choice"] = "wallpaper_aware"
        else:
            current_choice = (
                str(self.settings_state["appearance"].get("theme_choice", "dark"))
                .strip()
                .lower()
            )
            if current_choice == "wallpaper_aware":
                fallback_mode = (
                    str(self.settings_state["appearance"].get("theme_mode", "dark"))
                    .strip()
                    .lower()
                )
                self.settings_state["appearance"]["theme_choice"] = (
                    fallback_mode
                    if fallback_mode in {"light", "dark", "custom"}
                    else "dark"
                )
        save_settings_state(self.settings_state)
        if enabled:
            self._apply_matugen_palette()
            self.theme_palette = load_theme_palette()
            self._theme_mtime = palette_mtime()
            self._refresh_current_accent()
            self._apply_styles()
            self._sync_accent_controls()
            return
        write_default_pyqt_palette(use_matugen=False)
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._refresh_current_accent()
        self._apply_styles()
        self._sync_accent_controls()

    def _set_matugen_notifications_enabled(self, enabled: bool) -> None:
        self.settings_state["appearance"]["matugen_notifications_enabled"] = bool(
            enabled
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                "Matugen notifications enabled."
                if enabled
                else "Matugen notifications disabled."
            )

    def _set_wallpaper_change_notifications_enabled(self, enabled: bool) -> None:
        self.settings_state["appearance"]["wallpaper_change_notifications_enabled"] = (
            bool(enabled)
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                "Wallpaper change notifications enabled."
                if enabled
                else "Wallpaper change notifications disabled."
            )

    def _set_theme_choice(self, choice: str) -> None:
        choice = str(choice).strip().lower()
        if choice not in THEME_CHOICES:
            return
        self.settings_state["appearance"]["theme_choice"] = choice
        if choice == "wallpaper_aware":
            self.settings_state["appearance"]["use_matugen_palette"] = True
            save_settings_state(self.settings_state)
            self._apply_matugen_palette(force=True)
            self.theme_palette = load_theme_palette()
            self._theme_mtime = palette_mtime()
            self._refresh_current_accent()
            self._apply_styles()
            self._sync_accent_controls()
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText(
                    "Wallpaper aware mode is active. Hanauta will refresh colors from the current wallpaper."
                )
            return
        if choice == "custom":
            self.settings_state["appearance"]["theme_mode"] = "dark"
            self.settings_state["appearance"]["use_matugen_palette"] = False
            save_settings_state(self.settings_state)
            sync_static_theme_from_settings(self.settings_state, apply_gtk=True)
            self.theme_palette = load_theme_palette()
            self._theme_mtime = palette_mtime()
            self._refresh_current_accent()
            self._apply_styles()
            self._sync_accent_controls()
            self._ensure_system_theme_copy(selected_theme_key(self.settings_state))
            if self._restart_if_theme_fonts_changed():
                return
            if hasattr(self, "appearance_status"):
                label = THEME_LIBRARY[selected_theme_key(self.settings_state)]["label"]
                self.appearance_status.setText(f"Custom theme selected: {label}.")
            return
        self.settings_state["appearance"]["theme_mode"] = choice
        self.settings_state["appearance"]["use_matugen_palette"] = False
        save_settings_state(self.settings_state)
        sync_static_theme_from_settings(self.settings_state, apply_gtk=True)
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._refresh_current_accent()
        self._apply_styles()
        self._sync_accent_controls()
        self._ensure_system_theme_copy(selected_theme_key(self.settings_state))
        if self._restart_if_theme_fonts_changed():
            return
        if hasattr(self, "appearance_status"):
            labels = {
                "light": "Light mode selected.",
                "dark": "Dark mode selected.",
                "custom": "Custom theme mode selected. Theme selection will land here next.",
            }
            self.appearance_status.setText(labels.get(choice, "Theme mode updated."))

    def _set_custom_theme(self, theme_id: str) -> None:
        theme_id = str(theme_id).strip().lower()
        if theme_id not in CUSTOM_THEME_KEYS:
            return
        self.settings_state["appearance"]["custom_theme_id"] = theme_id
        self.settings_state["appearance"]["theme_choice"] = "custom"
        self.settings_state["appearance"]["use_matugen_palette"] = False
        save_settings_state(self.settings_state)
        sync_static_theme_from_settings(self.settings_state, apply_gtk=True)
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._refresh_current_accent()
        self._apply_styles()
        self._sync_accent_controls()
        self._ensure_system_theme_copy(theme_id)
        if self._restart_if_theme_fonts_changed():
            return
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                f"Custom theme applied: {THEME_LIBRARY[theme_id]['label']}."
            )

    def _ensure_system_theme_copy(self, theme_key: str) -> None:
        theme_key = str(theme_key).strip().lower()
        metadata = THEME_LIBRARY.get(theme_key)
        if not metadata:
            return
        theme_name = str(metadata.get("gtk_theme", "")).strip()
        if not theme_name:
            return
        if (SYSTEM_THEMES_HOME / theme_name).exists():
            return
        if theme_name in getattr(self, "_system_theme_install_declined", set()):
            return
        source_dir = THEMES_HOME / theme_name
        if not source_dir.exists():
            return
        if not SYSTEM_THEME_INSTALL_SCRIPT.exists():
            return
        if shutil.which("pkexec") is None:
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText(
                    f"{metadata['label']} is installed only for this user. Install pkexec or copy it into /usr/share/themes for apps like Thunar."
                )
            return
        result = subprocess.run(
            [
                "pkexec",
                "bash",
                str(SYSTEM_THEME_INSTALL_SCRIPT),
                theme_name,
                str(source_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText(
                    f"{metadata['label']} is now available in /usr/share/themes for apps that require a system theme install."
                )
            return
        self._system_theme_install_declined.add(theme_name)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                f"{metadata['label']} is active for this user. System-wide installation was skipped."
            )

    def _set_theme_mode(self, mode: str) -> None:
        self.settings_state["appearance"]["theme_mode"] = mode
        self.settings_state["appearance"]["theme_choice"] = (
            mode if mode in {"light", "dark", "custom"} else "dark"
        )
        self.settings_state["appearance"]["use_matugen_palette"] = False
        save_settings_state(self.settings_state)
        sync_static_theme_from_settings(self.settings_state, apply_gtk=False)
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._sync_accent_controls()
        self._apply_styles()

    def _set_accent(self, key: str) -> None:
        key = {"auto": "orchid"}.get(key, key)
        self.settings_state["appearance"]["accent"] = key
        save_settings_state(self.settings_state)
        self._sync_accent_controls()
        self._apply_styles()

    def _sync_accent_controls(self) -> None:
        accent = self.settings_state["appearance"].get("accent", "orchid")
        for key, chip in getattr(self, "accent_chips", {}).items():
            chip.setChecked(key == accent or (key == "auto" and accent == "orchid"))
        theme_mode = (
            str(self.settings_state["appearance"].get("theme_choice", ""))
            .strip()
            .lower()
        )
        if theme_mode not in THEME_CHOICES:
            theme_mode = (
                "wallpaper_aware"
                if self.settings_state["appearance"].get("use_matugen_palette", False)
                else str(self.settings_state["appearance"].get("theme_mode", "dark"))
                .strip()
                .lower()
            )
        if theme_mode not in THEME_CHOICES:
            theme_mode = "dark"
        for key, button in getattr(self, "theme_buttons", {}).items():
            button.setChecked(key == theme_mode)
        custom_theme_id = (
            str(self.settings_state["appearance"].get("custom_theme_id", "retrowave"))
            .strip()
            .lower()
        )
        for key, button in getattr(self, "custom_theme_buttons", {}).items():
            button.setChecked(key == custom_theme_id)
        custom_visible = theme_mode == "custom"
        if hasattr(self, "custom_theme_heading"):
            self.custom_theme_heading.setVisible(custom_visible)
        if hasattr(self, "custom_theme_wrap"):
            self.custom_theme_wrap.setVisible(custom_visible)
        if hasattr(self, "custom_theme_hint"):
            self.custom_theme_hint.setVisible(custom_visible)
        self._refresh_current_accent()

    def _refresh_current_accent(self) -> None:
        accent = self.settings_state["appearance"].get("accent", "orchid")
        self.current_accent = accent_palette(accent)
        theme_choice = (
            str(self.settings_state["appearance"].get("theme_choice", "dark"))
            .strip()
            .lower()
        )
        if self.theme_palette.use_matugen or theme_choice == "custom":
            self.current_accent = {
                "accent": self.theme_palette.primary,
                "on_accent": self.theme_palette.active_text,
                "soft": self.theme_palette.accent_soft,
            }

    def _current_theme_font_signature(self) -> tuple[str, str, str]:
        return (
            theme_font_family("ui"),
            theme_font_family("display"),
            theme_font_family("mono"),
        )

    def _restart_for_theme_refresh(self) -> None:
        if self._theme_refresh_restart_pending:
            return
        self._theme_refresh_restart_pending = True
        page = getattr(self, "current_page", self.initial_page or "appearance")
        command = [
            python_executable(),
            str(Path(__file__).resolve()),
            "--page",
            str(page or "appearance"),
        ]
        if page == "services" and self.initial_service_section:
            command.extend(["--service-section", str(self.initial_service_section)])
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        QTimer.singleShot(0, self.close)

    def _restart_if_theme_fonts_changed(self) -> bool:
        new_signature = self._current_theme_font_signature()
        if new_signature == getattr(self, "_theme_font_signature", ("", "", "")):
            return False
        self._theme_font_signature = new_signature
        self._restart_for_theme_refresh()
        return True

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme_palette = load_theme_palette()
        self._refresh_current_accent()
        if self._restart_if_theme_fonts_changed():
            return
        self._apply_styles()

    def _sync_wallpaper_controls(self) -> None:
        if hasattr(self, "preview_card"):
            self.preview_card.update_wallpaper(self.wallpaper)

    def _save_appearance_state(self) -> None:
        self.settings_state["appearance"]["wallpaper_path"] = str(self.wallpaper)
        save_settings_state(self.settings_state)
        self._sync_wallpaper_controls()

    def _sync_wallpaper_source(self, source_key: str) -> None:
        if getattr(self, "_wallpaper_sync_worker", None) is not None:
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText("Wallpaper sync is already running.")
            return
        if hasattr(self, "appearance_status"):
            preset = WALLPAPER_SOURCE_PRESETS.get(source_key, {})
            source_label = str(preset.get("label", "community source"))
            self.appearance_status.setText(f"Syncing wallpapers from {source_label}...")
        if hasattr(self, "wallpaper_sync_progress"):
            self.wallpaper_sync_progress.show()
        for button_name in (
            "sync_caelestia_button",
            "sync_end4_button",
            "sync_catholic_button",
        ):
            button = getattr(self, button_name, None)
            if isinstance(button, QPushButton):
                button.setEnabled(False)
        self._wallpaper_sync_worker = WallpaperSourceSyncWorker(source_key)
        self._wallpaper_sync_worker.finished_sync.connect(
            self._finish_wallpaper_source_sync
        )
        self._wallpaper_sync_worker.finished.connect(
            self._cleanup_wallpaper_source_worker
        )
        self._wallpaper_sync_worker.start()

    def _finish_wallpaper_source_sync(
        self, _source_key: str, ok: bool, message: str, folder_obj: object
    ) -> None:
        folder = folder_obj if isinstance(folder_obj, Path) else None
        if not ok or folder is None:
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText(message)
            return
        self.settings_state["appearance"]["slideshow_folder"] = str(folder)
        self.settings_state["appearance"]["wallpaper_mode"] = "slideshow"
        save_settings_state(self.settings_state)
        self._sync_wallpaper_controls()
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                f"{message} Slideshow folder now points to {folder}."
            )

    def _cleanup_wallpaper_source_worker(self) -> None:
        if hasattr(self, "wallpaper_sync_progress"):
            self.wallpaper_sync_progress.hide()
        for button_name in (
            "sync_caelestia_button",
            "sync_end4_button",
            "sync_catholic_button",
        ):
            button = getattr(self, button_name, None)
            if isinstance(button, QPushButton):
                button.setEnabled(True)
        worker = getattr(self, "_wallpaper_sync_worker", None)
        if worker is not None:
            worker.deleteLater()
        self._wallpaper_sync_worker = None

    def _apply_matugen_palette(self, force: bool = False) -> None:
        wallpaper_path = (
            self.wallpaper
            if self.wallpaper.exists() and self.wallpaper.is_file()
            else self._pick_wallpaper()
        )
        if not wallpaper_path.exists() or not wallpaper_path.is_file():
            return
        if force and not self.settings_state["appearance"].get(
            "use_matugen_palette", False
        ):
            self.settings_state["appearance"]["use_matugen_palette"] = True
            self.settings_state["appearance"]["theme_choice"] = "wallpaper_aware"
            save_settings_state(self.settings_state)
            if hasattr(self, "matugen_palette_switch"):
                self.matugen_palette_switch.setChecked(True)
                self.matugen_palette_switch._apply_state()
        if not self.settings_state["appearance"].get("use_matugen_palette", False):
            sync_static_theme_from_settings(self.settings_state, apply_gtk=False)
            return
        if MATUGEN_SCRIPT.exists():
            run_bg([str(MATUGEN_SCRIPT), str(wallpaper_path)])

    def _wallpaper_mode_for_output(self, output_name: str) -> str:
        fit_modes = self.settings_state["appearance"].get("wallpaper_fit_modes", {})
        if not isinstance(fit_modes, dict):
            return "fill"
        return str(fit_modes.get(output_name, "fill"))

    def _apply_current_wallpaper_layout(self) -> None:
        if not self.wallpaper.exists() or not self.wallpaper.is_file():
            return
        active_displays = [
            display for display in parse_xrandr_state() if display.get("enabled")
        ]
        if not active_displays:
            if WALLPAPER_SCRIPT.exists():
                run_bg([str(WALLPAPER_SCRIPT), str(self.wallpaper)])
            else:
                run_bg(["feh", "--bg-fill", str(self.wallpaper)])
            return
        rendered = self._render_wallpaper_variants(self.wallpaper, active_displays)
        if rendered:
            run_bg(["feh", "--bg-fill", *[str(path) for path in rendered]])
        elif WALLPAPER_SCRIPT.exists():
            run_bg([str(WALLPAPER_SCRIPT), str(self.wallpaper)])
        else:
            run_bg(["feh", "--bg-fill", str(self.wallpaper)])

    def _render_wallpaper_variants(
        self, path: Path, displays: list[dict]
    ) -> list[Path]:
        source = QImage(str(path))
        if source.isNull():
            return []
        RENDERED_WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
        rendered_paths: list[Path] = []
        for display in displays:
            mode_text = display.get("current_mode", "")
            if "x" not in mode_text:
                continue
            try:
                width_text, height_text = mode_text.split("x", 1)
                width = int(width_text)
                height = int(height_text)
            except Exception:
                continue
            canvas = QImage(width, height, QImage.Format.Format_RGB32)
            canvas.fill(QColor("#0E0C12"))
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            draw_wallpaper_mode(
                painter,
                source,
                width,
                height,
                self._wallpaper_mode_for_output(str(display.get("name", ""))),
            )
            painter.end()
            target = (
                RENDERED_WALLPAPER_DIR
                / f"{sanitize_output_name(str(display.get('name', 'display')))}.png"
            )
            canvas.save(str(target), "PNG")
            rendered_paths.append(target)
        return rendered_paths

    def _apply_wallpaper(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return
        self.wallpaper = path
        self._apply_current_wallpaper_layout()
        self._apply_matugen_palette()
        self.settings_state["appearance"]["wallpaper_mode"] = "picture"
        self.settings_state["appearance"]["slideshow_enabled"] = False
        self._slideshow_timer.stop()
        self._save_appearance_state()

    def _apply_random_wallpaper(self) -> None:
        folder = Path(
            self.settings_state["appearance"].get("slideshow_folder", str(WALLS_DIR))
        ).expanduser()
        choices = wallpaper_candidates(folder)
        if not choices:
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText(
                    "No images found in the current slideshow folder."
                )
            return
        choice = random.choice(choices)
        self._apply_wallpaper(choice)

    def _choose_wallpaper_file(self) -> None:
        selected = run_text(
            [
                "zenity",
                "--file-selection",
                "--title=Choose Wallpaper",
                "--file-filter=Images | *.png *.jpg *.jpeg *.webp *.bmp",
            ]
        )
        if not selected:
            return
        self._apply_wallpaper(Path(selected).expanduser())

    def _choose_wallpaper_folder(self) -> None:
        selected = run_text(
            [
                "zenity",
                "--file-selection",
                "--directory",
                "--title=Choose Slideshow Folder",
            ]
        )
        if not selected:
            return
        self.settings_state["appearance"]["slideshow_folder"] = str(
            Path(selected).expanduser()
        )
        self.settings_state["appearance"]["wallpaper_mode"] = "slideshow"
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                f"Slideshow folder updated to {Path(selected).expanduser()}."
            )

    def _set_slideshow_interval(self, value: int) -> None:
        self.settings_state["appearance"]["slideshow_interval"] = int(value)
        self.settings_state["appearance"]["local_randomizer_interval_seconds"] = int(
            value
        )
        save_settings_state(self.settings_state)
        self._slideshow_timer.setInterval(int(value) * 1000)
        if hasattr(self, "slideshow_interval_label"):
            self.slideshow_interval_label.setText(
                self._format_slideshow_interval_text(int(value))
            )

    def _toggle_slideshow(self) -> None:
        if self._slideshow_timer.isActive():
            self._slideshow_timer.stop()
            self.settings_state["appearance"]["slideshow_enabled"] = False
            save_settings_state(self.settings_state)
            self._sync_wallpaper_controls()
            return
        folder = Path(
            self.settings_state["appearance"].get("slideshow_folder", str(WALLS_DIR))
        ).expanduser()
        choices = wallpaper_candidates(folder)
        if not choices:
            return
        self.settings_state["appearance"]["wallpaper_mode"] = "slideshow"
        self.settings_state["appearance"]["slideshow_enabled"] = True
        self._slideshow_timer.setInterval(
            max(5, int(self.settings_state["appearance"].get("slideshow_interval", 30)))
            * 1000
        )
        save_settings_state(self.settings_state)
        self._advance_slideshow()
        self._slideshow_timer.start()
        self._sync_wallpaper_controls()

    def _advance_slideshow(self) -> None:
        if fullscreen_window_active():
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText(
                    "Slideshow is waiting for fullscreen content to close before rotating."
                )
            return
        folder = Path(
            self.settings_state["appearance"].get("slideshow_folder", str(WALLS_DIR))
        ).expanduser()
        choices = wallpaper_candidates(folder)
        if not choices:
            self._slideshow_timer.stop()
            self.settings_state["appearance"]["slideshow_enabled"] = False
            save_settings_state(self.settings_state)
            self._sync_wallpaper_controls()
            return
        self._slideshow_index = (self._slideshow_index + 1) % len(choices)
        self.wallpaper = choices[self._slideshow_index]
        self._apply_current_wallpaper_layout()
        self._apply_matugen_palette()
        self._save_appearance_state()

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

    def _refresh_system_overview(self) -> None:
        session = (
            os.environ.get("XDG_SESSION_DESKTOP")
            or os.environ.get("DESKTOP_SESSION")
            or "unknown"
        )
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            screen_text = "Unavailable"
        else:
            geo = screen.geometry()
            screen_text = f"{geo.width()}x{geo.height()}"
        uptime_seconds = 0
        try:
            uptime_seconds = int(
                float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
            )
        except Exception:
            uptime_seconds = 0
        values = {
            "Host": platform.node() or "unknown",
            "Kernel": platform.release() or "unknown",
            "Session": session,
            "Python": platform.python_version(),
            "Uptime": format_uptime(uptime_seconds),
            "Screen": screen_text,
        }
        for key, label in getattr(self, "system_overview_labels", {}).items():
            label.setText(values.get(key, "..."))

    def _current_picom_values(self) -> dict[str, object]:
        return {
            "backend": self.picom_backend_combo.currentText(),
            "vsync": self.picom_vsync_switch.isChecked(),
            "use-damage": self.picom_damage_switch.isChecked(),
            "shadow": self.picom_shadow_switch.isChecked(),
            "shadow-radius": self.picom_shadow_radius_slider.value(),
            "shadow-opacity": self.picom_shadow_opacity_slider.value() / 100.0,
            "shadow-offset-x": self.picom_shadow_offset_x_slider.value(),
            "shadow-offset-y": self.picom_shadow_offset_y_slider.value(),
            "fading": self.picom_fading_switch.isChecked(),
            "active-opacity": self.picom_active_opacity_slider.value() / 100.0,
            "inactive-opacity": self.picom_inactive_opacity_slider.value() / 100.0,
            "corner-radius": self.picom_corner_radius_slider.value(),
            "transparent-clipping": self.picom_clip_switch.isChecked(),
            "detect-rounded-corners": self.picom_rounded_switch.isChecked(),
        }

    def _apply_picom_settings(self) -> None:
        values = self._current_picom_values()
        text = sync_picom_rule_blocks(update_picom_config(read_picom_text(), values))
        try:
            PICOM_CONFIG_FILE.write_text(text, encoding="utf-8")
        except Exception as exc:
            self.picom_status.setText(f"Unable to write picom.conf: {exc}")
            return
        self.picom_state = dict(values)
        self.picom_status.setText(
            f"picom.conf updated. Exception files live in {PICOM_RULES_DIR}. Restart picom to apply immediately."
        )

    def _open_picom_rule_dir(self) -> None:
        ensure_picom_rule_files()
        run_bg(["xdg-open", str(PICOM_RULES_DIR)])
        self.picom_status.setText(f"Opened picom rule files in {PICOM_RULES_DIR}.")

    def _restart_picom(self) -> None:
        try:
            PICOM_CONFIG_FILE.write_text(
                sync_picom_rule_blocks(read_picom_text()), encoding="utf-8"
            )
        except Exception as exc:
            self.picom_status.setText(f"Unable to sync picom rule files: {exc}")
            return
        subprocess.run(
            ["pkill", "-x", "picom"], capture_output=True, text=True, check=False
        )
        result = subprocess.run(
            ["picom", "--config", str(PICOM_CONFIG_FILE), "--daemon"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.picom_status.setText(
                (result.stderr or result.stdout or "Unable to restart picom.").strip()
            )
            return
        self.picom_status.setText("Picom restarted with the current configuration.")

    def _reset_picom_defaults(self) -> None:
        try:
            ensure_picom_rule_files()
            PICOM_CONFIG_FILE.write_text(build_default_picom_config(), encoding="utf-8")
        except Exception as exc:
            self.picom_status.setText(f"Unable to reset picom.conf: {exc}")
            return
        self.picom_state = parse_picom_settings(build_default_picom_config())
        self._sync_picom_controls()
        self.picom_status.setText(
            f"picom.conf restored to the default profile. Rule files are in {PICOM_RULES_DIR}."
        )

    def _sync_picom_controls(self) -> None:
        self.picom_backend_combo.setCurrentText(
            str(self.picom_state.get("backend", "glx"))
        )
        for switch, value in (
            (self.picom_vsync_switch, bool(self.picom_state.get("vsync", True))),
            (self.picom_damage_switch, bool(self.picom_state.get("use-damage", True))),
            (self.picom_shadow_switch, bool(self.picom_state.get("shadow", True))),
            (self.picom_fading_switch, bool(self.picom_state.get("fading", False))),
            (
                self.picom_clip_switch,
                bool(self.picom_state.get("transparent-clipping", False)),
            ),
            (
                self.picom_rounded_switch,
                bool(self.picom_state.get("detect-rounded-corners", True)),
            ),
        ):
            switch.setChecked(value)
            switch._apply_state()
        for name, value in (
            (
                "picom_shadow_radius_slider",
                int(self.picom_state.get("shadow-radius", 18)),
            ),
            (
                "picom_shadow_opacity_slider",
                int(float(self.picom_state.get("shadow-opacity", 0.18)) * 100),
            ),
            (
                "picom_shadow_offset_x_slider",
                int(self.picom_state.get("shadow-offset-x", -12)),
            ),
            (
                "picom_shadow_offset_y_slider",
                int(self.picom_state.get("shadow-offset-y", -12)),
            ),
            (
                "picom_active_opacity_slider",
                int(float(self.picom_state.get("active-opacity", 1.0)) * 100),
            ),
            (
                "picom_inactive_opacity_slider",
                int(float(self.picom_state.get("inactive-opacity", 1.0)) * 100),
            ),
            (
                "picom_corner_radius_slider",
                int(self.picom_state.get("corner-radius", 18)),
            ),
        ):
            slider = getattr(self, name, None)
            if isinstance(slider, QSlider):
                slider.setValue(value)

    def _center_rect(self) -> QRect:
        screen = QGuiApplication.primaryScreen() or self.screen()
        if screen is None:
            return QRect(0, 0, self.width(), self.height())
        available = screen.availableGeometry()
        x = available.x() + (available.width() - self.width()) // 2
        y = available.y() + (available.height() - self.height()) // 2
        return QRect(x, y, self.width(), self.height())

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        target = self._center_rect()
        start = QRect(
            target.x(),
            target.y() + 24,
            int(target.width() * 0.96),
            int(target.height() * 0.96),
        )
        self.setGeometry(start)
        QTimer.singleShot(80, self._apply_i3_window_rules)
        opacity = QPropertyAnimation(self, b"windowOpacity", self)
        opacity.setDuration(240)
        opacity.setStartValue(0.0)
        opacity.setEndValue(1.0)
        opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
        geometry = QPropertyAnimation(self, b"geometry", self)
        geometry.setDuration(320)
        geometry.setStartValue(start)
        geometry.setEndValue(target)
        geometry.setEasingCurve(QEasingCurve.Type.OutBack)
        self._window_animation = QParallelAnimationGroup(self)
        self._window_animation.addAnimation(opacity)
        self._window_animation.addAnimation(geometry)
        self._window_animation.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(rgba(self.theme_palette.outline, 0.22)), 1))
        painter.setBrush(QColor(rgba(self.theme_palette.surface, 0.96)))
        painter.drawRoundedRect(rect, 20, 20)

    def _apply_i3_window_rules(self) -> None:
        target = self._center_rect()
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="Hanauta Settings"]',
                    (
                        "floating enable, move position "
                        f"{target.x()} px {target.y()} px, "
                        f"resize set {target.width()} px {target.height()} px"
                    ),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

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
            QFrame#appearanceCard {{
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
            }}
            QPushButton#actionCard {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 14px;
                color: {theme.text};
                text-align: left;
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

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--page",
        choices=(
            "overview",
            "appearance",
            "marketplace",
            "display",
            "energy",
            "audio",
            "notifications",
            "input",
            "startup",
            "privacy",
            "networking",
            "storage",
            "region",
            "bar",
            "services",
            "picom",
        ),
        default="appearance",
    )
    parser.add_argument("--service-section", default="")
    parser.add_argument("--ensure-settings", action="store_true")
    parser.add_argument("--restore-displays", action="store_true")
    parser.add_argument("--restore-wallpaper", action="store_true")
    parser.add_argument("--restore-vpn", action="store_true")
    parser.add_argument("--marketplace-refresh-catalog", action="store_true")
    parser.add_argument("--marketplace-update-all", action="store_true")
    parser.add_argument("--marketplace-update-plugin", default="")
    parser.add_argument("--marketplace-list-installed", action="store_true")
    parser.add_argument("--marketplace-list-catalog", action="store_true")
    args, _ = parser.parse_known_args(argv if argv is not None else sys.argv[1:])
    if args.ensure_settings:
        ensure_settings_state()
        return 0
    if args.restore_displays:
        restore_saved_displays()
        return 0
    if args.restore_wallpaper:
        restore_saved_wallpaper()
        return 0
    if args.restore_vpn:
        restore_saved_vpn()
        return 0
    if (
        args.marketplace_refresh_catalog
        or args.marketplace_update_all
        or str(args.marketplace_update_plugin).strip()
        or args.marketplace_list_installed
        or args.marketplace_list_catalog
    ):
        settings = load_settings_state()
        if args.marketplace_refresh_catalog:
            catalog, errors = marketplace_api_refresh_catalog_cache(settings)
            print(f"catalog entries: {len(catalog)}")
            if errors:
                print("catalog errors:")
                for row in errors:
                    print(f"- {row}")
        if args.marketplace_list_catalog:
            catalog_rows = (
                settings.get("marketplace", {}).get("catalog_cache", [])
                if isinstance(settings, dict)
                else []
            )
            if not isinstance(catalog_rows, list):
                catalog_rows = []
            for row in catalog_rows:
                if not isinstance(row, dict):
                    continue
                plugin_id = str(row.get("id", "")).strip()
                name = str(row.get("name", plugin_id)).strip() or plugin_id
                repo = str(row.get("repo", "")).strip()
                print(f"{plugin_id}\t{name}\t{repo}")
        if args.marketplace_list_installed:
            for row in marketplace_api_installed_plugins(settings):
                plugin_id = str(row.get("id", "")).strip()
                name = str(row.get("name", plugin_id)).strip() or plugin_id
                path = str(row.get("install_path", "")).strip()
                print(f"{plugin_id}\t{name}\t{path}")
        update_one = str(args.marketplace_update_plugin).strip()
        if update_one:
            ok, detail = marketplace_api_update_plugin(settings, update_one)
            print(detail)
            if not ok:
                return 1
        if args.marketplace_update_all:
            results = marketplace_api_update_all_plugins(settings)
            failures = 0
            for plugin_id, ok, detail in results:
                print(detail)
                if not ok:
                    failures += 1
            print(f"updated plugins: {len(results)} (failures: {failures})")
            return 1 if failures > 0 else 0
        return 0
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)
    window = SettingsWindow(
        initial_page=args.page, initial_service_section=str(args.service_section or "")
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
