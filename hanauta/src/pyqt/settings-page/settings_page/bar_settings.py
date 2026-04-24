from __future__ import annotations


DEFAULT_BAR_SETTINGS = {
    "launcher_offset": 0,
    "workspace_offset": 0,
    "workspace_count": 5,
    "show_workspace_label": False,
    "datetime_offset": 0,
    "media_offset": 0,
    "status_offset": 0,
    "tray_offset": 0,
    "status_icon_limit": 14,
    "bar_height": 45,
    "chip_radius": 0,
    "tray_tint_with_matugen": True,
    "use_color_widget_icons": False,
    "debug_tooltips": False,
    "merge_all_chips": False,
    "full_bar_radius": 18,
    "orientation_mode": "horizontal_top",
    "monitor_mode": "primary",
    "monitor_name": "",
    "service_icon_order": [],
    "polybar_widgets": [],
}


BAR_SERVICE_ICON_META: dict[str, tuple[str, str]] = {
    "christian_widget": ("Christian Widget", "church"),
    "home_assistant": ("Home Assistant", "home"),
    "reminders_widget": ("Reminders", "notifications"),
    "pomodoro_widget": ("Pomodoro", "timer"),
    "rss_widget": ("RSS", "public"),
    "obs_widget": ("OBS", "videocam"),
    "crypto_widget": ("Crypto", "show_chart"),
    "game_mode": ("Game Mode", "sports_esports"),
    "cap_alerts": ("Weather Alerts", "warning"),
    "study_tracker_widget": ("Study Tracker", "school"),
}


BAR_SERVICE_SWITCH_ATTRS: dict[str, str] = {
    "home_assistant": "ha_bar_switch",
    "reminders_widget": "reminders_bar_switch",
    "pomodoro_widget": "pomodoro_bar_switch",
    "rss_widget": "rss_bar_switch",
    "obs_widget": "obs_bar_switch",
    "crypto_widget": "crypto_bar_switch",
    "game_mode": "game_mode_bar_switch",
    "cap_alerts": "cap_alerts_bar_switch",
    "study_tracker_widget": "study_tracker_bar_switch",
}


SERVICE_DISPLAY_SWITCH_NON_BAR_KEYS = {
    "home_assistant",
    "vpn_control",
    "calendar_widget",
    "reminders_widget",
    "pomodoro_widget",
    "obs_widget",
    "crypto_widget",
    "vps_widget",
    "desktop_clock_widget",
    "game_mode",
    "cap_alerts",
    "study_tracker_widget",
}


def merged_bar_settings(payload: object) -> dict[str, object]:
    current = payload if isinstance(payload, dict) else {}
    merged = dict(DEFAULT_BAR_SETTINGS)
    offset_keys = {
        "launcher_offset",
        "workspace_offset",
        "datetime_offset",
        "media_offset",
        "status_offset",
        "tray_offset",
    }
    radius_keys = {"chip_radius", "full_bar_radius"}
    for key, default in DEFAULT_BAR_SETTINGS.items():
        if isinstance(default, str):
            merged[key] = (
                str(current.get(key, default)).strip()
                if isinstance(current, dict)
                else str(default)
            )
            continue
        if isinstance(default, bool):
            merged[key] = (
                bool(current.get(key, default))
                if isinstance(current, dict)
                else bool(default)
            )
            continue
        if isinstance(default, list):
            if isinstance(current, dict) and isinstance(current.get(key), list):
                merged[key] = list(current.get(key, []))
            else:
                merged[key] = list(default)
            continue
        try:
            merged[key] = (
                int(current.get(key, default))
                if isinstance(current, dict)
                else int(default)
            )
        except Exception:
            merged[key] = int(default)
        if key in offset_keys:
            merged[key] = max(-8, min(8, int(merged[key])))
        elif key == "workspace_count":
            merged[key] = max(1, min(10, int(merged[key])))
        elif key == "status_icon_limit":
            merged[key] = max(4, min(48, int(merged[key])))
        elif key == "bar_height":
            merged[key] = max(32, min(72, int(merged[key])))
        elif key in radius_keys:
            merged[key] = max(0, min(32, int(merged[key])))
    monitor_mode = str(merged.get("monitor_mode", "primary")).strip().lower()
    merged["monitor_mode"] = (
        monitor_mode
        if monitor_mode in {"primary", "follow_mouse", "named"}
        else "primary"
    )
    orientation_mode = str(merged.get("orientation_mode", "horizontal_top")).strip().lower()
    merged["orientation_mode"] = (
        orientation_mode
        if orientation_mode in {"horizontal_top", "vertical_left", "vertical_right"}
        else "horizontal_top"
    )
    merged["monitor_name"] = str(merged.get("monitor_name", "")).strip()
    if "polybar_widgets" in current and isinstance(current["polybar_widgets"], list):
        merged["polybar_widgets"] = list(current["polybar_widgets"])
    else:
        merged["polybar_widgets"] = []
    return merged

