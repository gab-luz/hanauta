from __future__ import annotations

import base64
from urllib import error, request, parse


NTFY_USER_AGENT = "Hanauta/ntfy-integration/1.0"


def normalize_ntfy_auth_mode(raw: str | None, has_token: bool = False) -> str:
    value = str(raw or "").strip().lower()
    if value in {"token", "access token", "bearer", "bearer token", "access"}:
        return "token"
    if value in {"basic", "username & password", "username/password", "basic auth"}:
        return "basic"
    if has_token:
        return "token"
    return "basic"


def send_ntfy_message(
    server_url: str,
    topic: str,
    title: str,
    message: str,
    token: str = "",
    username: str = "",
    password: str = "",
    auth_mode: str = "token",
) -> tuple[bool, str]:
    base = (server_url or "").strip().rstrip("/")
    channel = (topic or "").strip()
    if not base:
        return False, "Server URL is required."
    if not channel:
        return False, "Topic is required."
    if not message.strip():
        return False, "Message body is required."
    url = f"{base}/{parse.quote(channel)}"
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Accept": "text/plain, application/json, */*",
        "User-Agent": NTFY_USER_AGENT,
    }
    if title.strip():
        headers["Title"] = title.strip()
    has_token = bool(token.strip())
    auth_mode_clean = normalize_ntfy_auth_mode(auth_mode, has_token=has_token)
    if has_token:
        headers["Authorization"] = f"Bearer {token.strip()}"
    req = request.Request(
        url, data=message.encode("utf-8"), headers=headers, method="POST"
    )
    if not has_token and auth_mode_clean == "basic" and (username.strip() or password):
        credentials = f"{username.strip()}:{password}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {encoded}")
    try:
        with request.urlopen(req, timeout=8) as response:
            response.read()
        return True, "ntfy message sent."
    except error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            detail = ""
        return False, detail or f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

