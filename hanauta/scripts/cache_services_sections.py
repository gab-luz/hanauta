#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path


HOME = Path.home()
ROOT = HOME / ".config" / "i3"
SETTINGS_FILE = (
    HOME / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
)
CACHE_FILE = (
    HOME / ".local" / "state" / "hanauta" / "service" / "plugins" / "services-sections.json"
)
PLUGIN_ENTRYPOINT = "hanauta_plugin.py"


def _load_settings() -> dict[str, object]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _plugin_search_roots(settings: dict[str, object]) -> list[Path]:
    marketplace = settings.get("marketplace", {})
    install_dir = ""
    if isinstance(marketplace, dict):
        install_dir = str(marketplace.get("install_dir", "")).strip()
    roots = [
        Path(install_dir).expanduser() if install_dir else ROOT / "hanauta" / "plugins",
        ROOT / "hanauta" / "plugins",
        HOME / "dev",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.expanduser())
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _discover_plugin_dirs(settings: dict[str, object]) -> list[Path]:
    dirs: list[Path] = []
    seen: set[str] = set()
    for root in _plugin_search_roots(settings):
        if not root.exists() or not root.is_dir():
            continue
        if root.name == "dev":
            children = sorted(
                [
                    p
                    for p in root.iterdir()
                    if p.is_dir() and p.name.startswith("hanauta-plugin-")
                ]
            )
        else:
            children = sorted([p for p in root.iterdir() if p.is_dir()])
        for child in children:
            if not (child / PLUGIN_ENTRYPOINT).exists():
                continue
            resolved = str(child.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            dirs.append(child)
    return dirs


def _safe_icon_name(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        return "widgets"
    if len(text) > 40:
        return "widgets"
    return text


def _collect_rows_from_plugin(plugin_dir: Path) -> list[dict[str, object]]:
    entrypoint = plugin_dir / PLUGIN_ENTRYPOINT
    module_name = f"hanauta_plugin_service_cache_{hash(str(entrypoint)) & 0xFFFFFFFF:x}"
    plugin_path = str(plugin_dir)
    path_added = False
    try:
        if plugin_path not in sys.path:
            sys.path.insert(0, plugin_path)
            path_added = True
        spec = importlib.util.spec_from_file_location(module_name, str(entrypoint))
        if spec is None or spec.loader is None:
            return []
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        register = getattr(module, "register_hanauta_plugin", None)
        if not callable(register):
            return []
        payload = register()
    except Exception:
        return []
    finally:
        if path_added:
            try:
                sys.path.remove(plugin_path)
            except ValueError:
                pass

    if not isinstance(payload, dict):
        return []

    plugin_id = str(payload.get("id", plugin_dir.name)).strip() or plugin_dir.name
    plugin_name = str(payload.get("name", plugin_id)).strip() or plugin_id
    sections = payload.get("service_sections", [])
    if not isinstance(sections, list):
        return []

    rows: list[dict[str, object]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = str(section.get("key", "")).strip()
        if not key:
            continue
        label = str(section.get("label", "")).strip()
        if not label:
            label = plugin_name if len(sections) == 1 else key.replace("_", " ").title()
        rows.append(
            {
                "key": key,
                "label": label,
                "icon": _safe_icon_name(
                    section.get("icon_name", section.get("icon", "widgets"))
                ),
                "supports_show_in_bar": bool(section.get("supports_show_on_bar", False)),
                "plugin_id": plugin_id,
                "plugin_name": plugin_name,
                "plugin_dir": str(plugin_dir),
            }
        )
    return rows


def _collect_rows(settings: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for plugin_dir in _discover_plugin_dirs(settings):
        rows.extend(_collect_rows_from_plugin(plugin_dir))
    deduped: dict[str, dict[str, object]] = {}
    for row in rows:
        key = str(row.get("key", "")).strip()
        plugin_dir = str(row.get("plugin_dir", "")).strip()
        if not key or not plugin_dir:
            continue
        dedupe_key = f"{plugin_dir}::{key}"
        if dedupe_key not in deduped:
            deduped[dedupe_key] = row
    return [deduped[key] for key in sorted(deduped.keys())]


def main() -> int:
    settings = _load_settings()
    rows = _collect_rows(settings)
    payload = {
        "generated_at_epoch": int(time.time()),
        "rows": rows,
        "source": "cache_services_sections.py",
    }
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
