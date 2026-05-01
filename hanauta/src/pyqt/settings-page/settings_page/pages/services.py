from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from settings_page.material_icons import material_icon
from settings_page.ui_widgets import ExpandableServiceSection, SettingsRow, SwitchButton
from settings_page.widgets import IconLabel

def build_services_page(window) -> QWidget:
    return window._scroll_page(build_services_card(window))


def build_services_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("contentCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    icon = IconLabel(material_icon("settings"), window.icon_font, 15, "#F4EAF7")
    icon.setFixedSize(22, 22)
    title = QLabel("Services")
    title.setFont(QFont(window.display_font, 13))
    title.setStyleSheet("color: rgba(246,235,247,0.72);")
    header.addWidget(icon)
    header.addWidget(title)
    window._services_filter_query = ""
    window._services_sort_desc = False
    window._services_visibility_mode = "all"
    window.services_search_input = QLineEdit()
    window.services_search_input.setPlaceholderText("Search services/plugins")
    window.services_search_input.setObjectName("settingsInput")
    window.services_search_input.setMinimumWidth(220)
    window.services_search_input.textChanged.connect(window._services_filter_changed)
    window.services_sort_button = QPushButton("A→Z")
    window.services_sort_button.setObjectName("secondaryButton")
    window.services_sort_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    window.services_sort_button.clicked.connect(window._toggle_services_sort_order)
    window.services_visibility_button = QPushButton("All")
    window.services_visibility_button.setObjectName("secondaryButton")
    window.services_visibility_button.setCursor(
        QCursor(Qt.CursorShape.PointingHandCursor)
    )
    window.services_visibility_button.clicked.connect(
        window._cycle_services_visibility_mode
    )
    header.addWidget(window.services_search_input)
    header.addWidget(window.services_sort_button)
    header.addWidget(window.services_visibility_button)
    header.addStretch(1)
    layout.addLayout(header)

    window.service_sections: dict[str, ExpandableServiceSection] = {}
    window.service_display_switches: dict[str, SwitchButton] = {}
    window._plugin_service_wrappers: dict[str, QWidget] = {}
    window._services_section_widgets: list[QWidget] = []
    window._services_widget_insert_counter = 0
    window._refresh_installed_service_key_index()
    window._services_build_layout = layout
    window._services_build_finished = False
    window._services_core_queue = [
        ("mail", window._build_mail_service_section),
        ("kdeconnect", window._build_kdeconnect_service_section),
        ("weather", window._build_weather_section),
        ("calendar_widget", window._build_calendar_service_section),
        ("desktop_clock_widget", window._build_desktop_clock_service_section),
    ]
    window._services_plugin_queue: list[dict[str, object]] = []
    window._services_cached_plugin_queue = window._read_services_section_rows_cache()
    window._services_cached_plugins_used = bool(window._services_cached_plugin_queue)
    window._services_loading_label = QLabel("Loading service sections...")
    window._services_loading_label.setWordWrap(True)
    window._services_loading_label.setStyleSheet("color: rgba(246,235,247,0.72);")
    layout.addWidget(window._services_loading_label)
    window._services_sections_built = 0
    window._plugin_dir_scan_scheduled = False
    # Let Qt paint the tab immediately, then progressively add sections.
    QTimer.singleShot(25, window._build_next_services_section)
    return card

