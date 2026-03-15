#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Horizontal Hanauta window switcher for i3.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QIcon, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


ROOT = Path(__file__).resolve().parents[4]
APP_DIR = Path(__file__).resolve().parents[2]
FONTS_DIR = ROOT / "assets" / "fonts"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.button_helpers import create_close_button

IGNORED_CLASSES = {
    "CyberBar",
    "CyberDock",
    "HanautaHotkeys",
    "HanautaWindowSwitcher",
}
IGNORED_TITLE_PREFIXES = (
    "Hanauta Notification ",
)
MATERIAL_ICONS = {
    "apps": "\ue5c3",
    "close": "\ue5cd",
    "tab": "\ue8d6",
}


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
        break

    for screen in QGuiApplication.screens():
        if primary_name and screen.name() == primary_name:
            return screen

    for line in output.splitlines():
        if " connected primary " not in line:
            continue
        import re

        match = re.search(r"\d+x\d+\+(-?\d+)\+(-?\d+)", line)
        if match:
            primary_pos = (int(match.group(1)), int(match.group(2)))
        break

    for screen in QGuiApplication.screens():
        geometry = screen.geometry()
        if primary_pos and geometry.x() == primary_pos[0] and geometry.y() == primary_pos[1]:
            return screen

    return QApplication.primaryScreen()


