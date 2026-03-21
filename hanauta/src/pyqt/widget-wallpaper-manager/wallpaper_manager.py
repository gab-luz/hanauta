#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import signal
import subprocess
import sys
from pathlib import Path
from urllib import parse, request
import zipfile

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QApplication, QFileDialog


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
CURRENT_WALLPAPER = Path.home() / ".wallpapers" / "wallpaper.png"
WALLPAPER_SCRIPT = ROOT / "hanauta" / "scripts" / "set_wallpaper.sh"
MATUGEN_SCRIPT = ROOT / "hanauta" / "scripts" / "run_matugen.sh"
MATUGEN_BINARY = ROOT / "bin" / "matugen"
WALLPAPER_CACHE_BINARY = ROOT / "hanauta" / "bin" / "hanauta-wallcache"
QML_FILE = Path(__file__).resolve().with_suffix(".qml")
DEFAULT_WALLPAPER_FOLDER = ROOT / "hanauta" / "walls"
KONACHAN_CACHE_DIR = DEFAULT_WALLPAPER_FOLDER / "Konachan-cache"
MAX_KONACHAN_CACHE_ITEMS = 20
KONACHAN_PROVIDER_DAEMON = Path(__file__).resolve().with_name("wallpaper_provider_daemon.py")
WALLPAPER_THUMBNAIL_SERVICE = Path(__file__).resolve().with_name("wallpaper_thumbnail_service.py")
WALLPAPER_INDEX_CACHE = Path.home() / ".local" / "state" / "hanauta" / "service" / "wallpaper-index.json"
KONACHAN_USER_AGENT = "Mozilla/5.0 HanautaWallpaperManager/1.0"

PROVIDER_META: dict[str, dict[str, str]] = {
    "d3ext": {
        "key": "d3ext",
        "title": "D3Ext Aesthetic",
        "subtitle": "Retro, moody and polished aesthetic packs from D3Ext.",
        "folder": str(DEFAULT_WALLPAPER_FOLDER / "D3Ext-aesthetic-wallpapers"),
        "repo": "https://github.com/D3Ext/aesthetic-wallpapers.git",
        "mode": "static",
        "cta": "Download pack",
    },
    "jakoolit": {
        "key": "jakoolit",
        "title": "JaKooLit Bank",
        "subtitle": "Large mixed wallpaper bank built around desktop setups.",
        "folder": str(DEFAULT_WALLPAPER_FOLDER / "JaKooLit-Wallpaper-Bank"),
        "repo": "https://github.com/JaKooLit/Wallpaper-Bank.git",
        "mode": "static",
        "cta": "Download pack",
    },
    "catholic": {
        "key": "catholic",
        "title": "Catholic Hyprland Pack",
        "subtitle": "Catholic-themed wallpaper pack imported from the Hyprland community repo.",
        "folder": str(DEFAULT_WALLPAPER_FOLDER / "catholic-wallpapers-for-hyprland"),
        "repo": "https://github.com/ZZ-Frater/catholic-wallpapers-for-hyprland.git",
        "mode": "static",
        "cta": "Download pack",
        "archives": "catholic-wallpapers-for-hyprland.zip",
    },
    "konachan": {
        "key": "konachan",
        "title": "Konachan Stream",
        "subtitle": "Safe-rated online provider that refreshes every 2 minutes.",
        "folder": str(KONACHAN_CACHE_DIR),
        "repo": "",
        "mode": "dynamic",
        "cta": "Enable live feed",
    },
    "custom": {
        "key": "custom",
        "title": "Custom Folder",
        "subtitle": "Use your own folder and keep the fullscreen browser flow.",
        "folder": "",
        "repo": "",
        "mode": "custom",
        "cta": "Choose folder",
    },
}

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import python_executable
from pyqt.shared.theme import blend, load_theme_palette, rgba
from pyqt.shared.wallpaper_thumbs import image_paths_for_folder, thumbnail_path_for


def load_settings_state() -> dict:
    defaults = {
        "appearance": {
            "wallpaper_mode": "picture",
            "wallpaper_path": str(CURRENT_WALLPAPER),
            "slideshow_folder": str(DEFAULT_WALLPAPER_FOLDER),
            "slideshow_enabled": False,
            "theme_choice": "dark",
            "use_matugen_palette": False,
            "wallpaper_change_notifications_enabled": False,
            "wallpaper_provider": "",
            "wallpaper_provider_initialized": False,
            "konachan_enabled": False,
            "konachan_interval_seconds": 120,
            "konachan_tags": "rating:safe",
            "local_randomizer_enabled": False,
            "local_randomizer_interval_seconds": 120,
        }
    }
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    appearance = payload.get("appearance", {})
    if not isinstance(appearance, dict):
        appearance = {}
    merged_appearance = dict(defaults["appearance"])
    merged_appearance.update(appearance)
    payload["appearance"] = merged_appearance
    return payload


