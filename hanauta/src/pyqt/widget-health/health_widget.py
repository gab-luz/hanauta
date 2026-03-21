#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt6 health tracking widget styled to match the Christian widget direction.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
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
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.health import (
    DEFAULT_HEALTH_SERVICE_SETTINGS,
    adjust_manual_metric,
    format_sync_time,
    health_tooltip,
    load_current_snapshot,
    load_health_service_settings,
    poll_health_reminders,
)
from pyqt.shared.runtime import entry_command, python_executable
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba

FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_PAGE = APP_DIR / "pyqt" / "settings-page" / "settings.py"

MATERIAL_ICONS = {
    "favorite": "\ue87d",
    "refresh": "\ue5d5",
    "settings": "\ue8b8",
    "directions_walk": "\ue536",
    "whatshot": "\ue80e",
    "schedule": "\ue8b5",
    "water_drop": "\ue798",
    "sync": "\ue627",
    "add": "\ue145",
    "remove": "\ue15b",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


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


class ProgressBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("progressTrack")
        self._ratio = 0.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.fill = QFrame()
        self.fill.setObjectName("progressFill")
        self.fill.setMinimumWidth(10)
        layout.addWidget(self.fill, 0, Qt.AlignmentFlag.AlignLeft)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.set_ratio(self._ratio)

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, float(ratio)))
        width = max(10, int(self.width() * self._ratio))
        self.fill.setFixedWidth(width)
        self.fill.setFixedHeight(self.height())


class MetricCard(QFrame):
    def __init__(self, icon: str, title: str, material_font: str, ui_font: str) -> None:
        super().__init__()
        self.material_font = material_font
        self.ui_font = ui_font
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setObjectName("metricIcon")
        self.icon_label.setFont(QFont(self.material_font, 16))
        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricTitle")
        self.title_label.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        top.addWidget(self.icon_label)
        top.addWidget(self.title_label, 1)
        layout.addLayout(top)

        self.value_label = QLabel("--")
        self.value_label.setObjectName("metricValue")
        self.value_label.setFont(QFont(self.ui_font, 19, QFont.Weight.DemiBold))
        layout.addWidget(self.value_label)

        self.sub_label = QLabel("")
        self.sub_label.setObjectName("metricSub")
        self.sub_label.setFont(QFont(self.ui_font, 9))
        self.sub_label.setWordWrap(True)
        layout.addWidget(self.sub_label)

    def set_value(self, value: str, subtext: str = "") -> None:
        self.value_label.setText(value)
        self.sub_label.setText(subtext)


