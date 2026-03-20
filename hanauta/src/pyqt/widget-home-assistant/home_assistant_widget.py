#!/usr/bin/env python3
from __future__ import annotations

import json
import signal
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QFontDatabase, QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QApplication


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
QML_FILE = Path(__file__).resolve().with_suffix(".qml")
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_PAGE = APP_DIR / "pyqt" / "settings-page" / "settings.py"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.home_assistant import (
    entity_action,
    entity_attributes_text,
    entity_domain,
    entity_friendly_name,
    entity_icon_name,
    icon_source_for_entity,
    entity_relative_update_text,
    entity_secondary_text,
    entity_state_label,
    load_service_home_assistant_cache,
    normalize_ha_url,
    post_home_assistant_json,
)
from pyqt.shared.runtime import entry_command
from pyqt.shared.theme import blend, load_theme_palette, rgba


MATERIAL_ICONS = {
    "close": "\ue5cd",
    "settings": "\ue8b8",
    "refresh": "\ue5d5",
    "search": "\ue8b6",
    "home": "\ue88a",
    "person": "\ue7fd",
    "lightbulb": "\ue0f0",
    "toggle_on": "\ue9f6",
    "videocam": "\ue04b",
    "thermostat": "\ue1ff",
    "device_thermostat": "\ue1ff",
    "sensors": "\ue51e",
    "lock": "\ue897",
    "music_note": "\ue405",
    "window": "\uefe8",
    "mode_fan": "\uf168",
    "auto_awesome": "\ue65f",
    "bolt": "\uea0b",
    "location_on": "\ue0c8",
    "light_mode": "\ue518",
    "partly_cloudy_day": "\uf172",
    "shield": "\ue9e0",
    "water_drop": "\ue798",
    "push_pin": "\uef3e",
    "push_pin_outline": "\uf10f",
    "play_arrow": "\ue037",
    "chevron_right": "\ue5cc",
    "expand_more": "\ue5cf",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
    }
    for key, path in font_map.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    text = str(color or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return (255, 255, 255)
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except Exception:
        return (255, 255, 255)


def _relative_luminance(color: str) -> float:
    def channel(value: int) -> float:
        srgb = value / 255.0
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = _hex_to_rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _is_dark(color: str) -> bool:
    return _relative_luminance(color) < 0.42


def load_settings_state() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    services = payload.get("services", {})
    if not isinstance(services, dict):
        services = {}
    payload["services"] = services
    home_assistant = payload.get("home_assistant", {})
    if not isinstance(home_assistant, dict):
        home_assistant = {}
    home_assistant.setdefault("url", "")
    home_assistant.setdefault("token", "")
    pinned = home_assistant.get("pinned_entities", [])
    home_assistant["pinned_entities"] = [item for item in pinned if isinstance(item, str)]
    payload["home_assistant"] = home_assistant
    return payload


def save_settings_state(payload: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class Backend(QObject):
    entitiesChanged = pyqtSignal()
    pinnedEntitiesChanged = pyqtSignal()
    statusChanged = pyqtSignal()
    searchQueryChanged = pyqtSignal()
    busyChanged = pyqtSignal()
    closeRequested = pyqtSignal()

    def __init__(self, *, icon_tint: str = "#D0BCFF") -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.material_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self._icon_tint = str(icon_tint).strip() or "#D0BCFF"
        self._settings = load_settings_state()
        self._entities_raw: list[dict] = []
        self._entities: list[dict[str, object]] = []
        self._pinned_entities: list[dict[str, object]] = []
        self._favorite_entities: list[dict[str, object]] = []
        self._search_query = ""
        self._busy = False
        self._available = False
        self._latency_ms = -1
        self._headline = "Home Assistant unavailable"
        self._hint = "Save your URL and long-lived token in Settings to begin monitoring."
        self.refresh()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(15000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()

    def _service_enabled(self) -> bool:
        services = self._settings.get("services", {})
        if not isinstance(services, dict):
            return True
        service = services.get("home_assistant", {})
        if not isinstance(service, dict):
            return True
        return bool(service.get("enabled", True))

    def _rebuild_views(self) -> None:
        query = self._search_query.strip().lower()
        pinned_ids = self._settings.get("home_assistant", {}).get("pinned_entities", [])
        pinned_list = [item for item in pinned_ids if isinstance(item, str)]
        pinned_set = set(pinned_list)

        mapped: list[dict[str, object]] = []
        pinned_map: dict[str, dict[str, object]] = {}

        for entity in self._entities_raw:
            entity_id = str(entity.get("entity_id", "")).strip()
            if not entity_id:
                continue

            name = entity_friendly_name(entity)
            domain = entity_domain(entity_id)
            state_label = entity_state_label(entity)
            secondary = entity_secondary_text(entity)
            details = entity_attributes_text(entity)
            icon_name = entity_icon_name(entity)
            action = entity_action(entity)
            raw_state = str(entity.get("state", "")).strip().lower()

            item = {
                "entityId": entity_id,
                "friendlyName": name,
                "domain": domain,
                "domainLabel": domain.replace("_", " ").title() or "Entity",
                "state": state_label,
                "secondary": secondary,
                "details": details,
                "updatedText": entity_relative_update_text(entity),
                "iconName": icon_name,
                "iconGlyph": material_icon(icon_name),
                "iconSource": icon_source_for_entity(entity, tint_color=self._icon_tint),
                "favoriteIconSource": icon_source_for_entity(entity, tint_color="#F5F7FF"),
                "isPinned": entity_id in pinned_set,
                "canToggle": action is not None,
                "actionLabel": (
                    "Run"
                    if action and action[1] == "turn_on" and domain in {"script", "scene"}
                    else ("Turn off" if action and raw_state == "on" else "Turn on")
                ),
                "stateTone": (
                    "active"
                    if raw_state in {"on", "playing", "home", "open", "armed_away", "armed_home", "unlocked"}
                    else "idle"
                ),
                "rawState": str(entity.get("state", "")).strip(),
            }

            haystack = " ".join(
                (name, entity_id, domain, secondary, details, str(entity.get("state", "")))
            ).lower()

            if not query or query in haystack:
                mapped.append(item)

            if entity_id in pinned_set:
                pinned_map[entity_id] = item

        self._entities = mapped
        self._pinned_entities = [pinned_map[entity_id] for entity_id in pinned_list if entity_id in pinned_map][:5]
        favorite_items = [
            item for item in mapped
            if bool(item.get("canToggle")) and not bool(item.get("isPinned"))
        ]
        self._favorite_entities = favorite_items[:6]
        self.entitiesChanged.emit()
        self.pinnedEntitiesChanged.emit()

    def _set_status(self, headline: str, hint: str) -> None:
        self._headline = headline
        self._hint = hint
        self.statusChanged.emit()

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busyChanged.emit()

    @pyqtProperty(str, constant=True)
    def uiFontFamily(self) -> str:
        return self.ui_font

    @pyqtProperty(str, constant=True)
    def displayFontFamily(self) -> str:
        return self.display_font

    @pyqtProperty(str, constant=True)
    def materialFontFamily(self) -> str:
        return self.material_font

    @pyqtProperty("QVariantList", notify=entitiesChanged)
    def entities(self) -> list[dict[str, object]]:
        return self._entities

    @pyqtProperty("QVariantList", notify=pinnedEntitiesChanged)
    def pinnedEntities(self) -> list[dict[str, object]]:
        return self._pinned_entities

    @pyqtProperty("QVariantList", notify=entitiesChanged)
    def favoriteEntities(self) -> list[dict[str, object]]:
        return self._favorite_entities

    @pyqtProperty(str, notify=statusChanged)
    def statusHeadline(self) -> str:
        return self._headline

    @pyqtProperty(str, notify=statusChanged)
    def statusHint(self) -> str:
        return self._hint

    @pyqtProperty(bool, notify=statusChanged)
    def available(self) -> bool:
        return self._available

    @pyqtProperty(int, notify=statusChanged)
    def latencyMs(self) -> int:
        return self._latency_ms

    @pyqtProperty(str, notify=searchQueryChanged)
    def searchQuery(self) -> str:
        return self._search_query

    @pyqtProperty(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @pyqtSlot(str, result=str)
    def materialIcon(self, name: str) -> str:
        return material_icon(name)

    @pyqtSlot(str)
    def setSearchQuery(self, query: str) -> None:
        query = str(query)
        if query == self._search_query:
            return
        self._search_query = query
        self.searchQueryChanged.emit()
        self._rebuild_views()

    @pyqtSlot()
    def refresh(self) -> None:
        self._settings = load_settings_state()

        if not self._service_enabled():
            self._available = False
            self._latency_ms = -1
            self._entities_raw = []
            self._rebuild_views()
            self._set_status(
                "Home Assistant is disabled",
                "Enable the integration in Settings to show entities here.",
            )
            return

        base_url = normalize_ha_url(self._settings.get("home_assistant", {}).get("url", ""))
        token = str(self._settings.get("home_assistant", {}).get("token", "")).strip()

        if not base_url or not token:
            self._available = False
            self._latency_ms = -1
            self._entities_raw = []
            self._rebuild_views()
            self._set_status(
                "Home Assistant unavailable",
                "Add your server URL and long-lived token in Settings.",
            )
            return

        cache = load_service_home_assistant_cache(base_url)
        payload = cache.get("payload") if isinstance(cache, dict) else None
        updated_at = str(cache.get("updated_at", "")).strip() if isinstance(cache, dict) else ""

        if not isinstance(payload, list):
            self._available = False
            if not self._entities_raw:
                self._entities_raw = []
            self._rebuild_views()
            self._set_status(
                "Waiting for hanauta-service",
                "Home Assistant entities are being prepared in the background cache.",
            )
            return

        entities = [
            item for item in payload
            if isinstance(item, dict) and str(item.get("entity_id", "")).strip()
        ]
        entities.sort(key=lambda item: entity_friendly_name(item).lower())

        self._available = True
        self._latency_ms = -1
        self._entities_raw = entities
        self._rebuild_views()

        pinned_count = len(self._settings.get("home_assistant", {}).get("pinned_entities", []))
        cache_text = f"cached {updated_at}" if updated_at else "served from hanauta-service cache"
        self._set_status(
            f"Monitoring {len(entities)} entities",
            f"{min(pinned_count, 5)} pinned shortcuts • {cache_text}",
        )

    @pyqtSlot(str)
    def togglePinned(self, entity_id: str) -> None:
        entity_id = str(entity_id).strip()
        if not entity_id:
            return

        home_assistant = self._settings.setdefault("home_assistant", {})
        if not isinstance(home_assistant, dict):
            home_assistant = {}
            self._settings["home_assistant"] = home_assistant

        pinned = [item for item in home_assistant.get("pinned_entities", []) if isinstance(item, str)]

        if entity_id in pinned:
            pinned = [item for item in pinned if item != entity_id]
            message = "Entity removed from pinned shortcuts."
        else:
            if len(pinned) >= 5:
                self._set_status(
                    "Pinned shortcuts are full",
                    "You can pin up to five Home Assistant entities.",
                )
                return
            pinned.append(entity_id)
            message = "Entity pinned to the Home Assistant shortcuts row."

        home_assistant["pinned_entities"] = pinned
        save_settings_state(self._settings)
        self._rebuild_views()
        self._set_status(self._headline, message)

    @pyqtSlot(str)
    def activateEntity(self, entity_id: str) -> None:
        entity_id = str(entity_id).strip()
        entity = next(
            (item for item in self._entities_raw if str(item.get("entity_id", "")).strip() == entity_id),
            None,
        )
        if entity is None:
            self._set_status("Entity unavailable", "That Home Assistant entity is no longer loaded.")
            return

        action = entity_action(entity)
        if action is None:
            self._set_status(entity_friendly_name(entity), "This entity is view-only right now.")
            return

        service_domain, service_name, payload = action
        base_url = normalize_ha_url(self._settings.get("home_assistant", {}).get("url", ""))
        token = str(self._settings.get("home_assistant", {}).get("token", "")).strip()

        _result, error_text = post_home_assistant_json(
            base_url,
            token,
            f"/api/services/{service_domain}/{service_name}",
            payload,
        )
        if error_text:
            self._set_status("Action failed", error_text)
            return

        self._set_status(
            entity_friendly_name(entity),
            f"{service_name.replace('_', ' ').title()} sent to {entity_id}.",
        )
        QTimer.singleShot(900, self.refresh)

    @pyqtSlot()
    def openSettings(self) -> None:
        command = entry_command(SETTINGS_PAGE, "--page", "services", "--service-section", "home_assistant")
        if not command:
            return
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    @pyqtSlot()
    def closeWindow(self) -> None:
        self.closeRequested.emit()
        QGuiApplication.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta Home Assistant")
    app.setQuitOnLastWindowClosed(False)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())

    if not QML_FILE.exists():
        print(f"ERROR: QML file not found: {QML_FILE}", file=sys.stderr)
        return 2

    theme = load_theme_palette()

    panel_start_base = blend(theme.surface_container_high, theme.surface_container, 0.30)
    panel_end_base = blend(theme.surface_container, theme.surface, 0.24)
    card_base = blend(theme.surface_container_high, theme.surface_container, 0.42)
    card_strong_base = blend(theme.surface_container_high, theme.surface_container, 0.58)
    field_base = blend(theme.surface_container_high, theme.surface_container, 0.52)
    panel_reference = blend(panel_start_base, panel_end_base, 0.5)
    dark_mode_surface = _is_dark(panel_reference)
    fg = "#F5F7FF" if dark_mode_surface else "#15181E"
    fg_muted = "#C9D1E2" if dark_mode_surface else "#4D5562"
    icon_tint = "#E4EBFF" if dark_mode_surface else blend(theme.primary, "#2A3140", 0.62)
    on_primary = "#08111F" if _is_dark(theme.primary) else "#F7FAFF"

    theme_map = {
        "primary": theme.primary,
        "onPrimary": on_primary,
        "text": fg,
        "textMuted": fg_muted,
        "surface": theme.surface,
        "surfaceContainer": theme.surface_container,
        "surfaceContainerHigh": theme.surface_container_high,
        "outline": theme.outline,
        "panelStart": rgba(panel_start_base, 0.98),
        "panelEnd": rgba(panel_end_base, 0.95),
        "card": rgba(card_base, 0.92),
        "cardStrong": rgba(card_strong_base, 0.96),
        "field": rgba(field_base, 0.98),
        "border": rgba(theme.outline, 0.18),
        "heroStart": rgba(theme.primary_container, 0.40),
        "heroEnd": rgba(blend(theme.secondary, theme.surface_container_high, 0.30), 0.94),
        "active": rgba(theme.primary, 0.16),
        "activeBorder": rgba(theme.primary, 0.40),
        "hover": rgba(theme.primary, 0.13),
        "pressed": rgba(theme.primary, 0.20),
        "iconTint": icon_tint,
        "iconMuted": rgba(fg_muted, 0.96),
        "good": "#78d8a0",
        "warning": "#ffce73",
        "danger": "#ff8f8f",
        "surfaceIsDark": dark_mode_surface,
    }

    engine = QQmlApplicationEngine()
    backend = Backend(icon_tint=str(icon_tint))
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("themeModel", theme_map)

    current_root: dict[str, object | None] = {"window": None}
    qml_mtime = QML_FILE.stat().st_mtime_ns

    def _position_root(window: object) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = int(window.property("width"))
        window.setProperty("x", available.x() + available.width() - width - 46)
        window.setProperty("y", available.y() + 88)

    def _load_qml() -> bool:
        existing = current_root.get("window")
        if existing is not None:
            try:
                existing.setProperty("visible", False)
            except Exception:
                pass
            try:
                existing.close()
            except Exception:
                pass
            try:
                existing.deleteLater()
            except Exception:
                pass

        engine.clearComponentCache()
        engine.load(QUrl.fromLocalFile(str(QML_FILE)))
        roots = engine.rootObjects()
        if not roots:
            return False
        root = roots[-1]
        current_root["window"] = root
        _position_root(root)
        return True

    if not _load_qml():
        print("ERROR: failed to load Home Assistant widget QML.", file=sys.stderr)
        return 3

    qml_reload_timer = QTimer()
    qml_reload_timer.setInterval(1200)

    def _maybe_reload_qml() -> None:
        nonlocal qml_mtime
        try:
            current_mtime = QML_FILE.stat().st_mtime_ns
        except FileNotFoundError:
            return
        if current_mtime == qml_mtime:
            return
        qml_mtime = current_mtime
        _load_qml()

    qml_reload_timer.timeout.connect(_maybe_reload_qml)
    qml_reload_timer.start()

    backend.closeRequested.connect(app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
