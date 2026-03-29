#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication
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

HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, rgba

FONTS_DIR = APP_DIR.parents[1] / "assets" / "fonts"


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for key, file_name in {
        "material": "MaterialIcons-Regular.ttf",
        "ui": "Rubik-VariableFont_wght.ttf",
        "display": "Rubik-VariableFont_wght.ttf",
    }.items():
        path = FONTS_DIR / file_name
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


class VirtualizationPrompt(QWidget):
    def __init__(self, ide_key: str, ide_name: str, emulator_name: str, decision_file: Path) -> None:
        super().__init__()
        self.ide_key = ide_key
        self.ide_name = ide_name.strip() or ide_key
        self.emulator_name = emulator_name.strip() or "Android Emulator"
        self.decision_file = decision_file
        self.theme = load_theme_palette()
        fonts = load_app_fonts()
        self.ui_font = fonts.get("ui", "Sans Serif")
        self.display_font = fonts.get("display", self.ui_font)
        self._fade: QPropertyAnimation | None = None
        self._i3_rules_applied = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hanauta Virtualization Choice")

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._animate_in()
        self._position_overlay()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._i3_rules_applied:
            return
        self._i3_rules_applied = True
        QTimer.singleShot(100, self._apply_i3_window_rules)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        backdrop = QFrame()
        backdrop.setObjectName("backdrop")
        shell = QVBoxLayout(backdrop)
        shell.setContentsMargins(40, 40, 40, 40)
        shell.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(760)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 28)
        card_layout.setSpacing(14)

        overline = QLabel("EMULATOR LAYOUT")
        overline.setObjectName("overline")
        overline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overline.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        card_layout.addWidget(overline)

        title = QLabel("Choose emulator placement")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont(self.display_font, 26, QFont.Weight.DemiBold))
        card_layout.addWidget(title)

        detail = QLabel(
            f"{self.emulator_name} was opened while working in {self.ide_name}.\nHow should Hanauta place it?"
        )
        detail.setObjectName("detail")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setWordWrap(True)
        detail.setFont(QFont(self.ui_font, 12))
        card_layout.addWidget(detail)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 8, 0, 0)
        actions.setSpacing(10)

        split_btn = QPushButton("Split Current Workspace")
        split_btn.setObjectName("primaryButton")
        split_btn.clicked.connect(lambda: self._finish("split"))
        actions.addWidget(split_btn)

        move_btn = QPushButton("Move Emulator To Other Workspace")
        move_btn.setObjectName("secondaryButton")
        move_btn.clicked.connect(lambda: self._finish("move_workspace"))
        actions.addWidget(move_btn)

        card_layout.addLayout(actions)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("ghostButton")
        cancel_btn.clicked.connect(self.close)
        card_layout.addWidget(cancel_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        shell.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(backdrop)

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: \"{self.ui_font}\";
            }}
            QFrame#backdrop {{
                background: rgba(10, 12, 18, 0.90);
            }}
            QFrame#card {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.surface_container_high, 0.96)},
                    stop: 1 {rgba(theme.surface_container, 0.92)}
                );
                border: 1px solid {rgba(theme.primary, 0.36)};
                border-radius: 30px;
            }}
            QLabel#overline {{
                color: {theme.primary};
                letter-spacing: 2px;
            }}
            QLabel#title {{
                color: {theme.text};
            }}
            QLabel#detail {{
                color: {theme.text_muted};
            }}
            QPushButton {{
                min-height: 48px;
                border-radius: 14px;
                padding: 0 18px;
                font-size: 11pt;
                font-weight: 600;
            }}
            QPushButton#primaryButton {{
                background: {rgba(theme.primary, 0.30)};
                border: 1px solid {rgba(theme.primary, 0.58)};
                color: {theme.text};
            }}
            QPushButton#secondaryButton {{
                background: {rgba(theme.surface_variant, 0.42)};
                border: 1px solid {rgba(theme.outline, 0.42)};
                color: {theme.text};
            }}
            QPushButton#ghostButton {{
                min-width: 180px;
                background: transparent;
                border: 1px solid {rgba(theme.outline, 0.48)};
                color: {theme.text_muted};
            }}
            """
        )

    def _apply_shadow(self) -> None:
        card = self.findChild(QFrame, "card")
        if card is None:
            return
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(46)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 180))
        card.setGraphicsEffect(shadow)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start()
        self._fade = fade

    def _position_overlay(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1366, 768)
            return
        geometry = screen.availableGeometry()
        self.setGeometry(geometry)

    def _apply_i3_window_rules(self) -> None:
        if shutil.which("i3-msg") is None:
            return
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="Hanauta Virtualization Choice"]',
                    "floating enable, sticky enable, fullscreen enable global, border pixel 0, move position center",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return

    def _finish(self, action: str) -> None:
        self.decision_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ide_key": self.ide_key, "action": action}
        self.decision_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Hanauta virtualization placement prompt")
    parser.add_argument("--ide-key", default="")
    parser.add_argument("--ide", default="IDE")
    parser.add_argument("--emulator", default="Android Emulator")
    parser.add_argument("--decision-file", default="")
    args = parser.parse_args()

    decision_file = Path(str(args.decision_file or "")).expanduser()
    if not str(decision_file).strip():
        return 1

    app = QApplication(sys.argv)
    window = VirtualizationPrompt(str(args.ide_key or "").strip(), str(args.ide or "IDE"), str(args.emulator or "Android Emulator"), decision_file)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
