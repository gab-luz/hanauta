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


class ServicesMixin:
    """Service launcher cards methods for NotificationCenter."""

    def _build_vpn_launcher_card(self) -> QFrame:
        self.vpn_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.vpn.title"),
            t("service.vpn.detail"),
            "lock",
            t("service.vpn.action"),
            self._open_vpn_widget,
        )
        return self.vpn_launcher_card


    def _build_christian_launcher_card(self) -> QFrame:
        self.christian_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.christian.title"),
            t("service.christian.detail"),
            "auto_awesome",
            t("service.christian.action"),
            self._open_christian_widget,
        )
        return self.christian_launcher_card


    def _build_reminders_launcher_card(self) -> QFrame:
        self.reminders_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.reminders.title"),
            t("service.reminders.detail"),
            "notifications",
            t("service.reminders.action"),
            self._open_reminders_widget,
        )
        return self.reminders_launcher_card


    def _build_pomodoro_launcher_card(self) -> QFrame:
        self.pomodoro_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.pomodoro.title"),
            t("service.pomodoro.detail"),
            "timer",
            t("service.pomodoro.action"),
            self._open_pomodoro_widget,
        )
        return self.pomodoro_launcher_card


    def _build_rss_launcher_card(self) -> QFrame:
        self.rss_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.rss.title"),
            t("service.rss.detail"),
            "public",
            t("service.rss.action"),
            self._open_rss_widget,
        )
        return self.rss_launcher_card


    def _build_obs_launcher_card(self) -> QFrame:
        self.obs_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.obs.title"),
            t("service.obs.detail"),
            "videocam",
            t("service.obs.action"),
            self._open_obs_widget,
        )
        return self.obs_launcher_card


    def _build_crypto_launcher_card(self) -> QFrame:
        self.crypto_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.crypto.title"),
            t("service.crypto.detail"),
            "show_chart",
            t("service.crypto.action"),
            self._open_crypto_widget,
        )
        return self.crypto_launcher_card


    def _build_vps_launcher_card(self) -> QFrame:
        self.vps_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.vps.title"),
            t("service.vps.detail"),
            "storage",
            t("service.vps.action"),
            self._open_vps_widget,
        )
        return self.vps_launcher_card


    def _build_desktop_clock_launcher_card(self) -> QFrame:
        self.desktop_clock_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.desktop_clock.title"),
            t("service.desktop_clock.detail"),
            "watch",
            t("service.desktop_clock.action"),
            self._open_desktop_clock_widget,
        )
        return self.desktop_clock_launcher_card


    def _build_game_mode_launcher_card(self) -> QFrame:
        self.game_mode_launcher_card = ServiceLauncherCard(
            self.material_font,
            t("service.game_mode.title"),
            t("service.game_mode.detail"),
            "sports_esports",
            t("service.game_mode.action"),
            self._open_game_mode_popup,
        )
        return self.game_mode_launcher_card


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
        if hasattr(self, "vpn_launcher_card"):
            self.vpn_launcher_card.setVisible(
                self._service_visible_in_notification_center("vpn_control")
            )
        if hasattr(self, "christian_launcher_card"):
            self.christian_launcher_card.setVisible(
                self._service_visible_in_notification_center("christian_widget")
            )
        if hasattr(self, "reminders_launcher_card"):
            self.reminders_launcher_card.setVisible(
                self._service_visible_in_notification_center("reminders_widget")
            )
        if hasattr(self, "pomodoro_launcher_card"):
            self.pomodoro_launcher_card.setVisible(
                self._service_visible_in_notification_center("pomodoro_widget")
            )
        if hasattr(self, "rss_launcher_card"):
            self.rss_launcher_card.setVisible(
                self._service_visible_in_notification_center("rss_widget")
            )
        if hasattr(self, "obs_launcher_card"):
            self.obs_launcher_card.setVisible(
                self._service_visible_in_notification_center("obs_widget")
            )
        if hasattr(self, "crypto_launcher_card"):
            self.crypto_launcher_card.setVisible(
                self._service_visible_in_notification_center("crypto_widget")
            )
        if hasattr(self, "vps_launcher_card"):
            self.vps_launcher_card.setVisible(
                self._service_visible_in_notification_center("vps_widget")
            )
        if hasattr(self, "desktop_clock_launcher_card"):
            self.desktop_clock_launcher_card.setVisible(
                self._service_visible_in_notification_center("desktop_clock_widget")
            )
        if hasattr(self, "game_mode_launcher_card"):
            self.game_mode_launcher_card.setVisible(
                self._service_visible_in_notification_center("game_mode")
            )


    def _open_vpn_widget(self) -> None:
        if not self._service_enabled("vpn_control") or not VPN_CONTROL_SCRIPT.exists():
            return
        run_bg_singleton(VPN_CONTROL_SCRIPT)


    def _open_christian_widget(self) -> None:
        if (
            not self._service_enabled("christian_widget")
            or not CHRISTIAN_WIDGET_SCRIPT.exists()
        ):
            return
        run_bg_singleton(CHRISTIAN_WIDGET_SCRIPT)


    def _open_reminders_widget(self) -> None:
        if (
            not self._service_enabled("reminders_widget")
            or not REMINDERS_WIDGET_SCRIPT.exists()
        ):
            return
        run_bg_singleton(REMINDERS_WIDGET_SCRIPT)


    def _open_pomodoro_widget(self) -> None:
        if (
            not self._service_enabled("pomodoro_widget")
            or not POMODORO_WIDGET_SCRIPT.exists()
        ):
            return
        run_bg_singleton(POMODORO_WIDGET_SCRIPT)


    def _open_rss_widget(self) -> None:
        rss_widget_script = resolve_rss_widget_script(self.settings_state)
        if not self._service_enabled("rss_widget") or not rss_widget_script.exists():
            return
        run_bg_singleton(rss_widget_script)


    def _open_obs_widget(self) -> None:
        if not self._service_enabled("obs_widget") or not OBS_WIDGET_SCRIPT.exists():
            return
        run_bg_singleton(OBS_WIDGET_SCRIPT)


    def _open_crypto_widget(self) -> None:
        if (
            not self._service_enabled("crypto_widget")
            or not CRYPTO_WIDGET_SCRIPT.exists()
        ):
            return
        run_bg_singleton(CRYPTO_WIDGET_SCRIPT)


    def _open_vps_widget(self) -> None:
        if not self._service_enabled("vps_widget") or not VPS_WIDGET_SCRIPT.exists():
            return
        run_bg_singleton(VPS_WIDGET_SCRIPT)


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
        if (
            not self._service_enabled("game_mode")
            or not GAME_MODE_POPUP_SCRIPT.exists()
        ):
            return
        run_bg_singleton(GAME_MODE_POPUP_SCRIPT)


