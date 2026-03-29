#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command

SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
PROMPT_SCRIPT = HERE / "virtualization_prompt.py"

POLL_RETRY_SECONDS = 2.0

IDE_KEYS = ("vscode", "vscodium", "android_studio", "jetbrains")


def _load_settings() -> dict[str, Any]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _save_settings(payload: dict[str, Any]) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _service_settings(payload: dict[str, Any]) -> dict[str, Any]:
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return {}
    current = services.get("virtualization", {})
    if not isinstance(current, dict):
        return {}
    defaults = {
        "enabled": False,
        "virtualbox_manager_to_next_workspace": True,
        "virtualbox_guest_fullscreen": False,
        "virtualbox_guest_keep_current_workspace": True,
        "emulator_prompt_once_per_ide": True,
        "emulator_move_target": "next_on_output",
        "ide_actions": {key: "ask" for key in IDE_KEYS},
    }
    merged = dict(defaults)
    merged.update(current)
    actions = merged.get("ide_actions", {})
    if not isinstance(actions, dict):
        actions = {}
    merged_actions: dict[str, str] = {}
    for key in IDE_KEYS:
        value = str(actions.get(key, "ask")).strip().lower()
        if value not in {"ask", "split", "move_workspace"}:
            value = "ask"
        merged_actions[key] = value
    merged["ide_actions"] = merged_actions
    target = str(merged.get("emulator_move_target", "next_on_output")).strip().lower()
    merged["emulator_move_target"] = target if target in {"next", "next_on_output"} else "next_on_output"
    return merged


