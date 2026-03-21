from __future__ import annotations

import base64
import json
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import error, parse, request


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "health-widget"
STATE_FILE = STATE_DIR / "state.json"

FITBIT_API_BASE = "https://api.fitbit.com"
FITBIT_TOKEN_URL = f"{FITBIT_API_BASE}/oauth2/token"
FITBIT_ACTIVITIES_URL = f"{FITBIT_API_BASE}/1/user/-/activities/date/today.json"
FITBIT_SLEEP_URL = f"{FITBIT_API_BASE}/1.2/user/-/sleep/date/today.json"
FITBIT_HEART_URL = f"{FITBIT_API_BASE}/1/user/-/activities/heart/date/today/1d.json"

DEFAULT_HEALTH_SETTINGS: dict[str, Any] = {
    "provider": "manual",
    "step_goal": 10000,
    "water_goal_ml": 2000,
    "sync_interval_minutes": 30,
    "fitbit_client_id": "",
    "fitbit_client_secret": "",
    "fitbit_access_token": "",
    "fitbit_refresh_token": "",
}

DEFAULT_HEALTH_SERVICE_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "show_in_notification_center": False,
    "show_in_bar": True,
    "water_reminder_notifications": False,
    "stand_up_reminder_notifications": False,
    "movement_reminder_notifications": False,
}

WATER_REMINDER_VARIATIONS = [
    "Hydration check. A glass of water right now will help the rest of your day feel easier.",
    "Quick reset: drink some water and give your body the support it has been waiting for.",
    "A small win counts. Stand up for a moment and take a few good sips of water.",
    "You have been carrying a lot already. Pause for water and let your body catch up with you.",
    "Water break. A minute of care now can lift your focus for the next stretch.",
    "Keep the momentum kind. Refill your water and give yourself a fresh start.",
    "This is your reminder that energy is built gently. Drink some water and keep going.",
    "A steady day is made of small choices. Water first, then back to it.",
    "Take a breath, grab some water, and come back a little more refreshed.",
    "You do not need to power through everything dry. Drink some water and reset.",
]

STAND_UP_REMINDER_VARIATIONS = [
    "Time to stand up for a minute. Your back, neck, and focus will thank you.",
    "A quick stretch break now can make the next hour feel much lighter.",
    "Stand, roll your shoulders, and reset your posture. That small move matters.",
    "You have done enough sitting for now. Get up, breathe deep, and loosen up.",
    "A one-minute stand-up break is still progress. Give your body that break.",
    "Shift your weight, stretch a little, and come back feeling less pinned down.",
    "You are allowed to interrupt the grind. Stand up and take a real reset.",
    "A short posture break now can save you from feeling wrecked later. Get up for a bit.",
    "Stand tall for a minute and let your body remember it is meant to move.",
    "Pause the chair marathon. Stand up, stretch out, and reset your energy.",
]

MOVEMENT_REMINDER_VARIATIONS = [
    "A short walk or a quick workout would do you good right now. Let movement work for you.",
    "You do not need a perfect session. Ten honest minutes of movement is already a win.",
    "A quick walk can clear your head fast. If you can, step away and move a little.",
    "Gym, walk, stretch, or anything active. Your body deserves at least one real effort today.",
    "You will likely feel better after moving, even if it is only for a few minutes. Start small.",
    "This is your nudge to build momentum: shoes on, body moving, one step at a time.",
    "A little movement now can change the whole mood of the day. Go get that reset.",
    "You have enough in you for a walk around the block or a short session. Count that as real progress.",
    "Do something active for yourself today. It does not have to be dramatic to be worth it.",
    "Energy often follows action. Take a walk, hit the gym, or move however you can.",
]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_health_settings(payload: object) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}
    provider = str(current.get("provider", "manual")).strip().lower()
    if provider not in {"manual", "fitbit"}:
        provider = "manual"
    return {
        "provider": provider,
        "step_goal": clamp_int(current.get("step_goal", 10000), 10000, 1000, 50000),
        "water_goal_ml": clamp_int(current.get("water_goal_ml", 2000), 2000, 250, 6000),
        "sync_interval_minutes": clamp_int(current.get("sync_interval_minutes", 30), 30, 5, 360),
        "fitbit_client_id": str(current.get("fitbit_client_id", "")).strip(),
        "fitbit_client_secret": str(current.get("fitbit_client_secret", "")).strip(),
        "fitbit_access_token": str(current.get("fitbit_access_token", "")).strip(),
        "fitbit_refresh_token": str(current.get("fitbit_refresh_token", "")).strip(),
    }


