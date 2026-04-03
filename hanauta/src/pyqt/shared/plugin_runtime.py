from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Sequence

from pyqt.shared.runtime import project_root


SETTINGS_FILE = (
    Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
)
PLUGIN_DEV_ROOT = Path.home() / "dev"
PLUGIN_ENTRYPOINT = "hanauta_plugin.py"


def _safe_read_settings() -> dict[str, object]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _tokens(values: Sequence[str] | None) -> set[str]:
    if not values:
        return set()
    normalized = {_normalize_token(item) for item in values if str(item).strip()}
    return {item for item in normalized if item}


def _path_matches_hints(path: Path, hints: set[str]) -> bool:
    if not hints:
        return True
    candidates = {
        _normalize_token(path.name),
        _normalize_token(str(path)),
    }
    for hint in hints:
        if not hint:
            continue
        for candidate in candidates:
            if hint in candidate or candidate in hint:
                return True
    return False


def plugin_search_roots() -> list[Path]:
    settings = _safe_read_settings()
    marketplace = settings.get("marketplace", {}) if isinstance(settings, dict) else {}
    marketplace = marketplace if isinstance(marketplace, dict) else {}
    install_dir = str(marketplace.get("install_dir", "")).strip()
    roots: list[Path] = []
    if install_dir:
        roots.append(Path(install_dir).expanduser())
    roots.extend(
        [
            project_root() / "hanauta" / "plugins",
            Path.home() / ".config" / "i3" / "hanauta" / "plugins",
            PLUGIN_DEV_ROOT,
        ]
    )
    seen: set[str] = set()
    ordered: list[Path] = []
    for root in roots:
        try:
            key = str(root.expanduser().resolve())
        except Exception:
            key = str(root.expanduser())
        if key in seen:
            continue
        seen.add(key)
        ordered.append(root.expanduser())
    return ordered


def discover_plugin_dirs(
    hints: Sequence[str] | None = None, *, require_entrypoint: bool = True
) -> list[Path]:
    settings = _safe_read_settings()
    marketplace = settings.get("marketplace", {}) if isinstance(settings, dict) else {}
    marketplace = marketplace if isinstance(marketplace, dict) else {}
    installed = marketplace.get("installed_plugins", [])
    hint_tokens = _tokens(hints)
    seen: set[str] = set()
    found: list[Path] = []

    if isinstance(installed, list):
        for row in installed:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if hint_tokens and plugin_id:
                id_token = _normalize_token(plugin_id)
                if id_token and not any(
                    token in id_token or id_token in token for token in hint_tokens
                ):
                    continue
            install_path = str(row.get("install_path", "")).strip()
            if not install_path:
                continue
            plugin_dir = Path(install_path).expanduser()
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                continue
            if require_entrypoint and not (plugin_dir / PLUGIN_ENTRYPOINT).exists():
                continue
            if hint_tokens and not _path_matches_hints(plugin_dir, hint_tokens):
                continue
            key = str(plugin_dir.resolve())
            if key in seen:
                continue
            seen.add(key)
            found.append(plugin_dir)

    for root in plugin_search_roots():
        if not root.exists() or not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            if hint_tokens and not _path_matches_hints(child, hint_tokens):
                continue
            if require_entrypoint and not (child / PLUGIN_ENTRYPOINT).exists():
                continue
            key = str(child.resolve())
            if key in seen:
                continue
            seen.add(key)
            found.append(child)
    return found


def resolve_plugin_script(
    script_name: str,
    hints: Sequence[str] | None = None,
    *,
    required: bool = True,
) -> Path | None:
    target = str(script_name).strip()
    if not target:
        return None
    for plugin_dir in discover_plugin_dirs(hints):
        candidate = plugin_dir / target
        if candidate.exists():
            return candidate
    if not required:
        for plugin_dir in discover_plugin_dirs(hints, require_entrypoint=False):
            candidate = plugin_dir / target
            if candidate.exists():
                return candidate
    return None


def resolve_first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None
