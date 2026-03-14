#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import signal
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QCursor, QDesktopServices, QFont, QFontDatabase, QGuiApplication
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


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.rss import collect_entries, load_settings_state
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from PyQt6.QtCore import QUrl


MATERIAL_ICONS = {
    "settings": "\ue8b8",
    "refresh": "\ue5d5",
    "public": "\ue80b",
    "open_in_new": "\ue89e",
}


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
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


def python_bin() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


class ArticleCard(QFrame):
    def __init__(self, item: dict[str, str], ui_font: str, display_font: str) -> None:
        super().__init__()
        self.item = item
        self.setObjectName("articleCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel(item.get("title", "Untitled"))
        title.setObjectName("cardTitle")
        title.setFont(QFont(display_font, 12, QFont.Weight.DemiBold))
        title.setWordWrap(True)
        layout.addWidget(title)

        detail = QLabel(item.get("detail", ""))
        detail.setObjectName("cardDetail")
        detail.setFont(QFont(ui_font, 9))
        detail.setWordWrap(True)
        layout.addWidget(detail)

        open_button = QPushButton(f"{material_icon('open_in_new')}  Open story")
        open_button.setObjectName("secondaryButton")
        open_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_button.setFont(QFont(ui_font, 9, QFont.Weight.DemiBold))
        open_button.clicked.connect(self._open_link)
        layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignLeft)

    def _open_link(self) -> None:
        link = str(self.item.get("link", "")).strip()
        if link:
            QDesktopServices.openUrl(QUrl(link))


class RssWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.settings_state = load_settings_state()
        self._fade: QPropertyAnimation | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("Hanauta RSS")
        self.setFixedSize(492, 632)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self.refresh_feeds()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(3)
        eyebrow = QLabel("RSS WIDGET")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        title = QLabel("Read and return")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 22, QFont.Weight.DemiBold))
        self.subtitle = QLabel("Headlines from manual feeds or OPML-backed self-hosted exports.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setFont(QFont(self.ui_font, 9))
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_feeds)
        self.settings_button = self._icon_button("settings")
        self.settings_button.clicked.connect(self._open_settings)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.settings_button)
        header.addLayout(actions)
        layout.addLayout(header)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(6)
        self.hero_title = QLabel("No source loaded yet")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 16, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("Save some RSS URLs or an OPML source in Settings, then refresh this widget.")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setFont(QFont(self.ui_font, 9))
        self.hero_detail.setWordWrap(True)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_detail)
        layout.addWidget(self.hero)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll, 1)

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(38, 38)
        button.setFont(QFont(self.icon_font, 18))
        return button

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 132))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(available.x() + available.width() - self.width() - 52, available.y() + 78)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#panel {{
                background: {rgba(theme.surface_container, 0.94)};
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 28px;
            }}
            QLabel#eyebrow {{
                color: {theme.primary};
                letter-spacing: 1.3px;
            }}
            QLabel#title, QLabel#heroTitle, QLabel#cardTitle {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#heroDetail, QLabel#cardDetail, QLabel#statusLabel {{
                color: {theme.text_muted};
            }}
            QFrame#heroCard, QFrame#articleCard {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 22px;
            }}
            QFrame#heroCard {{
                background: {rgba(theme.surface_container_high, 0.90)};
            }}
            QPushButton#iconButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.primary};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                font-family: "{self.icon_font}";
            }}
            QPushButton#secondaryButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                padding: 8px 12px;
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

    def _clear_articles(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh_feeds(self) -> None:
        self.settings_state = load_settings_state()
        self._clear_articles()
        sources, collected = collect_entries(self.settings_state)
        if not sources:
            self.hero_title.setText("No feed sources configured")
            self.hero_detail.setText("Use manual RSS URLs or an OPML export in Settings, then refresh.")
            self.status_label.setText("RSS is idle.")
            return
        if not collected:
            self.hero_title.setText("Feeds could not be loaded")
            self.hero_detail.setText("Check your feed URLs, OPML source, or self-hosted credentials.")
            self.status_label.setText(f"Tried {len(sources)} source(s) but found no readable stories.")
            return
        self.hero_title.setText(collected[0].get("title", "Latest headline"))
        self.hero_detail.setText(collected[0].get("detail", "") or collected[0].get("link", ""))
        for item in collected:
            self.list_layout.insertWidget(self.list_layout.count() - 1, ArticleCard(item, self.ui_font, self.display_font))
        self.status_label.setText(f"Loaded {len(collected)} story entries from {len(sources)} source(s).")

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        try:
            subprocess.Popen(
                [
                    python_bin(),
                    str(SETTINGS_PAGE_SCRIPT),
                    "--page",
                    "services",
                    "--service-section",
                    "rss_widget",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    widget = RssWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
