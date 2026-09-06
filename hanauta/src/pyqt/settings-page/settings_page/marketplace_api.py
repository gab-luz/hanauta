from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from settings_page.settings_store import save_settings_state


def _log(message: str) -> None:
    print(f"[marketplace] {message}", flush=True)


def _marketplace_state(settings: Any) -> dict[str, Any]:
    if not isinstance(settings, dict):
        return {}
    marketplace = settings.setdefault("marketplace", {})
    if not isinstance(marketplace, dict):
        marketplace = {}
        settings["marketplace"] = marketplace
    return marketplace


def _normalize_plugin_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    plugin_id = str(row.get("id", "")).strip()
    repo = str(row.get("repo", "")).strip()
    if not plugin_id or not repo:
        return None
    normalized = dict(row)
    normalized["id"] = plugin_id
    normalized["repo"] = repo
    normalized["name"] = str(normalized.get("name", plugin_id)).strip() or plugin_id
    normalized["branch"] = str(normalized.get("branch", "main")).strip() or "main"
    normalized["path"] = str(normalized.get("path", "")).strip()
    normalized["entrypoint"] = str(normalized.get("entrypoint", "")).strip()
    return normalized


def _catalog_sources(marketplace: dict[str, Any]) -> list[dict[str, str]]:
    sources = marketplace.get("catalog_sources", [])
    rows: list[dict[str, str]] = []
    if isinstance(sources, list):
        for item in sources:
            if not isinstance(item, dict):
                continue
            repo_url = str(item.get("repo_url", item.get("repo", ""))).strip()
            if not repo_url:
                continue
            rows.append(
                {
                    "repo_url": repo_url,
                    "branch": str(item.get("branch", "main")).strip() or "main",
                    "manifest_path": str(item.get("manifest_path", "plugins.json"))
                    .strip()
                    .lstrip("/")
                    or "plugins.json",
                }
            )
    if not rows:
        rows = [
        {
            "repo_url": str(
                marketplace.get(
                    "catalog_repo_url", "https://github.com/gab-luz/hanauta-plugins"
                )
            ).strip()
            or "https://github.com/gab-luz/hanauta-plugins",
            "branch": str(marketplace.get("catalog_branch", "main")).strip() or "main",
            "manifest_path": str(
                marketplace.get("catalog_manifest_path", "plugins.json")
            )
            .strip()
            .lstrip("/")
            or "plugins.json",
        }
    ]

    # Dev/local fallback catalogs so refresh picks local registry changes
    # before they are pushed upstream.
    local_registry_roots = [
        Path("/mnt/outros/DEV/hanauta-plugins"),
        Path.home() / "dev" / "hanauta-plugins",
    ]
    for root in local_registry_roots:
        manifest = root / "plugins.json"
        if not manifest.exists():
            continue
        rows.append(
            {
                "repo_url": str(root),
                "branch": "main",
                "manifest_path": "plugins.json",
            }
        )

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("repo_url", "")).strip(),
            str(row.get("branch", "main")).strip() or "main",
            str(row.get("manifest_path", "plugins.json")).strip().lstrip("/")
            or "plugins.json",
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            {"repo_url": key[0], "branch": key[1], "manifest_path": key[2]}
        )
    return deduped


def _manifest_raw_url(source: dict[str, str]) -> str:
    repo_url = source.get("repo_url", "")
    branch = source.get("branch", "main")
    manifest_path = source.get("manifest_path", "plugins.json")
    repo_path = Path(repo_url).expanduser()
    if repo_path.exists():
        if repo_path.is_dir():
            return str(repo_path / manifest_path)
        return str(repo_path)
    if repo_url.startswith("https://github.com/"):
        slug = repo_url.removeprefix("https://github.com/").strip().strip("/")
        return f"https://raw.githubusercontent.com/{slug}/{branch}/{manifest_path}"
    if repo_url.startswith("http://github.com/"):
        slug = repo_url.removeprefix("http://github.com/").strip().strip("/")
        return f"https://raw.githubusercontent.com/{slug}/{branch}/{manifest_path}"
    return repo_url.rstrip("/") + "/" + manifest_path


