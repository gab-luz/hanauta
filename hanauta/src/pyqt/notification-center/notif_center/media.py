from __future__ import annotations

from notif_center.utils import run_cmd, run_script, run_script_bg


def poll_media_metadata() -> dict:
    title = run_script("mpris.sh", "title") or "No music"
    artist = run_script("mpris.sh", "artist") or "No artist"
    status = run_script("mpris.sh", "status") or "Stopped"
    player = run_script("mpris.sh", "player")
    art = run_script("mpris.sh", "coverloc")
    media_url = ""
    if player:
        media_url = run_cmd(
            ["playerctl", f"--player={player}", "metadata", "--format", "{{xesam:url}}"]
        )
    return {
        "title": title,
        "artist": artist,
        "status": status,
        "player": player,
        "art": art,
        "media_url": media_url,
    }


def poll_media_progress(player: str) -> tuple[int, int, str, str]:
    status_raw = run_cmd(["playerctl", f"--player={player}", "status"]) or "Stopped"
    position_raw = run_cmd(["playerctl", f"--player={player}", "position"])
    length_raw = run_cmd(["playerctl", f"--player={player}", "metadata", "--format", "{{mpris:length}}"])
    position_ms = 0
    duration_ms = 0
    try:
        position_ms = max(0, int(float(position_raw) * 1000)) if position_raw else 0
    except Exception:
        pass
    try:
        duration_ms = max(0, int(int(length_raw) / 1000)) if length_raw else 0
    except Exception:
        pass
    return position_ms, duration_ms, status_raw, player


def is_browser_player(player: str) -> bool:
    lowered = player.lower()
    browser_names = ("firefox", "librewolf", "chromium", "brave", "chrome", "vivaldi")
    return any(name in lowered for name in browser_names)


def duration_ms_from_media_url(url: str, cache: dict[str, int] | None = None) -> int | None:
    url = url.strip()
    if not url:
        return None
    if cache is not None and url in cache:
        return cache[url]
    duration_raw = run_cmd(
        ["yt-dlp", "--no-playlist", "--skip-download", "--print", "duration", "--no-warnings", url],
        timeout=4.0,
    )
    try:
        duration_ms = max(0, int(float(duration_raw.strip()) * 1000))
    except Exception:
        return None
    if cache is not None:
        cache[url] = duration_ms
    return duration_ms


def trigger_media_action(action: str) -> None:
    run_script_bg("mpris.sh", action)
