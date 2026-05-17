from __future__ import annotations


DEFAULT_SERVICE_SETTINGS = {
    "kdeconnect": {
        "enabled": True,
        "show_in_notification_center": True,
        "low_battery_fullscreen_notification": False,
        "low_battery_threshold": 20,
    },
    "home_assistant": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "vpn_control": {
        "enabled": False,
        "show_in_notification_center": False,
        "reconnect_on_login": False,
        "preferred_interface": "",
        "split_tunnel_apps": [],
    },
    "christian_widget": {
        "enabled": False,
        "show_in_notification_center": False,
        "show_in_bar": False,
        "next_devotion_notifications": False,
        "hourly_verse_notifications": False,
    },
    "health_widget": {
        "enabled": False,
        "show_in_notification_center": False,
        "show_in_bar": True,
        "water_reminder_notifications": False,
        "stand_up_reminder_notifications": False,
        "movement_reminder_notifications": False,
    },
    "calendar_widget": {
        "enabled": True,
        "show_in_notification_center": False,
    },
    "reminders_widget": {
        "enabled": False,
        "show_in_notification_center": False,
        "show_in_bar": False,
    },
    "pomodoro_widget": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "cap_alerts": {
        "enabled": True,
        "show_in_notification_center": False,
        "show_in_bar": True,
        "test_mode": False,
    },
    "rss_widget": {
        "enabled": False,
        "show_in_notification_center": False,
        "show_in_bar": False,
    },
    "obs_widget": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "crypto_widget": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "vps_widget": {
        "enabled": False,
        "show_in_notification_center": True,
    },
    "desktop_clock_widget": {
        "enabled": False,
        "show_in_notification_center": True,
    },
    "game_mode": {
        "enabled": False,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "virtualization": {
        "enabled": False,
        "show_in_notification_center": False,
        "virtualbox_manager_to_next_workspace": True,
        "virtualbox_guest_fullscreen": False,
        "virtualbox_guest_keep_current_workspace": True,
        "emulator_prompt_once_per_ide": True,
        "emulator_move_target": "next_on_output",
        "ide_actions": {
            "vscode": "ask",
            "vscodium": "ask",
            "android_studio": "ask",
            "jetbrains": "ask",
        },
    },
    "study_tracker_widget": {
        "enabled": False,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "mail": {
        "enabled": True,
        "show_in_notification_center": False,
    },
    "disk_space": {
        "enabled": True,
        "show_in_notification_center": False,
        "min_free_gb": 6,
    },
}


def merged_service_settings(payload: object) -> dict[str, dict[str, bool]]:
    services = payload if isinstance(payload, dict) else {}
    merged: dict[str, dict[str, bool]] = {}
    for key, defaults in DEFAULT_SERVICE_SETTINGS.items():
        current = services.get(key, {}) if isinstance(services, dict) else {}
        if not isinstance(current, dict):
            current = {}
        merged[key] = {"enabled": bool(current.get("enabled", defaults["enabled"]))}
        merged[key]["show_in_notification_center"] = bool(
            current.get(
                "show_in_notification_center",
                defaults["show_in_notification_center"],
            )
        )
        if key == "kdeconnect":
            try:
                merged[key]["low_battery_threshold"] = max(
                    1,
                    min(
                        100,
                        int(
                            current.get(
                                "low_battery_threshold",
                                defaults.get("low_battery_threshold", 20),
                            )
                        ),
                    ),
                )
            except Exception:
                merged[key]["low_battery_threshold"] = int(
                    defaults.get("low_battery_threshold", 20)
                )
            merged[key]["low_battery_fullscreen_notification"] = bool(
                current.get(
                    "low_battery_fullscreen_notification",
                    defaults.get("low_battery_fullscreen_notification", False),
                )
            )
        if key == "christian_widget":
            merged[key]["show_in_bar"] = bool(
                current.get(
                    "show_in_bar",
                    current.get(
                        "show_in_notification_center",
                        defaults.get("show_in_bar", False),
                    ),
                )
            )
            merged[key]["next_devotion_notifications"] = bool(
                current.get(
                    "next_devotion_notifications",
                    defaults.get("next_devotion_notifications", False),
                )
            )
            merged[key]["hourly_verse_notifications"] = bool(
                current.get(
                    "hourly_verse_notifications",
                    defaults.get("hourly_verse_notifications", False),
                )
            )
        elif key == "health_widget":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", True))
            )
            merged[key]["water_reminder_notifications"] = bool(
                current.get(
                    "water_reminder_notifications",
                    defaults.get("water_reminder_notifications", False),
                )
            )
            merged[key]["stand_up_reminder_notifications"] = bool(
                current.get(
                    "stand_up_reminder_notifications",
                    defaults.get("stand_up_reminder_notifications", False),
                )
            )
            merged[key]["movement_reminder_notifications"] = bool(
                current.get(
                    "movement_reminder_notifications",
                    defaults.get("movement_reminder_notifications", False),
                )
            )
        elif key == "vpn_control":
            merged[key]["reconnect_on_login"] = bool(
                current.get(
                    "reconnect_on_login", defaults.get("reconnect_on_login", False)
                )
            )
            merged[key]["preferred_interface"] = str(
                current.get(
                    "preferred_interface", defaults.get("preferred_interface", "")
                )
            ).strip()
            apps = current.get(
                "split_tunnel_apps", defaults.get("split_tunnel_apps", [])
            )
            merged[key]["split_tunnel_apps"] = apps if isinstance(apps, list) else []
        elif key == "home_assistant":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
        elif key == "disk_space":
            try:
                merged[key]["min_free_gb"] = max(
                    1,
                    min(
                        1024,
                        int(
                            current.get(
                                "min_free_gb",
                                defaults.get("min_free_gb", 6),
                            )
                            or defaults.get("min_free_gb", 6)
                        ),
                    ),
                )
            except Exception:
                merged[key]["min_free_gb"] = int(defaults.get("min_free_gb", 6))
        elif key == "reminders_widget":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
        elif key == "pomodoro_widget":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
        elif key in {
            "rss_widget",
            "obs_widget",
            "crypto_widget",
            "game_mode",
            "cap_alerts",
            "study_tracker_widget",
        }:
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
        elif key == "virtualization":
            merged[key]["virtualbox_manager_to_next_workspace"] = bool(
                current.get(
                    "virtualbox_manager_to_next_workspace",
                    defaults.get("virtualbox_manager_to_next_workspace", True),
                )
            )
            merged[key]["virtualbox_guest_fullscreen"] = bool(
                current.get(
                    "virtualbox_guest_fullscreen",
                    defaults.get("virtualbox_guest_fullscreen", False),
                )
            )
            merged[key]["virtualbox_guest_keep_current_workspace"] = bool(
                current.get(
                    "virtualbox_guest_keep_current_workspace",
                    defaults.get("virtualbox_guest_keep_current_workspace", True),
                )
            )
            merged[key]["emulator_prompt_once_per_ide"] = bool(
                current.get(
                    "emulator_prompt_once_per_ide",
                    defaults.get("emulator_prompt_once_per_ide", True),
                )
            )
            move_target = (
                str(
                    current.get(
                        "emulator_move_target",
                        defaults.get("emulator_move_target", "next_on_output"),
                    )
                )
                .strip()
                .lower()
            )
            if move_target not in {"next", "next_on_output"}:
                move_target = "next_on_output"
            merged[key]["emulator_move_target"] = move_target
            actions = current.get("ide_actions", defaults.get("ide_actions", {}))
            if not isinstance(actions, dict):
                actions = {}
            ide_actions: dict[str, str] = {}
            for ide_key in ("vscode", "vscodium", "android_studio", "jetbrains"):
                value = (
                    str(
                        actions.get(
                            ide_key, defaults.get("ide_actions", {}).get(ide_key, "ask")
                        )
                    )
                    .strip()
                    .lower()
                )
                if value not in {"ask", "split", "move_workspace"}:
                    value = "ask"
                ide_actions[ide_key] = value
            merged[key]["ide_actions"] = ide_actions
    return merged
