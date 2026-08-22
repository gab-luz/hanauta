from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from settings_page.dock_settings import load_dock_settings_state, save_dock_settings_state
from settings_page.material_icons import material_icon
from settings_page.ui_widgets import SettingsRow, SwitchButton
from settings_page.widgets import IconLabel, SegmentedChip


def build_dock_page(window) -> QWidget:
    card = QFrame()
    card.setObjectName("dockCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(14)

    header = QHBoxLayout()
    header.setSpacing(8)

    icon = IconLabel(material_icon("dock"), window.icon_font, 15, "#F4EAF7")
    icon.setFixedSize(22, 22)
    icon.setObjectName("dockHeaderIcon")
    title = QLabel("Dock")
    title.setObjectName("dockTitle")
    title.setFont(QFont(window.display_font, 13))
    subtitle = QLabel("Configure the application dock behavior and appearance.")
    subtitle.setObjectName("dockSubtitle")
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

    dock_cfg = window.settings_state.get("dock", load_dock_settings_state().get("dock", {}))

    auto_hide_switch = SwitchButton(bool(dock_cfg.get("auto_hide", False)))
    auto_hide_switch.toggledValue.connect(window._set_dock_auto_hide)
    auto_hide = SettingsRow(
        material_icon("auto_fix_high"),
        "Auto-hide",
        "Automatically hide the dock when not in use.",
        window.icon_font,
        window.ui_font,
        auto_hide_switch,
    )
    layout.addWidget(auto_hide)

    icons_left_switch = SwitchButton(bool(dock_cfg.get("icons_left", False)))
    icons_left_switch.toggledValue.connect(window._set_dock_icons_left)
    icons_left = SettingsRow(
        material_icon("format_align_left"),
        "Icons on left",
        "Align dock icons to the left instead of center.",
        window.icon_font,
        window.ui_font,
        icons_left_switch,
    )
    layout.addWidget(icons_left)

    width_spin = QSpinBox()
    width_spin.setRange(20, 300)
    width_spin.setValue(int(dock_cfg.get("width", 60)))
    width_spin.setSuffix(" px")
    width_spin.setFixedWidth(120)
    width_spin.valueChanged.connect(window._set_dock_width)
    width = SettingsRow(
        material_icon("tune"),
        "Width",
        "Set the dock width in pixels.",
        window.icon_font,
        window.ui_font,
        width_spin,
    )
    layout.addWidget(width)

    height_spin = QSpinBox()
    height_spin.setRange(40, 120)
    height_spin.setValue(int(dock_cfg.get("height", 64)))
    height_spin.setSuffix(" px")
    height_spin.setFixedWidth(120)
    height_spin.valueChanged.connect(window._set_dock_height)
    height = SettingsRow(
        material_icon("height"),
        "Height",
        "Set the dock height in pixels.",
        window.icon_font,
        window.ui_font,
        height_spin,
    )
    layout.addWidget(height)

    transparency_spin = QSpinBox()
    transparency_spin.setRange(0, 100)
    transparency_spin.setValue(int(dock_cfg.get("transparency", 60)))
    transparency_spin.setSuffix(" %")
    transparency_spin.setFixedWidth(120)
    transparency_spin.valueChanged.connect(window._set_dock_transparency)
    transparency = SettingsRow(
        material_icon("opacity"),
        "Transparency",
        "Set the dock background transparency.",
        window.icon_font,
        window.ui_font,
        transparency_spin,
    )
    layout.addWidget(transparency)

    position_chip = SegmentedChip(window)
    position_chip.addOption("Left", "left", window.icon_font, window.ui_font)
    position_chip.addOption("Center", "center", window.icon_font, window.ui_font)
    position_chip.addOption("Right", "right", window.icon_font, window.ui_font)
    current_pos = dock_cfg.get("position", "center")
    position_chip.setSelected(current_pos)
    position_chip.selectionChanged.connect(window._set_dock_position)
    position = SettingsRow(
        material_icon("horizontal_align_center"),
        "Position",
        "Set the dock horizontal position on screen.",
        window.icon_font,
        window.ui_font,
        position_chip,
    )
    layout.addWidget(position)

    monitor_mode_chip = SegmentedChip(window)
    monitor_mode_chip.addOption("Primary", "primary", window.icon_font, window.ui_font)
    monitor_mode_chip.addOption("Follow Mouse", "follow_mouse", window.icon_font, window.ui_font)
    monitor_mode_chip.addOption("Named", "named", window.icon_font, window.ui_font)
    current_mode = dock_cfg.get("monitor_mode", "primary")
    monitor_mode_chip.setSelected(current_mode)
    monitor_mode_chip.selectionChanged.connect(window._set_dock_monitor_mode)
    monitor_mode = SettingsRow(
        material_icon("monitor"),
        "Monitor mode",
        "Choose which monitor the dock appears on.",
        window.icon_font,
        window.ui_font,
        monitor_mode_chip,
    )
    layout.addWidget(monitor_mode)

    window.dock_monitor_name_input = QLineEdit()
    window.dock_monitor_name_input.setPlaceholderText("Monitor name (for 'Named' mode)")
    window.dock_monitor_name_input.setText(str(dock_cfg.get("monitor_name", "")))
    window.dock_monitor_name_input.setFixedWidth(220)
    window.dock_monitor_name_input.textChanged.connect(window._set_dock_monitor_name)
    monitor_name = SettingsRow(
        material_icon("desktop_access_disabled"),
        "Monitor name",
        "Specific monitor name when using 'Named' monitor mode.",
        window.icon_font,
        window.ui_font,
        window.dock_monitor_name_input,
    )
    layout.addWidget(monitor_name)

    layout.addStretch(1)
    return card


def build_lazy_dock_page(window) -> QWidget:
    placeholder = QWidget()
    layout = QVBoxLayout(placeholder)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)

    loading = QLabel("Dock settings loaded on demand.")
    loading.setWordWrap(True)
    loading.setStyleSheet("color: rgba(246,235,247,0.72);")

    layout.addWidget(loading)
    layout.addStretch(1)

    return placeholder