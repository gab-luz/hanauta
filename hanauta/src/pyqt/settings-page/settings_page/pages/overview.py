from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from settings_page.material_icons import material_icon
from settings_page.ui_widgets import ActionCard
from settings_page.widgets import IconLabel


def build_overview_page(window) -> QWidget:
    return window._scroll_page(
        build_overview_hero_card(window),
        build_system_overview_card(window),
        build_overview_actions_card(window),
        window._build_profile_card(),
    )


def build_overview_hero_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("overviewHeroCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 18)
    layout.setSpacing(10)

    profile = window._profile_state()
    name = str(profile.get("nickname") or profile.get("first_name") or "").strip()
    greeting = "Welcome back" + (f", {name}" if name else "")

    heading = QLabel(greeting)
    heading_font = QFont(window.display_font, 18, QFont.Weight.DemiBold)
    heading_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    heading.setFont(heading_font)

    summary = QLabel("Tune appearance, services, and plugins without leaving your workflow.")
    summary.setWordWrap(True)
    summary.setProperty("mutedText", True)
    summary_font = QFont(window.ui_font, 10)
    summary_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    summary.setFont(summary_font)

    chips = QHBoxLayout()
    chips.setSpacing(8)

    def _chip(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("overviewChip")
        label.setFont(QFont(window.ui_font, 9, QFont.Weight.DemiBold))
        return label

    appearance = window.settings_state.get("appearance", {})
    theme_choice = str(appearance.get("theme_choice", "dark")).strip().lower()
    accent = str(appearance.get("accent", "orchid")).strip()
    chips.addWidget(_chip(f"Theme: {theme_choice or 'dark'}"))
    chips.addWidget(_chip(f"Accent: {accent or 'orchid'}"))
    chips.addStretch(1)

    window.overview_status = QLabel("")
    window.overview_status.setProperty("mutedText", True)
    window.overview_status.setWordWrap(True)

    layout.addWidget(heading)
    layout.addWidget(summary)
    layout.addLayout(chips)
    layout.addWidget(window.overview_status)
    return card


def build_system_overview_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("contentCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    icon = IconLabel(material_icon("grid_view"), window.icon_font, 15, window.theme_palette.primary)
    icon.setFixedSize(22, 22)
    title = QLabel("System Overview")
    title_font = QFont(window.display_font, 13)
    title_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    title.setFont(title_font)
    subtitle = QLabel("Quick info for this session and shell environment.")
    subtitle.setProperty("mutedText", True)
    subtitle_font = QFont(window.ui_font, 9)
    subtitle_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    subtitle.setFont(subtitle_font)
    title_wrap = QVBoxLayout()
    title_wrap.setContentsMargins(0, 0, 0, 0)
    title_wrap.setSpacing(2)
    title_wrap.addWidget(title)
    title_wrap.addWidget(subtitle)
    header.addWidget(icon)
    header.addLayout(title_wrap)
    header.addStretch(1)
    layout.addLayout(header)

    grid = QGridLayout()
    grid.setContentsMargins(0, 4, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(10)
    window.system_overview_labels = {}
    for index, key in enumerate(("Host", "Kernel", "Session", "Python", "Uptime", "Screen")):
        label = QLabel("...")
        label_font = QFont(window.ui_font, 10)
        label_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        label.setFont(label_font)
        window.system_overview_labels[key] = label
        grid.addWidget(build_metric_card(window, key, label), index // 2, index % 2)
    layout.addLayout(grid)
    return card


def build_metric_card(window, title: str, value_label: QLabel) -> QWidget:
    card = QFrame()
    card.setObjectName("settingsRow")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)
    title_label = QLabel(title)
    title_font = QFont(window.ui_font, 8)
    title_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    title_label.setFont(title_font)
    title_label.setProperty("mutedText", True)
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    return card


def build_overview_actions_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("contentCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    icon = IconLabel(material_icon("auto_awesome"), window.icon_font, 15, window.theme_palette.primary)
    icon.setFixedSize(22, 22)
    title = QLabel("Quick actions")
    title_font = QFont(window.display_font, 13)
    title_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    title.setFont(title_font)
    subtitle = QLabel("Common ops for the shell and plugin workspace.")
    subtitle.setProperty("mutedText", True)
    subtitle_font = QFont(window.ui_font, 9)
    subtitle_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    subtitle.setFont(subtitle_font)
    title_wrap = QVBoxLayout()
    title_wrap.setContentsMargins(0, 0, 0, 0)
    title_wrap.setSpacing(2)
    title_wrap.addWidget(title)
    title_wrap.addWidget(subtitle)
    header.addWidget(icon)
    header.addLayout(title_wrap)
    header.addStretch(1)
    layout.addLayout(header)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(10)

    reload_i3 = ActionCard(
        material_icon("restart_alt"),
        "Reload i3",
        "Re-read i3 config without logging out",
        window.icon_font,
        window.ui_font,
    )
    reload_i3.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def _do_reload_i3() -> None:
        ok = window._reload_i3_keybindings()
        if hasattr(window, "overview_status"):
            window.overview_status.setText(
                "i3 reloaded." if ok else "i3 reload failed (check i3-msg output)."
            )

    reload_i3.clicked.connect(_do_reload_i3)

    bar_icons = ActionCard(
        material_icon("image"),
        "Bar icon config",
        "Open the bar icon overrides file",
        window.icon_font,
        window.ui_font,
    )
    bar_icons.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    bar_icons.clicked.connect(window._open_bar_icon_config)

    plugin_dir = ActionCard(
        material_icon("folder_open"),
        "Plugin folder",
        "Open the plugin install directory",
        window.icon_font,
        window.ui_font,
    )
    plugin_dir.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    plugin_dir.clicked.connect(window._marketplace_open_install_dir)

    grid.addWidget(reload_i3, 0, 0)
    grid.addWidget(bar_icons, 0, 1)
    grid.addWidget(plugin_dir, 1, 0)
    layout.addLayout(grid)
    return card

