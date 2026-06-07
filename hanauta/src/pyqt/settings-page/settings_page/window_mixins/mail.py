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







class MailMixin:
    """Extracted methods for mail."""

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


    def _save_mail_api_key_setting(self) -> None:
        if not hasattr(self, "mail_api_key_input"):
            return
        value = str(self.mail_api_key_input.text() or "").strip()
        try:
            save_email_client_api_key(value)
        except Exception as exc:
            if hasattr(self, "mail_status"):
                self.mail_status.setText(f"Failed to save email API key: {exc}")
            return
        if hasattr(self, "mail_status"):
            self.mail_status.setText("Email API key saved.")


    def _generate_mail_api_key_setting(self) -> None:
        if not hasattr(self, "mail_api_key_input"):
            return
        self.mail_api_key_input.setText(secrets.token_urlsafe(32))
        self._save_mail_api_key_setting()


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


