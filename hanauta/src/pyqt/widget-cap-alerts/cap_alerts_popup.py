#!/usr/bin/env python3
from __future__ import annotations

import signal
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QDesktopServices, QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.button_helpers import create_close_button
from pyqt.shared.cap_alerts import CapAlert, configured_alert_location, fallback_tip, fetch_active_alerts, relative_expiry, test_mode_enabled
from pyqt.shared.runtime import entry_command
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.weather import AnimatedWeatherIcon, animated_icon_path


SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
MATERIAL_ICONS = {
    "warning": "\ue002",
    "settings": "\ue8b8",
    "close": "\ue5cd",
    "open_in_new": "\ue89e",
    "call": "\ue0b0",
}


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
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


class AlertWorker(QThread):
    loaded = pyqtSignal(object, object)
    failed = pyqtSignal(str)

    def run(self) -> None:
        location = configured_alert_location()
        if location is None and not test_mode_enabled():
            self.failed.emit("Choose a shared location in Region settings first.")
            return
        alerts = fetch_active_alerts(location)
        self.loaded.emit(location, alerts)


class AlertCard(QFrame):
    def __init__(self, alert: CapAlert, ui_font: str, display_font: str) -> None:
        super().__init__()
        self.alert = alert
        self.ui_font = ui_font
        self.display_font = display_font
        self.setObjectName("alertCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        icon = AnimatedWeatherIcon(24)
        icon.set_icon_path(animated_icon_path(alert.icon_name))
        top.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        event = QLabel(alert.event)
        event.setObjectName("alertEvent")
        event.setFont(QFont(display_font, 15, QFont.Weight.DemiBold))
        headline = QLabel(alert.headline)
        headline.setObjectName("alertHeadline")
        headline.setWordWrap(True)
        headline.setFont(QFont(ui_font, 10, QFont.Weight.Medium))
        title_col.addWidget(event)
        title_col.addWidget(headline)
        top.addLayout(title_col, 1)
        layout.addLayout(top)

        meta = QLabel(f"{alert.severity} • {alert.urgency} • {relative_expiry(alert)}")
        meta.setObjectName("alertMeta")
        meta.setFont(QFont(ui_font, 9, QFont.Weight.DemiBold))
        layout.addWidget(meta)

        area = QLabel(alert.area_desc or "Affected area unavailable.")
        area.setObjectName("alertBody")
        area.setWordWrap(True)
        area.setFont(QFont(ui_font, 10))
        layout.addWidget(area)

        tip_text = alert.instruction or fallback_tip(alert)
        tip = QLabel(tip_text)
        tip.setObjectName("alertTip")
        tip.setWordWrap(True)
        tip.setFont(QFont(ui_font, 10))
        layout.addWidget(tip)

        contacts = QLabel(
            "\n".join(
                [
                    f"Source: {alert.sender_name}",
                    f"Emergency: {alert.contact_number or 'Official local emergency services'}",
                    f"Official bulletin: {alert.web or 'https://www.weather.gov/alerts'}",
                ]
            )
        )
        contacts.setObjectName("alertContacts")
        contacts.setWordWrap(True)
        contacts.setFont(QFont(ui_font, 9))
        layout.addWidget(contacts)

        actions = QHBoxLayout()
        actions.addStretch(1)
        open_button = QPushButton(f"{material_icon('open_in_new')} Open official alert")
        open_button.setObjectName("alertButton")
        open_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_button.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        open_button.clicked.connect(self._open_link)
        actions.addWidget(open_button)
        layout.addLayout(actions)

    def _open_link(self) -> None:
        target = self.alert.web or "https://www.weather.gov/alerts"
        QDesktopServices.openUrl(QUrl(target))


class CapAlertsPopup(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.material_font = self.icon_font
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._fade: QPropertyAnimation | None = None
        self.worker: AlertWorker | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("Hanauta CAP Alerts")
        self.setFixedSize(480, 620)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self.refresh_alerts()

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
        header.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        eyebrow = QLabel("CAP ALERTS")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.title_label = QLabel("Official local alerts")
        self.title_label.setObjectName("title")
        self.title_label.setFont(QFont(self.display_font, 22, QFont.Weight.DemiBold))
        self.subtitle = QLabel("Helpful info, contacts, and official alert guidance.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setFont(QFont(self.ui_font, 9))
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.settings_button = QPushButton(material_icon("settings"))
        self.settings_button.setObjectName("iconButton")
        self.settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.settings_button.setFont(QFont(self.icon_font, 18))
        self.settings_button.clicked.connect(self._open_region_settings)
        self.close_button = create_close_button(material_icon("close"), self.material_font)
        self.close_button.clicked.connect(self.close)
        actions.addWidget(self.settings_button)
        actions.addWidget(self.close_button)
        header.addLayout(actions)
        layout.addLayout(header)

        self.status_label = QLabel("Loading official alerts…")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll, 1)

    def _clear_cards(self) -> None:
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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
        self.move(available.x() + available.width() - self.width() - 56, available.y() + 80)

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
        yellow = "#F6C945"
        yellow_soft = "rgba(246,201,69,0.18)"
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#panel {{
                background: {rgba(theme.surface_container, 0.95)};
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 30px;
            }}
            QLabel#eyebrow {{
                color: {yellow};
                letter-spacing: 1.8px;
            }}
            QLabel#subtitle, QLabel#status, QLabel#alertBody, QLabel#alertContacts {{
                color: {theme.text_muted};
            }}
            QFrame#alertCard {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 24px;
            }}
            QLabel#alertMeta {{
                color: {yellow};
            }}
            QLabel#alertTip {{
                color: {theme.text};
                background: {yellow_soft};
                border: 1px solid rgba(246,201,69,0.22);
                border-radius: 16px;
                padding: 10px 12px;
            }}
            QPushButton#iconButton {{
                background: {rgba(theme.surface_container_high, 0.90)};
                color: {theme.primary};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 19px;
            }}
            QPushButton#alertButton {{
                background: rgba(246,201,69,0.92);
                color: #101114;
                border: none;
                border-radius: 16px;
                padding: 8px 12px;
            }}
            QScrollArea#scroll {{
                background: transparent;
                border: none;
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

    def refresh_alerts(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self._clear_cards()
        self.status_label.setText("Loading official alerts…")
        self.worker = AlertWorker()
        self.worker.loaded.connect(self._populate_alerts)
        self.worker.failed.connect(self._show_error)
        self.worker.finished.connect(self._finish_worker)
        self.worker.start()

    def _populate_alerts(self, location_obj: object, alerts_obj: object) -> None:
        location = location_obj
        alerts = alerts_obj
        demo = test_mode_enabled()
        label = location.label if hasattr(location, "label") else ("demo mode" if demo else "your saved location")
        if not isinstance(alerts, list) or not alerts:
            self.title_label.setText("No active official alerts")
            self.status_label.setText(
                "Demo mode is enabled but no sample alerts were generated."
                if demo
                else f"No active NWS alerts for {label}."
            )
            return
        self.title_label.setText(f"{len(alerts)} active alert(s)")
        self.status_label.setText(
            "Demo mode is enabled. These are sample alerts from random countries for UI testing."
            if demo
            else f"Official alerts affecting {label}."
        )
        for alert in alerts:
            if isinstance(alert, CapAlert):
                self.content_layout.insertWidget(self.content_layout.count() - 1, AlertCard(alert, self.ui_font, self.display_font))

    def _show_error(self, message: str) -> None:
        self.title_label.setText("Alerts unavailable")
        self.status_label.setText(message)

    def _finish_worker(self) -> None:
        self.worker = None

    def _open_region_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        command = entry_command(SETTINGS_PAGE_SCRIPT, "--page", "region")
        if command:
            from PyQt6.QtCore import QProcess
            QProcess.startDetached(command[0], command[1:])


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    widget = CapAlertsPopup()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
