#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from pathlib import Path
from urllib import parse, request


ROOT = Path(__file__).resolve().parents[3]
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
WALLPAPER_SCRIPT = ROOT / "scripts" / "set_wallpaper.sh"
MATUGEN_SCRIPT = ROOT / "scripts" / "run_matugen.sh"
MATUGEN_BINARY = ROOT / "bin" / "matugen"
KONACHAN_CACHE_DIR = ROOT / "walls" / "Konachan-cache"


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
    appearance.setdefault("wallpaper_provider", "")
    appearance.setdefault("wallpaper_provider_initialized", False)
    appearance.setdefault("konachan_enabled", False)
    appearance.setdefault("konachan_interval_seconds", 120)
    appearance.setdefault("konachan_tags", "rating:safe")
    appearance.setdefault("local_randomizer_enabled", False)
    appearance.setdefault("local_randomizer_interval_seconds", 120)
    payload["appearance"] = appearance
    return payload


def save_settings_state(payload: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_detached(command: list[str]) -> None:
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def matugen_available() -> bool:
    return MATUGEN_SCRIPT.exists() and MATUGEN_BINARY.exists() and bool(MATUGEN_BINARY.stat().st_mode & 0o111)


def image_paths_for_folder(folder: Path) -> list[Path]:
    suffixes = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    if not folder.exists() or not folder.is_dir():
        return []
    return [
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    ]


def build_request(tags: str) -> request.Request:
    chosen_page = random.randint(1, 80)
    query = parse.urlencode(
        {
            "limit": 24,
            "page": chosen_page,
            "tags": tags or "rating:safe",
        }
    )
    return request.Request(
        f"https://konachan.net/post.json?{query}",
        headers={
            "User-Agent": "Mozilla/5.0 HanautaWallpaperManager/1.0",
            "Accept": "application/json",
        },
    )


def fetch_konachan_wallpaper(tags: str) -> Path | None:
    KONACHAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for _ in range(5):
        try:
            with request.urlopen(build_request(tags), timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(payload, list) or not payload:
            continue
        candidates = [
            item
            for item in payload
            if isinstance(item, dict)
            and str(item.get("file_url", "")).startswith("http")
            and int(item.get("width", 0) or 0) >= 1600
            and int(item.get("height", 0) or 0) >= 900
        ]
        if not candidates:
            continue
        chosen = random.choice(candidates)
        file_url = str(chosen.get("file_url", "")).strip()
        if not file_url:
            continue
        suffix = Path(parse.urlparse(file_url).path).suffix.lower() or ".jpg"
        target = KONACHAN_CACHE_DIR / f"konachan-{chosen.get('id', 'wallpaper')}{suffix}"
        if target.exists():
            return target
        try:
            wallpaper_request = request.Request(file_url, headers={"User-Agent": "Mozilla/5.0 HanautaWallpaperManager/1.0"})
            with request.urlopen(wallpaper_request, timeout=60) as response:
                target.write_bytes(response.read())
            return target
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
    return None


def apply_wallpaper(path: Path, settings: dict) -> None:
    if not path.exists() or not path.is_file():
        return
    if WALLPAPER_SCRIPT.exists():
        run_detached([str(WALLPAPER_SCRIPT), str(path)])
    else:
        run_detached(["feh", "--bg-fill", str(path)])
    appearance = settings.setdefault("appearance", {})
    if not isinstance(appearance, dict):
        appearance = {}
        settings["appearance"] = appearance
    appearance["wallpaper_provider"] = "konachan"
    appearance["wallpaper_provider_initialized"] = True
    appearance["konachan_enabled"] = True
    appearance["wallpaper_path"] = str(path)
    appearance["slideshow_folder"] = str(KONACHAN_CACHE_DIR)
    appearance["wallpaper_mode"] = "picture"
    appearance["slideshow_enabled"] = False
    if matugen_available():
        appearance["use_matugen_palette"] = True
        appearance["theme_choice"] = "wallpaper_aware"
        run_detached([str(MATUGEN_SCRIPT), str(path)])
    save_settings_state(settings)


def run_once() -> int:
    settings = load_settings_state()
    appearance = settings.get("appearance", {})
    if not isinstance(appearance, dict):
        return 0
    if str(appearance.get("wallpaper_provider", "")).strip().lower() != "konachan":
        return 0
    if not bool(appearance.get("konachan_enabled", False)):
        return 0
    path = fetch_konachan_wallpaper(str(appearance.get("konachan_tags", "rating:safe")))
    if path is None:
        return 1
    apply_wallpaper(path, settings)
    return 0


def run_local_randomizer_once() -> int:
    settings = load_settings_state()
    appearance = settings.get("appearance", {})
    if not isinstance(appearance, dict):
        return 0
    provider = str(appearance.get("wallpaper_provider", "")).strip().lower()
    if provider in {"", "konachan"}:
        return 0
    if not bool(appearance.get("local_randomizer_enabled", False)):
        return 0
    folder = Path(str(appearance.get("slideshow_folder", ""))).expanduser()
    images = image_paths_for_folder(folder)
    if not images:
        return 1
    current = str(appearance.get("wallpaper_path", "")).strip()
    candidates = [path for path in images if str(path) != current]
    if not candidates:
        candidates = images
    chosen = random.choice(candidates)
    apply_wallpaper(chosen, settings)
    return 0


def main() -> int:
    if "--once" in sys.argv:
        return run_once()
    if "--local-once" in sys.argv:
        return run_local_randomizer_once()
    while True:
        settings = load_settings_state()
        appearance = settings.get("appearance", {})
        if not isinstance(appearance, dict):
            time.sleep(60)
            continue
        provider = str(appearance.get("wallpaper_provider", "")).strip().lower()
        enabled = bool(appearance.get("konachan_enabled", False))
        interval = max(120, int(appearance.get("konachan_interval_seconds", 120) or 120))
        if provider == "konachan" and enabled:
            run_once()
            time.sleep(interval)
            continue
        local_enabled = bool(appearance.get("local_randomizer_enabled", False))
        local_interval = max(120, int(appearance.get("local_randomizer_interval_seconds", 120) or 120))
        if provider and provider != "konachan" and local_enabled:
            run_local_randomizer_once()
            time.sleep(local_interval)
            continue
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
