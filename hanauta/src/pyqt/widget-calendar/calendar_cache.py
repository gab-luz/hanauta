#!/usr/bin/env python3
"""One-shot calendar cache fetcher for hanauta-service plugin system.

Called by hanauta-service via hanauta-service-plugin.json. Reads the
configured CalDAV accounts from settings, fetches events, and writes
an atomic JSON cache to ~/.local/state/hanauta/service/calendar_events.json
so the notification center can load data instantly.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request
import xml.etree.ElementTree as ET
import base64

STATE_DIR = Path(
    os.environ.get("HANAUTA_SERVICE_STATE_DIR")
    or os.environ.get("HANAUTA_STATE_DIR")
    or Path.home() / ".local" / "state" / "hanauta",
)
SERVICE_DIR = STATE_DIR / "service"
CALENDAR_CACHE = SERVICE_DIR / "calendar_events.json"
SETTINGS_FILE = Path(
    os.environ.get("HANAUTA_SETTINGS_PATH")
    or STATE_DIR / "notification-center" / "settings.json"
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_settings() -> dict[str, Any]:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _dav_request(
    url: str,
    method: str,
    body: str,
    *,
    depth: str | None = None,
    username: str = "",
    password: str = "",
    timeout: float = 10.0,
) -> tuple[int, str]:
    headers = {
        "User-Agent": "Hanauta/calendar-cache",
        "Accept": "application/xml, text/xml, */*",
        "Content-Type": "text/xml; charset=utf-8",
    }
    if depth is not None:
        headers["Depth"] = depth
    if username or password:
        headers["Authorization"] = _auth_header(username, password)
    data = body.encode("utf-8") if body else None
    current_url = url
    for _ in range(4):
        req = request.Request(current_url, data=data, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                try:
                    text = raw.decode("utf-8", errors="replace")
                except Exception:
                    text = ""
                return int(getattr(resp, "status", 200)), text
        except error.HTTPError as exc:
            code = int(getattr(exc, "code", 0) or 0)
            location = str(exc.headers.get("Location", "") or "").strip()
            if code in {301, 302, 303, 307, 308} and location:
                current_url = parse.urljoin(current_url, location)
                continue
            return code, ""
        except Exception:
            return 0, ""
    return 0, ""


def _parse_vevent(vevent: ET.Element, ns: dict[str, str]) -> dict[str, Any] | None:
    uid_elem = vevent.find("ICAL:uid", ns)
    summary_elem = vevent.find("ICAL:summary", ns)
    dtstart_elem = vevent.find("ICAL:dtstart", ns)
    dtend_elem = vevent.find("ICAL:dtend", ns)
    location_elem = vevent.find("ICAL:location", ns)
    description_elem = vevent.find("ICAL:description", ns)
    rrule_elem = vevent.find("ICAL:rrule", ns)

    if uid_elem is None or summary_elem is None or dtstart_elem is None:
        return None

    uid = uid_elem.text or ""
    summary = summary_elem.text or ""
    location = location_elem.text if location_elem is not None else ""
    description = description_elem.text if description_elem is not None else ""
    rrule = rrule_elem.text if rrule_elem is not None else ""

    dtstart_text = dtstart_elem.text or ""
    dtend_text = dtend_elem.text if dtend_elem is not None else ""

    try:
        if "T" in dtstart_text:
            dtstart = datetime.fromisoformat(dtstart_text.replace("Z", "+00:00"))
        else:
            dtstart = datetime.fromisoformat(dtstart_text + "T00:00:00").replace(tzinfo=timezone.utc)
    except Exception:
        return None

    try:
        if dtend_text:
            if "T" in dtend_text:
                dtend = datetime.fromisoformat(dtend_text.replace("Z", "+00:00"))
            else:
                dtend = datetime.fromisoformat(dtend_text + "T00:00:00").replace(tzinfo=timezone.utc)
        else:
            dtend = dtstart + timedelta(hours=1)
    except Exception:
        dtend = dtstart + timedelta(hours=1)

    return {
        "id": uid,
        "title": summary,
        "start": dtstart.isoformat(),
        "end": dtend.isoformat(),
        "location": location or "",
        "description": description or "",
        "rrule": rrule or "",
        "all_day": "T" not in dtstart_text,
    }


def _fetch_calendar_events(caldav_url: str, username: str, password: str, days: int = 14, limit: int = 50) -> list[dict[str, Any]]:
    now = _now_utc()
    start = now - timedelta(days=1)
    end = now + timedelta(days=days)

    start_str = start.strftime("%Y%m%dT%H%M%SZ")
    end_str = end.strftime("%Y%m%dT%H%M%SZ")

    body = f'''<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:ICAL="http://apple.com/ns/ical/">
  <D:prop>
    <D:getetag />
    <C:calendar-data />
  </D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="{start_str}" end="{end_str}" />
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>'''

    ns = {
        "D": "DAV:",
        "C": "urn:ietf:params:xml:ns:caldav",
        "ICAL": "http://apple.com/ns/ical/",
    }

    code, response_text = _dav_request(
        caldav_url, "REPORT", body, depth="1", username=username, password=password
    )
    if code != 207 and code != 200:
        return []

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError:
        return []

    events: list[dict[str, Any]] = []
    for response in root.findall(".//D:response", ns):
        href = response.find("D:href", ns)
        propstat = response.find("D:propstat", ns)
        if propstat is None:
            continue
        status = propstat.find("D:status", ns)
        if status is None or "200" not in (status.text or ""):
            continue
        prop = propstat.find("D:prop", ns)
        if prop is None:
            continue
        caldata = prop.find("C:calendar-data", ns)
        if caldata is None or caldata.text is None:
            continue

        try:
            cal_root = ET.fromstring(caldata.text)
        except ET.ParseError:
            continue

        for vevent in cal_root.findall(".//ICAL:VEVENT", ns):
            event = _parse_vevent(vevent, ns)
            if event:
                events.append(event)

    events.sort(key=lambda e: e["start"])
    return events[:limit]


def _write_cache(events: list[dict[str, Any]]) -> bool:
    import time as _time

    cache = {
        "events": events,
        "updated_at": _time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "generated_by": "calendar_cache.py",
    }
    try:
        SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        tmp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(SERVICE_DIR),
                prefix="calendar-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(json.dumps(cache, ensure_ascii=True, separators=(",", ":")))
                handle.flush()
                os.fsync(handle.fileno())
                tmp = Path(handle.name)
            os.replace(str(tmp), str(CALENDAR_CACHE))
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def main() -> int:
    settings = _load_settings()
    calendar = settings.get("calendar", {})
    if not isinstance(calendar, dict):
        return 0

    calendars = calendar.get("calendars", [])
    if not isinstance(calendars, list) or not calendars:
        return 0

    all_events: list[dict[str, Any]] = []
    for cal in calendars:
        if not isinstance(cal, dict):
            continue
        if not cal.get("enabled", True):
            continue
        caldav_url = str(cal.get("caldav_url", "")).strip()
        username = str(cal.get("caldav_username", "")).strip()
        password = str(cal.get("caldav_password", ""))
        if not caldav_url or not username:
            continue

        events = _fetch_calendar_events(caldav_url, username, password, days=14, limit=100)
        for event in events:
            event["source"] = "calendar"
            event["calendar_id"] = cal.get("id", "")
        all_events.extend(events)

    all_events.sort(key=lambda e: e["start"])

    ok = _write_cache(all_events[:100])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())