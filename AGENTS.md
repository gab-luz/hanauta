# AGENTS.md

## Current UI Stack

- The active desktop UI is PyQt6, not Eww.
- Primary UI entry points:
  - `hanauta/src/pyqt/bar/ui_bar.py`
  - `hanauta/src/pyqt/notification-center/notification_center.py`
- The active top-level shell currently uses Python source for:
  - `hanauta/src/pyqt/bar/ui_bar.py`
  - `hanauta/src/pyqt/dock/dock.py`
- Many secondary PyQt widgets/popups are still launched from Nuitka binaries under `hanauta/bin`.
- Do not assume the active shell is fully Nuitka-compiled.
- `hanauta-bar` and `hanauta-dock` exist, but they are not the current default because the compiled shell windows had input/click regressions in this environment.
- Do not reintroduce Eww startup, Eww window toggles, or Eww-specific widget/config work unless the user explicitly asks for it.

## PyQt6 UI Rules

- Prefer native Qt widgets and layouts. Do not embed HTML to build the bar or notification center.
- Keep the bar and notification center visually aligned with the corresponding `idea.html` mockups, but implement them in Python code.
- Reuse existing helper scripts under `hanauta/scripts/` for system state and actions when they already provide the needed behavior.
- When changing polling behavior, keep intervals pragmatic:
  - clock around `1s`
  - media around `2s`
  - slower system state around `5s`

## Icon Fonts

- Bundled fonts live in `assets/fonts`.
- Load UI fonts with `QFontDatabase.addApplicationFont(...)`, not by assuming a system-installed font.
- For Material icons, do not use ligature names like `play_arrow` or `skip_previous` as button text.
- Use explicit codepoints mapped in Python and render them with the bundled `Material Icons` family.
- If icon glyphs render as squares, first verify the widget stylesheet is not overriding the icon font family with the general text font.
- When styling icon widgets in Qt stylesheets, explicitly set `font-family` for those selectors.

## Shared Script Notes

- Media state and playback controls use `hanauta/scripts/mpris.sh`.
- Network state uses `hanauta/scripts/network.sh`.
- Bluetooth state uses `hanauta/scripts/bluetooth`.
- Volume uses `hanauta/scripts/volume.sh`.
- Brightness uses `hanauta/scripts/brightness.sh`.
- Redshift/night light uses `hanauta/scripts/redshift`.
- Background script launches must return quickly. If a helper performs a longer action, fork it and detach stdout/stderr.
- Any numeric script output consumed by Qt sliders or status widgets should fall back to a valid number instead of an empty string.

## Bar Notes

- The bar should open the PyQt notification center, not an Eww window.
- Workspace indicators must reflect `focused`, `occupied`, and `urgent` state from `i3-msg -t get_workspaces`.
- The bar is intended to stay visible across workspaces. Preserve the current dock/sticky behavior in both Qt window flags and i3 config rules when editing it.
- Bar widget icon mode is now user-configurable from settings:
  - `bar.use_color_widget_icons = false` (default): prefer `icon.svg` and tint with bar accent color.
  - `bar.use_color_widget_icons = true`: prefer `icon_color.svg`.
- Do not hardcode theme-based color icon selection for bar widgets; use `bar.use_color_widget_icons` as the source of truth.
- If plugin hooks apply icons, host-managed icon refresh can override them later in the same pass. Keep this ordering in mind when debugging icon changes.
- Debug icon/chip tooltips are opt-in:
  - `bar.debug_tooltips = false` (default).
  - Only call `_install_debug_tooltips()` through settings-gated flow (`_apply_debug_tooltips_setting()`), never unconditionally during startup.
- The center section contains the clock/date and current media.
- The media visualizer uses `cava` raw output, configured by `hanauta/src/pyqt/bar/cava_bar.conf`.
- The current stable visualizer path is:
  - `cava` stays in ASCII raw mode in `hanauta/src/pyqt/bar/cava_bar.conf`.
  - `ui_bar.py` reads `cava` from a dedicated `CavaWorker(QThread)`, not from `QProcess` on the GUI thread.
  - The worker emits parsed frame parts to the bar, and the bar only updates equalizer target levels.
  - A separate Qt timer renders interpolation for the visible bar heights.
  - Each equalizer bar is paint-based and constant-size, so the bar does not churn layout geometry every frame.
- When touching the visualizer, prefer preserving this architecture:
  - keep `cava` I/O off the GUI thread
  - keep the equalizer bars paint-based instead of resizing widgets in layouts
  - keep theme/Matugen color updates separate from audio-frame updates
- Regressions we already hit:
  - moving `cava` reading back onto the GUI thread reintroduced visible pauses
  - switching the live bar to binary `cava` output caused worse cadence and under/over-scaling in this environment
  - the working setup here is threaded ASCII `cava` plus paint-based bars
