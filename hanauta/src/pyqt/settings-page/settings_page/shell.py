from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pyqt.shared.button_helpers import create_close_button
from settings_page.material_icons import material_icon
from settings_page.widgets import NavPillButton


def build_header(window) -> QWidget:
    header = QFrame()
    header.setObjectName("topHeader")
    header.setFixedHeight(54)

    layout = QHBoxLayout(header)
    layout.setContentsMargins(18, 12, 18, 12)
    layout.setSpacing(14)

    lead_chip = QFrame()
    lead_chip.setObjectName("headerLeadChip")
    lead_layout = QHBoxLayout(lead_chip)
    lead_layout.setContentsMargins(12, 8, 12, 8)
    lead_layout.setSpacing(8)
    lead_icon = QLabel("♪")
    lead_icon.setProperty("iconRole", True)
    lead_icon.setObjectName("headerLeadIcon")
    lead_icon.setFont(QFont(window.icon_font, 14))
    lead_text = QLabel("hanauta")
    lead_text.setObjectName("headerLeadText")
    lead_text.setFont(QFont(window.ui_font, 9, QFont.Weight.DemiBold))
    lead_layout.addWidget(lead_icon)
    lead_layout.addWidget(lead_text)

    title_wrap = QVBoxLayout()
    title_wrap.setContentsMargins(0, 0, 0, 0)
    title_wrap.setSpacing(1)
    title = QLabel("Settings")
    title.setObjectName("headerTitle")
    title.setFont(QFont(window.display_font, 12))
    subtitle = QLabel("Wallpaper, accents, and shell behavior")
    subtitle.setObjectName("headerSubtitle")
    subtitle.setFont(QFont(window.ui_font, 8))
    title_wrap.addWidget(title)
    title_wrap.addWidget(subtitle)

    close_button = create_close_button(
        material_icon("close"),
        window.icon_font,
        font_size=16,
    )
    close_button.setFixedSize(32, 32)
    close_button.setProperty("iconButton", True)
    close_button.clicked.connect(window.close)

    layout.addWidget(
        lead_chip, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    layout.addLayout(title_wrap, 1)
    layout.addWidget(
        close_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    return header


def build_sidebar(window) -> QWidget:
    window.sidebar = QFrame()
    window.sidebar.setObjectName("sidebar")
    window.sidebar.setFixedWidth(244)

    layout = QVBoxLayout(window.sidebar)
    layout.setContentsMargins(16, 18, 16, 18)
    layout.setSpacing(12)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(8)

    window.sidebar_title = QLabel("Settings")
    window.sidebar_title.setObjectName("sidebarTitle")
    window.sidebar_title.setFont(QFont(window.display_font, 12, QFont.Weight.DemiBold))

    window.sidebar_menu_button = QPushButton(material_icon("menu"))
    window.sidebar_menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
    window.sidebar_menu_button.setFixedSize(38, 36)
    window.sidebar_menu_button.setFont(QFont(window.icon_font, 16))
    window.sidebar_menu_button.setProperty("iconButton", True)
    window.sidebar_menu_button.setProperty("iconButtonBorderless", True)
    window.sidebar_menu_button.clicked.connect(window._toggle_sidebar)

    window.search_button = QPushButton(material_icon("search"))
    window.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
    window.search_button.setFixedSize(38, 36)
    window.search_button.setFont(QFont(window.icon_font, 16))
    window.search_button.setProperty("iconButton", True)
    window.search_button.setProperty("iconButtonBorderless", True)
    window.search_button.clicked.connect(window._toggle_search)

    top_row.addWidget(window.sidebar_title, 1)
    top_row.addWidget(window.search_button, 0, Qt.AlignmentFlag.AlignRight)
    top_row.addWidget(window.sidebar_menu_button, 0, Qt.AlignmentFlag.AlignRight)
    layout.addLayout(top_row)

    nav_section = QFrame()
    nav_section.setObjectName("sidebarNavSection")
    nav_layout = QVBoxLayout(nav_section)
    nav_layout.setContentsMargins(6, 8, 6, 8)
    nav_layout.setSpacing(6)

    window.sidebar_section_label = QLabel("Workspace")
    window.sidebar_section_label.setObjectName("sidebarSectionLabel")
    window.sidebar_section_label.setFont(QFont(window.ui_font, 8, QFont.Weight.DemiBold))
    nav_layout.addWidget(window.sidebar_section_label)

    window.nav_group = QButtonGroup(window)
    window.nav_group.setExclusive(True)
    window.nav_buttons = {}

    items = [
        ("overview", material_icon("grid_view"), "Overview", False),
        ("appearance", material_icon("palette"), "Looks", True),
        ("marketplace", material_icon("storefront"), "Marketplace", False),
        ("display", material_icon("desktop_windows"), "Display", False),
        ("energy", material_icon("bolt"), "Energy", False),
        ("audio", material_icon("music_note"), "Audio", False),
        ("notifications", material_icon("notifications"), "Notifications", False),
        ("input", material_icon("language"), "Input", False),
        ("startup", material_icon("restart_alt"), "Startup", False),
        ("privacy", material_icon("shield"), "Privacy", False),
        ("networking", material_icon("hub"), "Networking", False),
        ("storage", material_icon("storage"), "Storage", False),
        ("region", material_icon("public"), "Region", False),
        ("bar", material_icon("crop_square"), "Bar", False),
        ("services", material_icon("widgets"), "Services", False),
    ]

    for key, glyph, label, checked in items:
        button = NavPillButton(glyph, label, window.icon_font, window.ui_font)
        button.setChecked(checked)
        button.clicked.connect(lambda checked=False, current=key: window._show_page(current))
        window.nav_group.addButton(button)
        window.nav_buttons[key] = button
        nav_layout.addWidget(button)

    layout.addWidget(nav_section)
    layout.addStretch(1)
    return window.sidebar


def build_scroll_body(window) -> QWidget:
    window.page_stack = QStackedWidget()
    window.page_stack.addWidget(window._build_overview_page())
    window.page_stack.addWidget(window._build_appearance_page())
    window.page_stack.addWidget(window._build_marketplace_page())
    window.page_stack.addWidget(window._build_display_page())
    window.page_stack.addWidget(window._build_energy_page())
    window.page_stack.addWidget(window._build_audio_page())
    window.page_stack.addWidget(window._build_notifications_page())
    window.page_stack.addWidget(window._build_input_page())
    window.page_stack.addWidget(window._build_startup_page())
    window.page_stack.addWidget(window._build_privacy_page())
    window.page_stack.addWidget(window._build_networking_page())
    window.page_stack.addWidget(window._build_storage_page())
    window.page_stack.addWidget(window._build_region_page())
    window.bar_page_index = window.page_stack.count()
    window._bar_page_ready = False
    window._bar_page_building = False
    window.page_stack.addWidget(build_bar_placeholder(window))
    window.services_page_index = window.page_stack.count()
    window._services_page_ready = False
    window._services_page_building = False
    window.page_stack.addWidget(build_services_placeholder(window))
    window._show_page(window.initial_page)

    build_search_overlay(window)

    return window.page_stack


def build_bar_placeholder(window) -> QWidget:
    placeholder = QWidget()
    layout = QVBoxLayout(placeholder)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)
    loading = QLabel("Bar page is loaded on demand for faster startup.")
    loading.setWordWrap(True)
    loading.setStyleSheet("color: rgba(246,235,247,0.72);")
    layout.addWidget(loading)
    layout.addStretch(1)
    return placeholder


def build_services_placeholder(window) -> QWidget:
    placeholder = QWidget()
    layout = QVBoxLayout(placeholder)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)
    loading = QLabel("Services page is loaded on demand for faster startup.")
    loading.setWordWrap(True)
    loading.setStyleSheet("color: rgba(246,235,247,0.72);")
    layout.addWidget(loading)
    layout.addStretch(1)
    return placeholder


