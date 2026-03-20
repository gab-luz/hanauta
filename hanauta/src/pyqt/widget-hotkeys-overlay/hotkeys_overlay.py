#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Animated PyQt6 overlay for current i3 hotkeys.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QKeySequence, QPalette, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


from pyqt.shared.runtime import fonts_root, project_root, source_root
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.button_helpers import create_close_button

ROOT = project_root()
APP_DIR = source_root()
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

FONTS_DIR = fonts_root()
I3_CONFIG = ROOT / "config"

MATERIAL_ICONS = {
    "apps": "\ue5c3",
    "close": "\ue5cd",
    "keyboard": "\ue312",
    "rocket": "\ue539",
    "search": "\ue8b6",
    "stars": "\ue8d0",
}


@dataclass(frozen=True)
class HotkeyItem:
    keys: str
    command: str
    detail: str
    section: str


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "material_symbols_outlined": FONTS_DIR / "MaterialSymbolsOutlined.ttf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
    }
    for key, path in font_map.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def parse_i3_variables(lines: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    pattern = re.compile(r'^set\s+(\$\S+)\s+"?([^"]+)"?$')
    for line in lines:
        stripped = line.strip()
        match = pattern.match(stripped)
        if match:
            variables[match.group(1)] = match.group(2).strip()
    return variables


def replace_variables(text: str, variables: dict[str, str]) -> str:
    result = text
    for name, value in sorted(variables.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(name, value)
    return result


def classify_binding(detail: str, command: str) -> str:
    joined = f"{detail} {command}".lower()
    if "workspace" in joined:
        return "Workspaces"
    if any(token in joined for token in ("focus", "move left", "move right", "move up", "move down", "fullscreen", "split ")):
        return "Layout"
    if any(token in joined for token in ("reload", "restart", "lock", "kill")):
        return "Session"
    if any(token in joined for token in ("launcher", "terminal", "flameshot", "window switcher", "clipboard", "powermenu")):
        return "Launch"
    return "General"


def parse_hotkeys(config_path: Path) -> list[HotkeyItem]:
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    variables = parse_i3_variables(lines)
    items: list[HotkeyItem] = []
    pending_detail = ""
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            pending_detail = ""
            continue
        if stripped.startswith("#"):
            comment = stripped.lstrip("#").strip()
            if comment and not comment.startswith("format:") and not comment.startswith("bspwm:"):
                pending_detail = comment
            continue
        if not stripped.startswith("bindsym "):
            pending_detail = ""
            continue

        parts = stripped.split()
        index = 1
        while index < len(parts) and parts[index].startswith("--"):
            index += 1
        if index >= len(parts):
            continue
        keys = replace_variables(parts[index], variables)
        command = replace_variables(" ".join(parts[index + 1 :]), variables)
        detail = pending_detail or command
        section = classify_binding(detail, command)
        items.append(HotkeyItem(keys=keys, command=command, detail=detail, section=section))
        pending_detail = ""
    return items


def primary_screen() -> object | None:
    primary_name = ""
    primary_pos: tuple[int, int] | None = None
    try:
        output = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        ).stdout
    except Exception:
        output = ""

    for line in output.splitlines():
        if " connected primary " not in line:
            continue
        primary_name = line.split()[0]
        match = re.search(r"\d+x\d+\+(-?\d+)\+(-?\d+)", line)
        if match:
            primary_pos = (int(match.group(1)), int(match.group(2)))
        break

    for screen in QGuiApplication.screens():
        if primary_name and screen.name() == primary_name:
            return screen

    for screen in QGuiApplication.screens():
        geometry = screen.geometry()
        if primary_pos and geometry.x() == primary_pos[0] and geometry.y() == primary_pos[1]:
            return screen

    return QApplication.primaryScreen()


class HotkeyCard(QFrame):
    def __init__(self, title: str, items: list[HotkeyItem], material_font: str, mono_font: str, ui_font: str) -> None:
        super().__init__()
        self.setObjectName("hotkeyCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        icon = QLabel(material_icon("keyboard"))
        icon.setObjectName("sectionIcon")
        icon.setFont(QFont(material_font, 18))

        heading_wrap = QVBoxLayout()
        heading_wrap.setContentsMargins(0, 0, 0, 0)
        heading_wrap.setSpacing(2)

        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        heading.setFont(QFont(ui_font, 12, QFont.Weight.DemiBold))
        sub = QLabel(f"{len(items)} bindings")
        sub.setObjectName("sectionSubtitle")
        sub.setFont(QFont(ui_font, 9, QFont.Weight.Medium))

        heading_wrap.addWidget(heading)
        heading_wrap.addWidget(sub)
        header.addWidget(icon)
        header.addLayout(heading_wrap, 1)
        root.addLayout(header)

        for item in items:
            row = QFrame()
            row.setObjectName("bindingRow")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 12, 12, 12)
            row_layout.setSpacing(8)

            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            top.setSpacing(10)

            keys = QLabel(item.keys)
            keys.setObjectName("bindingKeys")
            keys.setFont(QFont(mono_font, 10, QFont.Weight.DemiBold))
            keys.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            detail = QLabel(item.detail)
            detail.setObjectName("bindingTitle")
            detail.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
            detail.setWordWrap(True)

            top.addWidget(keys, 0, Qt.AlignmentFlag.AlignTop)
            top.addWidget(detail, 1)

            command = QLabel(item.command)
            command.setObjectName("bindingCommand")
            command.setWordWrap(True)
            command.setFont(QFont(ui_font, 9))

            row_layout.addLayout(top)
            row_layout.addWidget(command)
            root.addWidget(row)

        root.addStretch(1)


class HotkeysOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.material_font = detect_font(
            self.loaded_fonts.get("material_icons", ""),
            self.loaded_fonts.get("material_icons_outlined", ""),
            self.loaded_fonts.get("material_symbols_outlined", ""),
            self.loaded_fonts.get("material_symbols_rounded", ""),
            "Material Icons",
            "Material Icons Outlined",
            "Material Symbols Outlined",
            "Material Symbols Rounded",
        )
        self.ui_font = detect_font("Inter", "Noto Sans", "DejaVu Sans", "Sans Serif")
        self.display_font = detect_font("Outfit", "Inter", "Noto Sans", "Sans Serif")
        self.mono_font = detect_font("JetBrains Mono", "DejaVu Sans Mono", "Monospace")
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._card_effects: list[QGraphicsOpacityEffect] = []
        self._card_anims: list[QPropertyAnimation] = []
        self._intro_group: QParallelAnimationGroup | None = None

        self._setup_window()
        self._build_ui()
        self._apply_shadow()
        self._apply_styles()
        self._start_intro_animation()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _setup_window(self) -> None:
        self.setWindowTitle("Hanauta Hotkeys")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        screen = primary_screen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scrim = QFrame()
        self.scrim.setObjectName("scrim")

        self.shell = QFrame(self.scrim)
        self.shell.setObjectName("shell")
        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(28, 28, 28, 24)
        shell_layout.setSpacing(18)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(16)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)

        eyebrow = QLabel("I3 KEYBOARD MAP")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))

        title = QLabel("Current Hotkeys")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 28, QFont.Weight.Bold))

        subtitle = QLabel("Animated overlay generated from your current i3 config. Press Esc or use the close button.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont(self.ui_font, 10))

        title_wrap.addWidget(eyebrow)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        close_button = create_close_button(
            material_icon("close"),
            self.material_font,
            font_size=22,
            object_name="closeButton",
        )
        close_button.clicked.connect(self.close)

        header.addLayout(title_wrap, 1)
        header.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)
        shell_layout.addLayout(header)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(10)

        hotkeys = parse_hotkeys(I3_CONFIG)
        sections: dict[str, list[HotkeyItem]] = {}
        for item in hotkeys:
            sections.setdefault(item.section, []).append(item)

        for icon_name, text in (
            ("apps", f"{len(hotkeys)} bindings"),
            ("rocket", f"{len(sections)} groups"),
            ("stars", "Alt+F1 opens this overlay"),
        ):
            chip = QLabel(f"{material_icon(icon_name)}  {text}")
            chip.setObjectName("summaryChip")
            chip.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
            summary_row.addWidget(chip, 0)
        summary_row.addStretch(1)
        shell_layout.addLayout(summary_row)

        scroll = QScrollArea()
        scroll.setObjectName("scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        ordered_sections = ["Launch", "Workspaces", "Layout", "Session", "General"]
        cards: list[HotkeyCard] = []
        for name in ordered_sections:
            items = sections.get(name, [])
            if not items:
                continue
            card = HotkeyCard(name, items, self.material_font, self.mono_font, self.ui_font)
            cards.append(card)

        for index, card in enumerate(cards):
            row = index // 2
            col = index % 2
            grid.addWidget(card, row, col)

            effect = QGraphicsOpacityEffect(card)
            effect.setOpacity(0.0)
            card.setGraphicsEffect(effect)
            self._card_effects.append(effect)

        if len(cards) % 2 == 1:
            grid.setColumnStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        scroll.setWidget(content)
        shell_layout.addWidget(scroll, 1)

        root.addWidget(self.scrim, 1)

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(54)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.shell.setGraphicsEffect(shadow)

        QShortcut(QKeySequence("Escape"), self, activated=self.close)

        self.shell_effect = QGraphicsOpacityEffect(self.shell)
        self.shell_effect.setOpacity(0.0)
        self.shell.setGraphicsEffect(self.shell_effect)

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
            }}
            QFrame#scrim {{
                background: {rgba(theme.background, 0.70)};
            }}
            QFrame#shell {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {rgba(theme.surface_container_high, 0.98)},
                    stop:1 {rgba(theme.surface_container, 0.98)}
                );
                border: 1px solid {theme.panel_border};
                border-radius: 30px;
            }}
            QLabel#eyebrow {{
                color: {theme.primary};
                letter-spacing: 2px;
            }}
            QLabel#title {{
                color: {theme.text};
            }}
            QLabel#subtitle {{
                color: {theme.text_muted};
            }}
            QPushButton#closeButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 20px;
                color: {theme.icon};
                font-family: "{self.material_font}";
                min-width: 42px;
                max-width: 42px;
                min-height: 42px;
                max-height: 42px;
            }}
            QPushButton#closeButton:hover {{
                background: {theme.hover_bg};
            }}
            QLabel#summaryChip {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 16px;
                color: {theme.text};
                padding: 10px 14px;
            }}
            QScrollArea#scroll {{
                background: transparent;
            }}
            QFrame#hotkeyCard {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 22px;
            }}
            QLabel#sectionIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            QLabel#sectionTitle {{
                color: {theme.text};
            }}
            QLabel#sectionSubtitle {{
                color: {theme.text_muted};
            }}
            QFrame#bindingRow {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 18px;
            }}
            QFrame#bindingRow:hover {{
                background: {theme.hover_bg};
            }}
            QLabel#bindingKeys {{
                background: {theme.accent_soft};
                border: 1px solid {theme.app_focused_border};
                border-radius: 12px;
                color: {theme.primary};
                padding: 6px 10px;
            }}
            QLabel#bindingTitle {{
                color: {theme.text};
            }}
            QLabel#bindingCommand {{
                color: {theme.text_muted};
            }}
            """
        )

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()

    def _start_intro_animation(self) -> None:
        self._intro_group = QParallelAnimationGroup(self)

        shell_opacity = QPropertyAnimation(self.shell_effect, b"opacity", self)
        shell_opacity.setDuration(320)
        shell_opacity.setStartValue(0.0)
        shell_opacity.setEndValue(1.0)
        shell_opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._intro_group.addAnimation(shell_opacity)

        shell_start = self.shell.pos() + QPoint(0, 24)
        shell_end = self.shell.pos()
        shell_slide = QPropertyAnimation(self.shell, b"pos", self)
        shell_slide.setDuration(420)
        shell_slide.setStartValue(shell_start)
        shell_slide.setEndValue(shell_end)
        shell_slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._intro_group.addAnimation(shell_slide)

        for index, effect in enumerate(self._card_effects):
            fade_anim = QPropertyAnimation(effect, b"opacity", self)
            fade_anim.setDuration(300 + index * 45)
            fade_anim.setStartValue(0.0)
            fade_anim.setKeyValueAt(0.18, 0.0)
            fade_anim.setEndValue(1.0)
            fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._card_anims.append(fade_anim)
            self._intro_group.addAnimation(fade_anim)

        QTimer.singleShot(0, self._intro_group.start)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        shell_rect = self.shell.geometry().translated(self.scrim.pos())
        if not shell_rect.contains(event.position().toPoint()):
            self.close()
            return
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.scrim.setGeometry(self.rect())
        margin_x = max(24, self.width() // 18)
        margin_y = max(24, self.height() // 18)
        self.shell.setGeometry(QRect(
            margin_x,
            margin_y,
            max(720, self.width() - margin_x * 2),
            max(480, self.height() - margin_y * 2),
        ))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("HanautaHotkeys")
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    app.setPalette(palette)

    overlay = HotkeysOverlay()
    overlay.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
