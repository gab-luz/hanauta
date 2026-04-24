try:
    import tomllib
except Exception:
    tomllib = None

from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
DOCK_CONFIG = APP_DIR / "pyqt" / "dock" / "dock.toml"


def load_dock_settings_state() -> dict:
    defaults = {
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
            "monitor_mode": "primary",
            "monitor_name": "",
        },
    }
    if not DOCK_CONFIG.exists() or tomllib is None:
        return defaults
    try:
        config = tomllib.loads(DOCK_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    dock_cfg = dict(config.get("dock", {}))
    for key, value in defaults["dock"].items():
        dock_cfg.setdefault(key, value)
    monitor_mode = str(dock_cfg.get("monitor_mode", "primary")).strip().lower()
    dock_cfg["monitor_mode"] = (
        monitor_mode
        if monitor_mode in {"primary", "follow_mouse", "named"}
        else "primary"
    )
    dock_cfg["monitor_name"] = str(dock_cfg.get("monitor_name", "")).strip()
    config["dock"] = dock_cfg
    config.setdefault("pinned", {"apps": []})
    config.setdefault(
        "blacklist", {"wm_class": [], "desktop_id": [], "window_name": []}
    )
    blacklist_cfg = dict(config.get("blacklist", {}))
    blacklist_cfg.setdefault("wm_class", [])
    blacklist_cfg.setdefault("desktop_id", [])
    blacklist_cfg.setdefault("window_name", [])
    config["blacklist"] = blacklist_cfg
    return config


def save_dock_settings_state(config: dict) -> None:
    def write_list(values: list[str]) -> str:
        if not values:
            return "[]"
        items = ",\n".join(f'  "{value}"' for value in values)
        return f"[\n{items}\n]"

    dock = dict(config.get("dock", {}))
    dock.setdefault("monitor_mode", "primary")
    dock.setdefault("monitor_name", "")
    pinned = config.get("pinned", {})
    blacklist = config.get("blacklist", {})
    body = (
        "[dock]\n"
        f"auto_hide = {'true' if dock.get('auto_hide') else 'false'}\n"
        f"width = {int(dock.get('width', 0) or 0)}\n"
        f'width_unit = "{dock.get("width_unit", "px")}"\n'
        f"height = {int(dock.get('height', 64) or 64)}\n"
        f"icons_left = {'true' if dock.get('icons_left') else 'false'}\n"
        f'position = "{dock.get("position", "center")}"\n'
        f"transparency = {int(dock.get('transparency', 60) or 60)}\n"
        f'monitor_mode = "{dock.get("monitor_mode", "primary")}"\n'
        f'monitor_name = "{str(dock.get("monitor_name", "")).strip()}"\n\n'
        "[pinned]\n"
        f"apps = {write_list(list(pinned.get('apps', [])))}\n\n"
        "[blacklist]\n"
        f"wm_class = {write_list(list(blacklist.get('wm_class', [])))}\n\n"
        f"desktop_id = {write_list(list(blacklist.get('desktop_id', [])))}\n\n"
        f"window_name = {write_list(list(blacklist.get('window_name', [])))}\n"
    )
    DOCK_CONFIG.write_text(body, encoding="utf-8")