- If pauses come back, check in this order:
  - whether `cava` is still being read from `CavaWorker`
  - whether `cava_bar.conf` is still using ASCII raw output
  - whether any new timers or subprocess polls are running on the main bar thread
  - whether equalizer rendering has gone back to stylesheet or layout-driven updates

## Systray Notes

- The active tray implementation is the native PyQt StatusNotifier tray inside `hanauta/src/pyqt/bar/ui_bar.py`.
- The bar should use StatusNotifierItem / StatusNotifierWatcher DBus support, not Eww systray widgets and not `stalonetray`.
- If no watcher is present on the session bus, the bar starts `hanauta/src/pyqt/bar/status_notifier_watcher.py` as the fallback watcher service.
- Many tray apps register with a DBus object path only. The fallback watcher must normalize those registrations to `sender + path`, otherwise the bar cannot build a valid tray item interface.
- For both watcher properties and tray item properties, use explicit `org.freedesktop.DBus.Properties.Get` calls. In this environment, relying on `QDBusInterface.property(...)` for remote DBus properties caused empty tray state.
- Tray item clicks should use the pointer's real global coordinates when calling `Activate`, `SecondaryActivate`, and `ContextMenu`. Passing `0, 0` broke right click menus for apps here.
- Do not decide tray visibility using `button.isVisible()` during startup. The tray host may still be under a hidden parent while the bar is constructing. Use hidden-state / item state instead so the tray does not hide itself permanently before the bar is shown.
- Tray icons may come from either `IconName` or `IconPixmap`. Keep both paths working.
- `IconPixmap` rendering and optional tinting are currently fast enough in Python for this environment. Prefer the PyQt path first before offloading tray icon processing to the C service.
- The bar now supports a dedicated `tray_offset` setting. Use that for tray vertical alignment rather than shifting the entire status block when only the tray is off.
- Tray tinting should follow the live Matugen palette only when Matugen is enabled and the bar setting `tray_tint_with_matugen` is on.
- If tray icons disappear again, verify these in order:
  - `org.kde.StatusNotifierWatcher` exists on the session bus
  - `RegisteredStatusNotifierItems` is non-empty
  - tray items respond on `/StatusNotifierItem` or their registered object path
  - the tray host is not hiding itself during startup
  - the bar was fully restarted after tray changes

## Notification Center Notes

- The notification center is a native PyQt6 recreation of `hanauta/src/pyqt/notification-center/idea.html`.
- Keep the current compact Material 3 expressive direction unless the user asks for a new visual direction.
- Quick settings and media controls should remain wired to the shared helper scripts instead of duplicating shell logic in Python.

## Notification Toast Notes

- The active desktop notification toast renderer currently comes from the native GTK daemon at `hanauta/bin/hanauta-notifyd`, launched by `startup.sh`, not the PyQt file at `hanauta/src/pyqt/notification-daemon/notification_daemon.py`.
- Toast styling should be changed first in `hanauta/src/service/hanauta-notifyd.css`.
- The daemon also has a built-in fallback CSS template in `hanauta/src/service/hanauta-notifyd.c`; keep it aligned with `hanauta-notifyd.css` so styling still works if the CSS file is unavailable.
- The actual content inset from the toast border is controlled by the `#content` padding in CSS and the matching `gtk_container_set_border_width(...)` on the inner `content` box in `hanauta/src/service/hanauta-notifyd.c`.
- After notification daemon styling or layout changes, rebuild with `bash hanauta/src/service/build.sh` and restart `hanauta/bin/hanauta-notifyd` or rerun `startup.sh`, otherwise the old binary/process will keep rendering the previous toast layout.

## i3 Integration

- i3 should start the PyQt bar, not Eww.
- i3 currently starts the bar and dock through Python with `PYTHONPATH` pointing at `hanauta/src`.
- Keep the hybrid launch model unless the user explicitly asks to revisit Nuitka for the shell itself.
- Do not add Eww daemon startup back into `config` or `startup.sh`.
- If bar visibility across workspaces regresses, check both:
  - i3 `for_window` rules
  - Qt dock/sticky window setup in `ui_bar.py`

## Verification

- After PyQt code changes, run:
  - `python3 -m py_compile hanauta/src/pyqt/bar/ui_bar.py`
  - `python3 -m py_compile hanauta/src/pyqt/notification-center/notification_center.py`
  - `python3 -m py_compile hanauta/src/pyqt/bar/status_notifier_watcher.py`
  - `python3 -m py_compile hanauta/src/pyqt/settings-page/settings.py`
- If a change touches i3 startup behavior, also validate:
  - `bash -n startup.sh`
