from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QCursor, QFont, QIcon
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

DISPLAY_ASSETS_DIR = Path(__file__).resolve().parents[4] / "assets"


def build_display_page(window) -> QWidget:
    _apply_display_style(window)

    return window._scroll_page(
        build_display_card(window),
        window._build_picom_card(),
    )

def _lock_combo_wheel(combo: QComboBox) -> None:
    original_wheel_event = combo.wheelEvent

    def _guarded_wheel_event(event) -> None:
        if combo.view().isVisible():
            original_wheel_event(event)
            return
        event.ignore()

    combo.wheelEvent = _guarded_wheel_event  # type: ignore[method-assign]


def build_display_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("displayRootCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(12)

    if not hasattr(window, "display_controls") or not isinstance(
        window.display_controls, dict
    ):
        window.display_controls = {}
    else:
        window.display_controls.clear()

    # -------------------------------------------------------------------------
    # HERO
    # -------------------------------------------------------------------------
    hero = QFrame()
    hero.setObjectName("displayHero")

    hero_layout = QHBoxLayout(hero)
    hero_layout.setContentsMargins(16, 14, 16, 14)
    hero_layout.setSpacing(14)

    hero_icon = IconLabel(
        material_icon("monitor"),
        window.icon_font,
        24,
        "#201126",
    )
    hero_icon.setObjectName("displayHeroIcon")
    hero_icon.setFixedSize(56, 56)

    hero_text = QVBoxLayout()
    hero_text.setContentsMargins(0, 0, 0, 0)
    hero_text.setSpacing(3)

    kicker = QLabel("MONITOR CONTROL")
    kicker.setObjectName("displayKicker")
    kicker.setFont(QFont(window.ui_font, 8, QFont.Weight.DemiBold))

    title = QLabel("Displays")
    title.setObjectName("displayHeroTitle")
    title.setFont(QFont(window.display_font, 20, QFont.Weight.DemiBold))

    subtitle = QLabel(
        "Configure primary monitor, layout mode, resolution, refresh rate, rotation and wallpaper behavior."
    )
    subtitle.setObjectName("displayHeroSubtitle")
    subtitle.setFont(QFont(window.ui_font, 9))
    subtitle.setWordWrap(True)

    hero_text.addWidget(kicker)
    hero_text.addWidget(title)
    hero_text.addWidget(subtitle)

    hero_side = QVBoxLayout()
    hero_side.setContentsMargins(0, 0, 0, 0)
    hero_side.setSpacing(8)

    connected_count = len(getattr(window, "display_state", []) or [])
    active_count = sum(
        1
        for display in getattr(window, "display_state", []) or []
        if bool(display.get("enabled", True))
    )

    hero_side.addWidget(
        _display_metric_pill(
            window,
            material_icon("desktop_windows"),
            str(connected_count),
            "connected",
        )
    )
    hero_side.addWidget(
        _display_metric_pill(
            window,
            material_icon("visibility"),
            str(active_count),
            "active",
        )
    )

    hero_layout.addWidget(hero_icon)
    hero_layout.addLayout(hero_text, 1)
    hero_layout.addLayout(hero_side)

    layout.addWidget(hero)

    # -------------------------------------------------------------------------
    # ACTION BAR
    # -------------------------------------------------------------------------
    action_bar = QFrame()
    action_bar.setObjectName("displayActionBar")

    action_layout = QHBoxLayout(action_bar)
    action_layout.setContentsMargins(10, 8, 10, 8)
    action_layout.setSpacing(8)

    action_hint_icon = QLabel(material_icon("tune"))
    action_hint_icon.setObjectName("displayActionHintIcon")
    action_hint_icon.setFont(QFont(window.icon_font, 16))
    action_hint_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

    action_hint = QLabel("Changes are staged until you apply them.")
    action_hint.setObjectName("displayActionHint")
    action_hint.setFont(QFont(window.ui_font, 8))
    action_hint.setWordWrap(True)

    refresh_button = _display_action_button(
        window,
        "Refresh",
        "secondary",
        DISPLAY_ASSETS_DIR / "nav-icons" / "refresh.svg",
    )
    refresh_button.clicked.connect(window._refresh_display_state)

    apply_button = _display_action_button(
        window,
        "Apply displays",
        "primary",
        DISPLAY_ASSETS_DIR / "check.svg",
    )
    apply_button.clicked.connect(window._apply_display_settings)

    action_layout.addWidget(action_hint_icon)
    action_layout.addWidget(action_hint, 1)
    action_layout.addWidget(refresh_button)
    action_layout.addWidget(apply_button)

    layout.addWidget(action_bar)

    window.display_status = QLabel("")
    window.display_status.setObjectName("displayStatusText")
    window.display_status.setFont(QFont(window.ui_font, 8))
    window.display_status.setWordWrap(True)

    # -------------------------------------------------------------------------
    # EMPTY STATE
    # -------------------------------------------------------------------------
    if not window.display_state:
        window.display_status.setText("No displays detected through xrandr.")
        layout.addWidget(
            _display_empty_state(
                window,
                material_icon("desktop_access_disabled"),
                "No displays detected",
                "xrandr did not return connected outputs. Try refreshing or check if your session is running under X11.",
            )
        )
        layout.addWidget(window.display_status)
        return card

    # -------------------------------------------------------------------------
    # MONITOR PREVIEW
    # -------------------------------------------------------------------------
    layout.addWidget(build_display_preview_card(window))

    # -------------------------------------------------------------------------
    # GLOBAL MULTI-MONITOR CONTROLS
    # -------------------------------------------------------------------------
    window.display_outputs_container = QVBoxLayout()
    window.display_outputs_container.setContentsMargins(0, 0, 0, 0)
    window.display_outputs_container.setSpacing(10)

    if connected_count > 1:
        layout.addWidget(build_display_global_card(window))
    else:
        window.display_status.setText(
            "Single display detected. Primary and mirror controls are hidden."
        )

    # -------------------------------------------------------------------------
    # OUTPUT CARDS
    # -------------------------------------------------------------------------
    layout.addLayout(window.display_outputs_container)

    for display in window.display_state:
        window.display_outputs_container.addWidget(
            build_display_output_card(
                window,
                display,
                multi=connected_count > 1,
            )
        )

    layout.addWidget(build_display_status_card(window))

    return card


def build_display_preview_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("displayPreviewCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    layout.addWidget(
        _display_section_header(
            window,
            material_icon("dashboard"),
            "Layout preview",
            "A compact visual map of connected outputs.",
        )
    )

    preview_row = QHBoxLayout()
    preview_row.setContentsMargins(0, 0, 0, 0)
    preview_row.setSpacing(10)

    displays = getattr(window, "display_state", []) or []

    for index, display in enumerate(displays):
        preview_row.addWidget(
            _display_preview_monitor(
                window,
                display,
                index=index,
            ),
            1,
        )

    preview_row.addStretch(1)
    layout.addLayout(preview_row)

    return card


def build_display_global_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("displayPanelCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    layout.addWidget(
        _display_section_header(
            window,
            material_icon("hub"),
            "Multi-monitor layout",
            "Choose the primary display and whether active outputs extend or mirror.",
        )
    )

    body = QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(10)

    primary_box = QFrame()
    primary_box.setObjectName("displayFieldCard")

    primary_layout = QVBoxLayout(primary_box)
    primary_layout.setContentsMargins(10, 9, 10, 10)
    primary_layout.setSpacing(7)

    primary_header = QHBoxLayout()
    primary_header.setContentsMargins(0, 0, 0, 0)
    primary_header.setSpacing(8)

    primary_icon = QLabel(material_icon("stars"))
    primary_icon.setObjectName("displayFieldIcon")
    primary_icon.setFont(QFont(window.icon_font, 15))
    primary_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    primary_icon.setFixedSize(24, 24)

    primary_text = QVBoxLayout()
    primary_text.setContentsMargins(0, 0, 0, 0)
    primary_text.setSpacing(0)

    primary_title = QLabel("Primary display")
    primary_title.setObjectName("displayFieldTitle")
    primary_title.setFont(QFont(window.ui_font, 9, QFont.Weight.DemiBold))

    primary_desc = QLabel("Main output for panels, focus and default positioning.")
    primary_desc.setObjectName("displayFieldDescription")
    primary_desc.setFont(QFont(window.ui_font, 8))
    primary_desc.setWordWrap(True)

    primary_text.addWidget(primary_title)
    primary_text.addWidget(primary_desc)

    primary_header.addWidget(primary_icon)
    primary_header.addLayout(primary_text, 1)

    window.primary_display_combo = QComboBox()
    window.primary_display_combo.setObjectName("displayCombo")
    _lock_combo_wheel(window.primary_display_combo)

    for display in window.display_state:
        window.primary_display_combo.addItem(str(display["name"]))

    primary_name = next(
        (
            str(display["name"])
            for display in window.display_state
            if display.get("primary")
        ),
        str(window.display_state[0]["name"]),
    )
    window.primary_display_combo.setCurrentText(primary_name)

    primary_layout.addLayout(primary_header)
    primary_layout.addWidget(window.primary_display_combo)

    mode_box = QFrame()
    mode_box.setObjectName("displayFieldCard")

    mode_layout = QVBoxLayout(mode_box)
    mode_layout.setContentsMargins(10, 9, 10, 10)
    mode_layout.setSpacing(8)

    mode_header = QHBoxLayout()
    mode_header.setContentsMargins(0, 0, 0, 0)
    mode_header.setSpacing(8)

    mode_icon = QLabel(material_icon("compare_arrows"))
    mode_icon.setObjectName("displayFieldIcon")
    mode_icon.setFont(QFont(window.icon_font, 15))
    mode_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    mode_icon.setFixedSize(24, 24)

    mode_text = QVBoxLayout()
    mode_text.setContentsMargins(0, 0, 0, 0)
    mode_text.setSpacing(0)

    mode_title = QLabel("Layout mode")
    mode_title.setObjectName("displayFieldTitle")
    mode_title.setFont(QFont(window.ui_font, 9, QFont.Weight.DemiBold))

    mode_desc = QLabel("Extend side-by-side or duplicate the primary output.")
    mode_desc.setObjectName("displayFieldDescription")
    mode_desc.setFont(QFont(window.ui_font, 8))
    mode_desc.setWordWrap(True)

    mode_text.addWidget(mode_title)
    mode_text.addWidget(mode_desc)

    mode_header.addWidget(mode_icon)
    mode_header.addLayout(mode_text, 1)

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(8)

    window.display_layout_buttons = {}
    window.display_layout_group = QButtonGroup(window)
    window.display_layout_group.setExclusive(True)

    for key, label in (("extend", "Extend"), ("duplicate", "Duplicate")):
        chip = SegmentedChip(label, checked=(key == "extend"))
        chip.setObjectName("displaySegmentedChip")
        chip.clicked.connect(
            lambda checked=False, current=key: window._set_display_layout_mode(current)
        )
        window.display_layout_group.addButton(chip)
        window.display_layout_buttons[key] = chip
        mode_row.addWidget(chip)

    mode_row.addStretch(1)

    mode_layout.addLayout(mode_header)
    mode_layout.addLayout(mode_row)

    body.addWidget(primary_box, 1)
    body.addWidget(mode_box, 1)

    layout.addLayout(body)

    return card


def build_display_output_card(window, display: dict, multi: bool) -> QWidget:
    display_name = str(display.get("name", "Display")).strip() or "Display"
    enabled = bool(display.get("enabled", True))
    primary = bool(display.get("primary", False))

    card = QFrame()
    card.setObjectName("displayOutputCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(11)

    # -------------------------------------------------------------------------
    # OUTPUT HEADER
    # -------------------------------------------------------------------------
    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(10)

    icon = QLabel(material_icon("monitor"))
    icon.setObjectName("displayOutputIcon")
    icon.setFont(QFont(window.icon_font, 18))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFixedSize(38, 38)

    text = QVBoxLayout()
    text.setContentsMargins(0, 0, 0, 0)
    text.setSpacing(2)

    title = QLabel(display_name)
    title.setObjectName("displayOutputTitle")
    title.setFont(QFont(window.ui_font, 11, QFont.Weight.DemiBold))

    desc_bits = []
    if primary:
        desc_bits.append("Primary")
    desc_bits.append("Active" if enabled else "Connected but inactive")

    current_mode = str(display.get("current_mode", "")).strip()
    if current_mode:
        desc_bits.append(current_mode)

    subtitle = QLabel(" • ".join(desc_bits))
    subtitle.setObjectName("displayOutputSubtitle")
    subtitle.setFont(QFont(window.ui_font, 8))
    subtitle.setWordWrap(True)

    text.addWidget(title)
    text.addWidget(subtitle)

    badges = QHBoxLayout()
    badges.setContentsMargins(0, 0, 0, 0)
    badges.setSpacing(6)

    if primary:
        badges.addWidget(_display_badge(window, "Primary", "primary"))

    badges.addWidget(
        _display_badge(
            window,
            "Active" if enabled else "Inactive",
            "active" if enabled else "inactive",
        )
    )

    title_row.addWidget(icon)
    title_row.addLayout(text, 1)
    title_row.addLayout(badges)

    layout.addLayout(title_row)

    # -------------------------------------------------------------------------
    # CONTROLS
    # -------------------------------------------------------------------------
    control_grid = QGridLayout()
    control_grid.setContentsMargins(0, 0, 0, 0)
    control_grid.setHorizontalSpacing(9)
    control_grid.setVerticalSpacing(9)

    enabled_switch = SwitchButton(enabled)
    enabled_switch.setEnabled(multi)

    resolution_combo = QComboBox()
    resolution_combo.setObjectName("displayCombo")
    _lock_combo_wheel(resolution_combo)

    for mode in display.get("modes", []):
        resolution_combo.addItem(str(mode))

    if display.get("current_mode"):
        resolution_combo.setCurrentText(str(display["current_mode"]))

    refresh_combo = QComboBox()
    refresh_combo.setObjectName("displayCombo")
    _lock_combo_wheel(refresh_combo)

    orientation_combo = QComboBox()
    orientation_combo.setObjectName("displayCombo")
    _lock_combo_wheel(orientation_combo)

    for option in ("normal", "left", "right", "inverted"):
        orientation_combo.addItem(option.title(), option)

    orientation = str(display.get("orientation", "normal")).strip() or "normal"
    orientation_combo.setCurrentText(orientation.title())

    wallpaper_combo = QComboBox()
    wallpaper_combo.setObjectName("displayCombo")
    _lock_combo_wheel(wallpaper_combo)
    wallpaper_combo.blockSignals(True)

    for option in ("fill", "fit", "center", "stretch", "tile"):
        wallpaper_combo.addItem(option.title(), option)

    appearance = window.settings_state.setdefault("appearance", {})
    if not isinstance(appearance, dict):
        appearance = {}
        window.settings_state["appearance"] = appearance

    wallpaper_modes = appearance.get("wallpaper_fit_modes", {})
    if not isinstance(wallpaper_modes, dict):
        wallpaper_modes = {}
        appearance["wallpaper_fit_modes"] = wallpaper_modes

    saved_mode = str(wallpaper_modes.get(display_name, "fill")).strip() or "fill"
    wallpaper_combo.setCurrentText(saved_mode.title())
    wallpaper_combo.blockSignals(False)

    wallpaper_combo.currentTextChanged.connect(
        lambda _text, current=display_name, combo=wallpaper_combo: (
            window._set_display_wallpaper_mode(
                current,
                str(combo.currentData() or combo.currentText().lower()),
            )
        )
    )

    resolution_combo.currentTextChanged.connect(
        lambda mode, current=display_name: window._sync_refresh_rates_for_output(
            current,
            mode,
        )
    )

    window.display_controls[display_name] = {
        "enabled": enabled_switch,
        "resolution": resolution_combo,
        "refresh": refresh_combo,
        "orientation": orientation_combo,
        "wallpaper": wallpaper_combo,
    }

    window._sync_refresh_rates_for_output(display_name, resolution_combo.currentText())

    control_grid.addWidget(
        build_settings_labeled_field(
            window,
            material_icon("power_settings_new"),
            "Enabled",
            enabled_switch,
        ),
        0,
        0,
    )
    control_grid.addWidget(
        build_settings_labeled_field(
            window,
            material_icon("aspect_ratio"),
            "Resolution",
            resolution_combo,
        ),
        0,
        1,
    )
    control_grid.addWidget(
        build_settings_labeled_field(
            window,
            material_icon("speed"),
            "Refresh rate",
            refresh_combo,
        ),
        1,
        0,
    )
    control_grid.addWidget(
        build_settings_labeled_field(
            window,
            material_icon("screen_rotation"),
            "Rotation",
            orientation_combo,
        ),
        1,
        1,
    )
    control_grid.addWidget(
        build_settings_labeled_field(
            window,
            material_icon("wallpaper"),
            "Wallpaper fit",
            wallpaper_combo,
        ),
        2,
        0,
        1,
        2,
    )

    layout.addLayout(control_grid)

    return card


def build_display_status_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("displayStatusCard")

    layout = QHBoxLayout(card)
    layout.setContentsMargins(10, 9, 10, 9)
    layout.setSpacing(8)

    icon = QLabel(material_icon("info"))
    icon.setObjectName("displayStatusIcon")
    icon.setFont(QFont(window.icon_font, 15))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFixedSize(24, 24)

    if not hasattr(window, "display_status"):
        window.display_status = QLabel("")

    if not window.display_status.text().strip():
        window.display_status.setText(
            "Ready. Review your monitor settings, then apply when everything looks right."
        )

    window.display_status.setObjectName("displayStatusText")
    window.display_status.setFont(QFont(window.ui_font, 8))
    window.display_status.setWordWrap(True)

    layout.addWidget(icon)
    layout.addWidget(window.display_status, 1)

    return card


def build_settings_labeled_field(
    window,
    icon_text: str,
    label_text: str,
    widget: QWidget,
) -> QWidget:
    wrap = QFrame()
    wrap.setObjectName("displayControlField")

    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(9, 8, 9, 9)
    layout.setSpacing(7)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(6)

    icon = QLabel(icon_text)
    icon.setObjectName("displayControlIcon")
    icon.setFont(QFont(window.icon_font, 13))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFixedSize(20, 20)

    label = QLabel(label_text)
    label.setObjectName("displayControlLabel")
    label.setFont(QFont(window.ui_font, 8, QFont.Weight.DemiBold))

    header.addWidget(icon)
    header.addWidget(label, 1)

    layout.addLayout(header)
    layout.addWidget(widget)

    return wrap


def _display_section_header(
    window,
    icon_text: str,
    title: str,
    subtitle: str,
) -> QWidget:
    shell = QWidget()

    layout = QHBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    icon = QLabel(icon_text)
    icon.setObjectName("displaySectionIcon")
    icon.setFont(QFont(window.icon_font, 16))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFixedSize(30, 30)

    text = QVBoxLayout()
    text.setContentsMargins(0, 0, 0, 0)
    text.setSpacing(1)

    title_label = QLabel(title)
    title_label.setObjectName("displaySectionTitle")
    title_label.setFont(QFont(window.ui_font, 10, QFont.Weight.DemiBold))

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("displaySectionSubtitle")
    subtitle_label.setFont(QFont(window.ui_font, 8))
    subtitle_label.setWordWrap(True)

    text.addWidget(title_label)
    text.addWidget(subtitle_label)

    layout.addWidget(icon)
    layout.addLayout(text, 1)

    return shell


def _display_preview_monitor(window, display: dict, index: int) -> QWidget:
    enabled = bool(display.get("enabled", True))
    primary = bool(display.get("primary", False))
    name = str(display.get("name", f"Display {index + 1}")).strip()
    current_mode = str(display.get("current_mode", "")).strip()

    monitor = QFrame()
    monitor.setObjectName("displayPreviewMonitor")
    monitor.setProperty("primary", primary)
    monitor.setProperty("enabled", enabled)
    monitor.setMinimumHeight(82)
    monitor.setMaximumHeight(92)

    layout = QVBoxLayout(monitor)
    layout.setContentsMargins(10, 9, 10, 9)
    layout.setSpacing(5)

    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(6)

    icon = QLabel(material_icon("desktop_windows"))
    icon.setObjectName("displayPreviewIcon")
    icon.setFont(QFont(window.icon_font, 15))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title = QLabel(name)
    title.setObjectName("displayPreviewTitle")
    title.setFont(QFont(window.ui_font, 9, QFont.Weight.DemiBold))

    top.addWidget(icon)
    top.addWidget(title, 1)

    if primary:
        top.addWidget(_display_badge(window, "Primary", "primary"))

    meta = QLabel(current_mode or ("Active" if enabled else "Inactive"))
    meta.setObjectName("displayPreviewMeta")
    meta.setFont(QFont(window.ui_font, 8))

    bar = QFrame()
    bar.setObjectName("displayPreviewBar")
    bar.setMinimumHeight(6)
    bar.setMaximumHeight(6)

    layout.addLayout(top)
    layout.addWidget(meta)
    layout.addStretch(1)
    layout.addWidget(bar)

    return monitor


def _display_badge(window, text: str, variant: str) -> QWidget:
    badge = QLabel(text)
    badge.setObjectName("displayBadge")
    badge.setProperty("variant", variant)
    badge.setFont(QFont(window.ui_font, 7, QFont.Weight.DemiBold))
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return badge


def _display_metric_pill(
    window,
    icon_text: str,
    value: str,
    label: str,
) -> QWidget:
    pill = QFrame()
    pill.setObjectName("displayMetricPill")
    pill.setFixedWidth(116)

    layout = QHBoxLayout(pill)
    layout.setContentsMargins(9, 7, 9, 7)
    layout.setSpacing(7)

    icon = QLabel(icon_text)
    icon.setObjectName("displayMetricIcon")
    icon.setFont(QFont(window.icon_font, 14))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFixedSize(24, 24)

    text = QVBoxLayout()
    text.setContentsMargins(0, 0, 0, 0)
    text.setSpacing(0)

    value_label = QLabel(value)
    value_label.setObjectName("displayMetricValue")
    value_label.setFont(QFont(window.ui_font, 11, QFont.Weight.Bold))

    label_widget = QLabel(label)
    label_widget.setObjectName("displayMetricLabel")
    label_widget.setFont(QFont(window.ui_font, 7, QFont.Weight.DemiBold))

    text.addWidget(value_label)
    text.addWidget(label_widget)

    layout.addWidget(icon)
    layout.addLayout(text, 1)

    return pill


def _display_action_button(
    window,
    label: str,
    variant: str,
    icon_path: Path | None = None,
) -> QPushButton:
    button = QPushButton(label)
    button.setObjectName("displayActionButton")
    button.setProperty("variant", variant)
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    button.setFont(QFont(window.ui_font, 9, QFont.Weight.DemiBold))
    button.setMinimumHeight(32)
    if icon_path is not None and icon_path.exists():
        button.setIcon(QIcon(str(icon_path)))
    return button


def _display_empty_state(
    window,
    icon_text: str,
    title: str,
    body: str,
) -> QWidget:
    card = QFrame()
    card.setObjectName("displayEmptyState")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 24, 22, 24)
    layout.setSpacing(8)

    icon = QLabel(icon_text)
    icon.setObjectName("displayEmptyIcon")
    icon.setFont(QFont(window.icon_font, 34))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title_label = QLabel(title)
    title_label.setObjectName("displayEmptyTitle")
    title_label.setFont(QFont(window.ui_font, 12, QFont.Weight.DemiBold))
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    body_label = QLabel(body)
    body_label.setObjectName("displayEmptyBody")
    body_label.setFont(QFont(window.ui_font, 9))
    body_label.setWordWrap(True)
    body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(icon)
    layout.addWidget(title_label)
    layout.addWidget(body_label)

    return card


def _theme_color(window, attr: str, fallback: str) -> str:
    palette = getattr(window, "theme_palette", None)

    if palette is None:
        return fallback

    value = getattr(palette, attr, None)

    if isinstance(value, QColor):
        return value.name()

    text = str(value or "").strip()

    if text.startswith("#") or text.startswith("rgb") or text.startswith("hsl"):
        return text

    return fallback


def _apply_display_style(window) -> None:
    primary = _theme_color(window, "primary", "#d8b4fe")
    outline = _theme_color(window, "outline", "rgba(255,255,255,0.11)")

    qss = f"""
    QFrame#displayRootCard {{
        border: none;
        background: transparent;
    }}

    QFrame#displayHero {{
        border-radius: 24px;
        border: 1px solid {outline};
        background: qlineargradient(
            x1: 0, y1: 0,
            x2: 1, y2: 1,
            stop: 0 rgba(216, 180, 254, 0.22),
            stop: 0.42 rgba(255, 255, 255, 0.060),
            stop: 1 rgba(80, 60, 120, 0.16)
        );
    }}

    QLabel#displayHeroIcon {{
        border-radius: 19px;
        color: #201126;
        background: {primary};
    }}

    QLabel#displayKicker {{
        color: rgba(246,235,247,0.52);
        letter-spacing: 1px;
    }}

    QLabel#displayHeroTitle {{
        color: rgba(255,255,255,0.96);
    }}

    QLabel#displayHeroSubtitle {{
        color: rgba(246,235,247,0.62);
    }}

    QFrame#displayMetricPill {{
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.080);
        background: rgba(255,255,255,0.065);
    }}

    QLabel#displayMetricIcon {{
        border-radius: 8px;
        color: {primary};
        background: rgba(216,180,254,0.11);
    }}

    QLabel#displayMetricValue {{
        color: rgba(255,255,255,0.92);
    }}

    QLabel#displayMetricLabel {{
        color: rgba(246,235,247,0.45);
    }}

    QFrame#displayActionBar {{
        border-radius: 21px;
        border: 1px solid rgba(255,255,255,0.075);
        background: rgba(255,255,255,0.040);
    }}

    QLabel#displayActionHintIcon {{
        color: {primary};
    }}

    QLabel#displayActionHint {{
        color: rgba(246,235,247,0.52);
    }}

    QPushButton#displayActionButton {{
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.085);
        color: rgba(246,235,247,0.78);
        background: rgba(255,255,255,0.050);
        padding: 0 12px;
    }}

    QPushButton#displayActionButton:hover {{
        color: rgba(255,255,255,0.96);
        background: rgba(255,255,255,0.085);
    }}

    QPushButton#displayActionButton[variant="primary"] {{
        color: #201126;
        border: 1px solid rgba(255,255,255,0.16);
        background: {primary};
    }}

    QPushButton#displayActionButton[variant="primary"]:hover {{
        background: rgba(236,215,255,1);
    }}

    QFrame#displayPreviewCard,
    QFrame#displayPanelCard,
    QFrame#displayOutputCard,
    QFrame#displayFieldCard,
    QFrame#displayControlField,
    QFrame#displayStatusCard {{
        border-radius: 21px;
        border: 1px solid rgba(255,255,255,0.075);
        background: rgba(255,255,255,0.040);
    }}

    QLabel#displaySectionIcon {{
        border-radius: 10px;
        color: {primary};
        background: rgba(216,180,254,0.11);
        border: 1px solid rgba(216,180,254,0.13);
    }}

    QLabel#displaySectionTitle {{
        color: rgba(255,255,255,0.90);
    }}

    QLabel#displaySectionSubtitle {{
        color: rgba(246,235,247,0.50);
    }}

    QFrame#displayPreviewMonitor {{
        border-radius: 17px;
        border: 1px solid rgba(255,255,255,0.070);
        background: rgba(255,255,255,0.040);
    }}

    QFrame#displayPreviewMonitor:hover {{
        border: 1px solid rgba(216,180,254,0.22);
        background: rgba(255,255,255,0.060);
    }}

    QFrame#displayPreviewMonitor[primary="true"] {{
        border: 1px solid rgba(216,180,254,0.46);
        background: rgba(216,180,254,0.095);
    }}

    QFrame#displayPreviewMonitor[enabled="false"] {{
        border: 1px solid rgba(255,255,255,0.045);
        background: rgba(255,255,255,0.020);
    }}

    QLabel#displayPreviewIcon {{
        color: {primary};
    }}

    QLabel#displayPreviewTitle {{
        color: rgba(255,255,255,0.88);
    }}

    QLabel#displayPreviewMeta {{
        color: rgba(246,235,247,0.48);
    }}

    QFrame#displayPreviewBar {{
        border-radius: 3px;
        background: {primary};
    }}

    QFrame#displayFieldCard:hover {{
        border: 1px solid rgba(216,180,254,0.20);
        background: rgba(255,255,255,0.060);
    }}

    QLabel#displayFieldIcon {{
        border-radius: 8px;
        color: {primary};
        background: rgba(216,180,254,0.10);
    }}

    QLabel#displayFieldTitle {{
        color: rgba(255,255,255,0.86);
    }}

    QLabel#displayFieldDescription {{
        color: rgba(246,235,247,0.46);
    }}

    QFrame#displayOutputCard:hover {{
        border: 1px solid rgba(216,180,254,0.20);
        background: rgba(255,255,255,0.060);
    }}

    QLabel#displayOutputIcon {{
        border-radius: 14px;
        color: {primary};
        background: rgba(216,180,254,0.11);
        border: 1px solid rgba(216,180,254,0.13);
    }}

    QLabel#displayOutputTitle {{
        color: rgba(255,255,255,0.91);
    }}

    QLabel#displayOutputSubtitle {{
        color: rgba(246,235,247,0.48);
    }}

    QLabel#displayBadge {{
        border-radius: 9px;
        padding: 2px 7px;
        color: rgba(246,235,247,0.72);
        background: rgba(255,255,255,0.060);
        border: 1px solid rgba(255,255,255,0.060);
    }}

    QLabel#displayBadge[variant="primary"] {{
        color: #201126;
        background: {primary};
        border: 1px solid rgba(255,255,255,0.14);
    }}

    QLabel#displayBadge[variant="active"] {{
        color: rgba(210,255,224,0.88);
        background: rgba(80,210,130,0.12);
        border: 1px solid rgba(80,210,130,0.16);
    }}

    QLabel#displayBadge[variant="inactive"] {{
        color: rgba(246,235,247,0.42);
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.045);
    }}

    QFrame#displayControlField:hover {{
        border: 1px solid rgba(216,180,254,0.18);
        background: rgba(255,255,255,0.060);
    }}

    QLabel#displayControlIcon {{
        color: {primary};
    }}

    QLabel#displayControlLabel {{
        color: rgba(246,235,247,0.58);
    }}

    QComboBox#displayCombo {{
        min-height: 30px;
        border-radius: 11px;
        border: 1px solid rgba(255,255,255,0.075);
        color: rgba(255,255,255,0.90);
        background: rgba(0,0,0,0.16);
        padding: 0 10px;
        selection-background-color: {primary};
        selection-color: #201126;
    }}

    QComboBox#displayCombo:hover {{
        border: 1px solid rgba(216,180,254,0.24);
        background: rgba(0,0,0,0.20);
    }}

    QComboBox#displayCombo:focus {{
        border: 1px solid rgba(216,180,254,0.46);
        background: rgba(0,0,0,0.22);
    }}

    QComboBox#displayCombo::drop-down {{
        border: none;
        width: 26px;
    }}

    QComboBox#displayCombo QAbstractItemView {{
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.10);
        color: rgba(255,255,255,0.90);
        background: rgba(25,18,30,0.98);
        selection-background-color: rgba(216,180,254,0.24);
        selection-color: rgba(255,255,255,0.96);
        padding: 6px;
        outline: none;
    }}

    QFrame#displayStatusCard {{
        border-radius: 21px;
    }}

    QLabel#displayStatusIcon {{
        border-radius: 8px;
        color: {primary};
        background: rgba(216,180,254,0.10);
    }}

    QLabel#displayStatusText {{
        color: rgba(246,235,247,0.55);
    }}

    QLabel#picomTitle {{
        color: rgba(255,255,255,0.92);
    }}

    QLabel#picomSubtitle,
    QLabel#picomStatus {{
        color: rgba(246,235,247,0.62);
    }}

    QFrame#displayPanelCard QFrame#settingsRow {{
        border-radius: 15px;
        border: 1px solid rgba(255,255,255,0.055);
        background: rgba(255,255,255,0.040);
    }}

    QFrame#displayPanelCard QFrame#settingsRow:hover {{
        border: 1px solid rgba(216,180,254,0.18);
        background: rgba(255,255,255,0.060);
    }}

    QFrame#displayPanelCard QFrame#rowIconWrap {{
        border-radius: 9px;
        border: 1px solid rgba(216,180,254,0.13);
        background: rgba(216,180,254,0.10);
    }}

    QFrame#displayPanelCard QLabel#settingsRowTitle {{
        color: rgba(255,255,255,0.88);
    }}

    QFrame#displayPanelCard QLabel#settingsRowDetail {{
        color: rgba(246,235,247,0.52);
    }}

    QFrame#displayEmptyState {{
        border-radius: 21px;
        border: 1px dashed rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.030);
    }}

    QLabel#displayEmptyIcon {{
        color: {primary};
    }}

    QLabel#displayEmptyTitle {{
        color: rgba(255,255,255,0.88);
    }}

    QLabel#displayEmptyBody {{
        color: rgba(246,235,247,0.52);
    }}

    QScrollBar:vertical {{
        width: 8px;
        background: transparent;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        min-height: 28px;
        border-radius: 4px;
        background: rgba(246,235,247,0.18);
    }}

    QScrollBar::handle:vertical:hover {{
        background: rgba(246,235,247,0.28);
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    """

    current = window.styleSheet() or ""

    marker = "QFrame#displayRootCard"
    if marker not in current:
        window.setStyleSheet(current + "\n" + qss)
