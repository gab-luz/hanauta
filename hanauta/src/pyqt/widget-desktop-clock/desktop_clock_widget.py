#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import signal
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QWidget


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for key, path in {
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


def load_settings_state() -> dict:
    default = {
        "clock": {
            "size": 320,
            "show_seconds": True,
            "position_x": -1,
            "position_y": -1,
        },
        "region": {
            "use_24_hour": False,
        },
    }
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default
    clock = payload.get("clock", {})
    if isinstance(clock, dict):
        default["clock"].update(clock)
    region = payload.get("region", {})
    if isinstance(region, dict):
        default["region"].update(region)
    return default


def save_clock_position(x: int, y: int) -> None:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    clock = payload.setdefault("clock", {})
    if not isinstance(clock, dict):
        clock = {}
        payload["clock"] = clock
    clock["position_x"] = int(x)
    clock["position_y"] = int(y)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class DesktopClockWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font(fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font(fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.settings_state = load_settings_state()
        self.drag_offset = QPoint()
        self.dragging = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnBottomHint
        )
        self.setWindowTitle("Hanauta Desktop Clock")

        self._apply_size()
        self._place_window()

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.update)
        self.tick_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _apply_size(self) -> None:
        size = max(220, min(520, int(self.settings_state.get("clock", {}).get("size", 320) or 320)))
        self.setFixedSize(size, size)

    def _place_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        clock_settings = self.settings_state.get("clock", {})
        pos_x = int(clock_settings.get("position_x", -1) or -1)
        pos_y = int(clock_settings.get("position_y", -1) or -1)
        if pos_x >= 0 and pos_y >= 0:
            self.move(pos_x, pos_y)
            return
        self.move(
            available.x() + available.width() - self.width() - 64,
            available.y() + 96,
        )

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime != self._theme_mtime:
            self._theme_mtime = current_mtime
            self.theme = load_theme_palette()
        current_settings = load_settings_state()
        if current_settings.get("clock", {}) != self.settings_state.get("clock", {}):
            self.settings_state = current_settings
            self._apply_size()
            self._place_window()
        else:
            self.settings_state = current_settings
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self.dragging and event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            save_clock_position(self.x(), self.y())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _format_hour(self, moment: datetime) -> str:
        if bool(self.settings_state.get("region", {}).get("use_24_hour", False)):
            return moment.strftime("%H")
        return moment.strftime("%I")

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(10, 10, -10, -10)
        center = QPointF(rect.center())
        outer_radius = min(rect.width(), rect.height()) / 2.0 - 6.0
        inner_radius = outer_radius * 0.90

        face_path = QPainterPath()
        scallops = 18
        for index in range(scallops * 6 + 1):
            angle = (math.tau * index) / (scallops * 6)
            pulse = math.sin(angle * scallops)
            radius = outer_radius + pulse * (outer_radius * 0.045)
            point = QPointF(center.x() + math.cos(angle - math.pi / 2) * radius, center.y() + math.sin(angle - math.pi / 2) * radius)
            if index == 0:
                face_path.moveTo(point)
            else:
                face_path.lineTo(point)
        face_path.closeSubpath()

        painter.fillPath(face_path, QColor(rgba(self.theme.surface_container_high, 0.86)))
        outline_pen = QPen(QColor(rgba(self.theme.outline, 0.38)), 1.5)
        painter.setPen(outline_pen)
        painter.drawPath(face_path)

        tick_pen = QPen(QColor(rgba(self.theme.text, 0.72)), max(2.0, outer_radius * 0.012))
        tick_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(tick_pen)
        for index in range(60):
            angle = (math.tau * index) / 60.0 - math.pi / 2
            outer = inner_radius * 0.96
            inner = inner_radius * (0.83 if index % 5 == 0 else 0.89)
            start = QPointF(center.x() + math.cos(angle) * inner, center.y() + math.sin(angle) * inner)
            end = QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer)
            painter.drawLine(start, end)

        now = datetime.now()
        hour_text = self._format_hour(now)
        minute_text = now.strftime("%M")
        digital_color = QColor(rgba(self.theme.text, 0.36))
        painter.setPen(digital_color)
        painter.setFont(QFont(self.display_font, max(44, int(outer_radius * 0.46)), QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, int(-outer_radius * 0.22), 0, 0), Qt.AlignmentFlag.AlignCenter, hour_text)
        painter.drawText(self.rect().adjusted(0, int(outer_radius * 0.18), 0, 0), Qt.AlignmentFlag.AlignCenter, minute_text)

        hour_angle = ((now.hour % 12) + now.minute / 60.0) * (math.tau / 12.0) - math.pi / 2
        minute_angle = (now.minute + now.second / 60.0) * (math.tau / 60.0) - math.pi / 2
        second_angle = now.second * (math.tau / 60.0) - math.pi / 2

        painter.setPen(QPen(QColor(rgba(self.theme.text, 0.84)), max(10.0, outer_radius * 0.07), cap=Qt.PenCapStyle.RoundCap))
        painter.drawLine(center, QPointF(center.x() + math.cos(hour_angle) * inner_radius * 0.44, center.y() + math.sin(hour_angle) * inner_radius * 0.44))

        painter.setPen(QPen(QColor(rgba(self.theme.primary, 0.96)), max(7.0, outer_radius * 0.048), cap=Qt.PenCapStyle.RoundCap))
        painter.drawLine(center, QPointF(center.x() + math.cos(minute_angle) * inner_radius * 0.63, center.y() + math.sin(minute_angle) * inner_radius * 0.63))

        if bool(self.settings_state.get("clock", {}).get("show_seconds", True)):
            painter.setPen(QPen(QColor(self.theme.error), max(3.0, outer_radius * 0.018), cap=Qt.PenCapStyle.RoundCap))
            painter.drawLine(center, QPointF(center.x() + math.cos(second_angle) * inner_radius * 0.70, center.y() + math.sin(second_angle) * inner_radius * 0.70))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(rgba(self.theme.primary_container, 0.92)))
        painter.drawEllipse(center, max(8.0, outer_radius * 0.05), max(8.0, outer_radius * 0.05))
        painter.setBrush(QColor(self.theme.on_primary_container))
        painter.drawEllipse(center, max(3.0, outer_radius * 0.018), max(3.0, outer_radius * 0.018))


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    widget = DesktopClockWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
