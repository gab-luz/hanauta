#!/usr/bin/env python3
import fnmatch
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None

EWW_CONFIG_DIR = Path(os.environ.get("EWW_CONFIG_DIR", "")).expanduser()
# EWW sets {EWW_CONFIG_DIR} in yuck commands; but when running manually, fallback:
if not EWW_CONFIG_DIR or not EWW_CONFIG_DIR.exists():
    # infer from this file location: <eww>/scripts/eww-dock.py
    EWW_CONFIG_DIR = Path(__file__).resolve().parents[1]

CONFIG_PATH = EWW_CONFIG_DIR / "dock" / "dock.toml"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "eww-dock"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ICON_CACHE_PATH = CACHE_DIR / "icon_cache.json"
STATE_PATH = CACHE_DIR / "state.json"

DESKTOP_DIRS = [
    Path.home() / ".local/share/applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
]

ICON_DIRS = [
    Path.home() / ".local/share/icons",
    Path("/usr/local/share/icons"),
    Path("/usr/share/icons"),
    Path("/usr/share/pixmaps"),
]

FALLBACK_ICON_NAMES = ["application-x-executable", "applications-other", "application-default-icon"]

@dataclass
class DesktopEntry:
    desktop_id: str
    name: str
    icon: str
    startup_wm_class: str

def sh(cmd: List[str], check: bool = True, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text)

def load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    if tomllib is None:
        raise RuntimeError("Python is missing tomllib (need Python 3.11+ on Debian 13 it should exist).")
    return tomllib.loads(path.read_text(encoding="utf-8"))

def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def i3_tree() -> dict:
    p = sh(["i3-msg", "-t", "get_tree"], check=True)
    return json.loads(p.stdout)

def walk_nodes(node: dict):
    yield node
    for k in ("nodes", "floating_nodes"):
        for ch in node.get(k, []) or []:
            yield from walk_nodes(ch)

def norm(s: str) -> str:
    return (s or "").strip().lower()

def get_windows_by_class() -> Tuple[Dict[str, List[int]], Optional[str]]:
    tree = i3_tree()
    windows: Dict[str, List[int]] = {}
    focused_class: Optional[str] = None
    for n in walk_nodes(tree):
        if n.get("window") is None:
            continue
        wp = n.get("window_properties") or {}
        cls = wp.get("class") or wp.get("instance") or ""
        cls_n = norm(cls)
        if not cls_n:
            continue
        windows.setdefault(cls_n, []).append(n["id"])  # i3 container id for focusing
        if n.get("focused"):
            focused_class = cls_n
    return windows, focused_class

def get_workspaces_by_con_id() -> Dict[int, str]:
    tree = i3_tree()
    mapping: Dict[int, str] = {}

    def walk(node: dict, workspace_name: str = ""):
        current_workspace = workspace_name
        if node.get("type") == "workspace":
            current_workspace = node.get("name") or workspace_name
        if node.get("window") is not None and node.get("id") is not None and current_workspace:
            mapping[int(node["id"])] = current_workspace
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []) or []:
                walk(child, current_workspace)

    walk(tree)
    return mapping

def scan_desktop_entries() -> Tuple[Dict[str, DesktopEntry], Dict[str, str]]:
    """Returns (desktop_id->entry, wmclass->desktop_id best match)"""
    entries: Dict[str, DesktopEntry] = {}
    wm_map: Dict[str, str] = {}

    for d in DESKTOP_DIRS:
        if not d.exists():
            continue
        for f in d.glob("*.desktop"):
            desktop_id = f.name
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # super-light parser (avoid configparser edge-cases)
            name = ""
            icon = ""
            startup_wm = ""
            in_entry = False
            for line in txt.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line == "[Desktop Entry]":
                    in_entry = True
                    continue
                if line.startswith("[") and line.endswith("]") and line != "[Desktop Entry]":
                    in_entry = False
                    continue
                if not in_entry or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k == "Name" and not name:
                    name = v
                elif k == "Icon" and not icon:
                    icon = v
                elif k == "StartupWMClass" and not startup_wm:
                    startup_wm = v

            if not name:
                name = desktop_id.replace(".desktop", "")
            if not startup_wm:
                startup_wm = desktop_id.replace(".desktop", "")
            e = DesktopEntry(desktop_id=desktop_id, name=name, icon=icon, startup_wm_class=startup_wm)
            entries[desktop_id] = e

            # map by startup wm class and by desktop id base
            wm_map[norm(startup_wm)] = desktop_id
            wm_map[norm(desktop_id.replace(".desktop", ""))] = desktop_id

    return entries, wm_map

