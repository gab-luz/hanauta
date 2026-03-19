#!/usr/bin/env python3
from __future__ import annotations

import signal
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QApplication


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
QML_FILE = Path(__file__).resolve().with_suffix(".qml")

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.rss import collect_entries, load_settings_state
from pyqt.shared.runtime import entry_command
from pyqt.shared.theme import blend, load_theme_palette, palette_mtime, rgba


def relative_time_from_timestamp(timestamp: int) -> str:
    if timestamp <= 0:
        return ""
    now = datetime.now(timezone.utc).timestamp()
    delta = max(0, int(now - timestamp))
    if delta < 60:
        return "just now"
    if delta < 3600:
        minutes = max(1, delta // 60)
        return f"{minutes}min ago"
    if delta < 86400:
        hours = max(1, delta // 3600)
        return f"{hours}h ago"
    days = max(1, delta // 86400)
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


class RefreshWorker(QThread):
    refreshed = pyqtSignal(list, list)

    def __init__(self, settings: dict) -> None:
        super().__init__()
        self._settings = settings

    def run(self) -> None:
        try:
            sources, collected = collect_entries(self._settings)
        except Exception:
            sources, collected = [], []
        self.refreshed.emit(sources, collected)


class Backend(QObject):
    entriesChanged = pyqtSignal()
    statsChanged = pyqtSignal()
    statusChanged = pyqtSignal()
    loadingChanged = pyqtSignal()
    themeChanged = pyqtSignal()
    notify = pyqtSignal(str)
    searchQueryChanged = pyqtSignal()
    closeRequested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._settings = load_settings_state()
        self._entries: list[dict[str, object]] = []
        self._sources_count = 0
        self._status = "RSS is idle."
        self._loading = False
        self._search_query = ""
        self._theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._refresh_worker: RefreshWorker | None = None
        self.refresh()

        self._theme_timer = QTimer(self)
        self._theme_timer.timeout.connect(self._reload_theme_if_needed)
        self._theme_timer.start(3000)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self._theme = load_theme_palette()
        self.themeChanged.emit()

    def _set_loading(self, loading: bool) -> None:
        if self._loading == loading:
            return
        self._loading = loading
        self.loadingChanged.emit()

    @pyqtProperty("QVariantList", notify=entriesChanged)
    def entries(self) -> list[dict[str, object]]:
        return self._entries

    @pyqtProperty("QVariantList", notify=entriesChanged)
    def filteredEntries(self) -> list[dict[str, object]]:
        query = self._search_query.strip().lower()
        if not query:
            return self._entries
        return [
            entry
            for entry in self._entries
            if query in str(entry.get("title", "")).lower()
            or query in str(entry.get("description", "")).lower()
            or query in str(entry.get("source", "")).lower()
        ]

    @pyqtProperty(int, notify=statsChanged)
    def sourcesCount(self) -> int:
        return self._sources_count

    @pyqtProperty(int, notify=statsChanged)
    def itemCount(self) -> int:
        return len(self._entries)

    @pyqtProperty(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @pyqtProperty(bool, notify=loadingChanged)
    def loading(self) -> bool:
        return self._loading

    @pyqtProperty(str, notify=searchQueryChanged)
    def searchQuery(self) -> str:
        return self._search_query

    @pyqtProperty(str, notify=themeChanged)
    def primary(self) -> str:
        return self._theme.primary

    @pyqtProperty(str, notify=themeChanged)
    def textColor(self) -> str:
        return self._theme.text

    @pyqtProperty(str, notify=themeChanged)
    def mutedText(self) -> str:
        return self._theme.text_muted

    @pyqtProperty(str, notify=themeChanged)
    def panelStart(self) -> str:
        return rgba(self._theme.surface_container_high, 0.97)

    @pyqtProperty(str, notify=themeChanged)
    def panelEnd(self) -> str:
        return rgba(blend(self._theme.surface_container, self._theme.surface, 0.35), 0.92)

    @pyqtProperty(str, notify=themeChanged)
    def heroStart(self) -> str:
        return rgba(self._theme.primary_container, 0.48)

    @pyqtProperty(str, notify=themeChanged)
    def heroEnd(self) -> str:
        return rgba(blend(self._theme.surface_container_high, self._theme.surface, 0.18), 0.94)

    @pyqtProperty(str, notify=themeChanged)
    def cardColor(self) -> str:
        return rgba(self._theme.surface_container_high, 0.84)

    @pyqtProperty(str, notify=themeChanged)
    def cardBorder(self) -> str:
        return rgba(self._theme.outline, 0.18)

    @pyqtProperty(str, notify=themeChanged)
    def chipColor(self) -> str:
        return rgba(self._theme.primary, 0.14)

    @pyqtProperty(str, notify=themeChanged)
    def chipBorder(self) -> str:
        return rgba(self._theme.primary, 0.22)

    @pyqtProperty(str, notify=themeChanged)
    def backgroundShade(self) -> str:
        return "#0f1118"

    @pyqtSlot()
    def refresh(self) -> None:
        if self._loading:
            return
        self._set_loading(True)
        self._settings = load_settings_state()
        self._refresh_worker = RefreshWorker(self._settings)
        self._refresh_worker.refreshed.connect(self._apply_refresh_results)
        self._refresh_worker.finished.connect(self._cleanup_refresh_worker)
        self._refresh_worker.start()

    def _cleanup_refresh_worker(self) -> None:
        if self._refresh_worker is not None:
            self._refresh_worker.deleteLater()
            self._refresh_worker = None

    def _send_refresh_notification(self, item_count: int, source_count: int) -> None:
        title = "HanautaRSS"
        body = f"Refreshed {item_count} item(s) from {source_count} source(s)."
        try:
            subprocess.Popen(
                ["notify-send", "-a", title, title, body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass
        self.notify.emit(body)

    @pyqtSlot(list, list)
    def _apply_refresh_results(self, sources: list, collected: list) -> None:
        self._sources_count = len(sources)
        enriched: list[dict[str, object]] = []
        for item in collected:
            timestamp = 0
            try:
                timestamp = int(str(item.get("timestamp", "0")) or 0)
            except Exception:
                timestamp = 0
            enriched.append(
                {
                    "title": str(item.get("title", "Untitled")).strip() or "Untitled",
                    "link": str(item.get("link", "")).strip(),
                    "description": str(item.get("detail", "")).strip(),
                    "source": str(item.get("feed_title", item.get("source", "Feed"))).strip() or "Feed",
                    "timestamp": timestamp,
                    "relativeTime": relative_time_from_timestamp(timestamp),
                    "imageUrl": str(item.get("image_url", "")).strip(),
                }
            )
        sort_mode = str(self._settings.get("rss", {}).get("sort_mode", "newest")).strip().lower()
        if sort_mode == "oldest":
            enriched.sort(key=lambda entry: int(entry.get("timestamp", 0) or 0))
        elif sort_mode == "byfeed":
            enriched.sort(key=lambda entry: (str(entry.get("source", "")).lower(), -int(entry.get("timestamp", 0) or 0)))
            max_per_feed = max(1, int(self._settings.get("rss", {}).get("max_per_feed", 5) or 5))
            grouped: dict[str, int] = {}
            filtered: list[dict[str, object]] = []
            for entry in enriched:
                source = str(entry.get("source", ""))
                grouped[source] = grouped.get(source, 0) + 1
                if grouped[source] <= max_per_feed:
                    filtered.append(entry)
            enriched = filtered
        else:
            enriched.sort(key=lambda entry: int(entry.get("timestamp", 0) or 0), reverse=True)
        self._entries = enriched
        if not self._settings.get("rss", {}).get("feeds") and not str(self._settings.get("rss", {}).get("feed_urls", "")).strip() and not str(self._settings.get("rss", {}).get("opml_source", "")).strip():
            self._status = "No RSS feeds configured yet. Open Settings to add feeds."
        elif not self._entries:
            self._status = f"Checked {self._sources_count} source(s), but no readable items were found."
        else:
            self._status = f"Loaded {len(self._entries)} RSS item(s) from {self._sources_count} source(s)."
        self.entriesChanged.emit()
        self.statsChanged.emit()
        self.searchQueryChanged.emit()
        self.statusChanged.emit()
        self._set_loading(False)
        self._send_refresh_notification(len(self._entries), self._sources_count)

    @pyqtSlot(str)
    def setSearchQuery(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._search_query:
            return
        self._search_query = normalized
        self.searchQueryChanged.emit()
        self.entriesChanged.emit()

    @pyqtSlot(str)
    def openLink(self, url: str) -> None:
        if url:
            QGuiApplication.clipboard()  # ensure app object keeps GUI subsystems initialized
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot()
    def openSettings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        command = entry_command(SETTINGS_PAGE_SCRIPT, "--page", "services", "--service-section", "rss_widget")
        if not command:
            return
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    @pyqtSlot()
    def closeWindow(self) -> None:
        self.closeRequested.emit()
        QGuiApplication.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta RSS")
    app.setDesktopFileName("HanautaRSS")
    signal.signal(signal.SIGINT, lambda *_args: app.quit())

    if not QML_FILE.exists():
        print(f"ERROR: QML file not found: {QML_FILE}", file=sys.stderr)
        return 2

    engine = QQmlApplicationEngine()
    backend = Backend()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(QML_FILE)))
    if not engine.rootObjects():
        print("ERROR: failed to load RSS widget QML.", file=sys.stderr)
        return 3
    root = engine.rootObjects()[0]
    primary_screen = QGuiApplication.primaryScreen()
    if primary_screen is not None:
        geometry = primary_screen.availableGeometry()
        root.setProperty("x", geometry.x() + geometry.width() - int(root.property("width")) - 48)
        root.setProperty("y", geometry.y() + 84)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
