from __future__ import annotations

import hashlib
from pathlib import Path


THUMB_CACHE_DIR = Path.home() / ".local" / "state" / "hanauta" / "wallpaper-thumbs"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def image_paths_for_folder(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(
        (
            path
            for path in folder.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ),
        key=lambda path: path.name.lower(),
    )


def thumbnail_key(path: Path) -> str:
    resolved = path.expanduser().resolve()
    stat = resolved.stat()
    payload = f"{resolved}|{stat.st_mtime_ns}|{stat.st_size}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def thumbnail_path_for(path: Path) -> Path:
    return THUMB_CACHE_DIR / f"{thumbnail_key(path)}.jpg"
