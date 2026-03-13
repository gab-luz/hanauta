#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hanauta weather popup using Open-Meteo forecast data.
"""

from __future__ import annotations

import signal
import sys

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.weather import (
    AnimatedWeatherIcon,
    WeatherForecast,
    animated_icon_path,
    configured_city,
    fetch_forecast,
    static_icon_path,
)


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


class ForecastWorker(QThread):
    loaded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self) -> None:
        city = configured_city()
        if city is None:
            self.failed.emit("Choose a city in Weather settings first.")
            return
        forecast = fetch_forecast(city)
        if forecast is None:
            self.failed.emit("Weather data could not be loaded from Open-Meteo.")
            return
        self.loaded.emit(forecast)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, icon_name: str, ui_font: str, theme) -> None:
        super().__init__()
        self.setObjectName("metricCard")
        self.ui_font = ui_font
        self.theme = theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        icon = AnimatedWeatherIcon(16)
        icon.set_icon_path(static_icon_path(icon_name))
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        title_label.setFont(QFont(ui_font, 8, QFont.Weight.Medium))
        top.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(title_label, 1)
        layout.addLayout(top)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        self.value_label.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        layout.addWidget(self.value_label)


class DailyForecastRow(QFrame):
    def __init__(self, day: str, icon_name: str, precip: str, high: str, low: str, ui_font: str, theme) -> None:
        super().__init__()
        self.setObjectName("forecastRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.day_label = QLabel(day)
        self.day_label.setObjectName("forecastDay")
        self.day_label.setFont(QFont(ui_font, 11, QFont.Weight.Medium))
        self.day_label.setMinimumWidth(88)

        self.icon = AnimatedWeatherIcon(22)
        self.icon.set_icon_path(static_icon_path(icon_name))

        self.precip_label = QLabel(precip)
        self.precip_label.setObjectName("forecastMeta")
        self.precip_label.setFont(QFont(ui_font, 10))
        self.precip_label.setMinimumWidth(54)

        self.high_label = QLabel(high)
        self.high_label.setObjectName("forecastTempHigh")
        self.high_label.setFont(QFont(ui_font, 11, QFont.Weight.DemiBold))
        self.high_label.setMinimumWidth(34)

        self.low_label = QLabel(low)
        self.low_label.setObjectName("forecastTempLow")
        self.low_label.setFont(QFont(ui_font, 11, QFont.Weight.DemiBold))
        self.low_label.setMinimumWidth(34)

        layout.addWidget(self.day_label)
        layout.addWidget(self.icon)
        layout.addStretch(1)
        layout.addWidget(self.precip_label)
        layout.addWidget(self.high_label)
        layout.addWidget(self.low_label)


class WeatherPopup(QWidget):
    POPUP_RIGHT_SHIFT_RATIO = 0.72

    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.ui_font = detect_font("Inter", "Noto Sans", "DejaVu Sans", "Sans Serif")
        self.display_font = detect_font("Outfit", "Inter", "Noto Sans", "Sans Serif")
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.worker: ForecastWorker | None = None
        self._fade: QPropertyAnimation | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(470, 560)
        self.setWindowTitle("Hanauta Weather")

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self.refresh_forecast()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(3)
        eyebrow = QLabel("WEATHER")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        title = QLabel("Forecast")
        title.setObjectName("title")
        title.setFont(QFont(self.display_font, 24, QFont.Weight.Bold))
        subtitle = QLabel("Open-Meteo forecast for your selected city.")
        subtitle.setObjectName("subtitle")
        subtitle.setFont(QFont(self.ui_font, 10))
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_button.clicked.connect(self.refresh_forecast)
        header.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.hero = QFrame()
        self.hero.setObjectName("hero")
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(18)
        self.current_icon = AnimatedWeatherIcon(86)
        self.current_temp = QLabel("--")
        self.current_temp.setObjectName("currentTemp")
        self.current_temp.setFont(QFont(self.display_font, 32, QFont.Weight.Bold))
        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)
        self.current_condition = QLabel("Loading…")
        self.current_condition.setObjectName("condition")
        self.current_condition.setFont(QFont(self.ui_font, 14, QFont.Weight.Medium))
        self.city_label = QLabel("Choose a city in settings")
        self.city_label.setObjectName("city")
        self.city_label.setFont(QFont(self.ui_font, 11))
        info.addWidget(self.current_temp)
        info.addWidget(self.current_condition)
        info.addWidget(self.city_label)
        top.addWidget(self.current_icon, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(info, 1)

        sun = QVBoxLayout()
        sun.setContentsMargins(0, 0, 0, 0)
        sun.setSpacing(10)
        self.sunrise_label = QLabel("--:--")
        self.sunrise_label.setObjectName("sunValue")
        self.sunset_label = QLabel("--:--")
        self.sunset_label.setObjectName("sunValue")
        self.sunrise_wrap = self._small_stat("sunrise", "Sunrise", self.sunrise_label)
        self.sunset_wrap = self._small_stat("sunset", "Sunset", self.sunset_label)
        sun.addWidget(self.sunrise_wrap)
        sun.addWidget(self.sunset_wrap)
        top.addLayout(sun)
        hero_layout.addLayout(top)
        layout.addWidget(self.hero)

        metrics_grid = QHBoxLayout()
        metrics_grid.setSpacing(8)
        self.metric_feels = MetricCard("Feels like", "--", "thermometer", self.ui_font, self.theme)
        self.metric_humidity = MetricCard("Humidity", "--", "humidity", self.ui_font, self.theme)
        self.metric_wind = MetricCard("Wind", "--", "wind", self.ui_font, self.theme)
        self.metric_precip = MetricCard("Precip", "--", "raindrop", self.ui_font, self.theme)
        self.metric_pressure = MetricCard("Pressure", "--", "pressure-high-alt", self.ui_font, self.theme)
        for widget in (
            self.metric_feels,
            self.metric_humidity,
            self.metric_wind,
            self.metric_precip,
            self.metric_pressure,
        ):
            metrics_grid.addWidget(widget, 1)
        layout.addLayout(metrics_grid)

        self.status_label = QLabel("Loading forecast…")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        self.status_label.setFont(QFont(self.ui_font, 10))
        layout.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("forecastScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        host = QWidget()
        self.forecast_layout = QVBoxLayout(host)
        self.forecast_layout.setContentsMargins(0, 0, 0, 0)
        self.forecast_layout.setSpacing(8)
        self.forecast_layout.addStretch(1)
        self.scroll.setWidget(host)
        layout.addWidget(self.scroll, 1)

    def _small_stat(self, icon_name: str, title: str, value_label: QLabel) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("sunWrap")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        icon = AnimatedWeatherIcon(18)
        icon.set_icon_path(static_icon_path(icon_name))
        labels = QVBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("sunTitle")
        title_label.setFont(QFont(self.ui_font, 8, QFont.Weight.Medium))
        labels.addWidget(title_label)
        labels.addWidget(value_label)
        layout.addWidget(icon)
        layout.addLayout(labels)
        return wrap

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
            }}
            QFrame#panel {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {rgba(theme.surface_container_high, 0.98)},
                    stop:1 {rgba(theme.surface_container, 0.98)}
                );
                border: 1px solid {theme.panel_border};
                border-radius: 28px;
            }}
            QLabel#eyebrow {{
                color: {theme.primary};
                letter-spacing: 2px;
            }}
            QLabel#title {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#status, QLabel#city {{
                color: {theme.text_muted};
            }}
            QFrame#hero {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {rgba(theme.primary_container, 0.34)},
                    stop:1 {rgba(theme.surface_container_high, 0.92)}
                );
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 22px;
            }}
            QLabel#currentTemp {{
                color: {theme.text};
            }}
            QLabel#condition {{
                color: {theme.text};
            }}
            QFrame#sunWrap, QFrame#metricCard, QFrame#forecastRow {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 18px;
            }}
            QLabel#sunTitle, QLabel#metricTitle, QLabel#forecastMeta {{
                color: {theme.text_muted};
            }}
            QLabel#sunValue, QLabel#metricValue, QLabel#forecastDay, QLabel#forecastTempHigh {{
                color: {theme.text};
            }}
            QLabel#forecastTempLow {{
                color: {theme.text_muted};
            }}
            QPushButton#secondaryButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 16px;
                color: {theme.text};
                padding: 0 14px;
                min-height: 34px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton#secondaryButton:hover {{
                background: {theme.hover_bg};
            }}
            QScrollArea#forecastScroll {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {rgba(theme.outline, 0.30)};
                border-radius: 4px;
            }}
            """
        )

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 16)
        shadow.setColor(QColor(0, 0, 0, 190))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        target_x = cursor_pos.x() - self.width() + int(self.width() * self.POPUP_RIGHT_SHIFT_RATIO)
        target_y = cursor_pos.y() + 20
        clamped_x = max(rect.x() + 12, min(target_x, rect.right() - self.width() - 12))
        clamped_y = max(rect.y() + 12, min(target_y, rect.bottom() - self.height() - 12))
        self.move(clamped_x, clamped_y)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def refresh_forecast(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.status_label.setText("Refreshing weather forecast…")
        self.refresh_button.setDisabled(True)
        self.worker = ForecastWorker()
        self.worker.loaded.connect(self._apply_forecast)
        self.worker.failed.connect(self._show_error)
        self.worker.finished.connect(self._finish_worker)
        self.worker.start()

    def _clear_forecast_rows(self) -> None:
        while self.forecast_layout.count() > 1:
            item = self.forecast_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _apply_forecast(self, forecast: WeatherForecast) -> None:
        current = forecast.current
        self.current_icon.set_icon_path(animated_icon_path(current.icon_name))
        self.current_temp.setText(f"{round(current.temperature):.0f}°")
        self.current_condition.setText(current.condition)
        self.city_label.setText(forecast.city.label)
        self.sunrise_label.setText(current.sunrise)
        self.sunset_label.setText(current.sunset)
        self.metric_feels.value_label.setText(f"{round(current.apparent_temperature):.0f}°")
        self.metric_humidity.value_label.setText(f"{current.humidity}%")
        self.metric_wind.value_label.setText(f"{round(current.wind_speed):.0f} km/h")
        self.metric_precip.value_label.setText(f"{current.precipitation:.1f} mm")
        self.metric_pressure.value_label.setText(f"{current.pressure:.0f} hPa")
        self.status_label.setText(f"{len(forecast.daily)} day forecast loaded.")

        self._clear_forecast_rows()
        for day in forecast.daily:
            row = DailyForecastRow(
                day.weekday,
                day.icon_name,
                f"{day.precipitation_probability}%",
                f"{round(day.max_temp):.0f}°",
                f"{round(day.min_temp):.0f}°",
                self.ui_font,
                self.theme,
            )
            self.forecast_layout.insertWidget(self.forecast_layout.count() - 1, row)

    def _show_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.current_condition.setText("Unavailable")
        self.city_label.setText("Weather data is unavailable.")
        self.current_temp.setText("--")
        self.current_icon.set_icon_path(static_icon_path("not-available"))
        self._clear_forecast_rows()

    def _finish_worker(self) -> None:
        self.refresh_button.setDisabled(False)
        self.worker = None

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        QTimer.singleShot(0, self.close)


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)
    popup = WeatherPopup()
    popup.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
