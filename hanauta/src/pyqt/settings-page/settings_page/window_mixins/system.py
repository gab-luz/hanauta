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







class SystemPagesMixin:
    """Extracted methods for system."""

    def _refresh_display_state(self) -> None:
        self.display_state = parse_xrandr_state()
        display_page_index = int(getattr(self, "page_indices", {}).get("display", -1))
        if display_page_index < 0:
            return
        page = self._build_display_page()
        old_widget = self.page_stack.widget(display_page_index)
        if old_widget is not None:
            self.page_stack.removeWidget(old_widget)
            old_widget.deleteLater()
        self.page_stack.insertWidget(display_page_index, page)
        if str(getattr(self, "current_page", "")) == "display":
            self.page_stack.setCurrentIndex(display_page_index)


    def _set_display_layout_mode(self, mode: str) -> None:
        normalized = (
            "duplicate" if str(mode).strip().lower() == "duplicate" else "extend"
        )
        display_settings = self.settings_state.setdefault("display", {})
        if not isinstance(display_settings, dict):
            display_settings = {}
            self.settings_state["display"] = display_settings
        display_settings["layout_mode"] = normalized
        buttons = getattr(self, "display_layout_buttons", {})
        if isinstance(buttons, dict):
            button = buttons.get(normalized)
            if button is not None:
                button.setChecked(True)
        save_settings_state(self.settings_state)


    def _rebuild_display_output_cards(self) -> None:
        container = getattr(self, "display_outputs_container", None)
        if container is None:
            return
        while container.count():
            item = container.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        # Reuse the existing page builder helper that populates output cards.
        from settings_page.pages.display import build_display_global_card

        build_display_global_card(self)


    def _sync_refresh_rates_for_output(self, output_name: str, mode: str) -> None:
        controls = self.display_controls.get(output_name, {})
        refresh_combo = controls.get("refresh")
        if refresh_combo is None:
            return
        display = next(
            (
                item
                for item in self.display_state
                if str(item.get("name", "")).strip() == output_name
            ),
            None,
        )
        if not isinstance(display, dict):
            return
        refresh_rates = display.get("refresh_rates", {})
        rates = []
        if isinstance(refresh_rates, dict):
            rates = refresh_rates.get(mode, [])
        if not isinstance(rates, list):
            rates = []
        current = refresh_combo.currentText().strip()
        refresh_combo.blockSignals(True)
        refresh_combo.clear()
        refresh_combo.addItem("Auto")
        for rate in rates:
            value = str(rate).strip()
            if value:
                refresh_combo.addItem(value)
        preferred = str(display.get("current_refresh", "")).strip()
        if preferred and refresh_combo.findText(preferred) >= 0:
            refresh_combo.setCurrentText(preferred)
        elif current and refresh_combo.findText(current) >= 0:
            refresh_combo.setCurrentText(current)
        else:
            refresh_combo.setCurrentText("Auto")
        refresh_combo.blockSignals(False)


    def _set_display_wallpaper_mode(self, output_name: str, mode: str) -> None:
        appearance = self.settings_state.setdefault("appearance", {})
        if not isinstance(appearance, dict):
            appearance = {}
            self.settings_state["appearance"] = appearance
        fit_modes = appearance.setdefault("wallpaper_fit_modes", {})
        if not isinstance(fit_modes, dict):
            fit_modes = {}
            appearance["wallpaper_fit_modes"] = fit_modes
        normalized = str(mode).strip().lower()
        if normalized not in {"fill", "fit", "center", "stretch", "tile"}:
            normalized = "fill"
        fit_modes[str(output_name).strip()] = normalized
        save_settings_state(self.settings_state)
        self._apply_current_wallpaper_layout()


    def _apply_display_settings(self) -> None:
        if not self.display_state:
            if hasattr(self, "display_status"):
                self.display_status.setText("No displays detected through xrandr.")
            return

        def _combo_text_or_fallback(combo: object, fallback: str) -> str:
            if combo is None:
                return fallback
            try:
                return str(combo.currentText()).strip()
            except RuntimeError:
                return fallback

        def _switch_checked_or_fallback(widget: object, fallback: bool) -> bool:
            if widget is None:
                return fallback
            try:
                return bool(widget.isChecked())
            except RuntimeError:
                return fallback

        primary_name = ""
        primary_combo = getattr(self, "primary_display_combo", None)
        primary_name = _combo_text_or_fallback(primary_combo, "")
        if not primary_name:
            primary_name = str(self.display_state[0].get("name", "")).strip()

        display_settings = self.settings_state.setdefault("display", {})
        if not isinstance(display_settings, dict):
            display_settings = {}
            self.settings_state["display"] = display_settings
        layout_mode = str(display_settings.get("layout_mode", "extend")).strip().lower()
        if layout_mode not in {"extend", "duplicate"}:
            layout_mode = "extend"

        payload: list[dict[str, object]] = []
        for display in self.display_state:
            name = str(display.get("name", "")).strip()
            if not name:
                continue
            controls = self.display_controls.get(name, {})
            enabled_switch = controls.get("enabled")
            resolution_combo = controls.get("resolution")
            refresh_combo = controls.get("refresh")
            orientation_combo = controls.get("orientation")

            enabled = _switch_checked_or_fallback(
                enabled_switch, bool(display.get("enabled", True))
            )
            resolution = _combo_text_or_fallback(
                resolution_combo, str(display.get("current_mode", "")).strip()
            )
            refresh = _combo_text_or_fallback(
                refresh_combo, str(display.get("current_refresh", "")).strip()
            )
            orientation = normalize_display_orientation(
                _combo_text_or_fallback(
                    orientation_combo, str(display.get("orientation", "normal"))
                )
            )
            payload.append(
                {
                    "name": name,
                    "enabled": enabled,
                    "resolution": resolution,
                    "refresh": refresh,
                    "orientation": orientation,
                    "modes": display.get("modes", []),
                }
            )

        cmd = build_display_command(payload, primary_name, layout_mode)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip() or "xrandr failed."
            if hasattr(self, "display_status"):
                self.display_status.setText(
                    f"Failed to apply display settings: {detail}"
                )
            return

        display_settings["primary"] = primary_name
        display_settings["layout_mode"] = layout_mode
        display_settings["outputs"] = payload
        save_settings_state(self.settings_state)
        if hasattr(self, "display_status"):
            self.display_status.setText("Display settings applied.")
        self._refresh_display_state()


    def _populate_monitor_target_combo(
        self, combo: QComboBox, monitor_mode: str, monitor_name: str
    ) -> None:
        combo.clear()
        combo.setObjectName("settingsCombo")

        entries: list[tuple[str, str, str]] = [
            ("Primary monitor", "primary", ""),
            ("Follow mouse", "follow_mouse", ""),
        ]

        primary_output_name = ""
        for display in getattr(self, "display_state", []) or []:
            if isinstance(display, dict) and bool(display.get("primary")):
                primary_output_name = str(display.get("name", "")).strip()
                break

        try:
            from PyQt6.QtWidgets import QApplication

            seen: set[str] = set()
            for screen in QApplication.screens():
                name = str(screen.name() or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                label = f"{name} (primary)" if name == primary_output_name else name
                entries.append((label, "named", name))
        except Exception:
            pass

        for label, mode, name in entries:
            combo.addItem(label, {"mode": mode, "name": name})

        normalized_mode = str(monitor_mode or "primary").strip().lower()
        if normalized_mode not in {"primary", "follow_mouse", "named"}:
            normalized_mode = "primary"
        normalized_name = str(monitor_name or "").strip()

        selected_index = 0
        for index in range(combo.count()):
            payload = combo.itemData(index)
            if not isinstance(payload, dict):
                continue
            if payload.get("mode") == normalized_mode and payload.get("name") == normalized_name:
                selected_index = index
                break
        combo.setCurrentIndex(selected_index)


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
        sound = self.settings_state.setdefault("sound", {})
        sound["enabled"] = (
            bool(self.sound_enabled_switch.isChecked())
            if hasattr(self, "sound_enabled_switch")
            else True
        )
        sound["soundpack"] = (
            str(self.soundpack_combo.currentData() or "default")
            if hasattr(self, "soundpack_combo")
            else "default"
        )
        sound["default_volume"] = (
            int(self.sound_volume_slider.value() * 65536 // 100)
            if hasattr(self, "sound_volume_slider")
            else DEFAULT_SOUND_SETTINGS["default_volume"]
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


