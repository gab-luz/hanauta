#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt6 Christian devotion widget rebuilt from idea.html.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import json

from PyQt6.QtCore import Qt, QTimer
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


ROOT = Path(__file__).resolve().parents[4]
FONTS_DIR = ROOT / "assets" / "fonts"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SETTINGS_FILE = STATE_DIR / "settings.json"

MATERIAL_ICONS = {
    "auto_awesome": "\ue65f",
    "brightness_3": "\ue3a8",
    "calendar_today": "\ue935",
    "light_mode": "\ue518",
    "nights_stay": "\uf1d2",
    "refresh": "\ue5d5",
    "schedule": "\ue8b5",
    "wb_twilight": "\ue1c6",
}


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
    color: str
    icon: str


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


class DevotionRow(QFrame):
    def __init__(self, slot: DevotionSlot, material_font: str, ui_font: str) -> None:
        super().__init__()
        self.slot = slot
        self.material_font = material_font
        self.ui_font = ui_font
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

    def set_active(self, active: bool) -> None:
        bg = "rgba(195, 177, 225, 0.12)" if active else "transparent"
        border = "rgba(195, 177, 225, 0.32)" if active else "transparent"
        name_color = "#c3b1e1" if active else "rgba(255,255,255,0.90)"
        time_color = "#c3b1e1" if active else "rgba(255,255,255,0.60)"
        self.setStyleSheet(
            f"""
            QFrame#devotionRow {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QFrame#devotionRow:hover {{
                background: rgba(255,255,255,0.05);
            }}
            QLabel#rowIcon {{
                color: {self.slot.color};
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
        DevotionSlot("Morning Prayer", time(6, 30), "rgba(255, 232, 183, 0.78)", "wb_twilight"),
        DevotionSlot("Noon Grace", time(12, 15), "#c3b1e1", "light_mode"),
        DevotionSlot("Evening Vesper", time(18, 45), "rgba(255, 197, 136, 0.72)", "wb_twilight"),
        DevotionSlot("Night Prayer", time(21, 30), "rgba(165, 197, 255, 0.72)", "brightness_3"),
        DevotionSlot("Compline", time(23, 0), "rgba(170, 164, 255, 0.72)", "schedule"),
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
        self.verse_offset = 0
        self.rows: list[DevotionRow] = []

        self._setup_window()
        self._build_ui()
        self._apply_window_effects()
        self._place_window()
        self.refresh_content()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_content)
        self.timer.start(1000)

    def _setup_window(self) -> None:
        self.setWindowTitle("Christian Devotion")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(404, 624)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        self.card = QFrame()
        self.card.setObjectName("card")
        root.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

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
        for slot in self.SLOTS:
            row = DevotionRow(slot, self.material_font, self.ui_font)
            self.rows.append(row)
            timeline.addWidget(row)
        layout.addLayout(timeline)

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

        self.setStyleSheet(
            f"""
            QWidget {{
                color: #ede7f4;
                font-family: "Inter", "Noto Sans", sans-serif;
            }}
            QFrame#card {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(30, 27, 46, 230),
                    stop:1 rgba(18, 18, 28, 242));
                border: 1px solid rgba(195, 177, 225, 0.16);
                border-radius: 24px;
            }}
            QPushButton#iconButton {{
                background: transparent;
                border: none;
                border-radius: 18px;
                color: #c3b1e1;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
                font-family: "{self.material_font}";
            }}
            QPushButton#iconButton:hover {{
                background: rgba(255, 255, 255, 0.08);
            }}
            QLabel#dateLabel {{
                color: #ffffff;
            }}
            QLabel#periodLabel {{
                color: rgba(195, 177, 225, 0.78);
            }}
            QFrame#verseCard {{
                background: rgba(195, 177, 225, 0.05);
                border: 1px solid rgba(195, 177, 225, 0.22);
                border-radius: 20px;
            }}
            QLabel#verseHeading {{
                color: rgba(195, 177, 225, 0.64);
                letter-spacing: 2px;
                text-transform: uppercase;
            }}
            QLabel#verseLabel {{
                color: #ffffff;
                font-family: "{self.serif_font}";
                font-style: italic;
                line-height: 1.4;
            }}
            QLabel#citationLabel {{
                color: rgba(195, 177, 225, 0.84);
            }}
            QFrame#countdownWrap {{
                border-top: 1px solid rgba(255, 255, 255, 0.05);
            }}
            QLabel#countdownHint {{
                color: rgba(255, 255, 255, 0.40);
                letter-spacing: 1px;
            }}
            QLabel#countdownValue {{
                color: #c3b1e1;
            }}
            QLabel#nextLabel {{
                color: rgba(255, 255, 255, 0.60);
                padding-left: 2px;
            }}
            QPushButton#footerButton {{
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.34);
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
                text-transform: uppercase;
                padding: 6px 4px;
            }}
            QPushButton#footerButton:hover {{
                color: #c3b1e1;
            }}
            """
        )

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

    def _current_verse(self, today: date) -> Verse:
        index = (today.toordinal() + self.verse_offset) % len(self.VERSES)
        return self.VERSES[index]

    def _next_devotion(self, now: datetime) -> tuple[int, datetime]:
        for index, slot in enumerate(self.SLOTS):
            candidate = datetime.combine(now.date(), slot.at)
            if candidate >= now:
                return index, candidate
        return 0, datetime.combine(now.date() + timedelta(days=1), self.SLOTS[0].at)

    def rotate_verse(self) -> None:
        self.verse_offset = (self.verse_offset + 1) % len(self.VERSES)
        self.refresh_content()

    def refresh_content(self) -> None:
        now = datetime.now()
        today = now.date()
        verse = self._current_verse(today)
        next_index, next_time = self._next_devotion(now)

        self.date_label.setText(now.strftime("%d %B %Y"))
        self.period_label.setText(liturgical_label(today))
        self.verse_label.setText(f'"{verse.text}"')
        self.citation_label.setText(f"\u2014 {verse.citation}")
        self.countdown_value.setText(format_countdown(next_time - now))
        self.next_label.setText(
            f"Upcoming devotion: {self.SLOTS[next_index].name} at {self.SLOTS[next_index].at.strftime('%H:%M')}"
        )

        for index, row in enumerate(self.rows):
            row.set_active(index == next_index)


def main() -> int:
    if not service_enabled():
        return 0
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    app.setPalette(palette)

    widget = ChristianDevotionWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
