#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from typing import Any


IGNORED_CLASSES = {
    "CyberBar",
    "CyberDock",
    "HanautaHotkeys",
}
IGNORED_TITLE_PREFIXES = (
    "Hanauta Notification ",
)


def run_i3_msg(*args: str) -> str:
    result = subprocess.run(
        ["i3-msg", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def load_tree() -> dict[str, Any]:
    raw = run_i3_msg("-t", "get_tree")
    return json.loads(raw) if raw else {}


def iter_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    return list(node.get("nodes", [])) + list(node.get("floating_nodes", []))


def find_focused_workspace(node: dict[str, Any], workspace: dict[str, Any] | None = None) -> dict[str, Any] | None:
    current = workspace
    if node.get("type") == "workspace":
        current = node
    if node.get("focused"):
        if current is not None:
            return current
    for child in iter_children(node):
        found = find_focused_workspace(child, current)
        if found is not None:
            return found
    return None


def leaf_order(node: dict[str, Any]) -> list[dict[str, Any]]:
    children = iter_children(node)
    if not children:
        if node.get("window") is not None:
            return [node]
        return []

    by_id = {int(child.get("id", 0)): child for child in children}
    ordered: list[dict[str, Any]] = []
    seen: set[int] = set()
    for child_id in node.get("focus", []):
        child = by_id.get(int(child_id))
        if child is None:
            continue
        ordered.append(child)
        seen.add(int(child_id))
    for child in children:
        child_id = int(child.get("id", 0))
        if child_id not in seen:
            ordered.append(child)
    leaves: list[dict[str, Any]] = []
    for child in ordered:
        leaves.extend(leaf_order(child))
    return leaves


def should_ignore(node: dict[str, Any]) -> bool:
    props = node.get("window_properties") or {}
    wm_class = str(props.get("class", "") or "")
    title = str(node.get("name", "") or "")
    if wm_class in IGNORED_CLASSES:
        return True
    return any(title.startswith(prefix) for prefix in IGNORED_TITLE_PREFIXES)


def pick_next_window(workspace: dict[str, Any]) -> int | None:
    ordered = [node for node in leaf_order(workspace) if not should_ignore(node)]
    if len(ordered) < 2:
        return None
    focused = next((node for node in ordered if node.get("focused")), ordered[0])
    for node in ordered:
        if int(node.get("id", 0)) != int(focused.get("id", 0)):
            return int(node.get("id", 0))
    return None


def main() -> int:
    tree = load_tree()
    if not tree:
        return 1
    workspace = find_focused_workspace(tree)
    if workspace is None:
        return 1
    next_id = pick_next_window(workspace)
    if next_id is None:
        return 0
    subprocess.run(["i3-msg", f"[con_id={next_id}] focus"], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
