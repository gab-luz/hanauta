#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
STEAM_ICON = ASSETS_DIR / "steam-logo.svg"
LUTRIS_ICON = ASSETS_DIR / "lutris-logo.svg"

LUTRIS_DB = Path.home() / ".local" / "share" / "lutris" / "pga.db"
LUTRIS_COVERART_DIRS = [
    Path.home() / ".local" / "share" / "lutris" / "coverart",
    Path.home() / ".cache" / "lutris" / "coverart",
]

STEAM_ROOT_CANDIDATES = [
    Path.home() / ".steam",
    Path.home() / ".local" / "share" / "Steam",
    Path.home()
    / ".var"
    / "app"
    / "com.valvesoftware.Steam"
    / ".local"
    / "share"
    / "Steam",
    Path.home() / "snap" / "steam" / "common" / ".local" / "share" / "Steam",
]


def _format_playtime_hours(hours: float) -> str:
    if hours <= 0:
        return "0m total"
    whole_hours = int(hours)
    minutes = int(round((hours - whole_hours) * 60))
    if whole_hours <= 0:
        return f"{minutes}m total"
    if minutes <= 0:
        return f"{whole_hours}h total"
    return f"{whole_hours}h {minutes}m total"


@dataclass(frozen=True)
class Slide:
    title: str
    stats: list[str]
    logo: str
    platform: str
    accent: str
    source: str
    playtime_hours: float = 0.0
    cover: str | None = None
    lutris_slug: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "title": self.title,
            "stats": self.stats,
            "logo": self.logo,
            "platform": self.platform,
            "accent": self.accent,
            "source": self.source,
            "playtime_hours": self.playtime_hours,
        }
        if self.cover:
            payload["cover"] = self.cover
        if self.lutris_slug:
            payload["lutris_slug"] = self.lutris_slug
        return payload


def _lutris_cover(slug: str) -> str | None:
    if not slug:
        return None
    for root in LUTRIS_COVERART_DIRS:
        for ext in ("jpg", "png", "jpeg", "webp"):
            candidate = root / f"{slug}.{ext}"
            if candidate.is_file():
                return str(candidate)
    return None


def _load_lutris(limit: int) -> list[Slide]:
    if not LUTRIS_DB.exists():
        return []
    rows: list[tuple] = []
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(str(LUTRIS_DB), timeout=0.5)
        cursor = connection.cursor()
        rows = list(
            cursor.execute(
                """
                SELECT name, slug, playtime, lastplayed, runner, platform
                FROM games
                WHERE installed = 1
                ORDER BY lastplayed DESC, playtime DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
        )
    except Exception:
        rows = []
    finally:
        try:
            if connection is not None:
                connection.close()
        except Exception:
            pass

    slides: list[Slide] = []
    for name, slug, playtime, _lastplayed, runner, platform in rows:
        hours = float(playtime or 0.0)
        slug_text = str(slug or "")
        platform_label = f"Lutris • {runner or platform or 'Library'}"
        slides.append(
            Slide(
                title=str(name or "Lutris game"),
                stats=[_format_playtime_hours(hours), str(platform or runner or "Installed")],
                logo=str(LUTRIS_ICON),
                platform=platform_label,
                accent="primary",
                source="lutris",
                playtime_hours=hours,
                cover=_lutris_cover(slug_text),
                lutris_slug=slug_text or None,
            )
        )
    return slides


def _steam_localconfig_paths(max_users: int = 4) -> list[Path]:
    for root in STEAM_ROOT_CANDIDATES:
        userdata = root / "userdata"
        if not userdata.exists():
            continue
        results: list[Path] = []
        try:
            count = 0
            for entry in userdata.iterdir():
                if count >= max_users:
                    break
                if not entry.is_dir():
                    continue
                candidate = entry / "config" / "localconfig.vdf"
                if candidate.exists():
                    results.append(candidate)
                    count += 1
        except Exception:
            pass
        if results:
            return results
    return []


def _load_steam(limit: int) -> list[Slide]:
    app_pattern = re.compile(
        r'"(\d+)"\s*\{[^{}]*?"name"\s*"([^"]+)"[^{}]*?"Playtime"\s*"(\d+)"',
        re.DOTALL,
    )
    slides: list[Slide] = []
    for config_path in _steam_localconfig_paths():
        try:
            raw = config_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for appid, name, minutes_text in app_pattern.findall(raw):
            minutes = int(minutes_text or "0")
            if minutes <= 0:
                continue
            hours = minutes / 60.0
            slides.append(
                Slide(
                    title=str(name or "Steam game"),
                    stats=[_format_playtime_hours(hours), f"App {appid}"],
                    logo=str(STEAM_ICON),
                    platform="Steam library",
                    accent="secondary",
                    source="steam",
                    playtime_hours=hours,
                )
            )
        if slides:
            break
    slides.sort(key=lambda item: item.playtime_hours, reverse=True)
    return slides[: max(1, int(limit))]


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _any_game_running() -> bool:
    needles = (
        "lutris-wrapper",
        "lutris-wrapper.sh",
        "steam_app_",
        "pressure-vessel",
        "gamescope",
    )
    proc = Path("/proc")
    try:
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            cmdline_path = entry / "cmdline"
            try:
                raw = cmdline_path.read_bytes()
            except Exception:
                continue
            if not raw:
                continue
            text = raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").lower()
            if any(needle in text for needle in needles):
                return True
    except Exception:
        return False
    return False


def main() -> int:
    state_dir = os.environ.get("HANAUTA_STATE_DIR") or os.environ.get("HANAUTA_SERVICE_STATE_DIR")
    if not state_dir:
        return 1
    cache_path = Path(state_dir) / "games.json"

    slides: list[Slide] = []
    slides.extend(_load_lutris(2))
    slides.extend(_load_steam(2))
    if not slides:
        slides = [
            Slide(
                title="Welcome back",
                stats=["No launcher telemetry yet"],
                logo=str(STEAM_ICON),
                platform="Game library",
                accent="primary",
                source="library",
            )
        ]

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "any_playing": _any_game_running(),
        "slides": [slide.to_dict() for slide in slides[:4]],
    }
    _write_json_atomic(cache_path, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