def run_i3_msg(*args: str) -> str:
    result = subprocess.run(
        ["i3-msg", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def load_tree() -> dict[str, Any]:
    raw = run_i3_msg("-t", "get_tree")
    return json.loads(raw) if raw else {}


def iter_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    return list(node.get("nodes", [])) + list(node.get("floating_nodes", []))


def find_focused_workspace(node: dict[str, Any], workspace: dict[str, Any] | None = None) -> dict[str, Any] | None:
    current = workspace
    if node.get("type") == "workspace":
        current = node
    if node.get("focused") and current is not None:
        return current
    for child in iter_children(node):
        found = find_focused_workspace(child, current)
        if found is not None:
            return found
    return None


def leaf_order(node: dict[str, Any]) -> list[dict[str, Any]]:
    children = iter_children(node)
    if not children:
        if node.get("window") is not None:
            return [node]
        return []

    by_id = {int(child.get("id", 0)): child for child in children}
    ordered: list[dict[str, Any]] = []
    seen: set[int] = set()
    for child_id in node.get("focus", []):
        child = by_id.get(int(child_id))
        if child is None:
            continue
        ordered.append(child)
        seen.add(int(child_id))
    for child in children:
        child_id = int(child.get("id", 0))
        if child_id not in seen:
            ordered.append(child)
    leaves: list[dict[str, Any]] = []
    for child in ordered:
        leaves.extend(leaf_order(child))
    return leaves


def should_ignore(node: dict[str, Any]) -> bool:
    props = node.get("window_properties") or {}
    wm_class = str(props.get("class", "") or "")
    title = str(node.get("name", "") or "")
    if wm_class in IGNORED_CLASSES:
        return True
    return any(title.startswith(prefix) for prefix in IGNORED_TITLE_PREFIXES)


@dataclass(frozen=True)
class WindowItem:
    con_id: int
    title: str
    wm_class: str
    focused: bool
    app_id: str
    workspace: str


def all_windows() -> list[WindowItem]:
    tree = load_tree()
    if not tree:
        return []
    items: list[WindowItem] = []

    def walk(node: dict[str, Any], workspace_name: str = "") -> None:
        current_workspace = workspace_name
        if node.get("type") == "workspace":
            current_workspace = str(node.get("name", "") or "")
        children = iter_children(node)
        if not children:
            if node.get("window") is None or should_ignore(node):
                return
            props = node.get("window_properties") or {}
            wm_class = str(props.get("class", "") or "")
            title = str(node.get("name", "") or wm_class or "Window")
            items.append(
                WindowItem(
                    con_id=int(node.get("id", 0)),
                    title=title,
                    wm_class=wm_class,
                    focused=bool(node.get("focused")),
                    app_id=str(props.get("instance", "") or wm_class),
                    workspace=current_workspace or "Workspace",
                )
            )
            return
        for child in leaf_order(node):
            walk(child, current_workspace)

    walk(tree)
    return items


def focus_window(con_id: int) -> None:
    subprocess.run(["i3-msg", f"[con_id={con_id}] focus"], check=False)


class WindowChip(QPushButton):
    def __init__(self, item: WindowItem, ui_font: str, material_font: str, theme) -> None:
        super().__init__()
        self.item = item
        self.ui_font = ui_font
        self.material_font = material_font
        self.theme = theme
        self.setObjectName("windowChip")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCheckable(True)
        self.setFixedSize(220, 132)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)

        self.icon_label = QLabel(material_icon("apps"))
        self.icon_label.setObjectName("chipIcon")
        self.icon_label.setFont(QFont(self.material_font, 18))

        labels = QVBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.setSpacing(3)

        self.class_label = QLabel(item.wm_class or "Application")
        self.class_label.setObjectName("chipClass")
        self.class_label.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))

        self.title_label = QLabel(item.title)
        self.title_label.setObjectName("chipTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))

        self.workspace_label = QLabel(item.workspace)
        self.workspace_label.setObjectName("chipWorkspace")
        self.workspace_label.setFont(QFont(self.ui_font, 9))

        labels.addWidget(self.class_label)
        labels.addWidget(self.title_label)
        labels.addWidget(self.workspace_label)

        top.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(labels, 1)
        root.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)

        self.hint_label = QLabel("Enter to focus")
        self.hint_label.setObjectName("chipHint")
        self.hint_label.setFont(QFont(self.ui_font, 9))
        bottom.addWidget(self.hint_label)
        bottom.addStretch(1)

        keycap = QLabel("Tab")
        keycap.setObjectName("chipKeycap")
        keycap.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        bottom.addWidget(keycap)

        root.addStretch(1)
        root.addLayout(bottom)
        self.apply_state(False)

    def update_theme(self, theme) -> None:
        self.theme = theme
        self.apply_state(self.isChecked())

    def apply_state(self, active: bool) -> None:
        self.setChecked(active)
        theme = self.theme
        if active:
            bg = theme.primary_container
            border = rgba(theme.primary, 0.72)
            title = theme.on_primary_container
            meta = rgba(theme.on_primary_container, 0.82)
            icon = theme.on_primary_container
            keycap_bg = rgba(theme.on_primary_container, 0.10)
            keycap_border = rgba(theme.on_primary_container, 0.22)
        else:
            bg = theme.chip_bg
            border = theme.chip_border
            title = theme.text
            meta = theme.text_muted
            icon = theme.primary
            keycap_bg = theme.app_running_bg
            keycap_border = theme.app_running_border
        self.setStyleSheet(
            f"""
            QPushButton#windowChip {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 24px;
                text-align: left;
            }}
            QPushButton#windowChip:hover {{
                background: {theme.hover_bg};
                border: 1px solid {theme.app_focused_border};
            }}
            QLabel#chipIcon {{
                color: {icon};
                font-family: "{self.material_font}";
            }}
            QLabel#chipClass {{
                color: {meta};
                letter-spacing: 1px;
            }}
            QLabel#chipTitle {{
                color: {title};
            }}
            QLabel#chipWorkspace {{
                color: {meta};
            }}
            QLabel#chipHint {{
                color: {meta};
            }}
            QLabel#chipKeycap {{
                background: {keycap_bg};
                border: 1px solid {keycap_border};
                border-radius: 10px;
                color: {title};
                padding: 4px 10px;
            }}
            """
        )