def normalize_health_service_settings(payload: object) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}
    return {
        "enabled": bool(current.get("enabled", DEFAULT_HEALTH_SERVICE_SETTINGS["enabled"])),
        "show_in_notification_center": bool(
            current.get(
                "show_in_notification_center",
                DEFAULT_HEALTH_SERVICE_SETTINGS["show_in_notification_center"],
            )
        ),
        "show_in_bar": bool(current.get("show_in_bar", DEFAULT_HEALTH_SERVICE_SETTINGS["show_in_bar"])),
        "water_reminder_notifications": bool(
            current.get(
                "water_reminder_notifications",
                DEFAULT_HEALTH_SERVICE_SETTINGS["water_reminder_notifications"],
            )
        ),
        "stand_up_reminder_notifications": bool(
            current.get(
                "stand_up_reminder_notifications",
                DEFAULT_HEALTH_SERVICE_SETTINGS["stand_up_reminder_notifications"],
            )
        ),
        "movement_reminder_notifications": bool(
            current.get(
                "movement_reminder_notifications",
                DEFAULT_HEALTH_SERVICE_SETTINGS["movement_reminder_notifications"],
            )
        ),
    }


def _read_settings_payload() -> dict[str, Any]:
    return _read_json(SETTINGS_FILE)


def load_health_settings() -> dict[str, Any]:
    payload = _read_settings_payload()
    return normalize_health_settings(payload.get("health", {}))


def load_health_service_settings() -> dict[str, Any]:
    payload = _read_settings_payload()
    services = payload.get("services", {})
    if not isinstance(services, dict):
        services = {}
    return normalize_health_service_settings(services.get("health_widget", {}))


def choose_reminder_message(kind: str, index: int) -> str:
    mapping = {
        "water": WATER_REMINDER_VARIATIONS,
        "stand": STAND_UP_REMINDER_VARIATIONS,
        "movement": MOVEMENT_REMINDER_VARIATIONS,
    }
    options = mapping.get(kind, [])
    if not options:
        return ""
    return options[index % len(options)]


def save_health_settings(settings: dict[str, Any]) -> None:
    payload = _read_settings_payload()
    payload["health"] = normalize_health_settings(settings)
    _write_json(SETTINGS_FILE, payload)


