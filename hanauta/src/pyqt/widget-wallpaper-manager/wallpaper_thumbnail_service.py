#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage, QImageReader, QPainter


APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.wallpaper_thumbs import THUMB_CACHE_DIR, image_paths_for_folder, thumbnail_path_for


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
TARGET_SIZE = QSize(360, 220)


def load_settings_state() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    appearance = payload.get("appearance", {})
    if not isinstance(appearance, dict):
        appearance = {}
    payload["appearance"] = appearance
    return payload


def current_folder_from_settings() -> Path | None:
    settings = load_settings_state()
    appearance = settings.get("appearance", {})
    if not isinstance(appearance, dict):
        return None
    provider = str(appearance.get("wallpaper_provider", "")).strip().lower()
    if provider in {"", "konachan"}:
        return None
    folder = str(appearance.get("slideshow_folder", "")).strip()
    if not folder:
        return None
    path = Path(folder).expanduser()
    if not path.exists() or not path.is_dir():
        return None
    return path


def ensure_thumbnail(source: Path) -> None:
    target = thumbnail_path_for(source)
    if target.exists():
        return
    THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    reader = QImageReader(str(source))
    if not reader.canRead():
        return
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        scaled = size.scaled(TARGET_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(scaled)
    image = reader.read()
    if image.isNull():
        return
    if image.hasAlphaChannel():
        flattened = QImage(image.size(), QImage.Format.Format_RGB32)
        flattened.fill(0x101114)
        painter = QPainter(flattened)
        painter.drawImage(0, 0, image)
        painter.end()
        image = flattened
    image.save(str(target), "JPEG", quality=74)


def process_folder(folder: Path) -> int:
    count = 0
    for image_path in image_paths_for_folder(folder):
        ensure_thumbnail(image_path)
        count += 1
    return count


def main() -> int:
    if "--folder" in sys.argv:
        try:
            index = sys.argv.index("--folder")
            folder = Path(sys.argv[index + 1]).expanduser()
        except Exception:
            return 2
        if not folder.exists() or not folder.is_dir():
            return 1
        process_folder(folder)
        return 0
    if "--once" in sys.argv:
        folder = current_folder_from_settings()
        if folder is None:
            return 0
        process_folder(folder)
        return 0

    last_folder = ""
    while True:
        folder = current_folder_from_settings()
        current = str(folder) if folder is not None else ""
        if current and current != last_folder:
            process_folder(folder)
            last_folder = current
        elif current:
            process_folder(folder)
        time.sleep(600)


if __name__ == "__main__":
    raise SystemExit(main())
