import json
from pathlib import Path

from settings_page.theme_data import THEME_CHOICES, CUSTOM_THEME_KEYS

APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]

from settings_page.settings_store import SETTINGS_FILE, save_settings_state, _atomic_write_json_file
from settings_page.bar_settings import DEFAULT_BAR_SETTINGS, merged_bar_settings
from settings_page.service_settings import merged_service_settings

WALLS_DIR = ROOT / "hanauta" / "walls"
CURRENT_WALLPAPER = Path.home() / ".wallpapers" / "wallpaper.png"
DEFAULT_PLUGIN_INSTALL_DIR = ROOT / "hanauta" / "plugins"
DEFAULT_WIFI_PLUGIN_ID = "wifi-control"
DEFAULT_WIFI_PLUGIN_REPO = "https://github.com/gab-luz/hanauta-plugin-wifi-control"


def _default_wifi_plugin_entry() -> dict[str, object]:
    return {
        "id": DEFAULT_WIFI_PLUGIN_ID,
        "name": "Wi-Fi Control",
        "repo": DEFAULT_WIFI_PLUGIN_REPO,
        "branch": "main",
        "install_path": str(
            DEFAULT_PLUGIN_INSTALL_DIR / "hanauta-plugin-wifi-control"
        ),
    }


def _ensure_default_installed_plugins(rows: object) -> list[dict[str, object]]:
    normalized = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    found_wifi = False
    for row in normalized:
        if str(row.get("id", "")).strip() == DEFAULT_WIFI_PLUGIN_ID:
            found_wifi = True
            row.setdefault("name", "Wi-Fi Control")
            row.setdefault("repo", DEFAULT_WIFI_PLUGIN_REPO)
            row.setdefault("branch", "main")
            row.setdefault(
                "install_path",
                str(DEFAULT_PLUGIN_INSTALL_DIR / "hanauta-plugin-wifi-control"),
            )
            break
    if not found_wifi:
        normalized.append(_default_wifi_plugin_entry())
    return normalized


