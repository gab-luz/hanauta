#!/usr/bin/env python3
from __future__ import annotations

import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QPainter, QPainterPath, QPen
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
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba


MATERIAL_ICONS = {
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
        self.setMinimumHeight(224)

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

        gradient_fill = QColor(self.theme.primary)
        gradient_fill.setAlpha(48)
        painter.fillPath(area, gradient_fill)
        pen = QPen(QColor(self.theme.primary), 3)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.setPen(QColor(self.theme.text_muted))
        painter.drawText(QRectF(left, top, width, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"High {high:.2f}")
        painter.drawText(QRectF(left, top + height - 20, width, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, f"Low {low:.2f}")


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

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hanauta Crypto")
        self.setFixedSize(560, 682)

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
        titles = QVBoxLayout()
        eyebrow = QLabel("CRYPTO TRACKER")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        title = QLabel("Watch the market breathe")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 22, QFont.Weight.DemiBold))
        self.subtitle = QLabel("High-resolution price moves with multiple tracked coins.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_data)
        self.settings_button = self._icon_button("settings")
        self.settings_button.clicked.connect(self._open_settings)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.settings_button)
        header.addLayout(actions)
        layout.addLayout(header)

        top_row = QHBoxLayout()
        self.coin_combo = QComboBox()
        self.coin_combo.setObjectName("settingsCombo")
        self.coin_combo.currentIndexChanged.connect(self._refresh_chart_for_selection)
        top_row.addWidget(self.coin_combo, 1)
        layout.addLayout(top_row)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(6)
        self.hero_title = QLabel("No pricing yet")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 17, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("Refresh to fetch CoinGecko market data.")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setWordWrap(True)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_detail)
        layout.addWidget(self.hero)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.price_card = self._stat_card("Price", "--")
        self.move_card = self._stat_card("24h", "--")
        self.range_card = self._stat_card("Window", "7d")
        stats.addWidget(self.price_card)
        stats.addWidget(self.move_card)
        stats.addWidget(self.range_card)
        layout.addLayout(stats)

        self.chart = PriceChart()
        layout.addWidget(self.chart)

        self.status_label = QLabel("Crypto tracker is idle.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(38, 38)
        button.setFont(QFont(self.icon_font, 18))
        return button

    def _stat_card(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(3)
        title = QLabel(label.upper())
        title.setObjectName("eyebrow")
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        card_layout.addWidget(title)
        card_layout.addWidget(value_label)
        card._value_label = value_label  # type: ignore[attr-defined]
        return card

    def _set_stat_value(self, card: QFrame, value: str) -> None:
        label = getattr(card, "_value_label", None)
        if isinstance(label, QLabel):
            label.setText(value)

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
        self.move(available.x() + available.width() - self.width() - 48, available.y() + 92)

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
            QLabel#title, QLabel#heroTitle, QLabel#statValue {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#heroDetail, QLabel#statusLabel {{
                color: {theme.text_muted};
            }}
            QFrame#heroCard, QFrame#statCard {{
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
            QComboBox#settingsCombo {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                padding: 9px 12px;
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
        self.hero_title.setText(slug_to_name(coin_id))
        self.hero_detail.setText(f"Tracking {coin_id} against {str(price.get('currency', 'USD'))}.")
        self._set_stat_value(self.price_card, f"{price.get('price', 0.0):,.2f} {price.get('currency', 'USD')}")
        self._set_stat_value(self.move_card, f"{float(price.get('change_24h', 0.0)):+.2f}%")
        self._set_stat_value(self.range_card, f"{int(self.settings_state.get('crypto', {}).get('chart_days', 7))}d")
        try:
            points = fetch_chart(self.settings_state, coin_id)
        except Exception as exc:
            self.chart.set_points([], self.theme)
            self.status_label.setText(f"Chart fetch failed: {exc}")
            return
        self.chart.set_points(points, self.theme)

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