def build_search_overlay(window) -> None:
    window.search_container = QFrame(window.page_stack)
    window.search_container.setObjectName("searchOverlay")
    window.search_container.setVisible(False)
    search_layout = QVBoxLayout(window.search_container)
    search_layout.setContentsMargins(0, 0, 0, 0)
    search_layout.setSpacing(0)

    search_input_container = QFrame()
    search_input_container.setObjectName("searchInputContainer")
    input_layout = QHBoxLayout(search_input_container)
    input_layout.setContentsMargins(16, 12, 16, 12)
    input_layout.setSpacing(12)

    search_icon = QLabel(material_icon("search"))
    search_icon.setFont(QFont(window.icon_font, 18))
    search_icon.setStyleSheet("color: rgba(246,235,247,0.56);")
    input_layout.addWidget(search_icon)

    window.search_input = QLineEdit()
    window.search_input.setPlaceholderText("Search settings...")
    window.search_input.setObjectName("searchInputField")
    window.search_input.setFont(QFont(window.ui_font, 14))
    window.search_input.textChanged.connect(window._on_search_changed)
    input_layout.addWidget(window.search_input, 1)

    close_search_btn = QPushButton(material_icon("close"))
    close_search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    close_search_btn.setFixedSize(32, 32)
    close_search_btn.setFont(QFont(window.icon_font, 16))
    close_search_btn.setProperty("iconButton", True)
    close_search_btn.clicked.connect(window._toggle_search)
    input_layout.addWidget(close_search_btn)

    search_layout.addWidget(search_input_container)

    window.search_results_container = QScrollArea()
    window.search_results_container.setObjectName("searchResultsContainer")
    window.search_results_container.setWidgetResizable(True)
    window.search_results_container.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    window.search_results_layout = QVBoxLayout()
    window.search_results_layout.setContentsMargins(16, 8, 16, 16)
    window.search_results_layout.setSpacing(8)
    window.search_results_layout.addStretch(1)

    results_widget = QWidget()
    results_widget.setObjectName("searchResultsContent")
    results_widget.setLayout(window.search_results_layout)
    window.search_results_container.setWidget(results_widget)

    search_layout.addWidget(window.search_results_container, 1)

    window.search_overlay_index = window.page_stack.count()
    window.page_stack.addWidget(window.search_container)