def load_settings_state() -> dict:
    default = {
        "profile": {
            "first_name": "",
            "nickname": "",
            "pronunciations": [],
        },
        "appearance": {
            "accent": "orchid",
            "wallpaper_mode": "picture",
            "wallpaper_path": str(CURRENT_WALLPAPER),
            "wallpaper_fit_modes": {},
            "slideshow_folder": str(WALLS_DIR),
            "slideshow_interval": 30,
            "slideshow_enabled": False,
            "theme_mode": "dark",
            "theme_choice": "dark",
            "custom_theme_id": "retrowave",
            "transparency": True,
            "notification_center_panel_opacity": 84,
            "notification_center_card_opacity": 92,
            "notification_toast_max_width": 356,
            "notification_toast_max_height": 280,
            "wallpaper_change_notifications_enabled": False,
            "use_matugen_palette": False,
            "matugen_notifications_enabled": False,
        },
        "home_assistant": {
            "url": "",
            "token": "",
            "pinned_entities": [],
        },
        "ntfy": {
            "enabled": False,
            "show_in_bar": False,
            "server_url": "https://ntfy.sh",
            "topic": "",
            "token": "",
            "username": "",
            "password": "",
            "auth_mode": "token",
            "topics": [],
            "all_topics": False,
            "hide_notification_content": False,
        },
        "weather": {
            "enabled": False,
            "name": "",
            "admin1": "",
            "country": "",
            "latitude": 0.0,
            "longitude": 0.0,
            "timezone": "auto",
            "notify_climate_changes": True,
            "notify_rain_soon": True,
            "notify_sunset_soon": True,
            "notify_temperature_drop_soon": True,
            "notify_temperature_rise_soon": True,
            "notify_freezing_risk_tonight": True,
            "notify_high_uv_window": True,
            "notify_strong_wind_incoming": True,
            "notify_thunderstorm_likelihood": True,
            "notify_snow_ice_start": True,
            "notify_fog_low_visibility": True,
            "notify_air_quality_worsening": True,
            "notify_pollen_high": True,
            "notify_morning_commute_rain": True,
            "notify_evening_commute_risk": True,
            "notify_feels_like_extreme": True,
            "notify_sunrise_soon": True,
            "notify_dry_window_ending": True,
            "notify_lead_minutes": 30,
            "commute_morning_start": "07:00",
            "commute_morning_end": "09:00",
            "commute_evening_start": "17:00",
            "commute_evening_end": "19:00",
        },
        "calendar": {
            "show_week_numbers": False,
            "show_other_month_days": True,
            "first_day_of_week": "monday",
            "selected_calendar_id": "",
            "calendars": [],
            "selected_remote_calendar_url": "",
            "selected_contact_id": "",
            "contacts": [],
            "caldav_url": "",
            "caldav_username": "",
            "caldav_password": "",
            "last_sync_status": "",
            "connected": False,
        },
        "reminders": {
            "default_lead_minutes": 20,
            "default_intensity": "discrete",
            "tracked_events": [],
            "tea_label": "Tea",
            "tea_minutes": 5,
        },
        "pomodoro": {
            "work_minutes": 25,
            "short_break_minutes": 5,
            "long_break_minutes": 15,
            "long_break_every": 4,
            "auto_start_breaks": False,
            "auto_start_focus": False,
        },
        "rss": {
            "feeds": [],
            "feed_urls": "",
            "opml_source": "",
            "username": "",
            "password": "",
            "item_limit": 10,
            "check_interval_minutes": 15,
            "notify_new_items": True,
            "play_notification_sound": False,
            "show_feed_name": True,
            "open_in_browser": True,
            "show_images": True,
            "sort_mode": "newest",
            "max_per_feed": 5,
            "view_mode": "expanded",
        },
        "obs": {
            "host": "127.0.0.1",
            "port": 4455,
            "password": "",
            "auto_connect": False,
            "show_debug_tooltips": False,
        },
        "crypto": {
            "api_provider": "coingecko",
            "api_key": "",
            "tracked_coins": "bitcoin,ethereum",
            "vs_currency": "usd",
            "check_interval_minutes": 15,
            "chart_days": 7,
            "notify_price_moves": True,
            "price_up_percent": 3.0,
            "price_down_percent": 3.0,
        },
        "vps": {
            "host": "",
            "port": 22,
            "username": "",
            "identity_file": "",
            "app_service": "",
            "health_command": "uptime && df -h /",
            "update_command": "sudo apt update && sudo apt upgrade -y",
        },
        "clock": {
            "size": 320,
            "show_seconds": True,
            "digital_line_spacing": 14,
            "position_x": -1,
            "position_y": -1,
        },
        "autolock": {
            "enabled": True,
            "timeout_minutes": 2,
        },
        "lockscreen": {
            "blur_screenshot": False,
            "pause_media_on_lock": True,
            "use_slow_fade": True,
            "prefer_i3lock_color": True,
            "show_clock": True,
            "show_indicator": True,
            "pass_media_keys": True,
            "pass_volume_keys": True,
            "refresh_rate": 1,
            "ring_radius": 28,
            "ring_width": 6,
            "time_format": "%H:%M",
            "date_format": "%A, %d %B %Y",
            "greeter_text": "Hanauta locked • Type your password to unlock",
            "verifying_text": "Verifying...",
            "wrong_text": "Wrong password",
        },
        "audio": {
            "default_sink": "",
            "default_source": "",
            "alert_sounds_enabled": True,
            "mute_behavior": "leave_as_is",
            "route_new_apps_to_default_sink": True,
        },
        "notifications": {
            "history_limit": 150,
            "urgency_policy": "normal",
            "pause_while_sharing": True,
            "per_app_rules_enabled": True,
            "default_duration_ms": 10000,
            "lock_osd_enabled": True,
            "lock_osd_position": "bottom_center",
        },
        "input": {
            "keyboard_layout": "us",
            "repeat_delay_ms": 300,
            "repeat_rate": 30,
            "tap_to_click": True,
            "natural_scroll": False,
            "mouse_accel": 0,
        },
        "startup": {
            "launch_bar": True,
            "launch_dock": True,
            "restore_wallpaper": True,
            "restore_displays": True,
            "restore_vpn": True,
            "startup_delay_seconds": 0,
            "restart_hooks_enabled": True,
            "watchdog_enabled": False,
            "startup_apps": [],
        },
        "privacy": {
            "lock_on_suspend": True,
            "hide_notification_content_global": False,
            "pause_notifications_while_sharing": True,
            "screenshot_guard_enabled": False,
            "screen_share_guard_enabled": True,
        },
        "networking": {
            "preferred_wifi_interface": "",
            "preferred_wireguard_interface": "",
            "wifi_autoconnect": True,
            "vpn_reconnect_on_login": False,
            "split_tunnel_apps": [],
        },
        "storage": {
            "wallpaper_cache_cleanup_days": 30,
            "log_retention_days": 14,
            "clean_temp_state_on_startup": False,
        },
        "health": {
            "provider": "manual",
            "step_goal": 10000,
            "water_goal_ml": 2000,
            "sync_interval_minutes": 30,
            "fitbit_client_id": "",
            "fitbit_client_secret": "",
            "fitbit_access_token": "",
            "fitbit_refresh_token": "",
        },
        "display": {
            "layout_mode": "extend",
            "primary": "",
            "outputs": [],
        },
        "mail": {
            "notify_new_messages": True,
            "play_notification_sound": False,
            "hide_notification_content": False,
        },
        "marketplace": {
            "catalog_repo_url": "https://github.com/gab-luz/hanauta-plugins",
            "catalog_branch": "main",
            "catalog_manifest_path": "plugins.json",
            "catalog_sources": [
                {
                    "repo_url": "https://github.com/gab-luz/hanauta-plugins",
                    "branch": "main",
                    "manifest_path": "plugins.json",
                }
            ],
            "install_dir": str(DEFAULT_PLUGIN_INSTALL_DIR),
            "catalog_cache": [],
            "installed_plugins": [_default_wifi_plugin_entry()],
        },
        "region": {
            "locale_code": "",
            "keyboard_layout": "us",
            "use_24_hour": False,
            "date_style": "us",
            "temperature_unit": "c",
        },
        "bar": dict(DEFAULT_BAR_SETTINGS),
        "ai_popup": {
            "window_width": 452,
            "window_height": 930,
        },
        "services": merged_service_settings({}),
    }
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return default
    appearance = dict(payload.get("appearance", {}))
    appearance.setdefault("accent", "orchid")
    appearance.setdefault("wallpaper_mode", "picture")
    appearance.setdefault("wallpaper_path", str(CURRENT_WALLPAPER))
    appearance.setdefault("wallpaper_fit_modes", {})
    appearance.setdefault("slideshow_folder", str(WALLS_DIR))
    appearance.setdefault("slideshow_interval", 30)
    appearance.setdefault("slideshow_enabled", False)
    appearance.setdefault("theme_mode", "dark")
    appearance.setdefault("custom_theme_id", "retrowave")
    appearance.setdefault("transparency", True)
    try:
        appearance["notification_center_panel_opacity"] = max(
            35, min(100, int(appearance.get("notification_center_panel_opacity", 84)))
        )
    except Exception:
        appearance["notification_center_panel_opacity"] = 84
    try:
        appearance["notification_center_card_opacity"] = max(
            appearance["notification_center_panel_opacity"],
            min(100, int(appearance.get("notification_center_card_opacity", 92))),
        )
    except Exception:
        appearance["notification_center_card_opacity"] = max(
            appearance["notification_center_panel_opacity"], 92
        )
    try:
        appearance["notification_toast_max_width"] = max(
            260, min(640, int(appearance.get("notification_toast_max_width", 356)))
        )
    except Exception:
        appearance["notification_toast_max_width"] = 356
    try:
        appearance["notification_toast_max_height"] = max(
            160, min(640, int(appearance.get("notification_toast_max_height", 280)))
        )
    except Exception:
        appearance["notification_toast_max_height"] = 280
    appearance.setdefault("wallpaper_change_notifications_enabled", False)
    appearance.setdefault("use_matugen_palette", False)
    appearance.setdefault("matugen_notifications_enabled", False)
    theme_choice = str(appearance.get("theme_choice", "")).strip().lower()
    if theme_choice not in THEME_CHOICES:
        theme_choice = (
            "wallpaper_aware"
            if appearance.get("use_matugen_palette", False)
            else str(appearance.get("theme_mode", "dark")).strip().lower()
        )
    if theme_choice not in THEME_CHOICES:
        theme_choice = "dark"
    appearance["theme_choice"] = theme_choice
    custom_theme_id = (
        str(appearance.get("custom_theme_id", "retrowave")).strip().lower()
    )
    appearance["custom_theme_id"] = (
        custom_theme_id if custom_theme_id in CUSTOM_THEME_KEYS else "retrowave"
    )
    home_assistant = dict(payload.get("home_assistant", {}))
    home_assistant.setdefault("url", "")
    home_assistant.setdefault("token", "")
    home_assistant.setdefault("pinned_entities", [])
    ntfy = dict(payload.get("ntfy", {}))
    ntfy.setdefault("enabled", False)
    ntfy.setdefault("show_in_bar", False)
    ntfy.setdefault("server_url", "https://ntfy.sh")
    ntfy.setdefault("topic", "")
    ntfy.setdefault("token", "")
    ntfy.setdefault("username", "")
    ntfy.setdefault("password", "")
    ntfy.setdefault("auth_mode", "token")
    ntfy.setdefault("topics", [])
    ntfy.setdefault("all_topics", False)
    ntfy["hide_notification_content"] = bool(
        ntfy.get("hide_notification_content", False)
    )
    mail = dict(payload.get("mail", {}))
    mail["notify_new_messages"] = bool(mail.get("notify_new_messages", True))
    mail["play_notification_sound"] = bool(mail.get("play_notification_sound", False))
    mail["hide_notification_content"] = bool(
        mail.get("hide_notification_content", False)
    )
    marketplace = dict(payload.get("marketplace", {}))
    marketplace["catalog_repo_url"] = (
        str(
            marketplace.get(
                "catalog_repo_url", "https://github.com/gab-luz/hanauta-plugins"
            )
        ).strip()
        or "https://github.com/gab-luz/hanauta-plugins"
    )
    marketplace["catalog_branch"] = (
        str(marketplace.get("catalog_branch", "main")).strip() or "main"
    )
    marketplace["catalog_manifest_path"] = (
        str(marketplace.get("catalog_manifest_path", "plugins.json")).strip()
        or "plugins.json"
    )
    sources = marketplace.get("catalog_sources", [])
    normalized_sources: list[dict[str, str]] = []
    if isinstance(sources, list):
        for row in sources:
            if not isinstance(row, dict):
                continue
            repo_url = str(row.get("repo_url", row.get("repo", ""))).strip()
            if not repo_url:
                continue
            normalized_sources.append(
                {
                    "repo_url": repo_url,
                    "branch": str(row.get("branch", "main")).strip() or "main",
                    "manifest_path": str(
                        row.get(
                            "manifest_path",
                            row.get("catalog_manifest_path", "plugins.json"),
                        )
                    )
                    .strip()
                    .lstrip("/")
                    or "plugins.json",
                }
            )
    if not normalized_sources:
        normalized_sources = [
            {
                "repo_url": marketplace["catalog_repo_url"],
                "branch": marketplace["catalog_branch"],
                "manifest_path": marketplace["catalog_manifest_path"],
            }
        ]
    marketplace["catalog_sources"] = normalized_sources
    marketplace["install_dir"] = str(
        marketplace.get("install_dir", str(DEFAULT_PLUGIN_INSTALL_DIR))
    ).strip() or str(DEFAULT_PLUGIN_INSTALL_DIR)
    catalog_cache = marketplace.get("catalog_cache", [])
    marketplace["catalog_cache"] = (
        catalog_cache if isinstance(catalog_cache, list) else []
    )
    marketplace["installed_plugins"] = _ensure_default_installed_plugins(
        marketplace.get("installed_plugins", [])
    )
    weather = dict(payload.get("weather", {}))
    weather.setdefault("enabled", False)
    weather.setdefault("name", "")
    weather.setdefault("admin1", "")
    weather.setdefault("country", "")
    weather.setdefault("latitude", 0.0)
    weather.setdefault("longitude", 0.0)
    weather.setdefault("timezone", "auto")
    weather.setdefault("notify_climate_changes", True)
    weather.setdefault("notify_rain_soon", True)
    weather.setdefault("notify_sunset_soon", True)
    weather.setdefault("notify_temperature_drop_soon", True)
    weather.setdefault("notify_temperature_rise_soon", True)
    weather.setdefault("notify_freezing_risk_tonight", True)
    weather.setdefault("notify_high_uv_window", True)
    weather.setdefault("notify_strong_wind_incoming", True)
    weather.setdefault("notify_thunderstorm_likelihood", True)
    weather.setdefault("notify_snow_ice_start", True)
    weather.setdefault("notify_fog_low_visibility", True)
    weather.setdefault("notify_air_quality_worsening", True)
    weather.setdefault("notify_pollen_high", True)
    weather.setdefault("notify_morning_commute_rain", True)
    weather.setdefault("notify_evening_commute_risk", True)
    weather.setdefault("notify_feels_like_extreme", True)
    weather.setdefault("notify_sunrise_soon", True)
    weather.setdefault("notify_dry_window_ending", True)
    try:
        weather["notify_lead_minutes"] = max(
            5, min(180, int(weather.get("notify_lead_minutes", 30) or 30))
        )
    except Exception:
        weather["notify_lead_minutes"] = 30
    weather["commute_morning_start"] = (
        str(weather.get("commute_morning_start", "07:00")).strip() or "07:00"
    )
    weather["commute_morning_end"] = (
        str(weather.get("commute_morning_end", "09:00")).strip() or "09:00"
    )
    weather["commute_evening_start"] = (
        str(weather.get("commute_evening_start", "17:00")).strip() or "17:00"
    )
    weather["commute_evening_end"] = (
        str(weather.get("commute_evening_end", "19:00")).strip() or "19:00"
    )
    calendar = dict(payload.get("calendar", {}))
    calendar.setdefault("show_week_numbers", False)
    calendar.setdefault("show_other_month_days", True)
    first_day = str(calendar.get("first_day_of_week", "monday")).strip().lower()
    calendar["first_day_of_week"] = (
        first_day if first_day in {"monday", "sunday"} else "monday"
    )
    calendar.setdefault("caldav_url", "")
    calendar.setdefault("caldav_username", "")
    calendar.setdefault("caldav_password", "")
    calendar.setdefault("last_sync_status", "")
    calendar.setdefault("connected", False)
    calendar.setdefault("selected_calendar_id", "")
    calendar.setdefault("selected_contact_id", "")
    calendar.setdefault("selected_remote_calendar_url", "")

    calendars = calendar.get("calendars", [])
    if not isinstance(calendars, list):
        calendars = []
    sanitized_calendars: list[dict[str, object]] = []
    for item in calendars:
        if not isinstance(item, dict):
            continue
        account_id = str(item.get("id", "")).strip()
        if not account_id:
            continue
        remote_calendars = item.get("remote_calendars", [])
        if not isinstance(remote_calendars, list):
            remote_calendars = []
        sanitized_remote: list[dict[str, str]] = []
        for remote in remote_calendars:
            if not isinstance(remote, dict):
                continue
            remote_url = str(remote.get("url", "")).strip()
            if not remote_url:
                continue
            sanitized_remote.append(
                {
                    "name": str(remote.get("name", "")).strip() or "Calendar",
                    "url": remote_url,
                }
            )
        sanitized_calendars.append(
            {
                "id": account_id,
                "label": str(item.get("label", "")).strip() or "Calendar",
                "enabled": bool(item.get("enabled", True)),
                "caldav_url": str(item.get("caldav_url", "")).strip(),
                "caldav_username": str(item.get("caldav_username", "")).strip(),
                "caldav_password": str(item.get("caldav_password", "")),
                "connected": bool(item.get("connected", False)),
                "last_sync_status": str(item.get("last_sync_status", "")).strip(),
                "remote_calendars": sanitized_remote,
            }
        )
    if not sanitized_calendars and (
        str(calendar.get("caldav_url", "")).strip()
        or str(calendar.get("caldav_username", "")).strip()
        or str(calendar.get("caldav_password", "")).strip()
    ):
        legacy_id = "primary"
        sanitized_calendars = [
            {
                "id": legacy_id,
                "label": "Primary",
                "enabled": True,
                "caldav_url": str(calendar.get("caldav_url", "")).strip(),
                "caldav_username": str(calendar.get("caldav_username", "")).strip(),
                "caldav_password": str(calendar.get("caldav_password", "")),
                "connected": bool(calendar.get("connected", False)),
                "last_sync_status": str(calendar.get("last_sync_status", "")).strip(),
                "remote_calendars": [],
            }
        ]
        calendar["selected_calendar_id"] = legacy_id
    calendar["calendars"] = sanitized_calendars
    selected_calendar_id = str(calendar.get("selected_calendar_id", "")).strip()
    if sanitized_calendars and (
        not selected_calendar_id
        or not any(row.get("id") == selected_calendar_id for row in sanitized_calendars)
    ):
        calendar["selected_calendar_id"] = str(sanitized_calendars[0].get("id", ""))

    contacts = calendar.get("contacts", [])
    if not isinstance(contacts, list):
        contacts = []
    sanitized_contacts: list[dict[str, object]] = []
    for item in contacts:
        if not isinstance(item, dict):
            continue
        account_id = str(item.get("id", "")).strip()
        if not account_id:
            continue
        sanitized_contacts.append(
            {
                "id": account_id,
                "label": str(item.get("label", "")).strip() or "Contacts",
                "enabled": bool(item.get("enabled", True)),
                "carddav_url": str(item.get("carddav_url", "")).strip(),
                "carddav_username": str(item.get("carddav_username", "")).strip(),
                "carddav_password": str(item.get("carddav_password", "")),
                "connected": bool(item.get("connected", False)),
                "last_sync_status": str(item.get("last_sync_status", "")).strip(),
            }
        )
    calendar["contacts"] = sanitized_contacts
    selected_contact_id = str(calendar.get("selected_contact_id", "")).strip()
    if sanitized_contacts and (
        not selected_contact_id
        or not any(row.get("id") == selected_contact_id for row in sanitized_contacts)
    ):
        calendar["selected_contact_id"] = str(sanitized_contacts[0].get("id", ""))
    reminders = dict(payload.get("reminders", {}))
    try:
        reminders["default_lead_minutes"] = max(
            0, min(240, int(reminders.get("default_lead_minutes", 20)))
        )
    except Exception:
        reminders["default_lead_minutes"] = 20
    default_intensity = (
        str(reminders.get("default_intensity", "discrete")).strip().lower()
    )
    reminders["default_intensity"] = (
        default_intensity
        if default_intensity in {"quiet", "discrete", "disturbing"}
        else "discrete"
    )
    reminders["tea_label"] = str(reminders.get("tea_label", "Tea")).strip() or "Tea"
    try:
        reminders["tea_minutes"] = max(
            1, min(180, int(reminders.get("tea_minutes", 5)))
        )
    except Exception:
        reminders["tea_minutes"] = 5
    tracked = reminders.get("tracked_events", [])
    if not isinstance(tracked, list):
        tracked = []
    sanitized_tracked: list[dict] = []
    for item in tracked:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        start = str(item.get("start", "")).strip()
        if not title or not start:
            continue
        try:
            lead_minutes = max(
                0,
                min(
                    240,
                    int(item.get("lead_minutes", reminders["default_lead_minutes"])),
                ),
            )
        except Exception:
            lead_minutes = reminders["default_lead_minutes"]
        severity = (
            str(item.get("severity", reminders["default_intensity"])).strip().lower()
        )
        if severity not in {"quiet", "discrete", "disturbing"}:
            severity = reminders["default_intensity"]
        sanitized_tracked.append(
            {
                "title": title,
                "start": start,
                "lead_minutes": lead_minutes,
                "severity": severity,
                "calendar_index": int(item.get("calendar_index", -1))
                if str(item.get("calendar_index", "")).strip()
                else -1,
                "filename": str(item.get("filename", "")).strip(),
            }
        )
    reminders["tracked_events"] = sanitized_tracked
    pomodoro = dict(payload.get("pomodoro", {}))
    try:
        pomodoro["work_minutes"] = max(
            5, min(90, int(pomodoro.get("work_minutes", 25)))
        )
    except Exception:
        pomodoro["work_minutes"] = 25
    try:
        pomodoro["short_break_minutes"] = max(
            1, min(30, int(pomodoro.get("short_break_minutes", 5)))
        )
    except Exception:
        pomodoro["short_break_minutes"] = 5
    try:
        pomodoro["long_break_minutes"] = max(
            5, min(60, int(pomodoro.get("long_break_minutes", 15)))
        )
    except Exception:
        pomodoro["long_break_minutes"] = 15
    try:
        pomodoro["long_break_every"] = max(
            2, min(8, int(pomodoro.get("long_break_every", 4)))
        )
    except Exception:
        pomodoro["long_break_every"] = 4
    pomodoro["auto_start_breaks"] = bool(pomodoro.get("auto_start_breaks", False))
    pomodoro["auto_start_focus"] = bool(pomodoro.get("auto_start_focus", False))
    rss = dict(payload.get("rss", {}))
    feeds = rss.get("feeds", [])
    if not isinstance(feeds, list):
        feeds = []
    normalized_feeds: list[dict[str, str]] = []
    for item in feeds:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        normalized_feeds.append(
            {"name": str(item.get("name", "")).strip() or url, "url": url}
        )
    rss["feeds"] = normalized_feeds
    rss["feed_urls"] = str(rss.get("feed_urls", "")).strip()
    rss["opml_source"] = str(rss.get("opml_source", "")).strip()
    rss["username"] = str(rss.get("username", "")).strip()
    rss["password"] = str(rss.get("password", ""))
    try:
        rss["item_limit"] = max(3, min(30, int(rss.get("item_limit", 10))))
    except Exception:
        rss["item_limit"] = 10
    try:
        rss["check_interval_minutes"] = max(
            5, min(180, int(rss.get("check_interval_minutes", 15)))
        )
    except Exception:
        rss["check_interval_minutes"] = 15
    rss["notify_new_items"] = bool(rss.get("notify_new_items", True))
    rss["play_notification_sound"] = bool(rss.get("play_notification_sound", False))
    rss["show_feed_name"] = bool(rss.get("show_feed_name", True))
    rss["open_in_browser"] = bool(rss.get("open_in_browser", True))
    rss["show_images"] = bool(rss.get("show_images", True))
    sort_mode = str(rss.get("sort_mode", "newest")).strip().lower()
    rss["sort_mode"] = (
        sort_mode if sort_mode in {"newest", "oldest", "byfeed"} else "newest"
    )
    try:
        rss["max_per_feed"] = max(1, min(20, int(rss.get("max_per_feed", 5))))
    except Exception:
        rss["max_per_feed"] = 5
    view_mode = str(rss.get("view_mode", "expanded")).strip().lower()
    rss["view_mode"] = view_mode if view_mode in {"expanded", "compact"} else "expanded"
    obs = dict(payload.get("obs", {}))
    obs["host"] = str(obs.get("host", "127.0.0.1")).strip() or "127.0.0.1"
    try:
        obs["port"] = max(1, min(65535, int(obs.get("port", 4455))))
    except Exception:
        obs["port"] = 4455
    obs["password"] = str(obs.get("password", ""))
    obs["auto_connect"] = bool(obs.get("auto_connect", False))
    obs["show_debug_tooltips"] = bool(obs.get("show_debug_tooltips", False))
    crypto = dict(payload.get("crypto", {}))
    crypto["api_provider"] = "coingecko"
    crypto["api_key"] = str(crypto.get("api_key", "")).strip()
    crypto["tracked_coins"] = str(
        crypto.get("tracked_coins", "bitcoin,ethereum")
    ).strip()
    crypto["vs_currency"] = (
        str(crypto.get("vs_currency", "usd")).strip().lower() or "usd"
    )
    try:
        crypto["check_interval_minutes"] = max(
            5, min(180, int(crypto.get("check_interval_minutes", 15)))
        )
    except Exception:
        crypto["check_interval_minutes"] = 15
    try:
        crypto["chart_days"] = max(1, min(90, int(crypto.get("chart_days", 7))))
    except Exception:
        crypto["chart_days"] = 7
    crypto["notify_price_moves"] = bool(crypto.get("notify_price_moves", True))
    try:
        crypto["price_up_percent"] = max(
            0.5, min(50.0, float(crypto.get("price_up_percent", 3.0)))
        )
    except Exception:
        crypto["price_up_percent"] = 3.0
    try:
        crypto["price_down_percent"] = max(
            0.5, min(50.0, float(crypto.get("price_down_percent", 3.0)))
        )
    except Exception:
        crypto["price_down_percent"] = 3.0
    vps = dict(payload.get("vps", {}))
    vps["host"] = str(vps.get("host", "")).strip()
    try:
        vps["port"] = max(1, min(65535, int(vps.get("port", 22))))
    except Exception:
        vps["port"] = 22
    vps["username"] = str(vps.get("username", "")).strip()
    vps["identity_file"] = str(vps.get("identity_file", "")).strip()
    vps["app_service"] = str(vps.get("app_service", "")).strip()
    vps["health_command"] = (
        str(vps.get("health_command", "uptime && df -h /")).strip()
        or "uptime && df -h /"
    )
    vps["update_command"] = (
        str(vps.get("update_command", "sudo apt update && sudo apt upgrade -y")).strip()
        or "sudo apt update && sudo apt upgrade -y"
    )
    clock = dict(payload.get("clock", {}))
    try:
        clock["size"] = max(220, min(520, int(clock.get("size", 320))))
    except Exception:
        clock["size"] = 320
    clock["show_seconds"] = bool(clock.get("show_seconds", True))
    try:
        clock["digital_line_spacing"] = max(
            8, min(64, int(clock.get("digital_line_spacing", 14)))
        )
    except Exception:
        clock["digital_line_spacing"] = 14
    try:
        clock["position_x"] = int(clock.get("position_x", -1))
    except Exception:
        clock["position_x"] = -1
    try:
        clock["position_y"] = int(clock.get("position_y", -1))
    except Exception:
        clock["position_y"] = -1
    autolock = dict(payload.get("autolock", {}))
    autolock["enabled"] = bool(autolock.get("enabled", True))
    try:
        autolock["timeout_minutes"] = max(
            1, min(60, int(autolock.get("timeout_minutes", 2)))
        )
    except Exception:
        autolock["timeout_minutes"] = 2
    lockscreen = dict(payload.get("lockscreen", {}))
    lockscreen["blur_screenshot"] = bool(lockscreen.get("blur_screenshot", False))
    lockscreen["pause_media_on_lock"] = bool(
        lockscreen.get("pause_media_on_lock", True)
    )
    lockscreen["use_slow_fade"] = bool(lockscreen.get("use_slow_fade", True))
    lockscreen["prefer_i3lock_color"] = bool(
        lockscreen.get("prefer_i3lock_color", True)
    )
    lockscreen["show_clock"] = bool(lockscreen.get("show_clock", True))
    lockscreen["show_indicator"] = bool(lockscreen.get("show_indicator", True))
    lockscreen["pass_media_keys"] = bool(lockscreen.get("pass_media_keys", True))
    lockscreen["pass_volume_keys"] = bool(lockscreen.get("pass_volume_keys", True))
    try:
        lockscreen["refresh_rate"] = max(
            0, min(30, int(lockscreen.get("refresh_rate", 1)))
        )
    except Exception:
        lockscreen["refresh_rate"] = 1
    try:
        lockscreen["ring_radius"] = max(
            8, min(80, int(lockscreen.get("ring_radius", 28)))
        )
    except Exception:
        lockscreen["ring_radius"] = 28
    try:
        lockscreen["ring_width"] = max(1, min(24, int(lockscreen.get("ring_width", 6))))
    except Exception:
        lockscreen["ring_width"] = 6
    lockscreen["time_format"] = (
        str(lockscreen.get("time_format", "%H:%M")).strip() or "%H:%M"
    )
    lockscreen["date_format"] = (
        str(lockscreen.get("date_format", "%A, %d %B %Y")).strip() or "%A, %d %B %Y"
    )
    lockscreen["greeter_text"] = (
        str(
            lockscreen.get(
                "greeter_text", "Hanauta locked • Type your password to unlock"
            )
        ).strip()
        or "Hanauta locked • Type your password to unlock"
    )
    lockscreen["verifying_text"] = (
        str(lockscreen.get("verifying_text", "Verifying...")).strip() or "Verifying..."
    )
    lockscreen["wrong_text"] = (
        str(lockscreen.get("wrong_text", "Wrong password")).strip() or "Wrong password"
    )
    audio = dict(payload.get("audio", {}))
    audio["default_sink"] = str(audio.get("default_sink", "")).strip()
    audio["default_source"] = str(audio.get("default_source", "")).strip()
    audio["alert_sounds_enabled"] = bool(audio.get("alert_sounds_enabled", True))
    mute_behavior = str(audio.get("mute_behavior", "leave_as_is")).strip().lower()
    audio["mute_behavior"] = (
        mute_behavior
        if mute_behavior in {"leave_as_is", "mute_on_lock", "mute_on_suspend"}
        else "leave_as_is"
    )
    audio["route_new_apps_to_default_sink"] = bool(
        audio.get("route_new_apps_to_default_sink", True)
    )
    notifications = dict(payload.get("notifications", {}))
    try:
        notifications["history_limit"] = max(
            10, min(1000, int(notifications.get("history_limit", 150)))
        )
    except Exception:
        notifications["history_limit"] = 150
    urgency_policy = str(notifications.get("urgency_policy", "normal")).strip().lower()
    notifications["urgency_policy"] = (
        urgency_policy
        if urgency_policy in {"all", "normal", "critical_only"}
        else "normal"
    )
    notifications["pause_while_sharing"] = bool(
        notifications.get("pause_while_sharing", True)
    )
    notifications["per_app_rules_enabled"] = bool(
        notifications.get("per_app_rules_enabled", True)
    )
    notifications["lock_osd_enabled"] = bool(
        notifications.get("lock_osd_enabled", True)
    )
    try:
        notifications["default_duration_ms"] = max(
            2000, min(120000, int(notifications.get("default_duration_ms", 10000)))
        )
    except Exception:
        notifications["default_duration_ms"] = 10000
    lock_osd_position = str(
        notifications.get("lock_osd_position", "bottom_center")
    ).strip()
    notifications["lock_osd_position"] = (
        lock_osd_position
        if lock_osd_position
        in {
            "top_left",
            "top_center",
            "top_right",
            "center_left",
            "center",
            "center_right",
            "bottom_left",
            "bottom_center",
            "bottom_right",
        }
        else "bottom_center"
    )
    input_settings = dict(payload.get("input", {}))
    input_settings["keyboard_layout"] = (
        str(input_settings.get("keyboard_layout", "us")).strip() or "us"
    )
    try:
        input_settings["repeat_delay_ms"] = max(
            150, min(1200, int(input_settings.get("repeat_delay_ms", 300)))
        )
    except Exception:
        input_settings["repeat_delay_ms"] = 300
    try:
        input_settings["repeat_rate"] = max(
            10, min(60, int(input_settings.get("repeat_rate", 30)))
        )
    except Exception:
        input_settings["repeat_rate"] = 30
    input_settings["tap_to_click"] = bool(input_settings.get("tap_to_click", True))
    input_settings["natural_scroll"] = bool(input_settings.get("natural_scroll", False))
    try:
        input_settings["mouse_accel"] = max(
            -10, min(10, int(input_settings.get("mouse_accel", 0)))
        )
    except Exception:
        input_settings["mouse_accel"] = 0
    startup = dict(payload.get("startup", {}))
    startup["launch_bar"] = bool(startup.get("launch_bar", True))
    startup["launch_dock"] = bool(startup.get("launch_dock", True))
    startup["restore_wallpaper"] = bool(startup.get("restore_wallpaper", True))
    startup["restore_displays"] = bool(startup.get("restore_displays", True))
    startup["restore_vpn"] = bool(startup.get("restore_vpn", True))
    try:
        startup["startup_delay_seconds"] = max(
            0, min(120, int(startup.get("startup_delay_seconds", 0)))
        )
    except Exception:
        startup["startup_delay_seconds"] = 0
    startup["restart_hooks_enabled"] = bool(startup.get("restart_hooks_enabled", True))
    startup["watchdog_enabled"] = bool(startup.get("watchdog_enabled", False))
    privacy = dict(payload.get("privacy", {}))
    privacy["lock_on_suspend"] = bool(privacy.get("lock_on_suspend", True))
    privacy["hide_notification_content_global"] = bool(
        privacy.get("hide_notification_content_global", False)
    )
    privacy["pause_notifications_while_sharing"] = bool(
        privacy.get("pause_notifications_while_sharing", True)
    )
    privacy["screenshot_guard_enabled"] = bool(
        privacy.get("screenshot_guard_enabled", False)
    )
    privacy["screen_share_guard_enabled"] = bool(
        privacy.get("screen_share_guard_enabled", True)
    )
    networking = dict(payload.get("networking", {}))
    networking["preferred_wifi_interface"] = str(
        networking.get("preferred_wifi_interface", "")
    ).strip()
    networking["preferred_wireguard_interface"] = str(
        networking.get("preferred_wireguard_interface", "")
    ).strip()
    networking["wifi_autoconnect"] = bool(networking.get("wifi_autoconnect", True))
    networking["vpn_reconnect_on_login"] = bool(
        networking.get("vpn_reconnect_on_login", False)
    )
    split_tunnel_apps = networking.get("split_tunnel_apps", [])
    networking["split_tunnel_apps"] = (
        split_tunnel_apps if isinstance(split_tunnel_apps, list) else []
    )
    storage = dict(payload.get("storage", {}))
    try:
        storage["wallpaper_cache_cleanup_days"] = max(
            1, min(365, int(storage.get("wallpaper_cache_cleanup_days", 30)))
        )
    except Exception:
        storage["wallpaper_cache_cleanup_days"] = 30
    try:
        storage["log_retention_days"] = max(
            1, min(365, int(storage.get("log_retention_days", 14)))
        )
    except Exception:
        storage["log_retention_days"] = 14
    storage["clean_temp_state_on_startup"] = bool(
        storage.get("clean_temp_state_on_startup", False)
    )
    health = dict(payload.get("health", {}))
    health["provider"] = str(health.get("provider", "manual")).strip().lower()
    if health["provider"] not in {"manual", "fitbit"}:
        health["provider"] = "manual"
    try:
        health["step_goal"] = max(1000, min(50000, int(health.get("step_goal", 10000))))
    except Exception:
        health["step_goal"] = 10000
    try:
        health["water_goal_ml"] = max(
            250, min(6000, int(health.get("water_goal_ml", 2000)))
        )
    except Exception:
        health["water_goal_ml"] = 2000
    try:
        health["sync_interval_minutes"] = max(
            5, min(360, int(health.get("sync_interval_minutes", 30)))
        )
    except Exception:
        health["sync_interval_minutes"] = 30
    health["fitbit_client_id"] = str(health.get("fitbit_client_id", "")).strip()
    health["fitbit_client_secret"] = str(health.get("fitbit_client_secret", "")).strip()
    health["fitbit_access_token"] = str(health.get("fitbit_access_token", "")).strip()
    health["fitbit_refresh_token"] = str(health.get("fitbit_refresh_token", "")).strip()
    display = dict(payload.get("display", {}))
    display.setdefault("layout_mode", "extend")
    display.setdefault("primary", "")
    outputs = display.get("outputs", [])
    if not isinstance(outputs, list):
        outputs = []
    display["outputs"] = [item for item in outputs if isinstance(item, dict)]
    profile = dict(payload.get("profile", {}))
    profile["first_name"] = str(profile.get("first_name", "")).strip()
    profile["nickname"] = str(profile.get("nickname", "")).strip()
    pronunciations_raw = profile.get("pronunciations", [])
    pronunciations: list[dict[str, str]] = []
    if isinstance(pronunciations_raw, list):
        for row in pronunciations_raw:
            if not isinstance(row, dict):
                continue
            lang = str(row.get("lang", row.get("language", ""))).strip().replace("_", "-")
            pronunciations.append(
                {
                    "lang": lang,
                    "spoken_name": str(row.get("spoken_name", row.get("spoken", ""))).strip(),
                    "new_email_phrase": str(
                        row.get("new_email_phrase", row.get("email_new_phrase", ""))
                    ).strip(),
                }
            )
    profile["pronunciations"] = pronunciations
    region = dict(payload.get("region", {}))
    region["locale_code"] = str(region.get("locale_code", "")).strip()
    region["keyboard_layout"] = (
        str(region.get("keyboard_layout", input_settings.get("keyboard_layout", "us"))).strip()
        or "us"
    )
    region["use_24_hour"] = bool(region.get("use_24_hour", False))
    date_style = str(region.get("date_style", "us")).strip().lower()
    region["date_style"] = date_style if date_style in {"us", "iso", "eu"} else "us"
    temp_unit = str(region.get("temperature_unit", "c")).strip().lower()
    region["temperature_unit"] = temp_unit if temp_unit in {"c", "f"} else "c"
    bar = merged_bar_settings(payload.get("bar", {}))
    ai_popup = dict(payload.get("ai_popup", {}))
    try:
        ai_popup["window_width"] = max(
            360, min(1600, int(ai_popup.get("window_width", 452)))
        )
    except Exception:
        ai_popup["window_width"] = 452
    try:
        ai_popup["window_height"] = max(
            520, min(1800, int(ai_popup.get("window_height", 930)))
        )
    except Exception:
        ai_popup["window_height"] = 930
    services = merged_service_settings(payload.get("services", {}))
    result = {
        "profile": profile,
        "appearance": appearance,
        "home_assistant": home_assistant,
        "ntfy": ntfy,
        "weather": weather,
        "calendar": calendar,
        "reminders": reminders,
        "pomodoro": pomodoro,
        "rss": rss,
        "obs": obs,
        "crypto": crypto,
        "vps": vps,
        "clock": clock,
        "autolock": autolock,
        "lockscreen": lockscreen,
        "audio": audio,
        "notifications": notifications,
        "input": input_settings,
        "startup": startup,
        "privacy": privacy,
        "networking": networking,
        "storage": storage,
        "health": health,
        "display": display,
        "mail": mail,
        "marketplace": marketplace,
        "region": region,
        "bar": bar,
        "ai_popup": ai_popup,
        "services": services,
    }
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key not in result:
                result[key] = value
    return result


def ensure_settings_state() -> None:
    save_settings_state(load_settings_state())
