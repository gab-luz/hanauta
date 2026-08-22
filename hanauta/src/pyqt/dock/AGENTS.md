# AGENTS.md - Hanauta Dock (CyberDock)

## Overview
`hanauta/src/pyqt/dock/dock.py` is the native PyQt6 implementation of the CyberDock - a bottom-center application dock for i3 window manager. It replaces the previous Eww-based dock implementation.

## Key Components

### Main Classes
1. **CyberDock** - Main dock widget (QWidget)
2. **DockAppButton** - Individual app button in the dock
3. **VolumeButton** - Volume control with wheel support
4. **AudioDevicePopup** - Audio device switcher dialog
5. **DockSettingsDialog** - Settings dialog for dock configuration
6. **DockItemsWorker** - Background thread for building dock items

### Configuration
- **Config file**: `DOCK_CONFIG = APP_DIR / "pyqt" / "dock" / "dock.toml"`
- **Cache dir**: `CACHE_DIR = ~/.cache/hanauta-dock/`
- **Icon cache**: `ICON_CACHE_PATH = CACHE_DIR / "icon_cache.json"`
- **State file**: `STATE_PATH = CACHE_DIR / "state.json"`
- **Lock file**: `LOCK_PATH = CACHE_DIR / "dock.lock"`

### Dock Settings (dock.toml)
```toml
[dock]
auto_hide = false        # Auto-hide when not in use
width = 60               # Dock width (0 = fit content)
width_unit = "%"         # "px" or "%"
height = 64              # App button height
icons_left = false       # Align icons left instead of center
position = "center"      # "left", "center", "right"
transparency = 60        # 0-100%
monitor_mode = "primary" # "primary", "follow_mouse", "named"
monitor_name = ""        # Specific monitor name when mode is "named"

[pinned]
apps = ["app1.desktop", "app2.desktop"]

[blacklist]
wm_class = []
desktop_id = []
window_name = []
```

## Important Design Patterns

### 1. Real-time Config Reload
The dock watches `dock.toml` via `QFileSystemWatcher` and applies changes without restart:
- Width/height/position/auto_hide/icons_left changes apply immediately
- Width/width_unit changes trigger panel rebuild
- Implemented in `_on_config_changed()` method

### 2. Theme Integration
- Uses `load_theme_palette()` from `pyqt.shared.theme`
- Watches palette mtime for theme changes (`_reload_theme_if_needed`)
- Applies theme with transparency support (different for light/dark)
- All sub-widgets (VolumeButton, AudioDevicePopup, DockAppButton) implement `apply_theme(theme)`

### 3. i3 Integration
- Window rules: floating, sticky, position, size via `i3-msg`
- Bottom strut via `_NET_WM_STRUT_PARTIAL` for workspace reservation
- Workspace-aware app focusing

### 4. Desktop Entry Management
- Scans multiple `DESKTOP_DIRS` for `.desktop` files
- Maps WM_CLASS to desktop IDs
- Supports pinned apps and running apps
- Blacklist support for WM_CLASS, desktop IDs, window names

### 5. Audio Integration
- Uses `pactl` for device enumeration and control
- Volume wheel support (uses i3-volume if available, falls back to VOLUME_SCRIPT)
- Sink/source device switching with volume/mute controls

### 6. Animations
- Geometry animation for smooth position changes (180ms OutCubic)
- Opacity animation on startup (180ms)
- Auto-hide animation with 600ms delay

### 7. Build System
The dock is built via Nuitka compilation:
- Entry point: `hanauta-dock` (via `pyproject.toml` / `build-popup-widgets.sh`)
- See `hanauta/build-popup-widgets.sh` for build process

## Key Files & Paths
- **Source**: `hanauta/src/pyqt/dock/dock.py`
- **Config**: `hanauta/src/pyqt/dock/dock.toml`
- **Built binary**: `hanauta/bin/hanauta-dock` (Nuitka compiled)
- **Icons**: `hanauta/src/assets/icons/` (dock-width.svg, dock-height.svg, etc.)
- **Nav icon**: `hanauta/src/assets/nav-icons/dock.svg`

## Build Commands
```bash
# Build the dock (and other popup widgets)
bash hanauta/build-popup-widgets.sh

# Or manually:
cd hanauta && python3 -m nuitka --standalone --onefile --output-dir=bin --output-filename=hanauta-dock src/pyqt/dock/dock.py
```

## Testing
```bash
# Run directly (development)
python3 hanauta/src/pyqt/dock/dock.py run

# Test config reload
# Edit dock.toml and watch changes apply in real-time

# Test commands
python3 -m hanauta.src.pyqt.dock.dock activate com.example.app.desktop
python3 -m hanauta.src.pyqt.dock.dock new com.example.app.desktop
python3 -m hanauta.src.pyqt.dock.dock activate-wm "firefox"
```

## Common Modifications

### Adding New Settings
1. Add to `dock.toml` defaults in `load_dock_config()`
2. Add to `save_dock_config()` TOML output
3. Add UI in `DockSettingsDialog._build_config()`
4. Apply in `CyberDock._apply_dock_preferences()` or `_on_config_changed()`
4. Update AGENTS.md

### Adding New Dock Behaviors
1. Modify `CyberDock._apply_dock_preferences()` for panel layout changes
2. Modify `CyberDock._rebuild_apps()` for app button changes
3. Update `DockAppButton` for button behavior changes

### Theme Changes
- All theme-dependent styling goes in `CyberDock._apply_theme()`
- Sub-widgets must implement `apply_theme(theme)`
- Use `theme` object properties (theme.text, theme.primary, etc.)

### Icon Handling
- Uses `resolve_icon_path()` with icon cache
- Fallback icons in `FALLBACK_ICON_NAMES`
- Custom SVG icons in `hanauta/src/assets/icons/`

## Important Notes
- **Single instance lock**: Uses `QLockFile` at `~/.cache/hanauta-dock/dock.lock`
- **Font loading**: Uses bundled fonts from `assets/fonts/` via `load_app_fonts()`
- **Material Icons**: Uses custom `MATERIAL_ICONS` dict (not ligature names)
- **i3 dependency**: Requires i3-msg for workspace/window management
- **pactl dependency**: Required for audio device management
- **gtk-launch**: Used for launching desktop applications

## Debugging
- Logs: `init_app_logging("dock")` - see `pyqt.shared.app_logging`
- Config file: `~/.config/i3/hanauta/src/pyqt/dock/dock.toml`
- Cache: `~/.cache/hanauta-dock/`
- Run with `python3 -m hanauta.src.pyqt.dock.dock run` for dev testing

## REMEMBER: Any changes to the dock MUST update this AGENTS.md file!