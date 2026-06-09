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







class MarketplaceMixin:
    """Extracted methods for marketplace."""

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


    def _permission_icon_asset_for_key(self, key: str) -> str | None:
        icon_file = ASSETS_DIR / f"permission-{key}.svg"
        if icon_file.exists():
            return str(icon_file)
        known = {
            "storage": "folder_open",
            "network": "public",
            "notifications": "notifications_active",
            "audio": "music_note",
            "input": "keyboard",
            "display": "desktop_windows",
            "shell": "terminal",
            "clipboard": "content_paste",
            "file_system": "description",
            "fs": "description",
            "fs_hosts": "description",
        }
        alt = known.get(key)
        if alt:
            candidate = ASSETS_DIR / f"permission-{alt}.svg"
            if candidate.exists():
                return str(candidate)
        return None


    def _permission_icon_for_key(self, key: str) -> str:
        icon_map = {
            "polkit": material_icon("shield"),
            "fullscreen_alert": material_icon("warning"),
            "fullscreen_overlay": material_icon("desktop_windows"),
            "i3_config": material_icon("tune"),
            "privileged": material_icon("lock"),
            "desktop_files": material_icon("widgets"),
            "storage": material_icon("storage"),
            "network": material_icon("public"),
            "notifications": material_icon("notifications_active"),
            "audio": material_icon("music_note"),
            "input": material_icon("keyboard"),
            "display": material_icon("desktop_windows"),
            "shell": material_icon("terminal"),
            "clipboard": material_icon("description"),
            "file_system": material_icon("description"),
            "fs": material_icon("description"),
            "fs_hosts": material_icon("description"),
        }
        key_lower = key.lower()
        return icon_map.get(key_lower, material_icon("lock"))


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
                "Update: preserve local changes, fast-forward, and reapply them if possible."
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
        install_dir_text = ""
        input_widget = getattr(self, "marketplace_install_dir_input", None)
        if input_widget is not None:
            install_dir_text = str(input_widget.text()).strip()
        if not install_dir_text:
            marketplace = self.settings_state.get("marketplace", {})
            if isinstance(marketplace, dict):
                install_dir_text = str(
                    marketplace.get("install_dir", str(ROOT / "hanauta" / "plugins"))
                ).strip()
        install_dir = Path(
            install_dir_text or str(ROOT / "hanauta" / "plugins")
        ).expanduser()
        install_dir.mkdir(parents=True, exist_ok=True)
        run_bg(["xdg-open", str(install_dir)])

