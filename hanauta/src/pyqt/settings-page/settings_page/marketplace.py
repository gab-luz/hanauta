import base64
import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib import parse, request

from settings_page.settings_store import save_settings_state


def _marketplace_sources_from_state(settings: dict) -> list[dict[str, str]]:
    marketplace = settings.get("marketplace", {}) if isinstance(settings, dict) else {}
    if not isinstance(marketplace, dict):
        return []
    sources = marketplace.get("catalog_sources", [])
    normalized: list[dict[str, str]] = []
    if isinstance(sources, list):
        for row in sources:
            if not isinstance(row, dict):
                continue
            repo_url = str(row.get("repo_url", row.get("repo", ""))).strip()
            if not repo_url:
                continue
            normalized.append(
                {
                    "repo_url": repo_url,
                    "branch": str(row.get("branch", "main")).strip() or "main",
                    "manifest_path": str(
                        row.get(
                            "manifest_path",
                            row.get("catalog_manifest_path", "plugins.json"),
                        )
                    )
                    .strip()
                    .lstrip("/")
                    or "plugins.json",
                }
            )
    if normalized:
        return normalized
    repo = str(marketplace.get("catalog_repo_url", "")).strip()
    if not repo:
        return []
    return [
        {
            "repo_url": repo,
            "branch": str(marketplace.get("catalog_branch", "main")).strip() or "main",
            "manifest_path": str(
                marketplace.get("catalog_manifest_path", "plugins.json")
            )
            .strip()
            .lstrip("/")
            or "plugins.json",
        }
    ]


def _marketplace_manifest_url_for_source_api(
    repo_url: str, branch: str, manifest_path: str
) -> str:
    parsed = parse.urlparse(repo_url)
    if parsed.netloc.lower() == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            owner = parts[0]
            repo = parts[1].removesuffix(".git")
            return (
                f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{manifest_path}"
            )
    return repo_url.rstrip("/") + "/" + manifest_path


