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







class ServicesMixin:
    """Extracted methods for services."""

    def _build_services_placeholder(self) -> QWidget:
        return shell_build_services_placeholder(self)


    def _ensure_services_page_ready(self) -> None:
        if "services" in getattr(self, "page_ready", set()):
            return
        if bool(getattr(self, "_services_page_building", False)):
            return
        self._services_page_building = True

        try:
            services_page = self._build_services_page()
            index = int(getattr(self, "page_indices", {}).get("services", 14))
            old_widget = self.page_stack.widget(index)
            container = self.page_stack
            container.setUpdatesEnabled(False)
            try:
                if old_widget is not None:
                    self.page_stack.removeWidget(old_widget)
                    old_widget.deleteLater()
                self.page_stack.insertWidget(index, services_page)
                getattr(self, "page_ready", set()).add("services")
                if str(getattr(self, "current_page", "")) == "services":
                    self.page_stack.setCurrentIndex(index)
            finally:
                container.setUpdatesEnabled(True)
        finally:
            self._services_page_building = False


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
        container = layout.parentWidget()
        if container is not None:
            container.setUpdatesEnabled(False)
        try:
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
        finally:
            if container is not None:
                container.setUpdatesEnabled(True)


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


    def _plugin_api_versions_from_row(self, row: object) -> tuple[int, int]:
        if not isinstance(row, dict):
            return 1, HOST_PLUGIN_API_VERSION
        try:
            api_min_version = int(row.get("api_min_version", 1) or 1)
        except Exception:
            api_min_version = 1
        try:
            api_target_version = int(
                row.get("api_target_version", HOST_PLUGIN_API_VERSION)
                or HOST_PLUGIN_API_VERSION
            )
        except Exception:
            api_target_version = HOST_PLUGIN_API_VERSION
        return max(1, api_min_version), max(1, api_target_version)


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
        return build_services_card(self)



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
            if expand_after_replace and not new_widget._expanded:
                new_widget.toggle_expanded()
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
            container = layout.parentWidget()
            if container is not None:
                container.setUpdatesEnabled(False)
            try:
                while core_queue:
                    key, builder = core_queue.pop(0)
                    if self._installed_plugin_for_service_key(key) is not None:
                        continue
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
            finally:
                if container is not None:
                    container.setUpdatesEnabled(True)
            QTimer.singleShot(0, self._build_next_services_section)
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
            loading_label = getattr(self, "_services_loading_label", None)
            container = layout.parentWidget() if layout else None
            if container is not None:
                container.setUpdatesEnabled(False)
            try:
                if isinstance(loading_label, QLabel):
                    loading_label.setVisible(False)
                    loading_label.deleteLater()
                    self._services_loading_label = None
                self._refresh_service_widget_order()
                layout.addStretch(1)
            finally:
                if container is not None:
                    container.setUpdatesEnabled(True)
            if str(getattr(self, "initial_service_section", "")).strip():
                QTimer.singleShot(
                    0, lambda: self._focus_service_section(self.initial_service_section)
                )


    def _focus_service_section(self, key: str) -> None:
        section = getattr(self, "service_sections", {}).get(key)
        if section is None:
            return
        if not section._expanded:
            section.toggle_expanded()
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

        api_key_row = QWidget()
        api_key_layout = QHBoxLayout(api_key_row)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.setSpacing(8)
        self.mail_api_key_input = QLineEdit(load_email_client_api_key())
        self.mail_api_key_input.setPlaceholderText("Unset")
        self.mail_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.mail_api_key_input.editingFinished.connect(self._save_mail_api_key_setting)
        api_key_layout.addWidget(self.mail_api_key_input, 1)
        self.mail_api_key_generate_button = QPushButton("Generate")
        self.mail_api_key_generate_button.setObjectName("secondaryButton")
        self.mail_api_key_generate_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.mail_api_key_generate_button.clicked.connect(self._generate_mail_api_key_setting)
        api_key_layout.addWidget(self.mail_api_key_generate_button)
        layout.addWidget(
            SettingsRow(
                material_icon("key"),
                "Email API key",
                "Required to access the local mail plugin API on 127.0.0.1:11426.",
                self.icon_font,
                self.ui_font,
                api_key_row,
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


    def _build_disk_space_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        service = self.settings_state["services"].setdefault("disk_space", {})
        min_free = int(service.get("min_free_gb", 6) or 6)
        min_free = max(1, min(1024, min_free))
        service["min_free_gb"] = min_free

        self.disk_space_min_free_slider = QSlider(Qt.Orientation.Horizontal)
        self.disk_space_min_free_slider.setRange(1, 1024)
        self.disk_space_min_free_slider.setValue(min(1024, min_free))
        self.disk_space_min_free_slider.valueChanged.connect(
            self._set_disk_space_min_free_gb
        )
        self.disk_space_min_free_label = QLabel(f"{min(1024, min_free)} GB")
        self.disk_space_min_free_label.setFixedWidth(72)
        self.disk_space_min_free_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.disk_space_min_free_label.setStyleSheet("color: rgba(246,235,247,0.78);")

        threshold_wrap = QWidget()
        threshold_layout = QHBoxLayout(threshold_wrap)
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        threshold_layout.setSpacing(10)
        threshold_layout.addWidget(self.disk_space_min_free_slider)
        threshold_layout.addWidget(self.disk_space_min_free_label)
        layout.addWidget(
            SettingsRow(
                material_icon("storage"),
                "Minimum free space",
                "Trigger a fullscreen alert when free disk space (on your home filesystem) drops to this value or lower.",
                self.icon_font,
                self.ui_font,
                threshold_wrap,
            )
        )

        self.disk_space_status = QLabel(
            f"Fullscreen alerts enabled at ≤ {min(1024, min_free)} GB free (cooldown ~30 min)."
        )
        self.disk_space_status.setWordWrap(True)
        self.disk_space_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.disk_space_status)

        section = ExpandableServiceSection(
            "disk_space",
            "Disk Space",
            "Fullscreen warning when storage is running out.",
            material_icon("storage"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("disk_space"),
            lambda enabled: self._set_service_enabled("disk_space", enabled),
        )
        self.service_sections["disk_space"] = section
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
        self.weather_city_input.textChanged.connect(self._queue_weather_city_search)

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

        api_keys_title = QLabel("API Keys")
        api_keys_title.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        api_keys_title.setStyleSheet("color: rgba(246,235,247,0.86);")
        layout.addWidget(api_keys_title)

        self.weather_owm_key_input = QLineEdit(
            str(weather_settings.get("openweathermap_api_key", "")).strip()
        )
        self.weather_owm_key_input.setPlaceholderText(
            "Optional — overrides free Open-Meteo when set"
        )
        self.weather_owm_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.weather_owm_key_input.editingFinished.connect(
            self._save_weather_api_keys
        )
        layout.addWidget(
            SettingsRow(
                material_icon("key"),
                "OpenWeatherMap API key",
                "Free tier available at openweathermap.org. When set, weather data comes from OpenWeatherMap instead of Open-Meteo. Falls back to wttr.in if both fail.",
                self.icon_font,
                self.ui_font,
                self.weather_owm_key_input,
            )
        )

        self.weather_poll_interval_spin = QSpinBox()
        self.weather_poll_interval_spin.setRange(15, 1440)
        self.weather_poll_interval_spin.setSingleStep(5)
        self.weather_poll_interval_spin.setSuffix(" min")
        self.weather_poll_interval_spin.setValue(
            max(15, min(1440, int(weather_settings.get("poll_interval_minutes", 15) or 15)))
        )
        self.weather_poll_interval_spin.valueChanged.connect(
            self._save_weather_poll_interval
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Background poll interval",
                "How often the weather cache is refreshed in the background (minimum 15 minutes). The popup loads from cache instantly.",
                self.icon_font,
                self.ui_font,
                self.weather_poll_interval_spin,
            )
        )

        self.weather_language_combo = QComboBox()
        self.weather_language_combo.setObjectName("settingsCombo")
        languages = [
            ("English (US)", "en"),
            ("Portuguese (Brazil)", "pt-br"),
            ("Spanish (Argentina)", "es-ar"),
            ("Russian (Russia)", "ru-ru"),
            ("German (Germany)", "de-de"),
            ("French (France)", "fr-fr"),
            ("Italian (Italy)", "it-it"),
            ("Japanese (Japan)", "ja-jp"),
            ("Chinese (Simplified)", "zh-cn"),
        ]
        for label, code in languages:
            self.weather_language_combo.addItem(label, code)
        current_lang = str(weather_settings.get("language", "en"))
        idx = self.weather_language_combo.findData(current_lang)
        self.weather_language_combo.setCurrentIndex(max(0, idx))
        self.weather_language_combo.currentIndexChanged.connect(
            self._set_weather_language
        )
        layout.addWidget(
            SettingsRow(
                material_icon("translate"),
                "Weather language",
                "Language for weather conditions and forecast text.",
                self.icon_font,
                self.ui_font,
                self.weather_language_combo,
            )
        )

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

        self.calendar_background_sync_combo = QComboBox()
        self.calendar_background_sync_combo.setObjectName("settingsCombo")
        intervals = [
            ("1 minute", 1),
            ("5 minutes", 5),
            ("15 minutes", 15),
            ("30 minutes", 30),
            ("1 hour", 60),
            ("2 hours", 120),
            ("4 hours", 240),
            ("8 hours", 480),
            ("12 hours", 720),
            ("24 hours", 1440),
        ]
        for label, value in intervals:
            self.calendar_background_sync_combo.addItem(label, value)
        current_interval = int(
            self.settings_state["calendar"].get("background_sync_interval_minutes", 5)
        )
        idx = self.calendar_background_sync_combo.findData(current_interval)
        self.calendar_background_sync_combo.setCurrentIndex(max(0, idx))
        self.calendar_background_sync_combo.currentIndexChanged.connect(
            self._set_calendar_background_sync_interval
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Background sync interval",
                "How often hanauta-service should fetch calendar events in the background.",
                self.icon_font,
                self.ui_font,
                self.calendar_background_sync_combo,
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


    def _service_enabled(self, key: str) -> bool:
        return bool(self.settings_state["services"].get(key, {}).get("enabled", True))


    def _stop_entrypoint_process(self, script_path: Path | None) -> None:
        if script_path is None:
            return
        try:
            patterns = entry_patterns(script_path)
        except Exception:
            patterns = []
        for pattern in patterns:
            if not pattern:
                continue
            subprocess.run(
                ["pkill", "-f", pattern], capture_output=True, text=True, check=False
            )


    def _service_runtime_entrypoints(self, key: str) -> list[Path]:
        candidates: list[Path] = []

        plugin_targets: dict[str, list[tuple[str, list[str]]]] = {
            "vpn_control": [("vpn_control.py", ["vpn-control", "vpn"])],
            "christian_widget": [("christian_widget.py", ["christian-widget"])],
            "reminders_widget": [("reminders_widget.py", ["reminders"])],
            "pomodoro_widget": [("pomodoro_widget.py", ["pomodoro"])],
            "rss_widget": [("rss_widget.py", ["rss"])],
            "obs_widget": [("obs_widget.py", ["obs"])],
            "crypto_widget": [("crypto_widget.py", ["crypto"])],
            "game_mode": [("game_mode_popup.py", ["game-mode"])],
            "study_tracker_widget": [("study_tracker.py", ["study-tracker"])],
        }

        for script_name, aliases in plugin_targets.get(key, []):
            resolved = resolve_plugin_script(script_name, aliases, required=False)
            if resolved is not None and resolved.exists():
                candidates.append(resolved)

        if key == "calendar_widget":
            qcal = resolve_qcal_wrapper()
            if qcal is not None and qcal.exists():
                candidates.append(qcal)
        if key == "desktop_clock_widget":
            desktop_clock = resolve_desktop_clock_widget()
            if desktop_clock is not None and desktop_clock.exists():
                candidates.append(desktop_clock)
            if DESKTOP_CLOCK_BINARY.exists():
                candidates.append(DESKTOP_CLOCK_BINARY)
        if key == "virtualization":
            daemon = resolve_virtualization_daemon()
            if daemon is not None and daemon.exists():
                candidates.append(daemon)
        if key == "mail":
            mail_client = resolve_email_client_app()
            if mail_client is not None and mail_client.exists():
                candidates.append(mail_client)

        unique: list[Path] = []
        seen: set[str] = set()
        for path in candidates:
            token = str(path.resolve())
            if token in seen:
                continue
            seen.add(token)
            unique.append(path)
        return unique


    def _stop_service_runtime(self, key: str) -> None:
        for entrypoint in self._service_runtime_entrypoints(key):
            self._stop_entrypoint_process(entrypoint)

        if key == "virtualization":
            self._stop_virtualization_daemon()
        if key == "vpn_control":
            # Best-effort stop for WireGuard helper services if present.
            for cmd in (
                ["systemctl", "--user", "stop", "hanauta-wireguard-agent.service"],
                ["systemctl", "--user", "stop", "hanauta-wireguard-autoconnect.service"],
                ["systemctl", "stop", "hanauta-wireguard-agent.service"],
                ["systemctl", "stop", "hanauta-wireguard-autoconnect.service"],
            ):
                subprocess.run(cmd, capture_output=True, text=True, check=False)


    def _start_service_runtime(self, key: str) -> None:
        if key == "virtualization":
            self._start_virtualization_daemon()


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
            self._stop_service_runtime(key)
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
        if enabled:
            self._start_service_runtime(key)
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


