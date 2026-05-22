from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QDesktopServices,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from settings_page.material_icons import material_icon
from settings_page.settings_store import save_settings_state

from settings_page.marketplace_api import (
    marketplace_api_installed_plugins,
    marketplace_api_refresh_catalog_cache,
    marketplace_api_update_all_plugins,
    marketplace_api_update_plugin,
)


def _marketplace_sources_from_state(state: dict) -> list[dict]:
    return []


def _marketplace_manifest_url_for_source_api(source: dict) -> str:
    return ""


def _marketplace_fetch_manifest_payload_api(url: str) -> dict | None:
    return None


def _marketplace_normalize_shortcuts_field_api(shortcuts: list) -> list:
    return shortcuts


def _marketplace_normalize_catalog_api(catalog: list[dict]) -> list[dict]:
    return catalog


_MP_ASSETS_DIR = Path(__file__).resolve().parents[2].parent / "assets"
_MP_NAV_ICONS_DIR = _MP_ASSETS_DIR / "nav-icons"
_MP_ICON_CACHE_DIR = _MP_ASSETS_DIR / "plugin-icons"


def _tint_pixmap(source: QPixmap, color: QColor) -> QPixmap:
    if source.isNull():
        return QPixmap()
    src = source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    out = QImage(src.size(), QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(out.rect(), color)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, src)
    painter.end()
    return QPixmap.fromImage(out)


def _tinted_svg_pixmap(path: Path, color: QColor, size: int = 18) -> QPixmap | None:
    if not path.exists():
        return None
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return None
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return _tint_pixmap(pix, color)


def _plugin_icon_path(plugin: dict[str, Any]) -> str | None:
    raw = plugin.get("icon") or plugin.get("icon_url") or ""
    return str(raw).strip() or None


def _download_plugin_icon(url: str, plugin_id: str) -> Path | None:
    _MP_ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(url.split("?")[0]).suffix or ".png"
    cache_path = _MP_ICON_CACHE_DIR / f"{plugin_id}{ext}"
    if cache_path.exists():
        return cache_path
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Hanauta/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
        cache_path.write_bytes(data)
        return cache_path
    except Exception:
        return None


def build_marketplace_page(window) -> QWidget:
    return MarketplacePage(window)


