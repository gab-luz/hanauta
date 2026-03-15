# AGENTS.md

## Current UI Stack

- The active desktop UI is PyQt6, not Eww.
- Primary UI entry points:
  - `hanauta/src/pyqt/bar/ui_bar.py`
  - `hanauta/src/pyqt/notification-center/notification_center.py`
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
- The center section contains the clock/date and current media.
- The media visualizer uses `cava` raw output, configured by `hanauta/src/pyqt/bar/cava_bar.conf`.

## Notification Center Notes

- The notification center is a native PyQt6 recreation of `hanauta/src/pyqt/notification-center/idea.html`.
- Keep the current compact Material 3 expressive direction unless the user asks for a new visual direction.
- Quick settings and media controls should remain wired to the shared helper scripts instead of duplicating shell logic in Python.

## i3 Integration

- i3 should start the PyQt bar, not Eww.
- Do not add Eww daemon startup back into `config` or `startup.sh`.
- If bar visibility across workspaces regresses, check both:
  - i3 `for_window` rules
  - Qt dock/sticky window setup in `ui_bar.py`

## Verification

- After PyQt code changes, run:
  - `python3 -m py_compile hanauta/src/pyqt/bar/ui_bar.py`
  - `python3 -m py_compile hanauta/src/pyqt/notification-center/notification_center.py`
- If a change touches i3 startup behavior, also validate:
  - `bash -n startup.sh`
