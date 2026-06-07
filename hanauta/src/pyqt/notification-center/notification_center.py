#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt6 notification center rebuilt from idea.html.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import signal
import sys
import tempfile
import threading
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from time import monotonic
from urllib import error, parse, request

from PyQt6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QCursor, QFont, QFontDatabase, QIcon, QPalette,
    QPainter, QPainterPath, QPen, QPixmap, QTextCharFormat,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QFrame,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QStackedWidget, QVBoxLayout, QWidget,
)

from notif_center.poller import (
    BackgroundPoller, PollResult, get_cached_pixmap, get_static_val, store_pixmap,
)
from notif_center.game_carousel import (
    GameCarouselCard, any_game_running_fast, load_cached_game_slides,
    load_cached_games_payload, load_lutris_game_slides, load_steam_game_slides,
)
from notif_center.ha import fetch_home_assistant_json, post_home_assistant_json, normalize_ha_url

from notif_center.paths import (
    ASSETS_DIR, ARROW_BACK_ICON, BIN_DIR, CALENDAR_EVENTS_CACHE,
    CALENDAR_NOTIFICATION_ICON, CAFFEINE_NOTIFICATION_ICON,
    DESKTOP_CLOCK_BINARY, FALLBACK_COVER, FONTS_DIR, GAMES_CACHE_PATH,
    HISTORY_ICON, HOME_ASSISTANT_ICON, KDECONNECT_ICON,
    LUTRIS_COVERART_DIRS, LUTRIS_DB, LUTRIS_ICON,
    NIGHT_LIGHT_NOTIFICATION_ICON, NOTIFICATION_HISTORY_FILE,
    POWERMENU_SCRIPT, PROFILE_PHOTO_CANDIDATES,
    ROOT, SCRIPTS_DIR, SERVICE_STATE_DIR, SETTINGS_FILE,
    SETTINGS_PAGE_SCRIPT, STATE_DIR, STEAM_ICON, WEATHER_HISTORY_ICON,
)
from app_locale import t
from notif_center.settings_io import (
    DEFAULT_SERVICE_SETTINGS, load_notification_settings,
    merged_service_settings, save_notification_settings,
)
from notif_center.utils import (
    accent_palette, apply_antialias_font, desktop_clock_command,
    detect_font, format_millis, format_playtime_hours, load_app_fonts,
    material_icon, notification_control_command, parse_bool_text,
    render_svg_pixmap, render_theme_icon_pixmap, run_bg,
    run_bg_singleton, run_cmd, run_script, run_script_bg,
    terminate_background_matches, tinted_svg_pixmap,
)
from notif_center.widgets import (
    ActionTile, ClickableLabel, CompactIconAction, ElidedLabel,
    QuickSettingButton, ServiceLauncherCard, SidebarItemButton,
)
from notif_center.sections.theme import ThemeMixin
from notif_center.sections.quick_settings import QuickSettingsMixin
from notif_center.sections.services import ServicesMixin
from notif_center.sections.notifications import NotificationsMixin
from notif_center.sections.calendar import CalendarMixin
from notif_center.sections.media import MediaMixin
from notif_center.sections.games import GamesMixin
from notif_center.sections.home_assistant import HomeAssistantMixin
from notif_center.sections.settings_page import SettingsPageMixin
from notif_center.sections.profile import ProfileMixin
from notif_center.app_helpers import load_calendar_events, load_notification_history

APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command, entry_patterns, python_executable
from pyqt.shared.app_logging import init_app_logging
from pyqt.shared.plugin_runtime import resolve_plugin_script
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family
from pyqt.shared.calendar_card import apply_calendar_theme, build_calendar_card

