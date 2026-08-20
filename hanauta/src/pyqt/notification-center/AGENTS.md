# AGENTS.md — Notification Center (PyQt6)

## Overview

The PyQt6 Notification Center (`hanauta/src/pyqt/notification-center/`) is a native Qt recreation of the visual mockup in `idea.html`. It replaces the former Eww-based notification center and serves as the system control panel ("Hanauta Control Center").

**Entry point**: `notification_center.py` — `NotificationCenter` class (QWidget)

**Not a system notification daemon** — Desktop toasts come from the GTK daemon at `hanauta/bin/hanauta-notifyd`. This center is a panel for quick settings, media, calendar, notifications history, Home Assistant, and service launchers.

---

## Architecture

```
notification_center.py          # Main window, polls, UI composition
├── notif_center/
│   ├── paths.py                # Filesystem constants (state dirs, scripts, assets)
│   ├── widgets.py              # Reusable UI components (QuickSettingButton, ActionTile, etc.)
│   ├── media.py                # MPRIS polling (metadata + progress)
│   ├── ha.py                   # Home Assistant REST helpers
│   ├── settings_io.py          # Settings load/save (JSON in ~/.local/state)
│   ├── utils.py                # Shared helpers (icons, fonts, subprocess, theming)
│   ├── game_carousel.py        # Steam/Lutris game slides + play logic
│   └── providers.py            # Plugin-style widget providers (optional)
├── controlcenter/              # QML-based control center (legacy, not active)
└── idea.html                   # Visual reference (Tailwind + Material 3)
```

---

## Key Components

### `NotificationCenter` (notification_center.py)

**Window flags**
```python
Qt.WindowType.FramelessWindowHint
| Qt.WindowType.Tool
| Qt.WindowType.WindowStaysOnTopHint
```
Translucent background (`WA_TranslucentBackground`), centered top with 28px margin.

**Two page modes** (QStackedWidget):
- **Overview** (compact): quick settings, sliders, media, game carousel, phone/KDE Connect, Home Assistant tiles, calendar, events, notification history
- **Settings**: redirects to standalone Settings app (`settings-page/settings.py`)

**Polling timers** (all on GUI thread, lightweight subprocess calls):
| Timer | Interval | Purpose |
|-------|----------|---------|
| `timer` | 3.5s | Header, quick settings, sliders, media metadata, phone, calendar, notifications, HA tiles |
| `ha_timer` | 15s | Home Assistant entity refresh |
| `media_progress_timer` | 1s | Media progress bar interpolation |
| `theme_timer` | 3s | Matugen/theme palette reload |
| `calendar_timer` | 30s | Calendar events refetch |
| `games_cache_timer` | 5s | Game library cache sync |

---

### Overview Page Layout

```
Left column (11/20 width)          Right column (9/20 width)
─────────────────────────────      ─────────────────────────────
Quick Settings (6 tiles)           Calendar (QCalendarWidget)
Brightness/Volume sliders          Upcoming Events (scroll)
Media Card (cover + controls)      Last Notifications (scroll)
Game Carousel (4 slides)            
Phone / KDE Connect               
Home Assistant (5 action tiles)    
Service Launchers (VPN, RSS, etc.) 
```

---

### Reusable Widgets (`notif_center/widgets.py`)

| Widget | Purpose |
|--------|---------|
| `QuickSettingButton` | Toggle tile (Wi-Fi, BT, DND, etc.) with icon, title, subtitle; `apply_theme()` for Matugen sync |
| `SidebarItemButton` | Settings nav rail item (checkable) |
| `ActionTile` | Square tile with icon/title/subtitle; used for HA pinned entities |
| `CompactIconAction` | 28×28 icon-only button (active/inactive state via property) |
| `ServiceLauncherCard` | Row: icon + title/detail + "Open" button; launches external plugin scripts |
| `ElidedLabel` | Auto-elides text on resize |
| `ClickableLabel` | Label with click callback |

---

### Media Card (`_build_media_card`)

- **Cover art**: 54×54, fetched via MPRIS `mpris.sh` script
- **Progress bar**: Custom paint (4px track + fill), interpolated by 1s timer
- **Controls**: Prev / Play-Pause / Next via `mpris.sh --previous/--toggle/--next`
- **Dynamic palette**: Radial gradient from album art colors (`theme.media_active_start/end`), scrim for text contrast

---

### Quick Settings Tiles

Defined in `_build_quick_settings_card()` (compact) and `_build_quick_settings()` (settings page). Each uses `QuickSettingButton` with callbacks:
- Wi-Fi → `nmcli radio wifi on/off`
- Bluetooth → `bluetoothctl power on/off`
- DND → `notification_control_command("--toggle-dnd")`
- Airplane → `nmcli radio all on/off`
- Night Light → `redshift` script toggle
- Caffeine → `caffeine` script toggle

State polled every 3.5s via `_poll_quick_settings()`.

---

### Sliders (Brightness / Volume)

