from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QWidget

from pyqt.shared.runtime import source_root

ASSETS_DIR = source_root() / "assets"
WEATHER_ICON_DIR = ASSETS_DIR / "weather-icons"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
SERVICE_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
SERVICE_WEATHER_CACHE = SERVICE_STATE_DIR / "weather.json"
ANIMATED_ICON_FALLBACKS = {
    "partly-cloudy-day": "partly-cloudy-day-qt",
    "partly-cloudy-night": "partly-cloudy-night-qt",
}

WEATHER_API = "https://api.open-meteo.com/v1/forecast"
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
AIR_QUALITY_API = "https://air-quality-api.open-meteo.com/v1/air-quality"
WTTR_API = "https://wttr.in"
OPENWEATHER_API = "https://api.openweathermap.org/data/2.5/onecall"

_WTTR_CODE_MAP: dict[int, int] = {
    113: 0, 116: 2, 119: 3, 122: 3,
    143: 45, 176: 61, 179: 71, 182: 66, 185: 56,
    200: 95, 227: 75, 230: 75,
    248: 45, 260: 48,
    263: 51, 266: 53, 281: 56, 284: 57,
    293: 61, 296: 63, 299: 63, 302: 65, 305: 65, 308: 65,
    311: 66, 314: 67, 317: 66, 320: 67,
    323: 71, 326: 73, 329: 73, 332: 75, 335: 75, 338: 75,
    350: 77, 353: 80, 356: 81, 359: 82,
    362: 66, 365: 67, 368: 85, 371: 86,
    374: 77, 377: 77,
    386: 95, 389: 96, 392: 73, 395: 75,
}

_OPENWEATHER_CODE_MAP: dict[int, int] = {
    200: 95, 201: 95, 202: 96, 210: 95, 211: 95, 212: 96, 221: 95,
    230: 95, 231: 95, 232: 96,
    300: 51, 301: 51, 302: 53, 303: 53, 304: 55,
    310: 51, 311: 53, 312: 55, 313: 53, 314: 55,
    321: 53, 322: 55,
    500: 61, 501: 63, 502: 65, 503: 65, 504: 65,
    511: 66, 520: 80, 521: 80, 522: 81, 531: 81,
    600: 71, 601: 73, 602: 75, 611: 66, 612: 66, 613: 67,
    615: 71, 616: 73, 620: 71, 621: 73, 622: 75,
    701: 45, 711: 45, 721: 45, 731: 45, 741: 45, 751: 45, 761: 45, 762: 48, 771: 45, 781: 45,
    800: 0, 801: 1, 802: 2, 803: 3, 804: 3,
}


@dataclass(frozen=True)
class WeatherCity:
    name: str
    admin1: str
    country: str
    latitude: float
    longitude: float
    timezone: str

    @property
    def label(self) -> str:
        parts = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass(frozen=True)
class WeatherCurrent:
    observed_time_iso: str
    temperature: float
    apparent_temperature: float
    humidity: int
    wind_speed: float
    precipitation: float
    pressure: float
    weather_code: int
    is_day: bool
    condition: str
    icon_name: str
    sunrise_iso: str
    sunset_iso: str
    sunrise: str
    sunset: str


@dataclass(frozen=True)
class WeatherDaily:
    date: str
    weekday: str
    weather_code: int
    icon_name: str
    max_temp: float
    min_temp: float
    precipitation_probability: int


@dataclass(frozen=True)
class WeatherHourly:
    time_iso: str
    weather_code: int
    icon_name: str
    temperature: float
    apparent_temperature: float
    wind_speed: float
    wind_gusts: float
    visibility: float
    uv_index: float
    rain: float
    snowfall: float
    precipitation_probability: int
    precipitation: float
    us_aqi: int | None
    pollen_index: float | None
    minutes_from_current: int


@dataclass(frozen=True)
class WeatherForecast:
    city: WeatherCity
    current: WeatherCurrent
    daily: list[WeatherDaily]
    hourly: list[WeatherHourly]


def load_runtime_settings() -> dict[str, object]:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_weather_settings() -> dict[str, object]:
    settings = load_runtime_settings()
    weather = settings.get("weather", {})
    return weather if isinstance(weather, dict) else {}