def _resolve_qcal_wrapper_script() -> Path | None:
    resolved = resolve_plugin_script("qcal-wrapper.py", ["calendar"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-calendar" / "qcal-wrapper.py",
        Path.home() / "dev" / "hanauta-plugin-calendar" / "qcal-wrapper.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None

QCAL_WRAPPER = _resolve_qcal_wrapper_script() or Path()

VPN_CONTROL_SCRIPT = resolve_plugin_script("vpn_control.py", ["vpn-control", "vpn"]) or Path()
CHRISTIAN_WIDGET_SCRIPT = resolve_plugin_script("christian_widget.py", ["religion-christian", "christian"]) or Path()
REMINDERS_WIDGET_SCRIPT = resolve_plugin_script("reminders_widget.py", ["reminders"]) or Path()
POMODORO_WIDGET_SCRIPT = resolve_plugin_script("pomodoro_widget.py", ["pomodoro"]) or Path()
RSS_WIDGET_SCRIPT = resolve_plugin_script("rss_widget.py", ["rss"]) or Path()
OBS_WIDGET_SCRIPT: Path | None = resolve_plugin_script("obs_widget.py", ["obs"])
CRYPTO_WIDGET_SCRIPT: Path | None = resolve_plugin_script("crypto_widget.py", ["crypto"])
VPS_WIDGET_SCRIPT: Path | None = resolve_plugin_script("vps_widget.py", ["vps"])

def _resolve_desktop_clock_widget_script() -> Path | None:
    resolved = resolve_plugin_script("desktop_clock_widget.py", ["desktop-clock", "clock"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-desktop-clock" / "desktop_clock_widget.py",
        Path.home() / "dev" / "hanauta-plugin-desktop-clock" / "desktop_clock_widget.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None

DESKTOP_CLOCK_WIDGET_SCRIPT: Path | None = _resolve_desktop_clock_widget_script()
GAME_MODE_POPUP_SCRIPT: Path | None = resolve_plugin_script("game_mode_popup.py", ["game-mode", "gamemode"])

def resolve_rss_widget_script(settings_state: dict | None = None) -> Path:
    if RSS_WIDGET_SCRIPT.exists():
        return RSS_WIDGET_SCRIPT
    state = settings_state if isinstance(settings_state, dict) else {}
    marketplace = state.get("marketplace", {}) if isinstance(state, dict) else {}
    installed = marketplace.get("installed_plugins", []) if isinstance(marketplace, dict) else []
    if isinstance(installed, list):
        for row in installed:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if plugin_id != "rss_widget":
                continue
            install_path = str(row.get("install_path", "")).strip()
            if not install_path:
                continue
            candidate = Path(install_path).expanduser() / "rss_widget.py"
            if candidate.exists():
                return candidate
    return RSS_WIDGET_SCRIPT

class NotificationCenter(
    QWidget,
    ThemeMixin,
    QuickSettingsMixin,
    ServicesMixin,
    NotificationsMixin,
    CalendarMixin,
    MediaMixin,
    GamesMixin,
    HomeAssistantMixin,
    SettingsPageMixin,
    ProfileMixin,
):
    calendarEventsReady = pyqtSignal(list)
    gameSlidesReady = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.material_font = detect_font(
            self.loaded_fonts.get("material_icons", ""),
            self.loaded_fonts.get("material_icons_outlined", ""),
            self.loaded_fonts.get("material_symbols_outlined", ""),
            self.loaded_fonts.get("material_symbols_rounded", ""),
            "Material Icons",
            "Material Icons Outlined",
            "Material Symbols Outlined",
            "Material Symbols Rounded",
        )
        self.ui_font = detect_font(
            theme_font_family("ui"),
            "Rubik",
            self.loaded_fonts.get("ui_sans", ""),
            "Inter",
            "Noto Sans",
            "Sans Serif",
        )
        self.mono_font = detect_font(
            theme_font_family("mono"),
            "JetBrains Mono",
            "JetBrainsMono Nerd Font",
            "DejaVu Sans Mono",
        )
        self._panel_animation: QPropertyAnimation | None = None
        self._syncing_sliders = False
        self._pending_brightness = 0
        self._pending_volume = 0
        self._media_player = ""
        self._media_duration_ms = 0
        self._media_position_ms = 0
        self._media_status = "Stopped"
        self._media_track_key = ""
        self._media_last_sync = monotonic()
        self._media_estimated_progress = False
        self._media_url = ""
        self._media_last_anchor_time = 0.0
        self._media_duration_cache: dict[str, int] = {}
        self._media_duration_pending: set[str] = set()
        self._calendar_events: list[dict] = []
        self._calendar_last_error = ""
        self._calendar_fetch_in_progress = False
        self._calendar_last_fetch = 0.0
        self._calendar_render_signature = ""
        self._calendar_event_dialogs: list[QDialog] = []
        self._games_cache_signature = ""
        self._game_slides_data: list[dict] = []
        self._games_any_playing = False
        self._notification_history: list[dict] = []
        self.settings_state = load_notification_settings()
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.current_accent = accent_palette(
            self.settings_state["appearance"].get("accent", "orchid")
        )
        if self.theme_palette.use_matugen:
            self.current_accent = {
                "accent": self.theme_palette.primary,
                "on_accent": self.theme_palette.active_text,
                "soft": self.theme_palette.accent_soft,
            }
        self._ha_entities: list[dict] = []
        self._ha_entity_map: dict[str, dict] = {}
        self._ha_last_error = ""
        self._avatar_source: Path | None = None
        self._avatar_mtime_ns = -1
        self._poll_result: PollResult | None = None
        self._notif_mtime_ns = 0
        self._in_full_history_view = False
        self._notif_widgets: list[QWidget] = []
        self._system_overview_done = False
        self.system_overview_labels: dict[str, QLabel] = {}
        self.settings_nav_buttons: dict[str, SidebarItemButton] = {}
        self.appearance_buttons: dict[str, QPushButton] = {}
        self.appearance_status: QLabel | None = None
        self.ha_url_input: QLineEdit | None = None
        self.ha_token_input: QLineEdit | None = None
        self.ha_settings_status: QLabel | None = None
        self.ha_summary_label: QLabel | None = None
        self.ha_status_label: QLabel | None = None

        self._brightness_commit_timer = QTimer(self)
        self._brightness_commit_timer.setSingleShot(True)
        self._brightness_commit_timer.timeout.connect(self._commit_brightness)

        self._volume_commit_timer = QTimer(self)
        self._volume_commit_timer.setSingleShot(True)
        self._volume_commit_timer.timeout.connect(self._commit_volume)

        self._build_window()
        self._build_ui()
        self.calendarEventsReady.connect(self._apply_calendar_events)
        self.gameSlidesReady.connect(self._apply_game_slides)
        apply_antialias_font(self)
        self._apply_styles()
        self._apply_media_palette()
        self._start_polls()

    def _build_window(self) -> None:
        self.setWindowTitle(t("window.title"))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.screen_geo = QApplication.primaryScreen().availableGeometry()
        self.compact_size = (884, min(804, self.screen_geo.height() - 72))
        self.settings_size = (
            min(864, self.screen_geo.width() - 72),
            self.compact_size[1],
        )
        self._apply_window_mode("compact")

    def _apply_window_mode(self, mode: str) -> None:
        if mode == "settings":
            width, height = self.settings_size
        else:
            width, height = self.compact_size
        self.resize(width, height)
        self.move(
            self.screen_geo.center().x() - self.width() // 2, self.screen_geo.y() + 28
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.panel = QFrame()
        self.panel.setObjectName("glassPanel")
        self.panel_effect = QGraphicsOpacityEffect(self.panel)
        self.panel.setGraphicsEffect(self.panel_effect)
        self.panel_effect.setOpacity(0.0)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(0)
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.overview_page = self._build_overview_page()
        self.settings_page = self._build_settings_page()
        self.page_stack.addWidget(self.overview_page)
        self.page_stack.addWidget(self.settings_page)
        panel_layout.addWidget(self.page_stack)

        root.addWidget(self.panel)

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addLayout(self._build_header())

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(10)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(self._build_quick_settings_card())
        left_layout.addWidget(self._build_compact_sliders_card())
        left_layout.addWidget(self._build_media_card())
        left_layout.addWidget(self._build_game_carousel_card())
        left_layout.addWidget(self._build_phone_card())
        left_layout.addWidget(self._build_home_assistant_card())
        left_layout.addStretch(1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(self._build_calendar_card())
        right_layout.addWidget(self._build_events_card(), 1)
        right_layout.addWidget(self._build_notifications_card(), 1)

        columns.addWidget(left, 11)
        columns.addWidget(right, 9)
        layout.addLayout(columns, 1)
        self._sync_service_card_visibility()
        return page

    def _section_shell(
        self, title: str, subtitle: str, object_name: str = "overviewSection"
    ) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName(object_name)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("sectionSubtitle")
        subtitle_label.setWordWrap(True)
        subtitle_label.setVisible(bool(subtitle.strip()))
        header.addWidget(title_label)
        header.addWidget(subtitle_label)
        layout.addLayout(header)
        return card, layout

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left = QHBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)

        self.avatar = ClickableLabel(self._open_profile_photo_picker)
        self.avatar.setObjectName("avatar")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFixedSize(42, 42)
        self.avatar.setFont(QFont(self.material_font, 24))
        self.avatar.setProperty("hasPhoto", False)
        self._refresh_profile_avatar(force=True)

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)
        self.user_label = QLabel(t("overview.header.user"))
        self.user_label.setObjectName("userLabel")
        self.uptime_label = QLabel(t("uptime.less_than_minute"))
        self.uptime_label.setObjectName("uptimeLabel")
        self.uptime_label.setFont(QFont(self.mono_font, 9))
        text_wrap.addWidget(self.user_label)
        text_wrap.addWidget(self.uptime_label)

        left.addWidget(self.avatar)
        left.addLayout(text_wrap)

        right = QHBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        self.settings_btn = self._circle_icon_button("settings", rounded_rect=True)
        self.settings_btn.clicked.connect(self._open_settings)
        self.power_btn = self._circle_icon_button(
            "power_settings_new", accent="power", rounded_rect=True
        )
        self.power_btn.clicked.connect(self._open_powermenu)
        right.addWidget(self.settings_btn)
        right.addWidget(self.power_btn)

        layout.addLayout(left)
        layout.addStretch(1)
        layout.addLayout(right)
        return layout

    def _build_phone_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("infoCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        icon = QLabel()
        icon.setObjectName("sectionIcon")
        icon.setFixedWidth(20)
        icon.setPixmap(render_svg_pixmap(KDECONNECT_ICON, 18))
        self.phone_status_dot = QLabel("●")
        self.phone_status_dot.setObjectName("phoneStatusDot")
        self.phone_switch_btn = CompactIconAction(self.material_font, "chevron_right")
        self.phone_switch_btn.clicked.connect(
            lambda: run_script_bg("phone_info.sh", "--next")
        )
        self.phone_clipboard_btn = CompactIconAction(
            self.material_font, "content_paste"
        )
        self.phone_clipboard_btn.clicked.connect(
            lambda: run_script_bg("phone_info.sh", "--toggle-clip")
        )
        self.phone_name_value = QLabel(t("phone.disconnected"))
        self.phone_state_value = QLabel(t("phone.offline"))
        self.phone_battery_value = QLabel("0%")
        for label in (
            self.phone_name_value,
            self.phone_state_value,
            self.phone_battery_value,
        ):
            label.setObjectName("metricValue")
        self.phone_name_value.setObjectName("inlineMetricPrimary")
        self.phone_state_value.setObjectName("inlineMetric")
        self.phone_battery_value.setObjectName("inlineMetric")
        self.phone_name_value.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        layout.addWidget(icon)
        layout.addWidget(self.phone_name_value, 1)
        layout.addWidget(self.phone_state_value)
        layout.addWidget(self.phone_battery_value)
        layout.addWidget(self.phone_status_dot)
        layout.addWidget(self.phone_clipboard_btn)
        layout.addWidget(self.phone_switch_btn)
        return card

    def _circle_icon_button(
        self, icon: str, accent: str = "default", rounded_rect: bool = False
    ) -> QPushButton:
        button = QPushButton(material_icon(icon))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 18))
        button.setProperty("accent", accent)
        button.setProperty("roundedRect", rounded_rect)
        button.setObjectName("circleIconButton")
        button.setFixedSize(40, 40)
        return button

    def _plain_icon_button(self, icon: str) -> QPushButton:
        button = QPushButton(material_icon(icon))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 20))
        button.setObjectName("plainIconButton")
        button.setFixedSize(28, 28)
        return button

    def _start_polls(self) -> None:
        self._poller = BackgroundPoller()
        self._poller.pollComplete.connect(self._on_poll_complete)

        self.ha_timer = QTimer(self)
        self.ha_timer.timeout.connect(self._refresh_home_assistant_entities)
        self.ha_timer.start(15000)

        if hasattr(self, "media_card"):
            self.media_progress_timer = QTimer(self)
            self.media_progress_timer.timeout.connect(self._poll_media_progress)
            self.media_progress_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self.calendar_timer = QTimer(self)
        self.calendar_timer.timeout.connect(self._request_calendar_refresh)
        self.calendar_timer.start(30000)
        QTimer.singleShot(150, self._request_calendar_refresh)

        QTimer.singleShot(80, self._animate_in)

        self._poller.start()

    def _on_poll_complete(self, result: PollResult) -> None:
        self._poll_result = result
        self._poll_header()
        self._poll_quick_settings()
        self._poll_sliders()
        self._poll_media_metadata()
        if not self._system_overview_done:
            self._system_overview_done = True
            self._refresh_system_overview()
        self._poll_phone()
        self._render_calendar_events()
        self._poll_notification_history()
        self._render_home_assistant_tiles()

    def _poll_header(self) -> None:
        self.user_label.setText(os.environ.get("USER", t("overview.header.user")))
        r = self._poll_result
        self.uptime_label.setText(self._format_uptime(r.uptime_seconds if r else 0))
        self._refresh_profile_avatar()

    def _poll_phone(self) -> None:
        r = self._poll_result
        raw = r.phone_raw if r else ""
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}
        name = str(payload.get("name", t("phone.disconnected")))
        battery = str(payload.get("battery", "0"))
        status = str(payload.get("status", t("phone.offline")))
        clipboard = str(payload.get("clipboard", "off"))
        has_device = bool(payload.get("id")) and bool(payload.get("name"))
        if has_device:
            self.phone_name_value.setText(name)
            self.phone_state_value.setText(status)
            self.phone_battery_value.setText(f"{battery}%")
        else:
            self.phone_name_value.setText(t("phone.no_devices"))
            self.phone_state_value.setText("")
            self.phone_battery_value.setText("")
        self.phone_status_dot.setStyleSheet(
            f"color: {self.theme_palette.primary if has_device and status.lower() != 'offline' else self.theme_palette.workspace_empty};"
        )
        self.phone_clipboard_btn.set_active(has_device and clipboard == "on")
        self.phone_clipboard_btn.setEnabled(has_device)
        self.phone_switch_btn.setEnabled(has_device)

    def _refresh_system_overview(self) -> None:
        if not self.system_overview_labels:
            return
        metrics = {
            t("metric.host"): get_static_val("hostname", ["hostname"]) or t("metric.unknown"),
            t("metric.kernel"): get_static_val("kernel", ["uname", "-r"]) or t("metric.unknown"),
            t("metric.session"): os.environ.get("XDG_SESSION_DESKTOP", "i3"),
            t("metric.python"): sys.version.split()[0],
            t("metric.uptime"): self.uptime_label.text(),
            t("metric.screen"): f"{self.width()}x{self.height()}",
        }
        for key, value in metrics.items():
            label = self.system_overview_labels.get(key)
            if label is not None:
                label.setText(value)

    def _enable_dnd_after_warning(self) -> None:
        run_cmd(notification_control_command("set-paused", "true"))
        self._poll_quick_settings()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_media_card_layers()
        self._render_media_progress()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(rgba(self.theme_palette.panel_border, 0.92)), 1))
        painter.setBrush(QColor(rgba(self.theme_palette.panel_bg, 0.96)))
        painter.drawRoundedRect(rect, 28, 28)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._sync_media_card_layers()
        self._render_media_progress()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if hasattr(self, "_poller"):
            self._poller.stop()
            self._poller.wait(2000)
        super().closeEvent(event)


def main() -> int:
    init_app_logging("notification_center")
    logging.info("notification-center main starting")
    app = QApplication(sys.argv)
    app.setApplicationName(t("window.title"))

    signal.signal(signal.SIGINT, lambda sig, frame: app.quit())
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    window = NotificationCenter()
    window.show()
    logging.info("notification-center shown; entering event loop")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())