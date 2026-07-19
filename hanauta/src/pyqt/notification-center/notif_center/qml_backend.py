from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from time import monotonic

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot

from notif_center.ha import fetch_home_assistant_json, normalize_ha_url, post_home_assistant_json
from notif_center.paths import FONTS_DIR, ROOT, SCRIPTS_DIR, SERVICE_STATE_DIR, SETTINGS_PAGE_SCRIPT
from notif_center.poller import BackgroundPoller, PollResult, get_static_val, poll_all
from notif_center.settings_io import (
    load_notification_settings,
    merged_service_settings,
    save_notification_settings,
)
from notif_center.utils import (
    format_millis,
    load_app_fonts,
    detect_font,
    material_icon,
    notification_control_command,
    parse_bool_text,
    run_bg,
    run_cmd,
    run_script_bg,
)
from pyqt.shared.runtime import entry_command, entry_patterns, python_executable
from pyqt.shared.theme import load_theme_palette, palette_mtime, pick_foreground, rgba, theme_font_family

_SERVICE_KEY_MAP = {
    "vpn_control": ("VPN Control", "Encrypted tunnel", "lock", "vpn_control"),
    "christian_widget": ("Christian Widget", "Daily devotionals", "auto_awesome", "christian_widget"),
    "reminders_widget": ("Reminders", "Task management", "notifications", "reminders_widget"),
    "pomodoro_widget": ("Pomodoro", "Focus timer", "timer", "pomodoro_widget"),
    "rss_widget": ("RSS Feed", "News reader", "public", "rss_widget"),
    "obs_widget": ("OBS Control", "Stream control", "videocam", "obs_widget"),
    "crypto_widget": ("Crypto", "Market prices", "show_chart", "crypto_widget"),
    "vps_widget": ("VPS Monitor", "Server status", "storage", "vps_widget"),
    "desktop_clock_widget": ("Desktop Clock", "Always-on-top clock", "watch", "desktop_clock_widget"),
    "game_mode": ("Game Mode", "Performance profile", "sports_esports", "game_mode"),
}


def _format_uptime(seconds: int) -> str:
    if seconds < 60:
        return "less than a minute"
    total_minutes = seconds // 60
    hours = total_minutes // 60
    minutes = total_minutes % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "less than a minute"


