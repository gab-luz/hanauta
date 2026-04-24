from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path


def recursive_wallpaper_candidates(folder: Path, image_suffixes: set[str]) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in image_suffixes
    )


def file_sha1(path: Path) -> str | None:
    digest = hashlib.sha1()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def load_json_file(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def nested_dict_value(payload: dict, *keys: str) -> object | None:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def expand_wallpaper_dir(path_value: object) -> Path | None:
    if not isinstance(path_value, str):
        return None
    text = path_value.strip()
    if not text:
        return None
    return Path(os.path.expandvars(text)).expanduser()


def caelestia_wallpaper_dirs(cache_dir: Path) -> list[Path]:
    shell_config = Path.home() / ".config" / "caelestia" / "shell.json"
    config = load_json_file(shell_config)
    configured_dir = expand_wallpaper_dir(
        nested_dict_value(config, "paths", "wallpaperDir")
    )
    env_dir = expand_wallpaper_dir(os.environ.get("CAELESTIA_WALLPAPERS_DIR"))
    candidates = [
        configured_dir,
        env_dir,
        Path.home() / "Wallpaper-Bank" / "wallpapers",
        Path.home() / "Wallpaper-Bank",
        Path.home() / "Pictures" / "Wallpapers" / "showcase",
        Path.home() / "Pictures" / "Wallpapers",
        cache_dir / "assets",
    ]
    results: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = str(candidate.expanduser())
        if key in seen:
            continue
        seen.add(key)
        results.append(candidate)
    return results


def end4_wallpaper_dirs(cache_dir: Path) -> list[Path]:
    shell_config = Path.home() / ".config" / "illogical-impulse" / "config.json"
    config = load_json_file(shell_config)
    configured_file = expand_wallpaper_dir(
        nested_dict_value(config, "background", "wallpaperPath")
    )
    configured_dir = (
        configured_file.parent
        if configured_file and configured_file.suffix
        else configured_file
    )
    candidates = [
        configured_dir,
        Path.home() / "Wallpaper-Bank" / "wallpapers",
        Path.home() / "Wallpaper-Bank",
        Path.home() / "Pictures" / "Wallpapers" / "showcase",
        Path.home() / "Pictures" / "Wallpapers",
        cache_dir / "dots" / ".config" / "quickshell" / "ii" / "assets" / "images",
    ]
    results: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = str(candidate.expanduser())
        if key in seen:
            continue
        seen.add(key)
        results.append(candidate)
    return results


def wallpaper_source_directories(
    source_key: str, cache_dir: Path, presets: dict[str, dict[str, object]]
) -> list[Path]:
    if source_key == "caelestia":
        return caelestia_wallpaper_dirs(cache_dir)
    if source_key == "end4":
        return end4_wallpaper_dirs(cache_dir)

    preset = presets.get(source_key, {})
    subdirs = preset.get("subdirs", [])
    if not isinstance(subdirs, list):
        return []
    return [cache_dir / str(subdir) for subdir in subdirs]


def extract_wallpaper_source_archives(
    source_key: str, cache_dir: Path, presets: dict[str, dict[str, object]]
) -> list[Path]:
    preset = presets.get(source_key, {})
    archives = preset.get("archives", [])
    if not isinstance(archives, list):
        return []
    extracted_dirs: list[Path] = []
    for archive_name in archives:
        archive_path = cache_dir / str(archive_name)
        if not archive_path.exists() or not archive_path.is_file():
            continue
        target_dir = cache_dir / f"{archive_path.stem}-extracted"
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            target_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path) as bundle:
                bundle.extractall(target_dir)
            extracted_dirs.append(target_dir)
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            continue
    return extracted_dirs


def sync_wallpaper_source_preset(
    source_key: str,
    *,
    presets: dict[str, dict[str, object]],
    cache_root: Path,
    community_root: Path,
    image_suffixes: set[str],
) -> tuple[bool, str, Path | None]:
    preset = presets.get(source_key)
    if not preset:
        return False, "Wallpaper source preset is missing.", None

    repo_url = str(preset.get("repo", "")).strip()
    if not repo_url:
        return False, "Wallpaper source repository is missing.", None

    cache_dir = cache_root / source_key
    target_dir = community_root / source_key
    cache_root.mkdir(parents=True, exist_ok=True)
    community_root.mkdir(parents=True, exist_ok=True)

    try:
        if (cache_dir / ".git").exists():
            fetch = subprocess.run(
                ["git", "-C", str(cache_dir), "fetch", "--depth", "1", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
            if fetch.returncode != 0:
                message = (
                    fetch.stderr
                    or fetch.stdout
                    or "Failed to refresh wallpaper source."
                ).strip()
                return False, message, None
            reset = subprocess.run(
                ["git", "-C", str(cache_dir), "reset", "--hard", "FETCH_HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if reset.returncode != 0:
                message = (
                    reset.stderr or reset.stdout or "Failed to update wallpaper source."
                ).strip()
                return False, message, None
        else:
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            clone = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(cache_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            if clone.returncode != 0:
                message = (
                    clone.stderr or clone.stdout or "Failed to clone wallpaper source."
                ).strip()
                return False, message, None
    except Exception as exc:
        return False, str(exc), None

    source_dirs = wallpaper_source_directories(source_key, cache_dir, presets)
    source_dirs.extend(extract_wallpaper_source_archives(source_key, cache_dir, presets))
    candidates: list[Path] = []
    source_labels: list[str] = []
    for source_dir in source_dirs:
        if not source_dir.exists():
            continue
        discovered = recursive_wallpaper_candidates(source_dir, image_suffixes)
        if not discovered:
            continue
        candidates.extend(discovered)
        source_labels.append(str(source_dir))
    if not candidates:
        candidates = [
            path
            for path in cache_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in image_suffixes
        ]
    if not candidates:
        label = str(preset.get("label", "This wallpaper source"))
        return (
            False,
            f"{label} does not currently expose wallpaper images in the expected paths.",
            None,
        )

    shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    seen_hashes: set[str] = set()
    for source in sorted(candidates):
        digest = file_sha1(source)
        if digest and digest in seen_hashes:
            continue
        if digest:
            seen_hashes.add(digest)
        target = target_dir / f"{copied + 1:03d}-{source.name}"
        try:
            shutil.copy2(source, target)
            copied += 1
        except OSError:
            continue

    if copied == 0:
        label = str(preset.get("label", "this source"))
        return False, f"Hanauta could not copy any images from {label}.", None

    source_summary = ", ".join(source_labels[:2])
    if len(source_labels) > 2:
        source_summary += f", +{len(source_labels) - 2} more"
    label = str(preset.get("label", "this source"))
    if source_summary:
        return (
            True,
            f"Synced {copied} image(s) from {label} using {source_summary}.",
            target_dir,
        )
    return True, f"Synced {copied} image(s) from {label}.", target_dir