Custom `QSlider` with paint-based groove/sub-page (no handle). Value changes debounced via single-shot timers (`_brightness_commit_timer`, `_volume_commit_timer` → 150ms) then committed via `brightness.sh` / `volume.sh`.

---

### Calendar

Uses shared `pyqt.shared.calendar_card.build_calendar_card()` (QCalendarWidget wrapper). Events loaded from:
1. Cache file `~/.local/state/hanauta/service/calendar_events.json` (written by `qcal-wrapper.py` plugin)
2. Fallback: direct call to `qcal-wrapper.py list --days 14`

Clicking a date with events opens a frameless dialog listing that day's events.

---

### Notification History

Reads `~/.local/state/hanauta/notification-daemon/history.json` (written by GTK `hanauta-notifyd`). Shows last 3 items with app icon, title, body, timestamp. "Clear all" button truncates the file.

---

### Home Assistant Integration

- **Settings page**: URL + long-lived token input, "Fetch Entities" button
- **Overview**: Up to 5 pinned entities as `ActionTile` grid
- **Polling**: `/api/states` every 15s; tiles show state + icon, click toggles or calls service
- **Config**: `settings_state["home_assistant"]` (url, token, pinned_entity_ids)

---

### Game Carousel

`GameCarouselCard` (from `game_carousel.py`) shows 4 slides: Steam + Lutris recent games with playtime.
- Cache: `~/.local/state/hanauta/service/games.json` (written by background workers)
- "PLAY" button launches `lutris lutris:rungame/<slug>`
- Detects running games via `any_game_running_fast()` (process scan)

---

### Service Launchers

Each optional plugin gets a `ServiceLauncherCard` in the overview left column. Visibility controlled by:
```python
settings_state["services"][<key>]["enabled"]
settings_state["services"][<key>]["show_in_notification_center"]
```
Scripts resolved via `pyqt.shared.plugin_runtime.resolve_plugin_script()` (checks installed plugins + fallback paths).

---

## Theming

- Palette from `pyqt.shared.theme.load_theme_palette()` (Matugen + static fallback)
- Stylesheet built in `_apply_styles()` — single giant f-string with CSS variables interpolated from `theme` object
- Matugen accent overrides static accent presets (orchid/mint/sunset)
- Media card has separate `_apply_media_palette()` for dynamic album-art gradient
- Call `_apply_styles()` after any palette change (theme timer, Matugen regen, accent preset click)

---

## Icon Fonts

- Bundled in `assets/fonts/` (Material Icons, Material Symbols)
- Loaded via `QFontDatabase.addApplicationFont()` in `utils.load_app_fonts()`
- `material_icon(name)` returns codepoint string (e.g., `"\ue1da"` for `wifi`)
- **Never use ligature names** (`play_arrow`) as button text — use explicit codepoints

---

## External Scripts (from `hanauta/scripts/`)

| Script | Used For |
|--------|----------|
| `mpris.sh` | Media metadata, cover art, playback control |
| `network.sh` | Wi-Fi SSID, connection state |
| `bluetooth` | BT adapter state, connected device |
| `volume.sh` | Volume get/set |
| `brightness.sh` | Brightness get/set |
| `redshift` | Night light toggle |
| `phone_info.sh` | KDE Connect device info |
| `notification_control_command()` | DND toggle, history clear |

All script calls go through `utils.run_script()` / `run_bg()` / `run_bg_singleton()` (fork + detach stdout/stderr).

---

## Settings Persistence

File: `~/.local/state/hanauta/notification-center/settings.json`

Loaded via `notif_center.settings_io.load_notification_settings()` → returns dict with defaults from `DEFAULT_SERVICE_SETTINGS`.

Structure:
```json
{
  "appearance": { "accent": "orchid" },
  "home_assistant": { "url": "", "token": "", "pinned_entity_ids": [] },
  "services": {
    "home_assistant": { "enabled": true, "show_in_notification_center": true },
    "vpn_control": { "enabled": false, "show_in_notification_center": false },
    ...
  }
}
```

---

## Verification

```bash
# Syntax check
python3 -m py_compile hanauta/src/pyqt/notification-center/notification_center.py
python3 -m py_compile hanauta/src/pyqt/notification-center/notif_center/*.py
```

---

## Common Modifications

| Task | Where |
|------|-------|
| Add a quick setting tile | `_build_quick_settings_card()` + `_poll_quick_settings()` |
| Add a service launcher | `_build_<name>_launcher_card()` + `_sync_service_card_visibility()` + `_open_<name>_widget()` |
| Change polling interval | `_start_polls()` timer `start()` values |
| Modify media card layout | `_build_media_card()` + `_apply_media_palette()` |
| Add settings page | `_build_settings_page()` (but prefer redirecting to standalone Settings app) |
| Fix icon rendering | Check `material_font` passed to widget, ensure `font-family` in stylesheet |
| Debug tray/service visibility | `_sync_service_card_visibility()` logic + `settings_state["services"]` |