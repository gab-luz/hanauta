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







class BarMixin:
    """Extracted methods for bar."""

    def _build_bar_placeholder(self) -> QWidget:
        return shell_build_bar_placeholder(self)


    def _ensure_bar_page_ready(self) -> None:
        if "bar" in getattr(self, "page_ready", set()):
            return
        if bool(getattr(self, "_bar_page_building", False)):
            return
        self._bar_page_building = True

        def _build() -> None:
            try:
                bar_page = self._build_bar_page()
                index = int(getattr(self, "page_indices", {}).get("bar", 13))
                old_widget = self.page_stack.widget(index)
                if old_widget is not None:
                    self.page_stack.removeWidget(old_widget)
                    old_widget.deleteLater()
                self.page_stack.insertWidget(index, bar_page)
                getattr(self, "page_ready", set()).add("bar")
                if str(getattr(self, "current_page", "")) == "bar":
                    self.page_stack.setCurrentIndex(index)
            finally:
                self._bar_page_building = False

        QTimer.singleShot(0, _build)


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


    def _set_bar_full_radius(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["full_bar_radius"] = int(value)
        self._save_bar_settings()

    # Dock settings handlers
    def _set_dock_auto_hide(self, enabled: bool) -> None:
        self.settings_state.setdefault("dock", {})["auto_hide"] = bool(enabled)
        self._save_dock_settings()

    def _set_dock_icons_left(self, enabled: bool) -> None:
        self.settings_state.setdefault("dock", {})["icons_left"] = bool(enabled)
        self._save_dock_settings()

    def _set_dock_width(self, value: int) -> None:
        self.settings_state.setdefault("dock", {})["width"] = int(value)
        self._save_dock_settings()

    def _set_dock_height(self, value: int) -> None:
        self.settings_state.setdefault("dock", {})["height"] = int(value)
        self._save_dock_settings()

    def _set_dock_transparency(self, value: int) -> None:
        self.settings_state.setdefault("dock", {})["transparency"] = int(value)
        self._save_dock_settings()

    def _set_dock_position(self, position: str) -> None:
        valid_positions = {"left", "center", "right"}
        pos = position if position in valid_positions else "center"
        self.settings_state.setdefault("dock", {})["position"] = pos
        self._save_dock_settings()

    def _set_dock_monitor_mode(self, mode: str) -> None:
        valid_modes = {"primary", "follow_mouse", "named"}
        m = mode if mode in valid_modes else "primary"
        self.settings_state.setdefault("dock", {})["monitor_mode"] = m
        self._save_dock_settings()

    def _set_dock_monitor_name(self, name: str) -> None:
        self.settings_state.setdefault("dock", {})["monitor_name"] = str(name).strip()
        self._save_dock_settings()

    def _save_dock_settings(self) -> None:
        from settings_page.dock_settings import save_dock_settings_state
        save_dock_settings_state(self.settings_state)
        self._save_settings()


