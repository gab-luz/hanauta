#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, QUrl
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.rss import collect_entries, load_settings_state
from pyqt.shared.runtime import entry_command
from pyqt.shared.theme import blend, load_theme_palette, palette_mtime, rgba


MATERIAL_ICONS = {
    "close": "\ue5cd",
    "settings": "\ue8b8",
    "refresh": "\ue5d5",
    "public": "\ue80b",
    "open_in_new": "\ue89e",
    "play_arrow": "\ue037",
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


class FeedRow(QFrame):
    def __init__(
        self,
        item: dict[str, str],
        ui_font: str,
        display_font: str,
        icon_font: str,
        index: int,
    ) -> None:
        super().__init__()
        self.item = item
        self._link = str(item.get("link", "")).strip()

        self.setObjectName("feedRow")
        self.setProperty("hovered", False)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(96)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        index_badge = QLabel(f"{index + 1:02d}")
        index_badge.setObjectName("indexBadge")
        index_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        index_badge.setFont(QFont(ui_font, 8, QFont.Weight.DemiBold))
        index_badge.setFixedWidth(36)
        layout.addWidget(index_badge, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(6)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        source_chip = QLabel(str(item.get("feed_title", "Feed")).strip() or "Feed")
        source_chip.setObjectName("sourceChip")
        source_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        source_chip.setFont(QFont(ui_font, 8, QFont.Weight.DemiBold))

        video_chip = QLabel("VIDEO")
        video_chip.setObjectName("videoChip")
        video_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_chip.setFont(QFont(ui_font, 8, QFont.Weight.DemiBold))

        meta_row.addWidget(source_chip, 0)
        meta_row.addWidget(video_chip, 0)
        meta_row.addStretch(1)

        title = QLabel(str(item.get("title", "Untitled")).strip() or "Untitled")
        title.setObjectName("rowTitle")
        title.setFont(QFont(display_font, 11, QFont.Weight.DemiBold))
        title.setWordWrap(True)

        detail_text = str(item.get("detail", "")).strip()
        if not detail_text:
            detail_text = self._link

        detail = QLabel(detail_text)
        detail.setObjectName("rowDetail")
        detail.setFont(QFont(ui_font, 9))
        detail.setWordWrap(True)

        body.addLayout(meta_row)
        body.addWidget(title)
        body.addWidget(detail)

        layout.addLayout(body, 1)

        side = QVBoxLayout()
        side.setSpacing(4)

        open_icon = QLabel(material_icon("open_in_new"))
        open_icon.setObjectName("openIcon")
        open_icon.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        open_icon.setFont(QFont(icon_font, 18))

        side.addWidget(open_icon, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        side.addStretch(1)

        layout.addLayout(side, 0)

        self.setToolTip(self._link or title.text())

    def _repolish(self) -> None:
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def _activate(self) -> None:
        if self._link:
            QDesktopServices.openUrl(QUrl(self._link))

    def enterEvent(self, event) -> None:
        self.setProperty("hovered", True)
        self._repolish()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setProperty("hovered", False)
        self._repolish()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._activate()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self._activate()
            event.accept()
            return
        super().keyPressEvent(event)


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
        self.setFixedSize(412, 720)

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
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)

        titles = QVBoxLayout()
        titles.setSpacing(3)

        eyebrow = QLabel("RSS VIDEOS")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))

        title = QLabel("Latest uploads")
        title.setObjectName("panelTitle")
        title.setFont(QFont(self.display_font, 17, QFont.Weight.DemiBold))

        self.subtitle = QLabel("One video per row. Click any entry to open it.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setFont(QFont(self.ui_font, 9))
        self.subtitle.setWordWrap(True)

        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        actions.setSpacing(6)

        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_feeds)

        self.settings_button = self._icon_button("settings")
        self.settings_button.clicked.connect(self._open_settings)

        self.close_button = self._icon_button("close")
        self.close_button.clicked.connect(self.close)

        actions.addWidget(self.refresh_button)
        actions.addWidget(self.settings_button)
        actions.addWidget(self.close_button)

        header.addLayout(actions, 0)
        layout.addLayout(header)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")

        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(8)

        hero_top = QHBoxLayout()
        hero_top.setSpacing(8)

        self.hero_badge = QLabel("FEEDS")
        self.hero_badge.setObjectName("metaChip")
        self.hero_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_badge.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))

        self.hero_context = QLabel("Waiting for sources")
        self.hero_context.setObjectName("heroMeta")
        self.hero_context.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        hero_top.addWidget(self.hero_badge, 0)
        hero_top.addStretch(1)
        hero_top.addWidget(self.hero_context, 0)

        self.hero_title = QLabel("No source loaded yet")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 18, QFont.Weight.DemiBold))
        self.hero_title.setWordWrap(True)

        self.hero_detail = QLabel("Add RSS URLs or an OPML source in Settings, then refresh this widget.")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setFont(QFont(self.ui_font, 9))
        self.hero_detail.setWordWrap(True)

        hero_layout.addLayout(hero_top)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_detail)

        layout.addWidget(self.hero)

        stats = QGridLayout()
        stats.setHorizontalSpacing(10)
        stats.setVerticalSpacing(10)

        self.sources_card = self._stat_card("Sources", "0", "Configured feeds")
        self.videos_card = self._stat_card("Videos", "0", "Loaded entries")

        stats.addWidget(self.sources_card, 0, 0)
        stats.addWidget(self.videos_card, 0, 1)

        layout.addLayout(stats)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("feedScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.list_container = QWidget()
        self.list_container.setObjectName("feedListContainer")

        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll, 1)

        self.status_label = QLabel("RSS is idle.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(58)
        layout.addWidget(self.status_label)

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(36, 36)
        button.setFont(QFont(self.icon_font, 18))
        return button

    def _stat_card(self, label: str, value: str, note: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(4)

        title = QLabel(label.upper())
        title.setObjectName("eyebrow")

        value_label = QLabel(value)
        value_label.setObjectName("statValue")

        note_label = QLabel(note)
        note_label.setObjectName("statNote")
        note_label.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(value_label)
        card_layout.addWidget(note_label)

        card._value_label = value_label  # type: ignore[attr-defined]
        card._note_label = note_label  # type: ignore[attr-defined]
        return card

    def _set_stat_value(self, card: QFrame, value: str, note: str | None = None) -> None:
        value_label = getattr(card, "_value_label", None)
        note_label = getattr(card, "_note_label", None)
        if isinstance(value_label, QLabel):
            value_label.setText(value)
        if note is not None and isinstance(note_label, QLabel):
            note_label.setText(note)

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(46)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 132))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(
            available.x() + available.width() - self.width() - 48,
            available.y() + 84,
        )

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
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.surface_container_high, 0.97)},
                    stop: 0.55 {rgba(theme.surface_container, 0.94)},
                    stop: 1 {rgba(blend(theme.surface_container, theme.surface, 0.40), 0.90)}
                );
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 28px;
            }}

            QLabel#eyebrow {{
                color: {theme.primary};
                letter-spacing: 1.8px;
            }}

            QLabel#panelTitle,
            QLabel#heroTitle,
            QLabel#rowTitle,
            QLabel#statValue {{
                color: {theme.text};
            }}

            QLabel#subtitle,
            QLabel#heroMeta,
            QLabel#heroDetail,
            QLabel#rowDetail,
            QLabel#statNote {{
                color: {theme.text_muted};
            }}

            QLabel#heroTitle {{
                font-size: 18px;
                font-weight: 700;
            }}

            QLabel#statValue {{
                font-size: 16px;
                font-weight: 700;
            }}

            QFrame#heroCard {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.primary_container, 0.42)},
                    stop: 0.45 {rgba(theme.secondary, 0.14)},
                    stop: 1 {rgba(theme.surface_container_high, 0.94)}
                );
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 24px;
            }}

            QFrame#statCard {{
                background: {rgba(theme.surface_container_high, 0.84)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 20px;
            }}

            QScrollArea#feedScroll,
            QWidget#feedListContainer {{
                background: transparent;
                border: none;
            }}

            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 6px 0 6px 0;
            }}

            QScrollBar::handle:vertical {{
                background: {rgba(theme.outline, 0.30)};
                border-radius: 4px;
                min-height: 28px;
            }}

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0;
            }}

            QFrame#feedRow {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 20px;
            }}

            QFrame#feedRow[hovered="true"] {{
                background: {rgba(theme.primary, 0.10)};
                border: 1px solid {rgba(theme.primary, 0.26)};
            }}

            QLabel#indexBadge {{
                background: {rgba(theme.on_surface, 0.05)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 12px;
                color: {theme.text};
                padding: 8px 6px;
            }}

            QLabel#sourceChip,
            QLabel#videoChip,
            QLabel#metaChip {{
                background: {rgba(theme.primary, 0.12)};
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 999px;
                color: {theme.primary};
                padding: 5px 10px;
            }}

            QLabel#videoChip {{
                background: {rgba(theme.secondary, 0.12)};
                border: 1px solid {rgba(theme.secondary, 0.16)};
                color: {theme.text};
            }}

            QLabel#openIcon {{
                color: {rgba(theme.primary, 0.82)};
                font-family: "{self.icon_font}";
            }}

            QPushButton#iconButton {{
                background: {rgba(theme.surface_container_high, 0.90)};
                color: {theme.primary};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
                font-family: "{self.icon_font}";
                text-align: center;
            }}

            QPushButton#iconButton:hover {{
                background: {rgba(theme.primary, 0.10)};
                border: 1px solid {rgba(theme.primary, 0.24)};
            }}

            QLabel#statusLabel {{
                background: {rgba(theme.on_surface, 0.035)};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 18px;
                padding: 12px 14px;
                color: {theme.text};
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
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh_feeds(self) -> None:
        self.settings_state = load_settings_state()
        self._clear_articles()

        sources, collected = collect_entries(self.settings_state)

        self._set_stat_value(self.sources_card, str(len(sources)), "Configured feeds")
        self._set_stat_value(self.videos_card, str(len(collected)), "Loaded entries")

        if not sources:
            self.hero_title.setText("No feed sources configured")
            self.hero_detail.setText("Use manual RSS URLs or an OPML export in Settings, then refresh.")
            self.hero_context.setText("Waiting for sources")
            self.status_label.setText("RSS is idle.")
            return

        self.hero_context.setText(f"{len(sources)} source(s)")

        if not collected:
            self.hero_title.setText("Feeds could not be loaded")
            self.hero_detail.setText("Check feed URLs, OPML source, or credentials.")
            self.status_label.setText(f"Tried {len(sources)} source(s) but found no readable entries.")
            return

        first = collected[0]
        first_title = str(first.get("title", "Latest video")).strip() or "Latest video"
        first_source = str(first.get("feed_title", "Feed")).strip() or "Feed"
        first_detail = str(first.get("detail", "")).strip() or str(first.get("link", "")).strip()

        self.hero_title.setText(first_title)
        self.hero_detail.setText(f"{first_source} — {first_detail}" if first_detail else first_source)
        self.hero_context.setText(f"{len(collected)} video(s)")

        for index, item in enumerate(collected):
            self.list_layout.addWidget(
                FeedRow(
                    item=item,
                    ui_font=self.ui_font,
                    display_font=self.display_font,
                    icon_font=self.icon_font,
                    index=index,
                )
            )

        self.status_label.setText(
            f"Loaded {len(collected)} video entries from {len(sources)} source(s)."
        )

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        try:
            command = entry_command(
                SETTINGS_PAGE_SCRIPT,
                "--page",
                "services",
                "--service-section",
                "rss_widget",
            )
            if not command:
                return
            subprocess.Popen(
                command,
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