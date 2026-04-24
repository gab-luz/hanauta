# Agent Notes: `settings-page` (Dismantling Map)

This directory used to be a single giant `settings.py` script. The goal is to keep
`settings.py` as the runnable entry point while gradually moving data/helpers into
smaller modules.

## Entry Point

- `settings.py`: main PyQt6 Settings app (still large; being dismantled)

## Extracted Modules (New)

- `settings_page/material_icons.py`: Material icon codepoints + `material_icon(...)`
- `settings_page/bar_settings.py`: bar defaults + `merged_bar_settings(...)` + bar service icon maps
- `settings_page/service_settings.py`: default service settings + `merged_service_settings(...)`
- `settings_page/presets.py`: preset lists for:
  - `VOICE_LANGUAGE_PRESETS` (BCP-47 tags like `pt-BR`)
  - `LOCALE_LANGUAGE_PRESETS` (Linux locales like `pt_BR.UTF-8`)
- `settings_page/notification_rules.py`: default notification rules + load/save INI helpers
- `settings_page/picom_presets.py`: picom default template + default rule file contents
- `settings_page/wallpaper_presets.py`: wallpaper source presets (syncable repos)
- `settings_page/settings_store.py`: settings JSON paths + `_atomic_write_json_file(...)` + `save_settings_state(...)`
- `settings_page/__init__.py`: convenience re-exports

## Existing Modules

- `settings_languages.py`: keyboard layout presets (used by Region tab autocomplete)

## Refactor Direction (Next Moves)

- Move “settings state” IO + defaults into a small module (keep JSON schema stable).
- Split `SettingsWindow` page builders into `pages/` modules (Overview/Region/Services/...).
- Split shared UI widgets (`SettingsRow`, cards, switches) into `ui/` modules.
