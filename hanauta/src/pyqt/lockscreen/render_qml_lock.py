#!/usr/bin/env python3
import argparse
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Hanauta QML lockscreen to a PNG.")
    parser.add_argument(
        "--qml",
        default=str(Path(__file__).with_name("Lockscreen.qml")),
        help="Path to Lockscreen.qml",
    )
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--out", required=True, help="Output PNG path")
    args = parser.parse_args()

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtQuick import QQuickView

    app = QGuiApplication([])
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(os.path.abspath(args.qml)))
    view.resize(args.width, args.height)
    view.show()
    app.processEvents()

    image = view.grabWindow()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(out_path), "PNG"):
        raise SystemExit("Failed to save rendered PNG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

