#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Native Hanauta notification daemon with Freedesktop DBus support.
"""

from __future__ import annotations

import asyncio
import json
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from dbus_next.aio import MessageBus
from dbus_next.constants import PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method, signal as dbus_signal
from PyQt6.QtCore import QEasingCurve, QObject, QPoint, QPropertyAnimation, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QPixmap
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


from pyqt.shared.runtime import fonts_root, source_root
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family

APP_DIR = source_root()
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

FONTS_DIR = fonts_root()
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-daemon"
HISTORY_FILE = STATE_DIR / "history.json"
CONTROL_FILE = STATE_DIR / "control.json"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

MATERIAL_ICONS = {
    "network-wireless": "\ue63e",
    "wifi": "\ue63e",
    "bluetooth": "\ue1a7",
    "airplane-mode-symbolic": "\ue195",
    "airplanemode_active": "\ue195",
    "night-light": "\uf03d",
    "nightlight": "\uf03d",
    "coffee": "\uefef",
    "caffeine": "\uefef",
}


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


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "")


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, payload) -> None:
    ensure_state_dir()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def is_paused() -> bool:
    state = load_json(CONTROL_FILE, {"paused": False})
    return bool(state.get("paused", False)) if isinstance(state, dict) else False


def append_history(record: dict) -> None:
    history = load_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        history = []
    history.append(record)
    history = history[-80:]
    save_json(HISTORY_FILE, history)


def set_paused(value: bool) -> None:
    save_json(CONTROL_FILE, {"paused": bool(value)})


def load_toast_appearance() -> dict[str, int]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    appearance = payload.get("appearance", {}) if isinstance(payload, dict) else {}
    if not isinstance(appearance, dict):
        appearance = {}
    try:
        max_width = max(260, min(640, int(appearance.get("notification_toast_max_width", 356))))
    except Exception:
        max_width = 356
    try:
        max_height = max(160, min(640, int(appearance.get("notification_toast_max_height", 280))))
    except Exception:
        max_height = 280
    return {"max_width": max_width, "max_height": max_height}


class NotificationBridge(QObject):
    notificationRequested = pyqtSignal(dict)
    closeRequested = pyqtSignal(int)


class NotificationToast(QWidget):
    actionInvoked = pyqtSignal(int, str)
    dismissed = pyqtSignal(int, int)

    def __init__(
        self,
        notification_id: int,
        payload: dict,
        ui_font: str,
        material_font: str,
        theme,
        appearance: dict[str, int],
    ) -> None:
        super().__init__()
        self.notification_id = notification_id
        self.payload = payload
        self.ui_font = ui_font
        self.material_font = material_font
        self.theme = theme
        self.max_width = int(appearance.get("max_width", 356))
        self.max_height = int(appearance.get("max_height", 280))
        self._fade: QPropertyAnimation | None = None
        self._timeout_timer: QTimer | None = None
        self._i3_rules_applied = False

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle(f"Hanauta Notification {notification_id}")
        self.setMinimumWidth(min(320, self.max_width))
        self.setMaximumWidth(self.max_width)
        self.setMaximumHeight(self.max_height)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._start_timeout()
        self._animate_in()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._i3_rules_applied:
            return
        self._i3_rules_applied = True
        QTimer.singleShot(0, self._set_window_identity)
        QTimer.singleShot(120, self._apply_i3_window_rules)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        self.card = QFrame()
        self.card.setObjectName("card")
        root.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.icon_label = QLabel("")
        self.icon_label.setObjectName("iconLabel")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(28, 28)
        self.icon_label.setFont(QFont(self.material_font, 18))
        self._apply_notification_icon(self.payload.get("app_icon", ""))
        top.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        app_name = QLabel(self.payload.get("app_name", "") or "Notification")
        app_name.setObjectName("appLabel")
        app_name.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeButton")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(lambda: self.dismissed.emit(self.notification_id, 2))
        top.addWidget(app_name, 1)
        top.addWidget(close_btn)
        layout.addLayout(top)

        summary = QLabel(self.payload.get("summary", ""))
        summary.setObjectName("summaryLabel")
        summary.setWordWrap(True)
        summary.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        layout.addWidget(summary)

        body = self.payload.get("body", "")
        if body:
            body_label = QLabel(body)
            body_label.setObjectName("bodyLabel")
            body_label.setWordWrap(True)
            body_label.setFont(QFont(self.ui_font, 10))
            body_label.setMaximumHeight(max(56, self.max_height - 136))
            layout.addWidget(body_label)

        self.actions_wrap = QWidget()
        actions_layout = QHBoxLayout(self.actions_wrap)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        for action in self.payload.get("actions", []):
            button = QPushButton(action.get("label", "Action"))
            button.setObjectName("primaryActionButton" if actions_layout.count() == 0 else "secondaryActionButton")
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.clicked.connect(
                lambda _checked=False, action_key=action.get("key", "default"): self._trigger_action(str(action_key))
            )
            actions_layout.addWidget(button)
        if actions_layout.count():
            layout.addWidget(self.actions_wrap)
        else:
            self.actions_wrap.hide()

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
            }}
            QFrame#card {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 22px;
            }}
            QLabel#appLabel {{
                color: {theme.primary};
                letter-spacing: 0.5px;
            }}
            QLabel#iconLabel {{
                color: {theme.primary};
                background: {rgba(theme.surface_container_high, 0.78)};
                border-radius: 14px;
                font-family: "{self.material_font}";
            }}
            QLabel#summaryLabel {{
                color: {theme.text};
            }}
            QLabel#bodyLabel {{
                color: {theme.text_muted};
            }}
            QPushButton#closeButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 15px;
                color: {theme.icon};
                font-size: 16px;
                font-weight: 600;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
            }}
            QPushButton#closeButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#primaryActionButton, QPushButton#secondaryActionButton {{
                min-height: 36px;
                border-radius: 18px;
                padding: 0 16px;
                font-weight: 700;
            }}
            QPushButton#primaryActionButton {{
                background: {theme.primary};
                border: 1px solid {theme.primary};
                color: {theme.active_text};
            }}
            QPushButton#primaryActionButton:hover {{
                background: {theme.primary_container};
                color: {theme.on_primary_container};
            }}
            QPushButton#secondaryActionButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                color: {theme.text};
            }}
            QPushButton#secondaryActionButton:hover {{
                background: {theme.hover_bg};
            }}
            """
        )

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
                ["xprop", "-id", hex(wid), "-f", "WM_CLASS", "8s", "-set", "WM_CLASS", "HanautaNotification"],
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
                    f'[title="^{self.windowTitle()}$"]',
                    "floating enable, sticky enable, border pixel 0",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def _apply_notification_icon(self, icon_spec: str) -> None:
        icon_spec = str(icon_spec or "").strip()
        self.icon_label.clear()
        self.icon_label.setPixmap(QPixmap())
        if not icon_spec:
            self.icon_label.hide()
            return
        path = Path(icon_spec)
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.icon_label.setPixmap(
                    pixmap.scaled(
                        18,
                        18,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.icon_label.show()
                return
        theme_icon = QIcon.fromTheme(icon_spec)
        if not theme_icon.isNull():
            pixmap = theme_icon.pixmap(18, 18)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap)
                self.icon_label.show()
                return
        glyph = material_icon(icon_spec)
        if glyph:
            self.icon_label.setText(glyph)
            self.icon_label.show()
            return
        self.icon_label.hide()

    def update_theme(self, theme) -> None:
        self.theme = theme
        self._apply_styles()

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.card.setGraphicsEffect(shadow)

    def _start_timeout(self) -> None:
        timeout = int(self.payload.get("expire_timeout", 5000))
        if timeout <= 0:
            timeout = 5000
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(lambda: self.dismissed.emit(self.notification_id, 1))
        self._timeout_timer.start(timeout)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _trigger_action(self, action_key: str) -> None:
        self.actionInvoked.emit(self.notification_id, action_key)
        self.dismissed.emit(self.notification_id, 2)


class NotificationInterface(ServiceInterface):
    def __init__(self, daemon: "NotificationDaemon") -> None:
        super().__init__("org.freedesktop.Notifications")
        self.daemon = daemon
        self._next_id = 1

    @method()
    def GetCapabilities(self) -> "as":
        return ["body", "actions", "icon-static", "persistence"]

    @method()
    def GetServerInformation(self) -> "ssss":
        return ("Hanauta Notification Daemon", "Hanauta", "1.0", "1.2")

    @method()
    def Notify(
        self,
        app_name: "s",
        replaces_id: "u",
        app_icon: "s",
        summary: "s",
        body: "s",
        actions: "as",
        hints: "a{sv}",
        expire_timeout: "i",
    ) -> "u":
        notification_id = int(replaces_id) if int(replaces_id) > 0 else self._next_id
        if notification_id == self._next_id:
            self._next_id += 1
        action_pairs = []
        for index in range(0, len(actions), 2):
            key = actions[index]
            label = actions[index + 1] if index + 1 < len(actions) else actions[index]
            action_pairs.append({"key": key, "label": label})
        payload = {
            "id": notification_id,
            "app_name": app_name,
            "app_icon": app_icon,
            "summary": summary,
            "body": body,
            "actions": action_pairs,
            "hints": dict(hints),
            "expire_timeout": int(expire_timeout),
            "timestamp": time.time(),
        }
        append_history(
            {
                "id": notification_id,
                "app_name": app_name,
                "summary": summary,
                "body": body,
                "timestamp": time.time(),
            }
        )
        if not is_paused():
            self.daemon.bridge.notificationRequested.emit(payload)
        return notification_id

    @method()
    def CloseNotification(self, notification_id: "u") -> "":
        self.daemon.bridge.closeRequested.emit(int(notification_id))

    @dbus_signal()
    def ActionInvoked(self, notification_id: "u", action_key: "s") -> "us":
        return [notification_id, action_key]

    @dbus_signal()
    def NotificationClosed(self, notification_id: "u", reason: "u") -> "uu":
        return [notification_id, reason]


class LegacyCompatInterface(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.dunstproject.cmd0")

    @dbus_property(access=PropertyAccess.READWRITE)
    def paused(self) -> "b":
        return is_paused()

    @paused.setter
    def paused(self, value: "b") -> None:
        set_paused(bool(value))

    @dbus_property(access=PropertyAccess.READ)
    def pauseLevel(self) -> "u":
        return 1 if is_paused() else 0

    @dbus_property(access=PropertyAccess.READ)
    def historyLength(self) -> "u":
        history = load_json(HISTORY_FILE, [])
        return len(history) if isinstance(history, list) else 0


class BusThread(threading.Thread):
    def __init__(self, daemon: "NotificationDaemon") -> None:
        super().__init__(daemon=True)
        self.daemon_ref = daemon
        self.loop: asyncio.AbstractEventLoop | None = None
        self.interface: NotificationInterface | None = None
        self.legacy_compat: LegacyCompatInterface | None = None

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run())
        self.loop.run_forever()

    async def _run(self) -> None:
        bus = await MessageBus().connect()
        self.interface = NotificationInterface(self.daemon_ref)
        self.legacy_compat = LegacyCompatInterface()
        bus.export("/org/freedesktop/Notifications", self.interface)
        bus.export("/org/freedesktop/Notifications", self.legacy_compat)
        await bus.request_name("org.freedesktop.Notifications")

    def emit_action(self, notification_id: int, action_key: str) -> None:
        if self.loop is None or self.interface is None:
            return
        self.loop.call_soon_threadsafe(self.interface.ActionInvoked, int(notification_id), str(action_key))

    def emit_closed(self, notification_id: int, reason: int) -> None:
        if self.loop is None or self.interface is None:
            return
        self.loop.call_soon_threadsafe(self.interface.NotificationClosed, int(notification_id), int(reason))


class NotificationDaemon(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.ui_font = detect_font(theme_font_family("ui"), "Inter", "Noto Sans", "DejaVu Sans", "Sans Serif")
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
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.bridge = NotificationBridge()
        self.bridge.notificationRequested.connect(self.show_notification)
        self.bridge.closeRequested.connect(self.close_notification)
        self.toasts: dict[int, NotificationToast] = {}
        self.bus_thread = BusThread(self)
        self.bus_thread.start()

        ensure_state_dir()
        if not CONTROL_FILE.exists():
            save_json(CONTROL_FILE, {"paused": False})
        if not HISTORY_FILE.exists():
            save_json(HISTORY_FILE, [])

        self.theme_timer = QTimer()
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        for toast in self.toasts.values():
            toast.update_theme(self.theme)
        self._reposition_toasts()

    def show_notification(self, payload: dict) -> None:
        notification_id = int(payload.get("id", 0))
        if notification_id in self.toasts:
            old = self.toasts.pop(notification_id)
            old.close()
            old.deleteLater()
        toast = NotificationToast(
            notification_id,
            payload,
            self.ui_font,
            self.material_font,
            self.theme,
            load_toast_appearance(),
        )
        toast.actionInvoked.connect(self._emit_action)
        toast.dismissed.connect(self._toast_dismissed)
        self.toasts[notification_id] = toast
        self._reposition_toasts()
        toast.show()

    def close_notification(self, notification_id: int) -> None:
        self._toast_dismissed(notification_id, 3)

    def _emit_action(self, notification_id: int, action_key: str) -> None:
        self.bus_thread.emit_action(notification_id, action_key)

    def _toast_dismissed(self, notification_id: int, reason: int) -> None:
        toast = self.toasts.pop(notification_id, None)
        if toast is not None:
            toast.close()
            toast.deleteLater()
            self._reposition_toasts()
        self.bus_thread.emit_closed(notification_id, reason)

    def _reposition_toasts(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        right_margin = 16
        y = rect.y() + 56
        for toast in list(self.toasts.values()):
            toast.adjustSize()
            toast.resize(
                min(toast.sizeHint().width(), toast.maximumWidth()),
                min(toast.sizeHint().height(), toast.maximumHeight()),
            )
            x = rect.x() + rect.width() - toast.width() - right_margin
            toast.move(QPoint(x, y))
            y += toast.height() + 10


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    sigint_timer = QTimer()
    sigint_timer.timeout.connect(lambda: None)
    sigint_timer.start(250)
    daemon = NotificationDaemon()
    _ = daemon
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
