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


ROOT = Path(__file__).resolve().parents[4]
ASSETS_DIR = ROOT / "hanauta" / "src" / "assets"
WEATHER_ICON_DIR = ASSETS_DIR / "weather-icons"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

WEATHER_API = "https://api.open-meteo.com/v1/forecast"
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"


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
class WeatherForecast:
    city: WeatherCity
    current: WeatherCurrent
    daily: list[WeatherDaily]


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


def configured_city() -> WeatherCity | None:
    weather = load_weather_settings()
    if not weather or not weather.get("enabled", False):
        return None
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


def _get_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    req = request.Request(url, headers={"User-Agent": "Hanauta Weather/1.0"})
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


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


def fetch_forecast(city: WeatherCity) -> WeatherForecast | None:
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
        }
    )
    try:
        payload = _get_json(f"{WEATHER_API}?{params}", timeout=5.0)
    except Exception:
        return None

    current_payload = payload.get("current", {})
    daily_payload = payload.get("daily", {})
    if not isinstance(current_payload, dict) or not isinstance(daily_payload, dict):
        return None

    weather_code = int(current_payload.get("weather_code", -1))
    is_day = bool(int(current_payload.get("is_day", 1)))
    sunrise_list = daily_payload.get("sunrise", [])
    sunset_list = daily_payload.get("sunset", [])

    current = WeatherCurrent(
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
        sunrise=_fmt_time(str(sunrise_list[0])) if isinstance(sunrise_list, list) and sunrise_list else "--:--",
        sunset=_fmt_time(str(sunset_list[0])) if isinstance(sunset_list, list) and sunset_list else "--:--",
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

    return WeatherForecast(city=city, current=current, daily=daily)


def animated_icon_path(name: str) -> Path:
    return WEATHER_ICON_DIR / "fill" / "svg" / f"{name}.svg"


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
