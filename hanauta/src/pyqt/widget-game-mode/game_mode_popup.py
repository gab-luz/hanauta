#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command
from pyqt.shared.gamemode import service_enabled, set_active, summary
from pyqt.shared.theme import load_theme_palette, rgba
from pyqt.shared.button_helpers import create_close_button


MATERIAL_ICONS = {
    "sports_esports": "\uea28",
    "settings": "\ue8b8",
    "close": "\ue5cd",
    "speed": "\ue9e4",
    "blur_off": "\ue3a4",
    "check_circle": "\ue86c",
    "pause_circle": "\ue1a2",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def load_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
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


def run_bg(cmd: list[str]) -> None:
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def apply_antialias_font(widget: QWidget) -> None:
    font = widget.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child_font = child.font()
        child_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        child.setFont(child_font)


class MetricCard(QFrame):
    def __init__(
        self,
        icon_text: str,
        title_text: str,
        value_text: str,
        icon_font: str,
        ui_font: str,
        display_font: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)

        icon = QLabel(icon_text)
        icon.setObjectName("metricIcon")
        icon.setFont(QFont(icon_font, 16))
        icon.setProperty("iconRole", True)
        layout.addWidget(icon)

        title = QLabel(title_text)
        title.setObjectName("metricTitle")
        title.setFont(QFont(ui_font, 9))
        layout.addWidget(title)

        self.value_label = QLabel(value_text)
        self.value_label.setObjectName("metricValue")
        self.value_label.setFont(QFont(display_font, 12, QFont.Weight.DemiBold))
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)
        layout.addStretch(1)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


