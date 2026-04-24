from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont, QPalette, QTextCharFormat
from PyQt6.QtWidgets import QCalendarWidget, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


def build_calendar_card(
    *,
    material_font: str,
    settings_glyph: str,
    on_open_settings: Callable[[], None],
    title: str = "Calendar",
) -> tuple[QFrame, QCalendarWidget, QPushButton]:
    card = QFrame()
    card.setObjectName("overviewSection")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(8)

    title_label = QLabel(title)
    title_label.setObjectName("sectionTitle")

    settings_btn = QPushButton(settings_glyph)
    settings_btn.setObjectName("circleIconButton")
    settings_btn.setFixedSize(30, 30)
    settings_btn.setFont(QFont(material_font, 16))
    settings_btn.setToolTip("Open calendar service settings")
    settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    settings_btn.clicked.connect(on_open_settings)

    header.addWidget(title_label)
    header.addStretch(1)
    header.addWidget(settings_btn)
    layout.addLayout(header)

    calendar = QCalendarWidget()
    calendar.setObjectName("miniCalendar")
    calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    calendar.setGridVisible(False)
    layout.addWidget(calendar)
    return card, calendar, settings_btn


def apply_calendar_theme(
    calendar: QCalendarWidget,
    *,
    theme_primary: str,
    theme_active_text: str,
    theme_text: str,
    theme_surface_container_high: str,
    is_light: bool,
) -> None:
    body_color = QColor("#000000") if is_light else QColor(theme_text)
    if not body_color.isValid():
        body_color = QColor("#ffffff" if not is_light else "#000000")
    if not is_light:
        body_color.setAlphaF(0.92)

    disabled_color = QColor(body_color)
    disabled_color.setAlphaF(0.55 if not is_light else 0.60)

    palette = calendar.palette()
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(role, body_color)
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled_color)
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme_primary))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme_active_text))

    base_bg = QColor(theme_surface_container_high)
    base_bg.setAlphaF(0.36 if is_light else 0.20)
    for role in (
        QPalette.ColorRole.Base,
        QPalette.ColorRole.AlternateBase,
        QPalette.ColorRole.Button,
    ):
        palette.setColor(role, base_bg)
    calendar.setPalette(palette)

    # Extra safety: QCalendarWidget sometimes ignores palette text roles for the day grid.
    # Apply explicit per-widget stylesheet for item text.
    calendar_body_text = "#000000" if is_light else "rgba(255,255,255,0.92)"
    calendar_body_disabled = "#6c6c6c" if is_light else "rgba(255,255,255,0.55)"
    calendar.setStyleSheet(
        f"""
        QCalendarWidget#miniCalendar QAbstractItemView,
        QCalendarWidget#miniCalendar QTableView {{
            color: {calendar_body_text};
        }}
        QCalendarWidget#miniCalendar QAbstractItemView::item {{
            color: {calendar_body_text};
        }}
        QCalendarWidget#miniCalendar QAbstractItemView::item:disabled {{
            color: {calendar_body_disabled};
        }}
        """
    )

    header_fmt = QTextCharFormat()
    header_fmt.setForeground(QColor(theme_primary if not is_light else "#000000"))
    calendar.setHeaderTextFormat(header_fmt)

    weekday_fmt = QTextCharFormat()
    weekday_fmt.setForeground(body_color)
    weekend_fmt = QTextCharFormat()
    weekend_fmt.setForeground(QColor(theme_primary) if is_light else body_color)

    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Monday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Tuesday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Wednesday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Thursday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Friday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend_fmt)

    today_fmt = QTextCharFormat()
    today_fmt.setForeground(QColor(theme_active_text))
    today_fmt.setBackground(QColor(theme_primary))
    calendar.setDateTextFormat(QDate.currentDate(), today_fmt)

