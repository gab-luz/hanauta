from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtGui import QColor, QPixmap

from notif_center.paths import (
    CAFFEINE_NOTIFICATION_ICON,
    HOME_ASSISTANT_ICON,
    KDECONNECT_ICON,
    LUTRIS_ICON,
    NIGHT_LIGHT_NOTIFICATION_ICON,
    STEAM_ICON,
    WEATHER_HISTORY_ICON,
)
from notif_center.utils import render_svg_pixmap, render_theme_icon_pixmap, tinted_svg_pixmap

KNOWN_ASSETS: dict[str, Path] = {
    "kde connect": KDECONNECT_ICON,
    "kdeconnect": KDECONNECT_ICON,
    "home assistant": HOME_ASSISTANT_ICON,
    "steam": STEAM_ICON,
    "lutris": LUTRIS_ICON,
}

THEME_NAME_CANDIDATES: dict[str, list[str]] = {
    "kde connect": ["kdeconnect", "org.kde.kdeconnect", "kde-connect"],
    "kdeconnect": ["kdeconnect", "org.kde.kdeconnect", "kde-connect"],
    "discord": ["discord", "Discord", "com.discordapp.Discord"],
    "spotify": ["spotify", "Spotify", "com.spotify.Client"],
    "steam": ["steam", "Steam"],
    "lutris": ["lutris", "Lutris", "net.lutris.Lutris"],
    "telegram": ["telegram", "Telegram", "org.telegram.desktop"],
    "firefox": ["firefox", "Firefox", "firefox-esr"],
    "chromium": ["chromium", "Chromium"],
    "google chrome": ["google-chrome", "Google-chrome", "chrome"],
    "ferdium": ["ferdium", "Ferdium"],
    "thunderbird": ["thunderbird", "Thunderbird", "org.mozilla.Thunderbird"],
    "obs": ["obs", "com.obsproject.Studio"],
    "obsidian": ["obsidian", "md.obsidian.Obsidian"],
    "vlc": ["vlc", "VLC", "org.videolan.VLC"],
    "rhythmbox": ["rhythmbox", "org.gnome.Rhythmbox3"],
    "gimp": ["gimp", "GIMP", "org.gimp.GIMP"],
    "blueman": ["blueman", "bluetooth", "preferences-system-bluetooth"],
    "networkmanager": ["networkmanager", "nm-applet", "preferences-system-network"],
    "pavucontrol": ["pavucontrol", "multimedia-volume-control"],
    "copyq": ["copyq", "com.github.hluk.copyq"],
    "kitty": ["kitty", "org.kitty.Kitty"],
    "alacritty": ["alacritty", "Alacritty"],
    "code": ["code", "visual-studio-code", "com.visualstudio.code"],
    "slack": ["slack", "Slack", "com.slack.Slack"],
    "whatsapp": ["whatsapp", "WhatsApp", "io.whatsapp.WhatsApp"],
    "signal": ["signal", "Signal", "org.signal.Signal"],
    "element": ["element", "Element", "im.riot.Riot"],
    "vps care": ["dns", "cloud", "server", "network-server", "computer"],
    "vps": ["dns", "cloud", "server", "network-server", "computer"],
    "server": ["dns", "cloud", "server", "network-server", "computer"],
    "alertas-vps": ["dns", "cloud", "server", "network-server", "computer"],
    "terminal": ["terminal", "utilities-terminal", "gnome-terminal"],
    "system": ["computer", "system", "preferences-system", "application-x-executable"],
}


def notification_icon_pixmap(
    app_name: str,
    desktop_entry: str = "",
    icon_name: str = "",
    title: str = "",
    body: str = "",
    theme_palette: object = None,
) -> QPixmap:
    normalized = app_name.strip().lower()
    icon_name_normalized = icon_name.strip().lower()
    desktop_entry_normalized = desktop_entry.strip().lower()
    summary_normalized = title.strip().lower()
    body_normalized = body.strip().lower()
    if icon_name:
        direct_icon_path = Path(icon_name.replace("file://", "")).expanduser()
        if direct_icon_path.exists():
            direct = render_svg_pixmap(direct_icon_path, 18)
            if not direct.isNull():
                return direct
    is_caffeine = (
        "caffeine" in normalized
        or "caffeine" in summary_normalized
        or "caffeine" in body_normalized
    )
    if is_caffeine:
        caffeine_path = Path(CAFFEINE_NOTIFICATION_ICON).expanduser()
        if caffeine_path.exists():
            return tinted_svg_pixmap(
                caffeine_path, QColor(theme_palette.primary), 18
            )
        fallback = render_theme_icon_pixmap(["coffee"], 18)
        if not fallback.isNull():
            return fallback
    is_night_light = (
        "night light" in normalized
        or "nightlight" in normalized
        or "night light" in summary_normalized
        or "nightlight" in summary_normalized
        or "night light" in body_normalized
        or "nightlight" in body_normalized
        or icon_name.strip().lower() in {"nightlight", "weather-clear-night"}
    )
    if is_night_light:
        night_path = Path(NIGHT_LIGHT_NOTIFICATION_ICON).expanduser()
        if night_path.exists():
            return tinted_svg_pixmap(
                night_path, QColor(theme_palette.primary), 18
            )
        fallback = render_theme_icon_pixmap(["nightlight", "weather-clear-night"], 18)
        if not fallback.isNull():
            return fallback
    is_weather = (
        "weather" in normalized
        or "weather" in summary_normalized
        or "weather" in body_normalized
        or "sunrise" in summary_normalized
        or "sunset" in summary_normalized
        or "sunrise" in body_normalized
        or "sunset" in body_normalized
    )
    if is_weather and WEATHER_HISTORY_ICON.exists():
        return tinted_svg_pixmap(
            WEATHER_HISTORY_ICON, QColor(theme_palette.primary), 18
        )
    asset = KNOWN_ASSETS.get(normalized)
    if asset is not None:
        return tinted_svg_pixmap(asset, QColor(theme_palette.primary), 18)

    candidates = []
    if icon_name:
        candidates.append(icon_name)
    if desktop_entry:
        candidates.extend(
            [
                desktop_entry,
                desktop_entry.removesuffix(".desktop"),
                desktop_entry.replace(".desktop", ""),
            ]
        )
    candidates.extend(THEME_NAME_CANDIDATES.get(normalized, []))
    if not candidates:
        slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
        dotted = re.sub(r"[^a-z0-9]+", ".", normalized).strip(".")
        compact = re.sub(r"[^a-z0-9]+", "", normalized)
        candidates = [slug, dotted, compact, app_name]
    return render_theme_icon_pixmap(candidates, 18)
