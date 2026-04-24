from __future__ import annotations

import json
from urllib import error, request


def normalize_ha_url(url: str) -> str:
    return url.strip().rstrip("/")


def fetch_home_assistant_json(
    base_url: str, token: str, path: str
) -> tuple[object | None, str]:
    if not base_url or not token:
        return None, "Home Assistant URL and token are required."
    try:
        req = request.Request(
            f"{normalize_ha_url(base_url)}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=3.5) as response:
            return json.loads(response.read().decode("utf-8")), ""
    except error.HTTPError as exc:
        return None, f"Home Assistant returned HTTP {exc.code}."
    except Exception:
        return None, "Unable to reach Home Assistant."