def _fetch_manifest(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme in {"", "file"}:
        path = (
            Path(parsed.path).expanduser()
            if parsed.scheme == "file"
            else Path(url).expanduser()
        )
        data = path.read_text(encoding="utf-8")
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError("manifest payload is not an object")
        return payload
    req = urllib.request.Request(
        url, headers={"User-Agent": "Hanauta-Marketplace/1.0"}
    )
    with urllib.request.urlopen(req, timeout=8.0) as response:
        data = response.read().decode("utf-8")
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError("manifest payload is not an object")
    return payload


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _git_detail(result: subprocess.CompletedProcess[str], fallback: str) -> str:
    return (result.stderr or result.stdout or fallback).strip()


def _git_has_local_changes(install_path: Path) -> bool:
    status_result = _git(
        ["status", "--porcelain=v1", "--untracked-files=all"], install_path
    )
    if status_result.returncode != 0:
        detail = _git_detail(status_result, "git status failed")
        raise RuntimeError(detail)
    return bool((status_result.stdout or "").strip())


def _git_stash_local_changes(install_path: Path, plugin_id: str) -> bool:
    try:
        dirty = _git_has_local_changes(install_path)
    except RuntimeError as exc:
        raise RuntimeError(f"{plugin_id}: {exc}") from exc
    if not dirty:
        return False
    stash_result = _git(
        [
            "stash",
            "push",
            "--include-untracked",
            "-m",
            f"marketplace update for {plugin_id}",
        ],
        install_path,
    )
    if stash_result.returncode != 0:
        detail = _git_detail(stash_result, "git stash push failed")
        raise RuntimeError(f"{plugin_id}: {detail}")
    return True


def _git_restore_stash(install_path: Path, plugin_id: str) -> tuple[bool, str]:
    apply_result = _git(["stash", "apply", "--index", "stash@{0}"], install_path)
    if apply_result.returncode != 0:
        detail = _git_detail(apply_result, "git stash apply failed")
        _log(f"Could not reapply stashed changes for {plugin_id}: {detail}")
        return False, detail

    drop_result = _git(["stash", "drop", "stash@{0}"], install_path)
    if drop_result.returncode != 0:
        detail = _git_detail(drop_result, "git stash drop failed")
        _log(f"Applied stashed changes for {plugin_id}, but could not drop stash: {detail}")
        return True, detail

    return True, ""


def _plugin_dedupe_keys(plugin: dict[str, Any]) -> list[str]:
    """Return dedupe keys for a plugin: id, repo url, and install path."""
    keys = []
    plugin_id = str(plugin.get("id", "")).strip()
    repo = str(plugin.get("repo", "")).strip().lower().rstrip("/").removesuffix(".git")
    install_path = str(plugin.get("install_path", "")).strip()
    if plugin_id:
        keys.append(f"id:{plugin_id}")
    if repo:
        keys.append(f"repo:{repo}")
    if install_path:
        keys.append(f"path:{install_path}")
    return keys


def _installed_preference_score(plugin: dict[str, Any], install_dir: str) -> tuple[int, float]:
    """Score an installed entry for dedupe resolution.

    Prefer the entry whose install_path lives under the marketplace install_dir
    (the officially managed location), then the most recently updated one.
    """
    install_path = str(plugin.get("install_path", "")).strip()
    in_install_dir = 0
    if install_dir and install_path:
        try:
            if Path(install_path).resolve().is_relative_to(Path(install_dir).expanduser().resolve()):
                in_install_dir = 1
        except OSError:
            in_install_dir = 0
    updated = plugin.get("updated_at_epoch") or plugin.get("installed_at_epoch") or 0
    try:
        updated = float(updated)
    except (TypeError, ValueError):
        updated = 0.0
    return in_install_dir, updated


def marketplace_api_installed_plugins(settings: Any) -> list[dict[str, Any]]:
    marketplace = _marketplace_state(settings)
    rows = marketplace.get("installed_plugins", [])
    if not isinstance(rows, list):
        return []
    install_dir = str(marketplace.get("install_dir", "")).strip()
    normalized: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    removed_duplicates = False
    for row in rows:
        plugin = _normalize_plugin_row(row)
        if plugin is None:
            removed_duplicates = True
            continue
        keys = _plugin_dedupe_keys(plugin)
        existing_index = next((seen[key] for key in keys if key in seen), None)
        if existing_index is not None:
            removed_duplicates = True
            current = normalized[existing_index]
            new_score = _installed_preference_score(plugin, install_dir)
            cur_score = _installed_preference_score(current, install_dir)
            if new_score > cur_score:
                # Replace with the better entry; keep original position.
                _log(
                    f"Dedupe: keeping '{plugin['id']}' over '{current['id']}' "
                    f"(repo={plugin.get('repo', '')})"
                )
                for key in _plugin_dedupe_keys(current):
                    seen.pop(key, None)
                normalized[existing_index] = plugin
                seen.update({key: existing_index for key in keys})
            else:
                _log(
                    f"Dedupe: keeping '{current['id']}' over '{plugin['id']}' "
                    f"(repo={plugin.get('repo', '')})"
                )
                seen.update({key: existing_index for key in keys})
            continue
        seen.update({key: len(normalized) for key in keys})
        normalized.append(plugin)
    if removed_duplicates:
        marketplace["installed_plugins"] = normalized
        save_settings_state(settings)
        _log(f"Installed plugins deduplicated. kept={len(normalized)}")
    return normalized


def marketplace_api_refresh_catalog_cache(
    settings: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    marketplace = _marketplace_state(settings)
    merged: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for source in _catalog_sources(marketplace):
        url = _manifest_raw_url(source)
        try:
            _log(f"Refreshing catalog source: {url}")
            payload = _fetch_manifest(url)
            plugins = payload.get("plugins", [])
            if not isinstance(plugins, list):
                raise ValueError("manifest has no plugins list")
            for row in plugins:
                plugin = _normalize_plugin_row(row)
                if plugin is None:
                    continue
                merged[plugin["id"]] = plugin
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{url}: {exc}")
            _log(f"Catalog source error: {url}: {exc}")

    catalog = sorted(merged.values(), key=lambda item: str(item.get("name", "")).lower())
    marketplace["catalog_cache"] = catalog
    save_settings_state(settings)
    _log(f"Catalog refreshed. plugins={len(catalog)} errors={len(errors)}")
    return catalog, errors


def marketplace_api_update_plugin(
    settings: Any, plugin_id: str
) -> tuple[bool, str]:
    plugin_id = str(plugin_id or "").strip()
    if not plugin_id:
        return False, "missing plugin id"
    marketplace = _marketplace_state(settings)
    rows = marketplace.get("installed_plugins", [])
    if not isinstance(rows, list):
        return False, "no installed plugins state"

    target: dict[str, Any] | None = None
    for row in rows:
        if isinstance(row, dict) and str(row.get("id", "")).strip() == plugin_id:
            target = row
            break
    if target is None:
        return False, f"{plugin_id} is not installed"

    install_path = Path(str(target.get("install_path", "")).strip()).expanduser()
    if not install_path.exists() or not install_path.is_dir():
        return False, f"{plugin_id}: install path is missing"
    if not (install_path / ".git").exists():
        return False, f"{plugin_id}: install path is not a git repository"

    branch = str(target.get("branch", "main")).strip() or "main"
    _log(f"Updating plugin {plugin_id} in {install_path} (branch={branch})")

    stashed_local_changes = False
    try:
        stashed_local_changes = _git_stash_local_changes(install_path, plugin_id)
    except RuntimeError as exc:
        detail = str(exc).strip()
        _log(f"Update failed for {plugin_id}: {detail}")
        return False, detail

    fetch_result = _git(["fetch", "origin", branch], install_path)
    if fetch_result.returncode != 0:
        detail = _git_detail(fetch_result, "git fetch failed")
        if stashed_local_changes:
            _git_restore_stash(install_path, plugin_id)
        _log(f"Update failed for {plugin_id}: {detail}")
        return False, f"{plugin_id}: {detail}"

    behind_result = _git(
        ["rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"], install_path
    )
    if behind_result.returncode != 0:
        detail = _git_detail(behind_result, "git rev-list failed")
        if stashed_local_changes:
            _git_restore_stash(install_path, plugin_id)
        _log(f"Update check failed for {plugin_id}: {detail}")
        return False, f"{plugin_id}: {detail}"

    ahead = 0
    behind = 0
    parts = (behind_result.stdout or "").strip().split()
    if len(parts) >= 2:
        try:
            ahead = int(parts[0])
            behind = int(parts[1])
        except Exception:
            ahead = 0
            behind = 0

    if behind <= 0:
        if stashed_local_changes:
            restored, restore_detail = _git_restore_stash(install_path, plugin_id)
            if restored and restore_detail:
                detail = (
                    f"{plugin_id} is already up to date. "
                    f"Local changes were restored, but the stash could not be dropped cleanly: {restore_detail}"
                )
            else:
                detail = f"{plugin_id} is already up to date."
        else:
            detail = f"{plugin_id} is already up to date."
        target["updated_at_epoch"] = int(time.time())
        save_settings_state(settings)
        _log(f"{plugin_id} already up to date")
        return True, detail

    pull_result = _git(["pull", "--ff-only", "origin", branch], install_path)
    if pull_result.returncode != 0:
        detail = _git_detail(pull_result, "git pull failed")
        if stashed_local_changes:
            _git_restore_stash(install_path, plugin_id)
        _log(f"Update failed for {plugin_id}: {detail}")
        return False, f"{plugin_id}: {detail}"

    restore_warning = ""
    if stashed_local_changes:
        restored, restore_detail = _git_restore_stash(install_path, plugin_id)
        if not restored:
            restore_warning = (
                " Local changes were preserved in a stash because they could not be "
                f"reapplied automatically: {restore_detail}"
            )
        elif restore_detail:
            restore_warning = (
                " Local changes were restored, but the stash could not be dropped "
                f"cleanly: {restore_detail}"
            )

    target["updated_at_epoch"] = int(time.time())
    save_settings_state(settings)
    _log(f"Updated {plugin_id}: pulled {behind} commit(s)")
    return True, f"{plugin_id} updated ({behind} commit(s) pulled).{restore_warning}"


def marketplace_api_update_all_plugins(
    settings: Any,
) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for row in marketplace_api_installed_plugins(settings):
        plugin_id = str(row.get("id", "")).strip()
        if not plugin_id:
            continue
        ok, detail = marketplace_api_update_plugin(settings, plugin_id)
        results.append((plugin_id, ok, detail))
    return results
