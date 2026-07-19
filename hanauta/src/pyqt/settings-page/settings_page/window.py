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
from settings_page.window_mixins.services import ServicesMixin
from settings_page.window_mixins.marketplace import MarketplaceMixin
from settings_page.window_mixins.mail import MailMixin
from settings_page.window_mixins.appearance import AppearanceMixin
from settings_page.window_mixins.bar import BarMixin
from settings_page.window_mixins.region import RegionMixin
from settings_page.window_mixins.system import SystemPagesMixin
from settings_page.window_mixins.styles import StylesMixin
from settings_page.window_mixins.setters import SettersMixin


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






class SettingsWindow(
    QWidget,
    ServicesMixin,
    MarketplaceMixin,
    MailMixin,
    AppearanceMixin,
    BarMixin,
    RegionMixin,
    SystemPagesMixin,
    StylesMixin,
    SettersMixin,
):
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
        # Prefer application-loaded Material families directly for nav/menu glyphs.
        # `detect_font(...exactMatch...)` can fall through on some systems even after
        # QFontDatabase.addApplicationFont succeeds, which leaves icon labels as tofu.
        self.icon_font = (
            self.fonts.get("material_symbols_rounded")
            or self.fonts.get("material_icons")
            or self.fonts.get("material_icons_outlined")
            or detect_font(
                "Material Symbols Rounded",
                "Material Icons",
            )
        )

        self.settings_state = load_settings_state()
        self.plugin_service_builders: dict[str, dict[str, object]] = {}
        self._plugin_builders_loaded = False
        self._plugin_dir_scan_in_progress = False
        self._plugin_dirs_to_scan: list[Path] = []
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
        self.resize(1060, 620)
        self.setMinimumSize(980, 560)
        self.setMaximumHeight(680)
        self.setWindowOpacity(0.0)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(8, 5, 10, 150))
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("shell")
        shell.setStyleSheet("#shell { border-radius: 18px; background: rgba(31, 22, 38, 1.0); }")
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

    def _build_header(self) -> QWidget:
        return shell_build_header(self)

    def _build_sidebar(self) -> QWidget:
        return shell_build_sidebar(self)

    def _build_scroll_body(self) -> QWidget:
        return shell_build_scroll_body(self)

    def _build_search_overlay(self) -> None:
        shell_build_search_overlay(self)

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
        "notification center width": ("notification_center", "Width"),
        "notification center height": ("notification_center", "Height"),
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
            "notification_center": 7,
            "input": 8,
            "startup": 9,
            "privacy": 10,
            "networking": 11,
            "storage": 12,
            "region": 13,
            "bar": 14,
            "services": 15,
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
        return build_overview_page(self)

    def _build_appearance_page(self) -> QWidget:
        return build_appearance_page(self)

    def _build_bar_page(self) -> QWidget:
        return self._scroll_page(self._build_bar_screen_card())

    def _build_marketplace_page(self) -> QWidget:
        return build_marketplace_page(self)

    def _build_energy_page(self) -> QWidget:
        return self._scroll_page(self._build_energy_card())

    def _build_audio_page(self) -> QWidget:
        return build_audio_page(self)

    def _build_notifications_page(self) -> QWidget:
        return self._scroll_page(self._build_notifications_card())

    def _build_notification_center_page(self) -> QWidget:
        return self._scroll_page(self._build_notification_center_card())

    def _build_input_page(self) -> QWidget:
        return self._scroll_page(self._build_input_card())

    def _build_startup_page(self) -> QWidget:
        return self._scroll_page(self._build_startup_card())

    def _build_privacy_page(self) -> QWidget:
        return self._scroll_page(self._build_privacy_card())

    def _build_networking_page(self) -> QWidget:
        return self._scroll_page(self._build_networking_card())

    def _build_storage_page(self) -> QWidget:
        return build_storage_page(self)

    def _build_region_page(self) -> QWidget:
        return self._scroll_page(self._build_region_card())

    def _build_services_page(self) -> QWidget:
        return build_services_page(self)

    def _build_display_page(self) -> QWidget:
        return build_display_page(self)

    def _build_picom_page(self) -> QWidget:
        return self._scroll_page(self._build_picom_card())

    def _show_page(self, key: str) -> None:
        indices = getattr(self, "page_indices", {}) or {}
        supported = set(indices.keys()) if indices else {
            "overview",
            "appearance",
            "marketplace",
            "display",
            "energy",
            "audio",
            "notifications",
            "notification_center",
            "input",
            "startup",
            "privacy",
            "networking",
            "storage",
            "region",
            "bar",
            "services",
        }
        resolved = key if key in supported else "appearance"

        if resolved == "bar":
            self._ensure_bar_page_ready()
        elif resolved == "services":
            self._ensure_services_page_ready()
        else:
            self._ensure_page_ready(resolved)

        self.current_page = resolved
        index = int(indices.get(resolved, 0))
        self.page_stack.setCurrentIndex(index)
        if resolved == "marketplace":
            page_widget = self.page_stack.widget(index)
            on_page_activated = getattr(page_widget, "on_page_activated", None)
            if callable(on_page_activated):
                on_page_activated()
        for button_key, button in getattr(self, "nav_buttons", {}).items():
            button.setChecked(button_key == resolved)
        if resolved == "services" and self.initial_service_section:
            QTimer.singleShot(
                0, lambda: self._focus_service_section(self.initial_service_section)
            )

    def _ensure_page_ready(self, key: str) -> None:
        ready = getattr(self, "page_ready", set())
        if key in ready:
            return
        if key in {"overview", "appearance"}:
            return
        if not hasattr(self, "_lazy_page_building"):
            self._lazy_page_building = set()
        if key in self._lazy_page_building:
            return
        builders = {
            "display": self._build_display_page,
            "marketplace": self._build_marketplace_page,
            "networking": self._build_networking_page,
            "audio": self._build_audio_page,
            "energy": self._build_energy_page,
            "notifications": self._build_notifications_page,
            "notification_center": self._build_notification_center_page,
            "input": self._build_input_page,
            "startup": self._build_startup_page,
            "privacy": self._build_privacy_page,
            "storage": self._build_storage_page,
            "region": self._build_region_page,
        }
        builder = builders.get(key)
        if builder is None:
            return
        self._lazy_page_building.add(key)

        def _build() -> None:
            try:
                page = builder()
                index = int(getattr(self, "page_indices", {}).get(key, 0))
                old_widget = self.page_stack.widget(index)
                if old_widget is not None:
                    self.page_stack.removeWidget(old_widget)
                    old_widget.deleteLater()
                self.page_stack.insertWidget(index, page)
                ready.add(key)
                self.page_ready = ready
                if str(getattr(self, "current_page", "")) == key:
                    self.page_stack.setCurrentIndex(index)
            finally:
                self._lazy_page_building.discard(key)

        QTimer.singleShot(0, _build)

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
        return build_audio_card(self)

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

    def _build_notification_center_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("notifications"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Notification Center")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel(
            "Adjust the size of the notification center panel."
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

        nc = self.settings_state.get("notification_center", {})

        self.nc_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.nc_width_slider.setRange(400, 2400)
        self.nc_width_slider.setValue(int(nc.get("width", 800)))
        self.nc_width_slider.setFixedWidth(164)

        self.nc_width_label = QLabel(str(int(nc.get("width", 800))))
        self.nc_width_label.setFixedWidth(56)
        self.nc_width_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.nc_width_label.setStyleSheet("color: rgba(246,235,247,0.78);")

        width_row = QWidget()
        width_row_layout = QHBoxLayout(width_row)
        width_row_layout.setContentsMargins(0, 0, 0, 0)
        width_row_layout.setSpacing(10)
        width_row_layout.addWidget(self.nc_width_slider)
        width_row_layout.addWidget(self.nc_width_label)

        self.nc_width_slider.valueChanged.connect(self._on_nc_width_changed)

        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Width",
                "Panel width in pixels (400-2400).",
                self.icon_font,
                self.ui_font,
                width_row,
            )
        )

        self.nc_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.nc_height_slider.setRange(300, 1600)
        self.nc_height_slider.setValue(int(nc.get("height", 740)))
        self.nc_height_slider.setFixedWidth(164)

        self.nc_height_label = QLabel(str(int(nc.get("height", 740))))
        self.nc_height_label.setFixedWidth(56)
        self.nc_height_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.nc_height_label.setStyleSheet("color: rgba(246,235,247,0.78);")

        height_row = QWidget()
        height_row_layout = QHBoxLayout(height_row)
        height_row_layout.setContentsMargins(0, 0, 0, 0)
        height_row_layout.setSpacing(10)
        height_row_layout.addWidget(self.nc_height_slider)
        height_row_layout.addWidget(self.nc_height_label)

        self.nc_height_slider.valueChanged.connect(self._on_nc_height_changed)

        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Height",
                "Panel height in pixels (300-1600).",
                self.icon_font,
                self.ui_font,
                height_row,
            )
        )

        self.nc_status = QLabel("Notification center size settings are ready.")
        self.nc_status.setWordWrap(True)
        self.nc_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.nc_status)

        save_button = QPushButton("Save notification center size")
        save_button.setObjectName("primaryButton")
        save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_button.clicked.connect(self._save_notification_center_page_settings)
        layout.addWidget(save_button, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _on_nc_width_changed(self, value: int) -> None:
        value = max(400, min(2400, int(value)))
        self.settings_state.setdefault("notification_center", {})["width"] = value
        save_settings_state(self.settings_state)
        self.nc_width_label.setText(str(value))

    def _on_nc_height_changed(self, value: int) -> None:
        value = max(300, min(1600, int(value)))
        self.settings_state.setdefault("notification_center", {})["height"] = value
        save_settings_state(self.settings_state)
        self.nc_height_label.setText(str(value))

    def _save_notification_center_page_settings(self) -> None:
        nc = self.settings_state.setdefault("notification_center", {})
        nc["width"] = max(400, min(2400, int(self.nc_width_slider.value())))
        nc["height"] = max(300, min(1600, int(self.nc_height_slider.value())))
        save_settings_state(self.settings_state)
        self.nc_status.setText(
            f"Notification center size saved: {nc['width']}×{nc['height']}."
        )

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

        self._keyboard_layout_label_to_value: dict[str, str] = {}
        labels: list[str] = []
        for label, layout_value in KEYBOARD_LAYOUT_PRESETS:
            self._keyboard_layout_label_to_value[label] = layout_value
            labels.append(label)
        self.input_keyboard_layout_input = QLineEdit()
        self.input_keyboard_layout_input.setObjectName("settingsInput")
        self.input_keyboard_layout_input.setPlaceholderText("Type keyboard language")
        completer_model = QStringListModel(labels, self)
        self.input_keyboard_layout_completer = QCompleter(completer_model, self)
        self.input_keyboard_layout_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.input_keyboard_layout_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.input_keyboard_layout_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self.input_keyboard_layout_input.setCompleter(
            self.input_keyboard_layout_completer
        )
        self.input_keyboard_layout_input.textEdited.connect(
            lambda _text: self.input_keyboard_layout_completer.complete()
        )
        current_layout = self._normalize_keyboard_layout_value(
            str(self.settings_state["input"].get("keyboard_layout", "us"))
        )
        self.input_keyboard_layout_input.setText(
            self._keyboard_layout_label_for_value(current_layout)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("language"),
                "Keyboard language",
                "Choose a layout by language name. Hanauta saves and applies it to the current i3 session.",
                self.icon_font,
                self.ui_font,
                self.input_keyboard_layout_input,
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
                "System locale",
                "Set the desktop locale Hanauta should apply for your session and terminals. You can type a custom locale like en_US.UTF-8.",
                self.icon_font,
                self.ui_font,
                self.region_locale_combo,
            )
        )

        self._region_keyboard_layout_label_to_value: dict[str, str] = {}
        region_labels: list[str] = []
        for label, layout_value in KEYBOARD_LAYOUT_PRESETS:
            self._region_keyboard_layout_label_to_value[label] = layout_value
            region_labels.append(label)
        self.region_keyboard_layout_input = QLineEdit()
        self.region_keyboard_layout_input.setObjectName("settingsInput")
        self.region_keyboard_layout_input.setPlaceholderText("Type keyboard language")
        region_model = QStringListModel(region_labels, self)
        self.region_keyboard_layout_completer = QCompleter(region_model, self)
        self.region_keyboard_layout_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.region_keyboard_layout_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.region_keyboard_layout_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self.region_keyboard_layout_input.setCompleter(
            self.region_keyboard_layout_completer
        )
        self.region_keyboard_layout_input.textEdited.connect(
            lambda _text: self.region_keyboard_layout_completer.complete()
        )
        current_region_layout = self._normalize_keyboard_layout_value(
            str(
                self.settings_state["region"].get(
                    "keyboard_layout",
                    self.settings_state.get("input", {}).get("keyboard_layout", "us"),
                )
            )
        )
        self.region_keyboard_layout_input.setText(
            self._keyboard_layout_label_for_value(current_region_layout)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("keyboard"),
                "Keyboard language",
                "Autocomplete keyboard layout used by the current session (setxkbmap). Example: us, br, br abnt2.",
                self.icon_font,
                self.ui_font,
                self.region_keyboard_layout_input,
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
        self.region_location_input.textChanged.connect(self._queue_weather_city_search)
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
        return build_marketplace_card(self)


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

    def _build_picom_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("displayPanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Picom")
        title.setFont(QFont(self.display_font, 13))
        title.setObjectName("picomTitle")
        subtitle = QLabel(
            "Compositor controls for shadows, opacity, corner radius, and related rendering behavior."
        )
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setObjectName("picomSubtitle")
        subtitle.setProperty("mutedText", True)
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.picom_backend_combo = QComboBox()
        self.picom_backend_combo.setObjectName("settingsCombo")
        _original_picom_backend_wheel_event = self.picom_backend_combo.wheelEvent

        def _guarded_picom_backend_wheel_event(event) -> None:
            if self.picom_backend_combo.view().isVisible():
                _original_picom_backend_wheel_event(event)
                return
            event.ignore()

        self.picom_backend_combo.wheelEvent = _guarded_picom_backend_wheel_event  # type: ignore[method-assign]
        for option in ("glx", "xrender"):
            self.picom_backend_combo.addItem(option)

        self.picom_vsync_switch = SwitchButton(True)
        self.picom_damage_switch = SwitchButton(True)
        self.picom_shadow_switch = SwitchButton(True)
        self.picom_fading_switch = SwitchButton(False)
        self.picom_clip_switch = SwitchButton(False)
        self.picom_rounded_switch = SwitchButton(True)

        self.picom_shadow_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.picom_shadow_radius_slider.setRange(0, 100)
        self.picom_shadow_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.picom_shadow_opacity_slider.setRange(0, 100)
        self.picom_shadow_offset_x_slider = QSlider(Qt.Orientation.Horizontal)
        self.picom_shadow_offset_x_slider.setRange(-80, 80)
        self.picom_shadow_offset_y_slider = QSlider(Qt.Orientation.Horizontal)
        self.picom_shadow_offset_y_slider.setRange(-80, 80)
        self.picom_active_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.picom_active_opacity_slider.setRange(0, 100)
        self.picom_inactive_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.picom_inactive_opacity_slider.setRange(0, 100)
        self.picom_corner_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.picom_corner_radius_slider.setRange(0, 64)

        for row in (
            SettingsRow(material_icon("developer_board"), "Backend", "Picom renderer backend.", self.icon_font, self.ui_font, self.picom_backend_combo, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_backend.svg")),
            SettingsRow(material_icon("sync"), "VSync", "Reduce tearing when possible.", self.icon_font, self.ui_font, self.picom_vsync_switch, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_vsync.svg")),
            SettingsRow(material_icon("tune"), "Use Damage", "Track damaged regions for more efficient redraws.", self.icon_font, self.ui_font, self.picom_damage_switch, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_damage.svg")),
            SettingsRow(material_icon("gradient"), "Shadows", "Enable window shadows.", self.icon_font, self.ui_font, self.picom_shadow_switch, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_shadows.svg")),
            SettingsRow(material_icon("blur_on"), "Shadow Radius", "Blur radius for shadows.", self.icon_font, self.ui_font, self.picom_shadow_radius_slider, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_blur.svg")),
            SettingsRow(material_icon("opacity"), "Shadow Opacity", "Opacity for window shadows.", self.icon_font, self.ui_font, self.picom_shadow_opacity_slider, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_opacity.svg")),
            SettingsRow(material_icon("swap_horiz"), "Shadow Offset X", "Horizontal offset for shadows.", self.icon_font, self.ui_font, self.picom_shadow_offset_x_slider, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_offset_x.svg")),
            SettingsRow(material_icon("swap_vert"), "Shadow Offset Y", "Vertical offset for shadows.", self.icon_font, self.ui_font, self.picom_shadow_offset_y_slider, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_offset_y.svg")),
            SettingsRow(material_icon("animation"), "Fading", "Enable fade transitions.", self.icon_font, self.ui_font, self.picom_fading_switch, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_fading.svg")),
            SettingsRow(material_icon("filter_center_focus"), "Active Opacity", "Opacity for focused windows.", self.icon_font, self.ui_font, self.picom_active_opacity_slider, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_focus.svg")),
            SettingsRow(material_icon("filter_alt"), "Inactive Opacity", "Opacity for unfocused windows.", self.icon_font, self.ui_font, self.picom_inactive_opacity_slider, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_inactive.svg")),
            SettingsRow(material_icon("rounded_corner"), "Corner Radius", "Rounded corner radius in pixels.", self.icon_font, self.ui_font, self.picom_corner_radius_slider, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_radius.svg")),
            SettingsRow(material_icon("crop_din"), "Transparent Clipping", "Clip transparent regions more aggressively.", self.icon_font, self.ui_font, self.picom_clip_switch, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_clip.svg")),
            SettingsRow(material_icon("radio_button_checked"), "Detect Rounded Corners", "Honor rounded-corner hints from apps.", self.icon_font, self.ui_font, self.picom_rounded_switch, icon_svg_path=str(ASSETS_DIR / "nav-icons" / "picom_rounded.svg")),
        ):
            layout.addWidget(row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        apply_button = QPushButton("Apply Picom")
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self._apply_picom_settings)
        restart_button = QPushButton("Restart Picom")
        restart_button.setObjectName("secondaryButton")
        restart_button.clicked.connect(self._restart_picom)
        defaults_button = QPushButton("Reset Defaults")
        defaults_button.setObjectName("secondaryButton")
        defaults_button.clicked.connect(self._reset_picom_defaults)
        rules_button = QPushButton("Open Rule Files")
        rules_button.setObjectName("secondaryButton")
        rules_button.clicked.connect(self._open_picom_rule_dir)
        actions.addWidget(apply_button)
        actions.addWidget(restart_button)
        actions.addWidget(defaults_button)
        actions.addWidget(rules_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.picom_status = QLabel("")
        self.picom_status.setObjectName("picomStatus")
        self.picom_status.setProperty("mutedText", True)
        self.picom_status.setWordWrap(True)
        layout.addWidget(self.picom_status)

        self._sync_picom_controls()
        return card

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
        QTimer.singleShot(240, self._apply_i3_window_rules)

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

