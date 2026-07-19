from __future__ import annotations

from PyQt6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTextCharFormat, QPalette
from PyQt6.QtWidgets import QApplication, QButtonGroup, QDialog, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget, QVBoxLayout, QWidget

from app_locale import t
from notif_center.ha import *
from notif_center.game_carousel import *
from notif_center.paths import *
from notif_center.poller import *
from notif_center.settings_io import *
from notif_center.utils import *
from notif_center.widgets import *
from pyqt.shared.calendar_card import *
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family
from pyqt.shared.runtime import entry_command, entry_patterns, python_executable
from notif_center.plugin_paths import (
    VPN_CONTROL_SCRIPT, CHRISTIAN_WIDGET_SCRIPT, REMINDERS_WIDGET_SCRIPT,
    POMODORO_WIDGET_SCRIPT, OBS_WIDGET_SCRIPT, CRYPTO_WIDGET_SCRIPT,
    VPS_WIDGET_SCRIPT, GAME_MODE_POPUP_SCRIPT, resolve_rss_widget_script,
)

_SERVICE_DESCRIPTORS = (
    {"key": "vpn_control", "attr": "vpn_launcher_card", "title": "service.vpn.title", "detail": "service.vpn.detail", "icon": "lock", "action": "service.vpn.action", "open": "_open_vpn_widget"},
    {"key": "christian_widget", "attr": "christian_launcher_card", "title": "service.christian.title", "detail": "service.christian.detail", "icon": "auto_awesome", "action": "service.christian.action", "open": "_open_christian_widget"},
    {"key": "reminders_widget", "attr": "reminders_launcher_card", "title": "service.reminders.title", "detail": "service.reminders.detail", "icon": "notifications", "action": "service.reminders.action", "open": "_open_reminders_widget"},
    {"key": "pomodoro_widget", "attr": "pomodoro_launcher_card", "title": "service.pomodoro.title", "detail": "service.pomodoro.detail", "icon": "timer", "action": "service.pomodoro.action", "open": "_open_pomodoro_widget"},
    {"key": "rss_widget", "attr": "rss_launcher_card", "title": "service.rss.title", "detail": "service.rss.detail", "icon": "public", "action": "service.rss.action", "open": "_open_rss_widget"},
    {"key": "obs_widget", "attr": "obs_launcher_card", "title": "service.obs.title", "detail": "service.obs.detail", "icon": "videocam", "action": "service.obs.action", "open": "_open_obs_widget"},
    {"key": "crypto_widget", "attr": "crypto_launcher_card", "title": "service.crypto.title", "detail": "service.crypto.detail", "icon": "show_chart", "action": "service.crypto.action", "open": "_open_crypto_widget"},
    {"key": "vps_widget", "attr": "vps_launcher_card", "title": "service.vps.title", "detail": "service.vps.detail", "icon": "storage", "action": "service.vps.action", "open": "_open_vps_widget"},
    {"key": "desktop_clock_widget", "attr": "desktop_clock_launcher_card", "title": "service.desktop_clock.title", "detail": "service.desktop_clock.detail", "icon": "watch", "action": "service.desktop_clock.action", "open": "_open_desktop_clock_widget"},
    {"key": "game_mode", "attr": "game_mode_launcher_card", "title": "service.game_mode.title", "detail": "service.game_mode.detail", "icon": "sports_esports", "action": "service.game_mode.action", "open": "_open_game_mode_popup"},
)

_SERVICE_BY_ATTR = {d["attr"]: d for d in _SERVICE_DESCRIPTORS}


class ServicesMixin:
    """Service launcher cards methods for NotificationCenter."""

    def _build_launcher_card(self, desc: dict) -> QFrame:
        card = ServiceLauncherCard(
            self.material_font,
            t(desc["title"]),
            t(desc["detail"]),
            desc["icon"],
            t(desc["action"]),
            getattr(self, desc["open"]),
        )
        setattr(self, desc["attr"], card)
        return card

    def _build_vpn_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["vpn_launcher_card"])

    def _build_christian_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["christian_launcher_card"])

    def _build_reminders_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["reminders_launcher_card"])

    def _build_pomodoro_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["pomodoro_launcher_card"])

    def _build_rss_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["rss_launcher_card"])

    def _build_obs_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["obs_launcher_card"])

    def _build_crypto_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["crypto_launcher_card"])

    def _build_vps_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["vps_launcher_card"])

    def _build_desktop_clock_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["desktop_clock_launcher_card"])

    def _build_game_mode_launcher_card(self) -> QFrame:
        return self._build_launcher_card(_SERVICE_BY_ATTR["game_mode_launcher_card"])

    def _settings_field(self, label_text: str, widget: QWidget) -> QWidget:
        wrap = QWidget()
        row = QVBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        row.addWidget(label)
        row.addWidget(widget)
        return wrap

    def _metric_block(self, title: str, value_label: QLabel) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("metricCard")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("metricLabel")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return wrap

    def _soft_button(self, title: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("softButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        return button

    def _service_enabled(self, key: str) -> bool:
        return bool(
            self.settings_state.get("services", {}).get(key, {}).get("enabled", True)
        )

    def _service_visible_in_notification_center(self, key: str) -> bool:
        service = self.settings_state.get("services", {}).get(key, {})
        return bool(
            service.get("enabled", True)
            and service.get("show_in_notification_center", False)
        )

    def _sync_service_card_visibility(self) -> None:
        if hasattr(self, "ha_card"):
            self.ha_card.setVisible(
                self._service_visible_in_notification_center("home_assistant")
            )
        for desc in _SERVICE_DESCRIPTORS:
            card = getattr(self, desc["attr"], None)
            if card is not None:
                card.setVisible(
                    self._service_visible_in_notification_center(desc["key"])
                )

    def _open_standard_widget(self, key: str, script) -> None:
        if not self._service_enabled(key) or not script.exists():
            return
        run_bg_singleton(script)

    def _open_vpn_widget(self) -> None:
        self._open_standard_widget("vpn_control", VPN_CONTROL_SCRIPT)

    def _open_christian_widget(self) -> None:
        self._open_standard_widget("christian_widget", CHRISTIAN_WIDGET_SCRIPT)

    def _open_reminders_widget(self) -> None:
        self._open_standard_widget("reminders_widget", REMINDERS_WIDGET_SCRIPT)

    def _open_pomodoro_widget(self) -> None:
        self._open_standard_widget("pomodoro_widget", POMODORO_WIDGET_SCRIPT)

    def _open_rss_widget(self) -> None:
        rss_widget_script = resolve_rss_widget_script(self.settings_state)
        if not self._service_enabled("rss_widget") or not rss_widget_script.exists():
            return
        run_bg_singleton(rss_widget_script)

    def _open_obs_widget(self) -> None:
        self._open_standard_widget("obs_widget", OBS_WIDGET_SCRIPT)

    def _open_crypto_widget(self) -> None:
        self._open_standard_widget("crypto_widget", CRYPTO_WIDGET_SCRIPT)

    def _open_vps_widget(self) -> None:
        self._open_standard_widget("vps_widget", VPS_WIDGET_SCRIPT)

    def _open_desktop_clock_widget(self) -> None:
        if not self._service_enabled("desktop_clock_widget"):
            return
        command = desktop_clock_command()
        if not command:
            return
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    def _open_game_mode_popup(self) -> None:
        self._open_standard_widget("game_mode", GAME_MODE_POPUP_SCRIPT)