def save_settings_state(payload: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def file_url(path: Path) -> str:
    return QUrl.fromLocalFile(str(path)).toString()


def load_wallpaper_index_cache() -> dict:
    try:
        payload = json.loads(WALLPAPER_INDEX_CACHE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        return {}
    folders = payload.get("folders", {})
    return payload if isinstance(folders, dict) else {}


def run_detached(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )


def build_konachan_request(tags: str, *, limit: int = 24) -> request.Request:
    chosen_page = random.randint(1, 80)
    query = parse.urlencode(
        {
            "limit": limit,
            "page": chosen_page,
            "tags": tags or "rating:safe",
        }
    )
    return request.Request(
        f"https://konachan.net/post.json?{query}",
        headers={
            "User-Agent": KONACHAN_USER_AGENT,
            "Accept": "application/json",
        },
    )


def fetch_konachan_candidates(tags: str, *, limit: int = 10) -> list[dict[str, str]]:
    for _ in range(4):
        try:
            with request.urlopen(build_konachan_request(tags), timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(payload, list) or not payload:
            continue
        candidates: list[dict[str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            file_url = str(item.get("file_url", "")).strip()
            preview_url = (
                str(item.get("sample_url", "")).strip()
                or str(item.get("jpeg_url", "")).strip()
                or str(item.get("preview_url", "")).strip()
                or file_url
            )
            if not file_url.startswith("http") or not preview_url.startswith("http"):
                continue
            if int(item.get("width", 0) or 0) < 1280 or int(item.get("height", 0) or 0) < 720:
                continue
            post_id = str(item.get("id", "wallpaper")).strip() or "wallpaper"
            candidates.append(
                {
                    "id": post_id,
                    "name": f"Konachan #{post_id}",
                    "fileUrl": file_url,
                    "previewUrl": preview_url,
                    "detail": f"{int(item.get('width', 0) or 0)}x{int(item.get('height', 0) or 0)}",
                }
            )
        if candidates:
            random.shuffle(candidates)
            return candidates[:limit]
    return []


def download_konachan_candidate(candidate: dict[str, str]) -> Path | None:
    file_url = str(candidate.get("fileUrl", "")).strip()
    if not file_url:
        return None
    KONACHAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(parse.urlparse(file_url).path).suffix.lower() or ".jpg"
    target = KONACHAN_CACHE_DIR / f"konachan-{str(candidate.get('id', 'wallpaper')).strip() or 'wallpaper'}{suffix}"
    if target.exists():
        return target
    try:
        wallpaper_request = request.Request(file_url, headers={"User-Agent": KONACHAN_USER_AGENT})
        with request.urlopen(wallpaper_request, timeout=60) as response:
            target.write_bytes(response.read())
        return target
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
    return None


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


class Backend(QObject):
    wallpapersChanged = pyqtSignal()
    currentIndexChanged = pyqtSignal()
    currentFolderChanged = pyqtSignal()
    statusChanged = pyqtSignal()
    needsFolderSelectionChanged = pyqtSignal()
    backgroundSourceChanged = pyqtSignal()
    matugenAvailableChanged = pyqtSignal()
    selectedWallpaperChanged = pyqtSignal()
    pinnedSelectionChanged = pyqtSignal()
    providersChanged = pyqtSignal()
    providerChanged = pyqtSignal()
    providerSelectionRequiredChanged = pyqtSignal()
    busyChanged = pyqtSignal()
    randomizerChanged = pyqtSignal()
    konachanTagsChanged = pyqtSignal()
    konachanCandidatesChanged = pyqtSignal()
    konachanCurrentChanged = pyqtSignal()
    closeRequested = pyqtSignal()
    notify = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._settings = load_settings_state()
        self._wallpapers: list[dict[str, object]] = []
        self._konachan_candidates: list[dict[str, str]] = []
        self._konachan_current = -1
        self._current_index = 0
        self._pinned_index = -1
        self._status = "Choose your wallpaper pack to start building the library."
        self._needs_folder_selection = False
        self._background_source = self._resolve_background_source()
        self._theme = load_theme_palette()
        self._matugen_available = self._detect_matugen_available()
        self._busy = False
        self._wallpaper_index = load_wallpaper_index_cache()
        self._providers = self._build_providers()
        self._provider_selection_required = not self._provider_initialized()
        self._refresh_wallpapers(allow_scan=False)
        QTimer.singleShot(0, self._deferred_refresh_wallpapers)
        self._cache_watch_timer = QTimer(self)
        self._cache_watch_timer.setInterval(1200)
        self._cache_watch_timer.timeout.connect(self._poll_wallpaper_cache)
        self._cache_watch_timer.start()
        if self._active_provider() == "konachan":
            QTimer.singleShot(450, self.fetchKonachanCandidates)

    def _provider_initialized(self) -> bool:
        appearance = self._settings.get("appearance", {})
        if not isinstance(appearance, dict):
            return False
        if not bool(appearance.get("wallpaper_provider_initialized", False)):
            return False
        provider = str(appearance.get("wallpaper_provider", "")).strip().lower()
        return provider in PROVIDER_META

    def _build_providers(self) -> list[dict[str, object]]:
        appearance = self._settings.get("appearance", {})
        active = str(appearance.get("wallpaper_provider", "")).strip().lower() if isinstance(appearance, dict) else ""
        providers: list[dict[str, object]] = []
        for key in ("d3ext", "jakoolit", "catholic", "konachan", "custom"):
            meta = dict(PROVIDER_META[key])
            folder = Path(str(meta.get("folder", ""))).expanduser() if meta.get("folder") else Path()
            count = self._cached_count_for_folder(folder)
            meta["active"] = key == active
            meta["downloaded"] = bool(folder and folder.exists() and (count > 0 or any(folder.iterdir())))
            meta["count"] = count
            providers.append(meta)
        return providers

    def _cached_snapshot_for_folder(self, folder: Path) -> dict[str, object] | None:
        if not folder:
            return None
        folders = self._wallpaper_index.get("folders", {})
        if not isinstance(folders, dict):
            return None
        snapshot = folders.get(str(folder))
        return snapshot if isinstance(snapshot, dict) else None

    def _cached_count_for_folder(self, folder: Path) -> int:
        snapshot = self._cached_snapshot_for_folder(folder)
        if snapshot is None:
            return 0
        try:
            return int(snapshot.get("count", 0))
        except Exception:
            return 0

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busyChanged.emit()

    def _detect_matugen_available(self) -> bool:
        return (
            MATUGEN_SCRIPT.exists()
            and MATUGEN_BINARY.exists()
            and MATUGEN_BINARY.is_file()
            and bool(MATUGEN_BINARY.stat().st_mode & 0o111)
        )

    def _resolve_background_source(self) -> str:
        wallpaper_path = Path(str(self._settings.get("appearance", {}).get("wallpaper_path", ""))).expanduser()
        if wallpaper_path.exists() and wallpaper_path.is_file():
            return file_url(wallpaper_path)
        if CURRENT_WALLPAPER.exists() and CURRENT_WALLPAPER.is_file():
            return file_url(CURRENT_WALLPAPER)
        return ""

    def _active_provider(self) -> str:
        appearance = self._settings.get("appearance", {})
        if not isinstance(appearance, dict):
            return ""
        return str(appearance.get("wallpaper_provider", "")).strip().lower()

    def _current_folder_path(self) -> Path:
        appearance = self._settings.get("appearance", {})
        if not isinstance(appearance, dict):
            return Path()
        folder = str(appearance.get("slideshow_folder", "")).strip()
        if not folder:
            return Path()
        return Path(folder).expanduser()

    def _refresh_providers(self) -> None:
        self._wallpaper_index = load_wallpaper_index_cache()
        self._providers = self._build_providers()
        self.providersChanged.emit()
        self.providerChanged.emit()
        self.randomizerChanged.emit()

    def _trigger_wallpaper_cache_generation(self, folder: Path | None = None) -> None:
        if not WALLPAPER_CACHE_BINARY.exists():
            return
        command = [str(WALLPAPER_CACHE_BINARY)]
        if folder is not None:
            command.extend(["--folder", str(folder)])
        else:
            command.append("--once")
        run_detached(command)

    def _trigger_thumbnail_generation(self, folder: Path) -> None:
        if not WALLPAPER_THUMBNAIL_SERVICE.exists():
            return
        if self._active_provider() == "konachan":
            return
        run_detached([python_executable(), str(WALLPAPER_THUMBNAIL_SERVICE), "--folder", str(folder)])

    def _run_git_prepare_pack(self, target_dir: Path, repo_url: str) -> tuple[bool, str]:
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            cmd = ["git", "-C", str(target_dir), "pull", "--ff-only"]
        else:
            cmd = ["git", "clone", "--depth", "1", repo_url, str(target_dir)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception as exc:
            return False, str(exc)
        output = (result.stdout or "").strip() or (result.stderr or "").strip()
        return result.returncode == 0, output

    def _extract_repo_archives(self, provider_key: str, target_dir: Path) -> tuple[bool, str]:
        archives_raw = PROVIDER_META.get(provider_key, {}).get("archives", "")
        archives = [item.strip() for item in str(archives_raw).split(",") if item.strip()]
        if not archives:
            return True, ""
        extracted_count = 0
        for archive_name in archives:
            archive_path = target_dir / archive_name
            if not archive_path.exists() or not archive_path.is_file():
                continue
            try:
                with zipfile.ZipFile(archive_path) as bundle:
                    bundle.extractall(target_dir)
                extracted_count += 1
            except Exception as exc:
                return False, f"Failed to extract {archive_name}: {exc}"
        if extracted_count == 0:
            return True, ""
        return True, f"Extracted {extracted_count} archive(s)."

    def _persist_provider(self, provider_key: str, folder: Path | None = None) -> None:
        appearance = self._settings.setdefault("appearance", {})
        if not isinstance(appearance, dict):
            appearance = {}
            self._settings["appearance"] = appearance
        appearance["wallpaper_provider"] = provider_key
        appearance["wallpaper_provider_initialized"] = True
        appearance["konachan_enabled"] = provider_key == "konachan"
        if provider_key == "konachan":
            appearance["local_randomizer_enabled"] = False
        if provider_key == "konachan":
            folder = KONACHAN_CACHE_DIR
        elif folder is None:
            provider_folder = str(PROVIDER_META.get(provider_key, {}).get("folder", "")).strip()
            if provider_folder:
                folder = Path(provider_folder).expanduser()
        if folder is not None:
            appearance["slideshow_folder"] = str(folder)
        save_settings_state(self._settings)
        self._provider_selection_required = False
        self.providerSelectionRequiredChanged.emit()
        self.currentFolderChanged.emit()
        self._refresh_providers()

    def _set_wallpapers_from_cache_snapshot(self, snapshot: dict[str, object]) -> bool:
        items = snapshot.get("items", [])
        if not isinstance(items, list):
            return False
        wallpapers: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            path = Path(str(item.get("path", ""))).expanduser()
            if not path.exists():
                continue
            thumb_path = Path(str(item.get("thumb", ""))).expanduser()
            wallpapers.append(
                {
                    "name": str(item.get("name", "")).strip() or path.stem.replace("_", " ").replace("-", " ").strip() or path.name,
                    "path": str(path),
                    "url": file_url(path),
                    "thumbUrl": file_url(thumb_path) if thumb_path.exists() else file_url(path),
                    "folder": str(item.get("folder", "")).strip() or path.parent.name,
                }
            )
        self._wallpapers = wallpapers
        return True

    def _deferred_refresh_wallpapers(self) -> None:
        self._refresh_wallpapers(allow_scan=not WALLPAPER_CACHE_BINARY.exists())

    def _poll_wallpaper_cache(self) -> None:
        if self._needs_folder_selection or self._provider_selection_required:
            self._cache_watch_timer.stop()
            return
        if self._wallpapers:
            self._cache_watch_timer.stop()
            return
        self._refresh_wallpapers(allow_scan=False)

    def _refresh_wallpapers(self, *, allow_scan: bool = True) -> None:
        folder = self._current_folder_path()
        self._wallpaper_index = load_wallpaper_index_cache()
        self._wallpapers = []
        self._needs_folder_selection = False
        if self._active_provider() == "custom" and not (folder.exists() and folder.is_dir()):
            self._needs_folder_selection = True
        self.needsFolderSelectionChanged.emit()
        self.currentFolderChanged.emit()
        if self._needs_folder_selection:
            self._status = "Pick a custom wallpaper folder to populate the fullscreen gallery."
            self.statusChanged.emit()
            self.wallpapersChanged.emit()
            self.selectedWallpaperChanged.emit()
            return

        snapshot = self._cached_snapshot_for_folder(folder)
        if snapshot is not None and self._set_wallpapers_from_cache_snapshot(snapshot):
            if self._wallpapers:
                self._current_index = max(0, min(self._current_index, len(self._wallpapers) - 1))
                if self._pinned_index >= len(self._wallpapers):
                    self._pinned_index = -1
                if self._active_provider() == "konachan":
                    self._status = f"Konachan cache ready with {len(self._wallpapers)} wallpaper(s). New safe wallpaper arrives every 2 minutes."
                else:
                    self._status = f"Loaded {len(self._wallpapers)} cached wallpaper(s) from {folder}."
            else:
                self._current_index = 0
                self._pinned_index = -1
                self._status = f"No cached wallpapers found for {folder}."
            self.wallpapersChanged.emit()
            self.currentIndexChanged.emit()
            self.pinnedSelectionChanged.emit()
            self.statusChanged.emit()
            self.selectedWallpaperChanged.emit()
            self._refresh_providers()
            return

        self._trigger_wallpaper_cache_generation(folder)
        if not allow_scan:
            self._status = f"Preparing wallpaper library for {folder}."
            self.wallpapersChanged.emit()
            self.currentIndexChanged.emit()
            self.pinnedSelectionChanged.emit()
            self.statusChanged.emit()
            self.selectedWallpaperChanged.emit()
            self._refresh_providers()
            return

        image_paths = image_paths_for_folder(folder)
        self._wallpapers = [
            {
                "name": path.stem.replace("_", " ").replace("-", " ").strip() or path.name,
                "path": str(path),
                "url": file_url(path),
                "thumbUrl": file_url(thumbnail_path_for(path)) if thumbnail_path_for(path).exists() else file_url(path),
                "folder": path.parent.name,
            }
            for path in image_paths
        ]
        if self._wallpapers:
            self._current_index = max(0, min(self._current_index, len(self._wallpapers) - 1))
            if self._pinned_index >= len(self._wallpapers):
                self._pinned_index = -1
            if self._active_provider() == "konachan":
                self._status = f"Konachan cache ready with {len(self._wallpapers)} wallpaper(s). New safe wallpaper arrives every 2 minutes."
            else:
                self._status = f"Loaded {len(self._wallpapers)} wallpaper(s) from {folder}."
        else:
            self._current_index = 0
            self._pinned_index = -1
            if self._active_provider() == "konachan":
                self._status = "Konachan feed is enabled. The first safe wallpaper will be downloaded into the cache shortly."
            else:
                self._status = f"No supported images found in {folder}."
        self.wallpapersChanged.emit()
        self.currentIndexChanged.emit()
        self.pinnedSelectionChanged.emit()
        self.statusChanged.emit()
        self.selectedWallpaperChanged.emit()
        self._refresh_providers()

    def _apply_wallpaper_settings(self, wallpaper_path: Path) -> None:
        appearance = self._settings.setdefault("appearance", {})
        if not isinstance(appearance, dict):
            appearance = {}
            self._settings["appearance"] = appearance
        appearance["wallpaper_path"] = str(wallpaper_path)
        appearance["wallpaper_mode"] = "picture"
        appearance["slideshow_enabled"] = False
        if self._matugen_available:
            appearance["use_matugen_palette"] = True
            appearance["theme_choice"] = "wallpaper_aware"
        save_settings_state(self._settings)

    def _selected_item(self) -> dict[str, object] | None:
        if not self._wallpapers:
            return None
        if self._current_index < 0 or self._current_index >= len(self._wallpapers):
            return None
        item = self._wallpapers[self._current_index]
        return item if isinstance(item, dict) else None

    def _wallpaper_change_notifications_enabled(self) -> bool:
        appearance = self._settings.get("appearance", {})
        if not isinstance(appearance, dict):
            return False
        return bool(appearance.get("wallpaper_change_notifications_enabled", False))

    def _apply_wallpaper_path(self, wallpaper_path: Path, *, pin_selection: bool) -> None:
        if WALLPAPER_SCRIPT.exists():
            run_detached([str(WALLPAPER_SCRIPT), str(wallpaper_path)])
        else:
            run_detached(["feh", "--bg-fill", str(wallpaper_path)])
        if self._matugen_available:
            matugen_env = dict(os.environ)
            if not self._wallpaper_change_notifications_enabled():
                matugen_env["HANAUTA_SUPPRESS_MATUGEN_NOTIFY"] = "1"
            run_detached([str(MATUGEN_SCRIPT), str(wallpaper_path)], env=matugen_env)
        self._apply_wallpaper_settings(wallpaper_path)
        self._background_source = file_url(wallpaper_path)
        self.backgroundSourceChanged.emit()
        self._pinned_index = self._current_index if pin_selection else -1
        self.pinnedSelectionChanged.emit()
        self._status = (
            f"Applied {wallpaper_path.name}. Matugen palette refreshed."
            if self._matugen_available
            else f"Applied {wallpaper_path.name}. Matugen not available, so widget colors were left as-is."
        )
        if not pin_selection:
            self._status += " Selection released."
        self.statusChanged.emit()
        if self._wallpaper_change_notifications_enabled():
            self.notify.emit(self._status)

    def _start_konachan_daemon_once(self) -> None:
        if not KONACHAN_PROVIDER_DAEMON.exists():
            return
        run_detached([python_executable(), str(KONACHAN_PROVIDER_DAEMON), "--once"])

    def _appearance(self) -> dict:
        appearance = self._settings.setdefault("appearance", {})
        if not isinstance(appearance, dict):
            appearance = {}
            self._settings["appearance"] = appearance
        return appearance

    def _selected_konachan_candidate(self) -> dict[str, str] | None:
        if self._active_provider() != "konachan":
            return None
        if self._konachan_current < 0 or self._konachan_current >= len(self._konachan_candidates):
            return None
        item = self._konachan_candidates[self._konachan_current]
        return item if isinstance(item, dict) else None

    @pyqtProperty("QVariantList", notify=wallpapersChanged)
    def wallpapers(self) -> list[dict[str, object]]:
        return self._wallpapers

    @pyqtProperty(int, notify=currentIndexChanged)
    def currentIndex(self) -> int:
        return self._current_index

    @pyqtProperty(str, notify=currentFolderChanged)
    def currentFolder(self) -> str:
        folder = self._current_folder_path()
        return str(folder) if folder else ""

    @pyqtProperty(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @pyqtProperty(bool, notify=needsFolderSelectionChanged)
    def needsFolderSelection(self) -> bool:
        return self._needs_folder_selection

    @pyqtProperty(str, notify=backgroundSourceChanged)
    def backgroundSource(self) -> str:
        return self._background_source

    @pyqtProperty(bool, notify=matugenAvailableChanged)
    def matugenAvailable(self) -> bool:
        return self._matugen_available

    @pyqtProperty(str, notify=selectedWallpaperChanged)
    def selectedWallpaperName(self) -> str:
        candidate = self._selected_konachan_candidate()
        if candidate is not None:
            return str(candidate.get("name", "Konachan suggestion"))
        item = self._selected_item()
        return str(item.get("name", "")) if item else ""

    @pyqtProperty(str, notify=selectedWallpaperChanged)
    def selectedWallpaperPath(self) -> str:
        candidate = self._selected_konachan_candidate()
        if candidate is not None:
            detail = str(candidate.get("detail", "")).strip()
            file_url = str(candidate.get("fileUrl", "")).strip()
            return detail if detail else file_url
        item = self._selected_item()
        return str(item.get("path", "")) if item else ""

    @pyqtProperty(str, notify=selectedWallpaperChanged)
    def selectedWallpaperUrl(self) -> str:
        candidate = self._selected_konachan_candidate()
        if candidate is not None:
            return str(candidate.get("previewUrl", "")).strip()
        item = self._selected_item()
        return str(item.get("url", "")) if item else ""

    @pyqtProperty("QVariantList", notify=konachanCandidatesChanged)
    def konachanCandidates(self) -> list[dict[str, str]]:
        return self._konachan_candidates

    @pyqtProperty(int, notify=konachanCurrentChanged)
    def konachanCurrentIndex(self) -> int:
        return self._konachan_current

    @pyqtProperty("QVariantList", notify=providersChanged)
    def providers(self) -> list[dict[str, object]]:
        return self._providers

    @pyqtProperty(str, notify=providerChanged)
    def activeProvider(self) -> str:
        return self._active_provider()

    @pyqtProperty(bool, notify=providerSelectionRequiredChanged)
    def providerSelectionRequired(self) -> bool:
        return self._provider_selection_required

    @pyqtProperty(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @pyqtProperty(int, notify=pinnedSelectionChanged)
    def pinnedIndex(self) -> int:
        return self._pinned_index

    @pyqtProperty(bool, notify=pinnedSelectionChanged)
    def hasPinnedSelection(self) -> bool:
        return self._pinned_index >= 0

    @pyqtProperty(bool, notify=randomizerChanged)
    def localRandomizerEnabled(self) -> bool:
        appearance = self._settings.get("appearance", {})
        if not isinstance(appearance, dict):
            return False
        return bool(appearance.get("local_randomizer_enabled", False))

    @pyqtProperty(bool, notify=randomizerChanged)
    def canUseLocalRandomizer(self) -> bool:
        provider = self._active_provider()
        return provider not in {"", "konachan"} and bool(self._wallpapers)

    @pyqtProperty(str, notify=konachanTagsChanged)
    def konachanTags(self) -> str:
        appearance = self._settings.get("appearance", {})
        if not isinstance(appearance, dict):
            return "rating:safe"
        return str(appearance.get("konachan_tags", "rating:safe")).strip() or "rating:safe"

    @pyqtSlot()
    def openProviderDialog(self) -> None:
        if not self._provider_selection_required:
            self._provider_selection_required = True
            self.providerSelectionRequiredChanged.emit()

    @pyqtSlot()
    def dismissProviderDialog(self) -> None:
        if self._provider_initialized():
            self._provider_selection_required = False
            self.providerSelectionRequiredChanged.emit()

    @pyqtSlot()
    def ensureFolderConfigured(self) -> None:
        if self._provider_selection_required:
            return
        if self._needs_folder_selection:
            self.chooseFolder()

    @pyqtSlot()
    def chooseFolder(self) -> None:
        start_dir = self.currentFolder or str(DEFAULT_WALLPAPER_FOLDER)
        folder = QFileDialog.getExistingDirectory(
            None,
            "Choose wallpaper folder",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if not folder:
            self._status = "Wallpaper folder selection was cancelled."
            self.statusChanged.emit()
            return
        self._persist_provider("custom", Path(folder).expanduser())
        self._status = f"Custom wallpaper folder set to {folder}."
        self.statusChanged.emit()
        self._trigger_thumbnail_generation(Path(folder).expanduser())
        self._trigger_wallpaper_cache_generation(Path(folder).expanduser())
        self._refresh_wallpapers(allow_scan=False)
        QTimer.singleShot(350, self._deferred_refresh_wallpapers)

    @pyqtSlot(str)
    def setKonachanTags(self, tags: str) -> None:
        cleaned = (tags or "").strip() or "rating:safe"
        appearance = self._appearance()
        if str(appearance.get("konachan_tags", "rating:safe")).strip() == cleaned:
            return
        appearance["konachan_tags"] = cleaned
        save_settings_state(self._settings)
        self._konachan_candidates = []
        self._konachan_current = -1
        self.konachanTagsChanged.emit()
        self.konachanCandidatesChanged.emit()
        self.konachanCurrentChanged.emit()
        self.selectedWallpaperChanged.emit()
        self._status = f"Konachan tags updated to: {cleaned}"
        self.statusChanged.emit()
        QTimer.singleShot(120, self.fetchKonachanCandidates)

    @pyqtSlot()
    def fetchKonachanCandidates(self) -> None:
        if self._active_provider() != "konachan":
            self.notify.emit("Konachan is not the active wallpaper provider.")
            return
        self._set_busy(True)
        try:
            candidates = fetch_konachan_candidates(self.konachanTags, limit=10)
        finally:
            self._set_busy(False)
        if not candidates:
            self._status = f"Could not load Konachan suggestions for tags: {self.konachanTags}"
            self.statusChanged.emit()
            self.notify.emit(self._status)
            return
        self._konachan_candidates = candidates
        self._konachan_current = 0
        self.konachanCandidatesChanged.emit()
        self.konachanCurrentChanged.emit()
        self.selectedWallpaperChanged.emit()
        self._status = f"Loaded {len(candidates)} Konachan suggestions for tags: {self.konachanTags}"
        self.statusChanged.emit()

    @pyqtSlot()
    def fetchKonachanRandom(self) -> None:
        if self._active_provider() != "konachan":
            self.notify.emit("Konachan is not the active wallpaper provider.")
            return
        if not self._konachan_candidates:
            self.fetchKonachanCandidates()
            if not self._konachan_candidates:
                return
        next_index = random.randrange(len(self._konachan_candidates))
        if len(self._konachan_candidates) > 1:
            while next_index == self._konachan_current:
                next_index = random.randrange(len(self._konachan_candidates))
        self._konachan_current = next_index
        self.konachanCurrentChanged.emit()
        self.selectedWallpaperChanged.emit()
        self._status = f"Previewing random Konachan suggestion {next_index + 1} of {len(self._konachan_candidates)}."
        self.statusChanged.emit()

    @pyqtSlot(int)
    def previewKonachanCandidate(self, index: int) -> None:
        if self._active_provider() != "konachan":
            return
        if index < 0 or index >= len(self._konachan_candidates):
            return
        if self._konachan_current == index:
            return
        self._konachan_current = index
        self.konachanCurrentChanged.emit()
        self.selectedWallpaperChanged.emit()

    @pyqtSlot(int)
    def applyKonachanCandidate(self, index: int) -> None:
        if self._active_provider() != "konachan":
            return
        if index < 0 or index >= len(self._konachan_candidates):
            self.notify.emit("That Konachan suggestion is no longer available.")
            return
        self._konachan_current = index
        self.konachanCurrentChanged.emit()
        self.selectedWallpaperChanged.emit()
        self._set_busy(True)
        try:
            path = download_konachan_candidate(self._konachan_candidates[index])
        finally:
            self._set_busy(False)
        if path is None:
            self._status = "Failed to download the selected Konachan wallpaper."
            self.statusChanged.emit()
            self.notify.emit(self._status)
            return
        self._apply_wallpaper_path(path, pin_selection=False)
        prune_konachan_cache(keep=path)
        self._status = f"Applied Konachan suggestion {index + 1} for tags: {self.konachanTags}"
        self.statusChanged.emit()

    @pyqtSlot(str)
    def selectProvider(self, provider_key: str) -> None:
        provider_key = (provider_key or "").strip().lower()
        if provider_key not in PROVIDER_META:
            self.notify.emit("Unknown wallpaper provider.")
            return
        self._set_busy(True)
        try:
            meta = PROVIDER_META[provider_key]
            if provider_key == "custom":
                self.chooseFolder()
                return
            if provider_key == "konachan":
                KONACHAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                prune_konachan_cache()
                self._persist_provider("konachan", KONACHAN_CACHE_DIR)
                self._status = "Konachan live feed enabled. Loading tagged suggestions now."
                self.statusChanged.emit()
                self._refresh_wallpapers(allow_scan=False)
                self._start_konachan_daemon_once()
                QTimer.singleShot(300, self.fetchKonachanCandidates)
                return
            target_dir = Path(str(meta.get("folder", ""))).expanduser()
            repo_url = str(meta.get("repo", "")).strip()
            ok, output = self._run_git_prepare_pack(target_dir, repo_url)
            if not ok:
                self._status = f"Failed to prepare {meta['title']}: {output or 'git command failed'}"
                self.statusChanged.emit()
                self.notify.emit(self._status)
                return
            extracted_ok, extracted_message = self._extract_repo_archives(provider_key, target_dir)
            if not extracted_ok:
                self._status = f"Failed to prepare {meta['title']}: {extracted_message}"
                self.statusChanged.emit()
                self.notify.emit(self._status)
                return
            self._persist_provider(provider_key, target_dir)
            detail = output or "Pack prepared successfully."
            if extracted_message:
                detail = f"{detail} {extracted_message}"
            self._status = f"{meta['title']} is ready. {detail}"
            self.statusChanged.emit()
            self._trigger_thumbnail_generation(target_dir)
            self._trigger_wallpaper_cache_generation(target_dir)
            self._refresh_wallpapers(allow_scan=False)
            QTimer.singleShot(350, self._deferred_refresh_wallpapers)
            self.notify.emit(f"{meta['title']} wallpaper pack is ready.")
        finally:
            self._set_busy(False)

    @pyqtSlot(int)
    def setCurrentIndex(self, index: int) -> None:
        if not self._wallpapers:
            return
        clamped = max(0, min(index, len(self._wallpapers) - 1))
        if clamped == self._current_index:
            return
        self._current_index = clamped
        self.currentIndexChanged.emit()
        self.selectedWallpaperChanged.emit()

    @pyqtSlot()
    def applyRandomWallpaper(self) -> None:
        if not self._wallpapers:
            self.notify.emit("No wallpapers available to randomize.")
            return
        if self._active_provider() == "konachan":
            self.notify.emit("Konachan already rotates automatically every 2 minutes.")
            return
        current_path = self.selectedWallpaperPath
        candidates = [item for item in self._wallpapers if isinstance(item, dict) and str(item.get("path", "")) != current_path]
        if not candidates:
            candidates = self._wallpapers
        chosen = random.choice(candidates)
        chosen_path = str(chosen.get("path", ""))
        for index, item in enumerate(self._wallpapers):
            if str(item.get("path", "")) == chosen_path:
                self.setCurrentIndex(index)
                break
        wallpaper_path = Path(chosen_path).expanduser()
        if not wallpaper_path.exists():
            self.notify.emit("Random wallpaper file no longer exists.")
            return
        self._apply_wallpaper_path(wallpaper_path, pin_selection=False)

    @pyqtSlot()
    def toggleLocalRandomizer(self) -> None:
        if self._active_provider() == "konachan":
            self.notify.emit("Konachan already uses its own live 2-minute rotation.")
            return
        if not self._wallpapers:
            self.notify.emit("Load a wallpaper pack first before enabling random rotation.")
            return
        appearance = self._appearance()
        enabled = not bool(appearance.get("local_randomizer_enabled", False))
        appearance["local_randomizer_enabled"] = enabled
        appearance["local_randomizer_interval_seconds"] = 120
        save_settings_state(self._settings)
        self.randomizerChanged.emit()
        if enabled:
            self._status = "Random folder rotation enabled. A new wallpaper will be applied every 2 minutes."
            self.applyRandomWallpaper()
        else:
            self._status = "Random folder rotation disabled."
        self.statusChanged.emit()
        self.notify.emit(self._status)

    @pyqtSlot()
    def activateCurrent(self) -> None:
        item = self._selected_item()
        if item is None:
            if self._active_provider() == "konachan":
                self._start_konachan_daemon_once()
                self.notify.emit("Konachan is enabled. Waiting for the first downloaded wallpaper.")
            else:
                self.notify.emit("No wallpaper selected.")
            return
        wallpaper_path = Path(str(item.get("path", ""))).expanduser()
        if not wallpaper_path.exists():
            self.notify.emit("Wallpaper file no longer exists.")
            return
        try:
            if self._pinned_index == self._current_index:
                self._pinned_index = -1
                self.pinnedSelectionChanged.emit()
                self._status = f"Selection released for {wallpaper_path.name}."
                self.statusChanged.emit()
                self.notify.emit(self._status)
                return
            self._apply_wallpaper_path(wallpaper_path, pin_selection=True)
        except Exception as exc:
            self._status = f"Failed to apply wallpaper: {exc}"
            self.statusChanged.emit()
            self.notify.emit(self._status)

    @pyqtSlot()
    def refreshProviderContent(self) -> None:
        provider = self._active_provider()
        if provider == "konachan":
            self._start_konachan_daemon_once()
            self._status = "Refreshing Konachan cache now."
            self.statusChanged.emit()
            QTimer.singleShot(2500, self._refresh_wallpapers)
            return
        if provider in {"d3ext", "jakoolit", "catholic"}:
            self.selectProvider(provider)
            return
        self._refresh_wallpapers()

    @pyqtSlot()
    def closeWindow(self) -> None:
        self.closeRequested.emit()
        QGuiApplication.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta Wallpaper Manager")
    app.setDesktopFileName("HanautaWallpaperManager")
    signal.signal(signal.SIGINT, lambda *_args: app.quit())

    if not QML_FILE.exists():
        print(f"ERROR: QML file not found: {QML_FILE}", file=sys.stderr)
        return 2

    theme = load_theme_palette()
    theme_map = {
        "primary": theme.primary,
        "text": theme.text,
        "textMuted": theme.text_muted,
        "surface": theme.surface,
        "surfaceContainer": theme.surface_container,
        "surfaceContainerHigh": theme.surface_container_high,
        "outline": theme.outline,
        "heroStart": rgba(theme.primary_container, 0.46),
        "heroEnd": rgba(blend(theme.surface_container_high, theme.surface, 0.24), 0.96),
        "panelStart": rgba(theme.surface_container_high, 0.96),
        "panelEnd": rgba(blend(theme.surface_container, theme.surface, 0.28), 0.92),
        "card": rgba(theme.surface_container_high, 0.82),
        "cardDark": rgba(theme.surface, 0.72),
        "cardBorder": rgba(theme.outline, 0.18),
        "active": rgba(theme.primary, 0.22),
        "activeBorder": rgba(theme.primary, 0.52),
        "overlay": "#0d0d12",
        "shadow": "#000000",
    }

    engine = QQmlApplicationEngine()
    backend = Backend()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("themeModel", theme_map)
    engine.rootContext().setContextProperty(
        "fontsModel",
        {
            "ui": theme.ui_font_family or "Sans Serif",
            "display": theme.display_font_family or theme.ui_font_family or "Sans Serif",
        },
    )
    engine.load(QUrl.fromLocalFile(str(QML_FILE)))
    if not engine.rootObjects():
        print("ERROR: failed to load wallpaper manager QML.", file=sys.stderr)
        return 3

    QTimer.singleShot(0, backend.ensureFolderConfigured)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
