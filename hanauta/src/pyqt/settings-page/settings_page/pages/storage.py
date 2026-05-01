from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont, QIntValidator
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from settings_page.material_icons import material_icon
from settings_page.pages.metrics import build_metric_card
from settings_page.ui_widgets import SettingsRow, SwitchButton
from settings_page.widgets import IconLabel


def build_storage_page(window) -> QWidget:
    return window._scroll_page(build_storage_card(window))


def build_storage_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("contentCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    icon = IconLabel(material_icon("storage"), window.icon_font, 15, window.theme_palette.primary)
    icon.setFixedSize(22, 22)
    title = QLabel("Storage")
    title_font = QFont(window.display_font, 13)
    title_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    title.setFont(title_font)
    subtitle = QLabel(
        "Cache sizes, cleanup policies, wallpaper source data, and temporary Hanauta state."
    )
    subtitle.setFont(QFont(window.ui_font, 9))
    subtitle.setProperty("mutedText", True)
    title_wrap = QVBoxLayout()
    title_wrap.setContentsMargins(0, 0, 0, 0)
    title_wrap.setSpacing(2)
    title_wrap.addWidget(title)
    title_wrap.addWidget(subtitle)
    header.addWidget(icon)
    header.addLayout(title_wrap)
    header.addStretch(1)
    layout.addLayout(header)

    storage_state = window.settings_state.get("storage", {})
    if not isinstance(storage_state, dict):
        storage_state = {}
        window.settings_state["storage"] = storage_state

    window.storage_cache_cleanup_days_input = QLineEdit(
        str(int(storage_state.get("wallpaper_cache_cleanup_days", 30) or 30))
    )
    window.storage_cache_cleanup_days_input.setValidator(QIntValidator(1, 365, window))
    window.storage_cache_cleanup_days_input.setFixedWidth(96)
    window.storage_cache_cleanup_days_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(
        SettingsRow(
            material_icon("image"),
            "Wallpaper cache cleanup days",
            "Preferred retention window for wallpaper source caches and rendered wallpaper assets.",
            window.icon_font,
            window.ui_font,
            window.storage_cache_cleanup_days_input,
        )
    )

    window.storage_log_retention_days_input = QLineEdit(
        str(int(storage_state.get("log_retention_days", 14) or 14))
    )
    window.storage_log_retention_days_input.setValidator(QIntValidator(1, 365, window))
    window.storage_log_retention_days_input.setFixedWidth(96)
    window.storage_log_retention_days_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(
        SettingsRow(
            material_icon("schedule"),
            "Log retention days",
            "Preferred retention window for Hanauta logs and debugging traces.",
            window.icon_font,
            window.ui_font,
            window.storage_log_retention_days_input,
        )
    )

    window.storage_clean_temp_switch = SwitchButton(
        bool(storage_state.get("clean_temp_state_on_startup", False))
    )
    layout.addWidget(
        SettingsRow(
            material_icon("refresh"),
            "Clean temp state on startup",
            "Remember whether short-lived cache and temp state should be cleaned when the session boots.",
            window.icon_font,
            window.ui_font,
            window.storage_clean_temp_switch,
        )
    )

    window.storage_metrics = {}
    metrics_grid = QGridLayout()
    metrics_grid.setContentsMargins(0, 0, 0, 0)
    metrics_grid.setHorizontalSpacing(10)
    metrics_grid.setVerticalSpacing(10)
    for index, key in enumerate(
        (
            "Wallpaper Source Cache",
            "Rendered Wallpapers",
            "Mail Attachments",
            "State Root",
            "Filesystem Total",
            "Filesystem Free",
        )
    ):
        label = QLabel("...")
        label.setFont(QFont(window.ui_font, 10))
        window.storage_metrics[key] = label
        metrics_grid.addWidget(build_metric_card(window, key, label), index // 2, index % 2)
    layout.addLayout(metrics_grid)

    window.storage_status = QLabel("Storage tools are ready.")
    window.storage_status.setWordWrap(True)
    window.storage_status.setProperty("mutedText", True)
    layout.addWidget(window.storage_status)

    buttons = QHBoxLayout()
    buttons.setSpacing(8)
    refresh_button = QPushButton("Refresh sizes")
    refresh_button.setObjectName("secondaryButton")
    refresh_button.clicked.connect(window._refresh_storage_metrics)
    clear_wallpaper_button = QPushButton("Clear wallpaper cache")
    clear_wallpaper_button.setObjectName("secondaryButton")
    clear_wallpaper_button.clicked.connect(window._clear_wallpaper_cache)
    clear_temp_button = QPushButton("Clean temp state")
    clear_temp_button.setObjectName("secondaryButton")
    clear_temp_button.clicked.connect(window._clear_temp_state)
    save_button = QPushButton("Save storage settings")
    save_button.setObjectName("primaryButton")
    save_button.clicked.connect(window._save_storage_settings)
    for button in (refresh_button, clear_wallpaper_button, clear_temp_button, save_button):
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    buttons.addWidget(refresh_button)
    buttons.addWidget(clear_wallpaper_button)
    buttons.addWidget(clear_temp_button)
    buttons.addWidget(save_button)
    buttons.addStretch(1)
    layout.addLayout(buttons)

    window._refresh_storage_metrics()
    return card

