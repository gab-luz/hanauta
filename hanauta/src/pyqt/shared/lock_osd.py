#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

try:
    from pyqt.shared.theme import load_theme_palette
except Exception:
    load_theme_palette = None


class LockOsd(QWidget):
    def __init__(self, title: str, body: str, duration_ms: int) -> None:
        super().__init__()
        self._duration_ms = max(700, duration_ms)
        self._fade_in: QPropertyAnimation | None = None
        self._fade_out: QPropertyAnimation | None = None
        self._build_ui(title, body)
        self._place_center()

    def _build_ui(self, title: str, body: str) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle("Hanauta Lock OSD")

        palette = load_theme_palette() if callable(load_theme_palette) else None
        accent = getattr(palette, "accent", "#97ccf9") if palette else "#97ccf9"
        panel = getattr(palette, "panel", "#101417") if palette else "#101417"
        text = getattr(palette, "text", "#e0e3e8") if palette else "#e0e3e8"
        muted = getattr(palette, "subtext", "#a9b1d6") if palette else "#a9b1d6"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            f"""
            QFrame#card {{
                background: rgba({QColor(panel).red()}, {QColor(panel).green()}, {QColor(panel).blue()}, 230);
                border: 1px solid rgba({QColor(accent).red()}, {QColor(accent).green()}, {QColor(accent).blue()}, 120);
                border-radius: 22px;
            }}
            QLabel#title {{
                color: {text};
                font-size: 26px;
                font-weight: 700;
                font-family: Rubik, Sans Serif;
            }}
            QLabel#body {{
                color: {muted};
                font-size: 15px;
                font-weight: 500;
                font-family: Rubik, Sans Serif;
            }}
            """
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 180))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("title")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setFont(QFont("Rubik", 20, QFont.Weight.DemiBold))

        body_lbl = QLabel(body)
        body_lbl.setObjectName("body")
        body_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_lbl.setFont(QFont("Rubik", 11, QFont.Weight.Medium))

        layout.addWidget(title_lbl)
        layout.addWidget(body_lbl)
        root.addWidget(card)
        self.setFixedSize(480, 150)

    def _place_center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.center().x() - self.width() // 2, rect.center().y() - self.height() // 2)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._animate_in()
        QTimer.singleShot(self._duration_ms, self._animate_out)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(140)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in.start()

    def _animate_out(self) -> None:
        self._fade_out = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out.setDuration(220)
        self._fade_out.setStartValue(self.windowOpacity())
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(QApplication.instance().quit)
        self._fade_out.start()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hanauta lock OSD")
    parser.add_argument("--title", default="Locking...")
    parser.add_argument("--body", default="Please wait...")
    parser.add_argument("--duration-ms", type=int, default=1350)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta Lock OSD")
    widget = LockOsd(args.title, args.body, args.duration_ms)
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
