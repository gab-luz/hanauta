#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Native PyQt6 application launcher.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


ROOT = Path(__file__).resolve().parents[4]
FONTS_DIR = ROOT / "assets" / "fonts"

MATERIAL_ICONS = {
    "apps": "\ue5c3",
    "brush": "\ue3ae",
    "code": "\ue86f",
    "folder": "\ue2c7",
    "gamepad": "\ue30f",
    "movie": "\ue02c",
    "public": "\ue80b",
    "search": "\ue8b6",
    "settings": "\ue8b8",
    "terminal": "\ue31e",
}

CATEGORY_ITEMS = [
    ("all", "All Apps", "apps"),
    ("internet", "Internet", "public"),
    ("system", "System", "settings"),
    ("development", "Development", "code"),
    ("graphics", "Graphics", "brush"),
    ("games", "Games", "gamepad"),
    ("multimedia", "Multimedia", "movie"),
]

CATEGORY_MAP = {
    "all": set(),
    "internet": {"Network", "WebBrowser", "Email", "InstantMessaging", "Chat"},
    "system": {"System", "Settings", "Utility", "FileManager", "TerminalEmulator"},
    "development": {"Development", "IDE", "TextEditor", "Programming"},
    "graphics": {"Graphics", "Photography", "2DGraphics", "RasterGraphics", "VectorGraphics"},
    "games": {"Game"},
    "multimedia": {"AudioVideo", "Player", "Recorder", "Audio", "Video", "Music"},
}

DESKTOP_DIRS = [
    Path.home() / ".local/share/applications",
    Path("/var/lib/flatpak/exports/share/applications"),
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
]


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


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


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


@dataclass
class DesktopApp:
    name: str
    comment: str
    exec_line: str
    icon_name: str
    categories: set[str]
    desktop_id: str
    file_path: Path


def parse_desktop_file(path: Path) -> DesktopApp | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    in_entry = False
    data: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
            continue
        if not in_entry or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key not in data:
            data[key] = value.strip()

    if data.get("Type") != "Application":
        return None
    if data.get("NoDisplay", "").lower() == "true" or data.get("Hidden", "").lower() == "true":
        return None

    name = data.get("Name", "").strip()
    exec_line = data.get("Exec", "").strip()
    if not name or not exec_line:
        return None

    categories = {item for item in data.get("Categories", "").split(";") if item}
    comment = data.get("Comment", "").strip()
    icon_name = data.get("Icon", "").strip()
    return DesktopApp(
        name=name,
        comment=comment,
        exec_line=exec_line,
        icon_name=icon_name,
        categories=categories,
        desktop_id=path.name,
        file_path=path,
    )


def scan_desktop_apps() -> list[DesktopApp]:
    apps: list[DesktopApp] = []
    seen: set[str] = set()
    for base_dir in DESKTOP_DIRS:
        if not base_dir.exists():
            continue
        for path in sorted(base_dir.rglob("*.desktop")):
            app = parse_desktop_file(path)
            if app is None:
                continue
            dedupe_key = app.desktop_id.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            apps.append(app)
    apps.sort(key=lambda item: item.name.lower())
    return apps


