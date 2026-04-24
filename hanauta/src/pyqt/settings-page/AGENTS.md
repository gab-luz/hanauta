# Agent Notes: `settings-page` (Dismantling Map)

This directory is being dismantled - `settings.py` is being refactored into
modular components in `settings_page/`.

## Entry Point

- `settings.py`: main PyQt6 Settings app (~20K lines, being reduced)

## Extracted Modules (32 modules in `settings_page/`)

- `settings_page/theme_data.py` - theme palettes + THEME_LIBRARY + paths
- `settings_page/theme_gtk.py` - GTK theme install/apply helpers
- `settings_page/mail_store.py` - MailAccountStore + mail config
- `settings_page/settings_defaults.py` - load_settings_state() + defaults
- `settings_page/xrandr.py` - parse_xrandr_state()
- `settings_page/picom_config.py` - picom config helpers
- `settings_page/widgets.py` - IconLabel, NavPillButton, etc
- `settings_page/ui_widgets.py` - SwitchButton, PreviewCard, SettingsRow, etc
- `settings_page/marketplace.py` - marketplace API
- `settings_page/startup.py` - restore functions
- `settings_page/fonts.py` - font helpers
- `settings_page/dock_settings.py` - dock config
- `settings_page/workers.py` - background workers
- `settings_page/notification_state.py` - notification rules state
- `settings_page/plugin_backends.py` - plugin backends (gamemode, weather, HA)
- `settings_page/services.py` - service resolution helpers
- `settings_page/settings_store.py` - settings JSON paths + atomic write
- +15 more helpers (formatting, display_utils, battery, etc.)

## Refactor Status

- Significant code moved out of settings.py
- Working imports from modular components
- Still more duplicate code to remove
