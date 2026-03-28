# Hanauta Plugin Architecture

This document defines how Hanauta plugins integrate with the shell while keeping core Hanauta fully usable without any non-core plugin.

## Goals

- Hanauta core must boot and run with **zero optional plugins installed**.
- Optional features (widgets/services) are delivered as plugins and only appear after installation.
- Plugins integrate through stable contracts so they can be updated independently.

## Folder Layout

- Core plugin install root (default):
  - `/home/<user>/.config/i3/hanauta/plugins`
- Plugin catalog repo:
  - `https://github.com/gab-luz/hanauta-plugins`
- Local plugin dev repo example:
  - `/home/<user>/dev/hanauta-plugin-study-tracker`

A plugin directory should contain at least:

- `hanauta_plugin.py` (entrypoint used by Settings)
- `hanauta_bar_plugin.py` (optional entrypoint used by Bar integrations)
- `hanauta-service-plugin.json` (optional manifest for background tasks via `hanauta-service`)
- `icon.svg` or `icon.png` at plugin root (used in Services section header icon)
- plugin runtime files (`study_tracker_popup.py`, assets, etc.)

## Settings Integration Contract

`settings.py` dynamically loads service sections from installed plugins.

### Discovery

Settings searches plugin folders from:

1. marketplace `install_dir` in settings
2. fallback `/home/<user>/.config/i3/hanauta/plugins`

A directory is treated as a plugin when `hanauta_plugin.py` exists.

For installed plugins listed in marketplace metadata, Hanauta can prefer a dev override at:

- `/home/<user>/dev/<plugin-folder-name>/hanauta_plugin.py`

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

### New Plugin Runtime Helpers

To keep plugin behavior consistent with Hanauta internals, plugin APIs now also expose:

- `polkit_available() -> bool`
- `build_polkit_command(command: list[str]) -> list[str]`
- `run_with_polkit(command: list[str], detached: bool = True, env: dict[str, str] | None = None, timeout: float | None = None) -> bool`
- `trigger_fullscreen_alert(title: str, body: str, severity: str = "discrete") -> bool`

Notes:

- `run_with_polkit(...)` uses the same `pkexec` + polkit path already used by Hanauta widgets.
- `trigger_fullscreen_alert(...)` uses the native PyQt reminder fullscreen alert (`widget-reminders/reminder_alert.py`), not the regular toast daemon.
- These keys are additive and optional; existing plugins continue to work unchanged.

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
- Optional metadata for plugin capability/requirement disclosure:
  - `capabilities`: list (or boolean map) of feature flags such as:
    - `polkit`
    - `fullscreen_alert`
  - `requirements`: list of runtime requirements (examples: `pkexec`, `wireguard-tools`)

## Catalog Schema Proposal (v3 Draft)

The catalog at `hanauta-plugins/plugins.json` now contains a concrete draft proposal under:

- `standards.version = 3`
- `standards.status = "draft-proposal"`

### Exact Plugin Field Names

Required per plugin object:

- `id: str`
- `name: str`
- `repo: str`

Optional per plugin object:

- `description: str`
- `branch: str`
- `path: str`
- `entrypoint: str`
- `capabilities: list[str] | dict[str, bool]`
- `requirements: list[str]`
- `api_min_version: int`
- `api_target_version: int`
- `permissions: dict[str, object]`
- `compatibility: dict[str, object]`
- `x-<vendor-field>: any` (custom plugin-side metadata)

### Capability IDs (Proposed)

- `notifications`
- `popup_host`
- `quick_settings`
- `launcher_commands`
- `status_chips`
- `workspace_events`
- `window_events`
- `theme_tokens`
- `theme_reactive`
- `polkit`
- `fullscreen_alert`
- `fullscreen_overlay`
- `task_scheduler`
- `state_store`
- `secret_store`
- `dbus`
- `system_metrics`
- `media_controls`
- `context_menu`
- `permissions_manifest`
- `plugin_health`

### Compatibility Rules

