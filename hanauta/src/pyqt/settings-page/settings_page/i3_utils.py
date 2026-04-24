from __future__ import annotations

import json
import re
import subprocess


def fullscreen_window_active() -> bool:
    try:
        result = subprocess.run(
            ["i3-msg", "-t", "get_tree"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except Exception:
        return False
    if result.returncode != 0 or not result.stdout.strip():
        return False
    try:
        tree = json.loads(result.stdout)
    except Exception:
        return False

    def search(node: object) -> bool:
        if not isinstance(node, dict):
            return False
        if int(node.get("fullscreen_mode", 0) or 0) > 0 and node.get("window"):
            return True
        for key in ("nodes", "floating_nodes"):
            children = node.get(key, [])
            if not isinstance(children, list):
                continue
            for child in children:
                if search(child):
                    return True
        return False

    return search(tree)


def sanitize_output_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)

