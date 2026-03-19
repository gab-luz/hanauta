#!/usr/bin/env python3
from __future__ import annotations

import json
import signal
import subprocess
import sys
from pathlib import Path
from urllib import parse, request

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QApplication, QFileDialog


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
CURRENT_WALLPAPER = Path.home() / ".wallpapers" / "wallpaper.png"
WALLPAPER_SCRIPT = ROOT / "scripts" / "set_wallpaper.sh"
MATUGEN_SCRIPT = ROOT / "scripts" / "run_matugen.sh"
MATUGEN_BINARY = ROOT / "bin" / "matugen"
QML_FILE = Path(__file__).resolve().with_suffix(".qml")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
DEFAULT_WALLPAPER_FOLDER = ROOT / "hanauta" / "walls"
KONACHAN_CACHE_DIR = DEFAULT_WALLPAPER_FOLDER / "Konachan-cache"
KONACHAN_PROVIDER_DAEMON = Path(__file__).resolve().with_name("wallpaper_provider_daemon.py")

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


def load_settings_state() -> dict:
    defaults = {
        "appearance": {
            "wallpaper_mode": "picture",
            "wallpaper_path": str(CURRENT_WALLPAPER),
            "slideshow_folder": str(DEFAULT_WALLPAPER_FOLDER),
            "slideshow_enabled": False,
            "theme_choice": "dark",
            "use_matugen_palette": False,
            "wallpaper_provider": "",
            "wallpaper_provider_initialized": False,
            "konachan_enabled": False,
            "konachan_interval_seconds": 120,
            "konachan_tags": "rating:safe",
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


def run_detached(command: list[str]) -> None:
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


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


class Backend(QObject):
    wallpapersChanged = pyqtSignal()
    currentIndexChanged = pyqtSignal()
    currentFolderChanged = pyqtSignal()
    statusChanged = pyqtSignal()
    needsFolderSelectionChanged = pyqtSignal()
    backgroundSourceChanged = pyqtSignal()
    matugenAvailableChanged = pyqtSignal()
    selectedWallpaperChanged = pyqtSignal()
    providersChanged = pyqtSignal()
    providerChanged = pyqtSignal()
    providerSelectionRequiredChanged = pyqtSignal()
    busyChanged = pyqtSignal()
    closeRequested = pyqtSignal()
    notify = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._settings = load_settings_state()
        self._wallpapers: list[dict[str, object]] = []
        self._current_index = 0
        self._status = "Choose your wallpaper pack to start building the library."
        self._needs_folder_selection = False
        self._background_source = self._resolve_background_source()
        self._theme = load_theme_palette()
        self._matugen_available = self._detect_matugen_available()
        self._busy = False
        self._providers = self._build_providers()
        self._provider_selection_required = not self._provider_initialized()
        self._refresh_wallpapers()

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
        for key in ("d3ext", "jakoolit", "konachan", "custom"):
            meta = dict(PROVIDER_META[key])
            folder = Path(str(meta.get("folder", ""))).expanduser() if meta.get("folder") else Path()
            count = len(image_paths_for_folder(folder)) if folder else 0
            meta["active"] = key == active
            meta["downloaded"] = bool(folder and folder.exists() and count > 0)
            meta["count"] = count
            providers.append(meta)
        return providers

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
        self._providers = self._build_providers()
        self.providersChanged.emit()
        self.providerChanged.emit()

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

    def _persist_provider(self, provider_key: str, folder: Path | None = None) -> None:
        appearance = self._settings.setdefault("appearance", {})
        if not isinstance(appearance, dict):
            appearance = {}
            self._settings["appearance"] = appearance
        appearance["wallpaper_provider"] = provider_key
        appearance["wallpaper_provider_initialized"] = True
        appearance["konachan_enabled"] = provider_key == "konachan"
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

    def _refresh_wallpapers(self) -> None:
        folder = self._current_folder_path()
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

        image_paths = image_paths_for_folder(folder)
        self._wallpapers = [
            {
                "name": path.stem.replace("_", " ").replace("-", " ").strip() or path.name,
                "path": str(path),
                "url": file_url(path),
                "folder": path.parent.name,
            }
            for path in image_paths
        ]
        if self._wallpapers:
            self._current_index = max(0, min(self._current_index, len(self._wallpapers) - 1))
            if self._active_provider() == "konachan":
                self._status = f"Konachan cache ready with {len(self._wallpapers)} wallpaper(s). New safe wallpaper arrives every 2 minutes."
            else:
                self._status = f"Loaded {len(self._wallpapers)} wallpaper(s) from {folder}."
        else:
            self._current_index = 0
            if self._active_provider() == "konachan":
                self._status = "Konachan feed is enabled. The first safe wallpaper will be downloaded into the cache shortly."
            else:
                self._status = f"No supported images found in {folder}."
        self.wallpapersChanged.emit()
        self.currentIndexChanged.emit()
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

    def _start_konachan_daemon_once(self) -> None:
        if not KONACHAN_PROVIDER_DAEMON.exists():
            return
        run_detached([python_executable(), str(KONACHAN_PROVIDER_DAEMON), "--once"])

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
        item = self._selected_item()
        return str(item.get("name", "")) if item else ""

    @pyqtProperty(str, notify=selectedWallpaperChanged)
    def selectedWallpaperPath(self) -> str:
        item = self._selected_item()
        return str(item.get("path", "")) if item else ""

    @pyqtProperty(str, notify=selectedWallpaperChanged)
    def selectedWallpaperUrl(self) -> str:
        item = self._selected_item()
        return str(item.get("url", "")) if item else ""

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
        self._refresh_wallpapers()

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
                self._persist_provider("konachan", KONACHAN_CACHE_DIR)
                self._status = "Konachan live feed enabled. Downloading the first safe wallpaper now."
                self.statusChanged.emit()
                self._refresh_wallpapers()
                self._start_konachan_daemon_once()
                return
            target_dir = Path(str(meta.get("folder", ""))).expanduser()
            repo_url = str(meta.get("repo", "")).strip()
            ok, output = self._run_git_prepare_pack(target_dir, repo_url)
            if not ok:
                self._status = f"Failed to prepare {meta['title']}: {output or 'git command failed'}"
                self.statusChanged.emit()
                self.notify.emit(self._status)
                return
            self._persist_provider(provider_key, target_dir)
            self._status = f"{meta['title']} is ready. {output or 'Pack prepared successfully.'}"
            self.statusChanged.emit()
            self._refresh_wallpapers()
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
            if WALLPAPER_SCRIPT.exists():
                run_detached([str(WALLPAPER_SCRIPT), str(wallpaper_path)])
            else:
                run_detached(["feh", "--bg-fill", str(wallpaper_path)])
            if self._matugen_available:
                run_detached([str(MATUGEN_SCRIPT), str(wallpaper_path)])
            self._apply_wallpaper_settings(wallpaper_path)
            self._background_source = file_url(wallpaper_path)
            self.backgroundSourceChanged.emit()
            self._status = (
                f"Applied {wallpaper_path.name}. Matugen palette refreshed."
                if self._matugen_available
                else f"Applied {wallpaper_path.name}. Matugen not available, so widget colors were left as-is."
            )
            self.statusChanged.emit()
            self.notify.emit(self._status)
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
        if provider in {"d3ext", "jakoolit"}:
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
