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







class AppearanceMixin:
    """Extracted methods for appearance."""

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
        return build_wallpaper_colors_card(self)



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

    def _make_follow_system_switch(self) -> SwitchButton:
        switch = SwitchButton(
            bool(self.settings_state["appearance"].get("follow_system_theme", False))
        )
        switch.toggledValue.connect(self._set_follow_system_theme)
        self.follow_system_switch = switch
        return switch


    def _slider_settings_row(
        self,
        title: str,
        subtitle: str,
        min_value: int,
        max_value: int,
        current_value: int,
        icon: str,
        setting_key: str,
    ) -> QWidget:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(min_value), int(max_value))
        slider.setValue(int(current_value))
        slider.setFixedWidth(164)

        label = QLabel(str(int(current_value)))
        label.setFixedWidth(56)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("color: rgba(246,235,247,0.78);")

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        row_layout.addWidget(slider)
        row_layout.addWidget(label)

        slider_attr = f"{setting_key}_slider"
        label_attr = f"{setting_key}_label"
        setattr(self, slider_attr, slider)
        setattr(self, label_attr, label)

        handler = getattr(self, f"_set_{setting_key}", None)

        def on_value_changed(value: int) -> None:
            if handler is not None:
                handler(int(value))
                label.setText(str(int(self.settings_state["appearance"].get(setting_key, value))))
                return
            self.settings_state["appearance"][setting_key] = int(value)
            save_settings_state(self.settings_state)
            label.setText(str(int(value)))

        slider.valueChanged.connect(on_value_changed)

        return SettingsRow(icon, title, subtitle, self.icon_font, self.ui_font, row_widget)


    def _metric_card(self, title: str, value_label: QLabel) -> QFrame:
        return build_metric_card(self, title, value_label)


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


    def _set_follow_system_theme(self, enabled: bool) -> None:
        self.settings_state["appearance"]["follow_system_theme"] = bool(enabled)
        save_settings_state(self.settings_state)
        if enabled:
            self._apply_system_theme_preference()
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(
                "Follow system theme enabled. Hanauta will match GTK color-scheme."
                if enabled
                else "Follow system theme disabled."
            )

    def _apply_system_theme_preference(self) -> None:
        """Detect system GTK color-scheme and apply matching Hanauta theme."""
        from pathlib import Path
        import subprocess
        result = subprocess.run(
            ["bash", str(Path.home() / ".config" / "i3" / "hanauta" / "scripts" / "color_scheme.sh")],
            capture_output=True, text=True, timeout=2.0, check=False
        )
        system_scheme = result.stdout.strip()
        if system_scheme not in ("dark", "light"):
            system_scheme = "dark"
        current_choice = str(self.settings_state["appearance"].get("theme_choice", "dark")).strip().lower()
        target_choice = system_scheme if system_scheme in {"dark", "light"} else "dark"
        if current_choice != target_choice:
            self.settings_state["appearance"]["theme_choice"] = target_choice
            self.settings_state["appearance"]["theme_mode"] = target_choice
            self.settings_state["appearance"]["use_matugen_palette"] = False
            save_settings_state(self.settings_state)
            sync_static_theme_from_settings(self.settings_state, apply_gtk=True)
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

    def _set_media_player_style(self, style: str) -> None:
        style = str(style).strip().lower()
        if style not in ("artwork_gradient", "immersive_artwork"):
            return
        nc_cfg = self.settings_state.setdefault("notification_center", {})
        nc_cfg["media_player_style"] = style
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            labels = {
                "artwork_gradient": "Media player style: Artwork + Dynamic Gradient",
                "immersive_artwork": "Media player style: Immersive Artwork",
            }
            self.appearance_status.setText(labels.get(style, "Media player style updated."))

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
        follow_system = bool(self.settings_state["appearance"].get("follow_system_theme", False))
        if hasattr(self, "follow_system_switch"):
            self.follow_system_switch.setChecked(follow_system)
        for button in getattr(self, "theme_buttons", {}).values():
            button.setEnabled(not follow_system)
        if hasattr(self, "custom_theme_wrap"):
            self.custom_theme_wrap.setEnabled(not follow_system)
        if hasattr(self, "custom_theme_heading"):
            self.custom_theme_heading.setEnabled(not follow_system)
        if hasattr(self, "custom_theme_hint"):
            self.custom_theme_hint.setEnabled(not follow_system)
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


    def _check_system_theme_change(self) -> None:
        """Check if system GTK color-scheme changed and apply if follow_system_theme is enabled."""
        if not self.settings_state["appearance"].get("follow_system_theme", False):
            return
        self._apply_system_theme_preference()


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


