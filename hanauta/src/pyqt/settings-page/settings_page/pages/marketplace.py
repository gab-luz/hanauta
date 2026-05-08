from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from settings_page.material_icons import material_icon
from settings_page.settings_defaults import ROOT
from settings_page.ui_widgets import ActionCard, SettingsRow
from settings_page.widgets import IconLabel

def build_marketplace_page(window) -> QWidget:
    return window._scroll_page(build_marketplace_card(window))


def build_marketplace_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("contentCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    icon = IconLabel(material_icon("storefront"), window.icon_font, 15, "#F4EAF7")
    icon.setFixedSize(22, 22)
    title = QLabel("Marketplace")
    title.setFont(QFont(window.display_font, 13))
    title.setStyleSheet("color: rgba(246,235,247,0.72);")
    subtitle = QLabel(
        "Discover modular Hanauta services from one or more GitHub catalogs, or install private plugins from local ZIP bundles."
    )
    subtitle.setFont(QFont(window.ui_font, 9))
    subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
    subtitle.setWordWrap(True)
    title_wrap = QVBoxLayout()
    title_wrap.setContentsMargins(0, 0, 0, 0)
    title_wrap.setSpacing(2)
    title_wrap.addWidget(title)
    title_wrap.addWidget(subtitle)
    header.addWidget(icon)
    header.addLayout(title_wrap)
    header.addStretch(1)
    layout.addLayout(header)

    marketplace = window.settings_state.setdefault("marketplace", {})
    window.marketplace_repo_input = QLineEdit(
        str(
            marketplace.get(
                "catalog_repo_url", "https://github.com/gab-luz/hanauta-plugins"
            )
        )
    )
    window.marketplace_repo_input.setPlaceholderText(
        "https://github.com/gab-luz/hanauta-plugins"
    )
    layout.addWidget(
        SettingsRow(
            material_icon("public"),
            "Catalog repo URL",
            "GitHub repository that hosts your plugin catalog manifest and plugin repositories.",
            window.icon_font,
            window.ui_font,
            window.marketplace_repo_input,
        )
    )

    window.marketplace_branch_input = QLineEdit(
        str(marketplace.get("catalog_branch", "main"))
    )
    window.marketplace_branch_input.setPlaceholderText("main")
    layout.addWidget(
        SettingsRow(
            material_icon("settings"),
            "Catalog branch",
            "Branch used when fetching the marketplace catalog.",
            window.icon_font,
            window.ui_font,
            window.marketplace_branch_input,
        )
    )

    window.marketplace_manifest_input = QLineEdit(
        str(marketplace.get("catalog_manifest_path", "plugins.json"))
    )
    window.marketplace_manifest_input.setPlaceholderText("plugins.json")
    layout.addWidget(
        SettingsRow(
            material_icon("description"),
            "Manifest path",
            "Path in the repo that returns plugin metadata as JSON.",
            window.icon_font,
            window.ui_font,
            window.marketplace_manifest_input,
        )
    )

    sources = marketplace.get("catalog_sources", [])
    source_lines: list[str] = []
    if isinstance(sources, list):
        for row in sources:
            if not isinstance(row, dict):
                continue
            repo_url = str(row.get("repo_url", "")).strip()
            if not repo_url:
                continue
            branch = str(row.get("branch", "main")).strip() or "main"
            manifest_path = (
                str(row.get("manifest_path", "plugins.json")).strip().lstrip("/")
                or "plugins.json"
            )
            source_lines.append(f"{repo_url} | {branch} | {manifest_path}")
    window.marketplace_sources_input = QPlainTextEdit("\n".join(source_lines))
    window.marketplace_sources_input.setPlaceholderText(
        "One source per line: https://github.com/owner/repo | main | plugins.json"
    )
    window.marketplace_sources_input.setFixedHeight(86)
    layout.addWidget(
        SettingsRow(
            material_icon("hub"),
            "Catalog sources",
            "Optional multi-source format: repo URL | branch | manifest path (one per line).",
            window.icon_font,
            window.ui_font,
            window.marketplace_sources_input,
        )
    )

    window.marketplace_install_dir_input = QLineEdit(
        str(marketplace.get("install_dir", str(ROOT / "hanauta" / "plugins")))
    )
    window.marketplace_install_dir_input.setPlaceholderText(
        str(ROOT / "hanauta" / "plugins")
    )
    install_dir_row = QWidget()
    install_dir_layout = QHBoxLayout(install_dir_row)
    install_dir_layout.setContentsMargins(0, 0, 0, 0)
    install_dir_layout.setSpacing(8)
    install_dir_layout.addWidget(window.marketplace_install_dir_input, 1)
    window.marketplace_choose_dir_button = QPushButton("Choose")
    window.marketplace_choose_dir_button.setObjectName("secondaryButton")
    window.marketplace_choose_dir_button.setCursor(
        QCursor(Qt.CursorShape.PointingHandCursor)
    )
    window.marketplace_choose_dir_button.clicked.connect(
        window._marketplace_choose_install_dir
    )
    install_dir_layout.addWidget(window.marketplace_choose_dir_button)
    layout.addWidget(
        SettingsRow(
            material_icon("folder_open"),
            "Install directory",
            "Plugins are cloned here and can be wired into Hanauta services.",
            window.icon_font,
            window.ui_font,
            install_dir_row,
        )
    )

    actions = QHBoxLayout()
    actions.setSpacing(8)
    window.marketplace_save_button = QPushButton("Save marketplace config")
    window.marketplace_save_button.setObjectName("primaryButton")
    window.marketplace_refresh_button = QPushButton("Refresh catalog")
    window.marketplace_refresh_button.setObjectName("secondaryButton")
    window.marketplace_install_button = QPushButton("Install selected")
    window.marketplace_install_button.setObjectName("secondaryButton")
    window.marketplace_install_zip_button = QPushButton("Install ZIP")
    window.marketplace_install_zip_button.setObjectName("secondaryButton")
    window.marketplace_open_dir_button = QPushButton("Open plugin folder")
    window.marketplace_open_dir_button.setObjectName("secondaryButton")
    for button in (
        window.marketplace_save_button,
        window.marketplace_refresh_button,
        window.marketplace_install_button,
        window.marketplace_install_zip_button,
        window.marketplace_open_dir_button,
    ):
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    window.marketplace_save_button.clicked.connect(window._marketplace_save_settings)
    window.marketplace_refresh_button.clicked.connect(
        window._marketplace_refresh_catalog
    )
    window.marketplace_install_button.clicked.connect(
        window._marketplace_install_selected
    )
    window.marketplace_install_zip_button.clicked.connect(
        window._marketplace_install_zip
    )
    window.marketplace_open_dir_button.clicked.connect(
        window._marketplace_open_install_dir
    )
    actions.addWidget(window.marketplace_save_button)
    actions.addWidget(window.marketplace_refresh_button)
    actions.addWidget(window.marketplace_install_button)
    actions.addWidget(window.marketplace_install_zip_button)
    actions.addWidget(window.marketplace_open_dir_button)
    actions.addStretch(1)
    layout.addLayout(actions)

    marketplace_body = QHBoxLayout()
    marketplace_body.setSpacing(10)

    catalog_card = QFrame()
    catalog_card.setObjectName("marketplaceCatalogCard")
    catalog_layout = QVBoxLayout(catalog_card)
    catalog_layout.setContentsMargins(12, 12, 12, 12)
    catalog_layout.setSpacing(8)
    catalog_title = QLabel("Plugin catalog")
    catalog_title.setObjectName("marketplacePanelTitle")
    catalog_subtitle = QLabel("Install only the modules each user actually wants.")
    catalog_subtitle.setObjectName("marketplacePanelSubtitle")
    catalog_subtitle.setWordWrap(True)
    catalog_layout.addWidget(catalog_title)
    catalog_layout.addWidget(catalog_subtitle)
    window.marketplace_search_input = QLineEdit()
    window.marketplace_search_input.setPlaceholderText(
        "Search plugins by name, id, or description"
    )
    window.marketplace_search_input.textChanged.connect(
        window._marketplace_filter_catalog
    )
    catalog_layout.addWidget(window.marketplace_search_input)

    window.marketplace_plugin_list = QListWidget()
    window.marketplace_plugin_list.setObjectName("marketplacePluginList")
    window.marketplace_plugin_list.currentItemChanged.connect(
        window._marketplace_update_details
    )
    window.marketplace_plugin_list.setMinimumHeight(250)
    window.marketplace_plugin_list.setAlternatingRowColors(False)
    window.marketplace_plugin_list.setUniformItemSizes(False)
    catalog_layout.addWidget(window.marketplace_plugin_list, 1)
    marketplace_body.addWidget(catalog_card, 3)

    detail_card = QFrame()
    detail_card.setObjectName("marketplaceDetailCard")
    detail_layout = QVBoxLayout(detail_card)
    detail_layout.setContentsMargins(14, 14, 14, 14)
    detail_layout.setSpacing(8)
    detail_title = QLabel("Plugin details")
    detail_title.setObjectName("marketplacePanelTitle")
    detail_layout.addWidget(detail_title)

    window.marketplace_detail_label = QLabel(
        "Select a plugin from the catalog to inspect installation details."
    )
    window.marketplace_detail_label.setObjectName("marketplaceDetailText")
    window.marketplace_detail_label.setWordWrap(True)
    detail_layout.addWidget(window.marketplace_detail_label)

    status_title = QLabel("Marketplace status")
    status_title.setObjectName("marketplacePanelTitle")
    detail_layout.addWidget(status_title)

    window.marketplace_status = QLabel("Marketplace is ready.")
    window.marketplace_status.setObjectName("marketplaceStatusText")
    window.marketplace_status.setWordWrap(True)
    detail_layout.addWidget(window.marketplace_status)
    detail_layout.addStretch(1)
    marketplace_body.addWidget(detail_card, 2)
    layout.addLayout(marketplace_body)

    window._marketplace_populate_catalog(list(marketplace.get("catalog_cache", [])))
    return card