def build_marketplace_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("contentCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)
    title = QLabel("Marketplace")
    title.setFont(QFont(window.display_font, 13))
    title.setStyleSheet("color: rgba(246,235,247,0.72);")
    layout.addWidget(title)
    return card


class MarketplacePage(QFrame):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.settings = _settings_from_window(window)

        self.filter_mode = "all"
        self.search_text = ""

        self.catalog: list[dict[str, Any]] = self._catalog_from_settings()
        self.installed: list[dict[str, Any]] = marketplace_api_installed_plugins(
            self.settings
        )
        if not self.installed:
            self.installed = self._installed_from_settings()

        self.selected_catalog_ids: set[str] = set()
        self.selected_installed_ids: set[str] = set()

        self.setObjectName("marketplacePage")
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet(_marketplace_qss(window))

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        root.addWidget(self._build_hero())
        root.addWidget(self._build_maintenance_tools())
        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_batch_actions())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        body.addWidget(self._build_catalog_panel(), 1)

        root.addLayout(body, 1)

        self._render_all()

    def _ui_font(self, size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
        return QFont(getattr(self.window, "ui_font", ""), size, weight)

    def _display_font(
        self, size: int, weight: QFont.Weight = QFont.Weight.Normal
    ) -> QFont:
        return QFont(getattr(self.window, "display_font", ""), size, weight)

    def _icon_font(self, size: int) -> QFont:
        return QFont(getattr(self.window, "icon_font", ""), size)

    def _catalog_from_settings(self) -> list[dict[str, Any]]:
        marketplace = self.settings.get("marketplace", {})
        if not isinstance(marketplace, dict):
            return []
        cache = marketplace.get("catalog_cache", [])
        if not isinstance(cache, list):
            return []
        return [row for row in cache if isinstance(row, dict)]

    def _installed_ids(self) -> set[str]:
        ids: set[str] = set()
        for row in self.installed:
            plugin_id = str(row.get("id", "")).strip()
            if plugin_id:
                ids.add(plugin_id)
        return ids

    def _build_hero(self) -> QWidget:
        hero = QFrame()
        hero.setObjectName("mpHero")
        hero.setMinimumHeight(94)
        hero.setMaximumHeight(110)

        layout = QHBoxLayout(hero)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        icon = QLabel(material_icon("storefront"))
        icon.setObjectName("mpHeroIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(self._icon_font(24))
        icon.setFixedSize(54, 54)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        kicker = QLabel("HANAUTA PLUGINS")
        kicker.setObjectName("mpKicker")
        kicker.setFont(self._ui_font(8, QFont.Weight.DemiBold))

        title = QLabel("Marketplace")
        title.setObjectName("mpHeroTitle")
        title.setFont(self._display_font(18, QFont.Weight.DemiBold))

        subtitle = QLabel("Install, update, and manage compact extensions for your desktop shell.")
        subtitle.setObjectName("mpHeroSubtitle")
        subtitle.setFont(self._ui_font(9))
        subtitle.setWordWrap(False)

        text_col.addWidget(kicker)
        text_col.addWidget(title)
        text_col.addWidget(subtitle)

        stats = QHBoxLayout()
        stats.setContentsMargins(0, 0, 0, 0)
        stats.setSpacing(8)

        self.catalog_stat = self._stat_pill("0", "Catalog")
        self.installed_stat = self._stat_pill("0", "Installed")
        stats.addWidget(self.catalog_stat)
        stats.addWidget(self.installed_stat)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(4)
        right_col.addLayout(stats)

        layout.addWidget(icon)
        layout.addLayout(text_col, 1)
        layout.addLayout(right_col)

        return hero

    def _build_maintenance_tools(self) -> QWidget:
        row = QFrame()
        row.setObjectName("mpToolbar")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        tint = getattr(self.window, "theme_palette", None)
        tint_c = QColor(tint.primary) if tint else QColor("#7CB4FF")

        refresh_pix = _tinted_svg_pixmap(_MP_NAV_ICONS_DIR / "refresh.svg", tint_c, 16)
        refresh_btn = QPushButton("Refresh catalog")
        refresh_btn.setObjectName("mpToolButton")
        refresh_btn.setProperty("variant", "primary")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setMinimumHeight(32)
        refresh_btn.setFont(self._ui_font(9, QFont.Weight.DemiBold))
        if refresh_pix:
            refresh_btn.setIcon(QIcon(refresh_pix))
            refresh_btn.setIconSize(refresh_pix.size())
        refresh_btn.clicked.connect(self._refresh_catalog)

        update_pix = _tinted_svg_pixmap(_MP_NAV_ICONS_DIR / "update.svg", tint_c, 16)
        update_btn = QPushButton("Update all plugins")
        update_btn.setObjectName("mpToolButton")
        update_btn.setProperty("variant", "ghost")
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.setMinimumHeight(32)
        update_btn.setFont(self._ui_font(9, QFont.Weight.DemiBold))
        if update_pix:
            update_btn.setIcon(QIcon(update_pix))
            update_btn.setIconSize(update_pix.size())
        update_btn.clicked.connect(self._update_all)

        layout.addWidget(refresh_btn)
        layout.addWidget(update_btn)
        layout.addStretch(1)
        return row

    def _build_batch_actions(self) -> QWidget:
        row = QFrame()
        row.setObjectName("mpToolbar")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        install_selected_btn = QPushButton("Install selected")
        install_selected_btn.setObjectName("mpToolButton")
        install_selected_btn.setProperty("variant", "ghost")
        install_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        install_selected_btn.setMinimumHeight(32)
        install_selected_btn.setFont(self._ui_font(9, QFont.Weight.DemiBold))
        install_selected_btn.clicked.connect(self._install_selected_catalog)

        disable_selected_btn = QPushButton("Disable selected")
        disable_selected_btn.setObjectName("mpToolButton")
        disable_selected_btn.setProperty("variant", "ghost")
        disable_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        disable_selected_btn.setMinimumHeight(32)
        disable_selected_btn.setFont(self._ui_font(9, QFont.Weight.DemiBold))
        disable_selected_btn.clicked.connect(self._disable_selected_installed)

        remove_selected_btn = QPushButton("Remove selected")
        remove_selected_btn.setObjectName("mpToolButton")
        remove_selected_btn.setProperty("variant", "ghost")
        remove_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_selected_btn.setMinimumHeight(32)
        remove_selected_btn.setFont(self._ui_font(9, QFont.Weight.DemiBold))
        remove_selected_btn.clicked.connect(self._remove_selected_installed)

        layout.addWidget(install_selected_btn)
        layout.addWidget(disable_selected_btn)
        layout.addWidget(remove_selected_btn)
        layout.addStretch(1)
        return row

    def _build_toolbar(self) -> QWidget:
        toolbar = QFrame()
        toolbar.setObjectName("mpToolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        search_icon = QLabel(material_icon("search"))
        search_icon.setObjectName("mpSearchIcon")
        search_icon.setFont(self._icon_font(17))
        search_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("mpSearchInput")
        self.search_input.setPlaceholderText("Search plugins, capabilities, repos...")
        self.search_input.setFont(self._ui_font(10))
        self.search_input.textChanged.connect(self._on_search_changed)

        layout.addWidget(search_icon)
        layout.addWidget(self.search_input, 1)

        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)

        for mode, label in (
            ("all", "All"),
            ("available", "Available"),
            ("installed", "Installed"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("mpFilterButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setFont(self._ui_font(9, QFont.Weight.DemiBold))
            btn.setMinimumHeight(30)
            btn.clicked.connect(lambda checked=False, m=mode: self._set_filter(m))
            self.filter_group.addButton(btn)
            layout.addWidget(btn)

            if mode == "all":
                btn.setChecked(True)

        return toolbar

    def _build_catalog_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("mpCatalogPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setObjectName("mpCardsScroll")
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("mpCardsContent")

        self.cards_layout = QVBoxLayout(content)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)

        self.cards_scroll.setWidget(content)
        layout.addWidget(self.cards_scroll)

        return panel

    def _build_installed_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("mpInstalledPanel")
        panel.setFixedWidth(218)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        icon = QLabel(material_icon("inventory_2"))
        icon.setObjectName("mpSideIcon")
        icon.setFont(self._icon_font(17))

        title = QLabel("Installed")
        title.setObjectName("mpSideTitle")
        title.setFont(self._ui_font(10, QFont.Weight.DemiBold))

        top.addWidget(icon)
        top.addWidget(title, 1)

        layout.addLayout(top)

        self.installed_list = QVBoxLayout()
        self.installed_list.setContentsMargins(0, 0, 0, 0)
        self.installed_list.setSpacing(7)

        layout.addLayout(self.installed_list, 1)

        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("mpStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setFont(self._ui_font(8))

        layout.addWidget(self.status_label)

        return panel

    def _stat_pill(self, value: str, label: str) -> QWidget:
        pill = QFrame()
        pill.setObjectName("mpStatPill")
        pill.setMinimumHeight(54)

        layout = QVBoxLayout(pill)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(1)

        value_label = QLabel(value)
        value_label.setObjectName("mpStatValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setFont(self._ui_font(13, QFont.Weight.Bold))

        caption = QLabel(label)
        caption.setObjectName("mpStatCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setFont(self._ui_font(8, QFont.Weight.DemiBold))

        layout.addWidget(value_label)
        layout.addWidget(caption)

        pill.value_label = value_label  # type: ignore[attr-defined]
        return pill

    def _tool_button(self, icon: str, text: str, variant: str = "ghost") -> QPushButton:
        btn = QPushButton(f"{icon}  {text}")
        btn.setObjectName("mpToolButton")
        btn.setProperty("variant", variant)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(self._ui_font(9, QFont.Weight.DemiBold))
        btn.setMinimumHeight(32)
        btn.setMinimumWidth(96)
        return btn

    def _on_search_changed(self, text: str) -> None:
        self.search_text = text.strip().lower()
        self._render_cards()

    def _set_filter(self, mode: str) -> None:
        self.filter_mode = mode
        self._render_cards()

    def _render_all(self) -> None:
        self._render_stats()
        self._render_cards()

    def _render_stats(self) -> None:
        self.catalog_stat.value_label.setText(str(len(self.catalog)))  # type: ignore[attr-defined]
        self.installed_stat.value_label.setText(str(len(self.installed)))  # type: ignore[attr-defined]

    def _render_cards(self) -> None:
        _clear_layout(self.cards_layout)

        filtered = self._filtered_catalog()

        if not filtered:
            self.cards_layout.addWidget(
                self._empty_state(
                    icon=material_icon("inventory_2"),
                    title="No plugins found",
                    body="Refresh the catalog or adjust your search/filter.",
                )
            )
            self.cards_layout.addStretch(1)
            return

        for plugin in filtered:
            self.cards_layout.addWidget(self._plugin_card(plugin))

        self.cards_layout.addStretch(1)

    def _render_installed(self) -> None:
        _clear_layout(self.installed_list)

        if not self.installed:
            self.installed_list.addWidget(
                self._mini_empty(
                    "No plugins installed yet.",
                    "Install one from the catalog.",
                )
            )
            self.installed_list.addStretch(1)
            return

        for row in self.installed[:8]:
            self.installed_list.addWidget(self._installed_row(row))

        extra = len(self.installed) - 8
        if extra > 0:
            more = QLabel(f"+ {extra} more")
            more.setObjectName("mpMoreInstalled")
            more.setFont(self._ui_font(8, QFont.Weight.DemiBold))
            more.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.installed_list.addWidget(more)

        self.installed_list.addStretch(1)

    def _filtered_catalog(self) -> list[dict[str, Any]]:
        installed_ids = self._installed_ids()
        rows: list[dict[str, Any]] = []

        for plugin in self.catalog:
            plugin_id = str(plugin.get("id", "")).strip()
            is_installed = plugin_id in installed_ids

            if self.filter_mode == "installed" and not is_installed:
                continue

            if self.filter_mode == "available" and is_installed:
                continue

            if self.search_text and self.search_text not in _search_blob(plugin):
                continue

            rows.append(plugin)

        return rows

    def _plugin_card(self, plugin: dict[str, Any]) -> QWidget:
        plugin_id = str(plugin.get("id", "")).strip()
        name = str(plugin.get("name", plugin_id or "Plugin")).strip()
        description = str(plugin.get("description", "")).strip()
        repo = str(plugin.get("repo", "")).strip()
        branch = str(plugin.get("branch", "main")).strip() or "main"
        capabilities = _as_string_list(plugin.get("capabilities", []))
        requirements = _as_string_list(plugin.get("requirements", []))

        installed = plugin_id in self._installed_ids()

        card = QFrame()
        card.setObjectName("mpPluginCard")
        card.setMinimumHeight(96)
        card.setMaximumHeight(120)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        icon_box = QLabel()
        icon_box.setObjectName("mpPluginIcon")
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setFixedSize(48, 48)
        icon_path = _plugin_icon_path(plugin)
        if icon_path:
            cached = _download_plugin_icon(icon_path, plugin_id)
            if cached:
                pix = QPixmap(str(cached))
                if not pix.isNull():
                    scaled = pix.scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    icon_box.setPixmap(scaled)
        if not icon_box.pixmap() or icon_box.pixmap().isNull():
            icon_box.setText(material_icon("extension"))
            icon_box.setFont(self._icon_font(20))

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)

        title = QLabel(_shorten(name, 36))
        title.setObjectName("mpPluginTitle")
        title.setFont(self._ui_font(10, QFont.Weight.DemiBold))

        title_row.addWidget(title)

        if installed:
            badge = QLabel("Installed")
            badge.setObjectName("mpInstalledBadge")
            badge.setFont(self._ui_font(7, QFont.Weight.DemiBold))
            title_row.addWidget(badge)

        title_row.addStretch(1)

        desc = QLabel(_shorten(description or repo or "No description available.", 92))
        desc.setObjectName("mpPluginDescription")
        desc.setFont(self._ui_font(8))
        desc.setWordWrap(False)

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(5)

        shown_chips = capabilities[:3]
        if not shown_chips and requirements:
            shown_chips = requirements[:3]

        for chip_text in shown_chips:
            chips_row.addWidget(self._chip(chip_text))

        meta = QLabel(f"{branch} · API {plugin.get('api_target_version', 1)}")
        meta.setObjectName("mpPluginMeta")
        meta.setFont(self._ui_font(7))
        chips_row.addWidget(meta)
        chips_row.addStretch(1)

        content.addLayout(title_row)
        content.addWidget(desc)
        content.addLayout(chips_row)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        select_btn = QPushButton("✓")
        select_btn.setCheckable(True)
        select_btn.setObjectName("mpIconAction")
        select_btn.setToolTip("Select plugin")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setFixedSize(30, 30)
        select_btn.setFont(self._ui_font(8, QFont.Weight.DemiBold))
        select_btn.setChecked(plugin_id in self.selected_catalog_ids)
        select_btn.clicked.connect(
            lambda checked=False, pid=plugin_id: self._toggle_catalog_selection(pid, checked)
        )

        repo_btn = QPushButton(material_icon("open_in_new"))
        repo_btn.setObjectName("mpIconAction")
        repo_btn.setToolTip("Open repository")
        repo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        repo_btn.setFixedSize(30, 30)
        repo_btn.setFont(self._icon_font(15))
        repo_btn.clicked.connect(lambda checked=False, url=repo: self._open_repo(url))

        if installed:
            main_btn = QPushButton("Update")
            main_btn.setObjectName("mpCompactAction")
            main_btn.setProperty("variant", "ghost")
            main_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            main_btn.setFont(self._ui_font(8, QFont.Weight.DemiBold))
            main_btn.setFixedHeight(30)
            main_btn.clicked.connect(
                lambda checked=False, pid=plugin_id: self._update_plugin(pid)
            )
        else:
            main_btn = QPushButton("Install")
            main_btn.setObjectName("mpCompactAction")
            main_btn.setProperty("variant", "primary")
            main_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            main_btn.setFont(self._ui_font(8, QFont.Weight.DemiBold))
            main_btn.setFixedHeight(30)
            main_btn.clicked.connect(
                lambda checked=False, item=plugin: self._install_plugin(item)
            )

        actions.addWidget(select_btn)
        actions.addWidget(repo_btn)
        actions.addWidget(main_btn)

        layout.addWidget(icon_box)
        layout.addLayout(content, 1)
        layout.addLayout(actions)

        return card

    def _chip(self, text: str) -> QWidget:
        chip = QLabel(_shorten(str(text), 18))
        chip.setObjectName("mpChip")
        chip.setFont(self._ui_font(7, QFont.Weight.DemiBold))
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return chip

    def _installed_row(self, row: dict[str, Any]) -> QWidget:
        plugin_id = str(row.get("id", "")).strip()
        name = str(row.get("name", plugin_id or "Plugin")).strip()
        branch = str(row.get("branch", "main")).strip() or "main"

        card = QFrame()
        card.setObjectName("mpInstalledRow")
        card.setMinimumHeight(54)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        icon = QLabel(material_icon("check"))
        icon.setObjectName("mpInstalledRowIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(self._icon_font(13))
        icon.setFixedSize(28, 28)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)

        title = QLabel(_shorten(name, 22))
        title.setObjectName("mpInstalledRowTitle")
        title.setFont(self._ui_font(8, QFont.Weight.DemiBold))

        subtitle = QLabel(branch)
        subtitle.setObjectName("mpInstalledRowSubtitle")
        subtitle.setFont(self._ui_font(7))

        text.addWidget(title)
        text.addWidget(subtitle)

        palette = getattr(self.window, "theme_palette", None)
        tint_c = QColor(palette.primary) if palette else QColor("#7CB4FF")
        update_pix = _tinted_svg_pixmap(_MP_NAV_ICONS_DIR / "update.svg", tint_c, 14)
        select_btn = QPushButton("✓")
        select_btn.setCheckable(True)
        select_btn.setObjectName("mpTinyButton")
        select_btn.setToolTip("Select plugin")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setFixedSize(28, 28)
        select_btn.setFont(self._ui_font(8, QFont.Weight.DemiBold))
        select_btn.setChecked(plugin_id in self.selected_installed_ids)
        select_btn.clicked.connect(
            lambda checked=False, pid=plugin_id: self._toggle_installed_selection(pid, checked)
        )

        update = QPushButton()
        update.setObjectName("mpTinyButton")
        update.setToolTip("Update plugin")
        update.setCursor(Qt.CursorShape.PointingHandCursor)
        update.setFixedSize(28, 28)
        if update_pix:
            update.setIcon(QIcon(update_pix))
            update.setIconSize(update_pix.size())
        update.clicked.connect(lambda checked=False, pid=plugin_id: self._update_plugin(pid))

        layout.addWidget(icon)
        layout.addLayout(text, 1)
        layout.addWidget(select_btn)
        layout.addWidget(update)

        return card

    def _empty_state(self, icon: str, title: str, body: str) -> QWidget:
        box = QFrame()
        box.setObjectName("mpEmptyState")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(22, 24, 22, 24)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setObjectName("mpEmptyIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFont(self._icon_font(28))

        title_label = QLabel(title)
        title_label.setObjectName("mpEmptyTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(self._ui_font(12, QFont.Weight.DemiBold))

        body_label = QLabel(body)
        body_label.setObjectName("mpEmptyBody")
        body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_label.setWordWrap(True)
        body_label.setFont(self._ui_font(9))

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(body_label)

        return box

    def _mini_empty(self, title: str, body: str) -> QWidget:
        box = QFrame()
        box.setObjectName("mpMiniEmpty")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("mpMiniEmptyTitle")
        title_label.setFont(self._ui_font(8, QFont.Weight.DemiBold))
        title_label.setWordWrap(True)

        body_label = QLabel(body)
        body_label.setObjectName("mpMiniEmptyBody")
        body_label.setFont(self._ui_font(7))
        body_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(body_label)

        return box

    def _open_repo(self, repo_url: str) -> None:
        repo_url = str(repo_url).strip()
        if not repo_url:
            self._set_status("Plugin has no repository URL.")
            return
        QDesktopServices.openUrl(QUrl(repo_url))

    def _refresh_catalog(self) -> None:
        self._set_status("Refreshing catalog...")

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            old_catalog = list(self.catalog)
            old_installed = list(self.installed)
            catalog, errors = marketplace_api_refresh_catalog_cache(self.settings)
            if catalog:
                self.catalog = catalog
            elif old_catalog:
                self.catalog = old_catalog

            refreshed_installed = marketplace_api_installed_plugins(self.settings)
            if refreshed_installed:
                self.installed = refreshed_installed
            else:
                self.installed = self._installed_from_settings() or old_installed

            self._prune_selection_ids()

            if errors:
                self._set_status(f"Catalog refreshed with {len(errors)} source error(s).")
            else:
                self._set_status(f"Catalog refreshed: {len(self.catalog)} plugin(s).")

        except Exception as exc:
            self._set_status(f"Refresh failed: {exc}")

        finally:
            QApplication.restoreOverrideCursor()

        self._render_all()

    def _installed_from_settings(self) -> list[dict[str, Any]]:
        marketplace = self.settings.get("marketplace", {})
        if not isinstance(marketplace, dict):
            return []
        rows = marketplace.get("installed_plugins", [])
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _catalog_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for row in self.catalog:
            plugin_id = str(row.get("id", "")).strip()
            if plugin_id:
                index[plugin_id] = row
        return index

    def _prune_selection_ids(self) -> None:
        catalog_ids = {str(row.get("id", "")).strip() for row in self.catalog if str(row.get("id", "")).strip()}
        installed_ids = {str(row.get("id", "")).strip() for row in self.installed if str(row.get("id", "")).strip()}
        self.selected_catalog_ids.intersection_update(catalog_ids)
        self.selected_installed_ids.intersection_update(installed_ids)

    def _toggle_catalog_selection(self, plugin_id: str, checked: bool) -> None:
        plugin_id = str(plugin_id).strip()
        if not plugin_id:
            return
        if checked:
            self.selected_catalog_ids.add(plugin_id)
        else:
            self.selected_catalog_ids.discard(plugin_id)

    def _toggle_installed_selection(self, plugin_id: str, checked: bool) -> None:
        plugin_id = str(plugin_id).strip()
        if not plugin_id:
            return
        if checked:
            self.selected_installed_ids.add(plugin_id)
        else:
            self.selected_installed_ids.discard(plugin_id)

    def _install_selected_catalog(self) -> None:
        if not self.selected_catalog_ids:
            self._set_status("No catalog plugins selected.")
            return
        index = self._catalog_index()
        installed_now = 0
        for plugin_id in list(self.selected_catalog_ids):
            plugin = index.get(plugin_id)
            if not plugin:
                continue
            before = set(self._installed_ids())
            self._install_plugin(plugin)
            after = set(self._installed_ids())
            if plugin_id in after and plugin_id not in before:
                installed_now += 1
        self._prune_selection_ids()
        self._render_all()
        self._set_status(f"Installed {installed_now} selected plugin(s).")

    def _disable_selected_installed(self) -> None:
        if not self.selected_installed_ids:
            self._set_status("No installed plugins selected.")
            return
        marketplace = self.settings.setdefault("marketplace", {})
        if not isinstance(marketplace, dict):
            self._set_status("Marketplace settings are unavailable.")
            return
        rows = marketplace.get("installed_plugins", [])
        if not isinstance(rows, list):
            self._set_status("No installed plugin state to update.")
            return
        changed = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if plugin_id in self.selected_installed_ids:
                row["enabled"] = False
                changed += 1
        save_settings_state(self.settings)
        self.installed = marketplace_api_installed_plugins(self.settings) or self._installed_from_settings()
        self._prune_selection_ids()
        self._render_all()
        self._set_status(f"Disabled {changed} selected plugin(s).")

    def _remove_selected_installed(self) -> None:
        if not self.selected_installed_ids:
            self._set_status("No installed plugins selected.")
            return
        marketplace = self.settings.setdefault("marketplace", {})
        if not isinstance(marketplace, dict):
            self._set_status("Marketplace settings are unavailable.")
            return
        rows = marketplace.get("installed_plugins", [])
        if not isinstance(rows, list):
            self._set_status("No installed plugin state to update.")
            return
        selected = set(self.selected_installed_ids)
        kept_rows: list[dict[str, Any]] = []
        removed_count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if plugin_id in selected:
                removed_count += 1
                continue
            kept_rows.append(row)
        marketplace["installed_plugins"] = kept_rows
        save_settings_state(self.settings)
        self.selected_installed_ids.clear()
        self.installed = marketplace_api_installed_plugins(self.settings) or self._installed_from_settings()
        self._prune_selection_ids()
        self._render_all()
        self._set_status(f"Removed {removed_count} selected plugin(s).")

    def _install_plugin(self, plugin: dict[str, Any]) -> None:
        plugin_id = str(plugin.get("id", "")).strip()
        repo = str(plugin.get("repo", "")).strip()
        branch = str(plugin.get("branch", "main")).strip() or "main"

        if not plugin_id:
            self._set_status("Install failed: plugin has no id.")
            return

        if not repo:
            self._set_status(f"{plugin_id}: repository URL is missing.")
            return

        if plugin_id in self._installed_ids():
            self._set_status(f"{plugin_id} is already installed.")
            return

        if shutil.which("git") is None:
            self._set_status("Install failed: git is required.")
            return

        marketplace = self.settings.setdefault("marketplace", {})
        if not isinstance(marketplace, dict):
            marketplace = {}
            self.settings["marketplace"] = marketplace

        default_root = Path.home() / ".local" / "share" / "hanauta" / "plugins"
        install_root = Path(str(marketplace.get("install_dir", default_root))).expanduser()
        install_path = install_root / plugin_id

        try:
            install_root.mkdir(parents=True, exist_ok=True)

            if install_path.exists() and any(install_path.iterdir()):
                if not (install_path / ".git").exists():
                    self._set_status(f"{plugin_id}: install path exists but is not a git repo.")
                    return
            else:
                self._set_status(f"Installing {plugin_id}...")
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

                result = subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--branch",
                        branch,
                        repo,
                        str(install_path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "git clone failed").strip()
                    self._set_status(f"{plugin_id}: {detail}")
                    return

            installed_rows = marketplace.setdefault("installed_plugins", [])
            if not isinstance(installed_rows, list):
                installed_rows = []
                marketplace["installed_plugins"] = installed_rows

            entry = dict(plugin)
            entry["install_path"] = str(install_path)
            entry["installed_at_epoch"] = int(time.time())
            entry["updated_at_epoch"] = int(time.time())

            installed_rows[:] = [
                row
                for row in installed_rows
                if not (
                    isinstance(row, dict)
                    and str(row.get("id", "")).strip() == plugin_id
                )
            ]
            installed_rows.append(entry)

            save_settings_state(self.settings)

            self.installed = marketplace_api_installed_plugins(self.settings)
            self._set_status(f"{plugin_id} installed.")

        except Exception as exc:
            self._set_status(f"{plugin_id}: install failed: {exc}")

        finally:
            QApplication.restoreOverrideCursor()

        self._render_all()

    def _update_plugin(self, plugin_id: str) -> None:
        plugin_id = str(plugin_id).strip()
        if not plugin_id:
            self._set_status("Update failed: missing plugin id.")
            return

        self._set_status(f"Updating {plugin_id}...")

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            ok, detail = marketplace_api_update_plugin(self.settings, plugin_id)
            self.installed = marketplace_api_installed_plugins(self.settings)
            self._set_status(detail if detail else ("Updated." if ok else "Update failed."))

        except Exception as exc:
            self._set_status(f"{plugin_id}: update failed: {exc}")

        finally:
            QApplication.restoreOverrideCursor()

        self._render_all()

    def _update_all(self) -> None:
        if not self.installed:
            self._set_status("No installed plugins to update.")
            return

        self._set_status("Updating installed plugins...")

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            results = marketplace_api_update_all_plugins(self.settings)
            ok_count = sum(1 for _, ok, _ in results if ok)
            fail_count = len(results) - ok_count
            self.installed = marketplace_api_installed_plugins(self.settings)

            if fail_count:
                self._set_status(f"Updated {ok_count}; {fail_count} failed.")
            else:
                self._set_status(f"Updated {ok_count} plugin(s).")

        except Exception as exc:
            self._set_status(f"Update all failed: {exc}")

        finally:
            QApplication.restoreOverrideCursor()

        self._render_all()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(str(text).strip() or "Ready.")


def _settings_from_window(window) -> dict[str, Any]:
    for attr in (
        "settings_state",
        "settings",
        "state",
        "settings_data",
        "_settings_state",
    ):
        value = getattr(window, attr, None)
        if isinstance(value, dict):
            return value

    getter = getattr(window, "_get_settings_state", None)
    if callable(getter):
        try:
            value = getter()
            if isinstance(value, dict):
                return value
        except Exception:
            pass

    return {}


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [
            str(key).strip()
            for key, enabled in value.items()
            if str(key).strip() and bool(enabled)
        ]
    return []


def _search_blob(plugin: dict[str, Any]) -> str:
    values: list[str] = []

    for key in (
        "id",
        "name",
        "description",
        "repo",
        "branch",
        "path",
        "entrypoint",
        "catalog_source",
    ):
        values.append(str(plugin.get(key, "")))

    values.extend(_as_string_list(plugin.get("capabilities", [])))
    values.extend(_as_string_list(plugin.get("requirements", [])))

    return " ".join(values).lower()


def _shorten(text: Any, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)

        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
            continue

        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)


def _css_color(value: Any, fallback: str) -> str:
    if isinstance(value, QColor):
        return value.name()

    text = str(value or "").strip()
    if text.startswith("#") or text.startswith("rgb") or text.startswith("hsl"):
        return text

    return fallback


def _theme_color(window, name: str, fallback: str) -> str:
    palette = getattr(window, "theme_palette", None)
    if palette is None:
        return fallback

    return _css_color(getattr(palette, name, None), fallback)


def _marketplace_qss(window) -> str:
    primary = _theme_color(window, "primary", "#d8b4fe")
    primary_container = _theme_color(window, "primary_container", "#372044")
    surface = _theme_color(window, "surface", "#151018")
    surface_container = _theme_color(window, "surface_container", "#211823")
    outline = _theme_color(window, "outline", "rgba(246,235,247,0.14)")

    return f"""
    QFrame#marketplacePage {{
        background: transparent;
    }}

    QFrame#mpHero {{
        border-radius: 22px;
        border: 1px solid {outline};
        background: qlineargradient(
            x1: 0, y1: 0,
            x2: 1, y2: 1,
            stop: 0 rgba(216, 180, 254, 0.18),
            stop: 0.45 rgba(255, 255, 255, 0.055),
            stop: 1 rgba(80, 60, 120, 0.16)
        );
    }}

    QLabel#mpHeroIcon {{
        border-radius: 18px;
        color: #1b1023;
        background: {primary};
    }}

    QLabel#mpKicker {{
        color: rgba(246,235,247,0.58);
        letter-spacing: 1px;
    }}

    QLabel#mpHeroTitle {{
        color: rgba(255,255,255,0.96);
    }}

    QLabel#mpHeroSubtitle {{
        color: rgba(246,235,247,0.62);
    }}

    QFrame#mpStatPill {{
        min-width: 68px;
        border-radius: 14px;
        background: rgba(255,255,255,0.075);
        border: 1px solid rgba(255,255,255,0.075);
    }}

    QLabel#mpStatValue {{
        color: rgba(255,255,255,0.96);
    }}

    QLabel#mpStatCaption {{
        color: rgba(246,235,247,0.48);
    }}

    QPushButton#mpToolButton {{
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 14px;
        padding: 0 12px;
        color: rgba(246,235,247,0.86);
        background: rgba(255,255,255,0.055);
    }}

    QPushButton#mpToolButton:hover {{
        background: rgba(255,255,255,0.095);
    }}

    QPushButton#mpToolButton[variant="primary"] {{
        color: #1b1023;
        border: 1px solid rgba(255,255,255,0.18);
        background: {primary};
    }}

    QFrame#mpToolbar {{
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.045);
    }}

    QLabel#mpSearchIcon {{
        color: rgba(246,235,247,0.52);
    }}

    QLineEdit#mpSearchInput {{
        min-height: 30px;
        border: none;
        border-radius: 12px;
        color: rgba(255,255,255,0.94);
        background: transparent;
        selection-background-color: {primary};
        padding: 0 4px;
    }}

    QLineEdit#mpSearchInput::placeholder {{
        color: rgba(246,235,247,0.36);
    }}

    QPushButton#mpFilterButton {{
        border: 1px solid transparent;
        border-radius: 12px;
        padding: 0 12px;
        color: rgba(246,235,247,0.58);
        background: transparent;
    }}

    QPushButton#mpFilterButton:hover {{
        color: rgba(255,255,255,0.88);
        background: rgba(255,255,255,0.055);
    }}

    QPushButton#mpFilterButton:checked {{
        color: #1b1023;
        background: {primary};
    }}

    QFrame#mpCatalogPanel {{
        border: none;
        background: transparent;
    }}

    QScrollArea#mpCardsScroll {{
        border: none;
        background: transparent;
    }}

    QScrollArea#mpCardsScroll > QWidget {{
        background: transparent;
    }}

    QWidget#mpCardsContent {{
        background: transparent;
    }}

    QFrame#mpPluginCard {{
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.075);
        background: rgba(255,255,255,0.050);
    }}

    QFrame#mpPluginCard:hover {{
        border: 1px solid rgba(216,180,254,0.38);
        background: rgba(255,255,255,0.075);
    }}

    QLabel#mpPluginIcon {{
        border-radius: 15px;
        color: {primary};
        background: rgba(216,180,254,0.12);
        border: 1px solid rgba(216,180,254,0.16);
    }}

    QLabel#mpPluginTitle {{
        color: rgba(255,255,255,0.94);
    }}

    QLabel#mpPluginDescription {{
        color: rgba(246,235,247,0.58);
    }}

    QLabel#mpPluginMeta {{
        color: rgba(246,235,247,0.38);
        padding-left: 4px;
    }}

    QLabel#mpChip {{
        border-radius: 8px;
        padding: 2px 7px;
        color: rgba(246,235,247,0.72);
        background: rgba(255,255,255,0.065);
        border: 1px solid rgba(255,255,255,0.065);
    }}

    QLabel#mpInstalledBadge {{
        border-radius: 8px;
        padding: 2px 7px;
        color: #1b1023;
        background: {primary};
    }}

    QPushButton#mpIconAction {{
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.08);
        color: rgba(246,235,247,0.72);
        background: rgba(255,255,255,0.045);
    }}

    QPushButton#mpIconAction:hover {{
        color: rgba(255,255,255,0.96);
        background: rgba(255,255,255,0.085);
    }}

    QPushButton#mpCompactAction {{
        min-width: 66px;
        border-radius: 10px;
        padding: 0 10px;
        color: rgba(246,235,247,0.78);
        border: 1px solid rgba(255,255,255,0.09);
        background: rgba(255,255,255,0.05);
    }}

    QPushButton#mpCompactAction:hover {{
        background: rgba(255,255,255,0.09);
    }}

    QPushButton#mpCompactAction[variant="primary"] {{
        color: #1b1023;
        border: 1px solid rgba(255,255,255,0.18);
        background: {primary};
    }}

    QFrame#mpInstalledPanel {{
        border-radius: 20px;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.040);
    }}

    QLabel#mpSideIcon {{
        color: {primary};
    }}

    QLabel#mpSideTitle {{
        color: rgba(255,255,255,0.90);
    }}

    QFrame#mpInstalledRow {{
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.065);
        background: rgba(255,255,255,0.045);
    }}

    QLabel#mpInstalledRowIcon {{
        border-radius: 8px;
        color: #1b1023;
        background: {primary};
    }}

    QLabel#mpInstalledRowTitle {{
        color: rgba(255,255,255,0.88);
    }}

    QLabel#mpInstalledRowSubtitle {{
        color: rgba(246,235,247,0.42);
    }}

    QPushButton#mpTinyButton {{
        border-radius: 9px;
        border: none;
        color: rgba(246,235,247,0.58);
        background: transparent;
    }}

    QPushButton#mpTinyButton:hover {{
        color: rgba(255,255,255,0.92);
        background: rgba(255,255,255,0.08);
    }}

    QLabel#mpStatus {{
        color: rgba(246,235,247,0.46);
        border-radius: 12px;
        padding: 8px;
        background: rgba(255,255,255,0.040);
    }}

    QLabel#mpMoreInstalled {{
        color: rgba(246,235,247,0.42);
        padding: 6px;
    }}

    QFrame#mpEmptyState {{
        border-radius: 20px;
        border: 1px dashed rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.030);
    }}

    QLabel#mpEmptyIcon {{
        color: {primary};
    }}

    QLabel#mpEmptyTitle {{
        color: rgba(255,255,255,0.88);
    }}

    QLabel#mpEmptyBody {{
        color: rgba(246,235,247,0.52);
    }}

    QFrame#mpMiniEmpty {{
        border-radius: 14px;
        border: 1px dashed rgba(255,255,255,0.10);
        background: rgba(255,255,255,0.030);
    }}

    QLabel#mpMiniEmptyTitle {{
        color: rgba(255,255,255,0.78);
    }}

    QLabel#mpMiniEmptyBody {{
        color: rgba(246,235,247,0.45);
    }}
    """
