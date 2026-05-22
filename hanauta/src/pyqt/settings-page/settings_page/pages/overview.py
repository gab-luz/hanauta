from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QCursor, QFont, QPixmap
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
from settings_page.pages.metrics import build_metric_card

_ASSETS_DIR = Path(__file__).resolve().parents[4] / "assets"


def build_overview_page(window) -> QWidget:
    _apply_overview_style(window)

    return window._scroll_page(
        build_overview_hero_card(window),
        build_system_overview_card(window),
        build_overview_actions_card(window),
        window._build_profile_card(),
    )


def build_overview_hero_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("overviewHeroCard")
    card.setMinimumHeight(118)
    card.setMaximumHeight(142)

    layout = QHBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(14)

    profile = window._profile_state()
    name = str(profile.get("nickname") or profile.get("first_name") or "").strip()
    greeting = "Welcome back" + (f", {name}" if name else "")
    is_dark = _safe_setting(window, "appearance", "theme_choice", "dark").lower() == "dark"
    hero_text = "#F5F1F8" if is_dark else "#1D1B20"
    hero_muted = "#CDC3D3" if is_dark else "#514A57"
    hero_icon_fg = "#F5F1F8" if is_dark else _theme_color(window, "on_primary", "#201126")

    hero_icon = IconLabel(
        material_icon("auto_awesome"),
        window.icon_font,
        24,
        hero_icon_fg,
    )
    hero_icon.setObjectName("overviewHeroIcon")
    hero_icon.setFixedSize(56, 56)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(3)

    kicker = QLabel("HANAUTA CONTROL CENTER")
    kicker.setObjectName("overviewKicker")
    kicker.setFont(QFont(window.ui_font, 8, QFont.Weight.DemiBold))
    kicker.setStyleSheet(f"color: {hero_muted};")

    heading = QLabel(greeting)
    heading.setObjectName("overviewHeroTitle")

    heading_font = QFont(window.display_font, 20, QFont.Weight.DemiBold)
    heading_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    heading.setFont(heading_font)
    heading.setStyleSheet(f"color: {hero_text};")

    summary = QLabel(
        "Tune appearance, services, plugins and shell behavior without leaving your workflow."
    )
    summary.setObjectName("overviewHeroSummary")
    summary.setWordWrap(True)

    summary_font = QFont(window.ui_font, 9)
    summary_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    summary.setFont(summary_font)
    summary.setStyleSheet(f"color: {hero_muted};")

    chip_row = QHBoxLayout()
    chip_row.setContentsMargins(0, 5, 0, 0)
    chip_row.setSpacing(7)

    appearance = window.settings_state.get("appearance", {})
    theme_choice = str(appearance.get("theme_choice", "dark")).strip().lower()
    accent = str(appearance.get("accent", "orchid")).strip()

    chip_row.addWidget(
        _overview_chip(
            window,
            material_icon("dark_mode" if theme_choice == "dark" else "light_mode"),
            f"Theme: {theme_choice or 'dark'}",
            text_color=hero_text,
            icon_color=hero_text,
        )
    )
    chip_row.addWidget(
        _overview_chip(
            window,
            material_icon("palette"),
            f"Accent: {accent or 'orchid'}",
            text_color=hero_text,
            icon_color=hero_text,
        )
    )
    chip_row.addStretch(1)

    text_col.addWidget(kicker)
    text_col.addWidget(heading)
    text_col.addWidget(summary)
    text_col.addLayout(chip_row)

    right_col = QVBoxLayout()
    right_col.setContentsMargins(0, 0, 0, 0)
    right_col.setSpacing(8)

    shell_mode = _safe_setting(window, "appearance", "theme_choice", "dark")
    accent_mode = _safe_setting(window, "appearance", "accent", "orchid")

    right_col.addWidget(
        _hero_status_pill(
            window,
            material_icon("terminal"),
            "Shell",
            "i3 session",
            title_color=hero_text,
            subtitle_color=hero_muted,
            icon_color=hero_text,
        )
    )
    right_col.addWidget(
        _hero_status_pill(
            window,
            material_icon("tune"),
            str(shell_mode).title(),
            str(accent_mode).title(),
            title_color=hero_text,
            subtitle_color=hero_muted,
            icon_color=hero_text,
        )
    )

    layout.addWidget(hero_icon)
    layout.addLayout(text_col, 1)
    layout.addLayout(right_col)

    window.overview_status = QLabel("")
    window.overview_status.setObjectName("overviewStatusText")
    window.overview_status.setWordWrap(True)

    return card


