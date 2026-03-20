#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from urllib import parse, request


ROOT = Path(__file__).resolve().parents[4]
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
CURRENT_WALLPAPER = Path.home() / ".wallpapers" / "wallpaper.png"
WALLPAPER_SCRIPT = ROOT / "hanauta" / "scripts" / "set_wallpaper.sh"
MATUGEN_SCRIPT = ROOT / "hanauta" / "scripts" / "run_matugen.sh"
MATUGEN_BINARY = ROOT / "bin" / "matugen"
KONACHAN_CACHE_DIR = ROOT / "walls" / "Konachan-cache"
MAX_KONACHAN_CACHE_ITEMS = 20


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


def run_detached(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )


def matugen_available() -> bool:
    return MATUGEN_SCRIPT.exists() and MATUGEN_BINARY.exists() and bool(MATUGEN_BINARY.stat().st_mode & 0o111)


def wallpaper_aware_enabled(settings: dict) -> bool:
    appearance = settings.get("appearance", {})
    if not isinstance(appearance, dict):
        return False
    if bool(appearance.get("use_matugen_palette", False)):
        return True
    return str(appearance.get("theme_choice", "")).strip().lower() == "wallpaper_aware"


def wallpaper_change_notifications_enabled(settings: dict) -> bool:
    appearance = settings.get("appearance", {})
    if not isinstance(appearance, dict):
        return False
    return bool(appearance.get("wallpaper_change_notifications_enabled", False))


def preferred_wallpaper_path(settings: dict) -> Path | None:
    if CURRENT_WALLPAPER.exists() and CURRENT_WALLPAPER.is_file():
        return CURRENT_WALLPAPER.resolve()
    appearance = settings.get("appearance", {})
    if not isinstance(appearance, dict):
        return CURRENT_WALLPAPER if CURRENT_WALLPAPER.exists() else None
    configured = Path(str(appearance.get("wallpaper_path", ""))).expanduser()
    if configured.exists() and configured.is_file():
        return configured
    if CURRENT_WALLPAPER.exists() and CURRENT_WALLPAPER.is_file():
        return CURRENT_WALLPAPER
    return None


def maybe_refresh_matugen(settings: dict, state: dict[str, object]) -> None:
    if not wallpaper_aware_enabled(settings) or not matugen_available():
        state["last_matugen_wallpaper"] = ""
        state["last_matugen_mtime"] = 0.0
        return
    wallpaper = preferred_wallpaper_path(settings)
    if wallpaper is None:
        return
    try:
        mtime = wallpaper.stat().st_mtime
    except OSError:
        return
    last_wallpaper = str(state.get("last_matugen_wallpaper", ""))
    last_mtime = float(state.get("last_matugen_mtime", 0.0) or 0.0)
    current_wallpaper = str(wallpaper.resolve())
    if current_wallpaper == last_wallpaper and abs(mtime - last_mtime) < 0.0001:
        return
    matugen_env = dict(os.environ)
    if not wallpaper_change_notifications_enabled(settings):
        matugen_env["HANAUTA_SUPPRESS_MATUGEN_NOTIFY"] = "1"
    run_detached([str(MATUGEN_SCRIPT), str(wallpaper)], env=matugen_env)
    state["last_matugen_wallpaper"] = current_wallpaper
    state["last_matugen_mtime"] = mtime


def image_paths_for_folder(folder: Path) -> list[Path]:
    suffixes = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    if not folder.exists() or not folder.is_dir():
        return []
    return [
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    ]


def prune_konachan_cache(*, keep: Path | None = None) -> None:
    KONACHAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    keep_path = keep.resolve() if keep is not None and keep.exists() else None
    images = [
        path
        for path in KONACHAN_CACHE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    ]
    if len(images) <= MAX_KONACHAN_CACHE_ITEMS:
        return
    images.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    retained: set[Path] = set(images[:MAX_KONACHAN_CACHE_ITEMS])
    if keep_path is not None:
        retained.add(keep_path)
    for path in images:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in retained:
            continue
        try:
            path.unlink()
        except OSError:
            pass


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
        matugen_env = dict(os.environ)
        if not wallpaper_change_notifications_enabled(settings):
            matugen_env["HANAUTA_SUPPRESS_MATUGEN_NOTIFY"] = "1"
        run_detached([str(MATUGEN_SCRIPT), str(path)], env=matugen_env)
    save_settings_state(settings)
    prune_konachan_cache(keep=path)


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
    state: dict[str, object] = {"last_matugen_wallpaper": "", "last_matugen_mtime": 0.0}
    next_konachan_run = 0.0
    next_local_run = 0.0
    if "--once" in sys.argv:
        return run_once()
    if "--local-once" in sys.argv:
        return run_local_randomizer_once()
    while True:
        settings = load_settings_state()
        maybe_refresh_matugen(settings, state)
        appearance = settings.get("appearance", {})
        if not isinstance(appearance, dict):
            time.sleep(5)
            continue
        now = time.monotonic()
        provider = str(appearance.get("wallpaper_provider", "")).strip().lower()
        enabled = bool(appearance.get("konachan_enabled", False))
        interval = max(120, int(appearance.get("konachan_interval_seconds", 120) or 120))
        if provider == "konachan" and enabled and now >= next_konachan_run:
            run_once()
            next_konachan_run = now + interval
        local_enabled = bool(appearance.get("local_randomizer_enabled", False))
        local_interval = max(120, int(appearance.get("local_randomizer_interval_seconds", 120) or 120))
        if provider and provider != "konachan" and local_enabled and now >= next_local_run:
            run_local_randomizer_once()
            next_local_run = now + local_interval
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