class WindowSwitcher(QWidget):
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
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.items = all_windows()
        self.index = 0
        self._fade: QPropertyAnimation | None = None

        self._setup_window()
        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._animate_in()
        self._init_selection()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _setup_window(self) -> None:
        self.setWindowTitle("Hanauta Window Switcher")
        self.setObjectName("windowSwitcher")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        screen = primary_screen()
        if screen is not None:
            rect = screen.availableGeometry()
            width = min(1080, rect.width() - 96)
            self.setGeometry(
                rect.x() + (rect.width() - width) // 2,
                rect.y() + max(56, rect.height() // 4),
                width,
                348,
            )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scrim = QFrame()
        self.scrim.setObjectName("scrim")
        root.addWidget(self.scrim)

        shell = QVBoxLayout(self.scrim)
        shell.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame()
        self.card.setObjectName("shell")
        shell.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(3)

        eyebrow = QLabel("WINDOW SWITCHER")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        title = QLabel("Open Windows")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 24, QFont.Weight.Bold))
        subtitle = QLabel("Horizontal window strip across all workspaces. Tab moves quickly, Enter focuses, Esc closes.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont(self.ui_font, 10))

        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)

        close_button = create_close_button(
            material_icon("close"),
            self.material_font,
            font_size=20,
            object_name="closeButton",
        )
        close_button.clicked.connect(self.close)
        header.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        summary = QLabel(f"{len(self.items)} window(s) across all workspaces")
        summary.setObjectName("summary")
        summary.setFont(QFont(self.ui_font, 10, QFont.Weight.Medium))
        layout.addWidget(summary)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(164)

        self.content = QWidget()
        self.row = QHBoxLayout(self.content)
        self.row.setContentsMargins(4, 4, 4, 4)
        self.row.setSpacing(14)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll, 1)

        self.chips: list[WindowChip] = []
        if not self.items:
            empty = QLabel("There are no switchable windows available.")
            empty.setObjectName("empty")
            empty.setWordWrap(True)
            empty.setFont(QFont(self.ui_font, 11, QFont.Weight.Medium))
            self.row.addWidget(empty)
        else:
            for item in self.items:
                chip = WindowChip(item, self.ui_font, self.material_font, self.theme)
                chip.clicked.connect(lambda checked=False, con_id=item.con_id: self._activate_by_id(con_id))
                self.row.addWidget(chip)
                self.chips.append(chip)
            self.row.addStretch(1)

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
                background: transparent;
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
            QLabel#subtitle, QLabel#summary, QLabel#empty {{
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
            QScrollArea#scroll {{
                background: transparent;
                border: none;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                margin: 2px 12px 0 12px;
            }}
            QScrollBar::handle:horizontal {{
                background: {rgba(theme.outline, 0.30)};
                border-radius: 4px;
            }}
            """
        )

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(44)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 185))
        self.card.setGraphicsEffect(shadow)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(160)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _init_selection(self) -> None:
        if not self.items:
            return
        focused_index = next((i for i, item in enumerate(self.items) if item.focused), 0)
        self.index = (focused_index + 1) % len(self.items) if len(self.items) > 1 else focused_index
        self._update_selection()

    def _update_selection(self) -> None:
        for index, chip in enumerate(self.chips):
            chip.apply_state(index == self.index)
        if 0 <= self.index < len(self.chips):
            self.scroll.ensureWidgetVisible(self.chips[self.index], 40, 0)

    def _move(self, delta: int) -> None:
        if not self.chips:
            return
        self.index = (self.index + delta) % len(self.chips)
        self._update_selection()

    def _activate_current(self) -> None:
        if not (0 <= self.index < len(self.items)):
            self.close()
            return
        focus_window(self.items[self.index].con_id)
        self.close()

    def _activate_by_id(self, con_id: int) -> None:
        focus_window(con_id)
        self.close()

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()
        for chip in self.chips:
            chip.update_theme(self.theme)
        self._update_selection()

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        QTimer.singleShot(0, self.close)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        key = event.key()
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Right):
            self._move(1)
            event.accept()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Backtab):
            self._move(-1)
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._activate_current()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)
    window = WindowSwitcher()
    window.show()
    window.activateWindow()
    window.raise_()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
