from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from settings_page.material_icons import material_icon
from settings_page.ui_widgets import SwitchButton
from settings_page.widgets import IconLabel, SegmentedChip


def build_display_page(window) -> QWidget:
    return window._scroll_page(build_display_card(window), window._build_picom_card())


def build_display_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("contentCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    icon = IconLabel(material_icon("desktop_windows"), window.icon_font, 15, window.theme_palette.primary)
    icon.setFixedSize(22, 22)
    title = QLabel("Displays")
    title.setFont(QFont(window.display_font, 13))
    subtitle = QLabel(
        "Primary monitor, extend or duplicate mode, resolution, refresh rate, and rotation."
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

    actions = QHBoxLayout()
    actions.setSpacing(8)
    refresh_button = QPushButton("Refresh")
    refresh_button.setObjectName("secondaryButton")
    refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    refresh_button.clicked.connect(window._refresh_display_state)
    apply_button = QPushButton("Apply displays")
    apply_button.setObjectName("primaryButton")
    apply_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    apply_button.clicked.connect(window._apply_display_settings)
    actions.addWidget(refresh_button)
    actions.addWidget(apply_button)
    actions.addStretch(1)
    layout.addLayout(actions)

    window.display_status = QLabel("")
    window.display_status.setProperty("mutedText", True)
    window.display_status.setWordWrap(True)
    layout.addWidget(window.display_status)

    if not window.display_state:
        window.display_status.setText("No displays detected through xrandr.")
        return card

    connected_count = len(window.display_state)
    if connected_count > 1:
        layout.addWidget(build_display_global_card(window))
    else:
        window.display_status.setText(
            "Single display detected. Primary and mirror controls are hidden."
        )

    window.display_outputs_container = QVBoxLayout()
    window.display_outputs_container.setContentsMargins(0, 0, 0, 0)
    window.display_outputs_container.setSpacing(10)
    layout.addLayout(window.display_outputs_container)
    window._rebuild_display_output_cards()
    return card


def build_display_global_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("settingsRow")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(12)

    title = QLabel("Multi-monitor layout")
    title.setFont(QFont(window.ui_font, 10, QFont.Weight.DemiBold))
    detail = QLabel(
        "Choose the primary display and whether active outputs extend left-to-right or mirror the primary."
    )
    detail.setFont(QFont(window.ui_font, 8))
    detail.setProperty("mutedText", True)
    detail.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(detail)

    row = QHBoxLayout()
    row.setSpacing(10)
    primary_label = QLabel("Primary")
    primary_label.setFont(QFont(window.ui_font, 9))
    primary_label.setProperty("mutedText", True)

    window.primary_display_combo = QComboBox()
    window.primary_display_combo.setObjectName("settingsCombo")
    for display in window.display_state:
        window.primary_display_combo.addItem(display["name"])
    primary_name = next(
        (display["name"] for display in window.display_state if display.get("primary")),
        window.display_state[0]["name"],
    )
    window.primary_display_combo.setCurrentText(primary_name)

    row.addWidget(primary_label)
    row.addWidget(window.primary_display_combo, 1)
    layout.addLayout(row)

    mode_row = QHBoxLayout()
    mode_row.setSpacing(8)
    window.display_layout_buttons = {}
    window.display_layout_group = QButtonGroup(window)
    window.display_layout_group.setExclusive(True)
    for key, label in (("extend", "Extend"), ("duplicate", "Duplicate")):
        chip = SegmentedChip(label, checked=(key == "extend"))
        chip.clicked.connect(
            lambda checked=False, current=key: window._set_display_layout_mode(current)
        )
        window.display_layout_group.addButton(chip)
        window.display_layout_buttons[key] = chip
        mode_row.addWidget(chip)
    mode_row.addStretch(1)
    layout.addLayout(mode_row)

    multi = len(window.display_state) > 1
    for display in window.display_state:
        card = QFrame()
        card.setObjectName("settingsRow")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel(display["name"])
        title.setFont(QFont(window.ui_font, 10, QFont.Weight.DemiBold))
        desc_bits = []
        if display.get("primary"):
            desc_bits.append("Primary")
        desc_bits.append("Active" if display.get("enabled") else "Connected but inactive")
        subtitle = QLabel(" • ".join(desc_bits))
        subtitle.setFont(QFont(window.ui_font, 8))
        subtitle.setProperty("mutedText", True)
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        title_row.addLayout(title_wrap)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        control_grid = QGridLayout()
        control_grid.setContentsMargins(0, 0, 0, 0)
        control_grid.setHorizontalSpacing(10)
        control_grid.setVerticalSpacing(10)

        enabled_switch = SwitchButton(bool(display.get("enabled", True)))
        enabled_switch.setEnabled(multi)

        resolution_combo = QComboBox()
        resolution_combo.setObjectName("settingsCombo")
        for mode in display.get("modes", []):
            resolution_combo.addItem(mode)
        if display.get("current_mode"):
            resolution_combo.setCurrentText(display["current_mode"])

        refresh_combo = QComboBox()
        refresh_combo.setObjectName("settingsCombo")

        orientation_combo = QComboBox()
        orientation_combo.setObjectName("settingsCombo")
        for option in ("normal", "left", "right", "inverted"):
            orientation_combo.addItem(option)
        orientation_combo.setCurrentText(display.get("orientation", "normal"))

        wallpaper_combo = QComboBox()
        wallpaper_combo.setObjectName("settingsCombo")
        wallpaper_combo.blockSignals(True)
        for option in ("fill", "fit", "center", "stretch", "tile"):
            wallpaper_combo.addItem(option.title(), option)
        saved_mode = str(
            window.settings_state["appearance"]
            .get("wallpaper_fit_modes", {})
            .get(display["name"], "fill")
        )
        wallpaper_combo.setCurrentText(saved_mode.title())
        wallpaper_combo.blockSignals(False)
        wallpaper_combo.currentTextChanged.connect(
            lambda _text, current=display["name"], combo=wallpaper_combo: (
                window._set_display_wallpaper_mode(
                    current,
                    str(combo.currentData() or combo.currentText().lower()),
                )
            )
        )

        resolution_combo.currentTextChanged.connect(
            lambda mode, current=display["name"]: window._sync_refresh_rates_for_output(current, mode)
        )
        window.display_controls[display["name"]] = {
            "enabled": enabled_switch,
            "resolution": resolution_combo,
            "refresh": refresh_combo,
            "orientation": orientation_combo,
            "wallpaper": wallpaper_combo,
        }
        window._sync_refresh_rates_for_output(display["name"], resolution_combo.currentText())

        control_grid.addWidget(build_settings_labeled_field(window, "Enabled", enabled_switch), 0, 0)
        control_grid.addWidget(build_settings_labeled_field(window, "Resolution", resolution_combo), 0, 1)
        control_grid.addWidget(build_settings_labeled_field(window, "Refresh", refresh_combo), 1, 0)
        control_grid.addWidget(build_settings_labeled_field(window, "Orientation", orientation_combo), 1, 1)
        control_grid.addWidget(build_settings_labeled_field(window, "Wallpaper", wallpaper_combo), 2, 0, 1, 2)

        layout.addLayout(control_grid)
        window.display_outputs_container.addWidget(card)

    return card


def build_settings_labeled_field(window, label_text: str, widget: QWidget) -> QWidget:
    wrap = QWidget()
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    label = QLabel(label_text)
    label.setFont(QFont(window.ui_font, 8))
    label.setProperty("mutedText", True)
    layout.addWidget(label)
    layout.addWidget(widget)
    return wrap