class ColorPalette(QObject):
    _changed = pyqtSignal()

    def __init__(self, theme: object, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._panel_bg = "#211F26"
        self._panel_border = "rgba(147, 143, 153, 0.28)"
        self._card_bg = "rgba(20, 18, 24, 0.72)"
        self._card_strong_bg = "rgba(43, 41, 48, 0.92)"
        self._hover_bg = "rgba(208, 188, 255, 0.14)"
        self._accent_soft = "rgba(208, 188, 255, 0.18)"
        self._primary = "#D0BCFF"
        self._tertiary = "#EFB8C8"
        self._on_primary = "#381E72"
        self._text = "#E6E0E9"
        self._text_muted = "rgba(202, 196, 208, 0.78)"
        self._icon = "#E6E0E9"
        self._inactive = "rgba(202, 196, 208, 0.68)"
        self._danger_fg = "#F2B8B5"
        self._danger_bg = "rgba(242, 184, 181, 0.18)"
        self._play_fg = "#381E72"
        self._media_start = "rgba(79, 55, 139, 0.96)"
        self._media_end = "rgba(192, 187, 220, 0.96)"
        self._media_border = "rgba(208, 188, 255, 0.72)"
        self._phone_online = "#D0BCFF"
        self._phone_offline = "rgba(230, 224, 233, 0.18)"
        self.apply_theme(theme)

    def apply_theme(self, theme: object) -> None:
        error_hex = getattr(theme, "error", "#F2B8B5")
        active_text = getattr(theme, "active_text", None)
        if active_text is None:
            bg = getattr(theme, "primary", "#D0BCFF")
            on = getattr(theme, "on_primary", "#381E72")
            active_text = pick_foreground(bg, on, "#101114")
        self._panel_bg = getattr(theme, "panel_bg", "#211F26")
        self._panel_border = getattr(theme, "panel_border", "rgba(147, 143, 153, 0.28)")
        self._card_bg = rgba(getattr(theme, "surface", "#141218"), 0.72)
        self._card_strong_bg = rgba(getattr(theme, "surface_container_high", "#2B2930"), 0.92)
        self._hover_bg = getattr(theme, "hover_bg", "rgba(208, 188, 255, 0.14)")
        self._accent_soft = getattr(theme, "accent_soft", "rgba(208, 188, 255, 0.18)")
        self._primary = getattr(theme, "primary", "#D0BCFF")
        self._tertiary = getattr(theme, "tertiary", "#EFB8C8")
        self._on_primary = active_text
        self._text = getattr(theme, "text", "#E6E0E9")
        self._text_muted = getattr(theme, "text_muted", "rgba(202, 196, 208, 0.78)")
        self._icon = self._text
        self._inactive = getattr(theme, "inactive", "rgba(202, 196, 208, 0.68)")
        self._danger_fg = error_hex
        self._danger_bg = rgba(error_hex, 0.18)
        self._play_fg = active_text
        self._media_start = getattr(theme, "media_active_start", "rgba(79, 55, 139, 0.96)")
        self._media_end = getattr(theme, "media_active_end", "rgba(192, 187, 220, 0.96)")
        self._media_border = getattr(theme, "media_active_border", "rgba(208, 188, 255, 0.72)")
        self._phone_online = getattr(theme, "primary", "#D0BCFF")
        self._phone_offline = rgba(getattr(theme, "on_surface", "#E6E0E9"), 0.18)
        self._changed.emit()

    @pyqtProperty(str, notify=_changed)
    def panelBg(self) -> str:
        return self._panel_bg

    @pyqtProperty(str, notify=_changed)
    def panelBorder(self) -> str:
        return self._panel_border

    @pyqtProperty(str, notify=_changed)
    def cardBg(self) -> str:
        return self._card_bg

    @pyqtProperty(str, notify=_changed)
    def cardStrongBg(self) -> str:
        return self._card_strong_bg

    @pyqtProperty(str, notify=_changed)
    def hoverBg(self) -> str:
        return self._hover_bg

    @pyqtProperty(str, notify=_changed)
    def accentSoft(self) -> str:
        return self._accent_soft

    @pyqtProperty(str, notify=_changed)
    def primary(self) -> str:
        return self._primary

    @pyqtProperty(str, notify=_changed)
    def tertiary(self) -> str:
        return self._tertiary

    @pyqtProperty(str, notify=_changed)
    def onPrimary(self) -> str:
        return self._on_primary

    @pyqtProperty(str, notify=_changed)
    def text(self) -> str:
        return self._text

    @pyqtProperty(str, notify=_changed)
    def textMuted(self) -> str:
        return self._text_muted

    @pyqtProperty(str, notify=_changed)
    def icon(self) -> str:
        return self._icon

    @pyqtProperty(str, notify=_changed)
    def inactive(self) -> str:
        return self._inactive

    @pyqtProperty(str, notify=_changed)
    def dangerFg(self) -> str:
        return self._danger_fg

    @pyqtProperty(str, notify=_changed)
    def dangerBg(self) -> str:
        return self._danger_bg

    @pyqtProperty(str, notify=_changed)
    def playFg(self) -> str:
        return self._play_fg

    @pyqtProperty(str, notify=_changed)
    def mediaStart(self) -> str:
        return self._media_start

    @pyqtProperty(str, notify=_changed)
    def mediaEnd(self) -> str:
        return self._media_end

    @pyqtProperty(str, notify=_changed)
    def mediaBorder(self) -> str:
        return self._media_border

    @pyqtProperty(str, notify=_changed)
    def phoneOnline(self) -> str:
        return self._phone_online

    @pyqtProperty(str, notify=_changed)
    def phoneOffline(self) -> str:
        return self._phone_offline


class PhoneInfo(QObject):
    _changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = ""
        self._status = "Offline"
        self._battery = ""
        self._online = False

    def update_from_poll(self, poll_result: PollResult | None) -> None:
        raw = poll_result.phone_raw if poll_result else ""
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}
        name = str(payload.get("name", ""))
        battery = str(payload.get("battery", ""))
        status = str(payload.get("status", "Offline"))
        has_device = bool(payload.get("id")) and bool(payload.get("name"))
        online = has_device and status.lower() != "offline"
        changed = False
        if name != self._name:
            self._name = name
            changed = True
        if status != self._status:
            self._status = status
            changed = True
        if battery != self._battery:
            self._battery = battery
            changed = True
        if online != self._online:
            self._online = online
            changed = True
        if changed:
            self._changed.emit()

    @pyqtProperty(str, notify=_changed)
    def name(self) -> str:
        return self._name or "No phone connected"

    @pyqtProperty(str, notify=_changed)
    def status(self) -> str:
        return self._status

    @pyqtProperty(str, notify=_changed)
    def battery(self) -> str:
        return self._battery

    @pyqtProperty(bool, notify=_changed)
    def online(self) -> bool:
        return self._online


