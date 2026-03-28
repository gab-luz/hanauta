from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtQuickWidgets import QQuickWidget
from PyQt6.QtWidgets import QWidget

from pyqt.shared.theme import blend, load_theme_palette, rgba


LEGACY_QML_FILE = Path(__file__).resolve().parents[1] / "widget-rss" / "rss_settings.qml"
PLUGIN_INSTALL_QML_FILE = Path.home() / ".config" / "i3" / "hanauta" / "plugins" / "rss_widget" / "rss_settings.qml"


def _rss_settings_qml_file() -> Path:
    for candidate in (LEGACY_QML_FILE, PLUGIN_INSTALL_QML_FILE):
        if candidate.exists():
            return candidate
    return LEGACY_QML_FILE


class RssSettingsBridge(QObject):
    feedsChanged = pyqtSignal()
    statusChanged = pyqtSignal()
    scalarChanged = pyqtSignal()

    def __init__(self, settings_state: dict, save_callback, status_callback) -> None:
        super().__init__()
        self._settings_state = settings_state
        self._save_callback = save_callback
        self._status_callback = status_callback
        self._status = "RSS settings are ready."

    def _rss(self) -> dict:
        rss = self._settings_state.setdefault("rss", {})
        if not isinstance(rss, dict):
            rss = {}
            self._settings_state["rss"] = rss
        rss.setdefault("feeds", [])
        rss.setdefault("feed_urls", "")
        rss.setdefault("opml_source", "")
        rss.setdefault("username", "")
        rss.setdefault("password", "")
        rss.setdefault("item_limit", 10)
        rss.setdefault("check_interval_minutes", 15)
        rss.setdefault("notify_new_items", True)
        rss.setdefault("play_notification_sound", False)
        rss.setdefault("show_feed_name", True)
        rss.setdefault("open_in_browser", True)
        rss.setdefault("show_images", True)
        rss.setdefault("sort_mode", "newest")
        rss.setdefault("max_per_feed", 5)
        rss.setdefault("view_mode", "expanded")
        return rss

    def _save(self, message: str) -> None:
        self._save_callback()
        self._status = message
        self.statusChanged.emit()
        self.scalarChanged.emit()
        self.feedsChanged.emit()
        self._status_callback(message)

    @pyqtProperty("QVariantList", notify=feedsChanged)
    def feeds(self) -> list[dict[str, str]]:
        feeds = self._rss().get("feeds", [])
        if not isinstance(feeds, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in feeds:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            normalized.append({"name": str(item.get("name", "")).strip() or url, "url": url})
        return normalized

    @pyqtProperty(str, notify=scalarChanged)
    def opmlSource(self) -> str:
        return str(self._rss().get("opml_source", ""))

    @pyqtProperty(str, notify=scalarChanged)
    def username(self) -> str:
        return str(self._rss().get("username", ""))

    @pyqtProperty(str, notify=scalarChanged)
    def password(self) -> str:
        return str(self._rss().get("password", ""))

    @pyqtProperty(int, notify=scalarChanged)
    def itemLimit(self) -> int:
        return int(self._rss().get("item_limit", 10) or 10)

    @pyqtProperty(int, notify=scalarChanged)
    def checkIntervalMinutes(self) -> int:
        return int(self._rss().get("check_interval_minutes", 15) or 15)

    @pyqtProperty(bool, notify=scalarChanged)
    def notifyNewItems(self) -> bool:
        return bool(self._rss().get("notify_new_items", True))

    @pyqtProperty(bool, notify=scalarChanged)
    def playNotificationSound(self) -> bool:
        return bool(self._rss().get("play_notification_sound", False))

    @pyqtProperty(bool, notify=scalarChanged)
    def showFeedName(self) -> bool:
        return bool(self._rss().get("show_feed_name", True))

    @pyqtProperty(bool, notify=scalarChanged)
    def showImages(self) -> bool:
        return bool(self._rss().get("show_images", True))

    @pyqtProperty(bool, notify=scalarChanged)
    def openInBrowser(self) -> bool:
        return bool(self._rss().get("open_in_browser", True))

    @pyqtProperty(str, notify=scalarChanged)
    def sortMode(self) -> str:
        return str(self._rss().get("sort_mode", "newest"))

    @pyqtProperty(int, notify=scalarChanged)
    def maxPerFeed(self) -> int:
        return int(self._rss().get("max_per_feed", 5) or 5)

    @pyqtProperty(str, notify=scalarChanged)
    def viewMode(self) -> str:
        return str(self._rss().get("view_mode", "expanded"))

    @pyqtProperty(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @pyqtSlot(str, str, int)
    def upsertFeed(self, name: str, url: str, index: int) -> None:
        url = str(url).strip()
        if not url:
            self._status = "Feed URL is required."
            self.statusChanged.emit()
            return
        feeds = list(self.feeds)
        payload = {"name": str(name).strip() or url, "url": url}
        if index >= 0 and index < len(feeds):
            feeds[index] = payload
            message = f"Updated feed {payload['name']}."
        else:
            feeds.append(payload)
            message = f"Added feed {payload['name']}."
        self._rss()["feeds"] = feeds
        self._save(message)

    @pyqtSlot(int)
    def removeFeed(self, index: int) -> None:
        feeds = list(self.feeds)
        if index < 0 or index >= len(feeds):
            return
        removed = feeds.pop(index)
        self._rss()["feeds"] = feeds
        self._save(f"Removed feed {removed.get('name', 'feed')}.")

    @pyqtSlot(str, str)
    def setCredentials(self, username: str, password: str) -> None:
        rss = self._rss()
        rss["username"] = str(username).strip()
        rss["password"] = str(password)
        self._save("RSS credentials updated.")

    @pyqtSlot(str)
    def setOpmlSource(self, value: str) -> None:
        self._rss()["opml_source"] = str(value).strip()
        self._save("OPML source updated.")

    @pyqtSlot(int)
    def setItemLimit(self, value: int) -> None:
        self._rss()["item_limit"] = max(3, min(50, int(value)))
        self._save(f"RSS item limit set to {int(value)}.")

    @pyqtSlot(int)
    def setCheckInterval(self, value: int) -> None:
        self._rss()["check_interval_minutes"] = max(5, min(180, int(value)))
        self._save(f"RSS checks now run every {int(value)} minute(s).")

    @pyqtSlot(bool)
    def setNotifyNewItems(self, enabled: bool) -> None:
        self._rss()["notify_new_items"] = bool(enabled)
        self._save("RSS notifications are enabled." if enabled else "RSS notifications are paused.")

    @pyqtSlot(bool)
    def setPlayNotificationSound(self, enabled: bool) -> None:
        self._rss()["play_notification_sound"] = bool(enabled)
        self._save("RSS notification sound enabled." if enabled else "RSS notification sound disabled.")

    @pyqtSlot(bool)
    def setShowFeedName(self, enabled: bool) -> None:
        self._rss()["show_feed_name"] = bool(enabled)
        self._save("Feed source labels updated.")

    @pyqtSlot(bool)
    def setShowImages(self, enabled: bool) -> None:
        self._rss()["show_images"] = bool(enabled)
        self._save("RSS thumbnail visibility updated.")

    @pyqtSlot(bool)
    def setOpenInBrowser(self, enabled: bool) -> None:
        self._rss()["open_in_browser"] = bool(enabled)
        self._save("Link open behavior updated.")

    @pyqtSlot(str)
    def setSortMode(self, value: str) -> None:
        value = str(value).strip().lower()
        if value not in {"newest", "oldest", "byfeed"}:
            value = "newest"
        self._rss()["sort_mode"] = value
        self._save("RSS sort order updated.")

    @pyqtSlot(int)
    def setMaxPerFeed(self, value: int) -> None:
        self._rss()["max_per_feed"] = max(1, min(20, int(value)))
        self._save("Per-feed item cap updated.")

    @pyqtSlot(str)
    def setViewMode(self, value: str) -> None:
        value = str(value).strip().lower()
        if value not in {"compact", "expanded"}:
            value = "expanded"
        self._rss()["view_mode"] = value
        self._save("RSS view mode updated.")


def create_rss_settings_widget(parent: QWidget, settings_state: dict, save_callback, status_callback) -> tuple[QQuickWidget, RssSettingsBridge]:
    bridge = RssSettingsBridge(settings_state, save_callback, status_callback)
    widget = QQuickWidget(parent)
    widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    widget.setClearColor(QColor(0, 0, 0, 0))
    theme = load_theme_palette()
    theme_map = {
        "primary": theme.primary,
        "text": theme.text,
        "mutedText": theme.text_muted,
        "panel": rgba(theme.surface_container_high, 0.88),
        "panelAlt": rgba(blend(theme.surface_container, theme.surface, 0.35), 0.90),
        "card": rgba(theme.surface_container_high, 0.82),
        "cardBorder": rgba(theme.outline, 0.18),
        "chip": rgba(theme.primary, 0.14),
        "chipBorder": rgba(theme.primary, 0.22),
    }
    widget.rootContext().setContextProperty("rssSettings", bridge)
    widget.rootContext().setContextProperty("rssTheme", theme_map)
    widget.setSource(QUrl.fromLocalFile(str(_rss_settings_qml_file())))
    widget.setMinimumHeight(920)
    return widget, bridge