def configured_location() -> WeatherCity | None:
    weather = load_weather_settings()
    try:
        return WeatherCity(
            name=str(weather.get("name", "")).strip(),
            admin1=str(weather.get("admin1", "")).strip(),
            country=str(weather.get("country", "")).strip(),
            latitude=float(weather.get("latitude")),
            longitude=float(weather.get("longitude")),
            timezone=str(weather.get("timezone", "auto")).strip() or "auto",
        )
    except Exception:
        return None


def configured_city() -> WeatherCity | None:
    weather = load_weather_settings()
    if not weather or not weather.get("enabled", False):
        return None
    return configured_location()


def _get_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    req = request.Request(url, headers={"User-Agent": "Hanauta Weather/1.0"})
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_service_weather_cache(city: WeatherCity) -> dict[str, Any] | None:
    try:
        payload = json.loads(SERVICE_WEATHER_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    requested = payload.get("requested", {})
    cached = payload.get("payload", {})
    if not isinstance(requested, dict) or not isinstance(cached, dict):
        return None
    try:
        lat = float(requested.get("latitude"))
        lon = float(requested.get("longitude"))
    except Exception:
        return None
    timezone = str(requested.get("timezone", "auto")).strip() or "auto"
    if abs(lat - city.latitude) > 0.01 or abs(lon - city.longitude) > 0.01:
        return None
    if timezone != (city.timezone or "auto"):
        return None
    return cached


def search_cities(query: str, count: int = 8) -> list[WeatherCity]:
    cleaned = query.strip()
    if len(cleaned) < 2:
        return []
    params = parse.urlencode(
        {
            "name": cleaned,
            "count": str(max(1, min(count, 12))),
            "language": "en",
            "format": "json",
        }
    )
    try:
        payload = _get_json(f"{GEOCODING_API}?{params}", timeout=4.0)
    except Exception:
        return []
    results = payload.get("results", [])
    if not isinstance(results, list):
        return []
    cities: list[WeatherCity] = []
    for item in results:
        try:
            cities.append(
                WeatherCity(
                    name=str(item.get("name", "")).strip(),
                    admin1=str(item.get("admin1", "")).strip(),
                    country=str(item.get("country", "")).strip(),
                    latitude=float(item.get("latitude")),
                    longitude=float(item.get("longitude")),
                    timezone=str(item.get("timezone", "auto")).strip() or "auto",
                )
            )
        except Exception:
            continue
    return cities


def _current_icon_name(weather_code: int, is_day: bool) -> str:
    if weather_code == 0:
        return "clear-day" if is_day else "clear-night"
    if weather_code == 1:
        return "clear-day" if is_day else "clear-night"
    if weather_code == 2:
        return "partly-cloudy-day" if is_day else "partly-cloudy-night"
    if weather_code == 3:
        return "overcast"
    if weather_code in {45, 48}:
        return "fog"
    if weather_code in {51, 53, 55}:
        return "overcast-drizzle"
    if weather_code in {56, 57, 66, 67}:
        return "overcast-sleet"
    if weather_code in {61, 63, 65, 80, 81, 82}:
        return "overcast-rain"
    if weather_code in {71, 73, 75, 77, 85, 86}:
        return "overcast-snow"
    if weather_code in {95, 96, 99}:
        return "thunderstorms"
    return "not-available"


def _daily_icon_name(weather_code: int) -> str:
    return _current_icon_name(weather_code, True)


def weather_condition_label(weather_code: int) -> str:
    labels = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Rime fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Dense drizzle",
        56: "Freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Heavy freezing rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Rain showers",
        81: "Heavy showers",
        82: "Violent showers",
        85: "Snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm hail",
        99: "Severe thunderstorm",
    }
    return labels.get(weather_code, "Unavailable")


def _fmt_time(iso_text: str) -> str:
    try:
        moment = datetime.fromisoformat(iso_text)
    except Exception:
        return "--:--"
    return moment.strftime("%-I:%M %p")


def _load_weather_api_key(service: str) -> str:
    weather = load_weather_settings()
    return str(weather.get(f"{service}_api_key", "")).strip()


