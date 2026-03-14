# Hanauta

Hanauta is a wallpaper-reactive desktop theme and workflow layer for `i3` on X11, built around native PyQt6 components instead of an Eww shell. It aims to feel cohesive, fast, and readable across the bar, dock, notification center, settings surfaces, compositor, wallpaper flow, and even supported editors.

This project is intentionally focused on an X11 / XLibre desktop stack. The goal is not to be a generic Linux theme pack, but a tightly integrated desktop experience for an `i3`-driven session with strong control over visuals, system actions, and live theming.

## Screenshots

![Hanauta screenshot 1](assets/screenshots/2026-03-11_21-42.png)
![Hanauta screenshot 2](assets/screenshots/2026-03-11_21-43.png)
![Hanauta screenshot 3](assets/screenshots/2026-03-11_21-53.png)
Hyprland's clock succesfully ported:
![Hanauta screenshot 4](assets/screenshots/2026-03-14_13-16.png)

## Features

- Native PyQt6 bar with workspace state, media, clock, and system status
- Native PyQt6 notification center inspired by Material 3 expressive layouts
- Standalone PyQt6 settings application wired into the bar and notification center
- Wallpaper-aware theming for the bar and dock through a shared generated palette
- Matugen integration for extracting palette colors directly from the current wallpaper
- Wallpaper source sync presets for official Caelestia and End-4 upstream image packs
- Display management UI with multi-monitor controls, primary display selection, mirror/extend mode, orientation, refresh rate, and resolution
- Per-monitor wallpaper placement modes including `Fill`, `Fit`, `Center`, `Stretch`, and `Tile`
- Picom settings tab with reset-to-default support
- Home Assistant integration inside settings and notification workflows
- Live VS Code / VSCodium workbench theming from the same wallpaper palette
- Installer support for the desktop setup plus optional editor extension-only installs

## Hotkeys

- `Super+Return`: open `kitty`
- `Super+Space`: open the PyQt launcher
- `Alt+F1`: open the hotkeys overlay
- `Alt+Tab`: open the window switcher
- `Print`: open Flameshot screenshot UI
- `Super+Q`: close the focused window
- `Super+H/J/K/Right`: focus windows
- `Super+Shift+H/J/K/L`: move windows
- `Super+1..5`: switch workspaces
- `Super+Shift+1..5`: move the focused window to a workspace
- `Super+V`: vertical split
- `Super+B`: horizontal split
- `Super+F`: toggle fullscreen
- `Super+L`: lock the session
- `Super+Shift+C`: reload i3
- `Super+Shift+R`: restart i3

## Core Components

- Bar: `hanauta/src/pyqt/bar/ui_bar.py`
- Notification Center: `hanauta/src/pyqt/notification-center/notification_center.py`
- Settings App: `hanauta/src/pyqt/settings-page/settings.py`
- Shared Theme Logic: `hanauta/src/pyqt/shared/theme.py`
- VS Code / VSCodium extension: `hanauta/vscode-wallpaper-theme/package.json`

## Theming Model

Hanauta uses a shared palette pipeline so the desktop does not have to be styled component by component by hand.

1. A wallpaper is selected in the settings application.
2. Matugen derives a palette from that wallpaper.
3. The palette is written to `~/.local/state/hanauta/theme/pyqt_palette.json`.
4. PyQt surfaces such as the bar and dock read that palette and restyle live.
5. The VS Code / VSCodium extension watches the same palette file and updates the editor workbench in real time.

The palette layer is contrast-aware, so foregrounds are chosen to remain readable even when wallpapers generate very light or very dark surfaces.

## Editor Integration

The repository includes a small wallpaper-theme extension for VS Code and VSCodium. It reads the same palette file used by the desktop UI and applies matching workbench colors live.

Install only the editor extensions:

```bash
./install.sh --vscode
./install.sh --vscodium
```

Run the full desktop installer:

```bash
./install.sh
```

## Project Structure

- `config` and startup scripts for the `i3` session
- `picom.conf` for compositor behavior
- `assets/` for fonts and project media
- `hanauta/src/pyqt/` for the active desktop UI
- `hanauta/src/eww/scripts/` for helper scripts reused by the PyQt interface
- `hanauta/vscode-wallpaper-theme/` for live editor theming

## Notes

- The active desktop UI stack is PyQt6.
- Eww helper scripts are still reused where they already provide reliable system actions or state.
- This project is tuned for an opinionated personal desktop, not for every possible Linux environment.

## References

These are the main upstream references, inspirations, and compatibility targets used so far while building Hanauta:

- `dms-plugins`: https://github.com/AvengeMedia/dms-plugins
- `nucleus-shell`: https://github.com/xZepyx/nucleus-shell
- `caelestia shell`: https://github.com/caelestia-dots/shell
- `caelestia-dots` legacy repo: https://github.com/GuillaumeDeconinck/caelestia-dots
- `end-4 dots-hyprland`: https://github.com/end-4/dots-hyprland
- `end-4 dots-hyprland wiki`: https://github.com/end-4/dots-hyprland-wiki
- `FreshRSS`: https://github.com/FreshRSS/FreshRSS
- `FreshRSS docs`: https://freshrss.github.io/FreshRSS/en/
- `CoinGecko API docs`: https://docs.coingecko.com/reference/simple-price
- `CoinGecko market chart docs`: https://docs.coingecko.com/reference/coins-id-market-chart
