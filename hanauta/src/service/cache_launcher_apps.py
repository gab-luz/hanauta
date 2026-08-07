#!/usr/bin/env python3
"""Standalone desktop entry scanner for hanauta-service.

Called by the C service to keep the launcher app cache fresh.
No Qt dependencies — pure stdlib + pathlib.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

STATE_DIR = Path(
    os.environ.get("HANAUTA_LAUNCHER_STATE_DIR")
    or os.environ.get("HANAUTA_SERVICE_STATE_DIR")
    or os.environ.get("HANAUTA_STATE_DIR")
    or Path.home() / ".local" / "state" / "hanauta",
)
CACHE_FILE = STATE_DIR / "launcher" / "apps_cache.json"

DESKTOP_DIRS = [
    Path.home() / ".config" / "i3" / "hanauta" / "config" / "applications",
    Path.home() / ".local" / "share" / "applications",
    Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
    Path("/var/lib/flatpak/exports/share/applications"),
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
]


@dataclass
class DesktopApp:
    name: str
    comment: str
    exec_line: str
    icon_name: str
    categories: set[str]
    desktop_id: str
    file_path: Path

    def to_cache_dict(self) -> dict:
        return {
            "name": self.name,
            "comment": self.comment,
            "exec_line": self.exec_line,
            "icon_name": self.icon_name,
            "categories": sorted(self.categories),
            "desktop_id": self.desktop_id,
            "file_path": str(self.file_path),
        }


def parse_desktop_file(path: Path) -> DesktopApp | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    in_entry = False
    data: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
            continue
        if not in_entry or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key not in data:
            data[key] = value.strip()

    if data.get("Type") != "Application":
        return None
    if data.get("NoDisplay", "").lower() == "true" or data.get("Hidden", "").lower() == "true":
        return None

    name = data.get("Name", "").strip()
    exec_line = data.get("Exec", "").strip()
    if not name or not exec_line:
        return None

    categories = {item for item in data.get("Categories", "").split(";") if item}
    return DesktopApp(
        name=name,
        comment=data.get("Comment", "").strip(),
        exec_line=exec_line,
        icon_name=data.get("Icon", "").strip(),
        categories=categories,
        desktop_id=path.name,
        file_path=path,
    )


def scan_desktop_apps() -> list[DesktopApp]:
    apps: list[DesktopApp] = []
    seen: set[str] = set()
    for base_dir in DESKTOP_DIRS:
        if not base_dir.exists():
            continue
        for path in sorted(base_dir.rglob("*.desktop")):
            app = parse_desktop_file(path)
            if app is None:
                continue
            dedupe_key = app.desktop_id.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            apps.append(app)
    apps.sort(key=lambda item: item.name.lower())
    return apps


def save_cached_desktop_apps(apps: list[DesktopApp]) -> None:
    try:
        cache_dir = CACHE_FILE.parent
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(cache_dir), 0o755)
        payload = {"apps": [app.to_cache_dict() for app in apps]}
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(cache_dir),
                prefix="apps_cache-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            os.replace(str(temp_path), str(CACHE_FILE))
            os.chmod(str(CACHE_FILE), 0o644)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
    except Exception:
        pass


def main() -> int:
    apps = scan_desktop_apps()
    save_cached_desktop_apps(apps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