def _run_i3_json(*args: str) -> Any:
    try:
        result = subprocess.run(
            ["i3-msg", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=4.0,
        )
    except Exception:
        return None
    text = (result.stdout or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _run_i3_cmd(command: str) -> None:
    try:
        subprocess.run(["i3-msg", command], check=False, capture_output=True, text=True, timeout=4.0)
    except Exception:
        return


def _iter_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for key in ("nodes", "floating_nodes"):
        value = node.get(key, [])
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    children.append(item)
    return children


def _flatten_windows(tree: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], workspace: str) -> None:
        current_workspace = workspace
        if node.get("type") == "workspace":
            current_workspace = str(node.get("name", "")).strip()
        window_id = node.get("window")
        if window_id is not None and node.get("id") is not None:
            props = node.get("window_properties", {})
            if not isinstance(props, dict):
                props = {}
            rows.append(
                {
                    "id": int(node.get("id")),
                    "workspace": current_workspace,
                    "focused": bool(node.get("focused", False)),
                    "class": str(props.get("class", "")),
                    "instance": str(props.get("instance", "")),
                    "title": str(node.get("name", "")),
                }
            )
        for child in _iter_children(node):
            walk(child, current_workspace)

    walk(tree, "")
    return rows


def _detect_ide_key(class_name: str, title: str) -> str | None:
    cls = class_name.strip().lower()
    ttl = title.strip().lower()
    if "vscodium" in cls or cls == "codium":
        return "vscodium"
    if cls in {"code", "code-oss"} or "visual studio code" in ttl:
        return "vscode"
    if "android studio" in ttl or "jetbrains-studio" in cls or cls in {"studio", "android-studio"}:
        return "android_studio"
    jetbrains_markers = (
        "jetbrains",
        "idea",
        "pycharm",
        "webstorm",
        "goland",
        "clion",
        "rider",
        "phpstorm",
    )
    if any(marker in cls for marker in jetbrains_markers):
        return "jetbrains"
    return None


def _is_emulator_window(class_name: str, title: str) -> bool:
    cls = class_name.strip().lower()
    ttl = title.strip().lower()
    if "android emulator" in ttl:
        return True
    if cls in {"emulator", "android-emulator", "qemu-system-x86_64", "qemu-system"}:
        return True
    if "emulator" in cls and ("android" in cls or "qemu" in cls):
        return True
    if "qemu" in cls and "system" in cls:
        return True
    return False


def _is_virtualbox_manager(class_name: str, title: str) -> bool:
    cls = class_name.strip().lower()
    ttl = title.strip().lower()
    return ("virtualbox" in cls and "manager" in cls) or ("oracle vm virtualbox manager" in ttl)


def _is_virtualbox_machine(class_name: str, title: str) -> bool:
    cls = class_name.strip().lower()
    ttl = title.strip().lower()
    return ("virtualbox" in cls and "machine" in cls) or (" - oracle vm virtualbox" in ttl)


def _focused_workspace_name() -> str:
    workspaces = _run_i3_json("-t", "get_workspaces")
    if not isinstance(workspaces, list):
        return ""
    for item in workspaces:
        if not isinstance(item, dict):
            continue
        if bool(item.get("focused", False)):
            return str(item.get("name", "")).strip()
    return ""


def _focused_window_id() -> int | None:
    tree = _run_i3_json("-t", "get_tree")
    if not isinstance(tree, dict):
        return None
    for row in _flatten_windows(tree):
        if bool(row.get("focused", False)):
            try:
                return int(row.get("id"))
            except Exception:
                return None
    return None


def _find_related_ide(tree: dict[str, Any], workspace: str) -> tuple[str | None, int | None, str]:
    windows = _flatten_windows(tree)
    for row in windows:
        if bool(row.get("focused", False)):
            key = _detect_ide_key(str(row.get("class", "")), str(row.get("title", "")))
            if key:
                return key, int(row.get("id", 0) or 0), str(row.get("title", ""))
    for row in windows:
        if str(row.get("workspace", "")).strip() != workspace:
            continue
        key = _detect_ide_key(str(row.get("class", "")), str(row.get("title", "")))
        if key:
            return key, int(row.get("id", 0) or 0), str(row.get("title", ""))
    for row in windows:
        key = _detect_ide_key(str(row.get("class", "")), str(row.get("title", "")))
        if key:
            return key, int(row.get("id", 0) or 0), str(row.get("title", ""))
    return None, None, ""


def _move_virtualbox_managers_to_next_workspace() -> None:
    tree = _run_i3_json("-t", "get_tree")
    if not isinstance(tree, dict):
        return
    for row in _flatten_windows(tree):
        class_name = str(row.get("class", ""))
        title = str(row.get("title", ""))
        if not _is_virtualbox_manager(class_name, title):
            continue
        con_id = int(row.get("id", 0) or 0)
        if con_id <= 0:
            continue
        _run_i3_cmd(f"[con_id={con_id}] move container to workspace next")


def _apply_emulator_layout(action: str, emulator_con_id: int, ide_con_id: int | None, move_target: str) -> None:
    focused_before = _focused_window_id()
    if action == "move_workspace":
        target = "next_on_output" if move_target == "next_on_output" else "next"
        _run_i3_cmd(f"[con_id={emulator_con_id}] move container to workspace {target}")
    elif action == "split":
        if ide_con_id and ide_con_id > 0:
            _run_i3_cmd(f"[con_id={ide_con_id}] focus")
            _run_i3_cmd("split h")
        _run_i3_cmd(f"[con_id={emulator_con_id}] floating disable")
        _run_i3_cmd(f"[con_id={emulator_con_id}] focus")
    if focused_before and focused_before > 0:
        _run_i3_cmd(f"[con_id={focused_before}] focus")


def _prompt_emulator_layout(ide_key: str, ide_title: str, emulator_title: str) -> str | None:
    command = entry_command(
        PROMPT_SCRIPT,
        "--ide-key",
        ide_key,
        "--ide",
        ide_title or ide_key,
        "--emulator",
        emulator_title or "Android Emulator",
    )
    if not command:
        return None
    decision_file = Path(tempfile.gettempdir()) / f"hanauta-virtualization-{ide_key}-{int(time.time() * 1000)}.json"
    command.extend(["--decision-file", str(decision_file)])
    try:
        subprocess.run(command, check=False, timeout=180)
    except Exception:
        return None
    if not decision_file.exists():
        return None
    try:
        payload = json.loads(decision_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    finally:
        decision_file.unlink(missing_ok=True)
    if not isinstance(payload, dict):
        return None
    action = str(payload.get("action", "")).strip().lower()
    if action not in {"split", "move_workspace"}:
        return None
    return action


def _persist_ide_action(ide_key: str, action: str) -> None:
    settings = _load_settings()
    services = settings.setdefault("services", {})
    if not isinstance(services, dict):
        return
    virtualization = services.setdefault("virtualization", {})
    if not isinstance(virtualization, dict):
        return
    actions = virtualization.setdefault("ide_actions", {})
    if not isinstance(actions, dict):
        actions = {}
        virtualization["ide_actions"] = actions
    actions[ide_key] = action
    _save_settings(settings)


def _handle_window_event(event: dict[str, Any], processed_emulators: set[int]) -> None:
    settings = _load_settings()
    service = _service_settings(settings)
    if not bool(service.get("enabled", False)):
        return

    container = event.get("container", {})
    if not isinstance(container, dict):
        return
    con_id = int(container.get("id", 0) or 0)
    if con_id <= 0:
        return

    props = container.get("window_properties", {})
    if not isinstance(props, dict):
        props = {}
    class_name = str(props.get("class", ""))
    title = str(container.get("name", ""))
    workspace = _focused_workspace_name()

    if bool(service.get("virtualbox_manager_to_next_workspace", True)) and _is_virtualbox_manager(class_name, title):
        _run_i3_cmd(f"[con_id={con_id}] move container to workspace next")
        return

    if _is_virtualbox_machine(class_name, title):
        if bool(service.get("virtualbox_guest_keep_current_workspace", True)) and workspace:
            _run_i3_cmd(f"[con_id={con_id}] move container to workspace {workspace}")
        if bool(service.get("virtualbox_manager_to_next_workspace", True)):
            _move_virtualbox_managers_to_next_workspace()
        if bool(service.get("virtualbox_guest_fullscreen", False)):
            _run_i3_cmd(f"[con_id={con_id}] fullscreen enable")
        return

    if not _is_emulator_window(class_name, title):
        return
    if con_id in processed_emulators:
        return
    processed_emulators.add(con_id)

    tree = _run_i3_json("-t", "get_tree")
    if not isinstance(tree, dict):
        return
    ide_key, ide_con_id, ide_title = _find_related_ide(tree, workspace)
    if ide_key is None:
        return

    actions = service.get("ide_actions", {})
    if not isinstance(actions, dict):
        actions = {}
    action = str(actions.get(ide_key, "ask")).strip().lower()
    prompt_once = bool(service.get("emulator_prompt_once_per_ide", True))

    if action == "ask":
        resolved = _prompt_emulator_layout(ide_key, ide_title, title)
        if resolved is None:
            return
        action = resolved
        if prompt_once:
            _persist_ide_action(ide_key, action)

    if action not in {"split", "move_workspace"}:
        return
    _apply_emulator_layout(
        action,
        emulator_con_id=con_id,
        ide_con_id=ide_con_id,
        move_target=str(service.get("emulator_move_target", "next_on_output")),
    )


def main() -> int:
    processed_emulators: set[int] = set()
    while True:
        try:
            sub = subprocess.Popen(
                ["i3-msg", "-t", "subscribe", "-m", '["window"]'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception:
            time.sleep(POLL_RETRY_SECONDS)
            continue

        if sub.stdout is None:
            time.sleep(POLL_RETRY_SECONDS)
            continue

        try:
            for raw_line in sub.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                if payload.get("change") in {"new", "title", "focus"}:
                    _handle_window_event(payload, processed_emulators)
        except Exception:
            pass
        finally:
            try:
                sub.kill()
            except Exception:
                pass
        time.sleep(POLL_RETRY_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
