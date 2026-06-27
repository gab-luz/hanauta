#!/usr/bin/env python3
"""Background weather cache daemon for hanauta.

Polls Open-Meteo every 15 minutes and writes the forecast payload to
~/.local/state/hanauta/service/weather.json so that the weather popup
can load cached data instantly instead of showing a loading spinner.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib import parse, request

STATE_DIR = Path(
    os.environ.get("HANAUTA_SERVICE_STATE_DIR")
    or os.environ.get("HANAUTA_STATE_DIR")
    or Path.home() / ".local" / "state" / "hanauta",
)
SERVICE_DIR = STATE_DIR / "service"
WEATHER_CACHE = SERVICE_DIR / "weather.json"
SETTINGS_FILE = (
    STATE_DIR / "notification-center" / "settings.json"
)
POLL_INTERVAL_S = 900  # 15 minutes

WEATHER_API = "https://api.open-meteo.com/v1/forecast"


def load_weather_settings() -> dict[str, Any] | None:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    weather = payload.get("weather", {})
    if not isinstance(weather, dict):
        return None
    if not weather.get("enabled", False):
        return None
    return weather


def extract_city(weather: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return {
            "name": str(weather.get("name", "")).strip(),
            "latitude": float(weather.get("latitude")),
            "longitude": float(weather.get("longitude")),
            "timezone": str(weather.get("timezone", "auto")).strip() or "auto",
        }
    except Exception:
        return None


def fetch_weather_payload(city: dict[str, Any]) -> dict[str, Any] | None:
    params = parse.urlencode(
        {
            "latitude": f"{city['latitude']:.5f}",
            "longitude": f"{city['longitude']:.5f}",
            "timezone": city["timezone"],
            "forecast_days": "7",
            "current": ",".join(
                [
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "precipitation",
                    "pressure_msl",
                    "weather_code",
                    "wind_speed_10m",
                    "is_day",
                ]
            ),
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "sunrise",
                    "sunset",
                ]
            ),
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "apparent_temperature",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                    "visibility",
                    "uv_index",
                    "weather_code",
                    "precipitation_probability",
                    "precipitation",
                    "rain",
                    "snowfall",
                ]
            ),
        }
    )
    url = f"{WEATHER_API}?{params}"
    req = request.Request(url, headers={"User-Agent": "Hanauta Weather/1.0"})
    try:
        with request.urlopen(req, timeout=8.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def write_cache(city: dict[str, Any], payload: dict[str, Any]) -> bool:
    cache = {
        "requested": {
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "timezone": city["timezone"],
        },
        "payload": payload,
    }
    try:
        SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(SERVICE_DIR),
                prefix="weather-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(json.dumps(cache, ensure_ascii=True, separators=(",", ":")))
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            os.replace(str(temp_path), str(WEATHER_CACHE))
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def main() -> int:
    while True:
        weather = load_weather_settings()
        if weather is None:
            time.sleep(POLL_INTERVAL_S)
            continue

        city = extract_city(weather)
        if city is None:
            time.sleep(POLL_INTERVAL_S)
            continue

        payload = fetch_weather_payload(city)
        if payload is not None:
            write_cache(city, payload)

        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    raise SystemExit(main())