class NotificationCenterBackend(QObject):
    paletteChanged = pyqtSignal()
    quickSettingsChanged = pyqtSignal()
    brightnessChanged = pyqtSignal()
    volumeChanged = pyqtSignal()
    mediaChanged = pyqtSignal()
    homeAssistantChanged = pyqtSignal()
    serviceCardsChanged = pyqtSignal()
    systemOverviewChanged = pyqtSignal()
    appearanceStatusChanged = pyqtSignal()
    haSettingsChanged = pyqtSignal()
    haEntitiesChanged = pyqtSignal()
    sizeChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._phone_info = PhoneInfo(self)
        self._loaded_fonts = load_app_fonts()
        self._material_font = detect_font(
            self._loaded_fonts.get("material_icons", ""),
            self._loaded_fonts.get("material_icons_outlined", ""),
            self._loaded_fonts.get("material_symbols_outlined", ""),
            self._loaded_fonts.get("material_symbols_rounded", ""),
            "Material Icons",
            "Material Icons Outlined",
            "Material Symbols Outlined",
            "Material Symbols Rounded",
        )
        self._ui_font = detect_font(
            theme_font_family("ui"),
            "Rubik",
            self._loaded_fonts.get("ui_sans", ""),
            "Inter",
            "Noto Sans",
            "Sans Serif",
        )
        self._mono_font = detect_font(
            theme_font_family("mono"),
            "JetBrains Mono",
            "JetBrainsMono Nerd Font",
            "DejaVu Sans Mono",
        )

        self._settings_state = load_notification_settings()
        self._theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._color_palette = ColorPalette(self._theme_palette, self)
        self._accent_name = self._settings_state["appearance"].get("accent", "orchid")
        self._current_accent = {
            "accent": self._theme_palette.primary,
            "on_accent": self._theme_palette.active_text,
        }
        if self._theme_palette.use_matugen:
            self._current_accent = {
                "accent": self._theme_palette.primary,
                "on_accent": self._theme_palette.active_text,
            }

        self._username = os.environ.get("USER", "user")
        self._uptime = ""
        self._brightness = 67
        self._volume = 82
        self._media_status = "Stopped"
        self._media_title = ""
        self._media_artist = ""
        self._media_cover = ""
        self._media_progress = 0.0
        self._media_elapsed = "0:00"
        self._media_total = "0:00"
        self._media_player = ""
        self._media_position_ms = 0
        self._media_duration_ms = 0
        self._media_url = ""
        self._media_last_anchor_time = 0.0

        self._home_assistant_visible = False
        self._home_assistant_status = "Not configured"
        self._home_assistant_tiles: list[dict] = []
        self._ha_entities: list[dict] = []
        self._ha_entity_map: dict[str, dict] = {}
        self._ha_last_error = ""

        self._service_cards: list[dict] = []
        self._system_overview: list[dict] = []
        self._appearance_status = ""
        self._ha_url = self._settings_state["home_assistant"].get("url", "")
        self._ha_token = self._settings_state["home_assistant"].get("token", "")
        self._ha_settings_status = ""
        self._ha_entities_list: list[dict] = []

        nc_cfg = self._settings_state.get("notification_center", {})
        self._nc_width = nc_cfg.get("width", 800)
        self._nc_height = nc_cfg.get("height", 740)

        self._poll_result: PollResult | None = None
        self._apply_color_palette()
        self._build_service_cards()

        self._poller = BackgroundPoller()
        self._poller.pollComplete.connect(self._on_poll_complete)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_media_progress)
        self._poll_timer.start(1000)

        self._theme_timer = QTimer(self)
        self._theme_timer.timeout.connect(self._reload_theme_if_needed)
        self._theme_timer.start(3000)

        self._ha_timer = QTimer(self)
        self._ha_timer.timeout.connect(self._refresh_home_assistant_entities)
        self._ha_timer.start(15000)

        self._poller.start()
        self._poller_warm_up()

    def _poller_warm_up(self) -> None:
        result = poll_all()
        self._poll_result = result
        self._on_poll_complete(result)

    def _apply_color_palette(self) -> None:
        self._color_palette.apply_theme(self._theme_palette)
        self.paletteChanged.emit()

    def _build_service_cards(self) -> None:
        cards: list[dict] = []
        for key, (title, detail, icon, _) in _SERVICE_KEY_MAP.items():
            svc = self._settings_state.get("services", {}).get(key, {})
            enabled = bool(svc.get("enabled", True))
            show_in_nc = bool(svc.get("show_in_notification_center", False))
            if enabled and show_in_nc:
                cards.append({"icon": icon, "title": title, "detail": detail, "key": key})
        self._service_cards = cards
        self.serviceCardsChanged.emit()

    def _on_poll_complete(self, result: PollResult) -> None:
        self._poll_result = result
        self._username = os.environ.get("USER", "user")
        new_uptime = _format_uptime(result.uptime_seconds)
        if new_uptime != self._uptime:
            self._uptime = new_uptime
        new_bright = result.brightness
        if new_bright != self._brightness:
            self._brightness = new_bright
            self.brightnessChanged.emit()
        new_vol = result.volume
        if new_vol != self._volume:
            self._volume = new_vol
            self.volumeChanged.emit()
        self._apply_quick_settings_from_poll(result)
        self._apply_media_from_poll(result)
        self._phone_info.update_from_poll(result)
        self._refresh_system_overview()
        if not self._home_assistant_visible:
            ha_cfg = self._settings_state.get("home_assistant", {})
            if ha_cfg.get("url") and ha_cfg.get("token"):
                self._home_assistant_visible = True
                self._home_assistant_status = "Connected"
                self.homeAssistantChanged.emit()
                QTimer.singleShot(200, self._refresh_home_assistant_entities)
            else:
                self._home_assistant_visible = False
                self.homeAssistantChanged.emit()
        self._update_appearance_status()

    def _apply_quick_settings_from_poll(self, r: PollResult) -> None:
        from app_locale import t
        qs = [
            {
                "key": "wifi",
                "title": "Wi-Fi",
                "subtitle": r.wifi_ssid if r.wifi_on else "Disconnected",
                "icon": "wifi",
                "active": r.wifi_on,
            },
            {
                "key": "bluetooth",
                "title": "Bluetooth",
                "subtitle": "Connected" if r.bt_on else "Off",
                "icon": "bluetooth",
                "active": r.bt_on,
            },
            {
                "key": "dnd",
                "title": "Do Not Disturb",
                "subtitle": "On" if r.dnd_on else "Off",
                "icon": "do_not_disturb_on",
                "active": r.dnd_on,
            },
            {
                "key": "airplane",
                "title": "Airplane Mode",
                "subtitle": "On" if r.airplane_on else "Off",
                "icon": "airplanemode_active",
                "active": r.airplane_on,
            },
            {
                "key": "night",
                "title": "Night Light",
                "subtitle": "On" if r.night_on else "Off",
                "icon": "nightlight",
                "active": r.night_on,
            },
            {
                "key": "caffeine",
                "title": "Caffeine",
                "subtitle": "On" if r.caffeine_on else "Off",
                "icon": "coffee",
                "active": r.caffeine_on,
            },
        ]
        self._quick_settings = qs
        self.quickSettingsChanged.emit()

    def _apply_media_from_poll(self, r: PollResult) -> None:
        player = r.media_player
        status = r.media_status or "Stopped"
        title = r.media_title or ""
        artist = r.media_artist or ""
        art = r.media_art or ""
        media_url = r.media_url or ""
        changed = False
        if player != self._media_player:
            self._media_player = player
            changed = True
        if status != self._media_status:
            self._media_status = status
            changed = True
        if title != self._media_title:
            self._media_title = title
            changed = True
        if artist != self._media_artist:
            self._media_artist = artist
            changed = True
        if r.media_duration_ms != self._media_duration_ms:
            self._media_duration_ms = r.media_duration_ms
            changed = True
        if r.media_position_ms > 0:
            self._media_position_ms = r.media_position_ms
            self._media_last_anchor_time = r.timestamp
            changed = True
        cover = ""
        if art:
            p = Path(art)
            if p.exists():
                cover = str(p)
        if cover != self._media_cover:
            self._media_cover = cover
            changed = True
        if media_url != self._media_url:
            self._media_url = media_url
        if changed:
            self._update_media_progress_display()
            self.mediaChanged.emit()

    def _poll_media_progress(self) -> None:
        if self._media_status != "Playing" or self._media_duration_ms <= 0:
            return
        if self._media_last_anchor_time > 0:
            elapsed_since = max(0.0, monotonic() - self._media_last_anchor_time)
            self._media_position_ms = min(
                self._media_duration_ms,
                max(0, self._media_position_ms + int(elapsed_since * 1000)),
            )
            self._media_last_anchor_time = monotonic()
        self._update_media_progress_display()
        self.mediaChanged.emit()

    def _update_media_progress_display(self) -> None:
        self._media_elapsed = format_millis(self._media_position_ms)
        self._media_total = format_millis(self._media_duration_ms)
        if self._media_duration_ms > 0:
            self._media_progress = max(
                0.0, min(1.0, self._media_position_ms / self._media_duration_ms)
            )
        else:
            self._media_progress = 0.0

    def _refresh_system_overview(self) -> None:
        r = self._poll_result
        self._system_overview = [
            {"label": "Host", "value": get_static_val("hostname", ["hostname"]) or "unknown"},
            {"label": "Kernel", "value": get_static_val("kernel", ["uname", "-r"]) or "unknown"},
            {"label": "Session", "value": os.environ.get("XDG_SESSION_DESKTOP", "i3")},
            {"label": "Python", "value": sys.version.split()[0]},
            {"label": "Uptime", "value": _format_uptime(r.uptime_seconds if r else 0)},
            {"label": "Screen", "value": f"{self._nc_width}x{self._nc_height}"},
        ]
        self.systemOverviewChanged.emit()

    def _update_appearance_status(self) -> None:
        matugen = self._theme_palette.use_matugen
        accent_name = self._accent_name.title()
        if matugen:
            self._appearance_status = (
                f"Matugen palette active. Using dynamic colors from wallpaper. "
                f"Base accent: {accent_name}."
            )
        else:
            self._appearance_status = (
                f"Using {accent_name} accent preset. Matugen is off."
            )
        self.appearanceStatusChanged.emit()

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self._theme_palette = load_theme_palette()
        if self._theme_palette.use_matugen:
            self._current_accent = {
                "accent": self._theme_palette.primary,
                "on_accent": self._theme_palette.active_text,
            }
        self._apply_color_palette()

    def _refresh_home_assistant_entities(self) -> None:
        ha_cfg = self._settings_state.get("home_assistant", {})
        base_url = normalize_ha_url(ha_cfg.get("url", ""))
        token = ha_cfg.get("token", "")
        if not base_url or not token:
            self._ha_entities = []
            self._ha_entity_map = {}
            self._ha_entities_list = []
            self.haEntitiesChanged.emit()
            return
        import threading

        def fetch() -> None:
            try:
                payload, error_text = fetch_home_assistant_json(base_url, token, "/api/states")
            except Exception:
                payload, error_text = None, "Unable to reach Home Assistant."
            QTimer.singleShot(0, lambda: self._on_ha_fetch_done(payload, error_text))

        threading.Thread(target=fetch, daemon=True).start()

    def _on_ha_fetch_done(self, payload, error_text: str) -> None:
        self._ha_last_error = error_text
        if error_text or not isinstance(payload, list):
            self._ha_entities = []
            self._ha_entity_map = []
            self._ha_entities_list = []
            self._ha_settings_status = error_text or "Failed to load entities."
            self.haEntitiesChanged.emit()
            self.haSettingsChanged.emit()
            return
        self._ha_entities = sorted(
            [item for item in payload if isinstance(item, dict)],
            key=lambda item: str(item.get("entity_id", "")),
        )
        self._ha_entity_map = {
            str(item.get("entity_id", "")): item for item in self._ha_entities
        }
        self._ha_settings_status = "Entities loaded successfully."
        self.haSettingsChanged.emit()
        self._refresh_ha_entity_list()
        self._refresh_home_assistant_tiles()

    def _refresh_ha_entity_list(self) -> None:
        pinned = set(self._settings_state["home_assistant"].get("pinned_entities", []))
        entities_list: list[dict] = []
        for entity in self._ha_entities[:80]:
            entity_id = str(entity.get("entity_id", ""))
            state = str(entity.get("state", "unknown"))
            attrs = entity.get("attributes", {}) or {}
            name = str(attrs.get("friendly_name", entity_id))
            entities_list.append({
                "name": name,
                "entity_id": entity_id,
                "state": state,
                "pinned": entity_id in pinned,
            })
        self._ha_entities_list = entities_list
        self.haEntitiesChanged.emit()

    def _refresh_home_assistant_tiles(self) -> None:
        pinned = self._settings_state["home_assistant"].get("pinned_entities", [])
        ha_cfg = self._settings_state.get("home_assistant", {})
        has_url = bool(ha_cfg.get("url"))
        self._home_assistant_visible = has_url
        tiles: list[dict] = []
        for entity_id in pinned:
            entity = self._ha_entity_map.get(entity_id, {})
            attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
            name = str(attrs.get("friendly_name", entity_id))
            state = (
                str(entity.get("state", "Unavailable"))
                if isinstance(entity, dict)
                else "Unavailable"
            )
            domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
            icon = {
                "light": "lightbulb",
                "switch": "tune",
                "climate": "thermostat",
                "camera": "camera_alt",
            }.get(domain, "home")
            tiles.append({
                "icon": icon,
                "title": name[:16],
                "subtitle": state[:16],
                "enabled": True,
            })
        if has_url:
            if not tiles:
                self._home_assistant_status = "No entities pinned"
            else:
                self._home_assistant_status = f"{len(tiles)} pinned entities"
        else:
            self._home_assistant_status = "Not configured"
        self._home_assistant_tiles = tiles
        self.homeAssistantChanged.emit()

    @pyqtProperty(object, notify=paletteChanged)
    def palette(self) -> ColorPalette:
        return self._color_palette

    @pyqtProperty(str, notify=paletteChanged)
    def materialFontFamily(self) -> str:
        return self._material_font

    @pyqtProperty(str, notify=paletteChanged)
    def uiFontFamily(self) -> str:
        return self._ui_font

    @pyqtProperty(str, notify=paletteChanged)
    def monoFontFamily(self) -> str:
        return self._mono_font

    @pyqtProperty(str, notify=quickSettingsChanged)
    def username(self) -> str:
        return self._username

    @pyqtProperty(str, notify=quickSettingsChanged)
    def uptime(self) -> str:
        return self._uptime

    @pyqtProperty(int, notify=brightnessChanged)
    def brightness(self) -> int:
        return self._brightness

    @pyqtProperty(int, notify=volumeChanged)
    def volume(self) -> int:
        return self._volume

    @pyqtProperty(str, notify=mediaChanged)
    def mediaStatus(self) -> str:
        return self._media_status

    @pyqtProperty(str, notify=mediaChanged)
    def mediaTitle(self) -> str:
        return self._media_title

    @pyqtProperty(str, notify=mediaChanged)
    def mediaArtist(self) -> str:
        return self._media_artist

    @pyqtProperty(str, notify=mediaChanged)
    def mediaCover(self) -> str:
        if self._media_cover:
            return QUrl.fromLocalFile(self._media_cover).toString()
        return ""

    @pyqtProperty(float, notify=mediaChanged)
    def mediaProgress(self) -> float:
        return self._media_progress

    @pyqtProperty(str, notify=mediaChanged)
    def mediaElapsed(self) -> str:
        return self._media_elapsed

    @pyqtProperty(str, notify=mediaChanged)
    def mediaTotal(self) -> str:
        return self._media_total

    @pyqtProperty(object, notify=homeAssistantChanged)
    def phoneInfo(self) -> PhoneInfo:
        return self._phone_info

    @pyqtProperty(bool, notify=homeAssistantChanged)
    def homeAssistantVisible(self) -> bool:
        return self._home_assistant_visible

    @pyqtProperty(str, notify=homeAssistantChanged)
    def homeAssistantStatus(self) -> str:
        return self._home_assistant_status

    @pyqtProperty(list, notify=homeAssistantChanged)
    def homeAssistantTiles(self) -> list[dict]:
        return self._home_assistant_tiles

    @pyqtProperty(list, notify=serviceCardsChanged)
    def serviceCards(self) -> list[dict]:
        return self._service_cards

    @pyqtProperty(list, notify=systemOverviewChanged)
    def systemOverview(self) -> list[dict]:
        return self._system_overview

    @pyqtProperty(str, notify=appearanceStatusChanged)
    def appearanceStatus(self) -> str:
        return self._appearance_status

    @pyqtProperty(str, notify=haSettingsChanged)
    def haUrl(self) -> str:
        return self._ha_url

    @haUrl.setter
    def haUrl(self, value: str) -> None:
        if value != self._ha_url:
            self._ha_url = value

    @pyqtProperty(str, notify=haSettingsChanged)
    def haToken(self) -> str:
        return self._ha_token

    @haToken.setter
    def haToken(self, value: str) -> None:
        if value != self._ha_token:
            self._ha_token = value

    @pyqtProperty(str, notify=haSettingsChanged)
    def haSettingsStatus(self) -> str:
        return self._ha_settings_status

    @pyqtProperty(list, notify=haEntitiesChanged)
    def haEntities(self) -> list[dict]:
        return self._ha_entities_list

    @pyqtProperty(int, notify=sizeChanged)
    def ncWidth(self) -> int:
        return self._nc_width

    @pyqtProperty(int, notify=sizeChanged)
    def ncHeight(self) -> int:
        return self._nc_height

    @pyqtSlot()
    def closeCenter(self) -> None:
        from PyQt6.QtWidgets import QCoreApplication
        for win in QCoreApplication.topLevelWindows():
            win.close()

    @pyqtSlot(str)
    def toggleQuickSetting(self, key: str) -> None:
        if key == "wifi":
            run_script_bg("network.sh", "toggle")
        elif key == "bluetooth":
            run_script_bg("bluetooth", "toggle")
        elif key == "airplane":
            run_script_bg("network.sh", "toggle-radio")
        elif key == "night":
            run_script_bg("redshift", "toggle")
        elif key == "caffeine":
            caffeine_script = SCRIPTS_DIR / "caffeine.sh"
            if caffeine_script.exists():
                run_bg(["env", "HANAUTA_QUIET=1", str(caffeine_script), "toggle"])
        elif key == "dnd":
            dnd_on = parse_bool_text(
                run_cmd(notification_control_command("is-paused"))
            )
            if dnd_on:
                run_cmd(notification_control_command("set-paused", "false"))
            else:
                run_cmd(notification_control_command("set-paused", "true"))
        QTimer.singleShot(400, self._refresh_after_quick_toggle)

    def _refresh_after_quick_toggle(self) -> None:
        result = poll_all()
        self._poll_result = result
        self._apply_quick_settings_from_poll(result)
        self._brightness = result.brightness
        self.brightnessChanged.emit()
        self._volume = result.volume
        self.volumeChanged.emit()

    @pyqtSlot(int)
    def setBrightness(self, value: int) -> None:
        self._brightness = value
        run_script_bg("brightness.sh", "set", str(value))

    @pyqtSlot(int)
    def setVolume(self, value: int) -> None:
        self._volume = value
        run_script_bg("volume.sh", "set", str(value))

    @pyqtSlot(str)
    def triggerMediaAction(self, action: str) -> None:
        action_map = {
            "previous": "--previous",
            "toggle": "--toggle",
            "next": "--next",
        }
        mapped = action_map.get(action, action)
        run_script_bg("mpris.sh", mapped)
        for delay in (150, 450, 900):
            QTimer.singleShot(delay, self._refresh_media_after_action)

    def _refresh_media_after_action(self) -> None:
        r = poll_all()
        self._poll_result = r
        self._apply_media_from_poll(r)

    @pyqtSlot(str, result=str)
    def materialIcon(self, name: str) -> str:
        return material_icon(name)

    @pyqtSlot(str)
    def openSettingsApp(self, section: str = "overview") -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        args = ["--page", section]
        try:
            subprocess.Popen(
                [python_executable(), str(SETTINGS_PAGE_SCRIPT), *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    @pyqtSlot(int)
    def activateHomeAssistantTile(self, index: int) -> None:
        pinned = self._settings_state["home_assistant"].get("pinned_entities", [])
        if index >= len(pinned):
            self.openSettingsApp("services")
            return
        entity_id = pinned[index]
        entity = self._ha_entity_map.get(entity_id)
        if not entity:
            return
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        state = str(entity.get("state", ""))
        service_domain = domain
        service = ""
        payload = {"entity_id": entity_id}
        if domain in {"light", "switch", "input_boolean"}:
            service = "turn_off" if state == "on" else "turn_on"
        elif domain == "scene":
            service = "turn_on"
            service_domain = "scene"
        elif domain == "script":
            service = "turn_on"
            service_domain = "script"
        else:
            return
        ha_cfg = self._settings_state.get("home_assistant", {})
        base_url = normalize_ha_url(ha_cfg.get("url", ""))
        token = ha_cfg.get("token", "")
        if not base_url or not token:
            return
        import threading

        def post() -> None:
            try:
                post_home_assistant_json(
                    base_url, token,
                    f"/api/services/{service_domain}/{service}",
                    payload,
                )
            except Exception:
                pass
            QTimer.singleShot(900, self._refresh_home_assistant_entities)

        threading.Thread(target=post, daemon=True).start()

    @pyqtSlot(str)
    def launchService(self, key: str) -> None:
        from notif_center.plugin_paths import (
            VPN_CONTROL_SCRIPT, CHRISTIAN_WIDGET_SCRIPT, REMINDERS_WIDGET_SCRIPT,
            POMODORO_WIDGET_SCRIPT, OBS_WIDGET_SCRIPT, CRYPTO_WIDGET_SCRIPT,
            VPS_WIDGET_SCRIPT, GAME_MODE_POPUP_SCRIPT, resolve_rss_widget_script,
        )
        from notif_center.utils import run_bg_singleton, desktop_clock_command
        script_map = {
            "vpn_control": VPN_CONTROL_SCRIPT,
            "christian_widget": CHRISTIAN_WIDGET_SCRIPT,
            "reminders_widget": REMINDERS_WIDGET_SCRIPT,
            "pomodoro_widget": POMODORO_WIDGET_SCRIPT,
            "obs_widget": OBS_WIDGET_SCRIPT,
            "crypto_widget": CRYPTO_WIDGET_SCRIPT,
            "vps_widget": VPS_WIDGET_SCRIPT,
            "game_mode": GAME_MODE_POPUP_SCRIPT,
        }
        if key == "rss_widget":
            rss_script = resolve_rss_widget_script(self._settings_state)
            if rss_script.exists():
                run_bg_singleton(rss_script)
            return
        if key == "desktop_clock_widget":
            command = desktop_clock_command()
            if command:
                try:
                    subprocess.Popen(
                        command,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except Exception:
                    pass
            return
        script = script_map.get(key)
        if script and script.exists():
            run_bg_singleton(script)

    @pyqtSlot()
    def openOverviewSettings(self) -> None:
        self.openSettingsApp("overview")

    @pyqtSlot(str)
    def setAccent(self, key: str) -> None:
        from notif_center.utils import accent_palette
        self._accent_name = key
        self._settings_state["appearance"]["accent"] = key
        self._current_accent = accent_palette(key)
        save_notification_settings(self._settings_state)
        self._apply_color_palette()
        self._update_appearance_status()

    @pyqtSlot(str)
    def setHomeAssistantUrl(self, text: str) -> None:
        self._ha_url = text

    @pyqtSlot(str)
    def setHomeAssistantToken(self, text: str) -> None:
        self._ha_token = text

    @pyqtSlot()
    def saveHomeAssistantSettings(self) -> None:
        self._settings_state["home_assistant"]["url"] = normalize_ha_url(self._ha_url)
        self._settings_state["home_assistant"]["token"] = self._ha_token.strip()
        save_notification_settings(self._settings_state)
        self._ha_settings_status = "Connection saved."
        self.haSettingsChanged.emit()
        self._refresh_home_assistant_entities()

    @pyqtSlot()
    def refreshHomeAssistant(self) -> None:
        self._ha_settings_status = "Fetching entities..."
        self.haSettingsChanged.emit()
        self._refresh_home_assistant_entities()

    @pyqtSlot(str)
    def togglePinEntity(self, entity_id: str) -> None:
        pinned = list(self._settings_state["home_assistant"].get("pinned_entities", []))
        if entity_id in pinned:
            pinned.remove(entity_id)
        else:
            if len(pinned) >= 5:
                self._ha_settings_status = "You can pin up to five entities."
                self.haSettingsChanged.emit()
                return
            pinned.append(entity_id)
        self._settings_state["home_assistant"]["pinned_entities"] = pinned
        save_notification_settings(self._settings_state)
        self._ha_settings_status = f"{len(pinned)}/5 entities pinned."
        self.haSettingsChanged.emit()
        self._refresh_ha_entity_list()
        self._refresh_home_assistant_tiles()
