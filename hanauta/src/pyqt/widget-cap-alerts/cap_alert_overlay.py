#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QColor, QCursor, QDesktopServices, QFont, QFontDatabase, QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"
DEFAULT_ALERT_SOUND = Path("/usr/share/sounds/freedesktop/stereo/complete.ogg")

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command
from pyqt.shared.theme import blend, load_theme_palette, rgba
from pyqt.shared.weather import AnimatedWeatherIcon, animated_icon_path


MATERIAL_ICONS = {
    "warning": "\ue002",
    "open_in_new": "\ue89e",
    "close": "\ue5cd",
}

POPUP_SCRIPT = HERE / "cap_alerts_popup.py"
SETTINGS_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "ui_display": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
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


class CapAlertOverlay(QWidget):
    def __init__(self, title: str, headline: str, area: str, tip: str, contact: str, url: str, icon_name: str) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.theme = load_theme_palette()
        self.title_text = title.strip() or "Weather alert"
        self.headline_text = headline.strip() or "Official alert received."
        self.area_text = area.strip() or "Affected area unavailable."
        self.tip_text = tip.strip() or "Follow official safety guidance."
        self.contact_text = contact.strip() or "Official local emergency services"
        self.url = url.strip()
        self.icon_name = icon_name.strip() or "warning"
        self._fade: QPropertyAnimation | None = None
        self._audio_process: subprocess.Popen[str] | None = None
        self._i3_rules_applied = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
        )
        self.setWindowTitle("Hanauta CAP Alert")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._register_shortcuts()
        self._animate_in()
        self._start_sound()
        self._position_overlay()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._i3_rules_applied:
            return
        self._i3_rules_applied = True
        QTimer.singleShot(0, self._set_window_identity)
        QTimer.singleShot(120, self._apply_i3_window_rules)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        backdrop = QFrame()
        backdrop.setObjectName("backdrop")
        backdrop_layout = QVBoxLayout(backdrop)
        backdrop_layout.setContentsMargins(48, 48, 48, 48)
        backdrop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setMaximumWidth(760)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(34, 34, 34, 34)
        card_layout.setSpacing(18)

        top = QHBoxLayout()
        top.setSpacing(14)

        hero_icon_wrap = QFrame()
        hero_icon_wrap.setObjectName("heroIconWrap")
        hero_icon_layout = QVBoxLayout(hero_icon_wrap)
        hero_icon_layout.setContentsMargins(0, 0, 0, 0)
        hero_icon = AnimatedWeatherIcon(56)
        hero_icon.set_icon_path(animated_icon_path(self.icon_name))
        hero_icon_layout.addWidget(hero_icon, 0, Qt.AlignmentFlag.AlignCenter)
        top.addWidget(hero_icon_wrap, 0, Qt.AlignmentFlag.AlignTop)

        title_col = QVBoxLayout()
        title_col.setSpacing(8)
        overline = QLabel("OFFICIAL ALERT")
        overline.setObjectName("overline")
        overline.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        title = QLabel(self.title_text)
        title.setObjectName("title")
        title.setWordWrap(True)
        title.setFont(QFont(self.display_font, 30, QFont.Weight.DemiBold))
        headline = QLabel(self.headline_text)
        headline.setObjectName("headline")
        headline.setWordWrap(True)
        headline.setFont(QFont(self.ui_font, 12, QFont.Weight.Medium))
        title_col.addWidget(overline)
        title_col.addWidget(title)
        title_col.addWidget(headline)
        top.addLayout(title_col, 1)

        card_layout.addLayout(top)

        area_card = QFrame()
        area_card.setObjectName("infoCard")
        area_layout = QVBoxLayout(area_card)
        area_layout.setContentsMargins(16, 14, 16, 14)
        area_layout.setSpacing(8)
        area_label = QLabel("Affected Area")
        area_label.setObjectName("metaLabel")
        area_body = QLabel(self.area_text)
        area_body.setObjectName("infoBody")
        area_body.setWordWrap(True)
        area_layout.addWidget(area_label)
        area_layout.addWidget(area_body)
        card_layout.addWidget(area_card)

        tip_card = QFrame()
        tip_card.setObjectName("tipCard")
        tip_layout = QVBoxLayout(tip_card)
        tip_layout.setContentsMargins(18, 16, 18, 16)
        tip_layout.setSpacing(8)
        tip_label = QLabel("What To Do Right Now")
        tip_label.setObjectName("metaLabel")
        tip_body = QLabel(self.tip_text)
        tip_body.setObjectName("tipBody")
        tip_body.setWordWrap(True)
        tip_layout.addWidget(tip_label)
        tip_layout.addWidget(tip_body)
        card_layout.addWidget(tip_card)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        contact_card = QFrame()
        contact_card.setObjectName("infoCard")
        contact_layout = QVBoxLayout(contact_card)
        contact_layout.setContentsMargins(16, 14, 16, 14)
        contact_layout.setSpacing(6)
        contact_label = QLabel("Emergency Contact")
        contact_label.setObjectName("metaLabel")
        contact_value = QLabel(self.contact_text)
        contact_value.setObjectName("contactValue")
        contact_value.setWordWrap(True)
        contact_layout.addWidget(contact_label)
        contact_layout.addWidget(contact_value)
        bottom.addWidget(contact_card, 1)

        url_card = QFrame()
        url_card.setObjectName("infoCard")
        url_layout = QVBoxLayout(url_card)
        url_layout.setContentsMargins(16, 14, 16, 14)
        url_layout.setSpacing(6)
        url_label = QLabel("Official Bulletin")
        url_label.setObjectName("metaLabel")
        url_value = QLabel(self.url or "Open the detailed alert popup for the official source link.")
        url_value.setObjectName("infoBody")
        url_value.setWordWrap(True)
        url_layout.addWidget(url_label)
        url_layout.addWidget(url_value)
        bottom.addWidget(url_card, 1)
        card_layout.addLayout(bottom)

        actions = QFrame()
        actions.setObjectName("actionsWrap")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(10, 10, 10, 10)
        actions_layout.setSpacing(12)

        dismiss = self._button("Dismiss", material_icon("close"), primary=False)
        dismiss.clicked.connect(self.close)
        details = self._button("Open Details", material_icon("open_in_new"), primary=True)
        details.clicked.connect(self._open_details)
        region = self._button("Region Settings", material_icon("warning"), primary=False)
        region.clicked.connect(self._open_region)
        actions_layout.addWidget(dismiss)
        actions_layout.addWidget(details)
        actions_layout.addWidget(region)
        card_layout.addWidget(actions)

        backdrop_layout.addWidget(self.card, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(backdrop)

    def _button(self, label: str, icon_text: str, *, primary: bool) -> QPushButton:
        button = QPushButton(f"{icon_text}  {label}")
        button.setObjectName("primaryButton" if primary else "secondaryButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setMinimumHeight(48)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        return button

    def _apply_styles(self) -> None:
        theme = self.theme
        accent = "#f6cf5a"
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#backdrop {{
                background: rgba(8, 10, 16, 0.90);
            }}
            QFrame#card {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.surface_container_high, 0.97)},
                    stop: 0.52 {rgba(theme.surface_container, 0.93)},
                    stop: 1 {rgba(theme.surface, 0.91)}
                );
                border: 1px solid {rgba(accent, 0.30)};
                border-radius: 34px;
            }}
            QFrame#heroIconWrap {{
                background: {rgba(accent, 0.12)};
                border: 1px solid {rgba(accent, 0.26)};
                border-radius: 28px;
                min-width: 92px;
                max-width: 92px;
                min-height: 92px;
                max-height: 92px;
            }}
            QLabel#overline, QLabel#metaLabel {{
                color: {accent};
                letter-spacing: 1.8px;
            }}
            QLabel#title {{
                color: {theme.text};
            }}
            QLabel#headline, QLabel#infoBody {{
                color: {theme.text_muted};
            }}
            QFrame#infoCard {{
                background: {rgba(theme.surface_container_high, 0.84)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 22px;
            }}
            QFrame#tipCard {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(accent, 0.14)},
                    stop: 1 {rgba(theme.surface_container_high, 0.92)}
                );
                border: 1px solid {rgba(accent, 0.24)};
                border-radius: 24px;
            }}
            QLabel#tipBody, QLabel#contactValue {{
                color: {theme.text};
            }}
            QFrame#actionsWrap {{
                background: {rgba(theme.on_surface, 0.04)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 22px;
            }}
            QPushButton#primaryButton, QPushButton#secondaryButton {{
                border-radius: 18px;
                padding: 0 18px;
            }}
            QPushButton#primaryButton {{
                background: {accent};
                color: #101114;
                border: none;
            }}
            QPushButton#primaryButton:hover {{
                background: {blend(accent, theme.primary_container, 0.28)};
            }}
            QPushButton#secondaryButton {{
                background: {rgba(theme.on_surface, 0.05)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                color: {theme.text};
            }}
            QPushButton#secondaryButton:hover {{
                background: {rgba(accent, 0.10)};
                border: 1px solid {rgba(accent, 0.28)};
            }}
            """
        )

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(72)
        shadow.setOffset(0, 24)
        shadow.setColor(QColor(0, 0, 0, 210))
        self.card.setGraphicsEffect(shadow)

    def _register_shortcuts(self) -> None:
        QShortcut(QKeySequence("Escape"), self, activated=self.close)
        QShortcut(QKeySequence("Return"), self, activated=self._open_details)
        QShortcut(QKeySequence("Enter"), self, activated=self._open_details)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(220)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _position_overlay(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        self.setGeometry(screen.geometry())

    def _set_window_identity(self) -> None:
        try:
            wid = int(self.winId())
            subprocess.run(
                ["xprop", "-id", hex(wid), "-f", "_NET_WM_NAME", "8t", "-set", "_NET_WM_NAME", self.windowTitle()],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            subprocess.run(
                ["xprop", "-id", hex(wid), "-f", "WM_CLASS", "8s", "-set", "WM_CLASS", "HanautaCapAlert"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def _apply_i3_window_rules(self) -> None:
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="Hanauta CAP Alert"]',
                    "floating enable, sticky enable, border pixel 0, move position 0 0",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass
        self._position_overlay()

    def _start_sound(self) -> None:
        if DEFAULT_ALERT_SOUND.exists() and shutil.which("paplay"):
            try:
                self._audio_process = subprocess.Popen(
                    ["paplay", "--volume=18000", str(DEFAULT_ALERT_SOUND)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    text=True,
                )
            except Exception:
                self._audio_process = None

    def _open_details(self) -> None:
        command = entry_command(POPUP_SCRIPT)
        if command:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.close()

    def _open_region(self) -> None:
        command = entry_command(SETTINGS_SCRIPT, "--page", "region")
        if command:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fullscreen CAP alert overlay")
    parser.add_argument("--title", default="Weather Alert")
    parser.add_argument("--headline", default="Official alert received.")
    parser.add_argument("--area", default="")
    parser.add_argument("--tip", default="")
    parser.add_argument("--contact", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--icon", default="warning")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta CAP Alert")
    window = CapAlertOverlay(args.title, args.headline, args.area, args.tip, args.contact, args.url, args.icon)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
