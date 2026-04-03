#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Native PyQt6 dock for i3.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Callable, Optional
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None

from PyQt6.QtCore import QEasingCurve, QLockFile, QProcess, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QGuiApplication, QColor, QCursor, QFont, QFontDatabase, QIcon, QPalette, QPixmap, QScreen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyqt.shared.runtime import current_executable_path, entry_command, fonts_root, is_frozen, project_root, python_executable, scripts_root, source_root
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family

ROOT = project_root()
APP_DIR = source_root()
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

FONTS_DIR = fonts_root()
LAUNCHER_APP = APP_DIR / "pyqt" / "launcher" / "launcher.py"
DOCK_CONFIG = APP_DIR / "pyqt" / "dock" / "dock.toml"
VOLUME_SCRIPT = scripts_root() / "volume.sh"
I3_VOLUME_BIN = Path.home() / ".local" / "bin" / "volume"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "hanauta-dock"
ICON_CACHE_PATH = CACHE_DIR / "icon_cache.json"
STATE_PATH = CACHE_DIR / "state.json"
LOCK_PATH = CACHE_DIR / "dock.lock"
DESKTOP_DIRS = [
    ROOT / "hanauta" / "config" / "applications",
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
DOCK_INTERNAL_WM_CLASSES = {"dock.py", "hanauta-dock"}
DOCK_INTERNAL_WINDOW_TITLES = {"CyberDock", "Dock Settings"}
MATERIAL_ICONS = {
    "apps": "\ue5c3",
    "settings": "\ue8b8",
    "volume_down": "\ue04d",
    "volume_mute": "\ue04e",
    "volume_off": "\ue04f",
    "volume_up": "\ue050",
}
MONITOR_MODE_PRIMARY = "primary"
MONITOR_MODE_FOLLOW_MOUSE = "follow_mouse"
MONITOR_MODE_NAMED = "named"


def run_cmd(cmd: list[str], timeout: float = 3.0) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def run_bg(cmd: list[str]) -> None:
    if not cmd:
        return
    try:
        if QProcess.startDetached(cmd[0], cmd[1:]):
            return
    except Exception:
        pass
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "material_symbols_outlined": FONTS_DIR / "MaterialSymbolsOutlined.ttf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
    }
    for key, path in font_map.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


def apply_antialias_font(widget: QWidget) -> None:
    font = widget.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child_font = child.font()
        child_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        child.setFont(child_font)


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def norm(value: str) -> str:
    return (value or "").strip().lower()


def is_blacklisted(value: str, patterns: list[str]) -> bool:
    normalized = norm(value)
    if not normalized:
        return False
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, norm(pattern)):
            return True
    return False


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def acquire_runtime_lock() -> QLockFile | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(LOCK_PATH))
    lock.setStaleLockTime(0)
    if lock.tryLock(4000):
        return lock
    try:
        lock.removeStaleLockFile()
    except Exception:
        pass
    if lock.tryLock(1000):
        return lock
    return None


def multiply_alpha(color: str, factor: float) -> str:
    value = (color or "").strip()
    clamped = max(0.0, min(1.0, factor))
    if value.startswith("rgba(") and value.endswith(")"):
        parts = [part.strip() for part in value[5:-1].split(",")]
        if len(parts) == 4:
            try:
                red = int(parts[0])
                green = int(parts[1])
                blue = int(parts[2])
                alpha = float(parts[3])
                return f"rgba({red}, {green}, {blue}, {max(0.0, min(1.0, alpha * clamped)):.2f})"
            except Exception:
                pass
    if value.startswith("#"):
        return rgba(value, clamped)
    return value


def sh(cmd: list[str], timeout: float = 4.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )


def parse_pactl_devices(kind: str) -> list[dict[str, object]]:
    result = sh(["pactl", "list", kind], timeout=6.0)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    rows: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("Sink #", "Source #")):
            if isinstance(current, dict):
                rows.append(current)
            current = {
                "index": int(stripped.split("#", 1)[1] or 0),
                "name": "",
                "description": "",
                "mute": False,
                "volume": 0,
            }
            continue
        if not isinstance(current, dict):
            continue
        if stripped.startswith("Name:"):
            current["name"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Description:"):
            current["description"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Mute:"):
            current["mute"] = stripped.split(":", 1)[1].strip().lower() == "yes"
        elif stripped.startswith("Volume:"):
            match = re.search(r"(\d+)%", stripped)
            if match is not None:
                try:
                    current["volume"] = max(0, min(150, int(match.group(1))))
                except Exception:
                    current["volume"] = 0
    if isinstance(current, dict):
        rows.append(current)
    return rows


def i3_tree() -> dict:
    result = sh(["i3-msg", "-t", "get_tree"])
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except Exception:
        return {}


def _screen_matches_output(screen: QScreen, output_name: str) -> bool:
    screen_name = screen.name().strip()
    return bool(screen_name) and screen_name == output_name.strip()


def _active_output_names() -> tuple[str, str]:
    primary_output_name = ""
    fallback_output_name = ""
    raw = run_cmd(["i3-msg", "-t", "get_outputs"])
    if not raw:
        return primary_output_name, fallback_output_name
    try:
        outputs = json.loads(raw)
    except Exception:
        return primary_output_name, fallback_output_name
    if not isinstance(outputs, list):
        return primary_output_name, fallback_output_name
    for item in outputs:
        if not isinstance(item, dict) or not bool(item.get("active", False)):
            continue
        output_name = str(item.get("name", "")).strip()
        if not output_name:
            continue
        if not fallback_output_name:
            fallback_output_name = output_name
        if bool(item.get("primary", False)):
            primary_output_name = output_name
            break
    return primary_output_name, fallback_output_name


def _screen_by_name(output_name: str) -> QScreen | None:
    target_name = output_name.strip()
    if not target_name:
        return None
    for screen in QApplication.screens():
        if _screen_matches_output(screen, target_name):
            return screen
    return None


def preferred_dock_screen(monitor_mode: str = MONITOR_MODE_PRIMARY, monitor_name: str = "") -> QScreen | None:
    screens = QApplication.screens()
    if not screens:
        return None

    normalized_mode = str(monitor_mode or MONITOR_MODE_PRIMARY).strip().lower()
    if normalized_mode == MONITOR_MODE_FOLLOW_MOUSE:
        screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is not None:
            return screen
        normalized_mode = MONITOR_MODE_PRIMARY
    elif normalized_mode == MONITOR_MODE_NAMED:
        screen = _screen_by_name(monitor_name)
        if screen is not None:
            return screen
        normalized_mode = MONITOR_MODE_PRIMARY

    primary_output_name, fallback_output_name = _active_output_names()
    for output_name in (primary_output_name, fallback_output_name):
        screen = _screen_by_name(output_name)
        if screen is not None:
            return screen

    primary_screen = QApplication.primaryScreen()
    if primary_screen is not None:
        return primary_screen
    return screens[0]


def walk_nodes(node: dict):
    yield node
    for key in ("nodes", "floating_nodes"):
        for child in node.get(key, []) or []:
            yield from walk_nodes(child)


@dataclass
class DesktopEntry:
    desktop_id: str
    name: str
    icon: str
    startup_wm_class: str
    exec: str = ""
    actions: list["DesktopAction"] = field(default_factory=list)


@dataclass
class DesktopAction:
    action_id: str
    name: str
    exec: str


@dataclass
class WindowEntry:
    con_id: int
    wm_class: str
    title: str
    focused: bool


def get_open_windows() -> list[WindowEntry]:
    tree = i3_tree()
    if not tree:
        return []
    windows: list[WindowEntry] = []
    for node in walk_nodes(tree):
        if node.get("window") is None:
            continue
        properties = node.get("window_properties") or {}
        wm_class = norm(properties.get("class") or properties.get("instance") or "")
        if not wm_class:
            continue
        title = (node.get("name") or properties.get("title") or "").strip()
        if wm_class in DOCK_INTERNAL_WM_CLASSES or title in DOCK_INTERNAL_WINDOW_TITLES:
            continue
        con_id = int(node.get("id") or 0)
        if not con_id:
            continue
        windows.append(
            WindowEntry(
                con_id=con_id,
                wm_class=wm_class,
                title=title,
                focused=bool(node.get("focused")),
            )
        )
    return windows


def get_workspaces_by_con_id() -> dict[int, str]:
    tree = i3_tree()
    mapping: dict[int, str] = {}

    def walk(node: dict, workspace_name: str = "") -> None:
        current_workspace = workspace_name
        if node.get("type") == "workspace":
            current_workspace = node.get("name") or workspace_name
        if node.get("window") is not None and node.get("id") is not None and current_workspace:
            mapping[int(node["id"])] = current_workspace
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []) or []:
                walk(child, current_workspace)

    if tree:
        walk(tree)
    return mapping


def get_current_workspace() -> str:
    result = sh(["i3-msg", "-t", "get_workspaces"])
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    try:
        workspaces = json.loads(result.stdout)
    except Exception:
        return ""
    for workspace in workspaces:
        if workspace.get("focused"):
            return str(workspace.get("name") or "")
    return ""


def get_focused_con_id() -> Optional[int]:
    for window in get_open_windows():
        if window.focused:
            return window.con_id
    return None


def scan_desktop_entries() -> tuple[dict[str, DesktopEntry], dict[str, str]]:
    entries: dict[str, DesktopEntry] = {}
    wm_map: dict[str, str] = {}

    for directory in DESKTOP_DIRS:
        if not directory.exists():
            continue
        for desktop_file in directory.glob("*.desktop"):
            try:
                text = desktop_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            name = ""
            icon = ""
            startup_wm = ""
            exec_command = ""
            action_ids: list[str] = []
            actions: dict[str, DesktopAction] = {}
            in_entry = False
            current_action_id = ""
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line == "[Desktop Entry]":
                    in_entry = True
                    current_action_id = ""
                    continue
                if line.startswith("[Desktop Action ") and line.endswith("]"):
                    in_entry = False
                    current_action_id = line[len("[Desktop Action ") : -1].strip()
                    if current_action_id and current_action_id not in actions:
                        actions[current_action_id] = DesktopAction(current_action_id, current_action_id, "")
                    continue
                if line.startswith("[") and line.endswith("]") and line != "[Desktop Entry]":
                    in_entry = False
                    current_action_id = ""
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if in_entry:
                    if key == "Name" and not name:
                        name = value
                    elif key == "Icon" and not icon:
                        icon = value
                    elif key == "StartupWMClass" and not startup_wm:
                        startup_wm = value
                    elif key == "Exec" and not exec_command:
                        exec_command = value
                    elif key == "Actions" and not action_ids:
                        action_ids = [part.strip() for part in value.split(";") if part.strip()]
                    continue
                if current_action_id:
                    action = actions.setdefault(current_action_id, DesktopAction(current_action_id, current_action_id, ""))
                    if key == "Name" and (not action.name or action.name == current_action_id):
                        action.name = value
                    elif key == "Exec" and not action.exec:
                        action.exec = value

            desktop_id = desktop_file.name
            if not name:
                name = desktop_id.replace(".desktop", "")
            if not startup_wm:
                startup_wm = desktop_id.replace(".desktop", "")

            ordered_actions = [actions[action_id] for action_id in action_ids if action_id in actions and actions[action_id].exec]
            entry = DesktopEntry(
                desktop_id=desktop_id,
                name=name,
                icon=icon,
                startup_wm_class=startup_wm,
                exec=exec_command,
                actions=ordered_actions,
            )
            entries[desktop_id] = entry
            wm_map[norm(startup_wm)] = desktop_id
            wm_map[norm(desktop_id.replace(".desktop", ""))] = desktop_id

    return entries, wm_map


def load_icon_cache() -> dict[str, str]:
    return load_json(ICON_CACHE_PATH, {})


def save_icon_cache(cache: dict[str, str]) -> None:
    trimmed = cache
    if len(trimmed) > 4000:
        trimmed = dict(list(trimmed.items())[-2000:])
    save_json(ICON_CACHE_PATH, trimmed)


def resolve_icon_path(icon_name: str, icon_cache: dict[str, str]) -> str:
    icon_name = (icon_name or "").strip() or FALLBACK_ICON_NAMES[0]

    if icon_name in icon_cache and Path(icon_cache[icon_name]).exists():
        return icon_cache[icon_name]

    explicit = Path(icon_name)
    if explicit.is_absolute() and explicit.exists():
        icon_cache[icon_name] = str(explicit)
        return str(explicit)

    candidates: list[Path] = []
    exts = [".svg", ".png", ".xpm"]

    def add_if_exists(path: Path) -> None:
        if path.exists():
            candidates.append(path)

    for base in ICON_DIRS:
        if not base.exists():
            continue
        for ext in exts:
            add_if_exists(base / f"{icon_name}{ext}")
        if (base / "hicolor").exists() or (base / "Adwaita").exists():
            for theme in ("hicolor", "Adwaita", "Papirus", "Papirus-Dark"):
                theme_dir = base / theme
                if not theme_dir.exists():
                    continue
                for ext in exts:
                    add_if_exists(theme_dir / "scalable" / "apps" / f"{icon_name}{ext}")
                for size in ("256x256", "128x128", "64x64", "48x48", "32x32", "24x24", "16x16"):
                    for ext in exts:
                        add_if_exists(theme_dir / size / "apps" / f"{icon_name}{ext}")

    if not candidates:
        for fallback_name in FALLBACK_ICON_NAMES:
            if fallback_name == icon_name:
                continue
            fallback_path = resolve_icon_path(fallback_name, icon_cache) if fallback_name not in icon_cache else icon_cache[fallback_name]
            if fallback_path and Path(fallback_path).exists():
                icon_cache[icon_name] = fallback_path
                return fallback_path
        icon_cache[icon_name] = ""
        return ""

    def score(path: Path) -> tuple[int, int]:
        ext_score = 2 if path.suffix == ".svg" else (1 if path.suffix == ".png" else 0)
        size_score = 0
        for part in path.parts:
            if "x" not in part:
                continue
            width, _, height = part.partition("x")
            if width.isdigit() and height.isdigit():
                size_score = int(width)
        return ext_score, size_score

    best = sorted(candidates, key=score, reverse=True)[0]
    icon_cache[icon_name] = str(best)
    return str(best)


def load_dock_config() -> dict:
    if not DOCK_CONFIG.exists() or tomllib is None:
        return {
            "pinned": {"apps": []},
            "blacklist": {"wm_class": [], "desktop_id": [], "window_name": []},
            "dock": {
                "auto_hide": False,
                "width": 60,
                "width_unit": "%",
                "height": 64,
                "icons_left": False,
                "position": "center",
                "transparency": 60,
                "monitor_mode": MONITOR_MODE_PRIMARY,
                "monitor_name": "",
            },
        }
    try:
        config = tomllib.loads(DOCK_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {
            "pinned": {"apps": []},
            "blacklist": {"wm_class": [], "desktop_id": [], "window_name": []},
            "dock": {
                "auto_hide": False,
                "width": 60,
                "width_unit": "%",
                "height": 64,
                "icons_left": False,
                "position": "center",
                "transparency": 60,
                "monitor_mode": MONITOR_MODE_PRIMARY,
                "monitor_name": "",
            },
        }
    dock_cfg = dict(config.get("dock", {}))
    dock_cfg.setdefault("auto_hide", False)
    dock_cfg.setdefault("width", 60)
    dock_cfg.setdefault("width_unit", "%")
    dock_cfg.setdefault("height", 64)
    dock_cfg.setdefault("icons_left", False)
    dock_cfg.setdefault("position", "center")
    dock_cfg.setdefault("transparency", 60)
    monitor_mode = str(dock_cfg.get("monitor_mode", MONITOR_MODE_PRIMARY)).strip().lower()
    dock_cfg["monitor_mode"] = monitor_mode if monitor_mode in {MONITOR_MODE_PRIMARY, MONITOR_MODE_FOLLOW_MOUSE, MONITOR_MODE_NAMED} else MONITOR_MODE_PRIMARY
    dock_cfg["monitor_name"] = str(dock_cfg.get("monitor_name", "")).strip()
    config["dock"] = dock_cfg
    config.setdefault("pinned", {"apps": []})
    config.setdefault("blacklist", {"wm_class": [], "desktop_id": []})
    blacklist_cfg = dict(config.get("blacklist", {}))
    blacklist_cfg.setdefault("wm_class", [])
    blacklist_cfg.setdefault("desktop_id", [])
    blacklist_cfg.setdefault("window_name", [])
    config["blacklist"] = blacklist_cfg
    return config


def save_dock_config(config: dict) -> None:
    def write_list(values: list[str]) -> str:
        if not values:
            return "[]"
        items = ",\n".join(f'  "{value}"' for value in values)
        return f"[\n{items}\n]"

    dock = config.get("dock", {})
    pinned = config.get("pinned", {})
    blacklist = config.get("blacklist", {})
    body = (
        "[dock]\n"
        f"auto_hide = {'true' if dock.get('auto_hide') else 'false'}\n"
        f"width = {int(dock.get('width', 0) or 0)}\n"
        f'width_unit = "{dock.get("width_unit", "px")}"\n'
        f"height = {int(dock.get('height', 64) or 64)}\n"
        f"icons_left = {'true' if dock.get('icons_left') else 'false'}\n\n"
        f'position = "{dock.get("position", "center")}"\n'
        f"transparency = {int(dock.get('transparency', 60) or 60)}\n"
        f'monitor_mode = "{dock.get("monitor_mode", MONITOR_MODE_PRIMARY)}"\n'
        f'monitor_name = "{str(dock.get("monitor_name", "")).strip()}"\n\n'
        "[pinned]\n"
        f"apps = {write_list(list(pinned.get('apps', [])))}\n\n"
        "[blacklist]\n"
        f"wm_class = {write_list(list(blacklist.get('wm_class', [])))}\n\n"
        f"desktop_id = {write_list(list(blacklist.get('desktop_id', [])))}\n\n"
        f"window_name = {write_list(list(blacklist.get('window_name', [])))}\n"
    )
    DOCK_CONFIG.write_text(body, encoding="utf-8")


def i3_focus_con_id_on_workspace(con_id: int) -> None:
    workspace = get_workspaces_by_con_id().get(int(con_id))
    if workspace:
        subprocess.run(["i3-msg", "workspace", workspace], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(
        ["i3-msg", f'[con_id="{con_id}"]', "focus"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def launch_desktop(desktop_id: str) -> None:
    desktop_base = desktop_id.replace(".desktop", "")
    launched = subprocess.run(["gtk-launch", desktop_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if launched.returncode != 0:
        subprocess.Popen(["gtk-launch", desktop_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def desktop_exec_to_command(exec_line: str) -> list[str]:
    cleaned = (exec_line or "").strip()
    if not cleaned:
        return []
    for token in ("%f", "%F", "%u", "%U", "%i", "%c", "%k", "%d", "%D", "%n", "%N", "%v", "%m"):
        cleaned = cleaned.replace(token, "")
    cleaned = cleaned.replace("%%", "%")
    try:
        return [part for part in shlex.split(cleaned) if part]
    except Exception:
        return []


def get_next_focus_id(key: str, ids: list[int], focused: Optional[int]) -> int:
    state = load_json(STATE_PATH, {})
    last = state.get("last_index", {}).get(key, -1)
    if focused in ids:
        current_index = ids.index(focused)
    else:
        current_index = last if isinstance(last, int) and 0 <= last < len(ids) else -1
    next_index = (current_index + 1) % len(ids)
    state.setdefault("last_index", {})[key] = next_index
    save_json(STATE_PATH, state)
    return ids[next_index]


def self_command(command: str, arg: str) -> str:
    if is_frozen():
        target = current_executable_path()
        return f"{shlex.quote(str(target))} {command} {shlex.quote(arg)}"
    target = Path(__file__).resolve()
    interpreter = python_executable()
    return f"{shlex.quote(interpreter)} {shlex.quote(str(target))} {command} {shlex.quote(arg)}"


def build_dock_items(config: dict) -> list[DockItem]:
    pinned: list[str] = list((config.get("pinned", {}) or {}).get("apps", []) or [])
    blacklist = config.get("blacklist", {}) or {}
    bl_wm: list[str] = list(blacklist.get("wm_class", []) or [])
    bl_did: list[str] = list(blacklist.get("desktop_id", []) or [])
    bl_names: list[str] = list(blacklist.get("window_name", []) or [])

    visible_windows = [
        window
        for window in get_open_windows()
        if not is_blacklisted(window.wm_class, bl_wm) and not is_blacklisted(window.title, bl_names)
    ]
    workspace_by_con_id = get_workspaces_by_con_id()
    current_workspace = get_current_workspace()

    windows_by_class: dict[str, list[WindowEntry]] = {}
    for window in visible_windows:
        windows_by_class.setdefault(window.wm_class, []).append(window)

    desktop_db, wm_to_did = scan_desktop_entries()
    icon_cache = load_icon_cache()
    pinned_set = set(pinned)
    items: list[DockItem] = []

    pinned_wm_map: dict[str, str] = {}
    for desktop_id in pinned:
        entry = desktop_db.get(desktop_id)
        wm_class = norm(entry.startup_wm_class) if entry else norm(desktop_id.replace(".desktop", ""))
        if wm_class:
            pinned_wm_map[wm_class] = desktop_id

    def make_from_desktop(desktop_id: str, pinned_flag: bool) -> Optional[DockItem]:
        if is_blacklisted(desktop_id, bl_did):
            return None
        entry = desktop_db.get(desktop_id)
        wm_class = norm(entry.startup_wm_class) if entry else norm(desktop_id.replace(".desktop", ""))
        if is_blacklisted(wm_class, bl_wm):
            return None
        running_windows = windows_by_class.get(wm_class, [])
        name = entry.name if entry else desktop_id.replace(".desktop", "")
        icon_name = entry.icon if entry else ""
        icon_path = resolve_icon_path(icon_name, icon_cache) or resolve_icon_path(FALLBACK_ICON_NAMES[0], icon_cache)
        on_current_workspace = any(workspace_by_con_id.get(window.con_id) == current_workspace for window in running_windows)
        # Prefer focusing the live window class when the app is already running.
        click_command = self_command("activate-wm", wm_class) if running_windows else self_command("activate", desktop_id)
        return DockItem(
            item_id=desktop_id,
            name=name,
            icon=icon_path,
            running=len(running_windows),
            focused=on_current_workspace,
            pinned=pinned_flag,
            desktop_id=desktop_id,
            desktop_actions=list(entry.actions) if entry else [],
            cmd_click=click_command,
            cmd_new=self_command("new", desktop_id),
        )

    for desktop_id in pinned:
        item = make_from_desktop(desktop_id, True)
        if item is not None:
            items.append(item)

    for wm_class, running_windows in windows_by_class.items():
        if is_blacklisted(wm_class, bl_wm):
            continue
        desktop_id = pinned_wm_map.get(wm_class) or wm_to_did.get(wm_class)
        if desktop_id and desktop_id in pinned_set:
            continue
        if desktop_id and is_blacklisted(desktop_id, bl_did):
            continue
        if desktop_id and desktop_id in desktop_db:
            item = make_from_desktop(desktop_id, False)
            if item is not None:
                items.append(item)
            continue

        icon_path = resolve_icon_path(FALLBACK_ICON_NAMES[0], icon_cache)
        items.append(
            DockItem(
                item_id=f"wm:{wm_class}",
                name=wm_class,
                icon=icon_path,
                running=len(running_windows),
                focused=any(workspace_by_con_id.get(window.con_id) == current_workspace for window in running_windows),
                pinned=False,
                desktop_id=desktop_id if desktop_id else None,
                desktop_actions=list(desktop_db.get(desktop_id).actions) if desktop_id and desktop_id in desktop_db else [],
                cmd_click=self_command("activate-wm", wm_class),
                cmd_new=self_command("activate-wm", wm_class),
            )
        )

    pinned_count = len([item for item in items if item.pinned])
    pinned_items = items[:pinned_count]
    running_items = items[pinned_count:]
    running_items.sort(key=lambda item: (not item.focused, -item.running, item.name.lower()))
    save_icon_cache(icon_cache)
    return pinned_items + running_items


def cmd_activate(desktop_id: str) -> int:
    desktop_db, _ = scan_desktop_entries()
    entry = desktop_db.get(desktop_id)
    wm_class = norm(entry.startup_wm_class) if entry else norm(desktop_id.replace(".desktop", ""))
    matching_ids = [window.con_id for window in get_open_windows() if window.wm_class == wm_class]
    if not matching_ids:
        launch_desktop(desktop_id)
        return 0
    target = get_next_focus_id(f"did:{desktop_id}", matching_ids, get_focused_con_id())
    i3_focus_con_id_on_workspace(target)
    return 0


def cmd_new(desktop_id: str) -> int:
    launch_desktop(desktop_id)
    return 0


def cmd_activate_wm(wm_class: str) -> int:
    normalized = norm(wm_class)
    matching_ids = [window.con_id for window in get_open_windows() if window.wm_class == normalized]
    if not matching_ids:
        return 0
    target = get_next_focus_id(f"wm:{normalized}", matching_ids, get_focused_con_id())
    i3_focus_con_id_on_workspace(target)
    return 0


@dataclass
class DockItem:
    item_id: str
    name: str
    icon: str
    running: int
    focused: bool
    pinned: bool
    desktop_id: str | None
    desktop_actions: list[DesktopAction]
    cmd_click: str
    cmd_new: str


class DockAppButton(QFrame):
    def __init__(
        self,
        item: DockItem,
        button_height: int,
        theme,
        on_toggle_pin: Callable[[DockItem], None],
        on_run_action: Callable[[DockItem, DesktopAction], None],
    ) -> None:
        super().__init__()
        self.item = item
        self.theme = theme
        self.on_toggle_pin = on_toggle_pin
        self.on_run_action = on_run_action
        self.button_height = max(64, button_height)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("dockAppButton")
        self.setToolTip(item.name)
        self.setFixedSize(60, self.button_height)

        layout = QVBoxLayout(self)
        icon_box = min(48, max(44, self.button_height - 24))
        dot_height = 6
        spacing = 4
        # Keep the icon center aligned with the other dock controls while
        # leaving the running dot below it.
        top_padding = max(8, (self.button_height // 2) - (icon_box // 2))
        bottom_padding = max(8, self.button_height - top_padding - icon_box - spacing - dot_height)
        layout.setContentsMargins(8, top_padding, 8, bottom_padding)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(icon_box, icon_box)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        pixmap = QPixmap(item.icon)
        if not pixmap.isNull():
            icon_size = min(34, max(30, icon_box - 12))
            self.icon_label.setPixmap(
                pixmap.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.icon_label.setText(item.name[:1].upper())

        self.dot = QFrame()
        self.dot.setFixedSize(6, 6)
        self.dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignCenter)
        self._render()

    def apply_theme(self, theme) -> None:
        self.theme = theme
        self._render()

    def _render(self) -> None:
        theme = self.theme
        if self.item.focused:
            bg = theme.app_focused_bg
            border = theme.app_focused_border
            dot = theme.app_dot
        elif self.item.running:
            bg = theme.app_running_bg
            border = theme.app_running_border
            dot = theme.text
        else:
            bg = "transparent"
            border = "transparent"
            dot = "transparent"
        self.setStyleSheet(
            f"""
            QFrame#dockAppButton {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 20px;
            }}
            QFrame#dockAppButton:hover {{
                background: {theme.hover_bg};
            }}
            """
        )
        self.dot.setStyleSheet(f"background: {dot}; border-radius: 3px;")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            run_bg(shlex.split(self.item.cmd_click))
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            run_bg(shlex.split(self.item.cmd_new))
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def _show_context_menu(self, global_pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background: {self.theme.panel_bg};
                border: 1px solid {self.theme.panel_border};
                border-radius: 16px;
                padding: 8px;
                color: {self.theme.text};
                font-family: "{theme_font_family('ui') or 'Sans Serif'}";
            }}
            QMenu::item {{
                padding: 10px 14px;
                border-radius: 10px;
                margin: 2px 0;
            }}
            QMenu::item:selected {{
                background: {self.theme.hover_bg};
            }}
            QMenu::separator {{
                height: 1px;
                margin: 6px 2px;
                background: {self.theme.separator};
            }}
            """
        )
        for action in self.item.desktop_actions:
            qt_action = QAction(action.name, menu)
            qt_action.triggered.connect(lambda _checked=False, desktop_action=action: self.on_run_action(self.item, desktop_action))
            menu.addAction(qt_action)
        if self.item.desktop_actions:
            menu.addSeparator()
        pin_action = QAction("UNPIN" if self.item.pinned else "PIN IT", menu)
        pin_action.setEnabled(bool(self.item.desktop_id))
        pin_action.triggered.connect(lambda _checked=False: self.on_toggle_pin(self.item))
        menu.addAction(pin_action)
        menu.exec(global_pos)


class VolumeButton(QPushButton):
    rightClicked = pyqtSignal(object)

    def __init__(self, material_font: str, theme) -> None:
        super().__init__(material_icon("volume_up"))
        self.material_font = material_font
        self.theme = theme
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFont(QFont(material_font, 18))
        self.setObjectName("dockUtilityButton")
        self.setFixedSize(42, 42)

    def apply_theme(self, theme) -> None:
        self.theme = theme

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return

        # Prefer i3-volume so wheel changes also show volnoti notifications.
        if I3_VOLUME_BIN.exists():
            if delta > 0:
                run_bg([str(I3_VOLUME_BIN), "-n", "-N", "volnoti", "up", "5"])
            else:
                run_bg([str(I3_VOLUME_BIN), "-n", "-N", "volnoti", "down", "5"])
            event.accept()
            return

        # Fallback for environments without i3-volume installed.
        current = int(run_cmd([str(VOLUME_SCRIPT), "vol"]) or "0")
        if delta > 0:
            current = min(100, current + 5)
        else:
            current = max(0, current - 5)
        run_bg([str(VOLUME_SCRIPT), "set", str(current)])
        event.accept()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)


class AudioDevicePopup(QDialog):
    def __init__(self, theme, ui_font: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.ui_font = ui_font
        self._sink_rows: list[dict[str, object]] = []
        self._source_rows: list[dict[str, object]] = []
        self.setObjectName("dockAudioPopup")
        self.setWindowTitle("Audio Devices")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        title = QLabel("Audio Devices")
        title.setFont(QFont(ui_font, 11, QFont.Weight.DemiBold))
        header_row.addWidget(title, 1)
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("audioPopupCloseButton")
        self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_button.clicked.connect(self.hide)
        header_row.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignRight)
        subtitle = QLabel("Switch output/input and adjust microphone quickly.")
        subtitle.setObjectName("popupSubtitle")
        subtitle.setWordWrap(True)
        layout.addLayout(header_row)
        layout.addWidget(subtitle)

        output_section = QFrame()
        output_section.setObjectName("audioPopupSection")
        output_layout = QVBoxLayout(output_section)
        output_layout.setContentsMargins(12, 10, 12, 10)
        output_layout.setSpacing(8)
        out_label = QLabel("Output device")
        self.sink_combo = QComboBox()
        self.sink_combo.setObjectName("audioDeviceCombo")
        self.sink_combo.view().setObjectName("audioDeviceComboView")
        self.sink_combo.currentIndexChanged.connect(self._set_default_sink)
        output_layout.addWidget(out_label)
        output_layout.addWidget(self.sink_combo)

        self.sink_volume_label = QLabel("Output volume: 0%")
        self.sink_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.sink_volume_slider.setRange(0, 150)
        self.sink_volume_slider.sliderReleased.connect(self._apply_sink_volume)
        self.sink_mute_check = QCheckBox("Mute output")
        self.sink_mute_check.stateChanged.connect(self._set_sink_mute)
        output_layout.addWidget(self.sink_volume_label)
        output_layout.addWidget(self.sink_volume_slider)
        output_layout.addWidget(self.sink_mute_check)
        layout.addWidget(output_section)

        input_section = QFrame()
        input_section.setObjectName("audioPopupSection")
        input_layout = QVBoxLayout(input_section)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(8)
        in_label = QLabel("Input device")
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("audioDeviceCombo")
        self.source_combo.view().setObjectName("audioDeviceComboView")
        self.source_combo.currentIndexChanged.connect(self._set_default_source)
        input_layout.addWidget(in_label)
        input_layout.addWidget(self.source_combo)

        self.source_volume_label = QLabel("Input volume: 0%")
        self.source_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.source_volume_slider.setRange(0, 150)
        self.source_volume_slider.sliderReleased.connect(self._apply_source_volume)
        self.source_mute_check = QCheckBox("Mute microphone")
        self.source_mute_check.stateChanged.connect(self._set_source_mute)
        input_layout.addWidget(self.source_volume_label)
        input_layout.addWidget(self.source_volume_slider)
        input_layout.addWidget(self.source_mute_check)
        layout.addWidget(input_section)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.refresh_devices)
        layout.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignRight)

        self._apply_styles()
        self.refresh_devices()

    def _build_stylesheet(self) -> str:
        theme = self.theme
        return f"""
            QDialog#dockAudioPopup {{
                background: {rgba(theme.surface_container, 0.98)};
                border: 1px solid {rgba(theme.outline, 0.22)};
                border-radius: 18px;
                color: {theme.text};
            }}
            QFrame#audioPopupSection {{
                background: {rgba(theme.surface, 0.90)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                border-radius: 14px;
            }}
            QLabel {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QLabel#popupSubtitle {{
                color: {theme.text_muted};
                font-size: 11px;
            }}
            QPushButton#audioPopupCloseButton {{
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                border-radius: 14px;
                border: 1px solid {rgba(theme.outline, 0.26)};
                background: {rgba(theme.surface, 0.92)};
                color: {theme.text};
                font-family: "{self.ui_font}";
                font-weight: 700;
                padding: 0;
            }}
            QPushButton#audioPopupCloseButton:hover {{
                background: {rgba(theme.on_surface, 0.08)};
            }}
            QPushButton#audioPopupCloseButton:pressed {{
                background: {rgba(theme.on_surface, 0.14)};
            }}
            QComboBox, QSlider, QCheckBox {{
                font-family: "{self.ui_font}";
            }}
            QComboBox#audioDeviceCombo {{
                background: {rgba(theme.surface, 0.94)};
                border: 1px solid {rgba(theme.outline, 0.24)};
                border-radius: 12px;
                padding: 6px 10px;
                color: {theme.text};
            }}
            QComboBox#audioDeviceCombo:focus {{
                border: 1px solid {rgba(theme.primary, 0.72)};
            }}
            QComboBox#audioDeviceCombo QAbstractItemView,
            QAbstractItemView#audioDeviceComboView,
            QListView#audioDeviceComboView {{
                background: {rgba(theme.surface_container, 0.98)};
                color: {theme.text};
                selection-background-color: {rgba(theme.primary, 0.24)};
                selection-color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.28)};
                border-radius: 10px;
                outline: none;
                padding: 4px;
            }}
            QAbstractItemView#audioDeviceComboView::item,
            QListView#audioDeviceComboView::item {{
                min-height: 28px;
                border-radius: 8px;
                padding: 4px 8px;
            }}
            QCheckBox {{
                color: {theme.text};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 5px;
                border: 1px solid {rgba(theme.outline, 0.36)};
                background: {rgba(theme.surface, 0.90)};
            }}
            QCheckBox::indicator:checked {{
                background: {theme.primary};
                border: 1px solid {rgba(theme.primary, 0.9)};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                border-radius: 999px;
                background: {rgba(theme.outline, 0.25)};
            }}
            QSlider::sub-page:horizontal {{
                background: {theme.primary};
                border-radius: 999px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
                background: {theme.primary};
            }}
            QPushButton#refreshButton {{
                min-height: 34px;
                border-radius: 12px;
                background: {rgba(theme.primary, 0.16)};
                border: 1px solid {rgba(theme.primary, 0.25)};
                color: {theme.text};
                font-family: "{self.ui_font}";
                font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton#refreshButton:hover {{
                background: {rgba(theme.primary, 0.22)};
            }}
            """

    def _apply_styles(self) -> None:
        self.setStyleSheet(self._build_stylesheet())
        self._style_combo_popup_views()

    def _style_combo_popup_views(self) -> None:
        view_stylesheet = f"""
            QAbstractItemView#audioDeviceComboView,
            QListView#audioDeviceComboView {{
                background: {rgba(self.theme.surface_container, 0.98)};
                color: {self.theme.text};
                selection-background-color: {rgba(self.theme.primary, 0.24)};
                selection-color: {self.theme.text};
                border: 1px solid {rgba(self.theme.outline, 0.28)};
                border-radius: 10px;
                outline: none;
                padding: 4px;
            }}
            QAbstractItemView#audioDeviceComboView::item,
            QListView#audioDeviceComboView::item {{
                min-height: 28px;
                border-radius: 8px;
                padding: 4px 8px;
                background: transparent;
            }}
            QAbstractItemView#audioDeviceComboView::item:selected,
            QListView#audioDeviceComboView::item:selected {{
                background: {rgba(self.theme.primary, 0.24)};
            }}
            """
        base_color = QColor(rgba(self.theme.surface_container, 0.98))
        alt_color = QColor(rgba(self.theme.surface, 0.94))
        text_color = QColor(self.theme.text)
        highlight_color = QColor(rgba(self.theme.primary, 0.24))
        for combo in (getattr(self, "sink_combo", None), getattr(self, "source_combo", None)):
            if not isinstance(combo, QComboBox):
                continue
            view = combo.view()
            if view is None:
                continue
            view.setObjectName("audioDeviceComboView")
            view.setAutoFillBackground(True)
            view.setStyleSheet(view_stylesheet)
            palette = view.palette()
            palette.setColor(QPalette.ColorRole.Base, base_color)
            palette.setColor(QPalette.ColorRole.AlternateBase, alt_color)
            palette.setColor(QPalette.ColorRole.Text, text_color)
            palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
            palette.setColor(QPalette.ColorRole.HighlightedText, text_color)
            view.setPalette(palette)
            viewport = view.viewport()
            if viewport is not None:
                viewport.setAutoFillBackground(True)
                viewport.setStyleSheet(f"background: {rgba(self.theme.surface_container, 0.98)};")

    def apply_theme(self, theme) -> None:
        self.theme = theme
        self._apply_styles()

    def popup_at(self, global_pos) -> None:
        self.refresh_devices()
        self.adjustSize()
        x = int(global_pos.x() - self.width() + 36)
        y = int(global_pos.y() - self.height() - 8)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _combo_find_name(self, combo: QComboBox, name: str) -> int:
        for i in range(combo.count()):
            if str(combo.itemData(i) or "") == name:
                return i
        return -1

    def refresh_devices(self) -> None:
        if not shutil.which("pactl"):
            self.sink_combo.clear()
            self.source_combo.clear()
            self.sink_combo.addItem("pactl not available", "")
            self.source_combo.addItem("pactl not available", "")
            return
        default_sink = run_cmd(["pactl", "get-default-sink"]).strip()
        default_source = run_cmd(["pactl", "get-default-source"]).strip()
        self._sink_rows = parse_pactl_devices("sinks")
        self._source_rows = parse_pactl_devices("sources")

        self.sink_combo.blockSignals(True)
        self.sink_combo.clear()
        for row in self._sink_rows:
            name = str(row.get("name", "")).strip()
            label = str(row.get("description", "")).strip() or name
            if name:
                self.sink_combo.addItem(label, name)
        sink_index = self._combo_find_name(self.sink_combo, default_sink)
        self.sink_combo.setCurrentIndex(0 if sink_index < 0 else sink_index)
        self.sink_combo.blockSignals(False)

        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for row in self._source_rows:
            name = str(row.get("name", "")).strip()
            if ".monitor" in name:
                continue
            label = str(row.get("description", "")).strip() or name
            if name:
                self.source_combo.addItem(label, name)
        source_index = self._combo_find_name(self.source_combo, default_source)
        self.source_combo.setCurrentIndex(0 if source_index < 0 else source_index)
        self.source_combo.blockSignals(False)

        self._sync_sink_controls()
        self._sync_source_controls()

    def _selected_sink_name(self) -> str:
        return str(self.sink_combo.currentData() or "").strip()

    def _selected_source_name(self) -> str:
        return str(self.source_combo.currentData() or "").strip()

    def _row_by_name(self, rows: list[dict[str, object]], name: str) -> dict[str, object] | None:
        for row in rows:
            if str(row.get("name", "")).strip() == name:
                return row
        return None

    def _sync_sink_controls(self) -> None:
        row = self._row_by_name(self._sink_rows, self._selected_sink_name()) or {}
        vol = int(row.get("volume", 0) or 0)
        muted = bool(row.get("mute", False))
        self.sink_volume_label.setText(f"Output volume: {vol}%")
        self.sink_volume_slider.blockSignals(True)
        self.sink_volume_slider.setValue(max(0, min(150, vol)))
        self.sink_volume_slider.blockSignals(False)
        self.sink_mute_check.blockSignals(True)
        self.sink_mute_check.setChecked(muted)
        self.sink_mute_check.blockSignals(False)

    def _sync_source_controls(self) -> None:
        row = self._row_by_name(self._source_rows, self._selected_source_name()) or {}
        vol = int(row.get("volume", 0) or 0)
        muted = bool(row.get("mute", False))
        self.source_volume_label.setText(f"Input volume: {vol}%")
        self.source_volume_slider.blockSignals(True)
        self.source_volume_slider.setValue(max(0, min(150, vol)))
        self.source_volume_slider.blockSignals(False)
        self.source_mute_check.blockSignals(True)
        self.source_mute_check.setChecked(muted)
        self.source_mute_check.blockSignals(False)

    def _set_default_sink(self) -> None:
        sink = self._selected_sink_name()
        if sink and shutil.which("pactl"):
            subprocess.run(["pactl", "set-default-sink", sink], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        self.refresh_devices()

    def _set_default_source(self) -> None:
        source = self._selected_source_name()
        if source and shutil.which("pactl"):
            subprocess.run(["pactl", "set-default-source", source], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        self.refresh_devices()

    def _apply_sink_volume(self) -> None:
        sink = self._selected_sink_name()
        value = int(self.sink_volume_slider.value())
        self.sink_volume_label.setText(f"Output volume: {value}%")
        if sink and shutil.which("pactl"):
            subprocess.run(["pactl", "set-sink-volume", sink, f"{value}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    def _apply_source_volume(self) -> None:
        source = self._selected_source_name()
        value = int(self.source_volume_slider.value())
        self.source_volume_label.setText(f"Input volume: {value}%")
        if source and shutil.which("pactl"):
            subprocess.run(["pactl", "set-source-volume", source, f"{value}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    def _set_sink_mute(self) -> None:
        sink = self._selected_sink_name()
        state = "1" if self.sink_mute_check.isChecked() else "0"
        if sink and shutil.which("pactl"):
            subprocess.run(["pactl", "set-sink-mute", sink, state], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    def _set_source_mute(self) -> None:
        source = self._selected_source_name()
        state = "1" if self.source_mute_check.isChecked() else "0"
        if source and shutil.which("pactl"):
            subprocess.run(["pactl", "set-source-mute", source, state], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


class DockAppsScrollArea(QScrollArea):
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        angle_delta = event.angleDelta()
        horizontal_bar = self.horizontalScrollBar()
        if horizontal_bar is None:
            super().wheelEvent(event)
            return

        step = angle_delta.x() or angle_delta.y()
        if step:
            horizontal_bar.setValue(horizontal_bar.value() - step)
            event.accept()
            return
        super().wheelEvent(event)


class DockSettingsDialog(QDialog):
    def __init__(
        self,
        config: dict,
        theme,
        material_font: str,
        ui_font: str,
        display_font: str,
        on_transparency_preview=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.theme = theme
        self.material_font = material_font
        self.ui_font = ui_font
        self.display_font = display_font
        self.on_transparency_preview = on_transparency_preview
        self._accepted_config: dict | None = None
        self._width_value = int(config.get("dock", {}).get("width", 0) or 0)
        self._height_value = int(config.get("dock", {}).get("height", 74) or 74)
        self._transparency_value = int(config.get("dock", {}).get("transparency", 100) or 100)
        self.setWindowTitle("Dock Settings")
        self.resize(880, 620)
        self.setModal(True)
        self.setObjectName("dockSettingsDialog")
        self.setStyleSheet(
            f"""
            QDialog#dockSettingsDialog {{
                background: {rgba(theme.surface_container, 0.97)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 28px;
            }}
            QLabel {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QLabel#dockSettingsTitle {{
                color: {theme.on_surface};
                font-family: "{self.display_font}";
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#dockSettingsEyebrow {{
                color: {theme.text_muted};
                font-family: "{self.ui_font}";
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}
            QFrame#dockSettingsSurface {{
                background: transparent;
            }}
            QFrame#dockSettingsPanel {{
                background: {rgba(theme.surface, 0.62)};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 24px;
            }}
            QTextEdit, QListWidget, QComboBox, QSpinBox {{
                background: {rgba(theme.surface, 0.92)};
                border: 1px solid {rgba(theme.outline, 0.22)};
                border-radius: 18px;
                color: {theme.text};
                padding: 10px 12px;
                selection-background-color: {rgba(theme.primary, 0.22)};
                selection-color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QListWidget#dockSettingsSidebar {{
                background: {rgba(theme.surface, 0.68)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 22px;
                padding: 8px;
            }}
            QListWidget#dockSettingsSidebar::item {{
                border-radius: 16px;
                padding: 12px 14px;
                margin: 2px 0;
            }}
            QListWidget#dockSettingsSidebar::item:selected {{
                background: {rgba(theme.primary, 0.18)};
                color: {theme.text};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QComboBox QAbstractItemView {{
                background: {theme.surface_container};
                color: {theme.text};
                selection-background-color: {rgba(theme.primary, 0.22)};
                selection-color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.20)};
                outline: none;
            }}
            QCheckBox {{
                color: {theme.text};
                spacing: 10px;
                font-family: "{self.ui_font}";
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 1px solid {rgba(theme.outline, 0.36)};
                background: {rgba(theme.surface, 0.90)};
            }}
            QCheckBox::indicator:checked {{
                background: {theme.primary};
                border: 1px solid {rgba(theme.primary, 0.88)};
            }}
            QListWidget::item:selected {{
                background: {rgba(theme.primary, 0.18)};
                color: {theme.text};
                border-radius: 12px;
            }}
            QPushButton {{
                min-height: 42px;
                border-radius: 18px;
                padding: 0 16px;
                font-family: "{self.ui_font}";
                font-weight: 600;
            }}
            QPushButton#filledButton {{
                background: {theme.primary};
                border: none;
                color: {theme.active_text};
            }}
            QPushButton#filledButton:hover {{
                background: {theme.primary_container};
            }}
            QPushButton#filledButton:pressed {{
                background: {rgba(theme.primary, 0.80)};
            }}
            QPushButton#tonalButton {{
                background: {rgba(theme.primary, 0.14)};
                border: 1px solid {rgba(theme.primary, 0.16)};
                color: {theme.text};
            }}
            QPushButton#tonalButton:hover {{
                background: {rgba(theme.primary, 0.20)};
            }}
            QPushButton#tonalButton:pressed {{
                background: {rgba(theme.primary, 0.26)};
            }}
            QPushButton#textButton {{
                background: transparent;
                border: 1px solid {rgba(theme.outline, 0.16)};
                color: {theme.text_muted};
            }}
            QPushButton#textButton:hover {{
                background: {rgba(theme.on_surface, 0.06)};
                color: {theme.text};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {rgba(theme.outline, 0.20)};
                border-radius: 999px;
            }}
            QSlider::sub-page:horizontal {{
                background: {theme.primary};
                border-radius: 999px;
            }}
            QSlider::handle:horizontal {{
                background: {theme.primary};
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(14)

        eyebrow = QLabel("Dock")
        eyebrow.setObjectName("dockSettingsEyebrow")
        title = QLabel("Placement & behavior")
        title.setObjectName("dockSettingsTitle")
        subtitle = QLabel("Tune where the dock lives, how wide it feels, and which windows it should ignore.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {theme.text_muted}; font-family: \"{self.ui_font}\";")
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        surface = QFrame()
        surface.setObjectName("dockSettingsSurface")
        surface_layout = QHBoxLayout(surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(14)
        layout.addWidget(surface, 1)

        self.settings_sidebar = QListWidget()
        self.settings_sidebar.setObjectName("dockSettingsSidebar")
        self.settings_sidebar.setFixedWidth(180)
        self.settings_sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_sidebar.setSpacing(4)
        self.settings_sidebar.currentRowChanged.connect(self._switch_settings_page)
        surface_layout.addWidget(self.settings_sidebar)

        self.settings_stack = QStackedWidget()
        surface_layout.addWidget(self.settings_stack, 1)

        general_page = QFrame()
        general_page.setObjectName("dockSettingsPanel")
        general_layout = QVBoxLayout(general_page)
        general_layout.setContentsMargins(18, 18, 18, 18)
        general_layout.setSpacing(12)

        self.auto_hide = QCheckBox("Enable auto-hide")
        self.auto_hide.setChecked(bool(config.get("dock", {}).get("auto_hide", False)))
        general_layout.addWidget(self.auto_hide)

        self.icons_left = QCheckBox("Keep launcher and app icons on the left")
        self.icons_left.setChecked(bool(config.get("dock", {}).get("icons_left", False)))
        general_layout.addWidget(self.icons_left)

        position_label = QLabel("Dock position")
        self.position_combo = QComboBox()
        self.position_combo.addItem("Left", "left")
        self.position_combo.addItem("Center", "center")
        self.position_combo.addItem("Right", "right")
        position_index = self.position_combo.findData(config.get("dock", {}).get("position", "center"))
        self.position_combo.setCurrentIndex(max(0, position_index))
        general_layout.addWidget(position_label)
        general_layout.addWidget(self.position_combo)

        monitor_label = QLabel("Monitor target")
        self.monitor_combo = QComboBox()
        self._populate_monitor_combo()
        monitor_mode = str(config.get("dock", {}).get("monitor_mode", MONITOR_MODE_PRIMARY)).strip().lower()
        monitor_name = str(config.get("dock", {}).get("monitor_name", "")).strip()
        self._set_current_monitor_combo(monitor_mode, monitor_name)
        general_layout.addWidget(monitor_label)
        general_layout.addWidget(self.monitor_combo)

        width_label = QLabel("Dock width (0 = fit content)")
        width_row = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_unit = QComboBox()
        self.width_unit.addItem("Pixels", "px")
        self.width_unit.addItem("Percent", "%")
        index = self.width_unit.findData(config.get("dock", {}).get("width_unit", "px"))
        self.width_unit.setCurrentIndex(max(0, index))
        self.width_unit.currentIndexChanged.connect(self._sync_width_unit)
        self.width_spin.setKeyboardTracking(False)
        self.width_spin.setValue(self._width_value)
        self.width_spin.valueChanged.connect(self._remember_width)
        self._sync_width_unit()
        general_layout.addWidget(width_label)
        width_row.addWidget(self.width_spin, 1)
        width_row.addWidget(self.width_unit)
        general_layout.addLayout(width_row)

        height_label = QLabel("Dock app height")
        self.height_spin = QSpinBox()
        self.height_spin.setRange(64, 120)
        self.height_spin.setKeyboardTracking(False)
        self.height_spin.setValue(self._height_value)
        self.height_spin.valueChanged.connect(self._remember_height)
        self.height_spin.setSuffix(" px")
        general_layout.addWidget(height_label)
        general_layout.addWidget(self.height_spin)

        transparency_label = QLabel("Dock transparency")
        transparency_row = QHBoxLayout()
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_slider.setValue(self._transparency_value)
        self.transparency_slider.valueChanged.connect(self._preview_transparency)
        self.transparency_value_label = QLabel(f"{self._transparency_value}%")
        self.transparency_value_label.setMinimumWidth(44)
        transparency_row.addWidget(self.transparency_slider, 1)
        transparency_row.addWidget(self.transparency_value_label)
        general_layout.addWidget(transparency_label)
        general_layout.addLayout(transparency_row)
        general_layout.addStretch(1)

        blacklist_page = QFrame()
        blacklist_page.setObjectName("dockSettingsPanel")
        blacklist_layout = QVBoxLayout(blacklist_page)
        blacklist_layout.setContentsMargins(18, 18, 18, 18)
        blacklist_layout.setSpacing(12)

        wm_label = QLabel("Blacklisted WM_CLASS patterns")
        self.wm_edit = QTextEdit("\n".join(config.get("blacklist", {}).get("wm_class", [])))
        did_label = QLabel("Blacklisted desktop IDs")
        self.did_edit = QTextEdit("\n".join(config.get("blacklist", {}).get("desktop_id", [])))
        name_label = QLabel("Blacklisted window names")
        self.name_list = QListWidget()
        self.name_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.name_list.setMinimumHeight(180)
        for pattern in config.get("blacklist", {}).get("window_name", []):
            self.name_list.addItem(QListWidgetItem(pattern))
        blacklist_layout.addWidget(wm_label)
        blacklist_layout.addWidget(self.wm_edit, 1)
        blacklist_layout.addWidget(did_label)
        blacklist_layout.addWidget(self.did_edit, 1)
        blacklist_layout.addWidget(name_label)
        blacklist_layout.addWidget(self.name_list, 1)

        picker_page = QFrame()
        picker_page.setObjectName("dockSettingsPanel")
        picker_layout = QVBoxLayout(picker_page)
        picker_layout.setContentsMargins(18, 18, 18, 18)
        picker_layout.setSpacing(12)

        picker_label = QLabel("Current open window names. Select to blacklist.")
        self.open_windows_list = QListWidget()
        self.open_windows_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.open_windows_list.setMinimumHeight(260)
        self.add_names_button = QPushButton("Blacklist Selected Window Names")
        self.add_names_button.setObjectName("tonalButton")
        self.add_names_button.clicked.connect(self._add_selected_window_names)
        self.remove_names_button = QPushButton("Remove Selected Blacklist Names")
        self.remove_names_button.setObjectName("textButton")
        self.remove_names_button.clicked.connect(self._remove_selected_window_names)
        self.refresh_windows_button = QPushButton("Refresh Open Windows")
        self.refresh_windows_button.setObjectName("tonalButton")
        self.refresh_windows_button.clicked.connect(self._populate_open_windows)
        picker_actions = QHBoxLayout()
        picker_actions.addWidget(self.add_names_button, 1)
        picker_actions.addWidget(self.remove_names_button, 1)
        picker_actions.addWidget(self.refresh_windows_button, 1)
        picker_layout.addWidget(picker_label)
        picker_layout.addWidget(self.open_windows_list, 1)
        picker_layout.addLayout(picker_actions)
        self._populate_open_windows()

        self.settings_stack.addWidget(general_page)
        self.settings_stack.addWidget(blacklist_page)
        self.settings_stack.addWidget(picker_page)
        for label in ("Layout", "Blacklist", "Window picker"):
            self.settings_sidebar.addItem(QListWidgetItem(label))
        self.settings_sidebar.setCurrentRow(0)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText("Save dock settings")
            save_button.setObjectName("filledButton")
        if cancel_button is not None:
            cancel_button.setText("Cancel")
            cancel_button.setObjectName("textButton")
        buttons.accepted.connect(self._accept_with_commits)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        apply_antialias_font(self)

    def _build_config(self) -> dict:
        self.width_spin.interpretText()
        self.height_spin.interpretText()
        config = dict(self.config)
        config["dock"] = {
            "auto_hide": self.auto_hide.isChecked(),
            "width": int(self._width_value),
            "width_unit": self.width_unit.currentData(),
            "height": int(self._height_value),
            "icons_left": self.icons_left.isChecked(),
            "position": self.position_combo.currentData(),
            "transparency": int(self._transparency_value),
            "monitor_mode": self._selected_monitor_payload().get("mode", MONITOR_MODE_PRIMARY),
            "monitor_name": self._selected_monitor_payload().get("name", ""),
        }
        config["pinned"] = {"apps": list(self.config.get("pinned", {}).get("apps", []))}
        config["blacklist"] = {
            "wm_class": [line.strip() for line in self.wm_edit.toPlainText().splitlines() if line.strip()],
            "desktop_id": [line.strip() for line in self.did_edit.toPlainText().splitlines() if line.strip()],
            "window_name": [self.name_list.item(index).text().strip() for index in range(self.name_list.count()) if self.name_list.item(index).text().strip()],
        }
        return config

    def updated_config(self) -> dict:
        return dict(self._accepted_config or self._build_config())

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        screen = self.screen() or QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _switch_settings_page(self, index: int) -> None:
        if index < 0:
            return
        self.settings_stack.setCurrentIndex(index)

    def _monitor_entries(self) -> list[tuple[str, str, str]]:
        entries: list[tuple[str, str, str]] = [
            ("Primary monitor", MONITOR_MODE_PRIMARY, ""),
            ("Follow mouse", MONITOR_MODE_FOLLOW_MOUSE, ""),
        ]
        primary_output_name, _ = _active_output_names()
        seen: set[str] = set()
        for screen in QApplication.screens():
            name = screen.name().strip()
            if not name or name in seen:
                continue
            seen.add(name)
            label = f"{name} (primary)" if name == primary_output_name else name
            entries.append((label, MONITOR_MODE_NAMED, name))
        return entries

    def _populate_monitor_combo(self) -> None:
        self.monitor_combo.clear()
        for label, mode, name in self._monitor_entries():
            self.monitor_combo.addItem(label, {"mode": mode, "name": name})

    def _set_current_monitor_combo(self, monitor_mode: str, monitor_name: str) -> None:
        target_mode = monitor_mode if monitor_mode in {MONITOR_MODE_PRIMARY, MONITOR_MODE_FOLLOW_MOUSE, MONITOR_MODE_NAMED} else MONITOR_MODE_PRIMARY
        target_name = monitor_name.strip()
        selected_index = 0
        for index in range(self.monitor_combo.count()):
            payload = self.monitor_combo.itemData(index)
            if not isinstance(payload, dict):
                continue
            if payload.get("mode") == target_mode and payload.get("name") == target_name:
                selected_index = index
                break
        self.monitor_combo.setCurrentIndex(selected_index)

    def _selected_monitor_payload(self) -> dict[str, str]:
        payload = self.monitor_combo.currentData()
        if not isinstance(payload, dict):
            return {"mode": MONITOR_MODE_PRIMARY, "name": ""}
        mode = str(payload.get("mode", MONITOR_MODE_PRIMARY)).strip().lower()
        name = str(payload.get("name", "")).strip()
        if mode not in {MONITOR_MODE_PRIMARY, MONITOR_MODE_FOLLOW_MOUSE, MONITOR_MODE_NAMED}:
            mode = MONITOR_MODE_PRIMARY
        return {"mode": mode, "name": name}

    def _sync_width_unit(self) -> None:
        if self.width_unit.currentData() == "%":
            self.width_spin.setRange(0, 100)
            self.width_spin.setSuffix("%")
        else:
            self.width_spin.setRange(0, 2000)
            self.width_spin.setSuffix(" px")
        self._remember_width(self.width_spin.value())

    def _remember_width(self, value: int) -> None:
        self._width_value = int(value)

    def _remember_height(self, value: int) -> None:
        self._height_value = int(value)

    def _preview_transparency(self, value: int) -> None:
        self._transparency_value = int(value)
        self.transparency_value_label.setText(f"{self._transparency_value}%")
        if callable(self.on_transparency_preview):
            self.on_transparency_preview(self._transparency_value)

    def _accept_with_commits(self) -> None:
        self.width_spin.interpretText()
        self.height_spin.interpretText()
        self._remember_width(self.width_spin.value())
        self._remember_height(self.height_spin.value())
        self._accepted_config = self._build_config()
        self.accept()

    def _populate_open_windows(self) -> None:
        selected_titles = {item.text() for item in self.open_windows_list.selectedItems()}
        current_blacklist = {self.name_list.item(index).text().strip() for index in range(self.name_list.count()) if self.name_list.item(index).text().strip()}
        titles = sorted({window.title for window in get_open_windows() if window.title}, key=str.lower)
        self.open_windows_list.clear()
        for title in titles:
            item = QListWidgetItem(title)
            if title in current_blacklist or f"*{title}*" in current_blacklist:
                item.setToolTip("Already blacklisted")
            self.open_windows_list.addItem(item)
            if title in selected_titles:
                item.setSelected(True)

    def _add_selected_window_names(self) -> None:
        existing = [self.name_list.item(index).text().strip() for index in range(self.name_list.count()) if self.name_list.item(index).text().strip()]
        seen = set(existing)
        for item in self.open_windows_list.selectedItems():
            title = item.text().strip()
            pattern = title
            if pattern and pattern not in seen:
                self.name_list.addItem(QListWidgetItem(pattern))
                seen.add(pattern)
        self._populate_open_windows()

    def _remove_selected_window_names(self) -> None:
        for item in self.name_list.selectedItems():
            row = self.name_list.row(item)
            self.name_list.takeItem(row)
        self._populate_open_windows()


class CyberDock(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.loaded_fonts = load_app_fonts()
        self.material_font = detect_font(
            self.loaded_fonts.get("material_icons", ""),
            self.loaded_fonts.get("material_icons_outlined", ""),
            self.loaded_fonts.get("material_symbols_outlined", ""),
            self.loaded_fonts.get("material_symbols_rounded", ""),
            "Material Icons",
            "Material Icons Outlined",
            "Material Symbols Outlined",
            "Material Symbols Rounded",
        )
        self.ui_font = detect_font(theme_font_family("ui"), "Rubik", self.loaded_fonts.get("ui_sans", ""), "Inter", "Noto Sans", "DejaVu Sans", "Sans Serif")
        self.display_font = detect_font(theme_font_family("display"), "Rubik", self.ui_font)
        self.mono_font = detect_font(theme_font_family("mono"), "JetBrains Mono", "DejaVu Sans Mono", "Monospace")
        self._theme_font_signature = (
            theme_font_family("ui"),
            theme_font_family("display"),
            theme_font_family("mono"),
        )
        self._theme_refresh_restart_pending = False
        self.config = load_dock_config()
        self._last_items_json = ""
        self._geometry_animation: QPropertyAnimation | None = None
        self._panel_animation: QPropertyAnimation | None = None
        self._hidden = False
        self._transparency_preview: int | None = None

        self._build_window()
        self._build_ui()
        self._apply_shadow()
        self._apply_theme()
        self._start_timers()
        self._refresh_items()
        self._update_clock()
        self._update_volume()
        self._animate_in()

    def _build_window(self) -> None:
        self.setWindowTitle("CyberDock")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_X11NetWmWindowTypeDock, True)

    def _build_ui(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(18, 12, 18, 12)
        self.root_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)

        self.panel = QFrame()
        self.panel.setObjectName("dockPanel")
        self.root_layout.addWidget(self.panel, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)

        self.panel_layout = QHBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(16, 12, 16, 12)
        self.panel_layout.setSpacing(12)

        self.launcher_button = QPushButton(material_icon("apps"))
        self.launcher_button.setObjectName("dockUtilityButton")
        self.launcher_button.setFont(QFont(self.material_font, 20))
        self.launcher_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.launcher_button.setFixedSize(44, 44)
        self.launcher_button.clicked.connect(self._open_launcher)
        self.launcher_separator = self._separator()

        self.apps_scroll = DockAppsScrollArea()
        self.apps_scroll.setWidgetResizable(True)
        self.apps_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.apps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.apps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.apps_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.apps_scroll.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 0px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: transparent;
            }
            QScrollBar:vertical {
                width: 0px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: transparent;
            }
            """
        )
        self.apps_wrap = QWidget()
        self.apps_wrap.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.apps_layout = QHBoxLayout(self.apps_wrap)
        self.apps_layout.setContentsMargins(0, 0, 0, 2)
        self.apps_layout.setSpacing(8)
        self.apps_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.apps_scroll.setWidget(self.apps_wrap)
        self.apps_scroll.setMinimumWidth(1)
        self.middle_stretch = QWidget()
        self.middle_stretch.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.utility_separator = self._separator()

        self.clock_label = QLabel("--:--")
        self.clock_label.setObjectName("dockClock")
        self.clock_label.setFont(QFont(self.mono_font, 10))

        self.volume_button = VolumeButton(self.material_font, self.theme)
        self.volume_button.clicked.connect(self._toggle_volume_mute)
        self.volume_button.rightClicked.connect(self._open_audio_popup)
        self.audio_popup = AudioDevicePopup(self.theme, self.ui_font, self)

        self.settings_button = QPushButton(material_icon("settings"))
        self.settings_button.setObjectName("dockUtilityButton")
        self.settings_button.setFont(QFont(self.material_font, 18))
        self.settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.settings_button.setFixedSize(42, 42)
        self.settings_button.clicked.connect(self._open_settings)
        self._rebuild_panel_layout()
        self._apply_dock_preferences()

    def _separator(self) -> QFrame:
        sep = QFrame()
        sep.setFixedSize(1, 28)
        sep.setStyleSheet(f"background: {self.theme.separator};")
        return sep

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.panel.setGraphicsEffect(shadow)

    def _dock_app_height(self) -> int:
        return max(64, int(self.config.get("dock", {}).get("height", 74) or 74))

    def _dock_transparency(self) -> float:
        source = self._transparency_preview
        if source is None:
            source = int(self.config.get("dock", {}).get("transparency", 100) or 100)
        return max(0.0, min(1.0, source / 100.0))

    def _apply_dock_height(self) -> None:
        app_height = self._dock_app_height()
        scroll_height = app_height + 8
        self.apps_scroll.setMinimumHeight(scroll_height)
        self.apps_scroll.setMaximumHeight(scroll_height)
        self.apps_wrap.setMinimumHeight(app_height)
        self.apps_wrap.setMaximumHeight(app_height)

    def _clear_panel_layout(self) -> None:
        while self.panel_layout.count():
            item = self.panel_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _rebuild_panel_layout(self) -> None:
        self._clear_panel_layout()
        self.panel_layout.addWidget(self.launcher_button)
        self.panel_layout.addWidget(self.launcher_separator)
        self.panel_layout.addWidget(self.apps_scroll, 1)
        if self.config.get("dock", {}).get("icons_left", False):
            self.panel_layout.addWidget(self.middle_stretch, 1)
        self.panel_layout.addWidget(self.utility_separator)
        self.panel_layout.addWidget(self.clock_label)
        self.panel_layout.addWidget(self.volume_button)
        self.panel_layout.addWidget(self.settings_button)
        self._apply_dock_height()
        self._apply_theme()

    def _apply_dock_preferences(self) -> None:
        width = int(self.config.get("dock", {}).get("width", 0) or 0)
        width_unit = self.config.get("dock", {}).get("width_unit", "px")
        if width > 0:
            if width_unit == "%":
                screen = self._target_screen()
                if screen is not None:
                    available = screen.availableGeometry().width()
                    width = max(320, int(available * (width / 100.0)))
            self.panel.setMinimumWidth(0)
            self.panel.setMaximumWidth(width)
        else:
            self.panel.setMinimumWidth(0)
            self.panel.setMaximumWidth(16777215)
            self.panel.adjustSize()
        self._apply_dock_height()
        self.panel.updateGeometry()
        self.updateGeometry()

    def _dock_width_cap(self) -> int:
        width = int(self.config.get("dock", {}).get("width", 0) or 0)
        width_unit = self.config.get("dock", {}).get("width_unit", "px")
        if width <= 0:
            return 0
        if width_unit == "%":
            screen = self._target_screen()
            if screen is not None:
                available = screen.availableGeometry().width()
                return max(320, int(available * (width / 100.0)))
        return width

    def _update_apps_scroll_width(self, content_width: int) -> None:
        content_width = max(120, content_width)
        dock_cap = self._dock_width_cap()
        if dock_cap <= 0:
            self.apps_scroll.setMinimumWidth(content_width)
            self.apps_scroll.setMaximumWidth(16777215)
            return

        margins = self.panel_layout.contentsMargins()
        static_width = (
            margins.left()
            + margins.right()
            + self.launcher_button.sizeHint().width()
            + self.launcher_separator.width()
            + self.utility_separator.width()
            + self.clock_label.sizeHint().width()
            + self.volume_button.sizeHint().width()
            + self.settings_button.sizeHint().width()
        )
        static_spacing_count = 6
        available_for_apps = max(120, dock_cap - static_width - (self.panel_layout.spacing() * static_spacing_count))
        self.apps_scroll.setMinimumWidth(min(content_width, available_for_apps))
        self.apps_scroll.setMaximumWidth(available_for_apps)

    def _target_screen(self):
        dock_settings = self.config.get("dock", {})
        monitor_mode = str(dock_settings.get("monitor_mode", MONITOR_MODE_PRIMARY)).strip().lower()
        monitor_name = str(dock_settings.get("monitor_name", "")).strip()
        screen = preferred_dock_screen(monitor_mode, monitor_name)
        if screen is not None:
            return screen
        handle = self.windowHandle()
        if handle is not None and handle.screen() is not None:
            return handle.screen()
        screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is not None:
            return screen
        return QApplication.primaryScreen()

    def _start_timers(self) -> None:
        self.items_timer = QTimer(self)
        self.items_timer.timeout.connect(self._refresh_items)
        self.items_timer.start(1000)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

        self.volume_timer = QTimer(self)
        self.volume_timer.timeout.connect(self._update_volume)
        self.volume_timer.start(1500)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._hide_if_enabled)

    def _refresh_items(self) -> None:
        items = build_dock_items(self.config)
        raw = json.dumps([asdict(item) for item in items], sort_keys=True)
        if raw == self._last_items_json:
            return
        self._last_items_json = raw
        self._rebuild_apps(items)

    def _rebuild_apps(self, items: list[DockItem]) -> None:
        while self.apps_layout.count():
            item = self.apps_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for item in items:
            self.apps_layout.addWidget(
                DockAppButton(
                    item,
                    self._dock_app_height(),
                    self.theme,
                    self._toggle_pin_item,
                    self._run_desktop_action,
                )
            )
        self.apps_layout.activate()
        self._apply_dock_height()
        self.apps_wrap.adjustSize()
        self._update_apps_scroll_width(self.apps_wrap.sizeHint().width())
        self._apply_dock_preferences()
        self.adjustSize()
        self._update_position(animated=False)

    def _apply_theme(self) -> None:
        theme = self.theme
        transparency = self._dock_transparency()
        panel_bg = multiply_alpha(theme.panel_bg, transparency)
        panel_border = multiply_alpha(theme.panel_border, transparency)
        self.panel.setStyleSheet(
            f"""
            QFrame#dockPanel {{
                background: {panel_bg};
                border: 1px solid {panel_border};
                border-radius: 30px;
            }}
            QLabel {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            #dockUtilityButton {{
                background: transparent;
                border: none;
                border-radius: 999px;
                color: {theme.icon};
                font-family: "{self.material_font}";
            }}
            #dockUtilityButton:hover {{
                background: {theme.hover_bg};
            }}
            #dockClock {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 600;
                padding: 0 8px;
            }}
            """
        )
        self.launcher_separator.setStyleSheet(f"background: {theme.separator};")
        self.utility_separator.setStyleSheet(f"background: {theme.separator};")
        self.volume_button.apply_theme(theme)
        if hasattr(self, "audio_popup") and isinstance(self.audio_popup, AudioDevicePopup):
            self.audio_popup.apply_theme(theme)
        for index in range(self.apps_layout.count()):
            widget = self.apps_layout.itemAt(index).widget()
            if isinstance(widget, DockAppButton):
                widget.apply_theme(theme)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        new_signature = (
            theme_font_family("ui"),
            theme_font_family("display"),
            theme_font_family("mono"),
        )
        if new_signature != getattr(self, "_theme_font_signature", ("", "", "")):
            self._theme_font_signature = new_signature
            self._restart_for_theme_refresh()
            return
        self._apply_theme()

    def _restart_for_theme_refresh(self) -> None:
        if getattr(self, "_theme_refresh_restart_pending", False):
            return
        self._theme_refresh_restart_pending = True
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        QTimer.singleShot(0, self.close)

    def _update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%H:%M"))

    def _update_volume(self) -> None:
        vol = int(run_cmd([str(VOLUME_SCRIPT), "vol"]) or "0")
        muted = run_cmd([str(VOLUME_SCRIPT), "muted"]).strip().lower() == "yes"
        if muted or vol == 0:
            icon = "volume_off"
        elif vol <= 35:
            icon = "volume_mute"
        elif vol <= 70:
            icon = "volume_down"
        else:
            icon = "volume_up"
        self.volume_button.setText(material_icon(icon))
        self.volume_button.setToolTip(f"Volume {vol}%")

    def _toggle_volume_mute(self) -> None:
        if I3_VOLUME_BIN.exists():
            run_bg([str(I3_VOLUME_BIN), "-n", "-N", "volnoti", "mute"])
            return
        run_bg([str(VOLUME_SCRIPT), "toggle-muted"])

    def _open_audio_popup(self, global_pos) -> None:
        self.audio_popup.popup_at(global_pos)

    def _open_launcher(self) -> None:
        if LAUNCHER_APP.exists():
            command = entry_command(LAUNCHER_APP)
            if command:
                run_bg(command)

    def _open_settings(self) -> None:
        dialog = DockSettingsDialog(
            self.config,
            self.theme,
            self.material_font,
            self.ui_font,
            self.display_font,
            self._preview_transparency,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._transparency_preview = None
            self._apply_theme()
            return
        self.config = dialog.updated_config()
        self._transparency_preview = None
        save_dock_config(self.config)
        self._last_items_json = ""
        self._rebuild_panel_layout()
        self._apply_dock_preferences()
        self._refresh_items()
        self._update_position(animated=False)

    def _toggle_pin_item(self, item: DockItem) -> None:
        desktop_id = item.desktop_id
        if not desktop_id:
            return
        pinned = list((self.config.get("pinned", {}) or {}).get("apps", []) or [])
        if desktop_id in pinned:
            pinned = [entry for entry in pinned if entry != desktop_id]
        else:
            pinned.append(desktop_id)
        self.config["pinned"] = {"apps": pinned}
        save_dock_config(self.config)
        self._last_items_json = ""
        self._refresh_items()

    def _run_desktop_action(self, item: DockItem, action: DesktopAction) -> None:
        command = desktop_exec_to_command(action.exec)
        if not command:
            return
        run_bg(command)

    def _preview_transparency(self, value: int) -> None:
        self._transparency_preview = int(value)
        self._apply_theme()

    def _shown_geometry(self) -> QRect:
        self.root_layout.activate()
        self.adjustSize()
        size = self.sizeHint()
        width = max(self.width(), size.width())
        height = max(self.height(), size.height())
        screen = self._target_screen()
        if screen is None:
            return QRect(0, 0, width, height)
        rect = screen.availableGeometry()
        position = self.config.get("dock", {}).get("position", "center")
        if position == "left":
            x = rect.x() + 16
        elif position == "right":
            x = rect.x() + rect.width() - width - 16
        else:
            x = rect.x() + (rect.width() - width) // 2
        y = rect.y() + rect.height() - height - 16
        return QRect(x, y, width, height)

    def _hidden_geometry(self) -> QRect:
        shown = self._shown_geometry()
        return QRect(shown.x(), shown.y() + self.height() - 12, shown.width(), shown.height())

    def _update_position(self, animated: bool) -> None:
        target = self._hidden_geometry() if self._hidden else self._shown_geometry()
        if not animated:
            self.setGeometry(target)
            if self.isVisible():
                self._sync_i3_geometry(target)
            return
        if self._geometry_animation is not None:
            self._geometry_animation.stop()
        self._geometry_animation = QPropertyAnimation(self, b"geometry", self)
        self._geometry_animation.setDuration(180)
        self._geometry_animation.setStartValue(self.geometry())
        self._geometry_animation.setEndValue(target)
        self._geometry_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._geometry_animation.finished.connect(lambda: self._sync_i3_geometry(self.geometry()))
        self._geometry_animation.start()

    def _sync_i3_geometry(self, rect: QRect) -> None:
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="CyberDock"]',
                    (
                        "floating enable, sticky enable, "
                        f"move position {rect.x()} px {rect.y()} px, "
                        f"resize set {rect.width()} px {rect.height()} px"
                    ),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._panel_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._panel_animation.setDuration(180)
        self._panel_animation.setStartValue(0.0)
        self._panel_animation.setEndValue(1.0)
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.start()
        self._update_position(animated=False)

    def _hide_if_enabled(self) -> None:
        if not self.config.get("dock", {}).get("auto_hide", False):
            return
        self._hidden = True
        self._update_position(animated=True)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self.hide_timer.stop()
        if self.config.get("dock", {}).get("auto_hide", False):
            self._hidden = False
            self._update_position(animated=True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        if self.config.get("dock", {}).get("auto_hide", False):
            self.hide_timer.start(600)
        super().leaveEvent(event)

    def show(self) -> None:
        super().show()
        QTimer.singleShot(0, lambda: self._update_position(animated=False))
        QTimer.singleShot(120, self._apply_i3_window_rules)
        QTimer.singleShot(240, lambda: self._update_position(animated=False))

    def _apply_i3_window_rules(self) -> None:
        self._sync_i3_geometry(self._hidden_geometry() if self._hidden else self._shown_geometry())


def main() -> int:
    parser = argparse.ArgumentParser(description="CyberDock")
    parser.add_argument("command", nargs="?", choices=["run", "activate", "new", "activate-wm"], default="run")
    parser.add_argument("target", nargs="?")
    parser.add_argument("--ui", default="", help="Unused compatibility argument")
    args = parser.parse_args()

    if args.command == "activate" and args.target:
        return cmd_activate(args.target)
    if args.command == "new" and args.target:
        return cmd_new(args.target)
    if args.command == "activate-wm" and args.target:
        return cmd_activate_wm(args.target)

    app = QApplication(sys.argv)
    runtime_lock = acquire_runtime_lock()
    if runtime_lock is None:
        return 0
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    app.setPalette(palette)
    dock = CyberDock()
    dock.show()
    exit_code = app.exec()
    runtime_lock.unlock()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
