#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib import error, parse, request


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "crypto"
STATE_FILE = STATE_DIR / "tracker.json"
SERVICE_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
SERVICE_CRYPTO_CACHE = SERVICE_STATE_DIR / "crypto.json"
COINGECKO_API = "https://api.coingecko.com/api/v3"


def load_settings_state() -> dict:
    default = {
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
        "services": {
            "crypto_widget": {
                "enabled": True,
                "show_in_notification_center": True,
                "show_in_bar": False,
            }
        },
    }
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default
    crypto = payload.get("crypto", {})
    if isinstance(crypto, dict):
        default["crypto"].update(crypto)
    services = payload.get("services", {})
    if isinstance(services, dict):
        current = services.get("crypto_widget", {})
        if isinstance(current, dict):
            default["services"]["crypto_widget"].update(current)
    return default


def coin_ids(settings: dict) -> list[str]:
    raw = str(settings.get("crypto", {}).get("tracked_coins", "")).replace("\n", ",")
    items: list[str] = []
    for chunk in raw.split(","):
        value = chunk.strip().lower()
        if value and value not in items:
            items.append(value)
    return items


def request_json(url: str, api_key: str = ""):
    headers = {"accept": "application/json", "User-Agent": "HanautaCrypto/1.0"}
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_service_prices(settings: dict) -> dict[str, dict] | None:
    try:
        payload = json.loads(SERVICE_CRYPTO_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("payload", {})
    if not isinstance(raw, dict):
        return None
    crypto = settings.get("crypto", {})
    ids = coin_ids(settings)
    vs_currency = str(crypto.get("vs_currency", "usd")).strip().lower() or "usd"
    cached_currency = str(payload.get("vs_currency", "")).strip().lower()
    tracked = [item.strip().lower() for item in str(payload.get("tracked_coins", "")).split(",") if item.strip()]
    if cached_currency != vs_currency:
        return None
    if tracked != ids:
        return None
    results: dict[str, dict] = {}
    for coin_id in ids:
        item = raw.get(coin_id, {})
        if not isinstance(item, dict):
            continue
        price = item.get(vs_currency)
        if price is None:
            continue
        results[coin_id] = {
            "id": coin_id,
            "price": float(price),
            "change_24h": float(item.get(f"{vs_currency}_24h_change", 0.0) or 0.0),
            "updated_at": int(item.get("last_updated_at", 0) or 0),
            "currency": vs_currency.upper(),
        }
    return results


def fetch_prices(settings: dict) -> dict[str, dict]:
    ids = coin_ids(settings)
    if not ids:
        return {}
    cached = _load_service_prices(settings)
    if cached is not None:
        return cached
    crypto = settings.get("crypto", {})
    vs_currency = str(crypto.get("vs_currency", "usd")).strip().lower() or "usd"
    params = parse.urlencode(
        {
            "ids": ",".join(ids),
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_last_updated_at": "true",
        }
    )
    payload = request_json(
        f"{COINGECKO_API}/simple/price?{params}",
        str(crypto.get("api_key", "")).strip(),
    )
    results: dict[str, dict] = {}
    for coin_id in ids:
        item = payload.get(coin_id, {}) if isinstance(payload, dict) else {}
        if not isinstance(item, dict):
            item = {}
        price = item.get(vs_currency)
        if price is None:
            continue
        results[coin_id] = {
            "id": coin_id,
            "price": float(price),
            "change_24h": float(item.get(f"{vs_currency}_24h_change", 0.0) or 0.0),
            "updated_at": int(item.get("last_updated_at", 0) or 0),
            "currency": vs_currency.upper(),
        }
    return results


def fetch_chart(settings: dict, coin_id: str) -> list[tuple[datetime, float]]:
    crypto = settings.get("crypto", {})
    vs_currency = str(crypto.get("vs_currency", "usd")).strip().lower() or "usd"
    days = max(1, min(90, int(crypto.get("chart_days", 7) or 7)))
    params = parse.urlencode({"vs_currency": vs_currency, "days": str(days), "interval": "hourly"})
    payload = request_json(
        f"{COINGECKO_API}/coins/{parse.quote(coin_id)}/market_chart?{params}",
        str(crypto.get("api_key", "")).strip(),
    )
    prices = payload.get("prices", []) if isinstance(payload, dict) else []
    points: list[tuple[datetime, float]] = []
    for point in prices:
        if not isinstance(point, list) or len(point) < 2:
            continue
        try:
            stamp = datetime.fromtimestamp(float(point[0]) / 1000.0, UTC)
            value = float(point[1])
        except Exception:
            continue
        points.append((stamp, value))
    return points


def load_tracker_state() -> dict:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_prices": {}, "last_checked_at": ""}
    if not isinstance(payload, dict):
        return {"last_prices": {}, "last_checked_at": ""}
    payload.setdefault("last_prices", {})
    payload.setdefault("last_checked_at", "")
    return payload


def save_tracker_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def should_check(last_checked_at: str, interval_minutes: int) -> bool:
    if not last_checked_at:
        return True
    try:
        previous = datetime.fromisoformat(last_checked_at)
    except Exception:
        return True
    return datetime.now(UTC) - previous >= timedelta(minutes=max(1, interval_minutes))


def movement_summary(previous: float, current: float) -> float:
    if previous <= 0:
        return 0.0
    return ((current - previous) / previous) * 100.0


def slug_to_name(slug: str) -> str:
    return slug.replace("-", " ").title()
