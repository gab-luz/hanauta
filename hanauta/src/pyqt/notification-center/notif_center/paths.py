from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_APP_DIR = Path(__file__).resolve().parents[3]
if str(_APP_DIR) not in sys.path:
    sys.path.append(str(_APP_DIR))

ROOT = _APP_DIR.parents[1]
SCRIPTS_DIR = ROOT / "hanauta" / "scripts"
FONTS_DIR = ROOT / "assets" / "fonts"
ASSETS_DIR = _APP_DIR / "assets"
BIN_DIR = ROOT / "bin"

STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SERVICE_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
SETTINGS_FILE = STATE_DIR / "settings.json"
NOTIFICATION_HISTORY_FILE = (
    Path.home() / ".local" / "state" / "hanauta" / "notification-daemon" / "history.json"
)
CALENDAR_EVENTS_CACHE = SERVICE_STATE_DIR / "calendar_events.json"
GAMES_CACHE_PATH = SERVICE_STATE_DIR / "games.json"

FALLBACK_COVER = ROOT / "assets" / "fallback.webp"
SETTINGS_PAGE_SCRIPT = _APP_DIR / "pyqt" / "settings-page" / "settings.py"
POWERMENU_SCRIPT = _APP_DIR / "pyqt" / "powermenu" / "powermenu.py"
STEAM_ICON = ASSETS_DIR / "steam-logo.svg"
LUTRIS_ICON = ASSETS_DIR / "lutris-logo.svg"
HOME_ASSISTANT_ICON = ASSETS_DIR / "home-assistant-dark.svg"
PLATFORM_ICONS_DIR = ASSETS_DIR / "platform-icons"
KDECONNECT_ICON = ASSETS_DIR / "kdeconnect.svg"

LUTRIS_DB = Path.home() / ".local" / "share" / "lutris" / "pga.db"
LUTRIS_COVERART_DIRS = [
    Path.home() / ".local" / "share" / "lutris" / "coverart",
    Path.home() / ".cache" / "lutris" / "coverart",
]
PROFILE_PHOTO_CANDIDATES = [Path.home() / ".face.png", Path.home() / ".face.jpg"]
DESKTOP_CLOCK_BINARY = ROOT / "bin" / "hanauta-clock"


def preferred_icon_path(asset_name: str, system_path: str) -> str:
    local_icon = ASSETS_DIR / asset_name
    return str(local_icon) if local_icon.exists() else system_path