- Unknown top-level fields and unknown plugin fields must be ignored by Hanauta loaders.
- Unknown capability keys and permission keys must be ignored, not treated as hard errors.
- `api_min_version` defaults to `1` when omitted.
- `api_target_version` defaults to `1` when omitted.
- If `host_api_version < api_min_version`: mark plugin as incompatible and do not load.
- If `api_target_version > host_api_version` and `api_min_version` is satisfied: plugin may load in compatibility mode.
- New fields must be additive first; removals require deprecation cycle.
- Deprecation policy target:
  - announce at least 2 releases before removal
  - keep at least 60 days notice
  - actual removal only in a major API version bump

Current enforcement in Hanauta:

- Marketplace blocks install when `api_min_version` is higher than host plugin API version (`1` right now).
- Marketplace shows a confirmation warning before install when plugin metadata declares sensitive permissions/capabilities.
- Settings and Bar plugin loaders skip installed plugins whose `api_min_version` exceeds host support.

### Proposed Extended API Helper Surface

Draft helper keys intended for progressive rollout:

- `notify`
- `open_popup`
- `register_quick_setting_tile`
- `register_launcher_command`
- `add_status_chip`
- `workspace_event_stream`
- `window_event_stream`
- `theme_tokens`
- `on_theme_changed`
- `privileged_task`
- `fullscreen_overlay`
- `background_task_scheduler`
- `state_store`
- `secure_secret_store`
- `dbus_bridge`
- `system_metrics_feed`
- `media_controls_api`
- `context_menu_api`
- `permissions_manifest`
- `plugin_health_panel`

## Independence Rules (Core vs Plugins)

Core Hanauta must:

- Start bar, dock, notification center, settings without optional plugins.
- Hide plugin-only UI sections when plugin is not installed.
- Never crash if a plugin is missing, invalid, or incompatible.

Plugins must:

- Contain all runtime assets/scripts they need.
- Use only documented integration hooks.
- Avoid patching core files at runtime.

## Native Service Bridge Contract

Plugins can register background jobs with native `hanauta-service` using:

- `hanauta-service-plugin.json` at plugin root

Manifest shape:

```json
{
  "plugin_id": "ani_cli_widget",
  "tasks": [
    {
      "id": "catalog_preload",
      "enabled": true,
      "interval_seconds": 300,
      "timeout_seconds": 25,
      "working_dir": "${PLUGIN_DIR}",
      "command": ["python3", "${PLUGIN_DIR}/service_preload.py"]
    }
  ]
}
```

Rules:

- `plugin_id`: stable plugin identifier.
- `tasks[].id`: stable task identifier within plugin.
- `tasks[].enabled`: optional, default `true`.
- `tasks[].interval_seconds`: minimum 20 seconds enforced by service.
- `tasks[].command`: required argv array.
- `tasks[].working_dir`: optional.
- Token expansion supported in command/working dir:
  - `${PLUGIN_DIR}`
  - `${HOME}`

Discovery roots for service bridge:

- `~/.config/i3/hanauta/plugins/*`
- `~/dev/hanauta-plugin-*`

Bridge behavior:

- Core service stays plugin-agnostic (no plugin-specific code in C).
- Service executes due tasks on its normal refresh cadence.
- Failed tasks retry with a shorter backoff.
- Plugin tasks should write their own cache files under:
  - `~/.local/state/hanauta/service/plugins/`

## Study Tracker Plugin (Current)

Study Tracker is now plugin-powered for Services tab integration.

- Plugin repo: `/home/<user>/dev/hanauta-plugin-study-tracker`
- Installed copy: `/home/<user>/.config/i3/hanauta/plugins/hanauta-plugin-study-tracker`
- Entrypoint file:
  - `hanauta_plugin.py`

The Services tab section is created via plugin builder, not hardcoded core section assembly.

## RSS Widget Plugin (Current)

RSS widget shell files were decoupled from core and moved to a plugin repository.

- Plugin repo: `/home/<user>/dev/hanauta-plugin-rss`
- Catalog id: `rss_widget`
- Runtime files now live in plugin root:
  - `rss_widget.py`
  - `rss_widget.qml`
  - `rss_settings.qml`

## Recommended Workflow for New Plugins

1. Create repo `hanauta-plugin-<name>`.
2. Add `hanauta_plugin.py` with `register_hanauta_plugin()`.
3. Add plugin to `hanauta-plugins/plugins.json` catalog.
4. Install from Marketplace.
5. Verify plugin section appears in Services tab.
6. Keep plugin updates in plugin repo, not core Hanauta repo.
