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


class SettingsPageMixin:
    """Settings page methods for NotificationCenter."""

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("settingsContentWrap")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(10)

        title = QLabel(t("settings.moved.title"))
        title.setObjectName("settingsSectionTitle")
        card_layout.addWidget(title)

        subtitle = QLabel(
            t("settings.moved.subtitle")
        )
        subtitle.setObjectName("settingsSectionSubtitle")
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)

        open_button = QPushButton(t("settings.moved.btn"))
        open_button.setObjectName("softButton")
        open_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_button.clicked.connect(self._open_settings)
        card_layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignLeft)
        card_layout.addStretch(1)

        layout.addWidget(card)
        return page


    def _build_settings_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel(t("settings.overview.title"))
        header.setObjectName("settingsSectionTitle")
        sub = QLabel(t("settings.overview.subtitle"))
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)
        self.system_overview_grid = QGridLayout()
        self.system_overview_grid.setContentsMargins(0, 8, 0, 0)
        self.system_overview_grid.setHorizontalSpacing(12)
        self.system_overview_grid.setVerticalSpacing(12)
        self.system_overview_labels: dict[str, QLabel] = {}
        for index, key in enumerate(
            (t("metric.host"), t("metric.kernel"), t("metric.session"), t("metric.python"), t("metric.uptime"), t("metric.screen"))
        ):
            label = QLabel("...")
            label.setObjectName("metricValue")
            self.system_overview_labels[key] = label
            self.system_overview_grid.addWidget(
                self._metric_block(key, label), index // 2, index % 2
            )
        layout.addLayout(self.system_overview_grid)
        layout.addStretch(1)
        return page


    def _build_settings_appearance_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel(t("settings.appearance.title"))
        header.setObjectName("settingsSectionTitle")
        sub = QLabel(t("settings.appearance.subtitle"))
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)
        self.appearance_status = QLabel("")
        self.appearance_status.setObjectName("statusHint")
        layout.addWidget(self.appearance_status)

        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 0)
        row.setSpacing(10)
        self.appearance_buttons: dict[str, QPushButton] = {}
        for key in ("orchid", "mint", "sunset"):
            button = QPushButton(key.title())
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.setObjectName("appearancePreset")
            button.clicked.connect(
                lambda checked=False, current=key: self._set_accent(current)
            )
            self.appearance_buttons[key] = button
            row.addWidget(button)
        layout.addLayout(row)
        layout.addStretch(1)
        return page


    def _build_settings_homeassistant_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel(t("settings.ha.title"))
        header.setObjectName("settingsSectionTitle")
        sub = QLabel(
            t("settings.ha.subtitle")
        )
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)

        self.ha_url_input = QLineEdit(
            self.settings_state["home_assistant"].get("url", "")
        )
        self.ha_url_input.setPlaceholderText(t("settings.ha.placeholder_url"))
        self.ha_url_input.setObjectName("settingsInput")
        self.ha_token_input = QLineEdit(
            self.settings_state["home_assistant"].get("token", "")
        )
        self.ha_token_input.setPlaceholderText(t("settings.ha.placeholder_token"))
        self.ha_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ha_token_input.setObjectName("settingsInput")
        layout.addWidget(self._settings_field(t("settings.ha.server_url"), self.ha_url_input))
        layout.addWidget(self._settings_field(t("settings.ha.token"), self.ha_token_input))

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        self.ha_save_btn = self._soft_button(t("settings.ha.btn_save"))
        self.ha_save_btn.clicked.connect(self._save_home_assistant_settings)
        self.ha_refresh_btn = self._soft_button(t("settings.ha.btn_fetch"))
        self.ha_refresh_btn.clicked.connect(self._refresh_home_assistant_entities)
        buttons.addWidget(self.ha_save_btn)
        buttons.addWidget(self.ha_refresh_btn)
        layout.addLayout(buttons)

        self.ha_settings_status = QLabel(t("settings.ha.hint_pin"))
        self.ha_settings_status.setObjectName("statusHint")
        layout.addWidget(self.ha_settings_status)

        scroll = QScrollArea()
        scroll.setObjectName("entityScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.ha_entity_container = QWidget()
        self.ha_entity_layout = QVBoxLayout(self.ha_entity_container)
        self.ha_entity_layout.setContentsMargins(0, 0, 0, 0)
        self.ha_entity_layout.setSpacing(8)
        self.ha_entity_layout.addStretch(1)
        scroll.setWidget(self.ha_entity_container)
        layout.addWidget(scroll, 1)
        return page


    def _open_settings(self) -> None:
        self._launch_settings_page("overview")


    def _show_overview_page(self) -> None:
        self._apply_window_mode("compact")
        self.page_stack.setCurrentWidget(self.overview_page)


    def _show_settings_section(self, key: str) -> None:
        if not hasattr(self, "settings_stack") or not self.settings_nav_buttons:
            self._launch_settings_page(
                key if key in {"overview", "appearance"} else "services"
            )
            return
        order = {"overview": 0, "appearance": 1, "homeassistant": 2}
        self.settings_stack.setCurrentIndex(order.get(key, 0))
        for button_key, button in self.settings_nav_buttons.items():
            button.apply_state(
                button_key == key,
                self.current_accent["accent"],
                self.current_accent["on_accent"],
                self.theme_palette,
            )


    def _open_settings_homeassistant(self) -> None:
        self._launch_settings_page("services")


    def _open_powermenu(self) -> None:
        if not POWERMENU_SCRIPT.exists():
            return
        run_bg_singleton(POWERMENU_SCRIPT)
        self.hide()


    def _launch_settings_page(self, page: str, service_section: str = "") -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        args = ["--page", page]
        if service_section:
            args.extend(["--service-section", service_section])
        try:
            subprocess.Popen(
                [python_executable(), str(SETTINGS_PAGE_SCRIPT), *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass


    def _set_accent(self, key: str) -> None:
        self.settings_state["appearance"]["accent"] = key
        self.current_accent = accent_palette(key)
        save_notification_settings(self.settings_state)
        if self.appearance_status is not None:
            self.appearance_status.setText(f"Accent updated to {key.title()}.")
        self._apply_styles()
        self._apply_media_palette()
        if hasattr(self, "settings_stack"):
            self._show_settings_section("appearance")