class GameModePopup(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.fonts = load_fonts()
        self.theme = load_theme_palette()
        self.ui_font = detect_font("Inter", self.fonts.get("ui_sans", ""), "Sans Serif")
        self.display_font = detect_font("Outfit", self.fonts.get("ui_display", ""), self.ui_font)
        self.icon_font = detect_font(
            self.fonts.get("material_icons", ""),
            self.fonts.get("material_symbols_rounded", ""),
            "Material Icons",
        )
        self.setWindowTitle("Hanauta Game Mode")
        self.setObjectName("gameModePopup")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(420, 320)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(44)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(10, 8, 14, 170))
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        shell = QFrame()
        shell.setObjectName("shell")
        outer.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)
        icon = QLabel(material_icon("sports_esports"))
        icon.setFont(QFont(self.icon_font, 20))
        icon.setProperty("iconRole", True)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)
        title = QLabel("Game Mode")
        title.setObjectName("titleLabel")
        title.setFont(QFont(self.display_font, 15, QFont.Weight.DemiBold))
        subtitle = QLabel("Low-latency session profile for when you just want the desktop to get out of the way.")
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setObjectName("subtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        close_btn = create_close_button(material_icon("close"), self.icon_font, font_size=16)
        close_btn.setProperty("iconButton", True)
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self.close)
        header.addWidget(icon)
        header.addLayout(title_wrap, 1)
        header.addWidget(close_btn)
        layout.addLayout(header)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(10)

        self.status_pill = QLabel("")
        self.status_pill.setObjectName("statusPill")
        self.status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_pill.setMinimumHeight(36)
        hero_layout.addWidget(self.status_pill, 0, Qt.AlignmentFlag.AlignLeft)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("infoLabel")
        hero_layout.addWidget(self.info_label)
        layout.addWidget(hero)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self.service_metric = MetricCard(
            material_icon("speed"),
            "Service",
            "Waiting",
            self.icon_font,
            self.ui_font,
            self.display_font,
        )
        self.visual_metric = MetricCard(
            material_icon("blur_off"),
            "Desktop effects",
            "Restored",
            self.icon_font,
            self.ui_font,
            self.display_font,
        )
        metrics.addWidget(self.service_metric, 1)
        metrics.addWidget(self.visual_metric, 1)
        layout.addLayout(metrics)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.toggle_button = QPushButton("Enable")
        self.toggle_button.setObjectName("primaryButton")
        self.toggle_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_button.setMinimumHeight(42)
        self.toggle_button.clicked.connect(self._toggle)
        settings_button = QPushButton("Settings")
        settings_button.setObjectName("secondaryButton")
        settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        settings_button.setMinimumHeight(42)
        settings_button.clicked.connect(self._open_settings)
        actions.addWidget(self.toggle_button)
        actions.addWidget(settings_button)
        layout.addLayout(actions)

        self._apply_styles()
        apply_antialias_font(self)
        self._refresh()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        app = QApplication.instance()
        if app is not None:
            app.quit()
        super().closeEvent(event)

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget#gameModePopup {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#shell {{
                background: {rgba(theme.surface_container, 0.95)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 24px;
            }}
            QFrame#heroCard {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.primary, 0.16)},
                    stop: 0.5 {rgba(theme.secondary, 0.12)},
                    stop: 1 {rgba(theme.surface_container_high, 0.92)}
                );
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 20px;
            }}
            QFrame#metricCard {{
                background: {rgba(theme.surface_container_high, 0.84)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 18px;
            }}
            QLabel[iconRole="true"] {{
                color: {theme.primary};
                font-family: "{self.icon_font}";
            }}
            QLabel#titleLabel {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#infoLabel {{
                color: {theme.text_muted};
            }}
            QLabel#statusPill {{
                border-radius: 14px;
                background: {rgba(theme.surface, 0.72)};
                border: 1px solid {rgba(theme.primary, 0.22)};
                color: {theme.text};
                padding: 8px 14px;
                font-weight: 600;
            }}
            QLabel#metricTitle {{
                color: {theme.text_muted};
            }}
            QLabel#metricValue {{
                color: {theme.text};
            }}
            QPushButton#primaryButton, QPushButton#secondaryButton, QPushButton[iconButton="true"] {{
                border-radius: 16px;
                padding: 10px 16px;
                border: 1px solid {rgba(theme.outline, 0.16)};
            }}
            QPushButton[iconButton="true"] {{
                font-family: "{self.icon_font}";
                font-size: 16px;
                padding: 0px;
            }}
            QPushButton#primaryButton {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {theme.primary},
                    stop: 1 {theme.secondary}
                );
                color: {theme.active_text};
            }}
            QPushButton#secondaryButton, QPushButton[iconButton="true"] {{
                background: {rgba(theme.surface_container_high, 0.92)};
                color: {theme.text};
            }}
            QPushButton#primaryButton:hover {{
                background: {rgba(theme.primary, 0.92)};
            }}
            QPushButton#secondaryButton:hover, QPushButton[iconButton="true"]:hover {{
                background: {theme.hover_bg};
            }}
            """
        )

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 28, 28)

    def _refresh(self) -> None:
        current = summary()
        active = bool(current["active"])
        available = bool(current["available"])
        enabled = bool(current["enabled"])
        visuals_suppressed = bool(current.get("visuals_suppressed", False))
        if not enabled and not service_enabled():
            self.info_label.setText("Enable Game Mode in Hanauta Settings first.")
            self.toggle_button.setEnabled(False)
            self.status_pill.setText("Disabled in Hanauta")
            self.service_metric.set_value("Blocked")
            self.visual_metric.set_value("Unchanged")
            return
        self.toggle_button.setEnabled(available)
        self.toggle_button.setText("Disable" if active else "Enable")
        self.status_pill.setText("Live session active" if active else "Standing by")
        self.info_label.setText(str(current["note"]))
        self.service_metric.set_value("Running" if active else "Idle")
        self.visual_metric.set_value("Suppressed" if visuals_suppressed else "Restored")

    def _toggle(self) -> None:
        current = summary()
        ok, message = set_active(not bool(current["active"]))
        self.info_label.setText(message)
        self._refresh()
        if ok:
            QTimer.singleShot(1200, self._refresh)

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        command = entry_command(SETTINGS_PAGE_SCRIPT, "--page", "services", "--service-section", "game_mode")
        if command:
            run_bg(command)


def main() -> int:
    if not service_enabled():
        return 0
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    widget = GameModePopup()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
