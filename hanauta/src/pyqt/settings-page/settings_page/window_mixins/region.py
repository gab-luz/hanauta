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







class RegionMixin:
    """Extracted methods for region."""

    def _normalize_keyboard_layout_value(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "us"
        text = " ".join(part for part in text.split() if part)
        return text or "us"


    def _enable_combo_autocomplete(self, combo: QComboBox, completer: QCompleter) -> None:
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.setCompleter(completer)
        line_edit = combo.lineEdit()
        if line_edit is None:
            return
        line_edit.textEdited.connect(lambda _text: completer.complete())


    def _keyboard_layout_label_for_value(self, value: str) -> str:
        normalized = self._normalize_keyboard_layout_value(value)
        lowered = normalized.casefold()
        for label, layout_value in KEYBOARD_LAYOUT_PRESETS:
            if self._normalize_keyboard_layout_value(layout_value).casefold() == lowered:
                return str(label)
        return normalized


    def _resolve_keyboard_layout_value(self) -> str:
        line_edit = getattr(self, "input_keyboard_layout_input", None)
        if isinstance(line_edit, QLineEdit):
            text = line_edit.text().strip()
        else:
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
        combo = getattr(self, "input_keyboard_layout_combo", None)
        if isinstance(combo, QComboBox):
            data = combo.currentData()
            if isinstance(data, str) and data.strip():
                return self._normalize_keyboard_layout_value(data)
        return "us"


    def _resolve_region_keyboard_layout_value(self) -> str:
        line_edit = getattr(self, "region_keyboard_layout_input", None)
        if isinstance(line_edit, QLineEdit):
            text = line_edit.text().strip()
        else:
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
        combo = getattr(self, "region_keyboard_layout_combo", None)
        if isinstance(combo, QComboBox):
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


    def _set_region_use_24_hour(self, enabled: bool) -> None:
        self.settings_state.setdefault("region", {})["use_24_hour"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "region_status"):
            self.region_status.setText("Clock format updated.")


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


    def _write_managed_shell_block(self, path: Path, marker: str, content: str) -> None:
        begin = f"# >>> hanauta {marker} >>>"
        end = f"# <<< hanauta {marker} <<<"
        try:
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception:
            existing = ""
        lines: list[str] = []
        in_block = False
        for line in existing.splitlines():
            if line == begin:
                in_block = True
                continue
            if line == end:
                in_block = False
                continue
            if not in_block:
                lines.append(line)
        body = "\n".join(lines).rstrip()
        block = f"{begin}\n{content.rstrip()}\n{end}"
        final = f"{body}\n\n{block}\n" if body else f"{block}\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(final, encoding="utf-8")


    def _apply_user_locale_files(self, locale_code: str) -> None:
        locale_value = str(locale_code).strip()
        language_value = locale_value.split(".", 1)[0].split("_", 1)[0] or locale_value
        env_dir = Path.home() / ".config" / "environment.d"
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "90-hanauta-locale.conf").write_text(
            f'LANG="{locale_value}"\nLANGUAGE="{language_value}"\n',
            encoding="utf-8",
        )

        fish_dir = Path.home() / ".config" / "fish" / "conf.d"
        fish_dir.mkdir(parents=True, exist_ok=True)
        (fish_dir / "90-hanauta-locale.fish").write_text(
            f'set -gx LANG "{locale_value}"\nset -gx LANGUAGE "{language_value}"\n',
            encoding="utf-8",
        )

        shell_block = f'export LANG="{locale_value}"\nexport LANGUAGE="{language_value}"'
        self._write_managed_shell_block(Path.home() / ".profile", "system-locale", shell_block)
        self._write_managed_shell_block(Path.home() / ".bashrc", "system-locale", shell_block)
        self._write_managed_shell_block(Path.home() / ".zshenv", "system-locale", shell_block)


    def _apply_session_locale_env(self, locale_code: str) -> None:
        locale_value = str(locale_code).strip()
        language_value = locale_value.split(".", 1)[0].split("_", 1)[0] or locale_value
        os.environ["LANG"] = locale_value
        os.environ["LANGUAGE"] = language_value
        os.environ.pop("LC_ALL", None)
        try:
            pylocale.setlocale(pylocale.LC_ALL, locale_value)
        except Exception:
            pass
        env = {"LANG": locale_value, "LANGUAGE": language_value}
        for command in (
            ["dbus-update-activation-environment", "--systemd", f"LANG={locale_value}", f"LANGUAGE={language_value}"],
            ["systemctl", "--user", "import-environment", "LANG", "LANGUAGE"],
        ):
            try:
                subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, **env})
            except Exception:
                pass


    def _apply_system_locale_privileged(self, locale_code: str) -> bool:
        locale_value = str(locale_code).strip()
        if not locale_value or not polkit_available():
            return False
        if shutil.which("localectl"):
            if run_with_polkit(
                ["localectl", "set-locale", f"LANG={locale_value}"],
                detached=False,
                timeout=120,
            ):
                return True
        if shutil.which("update-locale"):
            if run_with_polkit(
                ["update-locale", f"LANG={locale_value}"],
                detached=False,
                timeout=120,
            ):
                return True
        shell_script = (
            f'printf \'LANG="{locale_value}"\\n\' > /etc/locale.conf\n'
            f'printf \'LANG="{locale_value}"\\n\' > /etc/default/locale\n'
        )
        return run_with_polkit(
            ["bash", "-lc", shell_script],
            detached=False,
            timeout=120,
        )


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
        locale_code = str(region.get("locale_code", "")).strip()
        if locale_code:
            self._apply_user_locale_files(locale_code)
            self._apply_session_locale_env(locale_code)
            if polkit_available():
                QMessageBox.information(
                    self,
                    "Apply system locale",
                    "Hanauta will now request your password through Polkit to apply this locale system-wide.",
                )
            privileged_ok = self._apply_system_locale_privileged(locale_code)
        else:
            privileged_ok = False
        if hasattr(self, "region_status"):
            locale_label = locale_code or "system default"
            keyboard_label = str(region.get("keyboard_layout", "us")).strip() or "us"
            if locale_code:
                if privileged_ok:
                    message = f"System locale applied as {locale_label} • keyboard {keyboard_label}."
                else:
                    message = f"Locale saved as {locale_label} for new sessions and terminals • keyboard {keyboard_label}."
            else:
                message = f"Region settings saved for {locale_label} • keyboard {keyboard_label}."
            self.region_status.setText(message)
        if locale_code and not privileged_ok and not polkit_available():
            QMessageBox.warning(
                self,
                "System locale not elevated",
                "pkexec is unavailable, so Hanauta saved the locale for your user session only. Install or enable Polkit to apply it system-wide.",
            )
        if locale_code:
            QMessageBox.information(
                self,
                "Locale change applied",
                "Locale changes are saved now. Open new terminal windows to pick it up immediately. For full system-wide effect across all apps, sign out and sign back in (or reboot).",
            )


