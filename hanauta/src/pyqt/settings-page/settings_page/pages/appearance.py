from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from settings_page.material_icons import material_icon
from settings_page.theme_data import CUSTOM_THEME_KEYS, THEME_CHOICES, THEME_LIBRARY
from settings_page.ui_widgets import ActionCard, PreviewCard, SettingsRow, SwitchButton
from settings_page.widgets import IconLabel, SegmentedChip, ThemeModeCard

def build_appearance_page(window) -> QWidget:
    return window._scroll_page(build_wallpaper_colors_card(window))


def build_wallpaper_colors_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("appearanceCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(14)

    header = QHBoxLayout()
    header.setSpacing(8)

    icon = IconLabel(material_icon("palette"), window.icon_font, 15, "#F4EAF7")
    icon.setFixedSize(22, 22)
    icon.setObjectName("appearanceHeaderIcon")
    title = QLabel("Wallpaper & Colors")
    title.setObjectName("appearanceTitle")
    title.setFont(QFont(window.display_font, 13))
    subtitle = QLabel(
        "Pick, import, and rotate wallpapers without disturbing Matugen theming."
    )
    subtitle.setObjectName("appearanceSubtitle")
    subtitle.setFont(QFont(window.ui_font, 9))

    title_wrap = QVBoxLayout()
    title_wrap.setContentsMargins(0, 0, 0, 0)
    title_wrap.setSpacing(2)
    title_wrap.addWidget(title)
    title_wrap.addWidget(subtitle)

    header.addWidget(icon)
    header.addLayout(title_wrap)
    header.addStretch(1)

    layout.addLayout(header)

    hero_wrap = QFrame()
    hero_wrap.setObjectName("appearanceHeroWrap")
    hero = QHBoxLayout(hero_wrap)
    hero.setContentsMargins(14, 14, 14, 14)
    hero.setSpacing(12)
    window.preview_card = PreviewCard(window.wallpaper, window.ui_font, window.display_font)
    hero.addWidget(window.preview_card, 11)

    actions_wrap = QFrame()
    actions_wrap.setObjectName("appearanceActionColumn")
    actions = QVBoxLayout(actions_wrap)
    actions.setContentsMargins(14, 14, 14, 14)
    actions.setSpacing(8)
    window.random_wall_button = ActionCard(
        material_icon("auto_awesome"),
        "Random Wallpaper",
        "Pick a random image from your slideshow folder",
        window.icon_font,
        window.ui_font,
    )
    window.choose_picture_button = ActionCard(
        material_icon("photo_library"),
        "Choose picture",
        "Select and apply a wallpaper image",
        window.icon_font,
        window.ui_font,
    )
    window.choose_folder_button = ActionCard(
        material_icon("folder_open"),
        "Choose folder",
        "Use a folder as a slideshow source",
        window.icon_font,
        window.ui_font,
    )
    window.random_wall_button.clicked.connect(window._apply_random_wallpaper)
    window.choose_picture_button.clicked.connect(window._choose_wallpaper_file)
    window.choose_folder_button.clicked.connect(window._choose_wallpaper_folder)
    actions.addWidget(window.random_wall_button)
    actions.addWidget(window.choose_picture_button)
    actions.addWidget(window.choose_folder_button)

    mode_heading = QLabel("Theme mode")
    mode_heading.setObjectName("appearanceSectionLabel")
    mode_heading.setFont(QFont(window.ui_font, 9, QFont.Weight.DemiBold))
    actions.addWidget(mode_heading)

    modes = QGridLayout()
    modes.setContentsMargins(0, 0, 0, 0)
    modes.setHorizontalSpacing(8)
    modes.setVerticalSpacing(8)
    light = ThemeModeCard(
        material_icon("light_mode"), "Light", window.icon_font, window.ui_font
    )
    dark = ThemeModeCard(
        material_icon("dark_mode"), "Dark", window.icon_font, window.ui_font
    )
    custom = ThemeModeCard(
        material_icon("palette"), "Custom", window.icon_font, window.ui_font
    )
    wallpaper_aware = ThemeModeCard(
        material_icon("auto_awesome"),
        "Wallpaper Aware (matugen)",
        window.icon_font,
        window.ui_font,
    )
    window.theme_buttons = {
        "light": light,
        "dark": dark,
        "custom": custom,
        "wallpaper_aware": wallpaper_aware,
    }
    window.mode_group = QButtonGroup(self)
    window.mode_group.setExclusive(True)
    for key, button in window.theme_buttons.items():
        window.mode_group.addButton(button)
        button.clicked.connect(
            lambda checked=False, current=key: window._set_theme_choice(current)
        )
    modes.addWidget(light, 0, 0)
    modes.addWidget(dark, 0, 1)
    modes.addWidget(custom, 1, 0)
    modes.addWidget(wallpaper_aware, 1, 1)

    actions.addLayout(modes)
    window.custom_theme_heading = QLabel("Custom theme")
    window.custom_theme_heading.setObjectName("appearanceSectionLabel")
    window.custom_theme_heading.setFont(QFont(window.ui_font, 9, QFont.Weight.DemiBold))
    actions.addWidget(window.custom_theme_heading)

    window.custom_theme_wrap = QFrame()
    window.custom_theme_wrap.setObjectName("appearanceAccentFrame")
    custom_theme_layout = QGridLayout(window.custom_theme_wrap)
    custom_theme_layout.setContentsMargins(10, 10, 10, 10)
    custom_theme_layout.setHorizontalSpacing(8)
    custom_theme_layout.setVerticalSpacing(8)
    retrowave = ThemeModeCard(
        material_icon("bolt"), "Retrowave", window.icon_font, window.ui_font
    )
    dracula = ThemeModeCard(
        material_icon("dark_mode"), "Dracula", window.icon_font, window.ui_font
    )
    caelestia = ThemeModeCard(
        material_icon("auto_awesome"), "Caelestia", window.icon_font, window.ui_font
    )
    window.custom_theme_buttons = {
        "retrowave": retrowave,
        "dracula": dracula,
        "caelestia": caelestia,
    }
    window.custom_theme_group = QButtonGroup(self)
    window.custom_theme_group.setExclusive(True)
    for key, button in window.custom_theme_buttons.items():
        window.custom_theme_group.addButton(button)
        button.clicked.connect(
            lambda checked=False, current=key: window._set_custom_theme(current)
        )
    custom_theme_layout.addWidget(retrowave, 0, 0)
    custom_theme_layout.addWidget(dracula, 0, 1)
    custom_theme_layout.addWidget(caelestia, 1, 0)
    actions.addWidget(window.custom_theme_wrap)
    window.custom_theme_hint = QLabel(
        "Custom themes drive both Hanauta colors and the matching GTK theme."
    )
    window.custom_theme_hint.setObjectName("settingsStatus")
    window.custom_theme_hint.setFont(QFont(window.ui_font, 8))
    actions.addWidget(window.custom_theme_hint)
    actions.addStretch(1)
    hero.addWidget(actions_wrap, 8)
    layout.addWidget(hero_wrap)

    window.appearance_status = QLabel(
        "Built-in wallpaper import can pull from your Caelestia and End-4 wallpaper folders, including nested downloads."
    )
    window.appearance_status.setObjectName("settingsStatus")
    window.appearance_status.setFont(QFont(window.ui_font, 9))
    layout.addWidget(window.appearance_status)
    window.wallpaper_sync_progress = QProgressBar()
    window.wallpaper_sync_progress.setObjectName("settingsProgressBar")
    window.wallpaper_sync_progress.setRange(0, 0)
    window.wallpaper_sync_progress.setTextVisible(False)
    window.wallpaper_sync_progress.hide()
    layout.addWidget(window.wallpaper_sync_progress)

    window.slideshow_interval = QSlider(Qt.Orientation.Horizontal)
    window.slideshow_interval.setRange(5, 86400)
    window.slideshow_interval.setValue(
        int(window.settings_state["appearance"].get("slideshow_interval", 30))
    )
    window.slideshow_interval.setFixedWidth(164)
    window.slideshow_interval.valueChanged.connect(window._set_slideshow_interval)
    window.slideshow_interval_label = QLabel(
        window._format_slideshow_interval_text(
            int(window.settings_state["appearance"].get("slideshow_interval", 30))
        )
    )
    window.slideshow_interval_label.setFixedWidth(108)
    window.slideshow_interval_label.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    window.slideshow_interval_label.setStyleSheet("color: rgba(246,235,247,0.78);")
    slideshow_interval_wrap = QWidget()
    slideshow_interval_layout = QHBoxLayout(slideshow_interval_wrap)
    slideshow_interval_layout.setContentsMargins(0, 0, 0, 0)
    slideshow_interval_layout.setSpacing(10)
    slideshow_interval_layout.addWidget(window.slideshow_interval)
    slideshow_interval_layout.addWidget(window.slideshow_interval_label)

    transparency = SettingsRow(
        material_icon("opacity"),
        "Transparency",
        "Keep glass surfaces active across the shell.",
        window.icon_font,
        window.ui_font,
        window._make_transparency_switch(),
    )
    layout.addWidget(transparency)
    layout.addWidget(
        window._slider_settings_row(
            "Control center shell opacity",
            "Adjust the overall transparency of the notification center panel.",
            35,
            100,
            int(
                window.settings_state["appearance"].get(
                    "notification_center_panel_opacity", 84
                )
            ),
            material_icon("opacity"),
            "notification_center_panel_opacity",
        )
    )
    layout.addWidget(
        window._slider_settings_row(
            "Control center widget opacity",
            "Control cards, sliders, quick actions, media, KDE Connect, and Home Assistant stay denser than the shell.",
            35,
            100,
            int(
                window.settings_state["appearance"].get(
                    "notification_center_card_opacity", 92
                )
            ),
            material_icon("widgets"),
            "notification_center_card_opacity",
        )
    )
    layout.addWidget(
        window._slider_settings_row(
            "Notification max width",
            "Limit how wide desktop notifications can grow on screen.",
            260,
            640,
            int(
                window.settings_state["appearance"].get(
                    "notification_toast_max_width", 356
                )
            ),
            material_icon("crop_square"),
            "notification_toast_max_width",
        )
    )
    layout.addWidget(
        window._slider_settings_row(
            "Notification max height",
            "Limit how tall desktop notifications can grow before content is clipped.",
            160,
            640,
            int(
                window.settings_state["appearance"].get(
                    "notification_toast_max_height", 280
                )
            ),
            material_icon("crop_square"),
            "notification_toast_max_height",
        )
    )
    interval = SettingsRow(
        material_icon("image"),
        "Slideshow interval",
        "Set how often folder slideshow rotates the wallpaper.",
        window.icon_font,
        window.ui_font,
        slideshow_interval_wrap,
    )
    matugen_button = QPushButton("Refresh palette")
    matugen_button.setObjectName("secondaryButton")
    matugen_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    matugen_button.clicked.connect(lambda: window._apply_matugen_palette(force=True))
    matugen = SettingsRow(
        material_icon("auto_awesome"),
        "Wallpaper-driven colors",
        "Use Matugen to generate a shared palette file for the dock and bar.",
        window.icon_font,
        window.ui_font,
        matugen_button,
    )
    window.matugen_notifications_switch = SwitchButton(
        bool(
            window.settings_state["appearance"].get(
                "matugen_notifications_enabled", False
            )
        )
    )
    window.matugen_notifications_switch.toggledValue.connect(
        window._set_matugen_notifications_enabled
    )
    matugen_notifications = SettingsRow(
        material_icon("notifications_active"),
        "Matugen notifications",
        "Show a desktop notification when wallpaper-driven colors are refreshed.",
        window.icon_font,
        window.ui_font,
        window.matugen_notifications_switch,
    )
    window.wallpaper_change_notifications_switch = SwitchButton(
        bool(
            window.settings_state["appearance"].get(
                "wallpaper_change_notifications_enabled", False
            )
        )
    )
    window.wallpaper_change_notifications_switch.toggledValue.connect(
        window._set_wallpaper_change_notifications_enabled
    )
    wallpaper_change_notifications = SettingsRow(
        material_icon("image"),
        "Wallpaper change notifications",
        "Show a desktop notification when Hanauta applies a new wallpaper.",
        window.icon_font,
        window.ui_font,
        window.wallpaper_change_notifications_switch,
    )
    layout.addWidget(interval)
    layout.addWidget(matugen)
    layout.addWidget(matugen_notifications)
    layout.addWidget(wallpaper_change_notifications)
    return card

