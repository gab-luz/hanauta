#!/usr/bin/env python3
from __future__ import annotations

import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
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
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.crypto import fetch_chart, fetch_prices, load_settings_state, slug_to_name
from pyqt.shared.runtime import entry_command, python_executable
from pyqt.shared.theme import blend, load_theme_palette, palette_mtime, rgba


MATERIAL_ICONS = {
    "close": "\ue5cd",
    "settings": "\ue8b8",
    "refresh": "\ue5d5",
    "show_chart": "\ue6e1",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def python_bin() -> str:
    return python_executable()


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for key, path in {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
    }.items():
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


class PriceChart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.points: list[tuple[datetime, float]] = []
        self.theme = load_theme_palette()
        self.setMinimumHeight(150)

    def set_points(self, points: list[tuple[datetime, float]], theme) -> None:
        self.points = points
        self.theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.fillRect(rect, QColor(0, 0, 0, 0))
        if len(self.points) < 2:
            painter.setPen(QColor(self.theme.text_muted))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Not enough chart data yet")
            return
        values = [point[1] for point in self.points]
        low = min(values)
        high = max(values)
        span = max(0.001, high - low)
        left = float(rect.left())
        top = float(rect.top())
        width = float(rect.width())
        height = float(rect.height())

        shell = QPainterPath()
        shell.addRoundedRect(QRectF(rect), 26.0, 26.0)
        panel_gradient = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomLeft()))
        panel_gradient.setColorAt(0.0, QColor(rgba(self.theme.surface_container_high, 0.96)))
        panel_gradient.setColorAt(0.55, QColor(rgba(blend(self.theme.surface_container, self.theme.surface, 0.28), 0.88)))
        panel_gradient.setColorAt(1.0, QColor(rgba(self.theme.surface, 0.78)))
        painter.fillPath(shell, panel_gradient)
        painter.setPen(QPen(QColor(rgba(self.theme.outline, 0.16)), 1))
        painter.drawPath(shell)

        graph_rect = rect.adjusted(16, 28, -16, -30)
        left = float(graph_rect.left())
        top = float(graph_rect.top())
        width = float(graph_rect.width())
        height = float(graph_rect.height())

        grid_pen = QPen(QColor(rgba(self.theme.outline, 0.16)), 1)
        for step in range(1, 5):
            y_line = top + (height * step / 4.0)
            painter.setPen(grid_pen)
            painter.drawLine(int(left), int(y_line), int(left + width), int(y_line))

        vertical_pen = QPen(QColor(rgba(self.theme.outline, 0.10)), 1)
        for step in range(1, 4):
            x_line = left + (width * step / 4.0)
            painter.setPen(vertical_pen)
            painter.drawLine(int(x_line), int(top), int(x_line), int(top + height))

        path = QPainterPath()
        area = QPainterPath()
        for index, (_, value) in enumerate(self.points):
            x = left + (width * index / max(1, len(self.points) - 1))
            ratio = (value - low) / span
            y = top + height - (ratio * height)
            point = QPointF(x, y)
            if index == 0:
                path.moveTo(point)
                area.moveTo(left, top + height)
                area.lineTo(point)
            else:
                path.lineTo(point)
                area.lineTo(point)
        area.lineTo(left + width, top + height)
        area.closeSubpath()

        fill_gradient = QLinearGradient(QPointF(left, top), QPointF(left, top + height))
        fill_gradient.setColorAt(0.0, QColor(rgba(self.theme.primary, 0.42)))
        fill_gradient.setColorAt(0.52, QColor(rgba(blend(self.theme.primary, self.theme.secondary, 0.35), 0.18)))
        fill_gradient.setColorAt(1.0, QColor(rgba(self.theme.primary, 0.03)))
        painter.fillPath(area, fill_gradient)

        painter.setPen(QPen(QColor(rgba(self.theme.primary, 0.14)), 8))
        painter.drawPath(path)

        pen = QPen(QColor(self.theme.primary), 3)
        painter.setPen(pen)
        painter.drawPath(path)

        first_y = top + height - (((values[0] - low) / span) * height)
        last_y = top + height - (((values[-1] - low) / span) * height)
        painter.setBrush(QColor(self.theme.surface))
        painter.setPen(QPen(QColor(rgba(self.theme.primary, 0.72)), 2))
        painter.drawEllipse(QPointF(left, first_y), 4.5, 4.5)
        painter.drawEllipse(QPointF(left + width, last_y), 5.5, 5.5)

        painter.setPen(QColor(self.theme.text_muted))
        painter.drawText(QRectF(left, rect.top() + 6, width, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"High {high:.2f}")
        painter.drawText(QRectF(left, rect.top() + 6, width, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, f"{len(self.points)} points")
        painter.drawText(QRectF(left, rect.bottom() - 22, width, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, f"Low {low:.2f}")
        painter.drawText(QRectF(left, rect.bottom() - 22, width, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, "Trend")


class CryptoWidget(QWidget):
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
        self.prices: dict[str, dict] = {}
        self._last_change_positive = True

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hanauta Crypto")
        self.setFixedSize(496, 805)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self.refresh_data()

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
        header.setSpacing(14)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        eyebrow = QLabel("CRYPTO TRACKER")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        title = QLabel("Market pulse")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 24, QFont.Weight.DemiBold))
        self.subtitle = QLabel("Tracked coins, daily move, and a clearer market trend view.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_data)
        self.settings_button = self._icon_button("settings")
        self.settings_button.clicked.connect(self._open_settings)
        self.close_button = self._icon_button("close")
        self.close_button.clicked.connect(self.close)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.settings_button)
        actions.addWidget(self.close_button)
        header.addLayout(actions)
        layout.addLayout(header)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self.coin_combo = QComboBox()
        self.coin_combo.setObjectName("settingsCombo")
        self.coin_combo.currentIndexChanged.connect(self._refresh_chart_for_selection)
        top_row.addWidget(self.coin_combo, 1)
        self.window_chip = QLabel("7D WINDOW")
        self.window_chip.setObjectName("metaChip")
        self.window_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.window_chip, 0)
        layout.addLayout(top_row)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(10)
        hero_meta = QHBoxLayout()
        hero_meta.setSpacing(10)
        self.hero_badge = QLabel("SELECTED COIN")
        self.hero_badge.setObjectName("heroBadge")
        self.hero_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_badge.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.hero_timestamp = QLabel("Waiting for market data")
        self.hero_timestamp.setObjectName("heroMeta")
        self.hero_timestamp.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hero_meta.addWidget(self.hero_badge, 0)
        hero_meta.addStretch(1)
        hero_meta.addWidget(self.hero_timestamp, 0)
        hero_layout.addLayout(hero_meta)
        self.hero_title = QLabel("No pricing yet")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 18, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setWordWrap(True)
        self.hero_detail.hide()
        self.hero_price = QLabel("--")
        self.hero_price.setObjectName("heroPrice")
        self.hero_price.setFont(QFont(self.display_font, 20, QFont.Weight.DemiBold))
        self.hero_move = QLabel("24h movement unavailable")
        self.hero_move.setObjectName("heroMove")
        self.hero_move.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        self.hero_symbol = QLabel("BTC")
        self.hero_symbol.setObjectName("heroSymbol")
        self.hero_symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_symbol.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        self.hero_price_row = QHBoxLayout()
        self.hero_price_row.setSpacing(10)
        self.hero_price_row.addWidget(self.hero_price, 0, Qt.AlignmentFlag.AlignVCenter)
        self.hero_price_row.addWidget(self.hero_symbol, 0, Qt.AlignmentFlag.AlignVCenter)
        self.hero_price_row.addStretch(1)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_detail)
        hero_layout.addLayout(self.hero_price_row)
        hero_layout.addWidget(self.hero_move)
        layout.addWidget(self.hero)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        self.price_card = self._stat_card("Spot price", "--", "Latest quote")
        self.move_card = self._stat_card("24h move", "--", "Daily direction")
        self.range_card = self._stat_card("Window", "7d", "Chart span")
        stats.addWidget(self.price_card)
        stats.addWidget(self.move_card)
        stats.addWidget(self.range_card)
        layout.addLayout(stats)

        self.chart_card = QFrame()
        self.chart_card.setObjectName("chartCard")
        chart_layout = QVBoxLayout(self.chart_card)
        chart_layout.setContentsMargins(12, 12, 12, 12)
        chart_layout.setSpacing(8)
        chart_title_row = QHBoxLayout()
        chart_title_row.setSpacing(10)
        chart_eyebrow = QLabel("TREND")
        chart_eyebrow.setObjectName("eyebrow")
        chart_eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.chart_caption = QLabel("Price motion across the active window.")
        self.chart_caption.setObjectName("chartCaption")
        self.chart_caption.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        chart_title_row.addWidget(chart_eyebrow, 0)
        chart_title_row.addStretch(1)
        chart_title_row.addWidget(self.chart_caption, 0)
        chart_layout.addLayout(chart_title_row)
        self.chart = PriceChart()
        self.chart.setSizePolicy(self.chart.sizePolicy().horizontalPolicy(), self.chart.sizePolicy().verticalPolicy())
        chart_layout.addWidget(self.chart)
        layout.addWidget(self.chart_card)

        self.status_label = QLabel("Crypto tracker is idle.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.setStretchFactor(self.hero, 0)
        layout.setStretchFactor(self.chart_card, 1)

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(38, 38)
        button.setFlat(True)
        button.setFont(QFont(self.icon_font, 18))
        return button

    def _stat_card(self, label: str, value: str, note: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(3)
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

    def _set_stat_value(self, card: QFrame, value: str) -> None:
        label = getattr(card, "_value_label", None)
        if isinstance(label, QLabel):
            label.setText(value)

    def _set_stat_note(self, card: QFrame, note: str) -> None:
        label = getattr(card, "_note_label", None)
        if isinstance(label, QLabel):
            label.setText(note)

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
        x = available.x() + available.width() - self.width() - 32
        y = available.y() + 28
        max_x = available.x() + max(0, available.width() - self.width())
        max_y = available.y() + max(0, available.height() - self.height())
        self.move(min(x, max_x), min(y, max_y))

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
                    stop: 1 {rgba(blend(theme.surface_container, theme.surface, 0.42), 0.90)}
                );
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 30px;
            }}
            QLabel#eyebrow {{
                color: {theme.primary};
                letter-spacing: 1.6px;
            }}
            QLabel#title, QLabel#heroTitle, QLabel#statValue, QLabel#heroPrice {{
                color: {theme.text};
            }}
            QLabel#heroTitle {{
                letter-spacing: 0.2px;
            }}
            QLabel#subtitle, QLabel#heroDetail, QLabel#statusLabel, QLabel#chartCaption, QLabel#heroMeta, QLabel#statNote {{
                color: {theme.text_muted};
            }}
            QLabel#heroMove {{
                color: {theme.primary if self._last_change_positive else theme.error};
            }}
            QLabel#heroPrice {{
                background: {rgba(theme.on_surface, 0.06)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 18px;
                padding: 8px 14px;
            }}
            QLabel#heroSymbol {{
                background: {rgba(theme.primary, 0.12)};
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 15px;
                color: {theme.primary};
                padding: 7px 12px;
            }}
            QFrame#heroCard {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.primary_container, 0.44)},
                    stop: 0.42 {rgba(theme.secondary, 0.18)},
                    stop: 1 {rgba(theme.surface_container_high, 0.92)}
                );
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 26px;
            }}
            QFrame#statCard, QFrame#chartCard {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 24px;
            }}
            QLabel#heroBadge, QLabel#metaChip {{
                background: {rgba(theme.primary, 0.12)};
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 999px;
                color: {theme.primary};
                padding: 6px 12px;
            }}
            QLabel#statusLabel {{
                background: {rgba(theme.on_surface, 0.035)};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 20px;
                padding: 12px 14px;
            }}
            QPushButton#iconButton {{
                background: transparent;
                color: {theme.primary};
                border: 1px solid {rgba(theme.outline, 0.28)};
                border-radius: 19px;
                min-width: 38px;
                max-width: 38px;
                min-height: 38px;
                max-height: 38px;
                padding: 0;
                outline: none;
                font-family: "{self.icon_font}";
            }}
            QPushButton#iconButton:hover {{
                background: {rgba(theme.primary, 0.10)};
                border: 1px solid {rgba(theme.primary, 0.30)};
            }}
            QPushButton#iconButton:pressed {{
                background: {rgba(theme.primary, 0.16)};
                border: 1px solid {rgba(theme.primary, 0.36)};
            }}
            QPushButton#iconButton:focus {{
                border: 1px solid {rgba(theme.primary, 0.34)};
            }}
            QComboBox#settingsCombo {{
                background: {rgba(blend(theme.surface, theme.surface_container, 0.22), 0.98)};
                border: 1px solid {rgba(theme.outline, 0.24)};
                border-radius: 999px;
                padding: 10px 14px;
                min-height: 22px;
                color: {theme.text};
                selection-background-color: {rgba(theme.primary, 0.20)};
                selection-color: {theme.text};
            }}
            QComboBox#settingsCombo::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox#settingsCombo::down-arrow {{
                image: none;
            }}
            QComboBox QAbstractItemView {{
                background: {rgba(blend(theme.surface, theme.surface_container, 0.16), 0.98)};
                border: 1px solid {rgba(theme.outline, 0.24)};
                border-radius: 18px;
                color: {theme.text};
                padding: 6px;
                selection-background-color: {rgba(theme.primary, 0.16)};
                selection-color: {theme.text};
                outline: none;
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
        self._refresh_chart_for_selection()

    def refresh_data(self) -> None:
        self.settings_state = load_settings_state()
        try:
            self.prices = fetch_prices(self.settings_state)
        except Exception as exc:
            self.status_label.setText(f"Crypto fetch failed: {exc}")
            return
        self.coin_combo.blockSignals(True)
        self.coin_combo.clear()
        for coin_id in self.prices.keys():
            self.coin_combo.addItem(slug_to_name(coin_id), coin_id)
        self.coin_combo.blockSignals(False)
        if self.coin_combo.count():
            self.coin_combo.setCurrentIndex(0)
            self._refresh_chart_for_selection()
        self.status_label.setText(f"Loaded {len(self.prices)} coin snapshot(s) from CoinGecko.")

    def _refresh_chart_for_selection(self) -> None:
        coin_id = self.coin_combo.currentData()
        if not coin_id:
            self.chart.set_points([], self.theme)
            return
        coin_id = str(coin_id)
        price = self.prices.get(coin_id, {})
        currency = str(price.get("currency", "USD")).upper()
        chart_days = int(self.settings_state.get("crypto", {}).get("chart_days", 7))
        spot_price = float(price.get("price", 0.0) or 0.0)
        change_24h = float(price.get("change_24h", 0.0) or 0.0)
        self._last_change_positive = change_24h >= 0.0
        coin_name = slug_to_name(coin_id)
        self.hero_title.setText(coin_name)
        self.hero_detail.setText("")
        self.hero_detail.hide()
        self.hero_price.setText(f"{spot_price:,.2f} {currency}")
        self.hero_symbol.setText(coin_name.split()[0][:4].upper())
        self.hero_move.setText(f"{change_24h:+.2f}% over the last 24h")
        self.hero_timestamp.setText(datetime.now().strftime("Updated %H:%M"))
        self.window_chip.setText(f"{chart_days}D WINDOW")
        self.chart_caption.setText(f"{currency} movement across the last {chart_days} day(s).")
        self._set_stat_value(self.price_card, f"{spot_price:,.2f}")
        self._set_stat_note(self.price_card, currency)
        self._set_stat_value(self.move_card, f"{change_24h:+.2f}%")
        self._set_stat_note(self.move_card, "Positive drift" if self._last_change_positive else "Cooling off")
        self._set_stat_value(self.range_card, f"{chart_days}d")
        self._set_stat_note(self.range_card, "Chart span")
        try:
            points = fetch_chart(self.settings_state, coin_id)
        except Exception as exc:
            self.chart.set_points([], self.theme)
            self.status_label.setText(f"Chart fetch failed: {exc}")
            return
        self.chart.set_points(points, self.theme)
        self._apply_styles()
        self.status_label.setText(f"{slug_to_name(coin_id)} refreshed with {len(points)} chart point(s).")

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        try:
            command = entry_command(SETTINGS_PAGE_SCRIPT, "--page", "services", "--service-section", "crypto_widget")
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
    widget = CryptoWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