class HealthWidget(QWidget):
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
        self.snapshot = load_current_snapshot(sync_remote=False)
        self._fade_animation: QPropertyAnimation | None = None

        self._setup_window()
        self._build_ui()
        self._apply_styles()
        self._apply_window_effects()
        self._place_window()
        self.refresh_snapshot()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_live)
        self.refresh_timer.start(60 * 1000)
        QTimer.singleShot(1500, self._refresh_live)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _setup_window(self) -> None:
        self.setWindowTitle("Hanauta Health")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(404, 812)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        self.card = QFrame()
        self.card.setObjectName("card")
        root.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("contentScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        card_layout.addWidget(self.scroll_area)

        self.content = QWidget()
        self.content.setObjectName("contentWidget")
        self.scroll_area.setWidget(self.content)

        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)

        self.date_label = QLabel()
        self.date_label.setObjectName("dateLabel")
        self.date_label.setFont(QFont(self.ui_font, 17, QFont.Weight.DemiBold))

        self.provider_label = QLabel()
        self.provider_label.setObjectName("providerLabel")
        self.provider_label.setFont(QFont(self.ui_font, 10, QFont.Weight.Medium))

        title_wrap.addWidget(self.date_label)
        title_wrap.addWidget(self.provider_label)
        header.addLayout(title_wrap, 1)

        self.sync_button = QPushButton(material_icon("sync"))
        self.sync_button.setObjectName("iconButton")
        self.sync_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.sync_button.setFont(QFont(self.material_font, 18))
        self.sync_button.clicked.connect(lambda: self.refresh_snapshot(force_sync=True))

        self.refresh_button = QPushButton(material_icon("refresh"))
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_button.setFont(QFont(self.material_font, 18))
        self.refresh_button.clicked.connect(self.refresh_snapshot)

        header.addWidget(self.sync_button, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("summaryCard")
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(18, 18, 18, 18)
        summary_layout.setSpacing(10)

        summary_title = QLabel("Today's Health")
        summary_title.setObjectName("summaryTitle")
        summary_title.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        summary_layout.addWidget(summary_title, 0, Qt.AlignmentFlag.AlignHCenter)

        self.steps_label = QLabel("--")
        self.steps_label.setObjectName("stepsValue")
        self.steps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.steps_label.setFont(QFont(self.serif_font, 29))
        summary_layout.addWidget(self.steps_label)

        self.steps_subtitle = QLabel("")
        self.steps_subtitle.setObjectName("stepsSubtitle")
        self.steps_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.steps_subtitle.setFont(QFont(self.ui_font, 10, QFont.Weight.Medium))
        summary_layout.addWidget(self.steps_subtitle)

        self.steps_progress = ProgressBar()
        self.steps_progress.setFixedHeight(14)
        summary_layout.addWidget(self.steps_progress)

        self.sync_status = QLabel("")
        self.sync_status.setObjectName("syncStatus")
        self.sync_status.setWordWrap(True)
        self.sync_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sync_status.setFont(QFont(self.ui_font, 9))
        summary_layout.addWidget(self.sync_status)
        layout.addWidget(self.summary_card)

        self.metrics_wrap = QWidget()
        metrics_grid = QGridLayout(self.metrics_wrap)
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        metrics_grid.setHorizontalSpacing(10)
        metrics_grid.setVerticalSpacing(10)

        self.calories_card = MetricCard("whatshot", "Calories", self.material_font, self.ui_font)
        self.active_card = MetricCard("schedule", "Active Time", self.material_font, self.ui_font)
        self.sleep_card = MetricCard("favorite", "Sleep", self.material_font, self.ui_font)
        self.heart_card = MetricCard("favorite", "Resting HR", self.material_font, self.ui_font)
        self.water_card = MetricCard("water_drop", "Hydration", self.material_font, self.ui_font)
        self.distance_card = MetricCard("directions_walk", "Distance", self.material_font, self.ui_font)

        cards = [
            self.calories_card,
            self.active_card,
            self.sleep_card,
            self.heart_card,
            self.water_card,
            self.distance_card,
        ]
        for index, card in enumerate(cards):
            metrics_grid.addWidget(card, index // 2, index % 2)
        layout.addWidget(self.metrics_wrap)

        self.manual_card = QFrame()
        self.manual_card.setObjectName("manualCard")
        manual_layout = QVBoxLayout(self.manual_card)
        manual_layout.setContentsMargins(16, 16, 16, 16)
        manual_layout.setSpacing(10)

        manual_title = QLabel("Manual Adjustments")
        manual_title.setObjectName("manualTitle")
        manual_title.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        manual_layout.addWidget(manual_title)

        manual_hint = QLabel("Quick shortcuts for manual mode. Fitbit mode keeps these hidden and uses synced values instead.")
        manual_hint.setObjectName("manualHint")
        manual_hint.setWordWrap(True)
        manual_hint.setFont(QFont(self.ui_font, 9))
        manual_layout.addWidget(manual_hint)

        self.manual_controls = []
        for label, metric, delta in (
            ("Steps", "steps", 500),
            ("Water", "water_ml", 250),
            ("Active", "active_minutes", 10),
            ("Calories", "calories_burned", 100),
        ):
            row = QHBoxLayout()
            row.setSpacing(8)
            title = QLabel(f"{label} {delta:+d}".replace("+", "+"))
            title.setObjectName("manualRowLabel")
            title.setFont(QFont(self.ui_font, 10, QFont.Weight.Medium))
            minus = self._adjust_button("remove", lambda _checked=False, m=metric, d=delta: self._adjust_metric(m, -d))
            plus = self._adjust_button("add", lambda _checked=False, m=metric, d=delta: self._adjust_metric(m, d))
            row.addWidget(title, 1)
            row.addWidget(minus)
            row.addWidget(plus)
            manual_layout.addLayout(row)
            self.manual_controls.extend([title, minus, plus])
        layout.addWidget(self.manual_card)

        footer = QHBoxLayout()
        footer.setSpacing(14)
        footer.addStretch(1)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("footerButton")
        self.settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.settings_button.clicked.connect(self._open_settings)
        footer.addWidget(self.settings_button)
        footer.addStretch(1)
        layout.addStretch(1)
        layout.addLayout(footer)

    def _adjust_button(self, icon_name: str, callback) -> QPushButton:
        button = QPushButton(material_icon(icon_name))
        button.setObjectName("trackerIconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 18))
        button.clicked.connect(callback)
        return button

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
            QScrollArea#contentScroll, QWidget#contentWidget {{
                background: transparent;
                border: none;
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
            QLabel#providerLabel, QLabel#syncStatus, QLabel#metricSub, QLabel#manualHint {{
                color: {theme.text_muted};
            }}
            QFrame#summaryCard, QFrame#metricCard, QFrame#manualCard {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 20px;
            }}
            QLabel#summaryTitle {{
                color: {theme.text_muted};
                letter-spacing: 2px;
                text-transform: uppercase;
            }}
            QLabel#stepsValue {{
                color: {theme.text};
                font-family: "{self.serif_font}";
                font-style: italic;
            }}
            QLabel#stepsSubtitle {{
                color: {theme.primary};
            }}
            QFrame#progressTrack {{
                background: {rgba(theme.on_surface_variant, 0.16)};
                border-radius: 7px;
            }}
            QFrame#progressFill {{
                background: {theme.primary};
                border-radius: 7px;
            }}
            QLabel#metricIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            QLabel#metricTitle, QLabel#manualTitle, QLabel#manualRowLabel {{
                color: {theme.text};
            }}
            QLabel#metricValue {{
                color: {theme.text};
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
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 12px 6px 12px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {rgba(theme.primary, 0.30)};
                border-radius: 4px;
                min-height: 24px;
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
        anchor_x = -1
        anchor_y = -1
        try:
            anchor_x = int(str(os.environ.get("HANAUTA_HEALTH_ANCHOR_X", "-1")))
        except Exception:
            anchor_x = -1
        try:
            anchor_y = int(str(os.environ.get("HANAUTA_HEALTH_ANCHOR_Y", "-1")))
        except Exception:
            anchor_y = -1
        if anchor_x >= 0 and anchor_y >= 0:
            x = anchor_x - (self.width() // 2)
            y = anchor_y
            x = max(geo.x() + 12, min(x, geo.x() + geo.width() - self.width() - 12))
            y = max(geo.y() + 12, min(y, geo.y() + geo.height() - self.height() - 12))
            self.move(x, y)
            return
        self.move(geo.x() + geo.width() - self.width() - 18, geo.y() + 72)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()
        self.refresh_snapshot()

    def _refresh_live(self) -> None:
        self.refresh_snapshot(sync_remote=False)

    def _adjust_metric(self, metric: str, delta: int) -> None:
        self.snapshot = adjust_manual_metric(metric, delta)
        self._update_ui()
        self._fade_in()

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE.exists():
            return
        command = entry_command(SETTINGS_PAGE, "--page", "services", "--service-section", "health_widget")
        if not command:
            command = [python_executable(), str(SETTINGS_PAGE), "--page", "services", "--service-section", "health_widget"]
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            return


    def _fade_in(self) -> None:
        if self._fade_animation is not None:
            self._fade_animation.stop()
        self.setWindowOpacity(0.92)
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setDuration(180)
        self._fade_animation.setStartValue(0.92)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.start()

    def refresh_snapshot(self, force_sync: bool = False, sync_remote: bool = True) -> None:
        self.snapshot = load_current_snapshot(sync_remote=sync_remote, force_sync=force_sync)
        self._update_ui()

    def _update_ui(self) -> None:
        snapshot = self.snapshot
        provider = str(snapshot.get("provider", "manual")).strip().lower()
        now = datetime.now()
        self.date_label.setText(now.strftime("%d %B %Y"))
        provider_name = "Fitbit sync" if provider == "fitbit" else "Manual health log"
        self.provider_label.setText(provider_name)
        self.steps_label.setText(f"{int(snapshot.get('steps', 0)):,}")
        self.steps_subtitle.setText(
            f"{int(snapshot.get('step_goal', 0)):,} step goal • {int(snapshot.get('active_minutes', 0))} active min"
        )
        self.steps_progress.set_ratio(float(snapshot.get("step_progress", 0.0) or 0.0))
        sync_hint = str(snapshot.get("last_sync_status", "")).strip() or "Waiting for health data."
        self.sync_status.setText(
            f"{sync_hint}\nLast sync: {format_sync_time(str(snapshot.get('last_sync_at', '')))}"
        )
        self.setToolTip(health_tooltip(snapshot))

        self.calories_card.set_value(f"{int(snapshot.get('calories_burned', 0)):,}", "burned today")
        self.active_card.set_value(f"{int(snapshot.get('active_minutes', 0))}", "minutes of movement")
        self.sleep_card.set_value(f"{float(snapshot.get('sleep_hours', 0.0)):.1f} hr", "last sleep summary")
        heart_rate = int(snapshot.get("resting_heart_rate", 0) or 0)
        self.heart_card.set_value("--" if heart_rate <= 0 else f"{heart_rate}", "resting bpm")
        self.water_card.set_value(
            f"{int(snapshot.get('water_ml', 0))} ml",
            f"goal {int(snapshot.get('water_goal_ml', 0))} ml",
        )
        self.distance_card.set_value(f"{float(snapshot.get('distance_km', 0.0)):.1f} km", "distance today")

        manual_mode = provider == "manual"
        self.manual_card.setVisible(manual_mode)
        self.sync_button.setVisible(provider == "fitbit")


def main() -> int:
    service = load_health_service_settings()
    if not bool(service.get("enabled", DEFAULT_HEALTH_SERVICE_SETTINGS["enabled"])):
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

    widget = HealthWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
