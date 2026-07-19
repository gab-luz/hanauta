#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt6 notification center powered by QML frontend and QObject backend.
"""

from __future__ import annotations

import logging
import signal
import sys

from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine

from notif_center.settings_io import load_notification_settings
from notif_center.qml_backend import NotificationCenterBackend

APP_DIR = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.app_logging import init_app_logging


QML_FILE = __import__("pathlib").Path(__file__).resolve().parent / "notification_center.qml"


def main() -> int:
    init_app_logging("notification_center")
    logging.info("notification-center main starting")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Hanauta Notification Center")

    signal.signal(signal.SIGINT, lambda sig, frame: app.quit())
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    backend = NotificationCenterBackend()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(QML_FILE)))

    if not engine.rootObjects():
        logging.error("Failed to load QML file: %s", QML_FILE)
        return 1

    root = engine.rootObjects()[0]
    screen = app.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        nc_cfg = load_notification_settings().get("notification_center", {})
        nc_width = nc_cfg.get("width", 800)
        nc_height = nc_cfg.get("height", 740)
        root.setWidth(nc_width)
        root.setHeight(min(nc_height, geo.height() - 72))
        root.setPosition(geo.center().x() - root.width() // 2, geo.y() + 28)

    root.show()
    logging.info("notification-center shown; entering event loop")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
