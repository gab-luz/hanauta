# Hanauta Native Services

This folder now contains the native C background stack for Hanauta:

- `hanauta-service.c`
  - GLib main-loop service for background weather and crypto refreshes.
  - Watches `~/.local/state/hanauta/notification-center/settings.json`.
  - Writes cache files to `~/.local/state/hanauta/service/`.
- `hanauta-notifyd.c`
  - GTK/GLib notification daemon.
  - Owns `org.freedesktop.Notifications` on the session bus.
  - Renders toast popups and persists notification history.
- `hanauta-notifyctl.c`
  - Native CLI for pause state, history, and notification closing.
- `hanauta-clock.cpp`
  - Native Qt desktop clock.
  - Uses the same Hanauta settings file as the PyQt clock.

## Build

```bash
bash hanauta/src/service/build.sh
```

That produces:

- `hanauta/bin/hanauta-service`
- `hanauta/bin/hanauta-notifyctl`
- `hanauta/bin/hanauta-notifyd`
- `hanauta/bin/hanauta-clock`

## Runtime

`startup.sh` prefers the native notification daemon when the binary exists, and still falls back to the older Python daemon if it does not.

The top-level wrapper at `bin/hanauta-notifyctl` forwards to the native binary, so the existing PyQt and Eww callers keep working without code changes.