def _default_state(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    current_settings = settings or load_health_settings()
    today = date.today().isoformat()
    return {
        "date": today,
        "provider": current_settings.get("provider", "manual"),
        "steps": 0,
        "calories_burned": 0,
        "active_minutes": 0,
        "distance_km": 0.0,
        "sleep_hours": 0.0,
        "resting_heart_rate": 0,
        "water_ml": 0,
        "last_sync_at": "",
        "last_sync_status": "Manual tracking is ready.",
        "source_name": "Manual",
        "reminders": {},
    }


def normalize_health_state(payload: object, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    current_settings = settings or load_health_settings()
    current = payload if isinstance(payload, dict) else {}
    base = _default_state(current_settings)
    state = {
        "date": str(current.get("date", base["date"])).strip() or base["date"],
        "provider": str(current.get("provider", current_settings.get("provider", "manual"))).strip().lower() or "manual",
        "steps": clamp_int(current.get("steps", 0), 0, 0, 500000),
        "calories_burned": clamp_int(current.get("calories_burned", 0), 0, 0, 25000),
        "active_minutes": clamp_int(current.get("active_minutes", 0), 0, 0, 1440),
        "distance_km": round(clamp_float(current.get("distance_km", 0.0), 0.0, 0.0, 500.0), 2),
        "sleep_hours": round(clamp_float(current.get("sleep_hours", 0.0), 0.0, 0.0, 24.0), 1),
        "resting_heart_rate": clamp_int(current.get("resting_heart_rate", 0), 0, 0, 240),
        "water_ml": clamp_int(current.get("water_ml", 0), 0, 0, 12000),
        "last_sync_at": str(current.get("last_sync_at", "")).strip(),
        "last_sync_status": str(current.get("last_sync_status", base["last_sync_status"])).strip() or base["last_sync_status"],
        "source_name": str(current.get("source_name", base["source_name"])).strip() or base["source_name"],
        "reminders": current.get("reminders", {}) if isinstance(current.get("reminders", {}), dict) else {},
    }
    if state["provider"] not in {"manual", "fitbit"}:
        state["provider"] = "manual"
    return rollover_health_state(state, current_settings)


def rollover_health_state(state: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, Any]:
    current_settings = settings or load_health_settings()
    today = date.today().isoformat()
    if str(state.get("date", "")).strip() == today:
        return state
    rolled = dict(state)
    rolled["date"] = today
    if current_settings.get("provider", "manual") == "manual":
        rolled["steps"] = 0
        rolled["calories_burned"] = 0
        rolled["active_minutes"] = 0
        rolled["distance_km"] = 0.0
        rolled["sleep_hours"] = 0.0
        rolled["resting_heart_rate"] = 0
        rolled["water_ml"] = 0
        rolled["last_sync_status"] = "Manual tracking reset for today."
    rolled["reminders"] = {}
    return rolled


def load_health_state(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    current_settings = settings or load_health_settings()
    state = normalize_health_state(_read_json(STATE_FILE), current_settings)
    if state.get("provider") != current_settings.get("provider"):
        state["provider"] = current_settings.get("provider", "manual")
    return state


def save_health_state(state: dict[str, Any], settings: dict[str, Any] | None = None) -> None:
    current_settings = settings or load_health_settings()
    _write_json(STATE_FILE, normalize_health_state(state, current_settings))


def _state_to_snapshot(settings: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    steps = int(state.get("steps", 0) or 0)
    step_goal = int(settings.get("step_goal", 10000) or 10000)
    water_ml = int(state.get("water_ml", 0) or 0)
    water_goal_ml = int(settings.get("water_goal_ml", 2000) or 2000)
    return {
        "provider": settings.get("provider", "manual"),
        "source_name": str(state.get("source_name", "Manual")).strip() or "Manual",
        "date": str(state.get("date", date.today().isoformat())),
        "steps": steps,
        "step_goal": step_goal,
        "step_progress": 0.0 if step_goal <= 0 else min(1.0, steps / step_goal),
        "calories_burned": int(state.get("calories_burned", 0) or 0),
        "active_minutes": int(state.get("active_minutes", 0) or 0),
        "distance_km": float(state.get("distance_km", 0.0) or 0.0),
        "sleep_hours": float(state.get("sleep_hours", 0.0) or 0.0),
        "resting_heart_rate": int(state.get("resting_heart_rate", 0) or 0),
        "water_ml": water_ml,
        "water_goal_ml": water_goal_ml,
        "water_progress": 0.0 if water_goal_ml <= 0 else min(1.0, water_ml / water_goal_ml),
        "last_sync_at": str(state.get("last_sync_at", "")).strip(),
        "last_sync_status": str(state.get("last_sync_status", "")).strip(),
    }


def format_steps_short(steps: int) -> str:
    if steps >= 1000000:
        return f"{steps / 1000000:.1f}m".rstrip("0").rstrip(".")
    if steps >= 1000:
        return f"{steps / 1000:.1f}k".rstrip("0").rstrip(".")
    return str(max(0, int(steps)))


def format_sync_time(raw: str) -> str:
    if not raw.strip():
        return "Never"
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    delta = datetime.now() - stamp
    if delta < timedelta(minutes=1):
        return "Just now"
    if delta < timedelta(hours=1):
        return f"{max(1, int(delta.total_seconds() // 60))} min ago"
    if delta < timedelta(days=1):
        return f"{max(1, int(delta.total_seconds() // 3600))} hr ago"
    return stamp.strftime("%d %b %H:%M")


def health_tooltip(snapshot: dict[str, Any]) -> str:
    provider_name = "Fitbit" if snapshot.get("provider") == "fitbit" else "Manual"
    return (
        f"{provider_name} health\n"
        f"Steps: {int(snapshot.get('steps', 0)):,} / {int(snapshot.get('step_goal', 0)):,}\n"
        f"Active: {int(snapshot.get('active_minutes', 0))} min\n"
        f"Sleep: {float(snapshot.get('sleep_hours', 0.0)):.1f} hr\n"
        f"Sync: {format_sync_time(str(snapshot.get('last_sync_at', '')))}"
    )


def send_health_notification(title: str, body: str) -> None:
    if not body.strip():
        return
    try:
        subprocess.Popen(
            ["notify-send", "-a", "Hanauta Health", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def poll_health_reminders(now: datetime | None = None) -> None:
    current_time = now or datetime.now()
    if current_time.hour < 9 or current_time.hour > 21:
        return
    service = load_health_service_settings()
    if not bool(service.get("enabled", DEFAULT_HEALTH_SERVICE_SETTINGS["enabled"])):
        return
    settings = load_health_settings()
    state = load_health_state(settings)
    reminders = state.get("reminders", {})
    if not isinstance(reminders, dict):
        reminders = {}

    checks = (
        ("water_reminder_notifications", "water", 90, "Hydration Reminder"),
        ("stand_up_reminder_notifications", "stand", 60, "Stand Up Reminder"),
        ("movement_reminder_notifications", "movement", 180, "Movement Reminder"),
    )
    changed = False
    minute_of_day = current_time.hour * 60 + current_time.minute
    stamp = current_time.strftime("%Y-%m-%dT%H:%M")
    for flag, kind, interval_minutes, title in checks:
        if not bool(service.get(flag, False)):
            continue
        if minute_of_day % interval_minutes != 0:
            continue
        if str(reminders.get(kind, "")).strip() == stamp:
            continue
        index = (current_time.toordinal() * 24 * 60 + minute_of_day) // interval_minutes
        body = choose_reminder_message(kind, index)
        send_health_notification(title, body)
        reminders[kind] = stamp
        changed = True
    if changed:
        state["reminders"] = reminders
        save_health_state(state, settings)


def _fitbit_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def _fetch_json(url: str, headers: dict[str, str] | None = None, data: bytes | None = None) -> dict[str, Any]:
    req = request.Request(url, headers=headers or {}, data=data)
    with request.urlopen(req, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read().decode(charset, errors="replace")
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def _save_fitbit_tokens(settings: dict[str, Any], token_payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(settings)
    access = str(token_payload.get("access_token", "")).strip()
    refresh = str(token_payload.get("refresh_token", "")).strip()
    if access:
        updated["fitbit_access_token"] = access
    if refresh:
        updated["fitbit_refresh_token"] = refresh
    save_health_settings(updated)
    return updated


def _refresh_fitbit_token(settings: dict[str, Any]) -> dict[str, Any]:
    client_id = str(settings.get("fitbit_client_id", "")).strip()
    client_secret = str(settings.get("fitbit_client_secret", "")).strip()
    refresh_token = str(settings.get("fitbit_refresh_token", "")).strip()
    if not client_id or not client_secret or not refresh_token:
        raise RuntimeError("Fitbit refresh needs client id, client secret, and refresh token.")
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    data = parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    payload = _fetch_json(
        FITBIT_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data=data,
    )
    return _save_fitbit_tokens(settings, payload)


def _request_fitbit_json(url: str, settings: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    current_settings = dict(settings)
    access_token = str(current_settings.get("fitbit_access_token", "")).strip()
    if not access_token and current_settings.get("fitbit_refresh_token"):
        current_settings = _refresh_fitbit_token(current_settings)
        access_token = str(current_settings.get("fitbit_access_token", "")).strip()
    if not access_token:
        raise RuntimeError("Add a Fitbit access token in Hanauta settings.")
    try:
        return _fetch_json(url, headers=_fitbit_headers(access_token)), current_settings
    except error.HTTPError as exc:
        if exc.code not in {401, 403} or not current_settings.get("fitbit_refresh_token"):
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            raise RuntimeError(detail.strip() or f"Fitbit request failed with HTTP {exc.code}.") from exc
        current_settings = _refresh_fitbit_token(current_settings)
        access_token = str(current_settings.get("fitbit_access_token", "")).strip()
        return _fetch_json(url, headers=_fitbit_headers(access_token)), current_settings


def _extract_fitbit_distance_km(summary: dict[str, Any]) -> float:
    distances = summary.get("distances", [])
    if not isinstance(distances, list):
        return 0.0
    for item in distances:
        if not isinstance(item, dict):
            continue
        activity = str(item.get("activity", "")).strip().lower()
        if activity in {"total", "tracker", "walk"}:
            return round(clamp_float(item.get("distance", 0.0), 0.0, 0.0, 500.0), 2)
    return 0.0


def sync_fitbit_snapshot(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    current_settings = settings or load_health_settings()
    activities, current_settings = _request_fitbit_json(FITBIT_ACTIVITIES_URL, current_settings)
    sleep, current_settings = _request_fitbit_json(FITBIT_SLEEP_URL, current_settings)
    heart, current_settings = _request_fitbit_json(FITBIT_HEART_URL, current_settings)

    summary = activities.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    sleep_summary = sleep.get("summary", {})
    if not isinstance(sleep_summary, dict):
        sleep_summary = {}
    heart_series = heart.get("activities-heart", [])
    if not isinstance(heart_series, list):
        heart_series = []
    resting_hr = 0
    if heart_series and isinstance(heart_series[0], dict):
        heart_value = heart_series[0].get("value", {})
        if isinstance(heart_value, dict):
            resting_hr = clamp_int(heart_value.get("restingHeartRate", 0), 0, 0, 240)

    state = load_health_state(current_settings)
    state.update(
        {
            "date": date.today().isoformat(),
            "provider": "fitbit",
            "steps": clamp_int(summary.get("steps", 0), 0, 0, 500000),
            "calories_burned": clamp_int(summary.get("caloriesOut", 0), 0, 0, 25000),
            "active_minutes": clamp_int(
                int(summary.get("veryActiveMinutes", 0) or 0)
                + int(summary.get("fairlyActiveMinutes", 0) or 0)
                + int(summary.get("lightlyActiveMinutes", 0) or 0),
                0,
                0,
                1440,
            ),
            "distance_km": _extract_fitbit_distance_km(summary),
            "sleep_hours": round(clamp_float(sleep_summary.get("totalMinutesAsleep", 0), 0.0, 0.0, 1440.0) / 60.0, 1),
            "resting_heart_rate": resting_hr,
            "last_sync_at": datetime.now().isoformat(timespec="seconds"),
            "last_sync_status": "Fitbit data synced successfully.",
            "source_name": "Fitbit",
        }
    )
    save_health_state(state, current_settings)
    return _state_to_snapshot(current_settings, state)


def load_current_snapshot(*, sync_remote: bool = False, force_sync: bool = False) -> dict[str, Any]:
    settings = load_health_settings()
    state = load_health_state(settings)
    if settings.get("provider") != "fitbit":
        state["provider"] = "manual"
        state["source_name"] = "Manual"
        save_health_state(state, settings)
        return _state_to_snapshot(settings, state)

    should_sync = force_sync
    if sync_remote and not should_sync:
        last_sync_raw = str(state.get("last_sync_at", "")).strip()
        if not last_sync_raw:
            should_sync = True
        else:
            try:
                last_sync = datetime.fromisoformat(last_sync_raw)
            except ValueError:
                should_sync = True
            else:
                should_sync = datetime.now() - last_sync >= timedelta(
                    minutes=int(settings.get("sync_interval_minutes", 30) or 30)
                )
    if should_sync:
        try:
            return sync_fitbit_snapshot(settings)
        except Exception as exc:
            state["last_sync_status"] = str(exc).strip() or "Fitbit sync failed."
            save_health_state(state, settings)
            return _state_to_snapshot(settings, state)
    return _state_to_snapshot(settings, state)


def set_manual_metric(metric: str, value: Any) -> dict[str, Any]:
    settings = load_health_settings()
    state = load_health_state(settings)
    if metric == "sleep_hours":
        state[metric] = round(clamp_float(value, state.get(metric, 0.0), 0.0, 24.0), 1)
    elif metric == "distance_km":
        state[metric] = round(clamp_float(value, state.get(metric, 0.0), 0.0, 500.0), 2)
    else:
        limits = {
            "steps": 500000,
            "calories_burned": 25000,
            "active_minutes": 1440,
            "resting_heart_rate": 240,
            "water_ml": 12000,
        }
        maximum = limits.get(metric, 500000)
        state[metric] = clamp_int(value, state.get(metric, 0), 0, maximum)
    state["provider"] = settings.get("provider", "manual")
    state["source_name"] = "Manual" if settings.get("provider") == "manual" else "Fitbit"
    state["date"] = date.today().isoformat()
    state["last_sync_status"] = "Manual values updated."
    save_health_state(state, settings)
    return _state_to_snapshot(settings, state)


def adjust_manual_metric(metric: str, delta: Any) -> dict[str, Any]:
    settings = load_health_settings()
    state = load_health_state(settings)
    current = state.get(metric, 0)
    if metric in {"sleep_hours", "distance_km"}:
        return set_manual_metric(metric, float(current or 0.0) + float(delta))
    return set_manual_metric(metric, int(current or 0) + int(delta))