def _fetch_open_meteo(city: WeatherCity) -> WeatherForecast | None:
    params = parse.urlencode(
        {
            "latitude": f"{city.latitude:.5f}",
            "longitude": f"{city.longitude:.5f}",
            "timezone": city.timezone or "auto",
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
    payload = _load_service_weather_cache(city)
    if payload is None:
        try:
            payload = _get_json(f"{WEATHER_API}?{params}", timeout=5.0)
        except Exception:
            return None

    air_payload: dict[str, Any] | None = None
    aqi_params = parse.urlencode(
        {
            "latitude": f"{city.latitude:.5f}",
            "longitude": f"{city.longitude:.5f}",
            "timezone": city.timezone or "auto",
            "hourly": ",".join(
                [
                    "us_aqi",
                    "alder_pollen",
                    "birch_pollen",
                    "grass_pollen",
                    "mugwort_pollen",
                    "olive_pollen",
                    "ragweed_pollen",
                ]
            ),
        }
    )
    try:
        candidate = _get_json(f"{AIR_QUALITY_API}?{aqi_params}", timeout=5.0)
        if isinstance(candidate, dict):
            air_payload = candidate
    except Exception:
        air_payload = None

    return _parse_open_meteo_payload(city, payload, air_payload)


def _parse_open_meteo_payload(
    city: WeatherCity,
    payload: dict[str, Any],
    air_payload: dict[str, Any] | None = None,
) -> WeatherForecast | None:
    current_payload = payload.get("current", {})
    daily_payload = payload.get("daily", {})
    if not isinstance(current_payload, dict) or not isinstance(daily_payload, dict):
        return None

    weather_code = int(current_payload.get("weather_code", -1))
    is_day = bool(int(current_payload.get("is_day", 1)))
    sunrise_list = daily_payload.get("sunrise", [])
    sunset_list = daily_payload.get("sunset", [])
    sunrise_iso = (
        str(sunrise_list[0])
        if isinstance(sunrise_list, list) and sunrise_list and str(sunrise_list[0]).strip()
        else ""
    )
    sunset_iso = (
        str(sunset_list[0])
        if isinstance(sunset_list, list) and sunset_list and str(sunset_list[0]).strip()
        else ""
    )

    current = WeatherCurrent(
        observed_time_iso=str(current_payload.get("time", "")).strip(),
        temperature=float(current_payload.get("temperature_2m", 0.0)),
        apparent_temperature=float(current_payload.get("apparent_temperature", 0.0)),
        humidity=int(current_payload.get("relative_humidity_2m", 0)),
        wind_speed=float(current_payload.get("wind_speed_10m", 0.0)),
        precipitation=float(current_payload.get("precipitation", 0.0)),
        pressure=float(current_payload.get("pressure_msl", 0.0)),
        weather_code=weather_code,
        is_day=is_day,
        condition=weather_condition_label(weather_code),
        icon_name=_current_icon_name(weather_code, is_day),
        sunrise_iso=sunrise_iso,
        sunset_iso=sunset_iso,
        sunrise=_fmt_time(sunrise_iso) if sunrise_iso else "--:--",
        sunset=_fmt_time(sunset_iso) if sunset_iso else "--:--",
    )

    daily: list[WeatherDaily] = []
    dates = daily_payload.get("time", [])
    codes = daily_payload.get("weather_code", [])
    maxes = daily_payload.get("temperature_2m_max", [])
    mins = daily_payload.get("temperature_2m_min", [])
    precip = daily_payload.get("precipitation_probability_max", [])
    if all(isinstance(item, list) for item in (dates, codes, maxes, mins, precip)):
        for index, iso_date in enumerate(dates[:7]):
            try:
                date_value = datetime.fromisoformat(str(iso_date))
                code_value = int(codes[index])
                max_value = float(maxes[index])
                min_value = float(mins[index])
                precip_value = int(float(precip[index]))
            except Exception:
                continue
            daily.append(
                WeatherDaily(
                    date=str(iso_date),
                    weekday="Today" if index == 0 else date_value.strftime("%a"),
                    weather_code=code_value,
                    icon_name=_daily_icon_name(code_value),
                    max_temp=max_value,
                    min_temp=min_value,
                    precipitation_probability=precip_value,
                )
            )

    hourly_payload = payload.get("hourly", {})
    hourly: list[WeatherHourly] = []
    reference_time = None
    try:
        reference_time = datetime.fromisoformat(current.observed_time_iso)
    except Exception:
        reference_time = None
    if isinstance(hourly_payload, dict):
        hourly_times = hourly_payload.get("time", [])
        hourly_temp = hourly_payload.get("temperature_2m", [])
        hourly_apparent = hourly_payload.get("apparent_temperature", [])
        hourly_wind = hourly_payload.get("wind_speed_10m", [])
        hourly_gusts = hourly_payload.get("wind_gusts_10m", [])
        hourly_visibility = hourly_payload.get("visibility", [])
        hourly_uv = hourly_payload.get("uv_index", [])
        hourly_codes = hourly_payload.get("weather_code", [])
        hourly_probability = hourly_payload.get("precipitation_probability", [])
        hourly_precip = hourly_payload.get("precipitation", [])
        hourly_rain = hourly_payload.get("rain", [])
        hourly_snowfall = hourly_payload.get("snowfall", [])
        aqi_by_time: dict[str, int | None] = {}
        pollen_by_time: dict[str, float | None] = {}
        if isinstance(air_payload, dict):
            aqi_hourly = air_payload.get("hourly", {})
            if isinstance(aqi_hourly, dict):
                aqi_times = aqi_hourly.get("time", [])
                aqi_values = aqi_hourly.get("us_aqi", [])
                alder = aqi_hourly.get("alder_pollen", [])
                birch = aqi_hourly.get("birch_pollen", [])
                grass = aqi_hourly.get("grass_pollen", [])
                mugwort = aqi_hourly.get("mugwort_pollen", [])
                olive = aqi_hourly.get("olive_pollen", [])
                ragweed = aqi_hourly.get("ragweed_pollen", [])
                if isinstance(aqi_times, list):
                    aqi_size = min(
                        len(aqi_times),
                        len(aqi_values) if isinstance(aqi_values, list) else 0,
                    )
                    for index in range(aqi_size):
                        time_key = str(aqi_times[index]).strip()
                        if not time_key:
                            continue
                        try:
                            aqi_value = int(float(aqi_values[index]))
                        except Exception:
                            aqi_value = None
                        aqi_by_time[time_key] = aqi_value
                    pollen_lists: list[list[object]] = []
                    for values in (alder, birch, grass, mugwort, olive, ragweed):
                        if isinstance(values, list):
                            pollen_lists.append(values)
                    for index, time_value in enumerate(aqi_times):
                        time_key = str(time_value).strip()
                        if not time_key:
                            continue
                        pollen_samples: list[float] = []
                        for samples in pollen_lists:
                            if index >= len(samples):
                                continue
                            try:
                                pollen_samples.append(float(samples[index]))
                            except Exception:
                                continue
                        pollen_by_time[time_key] = (
                            max(pollen_samples) if pollen_samples else None
                        )
        if all(
            isinstance(item, list)
            for item in (
                hourly_times,
                hourly_temp,
                hourly_apparent,
                hourly_wind,
                hourly_gusts,
                hourly_visibility,
                hourly_uv,
                hourly_codes,
                hourly_probability,
                hourly_precip,
                hourly_rain,
                hourly_snowfall,
            )
        ):
            size = min(
                len(hourly_times),
                len(hourly_temp),
                len(hourly_apparent),
                len(hourly_wind),
                len(hourly_gusts),
                len(hourly_visibility),
                len(hourly_uv),
                len(hourly_codes),
                len(hourly_probability),
                len(hourly_precip),
                len(hourly_rain),
                len(hourly_snowfall),
                48,
            )
            for index in range(size):
                try:
                    time_iso = str(hourly_times[index]).strip()
                    if not time_iso:
                        continue
                    timestamp = datetime.fromisoformat(time_iso)
                    temperature_value = float(hourly_temp[index])
                    apparent_value = float(hourly_apparent[index])
                    wind_value = float(hourly_wind[index])
                    gust_value = float(hourly_gusts[index])
                    visibility_value = float(hourly_visibility[index])
                    uv_value = float(hourly_uv[index])
                    code_value = int(hourly_codes[index])
                    probability_value = int(float(hourly_probability[index]))
                    precip_value = float(hourly_precip[index])
                    rain_value = float(hourly_rain[index])
                    snowfall_value = float(hourly_snowfall[index])
                    minutes_from_current = 0
                    if reference_time is not None:
                        minutes_from_current = int(
                            (timestamp - reference_time).total_seconds() // 60
                        )
                except Exception:
                    continue
                hourly.append(
                    WeatherHourly(
                        time_iso=time_iso,
                        weather_code=code_value,
                        icon_name=_current_icon_name(code_value, True),
                        temperature=temperature_value,
                        apparent_temperature=apparent_value,
                        wind_speed=wind_value,
                        wind_gusts=gust_value,
                        visibility=visibility_value,
                        uv_index=uv_value,
                        rain=rain_value,
                        snowfall=snowfall_value,
                        precipitation_probability=probability_value,
                        precipitation=precip_value,
                        us_aqi=aqi_by_time.get(time_iso),
                        pollen_index=pollen_by_time.get(time_iso),
                        minutes_from_current=minutes_from_current,
                    )
                )

    return WeatherForecast(city=city, current=current, daily=daily, hourly=hourly)


def _fetch_openweather(city: WeatherCity, api_key: str) -> WeatherForecast | None:
    params = parse.urlencode(
        {
            "lat": f"{city.latitude:.5f}",
            "lon": f"{city.longitude:.5f}",
            "appid": api_key,
            "units": "metric",
            "exclude": "minutely",
        }
    )
    try:
        payload = _get_json(f"{OPENWEATHER_API}?{params}", timeout=5.0)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    current_data = payload.get("current", {})
    if not isinstance(current_data, dict):
        return None

    owm_id = 800
    owm_desc = "Unknown"
    owm_weather = current_data.get("weather", [])
    if isinstance(owm_weather, list) and owm_weather:
        first = owm_weather[0]
        if isinstance(first, dict):
            owm_id = int(first.get("id", 800))
            owm_desc = str(first.get("description", "Unknown"))

    weather_code = _OPENWEATHER_CODE_MAP.get(owm_id, 0)
    is_day = bool(current_data.get("dt", 0)) and not _is_night_openweather(
        current_data, payload.get("daily", [])
    )
    sunrise_ts = current_data.get("sunrise", 0)
    sunset_ts = current_data.get("sunset", 0)
    sunrise_iso = _ts_to_iso(sunrise_ts)
    sunset_iso = _ts_to_iso(sunset_ts)

    current = WeatherCurrent(
        observed_time_iso=_ts_to_iso(current_data.get("dt", 0)),
        temperature=float(current_data.get("temp", 0.0)),
        apparent_temperature=float(current_data.get("feels_like", 0.0)),
        humidity=int(current_data.get("humidity", 0)),
        wind_speed=float(current_data.get("wind_speed", 0.0)) * 3.6,
        precipitation=float(
            (current_data.get("rain") or {}).get("1h", 0.0)
        ),
        pressure=float(current_data.get("pressure", 0.0)),
        weather_code=weather_code,
        is_day=is_day,
        condition=weather_condition_label(weather_code),
        icon_name=_current_icon_name(weather_code, is_day),
        sunrise_iso=sunrise_iso,
        sunset_iso=sunset_iso,
        sunrise=_fmt_time(sunrise_iso) if sunrise_iso else "--:--",
        sunset=_fmt_time(sunset_iso) if sunset_iso else "--:--",
    )

    daily: list[WeatherDaily] = []
    daily_list = payload.get("daily", [])
    if isinstance(daily_list, list):
        for index, day_data in enumerate(daily_list[:7]):
            if not isinstance(day_data, dict):
                continue
            try:
                day_weather = day_data.get("weather", [{}])
                day_owm_id = 800
                if isinstance(day_weather, list) and day_weather:
                    day_owm_id = int(day_weather[0].get("id", 800))
                day_code = _OPENWEATHER_CODE_MAP.get(day_owm_id, 0)
                day_dt = day_data.get("dt", 0)
                date_value = datetime.fromtimestamp(day_dt)
                temp_data = day_data.get("temp", {})
                daily.append(
                    WeatherDaily(
                        date=date_value.strftime("%Y-%m-%d"),
                        weekday="Today" if index == 0 else date_value.strftime("%a"),
                        weather_code=day_code,
                        icon_name=_daily_icon_name(day_code),
                        max_temp=float(temp_data.get("max", 0.0)),
                        min_temp=float(temp_data.get("min", 0.0)),
                        precipitation_probability=int(float(day_data.get("pop", 0)) * 100),
                    )
                )
            except Exception:
                continue

    hourly: list[WeatherHourly] = []
    hourly_list = payload.get("hourly", [])
    if isinstance(hourly_list, list):
        for index, hour_data in enumerate(hourly_list[:48]):
            if not isinstance(hour_data, dict):
                continue
            try:
                h_weather = hour_data.get("weather", [{}])
                h_owm_id = 800
                if isinstance(h_weather, list) and h_weather:
                    h_owm_id = int(h_weather[0].get("id", 800))
                h_code = _OPENWEATHER_CODE_MAP.get(h_owm_id, 0)
                h_dt = hour_data.get("dt", 0)
                h_iso = _ts_to_iso(h_dt)
                h_timestamp = datetime.fromtimestamp(h_dt)
                h_rain = float((hour_data.get("rain") or {}).get("1h", 0.0))
                h_snow = float((hour_data.get("snow") or {}).get("1h", 0.0))
                minutes_from_current = 0
                try:
                    ref = datetime.fromisoformat(current.observed_time_iso)
                    minutes_from_current = int((h_timestamp - ref).total_seconds() // 60)
                except Exception:
                    pass
                hourly.append(
                    WeatherHourly(
                        time_iso=h_iso,
                        weather_code=h_code,
                        icon_name=_current_icon_name(h_code, True),
                        temperature=float(hour_data.get("temp", 0.0)),
                        apparent_temperature=float(hour_data.get("feels_like", 0.0)),
                        wind_speed=float(hour_data.get("wind_speed", 0.0)) * 3.6,
                        wind_gusts=float(hour_data.get("wind_gust", 0.0)) * 3.6,
                        visibility=float(hour_data.get("visibility", 10000)),
                        uv_index=float(hour_data.get("uvi", 0.0)),
                        rain=h_rain,
                        snowfall=h_snow,
                        precipitation_probability=int(float(hour_data.get("pop", 0)) * 100),
                        precipitation=h_rain + h_snow,
                        us_aqi=None,
                        pollen_index=None,
                        minutes_from_current=minutes_from_current,
                    )
                )
            except Exception:
                continue

    return WeatherForecast(city=city, current=current, daily=daily, hourly=hourly)


def _ts_to_iso(ts: int | float) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).isoformat()
    except Exception:
        return ""


def _is_night_openweather(current: dict, daily: list) -> bool:
    dt = int(current.get("dt", 0))
    sunrise = int(current.get("sunrise", 0))
    sunset = int(current.get("sunset", 0))
    if sunrise and sunset:
        return dt < sunrise or dt > sunset
    if isinstance(daily, list) and daily:
        today = daily[0]
        if isinstance(today, dict):
            s = int(today.get("sunrise", 0))
            e = int(today.get("sunset", 0))
            if s and e:
                return dt < s or dt > e
    return False


def _fetch_wttr(city: WeatherCity) -> WeatherForecast | None:
    params = parse.urlencode({"format": "j1"})
    url = f"{WTTR_API}/{city.latitude:.5f},{city.longitude:.5f}?{params}"
    try:
        payload = _get_json(url, timeout=5.0)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    cc_list = payload.get("current_condition", [])
    if not isinstance(cc_list, list) or not cc_list:
        return None
    cc = cc_list[0]
    if not isinstance(cc, dict):
        return None

    wttr_code = int(cc.get("weatherCode", 113))
    weather_code = _WTTR_CODE_MAP.get(wttr_code, 0)
    is_day = str(cc.get("is_day", "yes")).lower() == "yes"

    weather_days = payload.get("weather", [])
    sunrise_iso = ""
    sunset_iso = ""
    if isinstance(weather_days, list) and weather_days:
        today = weather_days[0]
        if isinstance(today, dict):
            astr = today.get("astronomy", [{}])
            if isinstance(astr, list) and astr:
                ast = astr[0]
                if isinstance(ast, dict):
                    sunrise_raw = str(ast.get("sunrise", "")).strip()
                    sunset_raw = str(ast.get("sunset", "")).strip()
                    today_date = str(today.get("date", "")).strip()
                    if sunrise_raw and today_date:
                        sunrise_iso = f"{today_date}T{_parse_12h_to_24h(sunrise_raw)}"
                    if sunset_raw and today_date:
                        sunset_iso = f"{today_date}T{_parse_12h_to_24h(sunset_raw)}"

    current = WeatherCurrent(
        observed_time_iso=str(cc.get("observation_time", "")).strip(),
        temperature=float(cc.get("temp_C", 0.0)),
        apparent_temperature=float(cc.get("FeelsLikeC", 0.0)),
        humidity=int(cc.get("humidity", 0)),
        wind_speed=float(cc.get("windspeedKmph", 0.0)),
        precipitation=float(cc.get("precipMM", 0.0)),
        pressure=float(cc.get("pressure", 0.0)),
        weather_code=weather_code,
        is_day=is_day,
        condition=weather_condition_label(weather_code),
        icon_name=_current_icon_name(weather_code, is_day),
        sunrise_iso=sunrise_iso,
        sunset_iso=sunset_iso,
        sunrise=_fmt_time(sunrise_iso) if sunrise_iso else "--:--",
        sunset=_fmt_time(sunset_iso) if sunset_iso else "--:--",
    )

    daily: list[WeatherDaily] = []
    if isinstance(weather_days, list):
        for index, day_data in enumerate(weather_days[:7]):
            if not isinstance(day_data, dict):
                continue
            try:
                date_str = str(day_data.get("date", ""))
                date_value = datetime.fromisoformat(date_str)
                day_wttr = int(day_data.get("hourly", [{}])[4].get("weatherCode", 113)) if day_data.get("hourly") else 113
                day_code = _WTTR_CODE_MAP.get(day_wttr, 0)
                daily.append(
                    WeatherDaily(
                        date=date_str,
                        weekday="Today" if index == 0 else date_value.strftime("%a"),
                        weather_code=day_code,
                        icon_name=_daily_icon_name(day_code),
                        max_temp=float(day_data.get("maxtempC", 0.0)),
                        min_temp=float(day_data.get("mintempC", 0.0)),
                        precipitation_probability=int(
                            day_data.get("hourly", [{}])[4].get("chanceofrain", 0)
                            if day_data.get("hourly")
                            else 0
                        ),
                    )
                )
            except Exception:
                continue

    hourly: list[WeatherHourly] = []
    reference_time = None
    try:
        reference_time = datetime.fromisoformat(current.observed_time_iso)
    except Exception:
        reference_time = None
    if isinstance(weather_days, list):
        for day_data in weather_days[:3]:
            if not isinstance(day_data, dict):
                continue
            date_str = str(day_data.get("date", ""))
            hours = day_data.get("hourly", [])
            if not isinstance(hours, list):
                continue
            for h in hours:
                if not isinstance(h, dict):
                    continue
                try:
                    time_val = int(h.get("time", 0))
                    hour = time_val // 100
                    minute = time_val % 100
                    h_iso = f"{date_str}T{hour:02d}:{minute:02d}:00"
                    h_timestamp = datetime.fromisoformat(h_iso)
                    h_wttr = int(h.get("weatherCode", 113))
                    h_code = _WTTR_CODE_MAP.get(h_wttr, 0)
                    h_rain = float(h.get("precipMM", 0.0))
                    h_visibility = float(h.get("visibility", 10.0)) * 1000
                    minutes_from_current = 0
                    if reference_time is not None:
                        minutes_from_current = int(
                            (h_timestamp - reference_time).total_seconds() // 60
                        )
                    hourly.append(
                        WeatherHourly(
                            time_iso=h_iso,
                            weather_code=h_code,
                            icon_name=_current_icon_name(h_code, True),
                            temperature=float(h.get("tempC", 0.0)),
                            apparent_temperature=float(h.get("FeelsLikeC", 0.0)),
                            wind_speed=float(h.get("windspeedKmph", 0.0)),
                            wind_gusts=float(h.get("WindGustKmph", 0.0)),
                            visibility=h_visibility,
                            uv_index=float(h.get("uvIndex", 0.0)),
                            rain=h_rain,
                            snowfall=0.0,
                            precipitation_probability=int(float(h.get("chanceofrain", 0))),
                            precipitation=h_rain,
                            us_aqi=None,
                            pollen_index=None,
                            minutes_from_current=minutes_from_current,
                        )
                    )
                except Exception:
                    continue

    return WeatherForecast(city=city, current=current, daily=daily, hourly=hourly)


def _parse_12h_to_24h(time_str: str) -> str:
    cleaned = time_str.strip().upper()
    is_pm = "PM" in cleaned
    is_am = "AM" in cleaned
    cleaned = cleaned.replace("AM", "").replace("PM", "").strip()
    parts = cleaned.split(":")
    if len(parts) != 2:
        return cleaned
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return cleaned
    if is_pm and hour != 12:
        hour += 12
    elif is_am and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def fetch_forecast(city: WeatherCity) -> WeatherForecast | None:
    owm_key = _load_weather_api_key("openweathermap")
    if owm_key:
        forecast = _fetch_openweather(city, owm_key)
        if forecast is not None:
            return forecast
    forecast = _fetch_open_meteo(city)
    if forecast is not None:
        return forecast
    return _fetch_wttr(city)


def load_cached_forecast(city: WeatherCity) -> WeatherForecast | None:
    """Load the last forecast written by the plugin weather cache daemon.

    Returns a parsed WeatherForecast if the cache exists and matches the
    requested city, or None if the cache is missing / stale / wrong city.
    """
    cached = _load_service_weather_cache(city)
    if cached is None:
        return None
    air_payload: dict[str, Any] | None = None
    return _parse_open_meteo_payload(city, cached, air_payload)


def cache_age_seconds() -> float | None:
    """Return how many seconds have passed since the cache was last written.

    Returns None if the cache file does not exist or cannot be read.
    """
    try:
        raw = json.loads(SERVICE_WEATHER_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    updated = str(raw.get("updated_at", "")).strip()
    if not updated:
        return None
    try:
        from datetime import datetime, timezone
        ts = datetime.fromisoformat(updated)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        return max(0.0, delta.total_seconds())
    except Exception:
        return None


def animated_icon_path(name: str) -> Path:
    fallback_name = ANIMATED_ICON_FALLBACKS.get(name, "")
    if fallback_name:
        fallback = WEATHER_ICON_DIR / "fill" / "svg" / f"{fallback_name}.svg"
        if fallback.exists():
            return fallback
    preferred = WEATHER_ICON_DIR / "fill" / "svg" / f"{name}.svg"
    if preferred.exists():
        return preferred
    return WEATHER_ICON_DIR / "fill" / "svg" / "not-available.svg"


def static_icon_path(name: str) -> Path:
    return WEATHER_ICON_DIR / "monochrome" / "svg-static" / f"{name}.svg"


class AnimatedWeatherIcon(QWidget):
    clicked = pyqtSignal()

    def __init__(self, size: int = 24, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(self)
        self._renderer.repaintNeeded.connect(self.update)
        self._size = size
        self._tint: QColor | None = None
        self.setFixedSize(size, size)

    def set_icon_path(self, path: Path) -> None:
        if path.exists():
            self._renderer.load(str(path))
        else:
            self._renderer.load(b"")
        self.update()

    def set_tint(self, color: QColor | None) -> None:
        self._tint = color
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if not self._renderer.isValid():
            return
        painter = QPainter(self)
        self._renderer.render(painter, QRectF(self.rect()))
        if self._tint is not None:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(self.rect(), self._tint)
        painter.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)
