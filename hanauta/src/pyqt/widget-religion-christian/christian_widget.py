#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt6 Christian devotion widget rebuilt from idea.html.
"""

from __future__ import annotations

import html
import json
import signal
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba

FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
TRACKER_DIR = Path.home() / ".local" / "state" / "hanauta" / "christian-widget"
TRACKER_FILE = TRACKER_DIR / "tracker.json"

MATERIAL_ICONS = {
    "auto_awesome": "\ue65f",
    "book": "\ue865",
    "chevron_left": "\ue5cb",
    "chevron_right": "\ue5cc",
    "brightness_3": "\ue3a8",
    "calendar_today": "\ue935",
    "light_mode": "\ue518",
    "refresh": "\ue5d5",
    "schedule": "\ue8b5",
    "wb_twilight": "\ue1c6",
}

BIBLE_BOOKS: list[tuple[str, int]] = [
    ("Genesis", 50), ("Exodus", 40), ("Leviticus", 27), ("Numbers", 36), ("Deuteronomy", 34),
    ("Joshua", 24), ("Judges", 21), ("Ruth", 4), ("1 Samuel", 31), ("2 Samuel", 24),
    ("1 Kings", 22), ("2 Kings", 25), ("1 Chronicles", 29), ("2 Chronicles", 36), ("Ezra", 10),
    ("Nehemiah", 13), ("Esther", 10), ("Job", 42), ("Psalms", 150), ("Proverbs", 31),
    ("Ecclesiastes", 12), ("Song of Songs", 8), ("Isaiah", 66), ("Jeremiah", 52), ("Lamentations", 5),
    ("Ezekiel", 48), ("Daniel", 12), ("Hosea", 14), ("Joel", 3), ("Amos", 9),
    ("Obadiah", 1), ("Jonah", 4), ("Micah", 7), ("Nahum", 3), ("Habakkuk", 3),
    ("Zephaniah", 3), ("Haggai", 2), ("Zechariah", 14), ("Malachi", 4), ("Matthew", 28),
    ("Mark", 16), ("Luke", 24), ("John", 21), ("Acts", 28), ("Romans", 16),
    ("1 Corinthians", 16), ("2 Corinthians", 13), ("Galatians", 6), ("Ephesians", 6), ("Philippians", 4),
    ("Colossians", 4), ("1 Thessalonians", 5), ("2 Thessalonians", 3), ("1 Timothy", 6), ("2 Timothy", 4),
    ("Titus", 3), ("Philemon", 1), ("Hebrews", 13), ("James", 5), ("1 Peter", 5),
    ("2 Peter", 3), ("1 John", 5), ("2 John", 1), ("3 John", 1), ("Jude", 1), ("Revelation", 22),
]
TOTAL_BIBLE_CHAPTERS = sum(chapters for _, chapters in BIBLE_BOOKS)


def service_enabled() -> bool:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return True
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return True
    current = services.get("christian_widget", {})
    if not isinstance(current, dict):
        return True
    return bool(current.get("enabled", True))


@dataclass(frozen=True)
class Verse:
    text: str
    citation: str


@dataclass(frozen=True)
class DevotionSlot:
    name: str
    at: time
    icon: str


@dataclass
class TrackerState:
    book_index: int = 0
    chapter: int = 1


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


def easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def liturgical_label(today: date) -> str:
    easter = easter_sunday(today.year)
    ash_wednesday = easter - timedelta(days=46)
    palm_sunday = easter - timedelta(days=7)
    if ash_wednesday <= today < palm_sunday:
        week = ((today - ash_wednesday).days // 7) + 1
        return f"Lent Period • Week {week}"
    if palm_sunday <= today < easter:
        return "Holy Week"
    if today == easter:
        return "Easter Sunday"
    if easter < today <= easter + timedelta(days=49):
        week = ((today - easter).days // 7) + 1
        return f"Eastertide • Week {week}"
    return "Daily Devotion"


def format_countdown(delta: timedelta) -> str:
    total_seconds = max(0, int(delta.total_seconds()))
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def clamp_tracker_state(state: TrackerState) -> TrackerState:
    max_index = len(BIBLE_BOOKS) - 1
    book_index = max(0, min(max_index, int(state.book_index)))
    max_chapter = BIBLE_BOOKS[book_index][1]
    chapter = max(1, min(max_chapter, int(state.chapter)))
    return TrackerState(book_index=book_index, chapter=chapter)


def load_tracker_state() -> TrackerState:
    try:
        raw = TRACKER_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return TrackerState()
    return clamp_tracker_state(
        TrackerState(
            book_index=int(payload.get("book_index", 0)),
            chapter=int(payload.get("chapter", 1)),
        )
    )


def save_tracker_state(state: TrackerState) -> None:
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    TRACKER_FILE.write_text(
        json.dumps({"book_index": state.book_index, "chapter": state.chapter}, indent=2),
        encoding="utf-8",
    )


class TrackerProgressBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("trackerProgress")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.fill = QFrame()
        self.fill.setObjectName("trackerProgressFill")
        self.fill.setMinimumWidth(12)
        layout.addWidget(self.fill, 0, Qt.AlignmentFlag.AlignLeft)
        self._ratio = 0.0

    def apply_theme(self, track_color: str, fill_color: str) -> None:
        self.setStyleSheet(
            f"""
            QFrame#trackerProgress {{
                background: {track_color};
                border-radius: 7px;
            }}
            QFrame#trackerProgressFill {{
                background: {fill_color};
                border-radius: 7px;
            }}
            """
        )

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.set_ratio(self._ratio)

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        width = max(12, int(self.width() * self._ratio))
        self.fill.setFixedWidth(width)
        self.fill.setFixedHeight(self.height())


class DevotionRow(QFrame):
    def __init__(self, slot: DevotionSlot, material_font: str, ui_font: str, accent: str) -> None:
        super().__init__()
        self.slot = slot
        self.material_font = material_font
        self.ui_font = ui_font
        self.accent = accent
        self.setObjectName("devotionRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lead = QHBoxLayout()
        lead.setContentsMargins(0, 0, 0, 0)
        lead.setSpacing(10)

        self.icon_label = QLabel(material_icon(slot.icon))
        self.icon_label.setObjectName("rowIcon")
        self.icon_label.setFont(QFont(self.material_font, 15))

        self.name_label = QLabel(slot.name)
        self.name_label.setObjectName("rowName")
        self.name_label.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))

        lead.addWidget(self.icon_label)
        lead.addWidget(self.name_label)

        self.time_label = QLabel(slot.at.strftime("%H:%M"))
        self.time_label.setObjectName("rowTime")
        self.time_label.setFont(QFont("Monospace", 9))

        layout.addLayout(lead, 1)
        layout.addWidget(self.time_label, 0, Qt.AlignmentFlag.AlignRight)
        self.set_active(False)

    def set_accent(self, accent: str) -> None:
        self.accent = accent

    def set_active(self, active: bool) -> None:
        bg = rgba(self.accent, 0.14) if active else "transparent"
        border = rgba(self.accent, 0.30) if active else "transparent"
        name_color = self.accent if active else "rgba(255,255,255,0.90)"
        time_color = self.accent if active else "rgba(255,255,255,0.60)"
        self.setStyleSheet(
            f"""
            QFrame#devotionRow {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QFrame#devotionRow:hover {{
                background: {rgba(self.accent, 0.08)};
            }}
            QLabel#rowIcon {{
                color: {self.accent};
                font-family: "{self.material_font}";
            }}
            QLabel#rowName {{
                color: {name_color};
            }}
            QLabel#rowTime {{
                color: {time_color};
            }}
            """
        )


class ChristianDevotionWidget(QWidget):
    VERSES = [
        Verse("Be still, and know that I am God.", "Psalm 46:10"),
        Verse("The Lord is my shepherd; I shall not want.", "Psalm 23:1"),
        Verse("Let all that you do be done in love.", "1 Corinthians 16:14"),
        Verse("Rejoice in hope, be patient in tribulation, be constant in prayer.", "Romans 12:12"),
        Verse("My grace is sufficient for you, for my power is made perfect in weakness.", "2 Corinthians 12:9"),
    ]

    SLOTS = [
        DevotionSlot("Morning Prayer", time(6, 30), "wb_twilight"),
        DevotionSlot("Noon Grace", time(12, 15), "light_mode"),
        DevotionSlot("Evening Vesper", time(18, 45), "wb_twilight"),
        DevotionSlot("Night Prayer", time(21, 30), "brightness_3"),
        DevotionSlot("Compline", time(23, 0), "schedule"),
    ]

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
        self.serif_font = detect_font("Playfair Display", "Noto Serif", "DejaVu Serif", "Serif")
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.verse_offset = 0
        self.rows: list[DevotionRow] = []
        self.tracker_state = load_tracker_state()
        self._fade_animation: QPropertyAnimation | None = None

        self._setup_window()
        self._build_ui()
        self._apply_styles()
        self._apply_window_effects()
        self._place_window()
        self.refresh_content()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_content)
        self.timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _setup_window(self) -> None:
        self.setWindowTitle("Christian Devotion")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(404, 758)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        self.card = QFrame()
        self.card.setObjectName("card")
        root.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)

        self.date_label = QLabel()
        self.date_label.setObjectName("dateLabel")
        self.date_label.setFont(QFont(self.ui_font, 17, QFont.Weight.DemiBold))

        self.period_label = QLabel()
        self.period_label.setObjectName("periodLabel")
        self.period_label.setFont(QFont(self.ui_font, 10, QFont.Weight.Medium))

        title_wrap.addWidget(self.date_label)
        title_wrap.addWidget(self.period_label)
        header.addLayout(title_wrap, 1)

        self.refresh_button = QPushButton(material_icon("refresh"))
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_button.setFont(QFont(self.material_font, 18))
        self.refresh_button.clicked.connect(self.rotate_verse)
        header.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.verse_card = QFrame()
        self.verse_card.setObjectName("verseCard")
        verse_layout = QVBoxLayout(self.verse_card)
        verse_layout.setContentsMargins(18, 18, 18, 18)
        verse_layout.setSpacing(10)

        verse_heading = QLabel("Daily Verse")
        verse_heading.setObjectName("verseHeading")
        verse_heading.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        verse_layout.addWidget(verse_heading, 0, Qt.AlignmentFlag.AlignHCenter)

        self.verse_label = QLabel()
        self.verse_label.setObjectName("verseLabel")
        self.verse_label.setWordWrap(True)
        self.verse_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.verse_label.setTextFormat(Qt.TextFormat.RichText)
        self.verse_label.setFont(QFont(self.serif_font, 15))
        verse_layout.addWidget(self.verse_label)

        self.citation_label = QLabel()
        self.citation_label.setObjectName("citationLabel")
        self.citation_label.setFont(QFont(self.ui_font, 9, QFont.Weight.Medium))
        verse_layout.addWidget(self.citation_label, 0, Qt.AlignmentFlag.AlignHCenter)

        countdown_wrap = QFrame()
        countdown_wrap.setObjectName("countdownWrap")
        countdown_layout = QVBoxLayout(countdown_wrap)
        countdown_layout.setContentsMargins(0, 12, 0, 0)
        countdown_layout.setSpacing(2)

        self.countdown_hint = QLabel("Next Devotion In")
        self.countdown_hint.setObjectName("countdownHint")
        self.countdown_hint.setFont(QFont(self.ui_font, 6, QFont.Weight.DemiBold))
        self.countdown_value = QLabel()
        self.countdown_value.setObjectName("countdownValue")
        self.countdown_value.setFont(QFont(self.ui_font, 19, QFont.Weight.Light))

        countdown_layout.addWidget(self.countdown_hint, 0, Qt.AlignmentFlag.AlignHCenter)
        countdown_layout.addWidget(self.countdown_value, 0, Qt.AlignmentFlag.AlignHCenter)
        verse_layout.addWidget(countdown_wrap)
        layout.addWidget(self.verse_card)

        self.next_label = QLabel()
        self.next_label.setObjectName("nextLabel")
        self.next_label.setFont(QFont(self.ui_font, 10, QFont.Weight.Medium))
        layout.addWidget(self.next_label)

        timeline = QVBoxLayout()
        timeline.setSpacing(6)
        for index, slot in enumerate(self.SLOTS):
            row = DevotionRow(slot, self.material_font, self.ui_font, self._slot_accent(index))
            self.rows.append(row)
            timeline.addWidget(row)
        layout.addLayout(timeline)

        self.tracker_card = QFrame()
        self.tracker_card.setObjectName("trackerCard")
        tracker_layout = QVBoxLayout(self.tracker_card)
        tracker_layout.setContentsMargins(16, 16, 16, 16)
        tracker_layout.setSpacing(10)

        tracker_header = QHBoxLayout()
        tracker_header.setSpacing(8)
        tracker_icon = QLabel(material_icon("book"))
        tracker_icon.setObjectName("trackerIcon")
        tracker_icon.setFont(QFont(self.material_font, 16))
        tracker_title = QLabel("Bible Tracker")
        tracker_title.setObjectName("trackerTitle")
        tracker_title.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        tracker_header.addWidget(tracker_icon)
        tracker_header.addWidget(tracker_title)
        tracker_header.addStretch(1)
        tracker_layout.addLayout(tracker_header)

        self.tracker_book_label = QLabel()
        self.tracker_book_label.setObjectName("trackerBook")
        self.tracker_book_label.setFont(QFont(self.ui_font, 14, QFont.Weight.DemiBold))
        tracker_layout.addWidget(self.tracker_book_label)

        self.tracker_meta_label = QLabel()
        self.tracker_meta_label.setObjectName("trackerMeta")
        self.tracker_meta_label.setFont(QFont(self.ui_font, 9))
        tracker_layout.addWidget(self.tracker_meta_label)

        self.tracker_progress = TrackerProgressBar()
        self.tracker_progress.setFixedHeight(14)
        tracker_layout.addWidget(self.tracker_progress)

        self.tracker_progress_label = QLabel()
        self.tracker_progress_label.setObjectName("trackerProgressLabel")
        self.tracker_progress_label.setFont(QFont(self.ui_font, 9, QFont.Weight.Medium))
        tracker_layout.addWidget(self.tracker_progress_label)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.prev_button = self._tracker_button("chevron_left", "Previous chapter", self._go_previous_chapter)
        self.next_button = self._tracker_button("chevron_right", "Next chapter", self._go_next_chapter)
        self.finish_book_button = QPushButton("Finish Book")
        self.finish_book_button.setObjectName("trackerTextButton")
        self.finish_book_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.finish_book_button.clicked.connect(self._finish_current_book)
        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addStretch(1)
        controls.addWidget(self.finish_book_button)
        tracker_layout.addLayout(controls)
        layout.addWidget(self.tracker_card)

        footer = QHBoxLayout()
        footer.setSpacing(14)
        footer.addStretch(1)
        self.reflection_button = QPushButton("Reflection")
        self.settings_button = QPushButton("Settings")
        for button in (self.reflection_button, self.settings_button):
            button.setObjectName("footerButton")
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            footer.addWidget(button)
        footer.addStretch(1)
        layout.addStretch(1)
        layout.addLayout(footer)

    def _tracker_button(self, icon_name: str, tooltip: str, callback) -> QPushButton:
        button = QPushButton(material_icon(icon_name))
        button.setObjectName("trackerIconButton")
        button.setFont(QFont(self.material_font, 18))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        return button

    def _slot_accent(self, index: int) -> str:
        accents = [
            self.theme.primary,
            self.theme.secondary,
            self.theme.tertiary,
            self.theme.on_primary_container,
            self.theme.on_secondary,
        ]
        return accents[index % len(accents)]

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
                background: transparent;
            }}
            QFrame#card {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 24px;
            }}
            QPushButton#iconButton, QPushButton#trackerIconButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 18px;
                color: {theme.primary};
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
                font-family: "{self.material_font}";
            }}
            QPushButton#iconButton:hover, QPushButton#trackerIconButton:hover {{
                background: {theme.hover_bg};
            }}
            QLabel#dateLabel {{
                color: {theme.text};
            }}
            QLabel#periodLabel {{
                color: {theme.text_muted};
            }}
            QFrame#verseCard, QFrame#trackerCard {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 20px;
            }}
            QLabel#verseHeading {{
                color: {theme.text_muted};
                letter-spacing: 2px;
                text-transform: uppercase;
            }}
            QLabel#verseLabel {{
                color: {theme.text};
                font-family: "{self.serif_font}";
                font-style: italic;
                padding: 2px 8px 6px 8px;
            }}
            QLabel#citationLabel {{
                color: {theme.primary};
            }}
            QFrame#countdownWrap {{
                border-top: 1px solid {theme.separator};
            }}
            QLabel#countdownHint {{
                color: {theme.inactive};
                letter-spacing: 1px;
            }}
            QLabel#countdownValue {{
                color: {theme.primary};
            }}
            QLabel#nextLabel, QLabel#trackerMeta, QLabel#trackerProgressLabel {{
                color: {theme.text_muted};
                padding-left: 2px;
            }}
            QLabel#trackerTitle, QLabel#trackerBook {{
                color: {theme.text};
            }}
            QLabel#trackerIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            QPushButton#trackerTextButton {{
                background: {theme.primary};
                border: none;
                border-radius: 16px;
                color: {theme.active_text};
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
                min-height: 34px;
            }}
            QPushButton#trackerTextButton:hover {{
                background: {theme.primary_container};
                color: {theme.on_primary_container};
            }}
            QPushButton#footerButton {{
                background: transparent;
                border: none;
                color: {theme.inactive};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
                text-transform: uppercase;
                padding: 6px 4px;
            }}
            QPushButton#footerButton:hover {{
                color: {theme.primary};
            }}
            """
        )
        self.tracker_progress.apply_theme(rgba(theme.on_surface_variant, 0.16), theme.primary)
        for index, row in enumerate(self.rows):
            row.set_accent(self._slot_accent(index))

    def _apply_window_effects(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 190))
        self.card.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.x() + geo.width() - self.width() - 18, geo.y() + 72)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()
        self.refresh_content()

    def _current_verse(self, today: date) -> Verse:
        index = (today.toordinal() + self.verse_offset) % len(self.VERSES)
        return self.VERSES[index]

    def _next_devotion(self, now: datetime) -> tuple[int, datetime]:
        for index, slot in enumerate(self.SLOTS):
            candidate = datetime.combine(now.date(), slot.at)
            if candidate >= now:
                return index, candidate
        return 0, datetime.combine(now.date() + timedelta(days=1), self.SLOTS[0].at)

    def _tracker_completed_chapters(self) -> int:
        completed = sum(chapters for _, chapters in BIBLE_BOOKS[: self.tracker_state.book_index])
        completed += self.tracker_state.chapter - 1
        return max(0, min(TOTAL_BIBLE_CHAPTERS, completed))

    def _update_tracker_labels(self) -> None:
        book_name, total_chapters = BIBLE_BOOKS[self.tracker_state.book_index]
        completed = self._tracker_completed_chapters()
        ratio = completed / TOTAL_BIBLE_CHAPTERS if TOTAL_BIBLE_CHAPTERS else 0.0
        self.tracker_book_label.setText(book_name)
        self.tracker_meta_label.setText(
            f"Chapter {self.tracker_state.chapter} of {total_chapters} • {TOTAL_BIBLE_CHAPTERS - completed} chapters remaining"
        )
        self.tracker_progress_label.setText(
            f"{completed} / {TOTAL_BIBLE_CHAPTERS} chapters completed • {ratio * 100:.1f}%"
        )
        self.tracker_progress.set_ratio(ratio)
        is_last_book = self.tracker_state.book_index == len(BIBLE_BOOKS) - 1
        is_last_chapter = self.tracker_state.chapter == total_chapters
        self.finish_book_button.setDisabled(is_last_book and is_last_chapter)

    def _persist_tracker(self) -> None:
        self.tracker_state = clamp_tracker_state(self.tracker_state)
        save_tracker_state(self.tracker_state)
        self._update_tracker_labels()

    def _go_previous_chapter(self) -> None:
        if self.tracker_state.chapter > 1:
            self.tracker_state.chapter -= 1
        elif self.tracker_state.book_index > 0:
            self.tracker_state.book_index -= 1
            self.tracker_state.chapter = BIBLE_BOOKS[self.tracker_state.book_index][1]
        self._persist_tracker()

    def _go_next_chapter(self) -> None:
        book_name, total_chapters = BIBLE_BOOKS[self.tracker_state.book_index]
        if self.tracker_state.chapter < total_chapters:
            self.tracker_state.chapter += 1
        elif self.tracker_state.book_index < len(BIBLE_BOOKS) - 1:
            self.tracker_state.book_index += 1
            self.tracker_state.chapter = 1
        else:
            self.tracker_state.chapter = total_chapters
        self._persist_tracker()

    def _finish_current_book(self) -> None:
        if self.tracker_state.book_index < len(BIBLE_BOOKS) - 1:
            self.tracker_state.book_index += 1
            self.tracker_state.chapter = 1
        else:
            self.tracker_state.chapter = BIBLE_BOOKS[self.tracker_state.book_index][1]
        self._persist_tracker()

    def rotate_verse(self) -> None:
        self.verse_offset = (self.verse_offset + 1) % len(self.VERSES)
        self.refresh_content()
        self._fade_in_verse()

    def _fade_in_verse(self) -> None:
        if self._fade_animation is not None:
            self._fade_animation.stop()
        self.setWindowOpacity(0.92)
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setDuration(180)
        self._fade_animation.setStartValue(0.92)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.start()

    def refresh_content(self) -> None:
        now = datetime.now()
        today = now.date()
        verse = self._current_verse(today)
        next_index, next_time = self._next_devotion(now)

        self.date_label.setText(now.strftime("%d %B %Y"))
        self.period_label.setText(liturgical_label(today))
        self.verse_label.setText(
            (
                f"<div style='line-height: 145%;'>"
                f"&ldquo;{html.escape(verse.text)}&rdquo;"
                f"</div>"
            )
        )
        self.citation_label.setText(f"\u2014 {verse.citation}")
        self.countdown_value.setText(format_countdown(next_time - now))
        self.next_label.setText(
            f"Upcoming devotion: {self.SLOTS[next_index].name} at {self.SLOTS[next_index].at.strftime('%H:%M')}"
        )

        for index, row in enumerate(self.rows):
            row.set_active(index == next_index)
        self._update_tracker_labels()


def main() -> int:
    if not service_enabled():
        return 0
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    app.setPalette(palette)

    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)

    widget = ChristianDevotionWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