def load_icon_cache() -> Dict[str, str]:
    return read_json(ICON_CACHE_PATH, {})

def save_icon_cache(cache: Dict[str, str]):
    # keep it from growing forever
    if len(cache) > 4000:
        # drop oldest-ish by arbitrary order
        cache = dict(list(cache.items())[-2000:])
    write_json(ICON_CACHE_PATH, cache)

def resolve_icon_path(icon_name: str, icon_cache: Dict[str, str]) -> str:
    icon_name = (icon_name or "").strip()
    if not icon_name:
        icon_name = FALLBACK_ICON_NAMES[0]

    if icon_name in icon_cache and Path(icon_cache[icon_name]).exists():
        return icon_cache[icon_name]

    # absolute / explicit path
    p = Path(icon_name)
    if p.is_absolute() and p.exists():
        icon_cache[icon_name] = str(p)
        return str(p)

    # try with extensions in common icon roots
    exts = [".svg", ".png", ".xpm"]
    candidates: List[Path] = []

    def add_if_exists(pp: Path):
        if pp.exists():
            candidates.append(pp)

    # /usr/share/pixmaps often contains <name>.png
    for base in ICON_DIRS:
        if not base.exists():
            continue

        # direct file in pixmaps/icons root
        for ext in exts:
            add_if_exists(base / f"{icon_name}{ext}")

        # themed search (hicolor/adwaita/papirus/etc) - limited depth for speed
        if (base / "hicolor").exists() or (base / "Adwaita").exists():
            for theme in ("hicolor", "Adwaita", "Papirus", "Papirus-Dark"):
                t = base / theme
                if not t.exists():
                    continue
                # prefer scalable first
                for ext in exts:
                    add_if_exists(t / "scalable" / "apps" / f"{icon_name}{ext}")
                # then common sizes
                for size in ("256x256", "128x128", "64x64", "48x48", "32x32", "24x24", "16x16"):
                    for ext in exts:
                        add_if_exists(t / size / "apps" / f"{icon_name}{ext}")

    if not candidates:
        # fallback icons
        for fb in FALLBACK_ICON_NAMES:
            if fb == icon_name:
                continue
            path = resolve_icon_path(fb, icon_cache) if fb not in icon_cache else icon_cache[fb]
            if path and Path(path).exists():
                icon_cache[icon_name] = path
                return path
        icon_cache[icon_name] = ""
        return ""

    # pick best: svg > largest png
    def score(pp: Path) -> Tuple[int, int]:
        ext_score = 2 if pp.suffix == ".svg" else (1 if pp.suffix == ".png" else 0)
        size_score = 0
        parts = pp.parts
        for part in parts:
            if "x" in part and part.replace("x", "").isdigit():
                try:
                    size_score = int(part.split("x")[0])
                except Exception:
                    pass
        return (ext_score, size_score)

    best = sorted(candidates, key=score, reverse=True)[0]
    icon_cache[icon_name] = str(best)
    return str(best)

def is_blacklisted(value: str, patterns: List[str]) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    for pat in patterns:
        if fnmatch.fnmatch(norm(v), norm(pat)):
            return True
    return False

def i3_focus_con_id(con_id: int):
    sh(["i3-msg", f'[con_id="{con_id}"]', "focus"], check=False)

def i3_focus_con_id_on_workspace(con_id: int):
    ws_map = get_workspaces_by_con_id()
    workspace = ws_map.get(int(con_id))
    if workspace:
        sh(["i3-msg", "workspace", workspace], check=False)
    sh(["i3-msg", f'[con_id="{con_id}"]', "focus"], check=False)

