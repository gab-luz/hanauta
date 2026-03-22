#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.gamemode import LUTRIS_AUTO_SOURCE, STATE_FILE, ensure_visuals_restored_if_inactive, service_enabled, set_active, summary


POLL_INTERVAL_SECONDS = 5
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "game-mode"
MONITOR_STATE_FILE = STATE_DIR / "lutris-monitor.json"
RUNNER_MARKERS = (
    "lutris:rungame",
    "lutris-wrapper",
    "umu-run",
    "gamescope",
    "mangohud",
    "wine",
    "wine64",
    "retroarch",
    "dolphin-emu",
    "rpcs3",
    "pcsx2",
    "citra",
    "yuzu",
    "ryujinx",
)


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_runtime_state() -> dict:
    return _load_json(STATE_FILE)


def _write_runtime_state(payload: dict) -> None:
    _write_json(STATE_FILE, payload)


def _load_monitor_state() -> dict:
    return _load_json(MONITOR_STATE_FILE)


def _write_monitor_state(payload: dict) -> None:
    _write_json(MONITOR_STATE_FILE, payload)


def _list_processes() -> list[dict[str, object]]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,comm=,args="],
            capture_output=True,
            text=True,
            check=False,
            timeout=4.0,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    processes: list[dict[str, object]] = []
    for raw_line in result.stdout.splitlines():
        parts = raw_line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        processes.append(
            {
                "pid": pid,
                "ppid": ppid,
                "comm": parts[2],
                "args": parts[3],
            }
        )
    return processes


def _process_mentions_lutris(proc: dict[str, object]) -> bool:
    comm = str(proc.get("comm", "")).lower()
    args = str(proc.get("args", "")).lower()
    return "lutris" in comm or "lutris" in args


def _build_indexes(processes: list[dict[str, object]]) -> tuple[dict[int, dict[str, object]], dict[int, list[int]]]:
    by_pid = {int(proc["pid"]): proc for proc in processes}
    children: dict[int, list[int]] = {}
    for proc in processes:
        parent = int(proc["ppid"])
        children.setdefault(parent, []).append(int(proc["pid"]))
    return by_pid, children


def _has_lutris_ancestor(pid: int, by_pid: dict[int, dict[str, object]]) -> bool:
    visited: set[int] = set()
    current = pid
    while current and current not in visited:
        visited.add(current)
        proc = by_pid.get(current)
        if not proc:
            return False
        if _process_mentions_lutris(proc):
            return True
        current = int(proc.get("ppid", 0))
    return False


def detect_lutris_game() -> tuple[bool, str]:
    processes = _list_processes()
    if not processes:
        return False, ""
    by_pid, _ = _build_indexes(processes)
    sessions: list[str] = []
    for proc in processes:
        pid = int(proc["pid"])
        comm = str(proc.get("comm", ""))
        args = str(proc.get("args", ""))
        combined = f"{comm} {args}".lower()
        if not any(marker in combined for marker in RUNNER_MARKERS):
            continue
        if not _has_lutris_ancestor(pid, by_pid):
            continue
        pretty = args.strip() or comm.strip()
        if pretty and pretty not in sessions:
            sessions.append(pretty)
    if sessions:
        return True, sessions[0]
    return False, ""


def sync_runtime_flags(game_active: bool, detail: str) -> None:
    runtime_state = _load_runtime_state()
    runtime_state["lutris_game_active"] = bool(game_active)
    runtime_state["lutris_game_detail"] = detail
    if not game_active:
        runtime_state["manual_override_disable"] = False
    _write_runtime_state(runtime_state)


def main() -> int:
    while True:
        game_active, detail = detect_lutris_game()
        sync_runtime_flags(game_active, detail)
        current = summary()
        runtime_state = _load_runtime_state()
        auto_enabled = bool(runtime_state.get("activation_source") == LUTRIS_AUTO_SOURCE)
        manual_override = bool(runtime_state.get("manual_override_disable", False))

        if not service_enabled():
            if auto_enabled and bool(current.get("active", False)):
                set_active(False, source=LUTRIS_AUTO_SOURCE)
            _write_monitor_state(
                {
                    "games_active": game_active,
                    "detail": detail,
                    "manual_override_disable": manual_override,
                    "status": "service_disabled",
                }
            )
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if game_active:
            if not bool(current.get("active", False)) and not manual_override:
                set_active(True, source=LUTRIS_AUTO_SOURCE)
                current = summary()
            auto_enabled = bool(current.get("activation_source") == LUTRIS_AUTO_SOURCE)
        else:
            if auto_enabled and bool(current.get("active", False)):
                set_active(False, source=LUTRIS_AUTO_SOURCE)
                current = summary()
            auto_enabled = bool(current.get("activation_source") == LUTRIS_AUTO_SOURCE)
            ensure_visuals_restored_if_inactive()

        _write_monitor_state(
            {
                "games_active": game_active,
                "detail": detail,
                "manual_override_disable": manual_override,
                "active": bool(current.get("active", False)),
                "activation_source": str(current.get("activation_source", "")),
                "status": "watching",
            }
        )
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