def launch_desktop_app(app: DesktopApp) -> bool:
    try:
        result = subprocess.Popen(
            ["gio", "launch", str(app.file_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.poll() is None or result.returncode == 0
    except Exception:
        try:
            cleaned = re.sub(r"%[fFuUdDnNickvm]", "", app.exec_line).strip()
            cmd = shlex.split(cleaned)
            if not cmd:
                return False
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False


class SearchLineEdit(QLineEdit):
    move_selection = pyqtSignal(int)
    launch_selected = pyqtSignal()
    close_requested = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Down:
            self.move_selection.emit(1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Up:
            self.move_selection.emit(-1)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.launch_selected.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class CategoryButton(QPushButton):
    def __init__(self, label: str, icon_text: str, material_font: str) -> None:
        super().__init__()
        self._label_text = label
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCheckable(True)
        self.setMinimumHeight(46)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        self.icon_label = QLabel(icon_text)
        self.icon_label.setFont(QFont(material_font, 18))
        self.icon_label.setObjectName("categoryIcon")
        self.text_label = QLabel(label)
        self.text_label.setObjectName("categoryText")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)
        self.apply_state(False)

    def apply_state(self, active: bool) -> None:
        self.setChecked(active)
        if active:
            self.icon_label.setStyleSheet("color: #381e72;")
            self.text_label.setStyleSheet("color: #381e72; font-weight: 700;")
        else:
            self.icon_label.setStyleSheet("color: rgba(255,255,255,0.82);")
            self.text_label.setStyleSheet("color: rgba(255,255,255,0.96); font-weight: 600;")


class AppCard(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, app: DesktopApp, material_font: str, ui_font: str) -> None:
        super().__init__()
        self.app = app
        self.material_font = material_font
        self.setObjectName("appCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(68)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        self.icon_wrap = QLabel()
        self.icon_wrap.setFixedSize(42, 42)
        self.icon_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_wrap.setObjectName("appCardIconWrap")
        icon = QIcon.fromTheme(app.icon_name)
        if not icon.isNull():
            self.icon_wrap.setPixmap(icon.pixmap(28, 28))
        else:
            self.icon_wrap.setText(material_icon("apps"))
            self.icon_wrap.setFont(QFont(material_font, 20))

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)
        self.title_label = QLabel(app.name)
        self.title_label.setFont(QFont(ui_font, 11, QFont.Weight.DemiBold))
        self.subtitle_label = QLabel(app.comment or app.desktop_id)
        self.subtitle_label.setWordWrap(False)
        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.subtitle_label)

        self.hint_label = QLabel("Enter")
        self.hint_label.setFont(QFont(ui_font, 10, QFont.Weight.Bold))

        layout.addWidget(self.icon_wrap)
        layout.addLayout(text_wrap, 1)
        layout.addWidget(self.hint_label)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        if selected:
            bg = "#d0bcff"
            border = "rgba(229,214,255,0.95)"
            title_color = "#251431"
            subtitle_color = "rgba(37,20,49,0.82)"
            hint_color = "#381e72"
            icon_bg = "rgba(56,30,114,0.10)"
            icon_color = "#381e72"
        else:
            bg = "rgba(255,255,255,0.02)"
            border = "rgba(255,255,255,0.04)"
            title_color = "#ffffff"
            subtitle_color = "rgba(246,239,255,0.52)"
            hint_color = "rgba(208,188,255,0.76)"
            icon_bg = "rgba(255,255,255,0.05)"
            icon_color = "#d0bcff"
        self.setStyleSheet(
            f"""
            QFrame#appCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QFrame#appCard:hover {{
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.08);
            }}
            QLabel#appCardIconWrap {{
                background: {icon_bg};
                border-radius: 13px;
            }}
            """
        )
        self.title_label.setStyleSheet(f"color: {title_color};")
        self.subtitle_label.setStyleSheet(f"color: {subtitle_color}; font-size: 10px;")
        self.hint_label.setStyleSheet(f"color: {hint_color}; font-size: 10px; font-weight: 700;")
        if self.icon_wrap.pixmap() is None:
            self.icon_wrap.setStyleSheet(f"color: {icon_color};")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.app)
            event.accept()
            return
        super().mousePressEvent(event)


class LauncherWindow(QWidget):
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
        self.ui_font = detect_font("Noto Sans", "DejaVu Sans", "Sans Serif")
        self.mono_font = detect_font("JetBrains Mono", "DejaVu Sans Mono", "Monospace")
        self.apps = scan_desktop_apps()
        self.filtered_apps: list[DesktopApp] = []
        self.category = "all"
        self.selected_index = 0
        self._panel_animation: QPropertyAnimation | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.resize(860, 600)
        self.setWindowTitle("Hanauta Launcher")

        self._build_ui()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self._apply_filter()
        QTimer.singleShot(40, self.search_input.setFocus)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        self.panel.setStyleSheet(
            """
            QFrame#panel {
                background: rgba(28, 27, 31, 0.97);
                border: 1px solid rgba(147,143,153,0.15);
                border-radius: 28px;
            }
            QWidget {
                color: #f5f2f7;
            }
            """
        )
        root.addWidget(self.panel)

        shell = QHBoxLayout(self.panel)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(208)
        sidebar.setStyleSheet(
            """
            QFrame#sidebar {
                background: rgba(43,41,48,0.44);
                border-right: 1px solid rgba(255,255,255,0.05);
                border-top-left-radius: 28px;
                border-bottom-left-radius: 28px;
            }
            """
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 18, 16, 18)
        sidebar_layout.setSpacing(8)

        brand = QHBoxLayout()
        brand_icon = QLabel(material_icon("apps"))
        brand_icon.setFont(QFont(self.material_font, 20))
        brand_icon.setStyleSheet("color: #d0bcff;")
        brand_label = QLabel("Hanauta Launcher")
        brand_label.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        brand_label.setStyleSheet("color: #d0bcff;")
        brand.addWidget(brand_icon)
        brand.addWidget(brand_label)
        brand.addStretch(1)
        sidebar_layout.addLayout(brand)
        sidebar_layout.addSpacing(10)

        self.category_buttons: dict[str, CategoryButton] = {}
        for key, label, icon_name in CATEGORY_ITEMS:
            button = CategoryButton(label, material_icon(icon_name), self.material_font)
            button.clicked.connect(lambda checked=False, value=key: self._set_category(value))
            button.setStyleSheet(
                """
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 18px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.05);
                }
                QPushButton:checked {
                    background: #d0bcff;
                }
                """
            )
            sidebar_layout.addWidget(button)
            self.category_buttons[key] = button
        sidebar_layout.addStretch(1)

        footer = QLabel("ESC to close")
        footer.setFont(QFont(self.mono_font, 10))
        footer.setStyleSheet("color: rgba(255,255,255,0.42);")
        sidebar_layout.addWidget(footer)

        shell.addWidget(sidebar)

        main = QFrame()
        main.setObjectName("main")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(24, 20, 18, 14)
        main_layout.setSpacing(12)

        search_wrap = QFrame()
        search_wrap.setObjectName("searchWrap")
        search_wrap.setStyleSheet(
            """
            QFrame#searchWrap {
                background: rgba(43,41,48,0.86);
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,0.05);
            }
            """
        )
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(14, 10, 14, 10)
        search_layout.setSpacing(10)
        search_icon = QLabel(material_icon("search"))
        search_icon.setFont(QFont(self.material_font, 20))
        search_icon.setStyleSheet("color: #d0bcff;")
        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("Type to search applications…")
        self.search_input.setFont(QFont(self.ui_font, 12))
        self.search_input.setStyleSheet(
            """
            QLineEdit {
                background: transparent;
                border: none;
                color: #ffffff;
                selection-background-color: #d0bcff;
                selection-color: #251431;
            }
            """
        )
        self.search_input.textChanged.connect(self._apply_filter)
        self.search_input.move_selection.connect(self._move_selection)
        self.search_input.launch_selected.connect(self._launch_selected)
        self.search_input.close_requested.connect(self.close)
        search_layout.addWidget(search_icon)
        search_layout.addWidget(self.search_input, 1)
        main_layout.addWidget(search_wrap)

        self.results_count = QLabel("")
        self.results_count.setFont(QFont(self.mono_font, 10))
        self.results_count.setStyleSheet("color: rgba(255,255,255,0.46);")
        main_layout.addWidget(self.results_count)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                background: rgba(19,17,28,0.88);
                border: none;
                border-radius: 22px;
            }
            QScrollArea > QWidget > QWidget {
                background: rgba(19,17,28,0.88);
                border-radius: 22px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: rgba(147,143,153,0.30);
                border-radius: 4px;
            }
            """
        )
        self.results_host = QWidget()
        self.results_host.setObjectName("resultsHost")
        self.results_host.setStyleSheet(
            """
            QWidget#resultsHost {
                background: rgba(19,17,28,0.88);
                border-radius: 22px;
            }
            """
        )
        self.results_layout = QVBoxLayout(self.results_host)
        self.results_layout.setContentsMargins(0, 0, 6, 0)
        self.results_layout.setSpacing(8)
        self.results_layout.addStretch(1)
        self.scroll_area.setWidget(self.results_host)
        main_layout.addWidget(self.scroll_area, 1)

        self.footer_label = QLabel("")
        self.footer_label.setFont(QFont(self.mono_font, 10))
        self.footer_label.setStyleSheet("color: rgba(255,255,255,0.42);")
        main_layout.addWidget(self.footer_label)

        shell.addWidget(main, 1)

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 24)
        shadow.setColor(QColor(0, 0, 0, 190))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.center().x() - self.width() // 2, rect.center().y() - self.height() // 2)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._panel_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._panel_animation.setDuration(160)
        self._panel_animation.setStartValue(0.0)
        self._panel_animation.setEndValue(1.0)
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.start()

    def _set_category(self, category: str) -> None:
        self.category = category
        self._apply_filter()

    def _match_category(self, app: DesktopApp) -> bool:
        if self.category == "all":
            return True
        return bool(CATEGORY_MAP[self.category].intersection(app.categories))

    def _apply_filter(self) -> None:
        query = self.search_input.text().strip().lower()
        self.filtered_apps = []
        for app in self.apps:
            if not self._match_category(app):
                continue
            haystack = f"{app.name} {app.comment} {' '.join(sorted(app.categories))} {app.desktop_id}".lower()
            if query and query not in haystack:
                continue
            self.filtered_apps.append(app)
        self.selected_index = 0 if self.filtered_apps else -1
        self._render_results()
        for key, button in self.category_buttons.items():
            button.apply_state(key == self.category)

    def _render_results(self) -> None:
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.filtered_apps:
            empty = QLabel("No applications match this search.")
            empty.setStyleSheet("color: rgba(255,255,255,0.56); padding: 10px 2px;")
            self.results_layout.insertWidget(0, empty)
            self.results_count.setText("0 applications")
            self.footer_label.setText("Enter launches the selected app")
            return

        for index, app in enumerate(self.filtered_apps):
            card = AppCard(app, self.material_font, self.ui_font)
            card.set_selected(index == self.selected_index)
            card.clicked.connect(self._launch_app)
            self.results_layout.insertWidget(self.results_layout.count() - 1, card)

        self.results_count.setText(f"{len(self.filtered_apps)} applications")
        self.footer_label.setText("Enter launches the selected app • Up/Down changes selection")
        self._scroll_selection_into_view()

    def _move_selection(self, delta: int) -> None:
        if not self.filtered_apps:
            return
        self.selected_index = (self.selected_index + delta) % len(self.filtered_apps)
        self._render_results()

    def _launch_selected(self) -> None:
        if 0 <= self.selected_index < len(self.filtered_apps):
            self._launch_app(self.filtered_apps[self.selected_index])

    def _launch_app(self, app: DesktopApp) -> None:
        if launch_desktop_app(app):
            self.close()

    def _scroll_selection_into_view(self) -> None:
        if self.selected_index < 0:
            return
        item = self.results_layout.itemAt(self.selected_index)
        if item is None:
            return
        widget = item.widget()
        if widget is None:
            return
        self.scroll_area.ensureWidgetVisible(widget, 0, 32)

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        QTimer.singleShot(0, self.close)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
