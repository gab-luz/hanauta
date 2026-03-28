# Hanauta Plugin Architecture

This document defines how Hanauta plugins integrate with the shell while keeping core Hanauta fully usable without any non-core plugin.

## Goals

- Hanauta core must boot and run with **zero optional plugins installed**.
- Optional features (widgets/services) are delivered as plugins and only appear after installation.
- Plugins integrate through stable contracts so they can be updated independently.

## Folder Layout

- Core plugin install root (default):
  - `/home/gabi/.config/i3/hanauta/plugins`
- Plugin catalog repo:
  - `https://github.com/gab-luz/hanauta-plugins`
- Local plugin dev repo example:
  - `/home/gabi/dev/hanauta-plugin-study-tracker`

A plugin directory should contain at least:

- `hanauta_plugin.py` (entrypoint used by Settings)
- `hanauta_bar_plugin.py` (optional entrypoint used by Bar integrations)
- `icon.svg` or `icon.png` at plugin root (used in Services section header icon)
- plugin runtime files (`study_tracker_popup.py`, assets, etc.)

## Settings Integration Contract

`settings.py` dynamically loads service sections from installed plugins.

### Discovery

Settings searches plugin folders from:

1. marketplace `install_dir` in settings
2. fallback `/home/gabi/.config/i3/hanauta/plugins`

A directory is treated as a plugin when `hanauta_plugin.py` exists.

For installed plugins listed in marketplace metadata, Hanauta can prefer a dev override at:

- `/home/gabi/dev/<plugin-folder-name>/hanauta_plugin.py`

This keeps the plugin "installed" requirement while still letting you iterate in a dev clone.

### Entrypoint API

Each plugin must expose:

```python
def register_hanauta_plugin() -> dict[str, object]:
    return {
        "id": "study_tracker_widget",
        "name": "Study Tracker",
        "service_sections": [
            {
                "key": "study_tracker_widget",
                "builder": build_study_tracker_service_section,
            }
        ],
    }
```

- `service_sections[].key` maps to `settings_state["services"][key]`
- `service_sections[].builder` is called by Settings as:
  - `builder(window, api)`

`api` provides shared classes/helpers (`SettingsRow`, `SwitchButton`, `ExpandableServiceSection`, `material_icon`, `entry_command`, `run_bg`).

## Service Visibility Rules

- Plugin service sections are shown only when plugin entrypoint is discoverable.
- Core services must not depend on plugin modules.
- If plugin loading fails, Settings must continue working (plugin is skipped).

## State Rules

- Plugin service config lives in the same settings file under:
  - `services.<plugin_service_key>`
- Plugin defaults must be created via `setdefault` inside plugin builder.
- Plugin install metadata is stored under:
  - `marketplace.installed_plugins[]`

## Marketplace Rules

- Catalog JSON defines plugin ids/repos/branches.
- Installing a plugin clones it into `install_dir/<plugin_id>`.
- Marketplace should not require bundling all plugins in core repository.

## Independence Rules (Core vs Plugins)

Core Hanauta must:

- Start bar, dock, notification center, settings without optional plugins.
- Hide plugin-only UI sections when plugin is not installed.
- Never crash if a plugin is missing, invalid, or incompatible.

Plugins must:

- Contain all runtime assets/scripts they need.
- Use only documented integration hooks.
- Avoid patching core files at runtime.

## Study Tracker Plugin (Current)

Study Tracker is now plugin-powered for Services tab integration.

- Plugin repo: `/home/gabi/dev/hanauta-plugin-study-tracker`
- Installed copy: `/home/gabi/.config/i3/hanauta/plugins/hanauta-plugin-study-tracker`
- Entrypoint file:
  - `hanauta_plugin.py`

The Services tab section is created via plugin builder, not hardcoded core section assembly.

## Recommended Workflow for New Plugins

1. Create repo `hanauta-plugin-<name>`.
2. Add `hanauta_plugin.py` with `register_hanauta_plugin()`.
3. Add plugin to `hanauta-plugins/plugins.json` catalog.
4. Install from Marketplace.
5. Verify plugin section appears in Services tab.
6. Keep plugin updates in plugin repo, not core Hanauta repo.
