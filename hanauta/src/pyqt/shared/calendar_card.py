from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QDate, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QTextCharFormat
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class HanautaCalendarWidget(QCalendarWidget):
    def __init__(self) -> None:
        super().__init__()
        self._body_color = QColor("#ffffff")
        self._muted_color = QColor(255, 255, 255, 140)
        self._primary_color = QColor("#d0bcff")
        self._active_text_color = QColor("#1c1b1f")
        self._today_outline_color = QColor("#d0bcff")

    def set_theme_colors(
        self,
        *,
        body: QColor,
        muted: QColor,
        primary: QColor,
        active_text: QColor,
    ) -> None:
        self._body_color = QColor(body)
        self._muted_color = QColor(muted)
        self._primary_color = QColor(primary)
        self._active_text_color = QColor(active_text)
        self._today_outline_color = QColor(primary)
        self.updateCells()

    def paintCell(  # type: ignore[override]
        self, painter: QPainter, rect: QRect, date: QDate
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cell_rect = rect.adjusted(3, 3, -3, -3)
        is_selected = date == self.selectedDate()
        is_today = date == QDate.currentDate()
        is_current_month = (
            date.month() == self.monthShown() and date.year() == self.yearShown()
        )

        if is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._primary_color)
            painter.drawRoundedRect(cell_rect, 8, 8)
            text_color = self._active_text_color
        else:
            if is_today:
                painter.setPen(QPen(self._today_outline_color, 1.2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(cell_rect, 8, 8)
            text_color = self._body_color if is_current_month else self._muted_color

        painter.setPen(text_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(date.day()))
        painter.restore()


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

    calendar = HanautaCalendarWidget()
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
    body_color = QColor("#000000") if is_light else QColor("#ffffff")
    if not is_light:
        body_color.setAlphaF(0.94)

    disabled_color = QColor(body_color)
    disabled_color.setAlphaF(0.52 if not is_light else 0.60)
    primary_color = QColor(theme_primary)
    active_text_color = QColor(theme_active_text)
    if not primary_color.isValid():
        primary_color = QColor("#d0bcff")
    if not active_text_color.isValid():
        active_text_color = QColor("#1c1b1f")

    palette = calendar.palette()
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(role, body_color)
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled_color)
    palette.setColor(QPalette.ColorRole.Highlight, primary_color)
    palette.setColor(QPalette.ColorRole.HighlightedText, active_text_color)

    base_bg = QColor(theme_surface_container_high)
    base_bg.setAlphaF(0.36 if is_light else 0.20)
    for role in (
        QPalette.ColorRole.Base,
        QPalette.ColorRole.AlternateBase,
        QPalette.ColorRole.Button,
    ):
        palette.setColor(role, base_bg)
    calendar.setPalette(palette)

    if isinstance(calendar, HanautaCalendarWidget):
        calendar.set_theme_colors(
            body=body_color,
            muted=disabled_color,
            primary=primary_color,
            active_text=active_text_color,
        )

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
    header_fmt.setForeground(primary_color if not is_light else QColor("#000000"))
    calendar.setHeaderTextFormat(header_fmt)

    weekday_fmt = QTextCharFormat()
    weekday_fmt.setForeground(body_color)
    weekend_fmt = QTextCharFormat()
    weekend_fmt.setForeground(primary_color if is_light else body_color)

    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Monday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Tuesday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Wednesday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Thursday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Friday, weekday_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend_fmt)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend_fmt)

    today_fmt = QTextCharFormat()
    today_fmt.setForeground(active_text_color)
    today_fmt.setBackground(primary_color)
    calendar.setDateTextFormat(QDate.currentDate(), today_fmt)