def launch_desktop(desktop_id: str):
    # gtk-launch accepts desktop id; try both with/without .desktop
    did = desktop_id
    base = desktop_id.replace(".desktop", "")
    p1 = subprocess.run(["gtk-launch", did], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if p1.returncode != 0:
        subprocess.Popen(["gtk-launch", base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_next_focus_id(key: str, ids: List[int], focused: Optional[int]) -> int:
    st = read_json(STATE_PATH, {})
    last = st.get("last_index", {}).get(key, -1)
    if focused in ids:
        idx = ids.index(focused)
    else:
        idx = last if isinstance(last, int) and 0 <= last < len(ids) else -1
    nxt = (idx + 1) % len(ids)
    st.setdefault("last_index", {})[key] = nxt
    write_json(STATE_PATH, st)
    return ids[nxt]

def get_prev_focus_id(key: str, ids: List[int], focused: Optional[int]) -> int:
    st = read_json(STATE_PATH, {})
    last = st.get("last_index", {}).get(key, 0)
    if focused in ids:
        idx = ids.index(focused)
    else:
        idx = last if isinstance(last, int) and 0 <= last < len(ids) else 0
    prv = (idx - 1) % len(ids)
    st.setdefault("last_index", {})[key] = prv
    write_json(STATE_PATH, st)
    return ids[prv]

def get_focused_con_id() -> Optional[int]:
    tree = i3_tree()
    for n in walk_nodes(tree):
        if n.get("focused") and n.get("id"):
            return n["id"]
    return None

def build_items() -> List[dict]:
    cfg = load_toml(CONFIG_PATH) if CONFIG_PATH.exists() else {}
    pinned: List[str] = (cfg.get("pinned", {}) or {}).get("apps", []) or []
    bl = cfg.get("blacklist", {}) or {}
    bl_wm: List[str] = bl.get("wm_class", []) or []
    bl_did: List[str] = bl.get("desktop_id", []) or []

    windows_by_class, focused_class = get_windows_by_class()
    desktop_db, wm_to_did = scan_desktop_entries()
    icon_cache = load_icon_cache()

    pinned_set = set(pinned)
    items: List[dict] = []

    # helper: create item from desktop id
    def make_from_desktop(did: str, pinned_flag: bool) -> Optional[dict]:
        if is_blacklisted(did, bl_did):
            return None
        e = desktop_db.get(did)
        name = e.name if e else did.replace(".desktop", "")
        wm = norm(e.startup_wm_class) if e else norm(did.replace(".desktop", ""))
        if is_blacklisted(wm, bl_wm):
            return None
        icon_name = e.icon if e else ""
        icon_path = resolve_icon_path(icon_name, icon_cache) or resolve_icon_path(FALLBACK_ICON_NAMES[0], icon_cache)
        running_ids = windows_by_class.get(wm, [])
        focused = (focused_class == wm)
        key = f"did:{did}"
        return {
            "id": did,
            "name": name,
            "icon": icon_path,
            "running": len(running_ids),
            "focused": focused,
            "pinned": pinned_flag,
            "cmd_click": f"python3 {EWW_CONFIG_DIR}/scripts/eww-dock.py activate {did}",
            "cmd_new": f"python3 {EWW_CONFIG_DIR}/scripts/eww-dock.py new {did}",
            "cmd_next": f"python3 {EWW_CONFIG_DIR}/scripts/eww-dock.py next {did}",
            "cmd_prev": f"python3 {EWW_CONFIG_DIR}/scripts/eww-dock.py prev {did}",
            "key": key,
            "wm": wm,
        }

    # pinned first (in order)
    for did in pinned:
        it = make_from_desktop(did, True)
        if it:
            items.append(it)

    # running apps not pinned
    for wm, ids in windows_by_class.items():
        if is_blacklisted(wm, bl_wm):
            continue
        did = wm_to_did.get(wm)
        if did and did in pinned_set:
            continue
        if did and is_blacklisted(did, bl_did):
            continue

        # if we can map to desktop entry, use it; else make a fallback pseudo item
        if did and did in desktop_db:
            it = make_from_desktop(did, False)
            if it:
                items.append(it)
        else:
            # fallback
            icon_path = resolve_icon_path(FALLBACK_ICON_NAMES[0], icon_cache)
            key = f"wm:{wm}"
            items.append({
                "id": key,
                "name": wm,
                "icon": icon_path,
                "running": len(ids),
                "focused": (focused_class == wm),
                "pinned": False,
                "cmd_click": f"python3 {EWW_CONFIG_DIR}/scripts/eww-dock.py activate-wm {wm}",
                "cmd_new": f"python3 {EWW_CONFIG_DIR}/scripts/eww-dock.py activate-wm {wm}",
                "cmd_next": f"python3 {EWW_CONFIG_DIR}/scripts/eww-dock.py next-wm {wm}",
                "cmd_prev": f"python3 {EWW_CONFIG_DIR}/scripts/eww-dock.py prev-wm {wm}",
                "key": key,
                "wm": wm,
            })

    # stable ordering for non-pinned: focused first, then running count desc, then name
    pinned_count = len(items)
    pinned_part = items[:pinned_count]
    rest = items[pinned_count:]
    rest.sort(key=lambda x: (not bool(x.get("focused")), -int(x.get("running", 0)), str(x.get("name", "")).lower()))
    items = pinned_part + rest

    save_icon_cache(icon_cache)
    return items

def cmd_list():
    print(json.dumps(build_items(), ensure_ascii=False))

def cmd_listen():
    # initial state
    print(json.dumps(build_items(), ensure_ascii=False), flush=True)

    # subscribe to i3 events for realtime updates
    sub = subprocess.Popen(
        ["i3-msg", "-t", "subscribe", "-m", '["window","workspace"]'],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    last_emit = 0.0
    debounce = 0.10

    while True:
        line = sub.stdout.readline() if sub.stdout else ""
        if not line:
            time.sleep(0.2)
            continue
        now = time.time()
        if now - last_emit < debounce:
            continue
        last_emit = now
        try:
            print(json.dumps(build_items(), ensure_ascii=False), flush=True)
        except Exception:
            # don't crash the dock; try again next event
            pass

def focus_cycle_for_desktop(desktop_id: str, direction: str):
    desktop_db, wm_to_did = scan_desktop_entries()
    e = desktop_db.get(desktop_id)
    wm = norm(e.startup_wm_class) if e else norm(desktop_id.replace(".desktop", ""))
    windows_by_class, _ = get_windows_by_class()
    ids = windows_by_class.get(wm, [])
    if not ids:
        launch_desktop(desktop_id)
        return
    focused = get_focused_con_id()
    key = f"did:{desktop_id}"
    target = get_next_focus_id(key, ids, focused) if direction == "next" else get_prev_focus_id(key, ids, focused)
    i3_focus_con_id_on_workspace(target)

def focus_cycle_for_wm(wm: str, direction: str):
    wm = norm(wm)
    windows_by_class, _ = get_windows_by_class()
    ids = windows_by_class.get(wm, [])
    if not ids:
        return
    focused = get_focused_con_id()
    key = f"wm:{wm}"
    target = get_next_focus_id(key, ids, focused) if direction == "next" else get_prev_focus_id(key, ids, focused)
    i3_focus_con_id_on_workspace(target)

def cmd_activate(desktop_id: str):
    desktop_db, wm_to_did = scan_desktop_entries()
    e = desktop_db.get(desktop_id)
    wm = norm(e.startup_wm_class) if e else norm(desktop_id.replace(".desktop", ""))
    windows_by_class, _ = get_windows_by_class()
    ids = windows_by_class.get(wm, [])
    if not ids:
        launch_desktop(desktop_id)
        return
    focused = get_focused_con_id()
    target = get_next_focus_id(f"did:{desktop_id}", ids, focused)
    i3_focus_con_id_on_workspace(target)

def cmd_new(desktop_id: str):
    launch_desktop(desktop_id)

def main():
    if len(sys.argv) < 2:
        print("usage: eww-dock.py <list|listen|activate|new|next|prev|activate-wm|next-wm|prev-wm> [arg]")
        sys.exit(2)

    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "list":
        cmd_list()
        return
    if cmd == "listen":
        cmd_listen()
        return

    if cmd == "activate" and arg:
        cmd_activate(arg)
        return
    if cmd == "new" and arg:
        cmd_new(arg)
        return
    if cmd == "next" and arg:
        focus_cycle_for_desktop(arg, "next")
        return
    if cmd == "prev" and arg:
        focus_cycle_for_desktop(arg, "prev")
        return

    if cmd == "activate-wm" and arg:
        focus_cycle_for_wm(arg, "next")
        return
    if cmd == "next-wm" and arg:
        focus_cycle_for_wm(arg, "next")
        return
    if cmd == "prev-wm" and arg:
        focus_cycle_for_wm(arg, "prev")
        return

    print("unknown command or missing arg")
    sys.exit(2)

if __name__ == "__main__":
    main()
