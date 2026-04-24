from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from settings_page.wallpaper_sources import sync_wallpaper_source_preset as sync_wallpaper_source_preset_impl
from settings_page.wallpaper_presets import WALLPAPER_SOURCE_PRESETS
from settings_page.xdg_mail import current_favorite_mail_handler, current_mailto_handler
from settings_page.plugin_backends import gamemode_summary


ROOT = Path(__file__).resolve().parents[2].parents[1]
WALLPAPER_SOURCE_CACHE_DIR = ROOT / "hanauta" / "vendor" / "wallpaper-sources"
COMMUNITY_WALLPAPER_DIR = ROOT / "hanauta" / "walls" / "community"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class WallpaperSourceSyncWorker(QThread):
    finished_sync = pyqtSignal(str, bool, str, object)

    def __init__(self, source_key: str) -> None:
        super().__init__()
        self.source_key = source_key

    def run(self) -> None:
        ok, message, folder = sync_wallpaper_source_preset(
            self.source_key,
            presets=WALLPAPER_SOURCE_PRESETS,
            cache_root=WALLPAPER_SOURCE_CACHE_DIR,
            community_root=COMMUNITY_WALLPAPER_DIR,
            image_suffixes=IMAGE_SUFFIXES,
        )
        self.finished_sync.emit(self.source_key, ok, message, folder)


class MailIntegrationProbeWorker(QThread):
    finished_probe = pyqtSignal(str, str)

    def run(self) -> None:
        self.finished_probe.emit(current_favorite_mail_handler(), current_mailto_handler())


class GameModeSummaryWorker(QThread):
    finished_summary = pyqtSignal(object)

    def run(self) -> None:
        from settings_page.plugin_backends import gamemode_summary
        self.finished_summary.emit(gamemode_summary())