def build_system_overview_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("overviewPanelCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 13, 14, 14)
    layout.setSpacing(11)

    layout.addWidget(
        _section_header(
            window,
            material_icon("grid_view"),
            "System Overview",
            "Quick info for this session and shell environment.",
        )
    )

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(9)
    grid.setVerticalSpacing(9)

    window.system_overview_labels = {}
    is_dark = _safe_setting(window, "appearance", "theme_choice", "dark").lower() == "dark"
    metric_value_color = "#F5F1F8" if is_dark else "#1D1B20"

    keys = ("Host", "Kernel", "Session", "Python", "Uptime", "Screen")

    for index, key in enumerate(keys):
        label = QLabel("...")
        label.setObjectName("overviewMetricValue")
        label.setStyleSheet(f"color: {metric_value_color};")

        label_font = QFont(window.ui_font, 10, QFont.Weight.DemiBold)
        label_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        label.setFont(label_font)

        window.system_overview_labels[key] = label

        metric = build_metric_card(window, key, label)
        metric.setObjectName("overviewMetricCard")

        grid.addWidget(metric, index // 3, index % 3)

    layout.addLayout(grid)

    return card


def build_overview_actions_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("overviewPanelCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 13, 14, 14)
    layout.setSpacing(11)

    layout.addWidget(
        _section_header(
            window,
            material_icon("bolt"),
            "Quick actions",
            "Common operations for the shell and plugin workspace.",
        )
    )

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(9)
    grid.setVerticalSpacing(9)
    is_dark = _safe_setting(window, "appearance", "theme_choice", "dark").lower() == "dark"
    action_bg = "rgba(32, 24, 41, 0.96)" if is_dark else "rgba(255,255,255,0.90)"
    action_bg_hover = "rgba(44, 33, 56, 0.98)" if is_dark else "rgba(245,245,245,0.96)"
    action_border = "rgba(255,255,255,0.14)" if is_dark else "rgba(0,0,0,0.12)"

    reload_i3 = ActionCard(
        material_icon("restart_alt"),
        "Reload i3",
        "Re-read i3 config without logging out",
        window.icon_font,
        window.ui_font,
    )
    reload_i3.setObjectName("overviewActionCard")
    reload_i3.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    reload_i3.setMinimumHeight(78)
    reload_i3.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {action_bg};
            border: 1px solid {action_border};
            border-radius: 17px;
        }}
        QPushButton:hover {{
            background-color: {action_bg_hover};
            border: 1px solid rgba(216,180,254,0.30);
        }}
        """
    )

    def _do_reload_i3() -> None:
        ok = window._reload_i3_keybindings()

        if hasattr(window, "overview_status"):
            window.overview_status.setText(
                "i3 reloaded." if ok else "i3 reload failed. Check i3-msg output."
            )

    reload_i3.clicked.connect(_do_reload_i3)

    bar_icons = ActionCard(
        material_icon("image"),
        "Bar icons",
        "Open the bar icon overrides file",
        window.icon_font,
        window.ui_font,
    )
    bar_icons.setObjectName("overviewActionCard")
    bar_icons.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    bar_icons.setMinimumHeight(78)
    bar_icons.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {action_bg};
            border: 1px solid {action_border};
            border-radius: 17px;
        }}
        QPushButton:hover {{
            background-color: {action_bg_hover};
            border: 1px solid rgba(216,180,254,0.30);
        }}
        """
    )
    bar_icons.clicked.connect(window._open_bar_icon_config)

    plugin_dir = ActionCard(
        material_icon("folder_open"),
        "Plugin folder",
        "Open the plugin install directory",
        window.icon_font,
        window.ui_font,
    )
    plugin_dir.setObjectName("overviewActionCard")
    plugin_dir.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    plugin_dir.setMinimumHeight(78)
    plugin_dir.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {action_bg};
            border: 1px solid {action_border};
            border-radius: 17px;
        }}
        QPushButton:hover {{
            background-color: {action_bg_hover};
            border: 1px solid rgba(216,180,254,0.30);
        }}
        """
    )
    plugin_dir.clicked.connect(window._marketplace_open_install_dir)

    grid.addWidget(reload_i3, 0, 0)
    grid.addWidget(bar_icons, 0, 1)
    grid.addWidget(plugin_dir, 0, 2)

    layout.addLayout(grid)

    status_box = QFrame()
    status_box.setObjectName("overviewStatusBox")

    status_layout = QHBoxLayout(status_box)
    status_layout.setContentsMargins(10, 8, 10, 8)
    status_layout.setSpacing(8)

    status_icon = QLabel("")
    status_icon.setObjectName("overviewStatusIcon")
    status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status_icon.setFixedSize(22, 22)
    check_svg = _ASSETS_DIR / "check.svg"
    pix = QPixmap(str(check_svg))
    if not pix.isNull():
        status_icon.setPixmap(
            pix.scaled(
                16,
                16,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    else:
        status_icon.setText(material_icon("check"))
        status_icon.setStyleSheet("color: #7EE081;")
        status_icon.setFont(QFont(window.icon_font, 15))

    if not hasattr(window, "overview_status"):
        window.overview_status = QLabel("")

    window.overview_status.setObjectName("overviewStatusText")
    window.overview_status.setFont(QFont(window.ui_font, 8))
    window.overview_status.setText(
        window.overview_status.text() or "Ready. Choose an action above when needed."
    )
    window.overview_status.setWordWrap(True)
    is_dark = _safe_setting(window, "appearance", "theme_choice", "dark").lower() == "dark"
    status_text = "#F5F1F8" if is_dark else "#1D1B20"
    window.overview_status.setStyleSheet(f"color: {status_text};")

    status_layout.addWidget(status_icon)
    status_layout.addWidget(window.overview_status, 1)

    layout.addWidget(status_box)

    return card


def _section_header(
    window,
    icon_text: str,
    title: str,
    subtitle: str,
) -> QWidget:
    is_dark = _safe_setting(window, "appearance", "theme_choice", "dark").lower() == "dark"
    section_text = "#F5F1F8" if is_dark else "#1D1B20"
    section_muted = "#CDC3D3" if is_dark else "#514A57"
    shell = QWidget()

    layout = QHBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    icon = QLabel(icon_text)
    icon.setObjectName("overviewSectionIcon")
    icon.setFont(QFont(window.icon_font, 16))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFixedSize(30, 30)
    icon.setStyleSheet(f"color: {section_text};")

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(1)

    title_label = QLabel(title)
    title_label.setObjectName("overviewSectionTitle")

    title_font = QFont(window.display_font, 12, QFont.Weight.DemiBold)
    title_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    title_label.setFont(title_font)
    title_label.setStyleSheet(f"color: {section_text};")

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("overviewSectionSubtitle")
    subtitle_label.setWordWrap(True)

    subtitle_font = QFont(window.ui_font, 8)
    subtitle_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    subtitle_label.setFont(subtitle_font)
    subtitle_label.setStyleSheet(f"color: {section_muted};")

    text_col.addWidget(title_label)
    text_col.addWidget(subtitle_label)

    layout.addWidget(icon)
    layout.addLayout(text_col, 1)

    return shell


def _overview_chip(
    window,
    icon_text: str,
    text: str,
    text_color: str | None = None,
    icon_color: str | None = None,
) -> QWidget:
    chip = QFrame()
    chip.setObjectName("overviewChip")

    layout = QHBoxLayout(chip)
    layout.setContentsMargins(8, 4, 9, 4)
    layout.setSpacing(5)

    icon = QLabel(icon_text)
    icon.setObjectName("overviewChipIcon")
    icon.setFont(QFont(window.icon_font, 12))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if icon_color:
        icon.setStyleSheet(f"color: {icon_color};")

    label = QLabel(text)
    label.setObjectName("overviewChipText")
    label.setFont(QFont(window.ui_font, 8, QFont.Weight.DemiBold))
    if text_color:
        label.setStyleSheet(f"color: {text_color};")

    layout.addWidget(icon)
    layout.addWidget(label)

    return chip


def _hero_status_pill(
    window,
    icon_text: str,
    title: str,
    subtitle: str,
    title_color: str | None = None,
    subtitle_color: str | None = None,
    icon_color: str | None = None,
) -> QWidget:
    pill = QFrame()
    pill.setObjectName("overviewHeroPill")
    pill.setFixedWidth(118)

    layout = QHBoxLayout(pill)
    layout.setContentsMargins(9, 7, 9, 7)
    layout.setSpacing(7)

    icon = QLabel(icon_text)
    icon.setObjectName("overviewHeroPillIcon")
    icon.setFont(QFont(window.icon_font, 14))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFixedSize(24, 24)
    if icon_color:
        icon.setStyleSheet(f"color: {icon_color};")

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(0)

    title_label = QLabel(title)
    title_label.setObjectName("overviewHeroPillTitle")
    title_label.setFont(QFont(window.ui_font, 8, QFont.Weight.DemiBold))
    if title_color:
        title_label.setStyleSheet(f"color: {title_color};")

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("overviewHeroPillSubtitle")
    subtitle_label.setFont(QFont(window.ui_font, 7))
    if subtitle_color:
        subtitle_label.setStyleSheet(f"color: {subtitle_color};")

    text_col.addWidget(title_label)
    text_col.addWidget(subtitle_label)

    layout.addWidget(icon)
    layout.addLayout(text_col, 1)

    return pill


def _safe_setting(window, section: str, key: str, fallback: str) -> str:
    settings = getattr(window, "settings_state", {})
    if not isinstance(settings, dict):
        return fallback

    section_data = settings.get(section, {})
    if not isinstance(section_data, dict):
        return fallback

    value = str(section_data.get(key, fallback)).strip()
    return value or fallback


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


def _apply_overview_style(window) -> None:
    primary = _theme_color(window, "primary", "#d8b4fe")
    on_primary = _theme_color(window, "on_primary", "#201126")
    text = _theme_color(window, "on_surface", "rgba(255,255,255,0.96)")
    text_muted = _theme_color(window, "on_surface_variant", "rgba(246,235,247,0.72)")
    surface = _theme_color(window, "surface", "#151018")
    surface_container = _theme_color(window, "surface_container", "#211823")
    primary_container = _theme_color(window, "primary_container", "#372044")
    outline = _theme_color(window, "outline", "rgba(255,255,255,0.11)")

    qss = f"""
    QFrame#overviewHeroCard {{
        border-radius: 24px;
        border: 1px solid {outline};
        background: qlineargradient(
            x1: 0, y1: 0,
            x2: 1, y2: 1,
            stop: 0 {primary_container},
            stop: 0.45 {surface_container},
            stop: 1 {surface}
        );
    }}

    QLabel#overviewHeroIcon {{
        border-radius: 19px;
        color: {on_primary};
        background: {primary};
    }}

    QLabel#overviewKicker {{
        color: {text_muted};
        letter-spacing: 1px;
    }}

    QLabel#overviewHeroTitle {{
        color: {text};
    }}

    QLabel#overviewHeroSummary {{
        color: {text_muted};
    }}

    QFrame#overviewChip {{
        border-radius: 11px;
        border: 1px solid rgba(255,255,255,0.075);
        background: rgba(255,255,255,0.060);
    }}

    QLabel#overviewChipIcon {{
        color: {primary};
    }}

    QLabel#overviewChipText {{
        color: {text};
    }}

    QFrame#overviewHeroPill {{
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.080);
        background: rgba(255,255,255,0.065);
    }}

    QLabel#overviewHeroPillIcon {{
        border-radius: 8px;
        color: {primary};
        background: rgba(216,180,254,0.11);
    }}

    QLabel#overviewHeroPillTitle {{
        color: {text};
    }}

    QLabel#overviewHeroPillSubtitle {{
        color: {text_muted};
    }}

    QFrame#overviewPanelCard {{
        border-radius: 21px;
        border: 1px solid rgba(255,255,255,0.075);
        background: rgba(255,255,255,0.040);
    }}

    QLabel#overviewSectionIcon {{
        border-radius: 10px;
        color: {text};
        background: rgba(216,180,254,0.11);
        border: 1px solid rgba(216,180,254,0.13);
    }}

    QLabel#overviewSectionTitle {{
        color: {text};
    }}

    QLabel#overviewSectionSubtitle {{
        color: {text_muted};
    }}

    QFrame#overviewMetricCard {{
        border-radius: 17px;
        border: 1px solid rgba(255,255,255,0.065);
        background: rgba(255,255,255,0.038);
    }}

    QFrame#overviewMetricCard:hover {{
        border: 1px solid rgba(216,180,254,0.22);
        background: rgba(255,255,255,0.055);
    }}

    QLabel#overviewMetricValue {{
        color: {text};
    }}

    QPushButton#overviewActionCard {{
        border-radius: 17px;
        border: 1px solid rgba(255,255,255,0.10);
        background-color: rgba(255,255,255,0.09);
    }}

    QPushButton#overviewActionCard:hover {{
        border: 1px solid rgba(216,180,254,0.28);
        background-color: rgba(255,255,255,0.14);
    }}

    QPushButton#overviewActionCard QFrame#actionIconWrap {{
        border-radius: 10px;
        background: rgba(216,180,254,0.12);
        border: 1px solid rgba(216,180,254,0.16);
    }}

    QPushButton#overviewActionCard QLabel[iconRole="true"] {{
        color: {text};
    }}

    QPushButton#overviewActionCard QLabel#actionCardTitle {{
        color: {text};
    }}

    QPushButton#overviewActionCard QLabel#actionCardDetail {{
        color: {text_muted};
    }}

    QFrame#overviewMetricCard QLabel[mutedText="true"] {{
        color: {text_muted};
    }}

    QFrame#overviewStatusBox {{
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.060);
        background: rgba(255,255,255,0.034);
    }}

    QLabel#overviewStatusIcon {{
        border-radius: 8px;
        color: {text};
        background: rgba(216,180,254,0.10);
    }}

    QLabel#overviewStatusText {{
        color: {text_muted};
    }}
    """

    current = window.styleSheet() or ""

    marker = "QFrame#overviewHeroCard"
    if marker not in current:
        window.setStyleSheet(current + "\n" + qss)
