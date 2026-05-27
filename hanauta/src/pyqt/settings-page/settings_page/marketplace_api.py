from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

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
    if rows:
        return rows
    return [
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


def _manifest_raw_url(source: dict[str, str]) -> str:
    repo_url = source.get("repo_url", "")
    branch = source.get("branch", "main")
    manifest_path = source.get("manifest_path", "plugins.json")
    if repo_url.startswith("https://github.com/"):
        slug = repo_url.removeprefix("https://github.com/").strip().strip("/")
        return f"https://raw.githubusercontent.com/{slug}/{branch}/{manifest_path}"
    if repo_url.startswith("http://github.com/"):
        slug = repo_url.removeprefix("http://github.com/").strip().strip("/")
        return f"https://raw.githubusercontent.com/{slug}/{branch}/{manifest_path}"
    return repo_url.rstrip("/") + "/" + manifest_path


def _fetch_manifest(url: str) -> dict[str, Any]:
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


def marketplace_api_installed_plugins(settings: Any) -> list[dict[str, Any]]:
    marketplace = _marketplace_state(settings)
    rows = marketplace.get("installed_plugins", [])
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        plugin = _normalize_plugin_row(row)
        if plugin is None:
            continue
        plugin_id = plugin["id"]
        if plugin_id in seen:
            continue
        seen.add(plugin_id)
        normalized.append(plugin)
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

    fetch_result = _git(["fetch", "origin", branch], install_path)
    if fetch_result.returncode != 0:
        detail = (fetch_result.stderr or fetch_result.stdout or "git fetch failed").strip()
        _log(f"Update failed for {plugin_id}: {detail}")
        return False, f"{plugin_id}: {detail}"

    behind_result = _git(
        ["rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"], install_path
    )
    if behind_result.returncode != 0:
        detail = (behind_result.stderr or behind_result.stdout or "git rev-list failed").strip()
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
        target["updated_at_epoch"] = int(time.time())
        save_settings_state(settings)
        _log(f"{plugin_id} already up to date")
        return True, f"{plugin_id} is already up to date."

    pull_result = _git(["pull", "--ff-only", "origin", branch], install_path)
    if pull_result.returncode != 0:
        detail = (pull_result.stderr or pull_result.stdout or "git pull failed").strip()
        _log(f"Update failed for {plugin_id}: {detail}")
        return False, f"{plugin_id}: {detail}"

    target["updated_at_epoch"] = int(time.time())
    save_settings_state(settings)
    _log(f"Updated {plugin_id}: pulled {behind} commit(s)")
    return True, f"{plugin_id} updated ({behind} commit(s) pulled)."


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
