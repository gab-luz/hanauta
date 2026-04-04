# SKILLS.md

## Hanauta Core Editing

- Scope changes to the active stack first: PyQt (`hanauta/src/pyqt/...`), not Eww.
- Prefer settings-driven behavior over hardcoded logic when adding UX options.
- Keep plugin-specific behavior inside plugin repos when possible; only generalize in core when reusable.
- Preserve bar stability patterns:
  - no heavy work on GUI thread
  - avoid unnecessary relayout churn
  - keep polling intervals pragmatic

## Bar + Plugin Icon Work

- Use bar settings as the single source of truth for icon behavior:
  - `bar.use_color_widget_icons` for mono-vs-color icon preference
  - `bar.debug_tooltips` for diagnostics
- For monochrome mode, prefer tinting `icon.svg` using current bar accent color.
- For color mode, prefer `icon_color.svg` and keep fallback chain to `icon.svg`.
- After icon changes, test both modes:
  - dark/light static themes
  - wallpaper-aware mode
  - plugin enabled/disabled visibility states

## Settings Page Work

- Add new toggles under the most relevant section (usually Bar for bar behavior).
- Wire toggle -> setter -> `_save_bar_settings()` (or equivalent save path).
- Ensure defaults exist in both:
  - runtime defaults (bar/settings loader)
  - settings page defaults

## Tooltip/Debug UX

- User-facing tooltips should describe actions or state.
- Internal debug labels should be gated behind a debug setting and default to off.
- Avoid setting placeholder tooltips like `IconButton <name>` in production path.

## Verification Routine

- Always run:
  - `python3 -m py_compile hanauta/src/pyqt/bar/ui_bar.py`
  - `python3 -m py_compile hanauta/src/pyqt/notification-center/notification_center.py`
  - `python3 -m py_compile hanauta/src/pyqt/bar/status_notifier_watcher.py`
  - `python3 -m py_compile hanauta/src/pyqt/settings-page/settings.py`
- If startup/integration changed:
  - `bash -n startup.sh`

## Git Hygiene

- Do not revert unrelated local changes.
- Commit only the files needed for the requested change.
- Keep commit messages scoped to behavior, not implementation details.
