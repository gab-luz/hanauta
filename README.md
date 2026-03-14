# 🌸 Hanauta

> A wallpaper-reactive desktop theme and workflow layer for **i3** on X11

Hanauta transforms your X11 desktop into a cohesive, modern experience with native **PyQt6** components. Everything—from the bar to the notification center—adapts dynamically to your wallpaper colors.

## ✨ What Makes Hanauta Special

- **🎨 Wallpaper-Reactive Theming** — Colors extracted automatically from your wallpaper via Matugen
- **🔔 Native Notification Daemon** — Full Freedesktop DBus support with notification history
- **🖥️ All-Native PyQt6 UI** — No Electron, no Eww shell—just pure Python widgets
- **🔄 Live Editor Theming** — VS Code / VSCodium matches your desktop colors in real-time

## 🚀 Features

### Core UI
- **Bar** — Workspace indicators, media player, clock, system status (battery, volume, WiFi, Bluetooth)
- **Notification Center** — Material 3 expressive layout with quick settings
- **Notification Daemon** — Native DBus implementation with notification history
- **Dock** — Elegant app dock with wallpaper-aware theming
- **Launcher** — Quick app launcher (`Super+Space`)
- **Window Switcher** — Visual window switcher (`Alt+Tab`)
- **Hotkeys Overlay** — Visual hotkeys reference (`Alt+F1`)
- **Power Menu** — Session controls (lock, logout, reboot, shutdown)

### Settings Application
- **Wallpaper & Colors** — Choose wallpapers, configure placement modes (Fill, Fit, Center, Stretch, Tile)
- **Display Management** — Multi-monitor controls, primary display, mirror/extend, orientation, refresh rate, resolution
- **Picom Compositor** — GUI for blur, shadows, fading, rounded corners
- **Bar Configuration** — Customize what's shown in the bar

### Integrations & Widgets
- **Home Assistant** — Control smart home entities directly from settings
- **VPN Control** — Manage WireGuard/OpenVPN connections
- **Weather** — Current conditions and forecasts
- **Calendar** — Events integration
- **Reminders** — Task reminders
- **Pomodoro Timer** — Focus timer with notifications
- **RSS Reader** — Follow your favorite feeds
- **Crypto Prices** — Live cryptocurrency prices (CoinGecko)
- **OBS Control** — Scene switching and streaming controls
- **VPS Monitor** — Remote server status monitoring
- **Desktop Clock** — Floating clock widget
- **Game Mode** — Gaming mode toggle with Lutris/Steam integration
- **NTFY Support** — Push notification integration

### Desktop Features
- **Wallpaper Source Sync** — Presets for Caelestia and End-4 wallpaper packs
- **Per-Monitor Wallpaper** — Different wallpapers per display
- **Live Editor Theming** — VS Code / VSCodium workbench matches wallpaper colors

## 📸 Screenshots

![Hanauta screenshot 1](assets/screenshots/2026-03-11_21-42.png)
![Hanauta screenshot 2](assets/screenshots/2026-03-11_21-43.png)
![Hanauta screenshot 3](assets/screenshots/2026-03-11_21-53.png)
Hyprland's clock successfully ported:
![Hanauta screenshot 4](assets/screenshots/2026-03-14_13-16.png)

## ⌨️ Hotkeys

| Shortcut | Action |
|----------|--------|
| `Super+Return` | Open terminal (kitty) |
| `Super+Space` | Open launcher |
| `Alt+F1` | Hotkeys overlay |
| `Alt+Tab` | Window switcher |
| `Print` | Screenshot (Flameshot) |
| `Super+Q` | Close window |
| `Super+H/J/K/L` | Focus windows |
| `Super+Shift+H/J/K/L` | Move windows |
| `Super+1..5` | Switch workspaces |
| `Super+Shift+1..5` | Move window to workspace |
| `Super+V` | Vertical split |
| `Super+B` | Horizontal split |
| `Super+F` | Toggle fullscreen |
| `Super+L` | Lock session |
| `Super+Shift+C` | Reload i3 |
| `Super+Shift+R` | Restart i3 |

## 🏗️ Architecture

### Core Components
- **Bar**: `hanauta/src/pyqt/bar/ui_bar.py`
- **Notification Center**: `hanauta/src/pyqt/notification-center/notification_center.py`
- **Notification Daemon**: `hanauta/src/pyqt/notification-daemon/notification_daemon.py`
- **Settings App**: `hanauta/src/pyqt/settings-page/settings.py`
- **Shared Theme Logic**: `hanauta/src/pyqt/shared/theme.py`
- **VS Code Extension**: `hanauta/vscode-wallpaper-theme/`

### Theming Pipeline

```
Wallpaper → Matugen → Palette JSON → PyQt UI + VS Code
```

1. Select a wallpaper in settings
2. Matugen extracts a color palette
3. Palette written to `~/.local/state/hanauta/theme/pyqt_palette.json`
4. All PyQt surfaces (bar, dock, notification center) restyle live
5. VS Code extension watches the same file and updates the editor

## 📁 Project Structure

```
├── config/              # i3 configuration
├── picom.conf          # Compositor settings
├── assets/             # Fonts and media
├── hanauta/
│   ├── src/pyqt/      # Active desktop UI
│   │   ├── bar/               # Top bar
│   │   ├── notification-center/   # Notification center
│   │   ├── notification-daemon/   # DBus notification daemon
│   │   ├── settings-page/     # Settings app
│   │   ├── dock/              # App dock
│   │   ├── launcher/          # App launcher
│   │   ├── widget-*/          # Various widgets
│   │   └── shared/            # Shared utilities
│   ├── src/eww/scripts/  # Helper scripts
│   └── vscode-wallpaper-theme/  # Editor theming
└── install.sh          # Installation script
```

## 🛠️ Installation

### Full Desktop Setup
```bash
./install.sh
```

### Editor Theme Only
```bash
./install.sh --vscode    # VS Code
./install.sh --vscodium  # VSCodium
```

## 📚 Credits & Inspiration

- [dms-plugins](https://github.com/AvengeMedia/dms-plugins)
- [nucleus-shell](https://github.com/xZepyx/nucleus-shell)
- [caelestia shell](https://github.com/caelestia-dots/shell)
- [end-4 dots-hyprland](https://github.com/end-4/dots-hyprland)
- [FreshRSS](https://FreshRSS.github.io/FreshRSS/en/)
- [CoinGecko API](https://docs.coingecko.com/)

---

Built with ❤️ for the X11/Linux desktop community