def _marketplace_fetch_manifest_payload_api(
    repo_url: str, branch: str, manifest_path: str
) -> object:
    parsed = parse.urlparse(repo_url)
    if parsed.netloc.lower() == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            owner = parts[0]
            repo = parts[1].removesuffix(".git")
            api_url = (
                f"https://api.github.com/repos/{owner}/{repo}/contents/{manifest_path}"
                f"?ref={branch}"
            )
            try:
                req = request.Request(
                    api_url,
                    headers={
                        "User-Agent": "HanautaSettings/Marketplace",
                        "Accept": "application/vnd.github+json",
                    },
                )
                with request.urlopen(req, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if isinstance(payload, dict):
                    content = str(payload.get("content", "")).strip()
                    if content:
                        content = content.replace("\n", "")
                        decoded = base64.b64decode(content).decode("utf-8")
                        return json.loads(decoded)
            except Exception:
                pass

    manifest_url = _marketplace_manifest_url_for_source_api(
        repo_url, branch, manifest_path
    )
    req = request.Request(
        manifest_url, headers={"User-Agent": "HanautaSettings/Marketplace"}
    )
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _marketplace_normalize_shortcuts_field_api(
    raw_shortcuts: object,
) -> list[dict[str, str]]:
    if not isinstance(raw_shortcuts, list):
        return []
    rows: list[dict[str, str]] = []
    for row in raw_shortcuts:
        if not isinstance(row, dict):
            continue
        combo = str(row.get("keys", row.get("shortcut", row.get("combo", "")) or "")).strip()
        command = str(row.get("command", row.get("i3_command", "") or "")).strip()
        description = str(row.get("description", row.get("label", row.get("action", "") or "") or "")).strip()
        if not combo or not command:
            continue
        rows.append(
            {
                "keys": combo,
                "command": command,
                "description": description,
            }
        )
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        signature = (
            f"{row.get('keys', '').strip().lower()}|"
            f"{row.get('command', '').strip().lower()}"
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(row)
    return deduped


def _marketplace_normalize_catalog_api(payload: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    plugins: object = payload
    if isinstance(payload, dict):
        plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return rows
    for item in plugins:
        if not isinstance(item, dict):
            continue
        plugin_id = str(item.get("id", "")).strip() or str(item.get("name", "")).strip().lower().replace(" ", "_")
        repo = str(item.get("repo", "")).strip() or str(item.get("repository", "")).strip()
        if not plugin_id or not repo:
            continue
        capabilities_raw = item.get("capabilities", [])
        capabilities: list[str] = []
        if isinstance(capabilities_raw, dict):
            capabilities = [
                str(key).strip()
                for key, enabled in capabilities_raw.items()
                if str(key).strip() and bool(enabled)
            ]
        elif isinstance(capabilities_raw, list):
            capabilities = [str(value).strip() for value in capabilities_raw if str(value).strip()]
        requirements_raw = item.get("requirements", [])
        requirements: list[str] = []
        if isinstance(requirements_raw, list):
            requirements = [str(value).strip() for value in requirements_raw if str(value).strip()]
        try:
            api_min_version = int(item.get("api_min_version", 1) or 1)
        except Exception:
            api_min_version = 1
        try:
            api_target_version = int(item.get("api_target_version", 1) or 1)
        except Exception:
            api_target_version = 1
        rows.append(
            {
                "id": plugin_id,
                "name": str(item.get("name", plugin_id)).strip() or plugin_id,
                "description": str(item.get("description", "")).strip(),
                "repo": repo,
                "branch": str(item.get("branch", "main")).strip() or "main",
                "path": str(item.get("path", "")).strip(),
                "entrypoint": str(item.get("entrypoint", "")).strip(),
                "capabilities": capabilities,
                "requirements": requirements,
                "api_min_version": max(1, api_min_version),
                "api_target_version": max(1, api_target_version),
                "permissions": item.get("permissions", {})
                if isinstance(item.get("permissions", {}), dict)
                else {},
                "shortcuts": _marketplace_normalize_shortcuts_field_api(
                    item.get("shortcuts", [])
                ),
            }
        )
    return rows


def marketplace_api_refresh_catalog_cache(
    settings: dict,
) -> tuple[list[dict[str, object]], list[str]]:
    sources = _marketplace_sources_from_state(settings)
    merged: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    source_errors: list[str] = []
    for source in sources:
        repo_url = str(source.get("repo_url", "")).strip()
        branch = str(source.get("branch", "main")).strip() or "main"
        manifest_path = str(source.get("manifest_path", "plugins.json")).strip().lstrip("/") or "plugins.json"
        if not repo_url:
            continue
        try:
            payload = _marketplace_fetch_manifest_payload_api(
                repo_url, branch, manifest_path
            )
            catalog = _marketplace_normalize_catalog_api(payload)
            for plugin in catalog:
                plugin_id = str(plugin.get("id", "")).strip()
                if not plugin_id or plugin_id in seen_ids:
                    continue
                plugin["catalog_source"] = repo_url
                merged.append(plugin)
                seen_ids.add(plugin_id)
        except Exception as exc:
            source_errors.append(f"{repo_url}@{branch}: {exc}")
    marketplace = settings.setdefault("marketplace", {})
    if not isinstance(marketplace, dict):
        marketplace = {}
        settings["marketplace"] = marketplace
    marketplace["catalog_cache"] = merged
    save_settings_state(settings)
    return merged, source_errors


def marketplace_api_installed_plugins(settings: dict) -> list[dict[str, object]]:
    marketplace = settings.get("marketplace", {}) if isinstance(settings, dict) else {}
    if not isinstance(marketplace, dict):
        return []
    rows = marketplace.get("installed_plugins", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _installed_plugin_entry_by_id_api(
    settings: dict, plugin_id: str
) -> dict[str, object] | None:
    target = str(plugin_id).strip()
    if not target:
        return None
    for row in marketplace_api_installed_plugins(settings):
        if str(row.get("id", "")).strip() == target:
            return row
    return None


def marketplace_api_update_plugin(
    settings: dict, plugin_id: str
) -> tuple[bool, str]:
    ROOT = Path(__file__).resolve().parents[2].parents[1]
    entry = _installed_plugin_entry_by_id_api(settings, plugin_id)
    if entry is None:
        return False, f"{plugin_id}: not found in installed_plugins."
    install_path = Path(str(entry.get("install_path", "")).strip()).expanduser()
    if not str(install_path).strip():
        install_root = Path(
            str(settings.get("marketplace", {}).get("install_dir", ROOT / "hanauta" / "plugins"))
        ).expanduser()
        install_path = install_root / str(plugin_id).strip()
    if not install_path.exists():
        return False, f"{plugin_id}: install path does not exist ({install_path})."
    if not (install_path / ".git").exists():
        return False, f"{plugin_id}: install path is not a git repository."
    branch = str(entry.get("branch", "main")).strip() or "main"
    if shutil.which("git") is None:
        return False, "git is required for marketplace update."
    fetch = subprocess.run(
        ["git", "-C", str(install_path), "fetch", "origin", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if fetch.returncode != 0:
        detail = (fetch.stderr or fetch.stdout or "").strip() or "git fetch failed"
        return False, f"{plugin_id}: {detail}"
    pull = subprocess.run(
        ["git", "-C", str(install_path), "pull", "--ff-only", "origin", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if pull.returncode != 0:
        detail = (pull.stderr or pull.stdout or "").strip() or "git pull failed"
        return False, f"{plugin_id}: {detail}"
    entry["install_path"] = str(install_path)
    entry["updated_at_epoch"] = int(time.time())
    save_settings_state(settings)
    detail = (pull.stdout or pull.stderr or "").strip() or "up to date"
    return True, f"{plugin_id}: {detail}"


def marketplace_api_update_all_plugins(settings: dict) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    seen: set[str] = set()
    for row in marketplace_api_installed_plugins(settings):
        plugin_id = str(row.get("id", "")).strip()
        if not plugin_id or plugin_id in seen:
            continue
        seen.add(plugin_id)
        ok, detail = marketplace_api_update_plugin(settings, plugin_id)
        results.append((plugin_id, ok, detail))
    return results