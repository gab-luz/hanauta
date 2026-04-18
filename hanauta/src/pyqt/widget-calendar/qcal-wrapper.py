#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal CalDAV wrapper used by the notification center and settings page.

This is intentionally dependency-free: it uses basic DAV discovery and a CalDAV
calendar-query REPORT to extract upcoming events.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request
import xml.etree.ElementTree as ET

try:
    import caldav  # type: ignore
    from caldav.collection import Calendar as CaldavCalendar  # type: ignore
except Exception:  # pragma: no cover
    caldav = None
    CaldavCalendar = None  # type: ignore


SETTINGS_FILE = (
    Path.home()
    / ".local"
    / "state"
    / "hanauta"
    / "notification-center"
    / "settings.json"
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _read_settings() -> dict[str, Any]:
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
    timeout: float = 5.0,
) -> tuple[int, str]:
    headers = {
        "User-Agent": "Hanauta/qcal-wrapper",
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
            raise
    raise RuntimeError("Too many redirects.")


def _parse_multistatus(xml_text: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    def tag(ns: str, name: str) -> str:
        return f"{{{ns}}}{name}"

    dav = "DAV:"
    caldav = "urn:ietf:params:xml:ns:caldav"
    items: list[dict[str, Any]] = []
    for response in root.findall(f".//{tag(dav, 'response')}"):
        href = response.findtext(tag(dav, "href")) or ""
        props: dict[str, Any] = {}
        for propstat in response.findall(tag(dav, "propstat")):
            prop = propstat.find(tag(dav, "prop"))
            if prop is None:
                continue
            displayname = prop.findtext(tag(dav, "displayname"))
            if displayname is not None:
                props["displayname"] = displayname
            current_user_principal = prop.find(tag(dav, "current-user-principal"))
            if current_user_principal is not None:
                href_text = current_user_principal.findtext(tag(dav, "href")) or ""
                if href_text:
                    props["current_user_principal"] = href_text
            principal_url = prop.find(tag(dav, "principal-URL"))
            if principal_url is not None:
                href_text = principal_url.findtext(tag(dav, "href")) or ""
                if href_text:
                    props["principal_url"] = href_text
            calendar_home_set = prop.find(tag(caldav, "calendar-home-set"))
            if calendar_home_set is not None:
                href_text = calendar_home_set.findtext(tag(dav, "href")) or ""
                if href_text:
                    props["calendar_home_set"] = href_text
            resourcetype = prop.find(tag(dav, "resourcetype"))
            if resourcetype is not None:
                types = {child.tag for child in resourcetype}
                props["resourcetype"] = types
        if href:
            items.append({"href": href, "props": props})
    return items


def _normalize_url(url: str) -> str:
    normalized = str(url or "").strip()
    if not normalized:
        return ""
    parsed = parse.urlparse(normalized)
    if not parsed.scheme:
        return ""
    # Ensure trailing slash so urljoin() keeps the last path segment.
    # Example: Nextcloud uses ".../remote.php/dav/" and returns relative hrefs.
    if parsed.path and not parsed.path.endswith("/"):
        normalized = normalized + "/"
    return normalized


def _absolute_url(base_url: str, href: str) -> str:
    if not href:
        return ""
    return parse.urljoin(base_url, href)


def discover_calendars(url: str, username: str, password: str) -> list[dict[str, str]]:
    caldav_calendars, caldav_error = _discover_calendars_caldav(url, username, password)
    if caldav_calendars:
        return caldav_calendars
    if caldav_error:
        raise RuntimeError(caldav_error)
    base_url = _normalize_url(url)
    if not base_url:
        return []
    username_token = parse.quote(str(username).strip(), safe="")

    propfind_principal = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:current-user-principal />
    <d:principal-URL />
    <cal:calendar-home-set />
  </d:prop>
</d:propfind>
"""
    props: dict[str, Any] = {}
    principal_url = base_url
    home_url_guess = (
        _absolute_url(base_url, f"calendars/{username_token}/") if username_token else ""
    )
    try:
        _status, xml_text = _dav_request(
            base_url,
            "PROPFIND",
            propfind_principal,
            depth="0",
            username=username,
            password=password,
            timeout=5.5,
        )
        rows = _parse_multistatus(xml_text)
        props = rows[0]["props"] if rows else {}
        principal_href = str(
            props.get("current_user_principal") or props.get("principal_url") or ""
        ).strip()
        principal_url = (
            _absolute_url(base_url, principal_href) if principal_href else base_url
        )
    except error.HTTPError as exc:
        # Nextcloud can forbid probing the root DAV collection, but allow direct principal access.
        if int(getattr(exc, "code", 0) or 0) in {401, 403} and username_token:
            principal_url = _absolute_url(
                base_url, f"principals/users/{username_token}/"
            )
            home_url_guess = _absolute_url(base_url, f"calendars/{username_token}/")
        else:
            raise RuntimeError(f"PROPFIND failed at base URL: {base_url}") from exc
    except Exception as exc:
        raise RuntimeError(f"PROPFIND failed at base URL: {base_url}") from exc

    try:
        _status, principal_xml = _dav_request(
            principal_url,
            "PROPFIND",
            propfind_principal,
            depth="0",
            username=username,
            password=password,
            timeout=5.5,
        )
    except Exception as exc:
        raise RuntimeError(f"PROPFIND failed at principal URL: {principal_url}") from exc
    principal_rows = _parse_multistatus(principal_xml) if principal_xml else []
    principal_props = principal_rows[0]["props"] if principal_rows else {}
    home_href = str(
        principal_props.get("calendar_home_set") or props.get("calendar_home_set") or ""
    ).strip()
    home_url = _absolute_url(base_url, home_href) if home_href else (home_url_guess or base_url)

    propfind_calendars = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:displayname />
    <d:resourcetype />
  </d:prop>
</d:propfind>
"""
    try:
        _status, home_xml = _dav_request(
            home_url,
            "PROPFIND",
            propfind_calendars,
            depth="1",
            username=username,
            password=password,
            timeout=6.5,
        )
    except Exception as exc:
        raise RuntimeError(f"PROPFIND failed at calendar-home URL: {home_url}") from exc
    calendars: list[dict[str, str]] = []
    for row in _parse_multistatus(home_xml):
        href = str(row.get("href", "")).strip()
        props = row.get("props", {}) if isinstance(row.get("props"), dict) else {}
        resourcetype = props.get("resourcetype", set())
        if not isinstance(resourcetype, set):
            resourcetype = set()
        is_calendar = any("urn:ietf:params:xml:ns:caldav" in t and t.endswith("calendar") for t in resourcetype) or any(
            t.endswith("calendar") for t in resourcetype
        )
        if not is_calendar:
            continue
        displayname = str(props.get("displayname", "")).strip() or "Calendar"
        calendars.append(
            {
                "name": displayname,
                "url": _absolute_url(base_url, href),
            }
        )
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in calendars:
        key = str(item.get("url", "")).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _discover_calendars_caldav(
    url: str, username: str, password: str
) -> tuple[list[dict[str, str]], str]:
    if caldav is None:
        return [], "python package 'caldav' is not installed"
    base_url = _normalize_url(url)
    if not base_url or not username or not password:
        return [], "missing url/username/password"
    try:
        client = caldav.DAVClient(
            url=base_url,
            username=username,
            password=password,
            timeout=4,
        )
        principal = (
            client.get_principal() if hasattr(client, "get_principal") else client.principal()
        )
        calendars = (
            principal.get_calendars()
            if hasattr(principal, "get_calendars")
            else principal.calendars()
        )
    except Exception as exc:
        reason = str(exc).strip() or exc.__class__.__name__
        return [], f"caldav library failed to connect: {reason}"
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for cal in calendars or []:
        try:
            name = ""
            if hasattr(cal, "get_display_name"):
                name = str(cal.get_display_name() or "").strip()
            if not name:
                name = str(getattr(cal, "name", "") or "").strip()
            if not name:
                name = "Calendar"
            cal_url = str(getattr(cal, "url", "") or "").strip()
            if not cal_url:
                continue
            if cal_url in seen:
                continue
            seen.add(cal_url)
            results.append({"name": name, "url": cal_url})
        except Exception:
            continue
    if not results:
        return [], "No calendars discovered via caldav library."
    return results, ""


def _unfold_ical_lines(raw: str) -> list[str]:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in lines:
        if not line:
            continue
        if line.startswith(" ") or line.startswith("\t"):
            if unfolded:
                unfolded[-1] += line[1:]
            else:
                unfolded.append(line.lstrip())
        else:
            unfolded.append(line)
    return unfolded


def _parse_ical_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text.removesuffix("Z")
        tz = timezone.utc
    else:
        tz = None
    if len(text) == 8 and text.isdigit():
        try:
            dt = datetime.strptime(text, "%Y%m%d")
            return dt.replace(tzinfo=tz)
        except Exception:
            return None
    try:
        dt = datetime.strptime(text, "%Y%m%dT%H%M%S")
        return dt.replace(tzinfo=tz)
    except Exception:
        return None


def _extract_events_from_ical(ical_text: str, source: str) -> list[dict[str, str]]:
    lines = _unfold_ical_lines(ical_text)
    events: list[dict[str, str]] = []
    inside = False
    current: dict[str, str] = {}
    for line in lines:
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            inside = True
            current = {}
            continue
        if upper == "END:VEVENT":
            inside = False
            title = current.get("SUMMARY", "").strip() or "Untitled event"
            start_raw = current.get("DTSTART", "").strip()
            end_raw = current.get("DTEND", "").strip()
            location = current.get("LOCATION", "").strip()
            start_dt = _parse_ical_datetime(start_raw)
            end_dt = _parse_ical_datetime(end_raw)
            start_iso = (
                start_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                if isinstance(start_dt, datetime) and start_dt.tzinfo is not None
                else (start_dt.isoformat() if isinstance(start_dt, datetime) else start_raw)
            )
            end_iso = (
                end_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                if isinstance(end_dt, datetime) and end_dt.tzinfo is not None
                else (end_dt.isoformat() if isinstance(end_dt, datetime) else end_raw)
            )
            events.append(
                {
                    "title": title,
                    "start": start_iso,
                    "end": end_iso,
                    "location": location,
                    "source": source,
                }
            )
            current = {}
            continue
        if not inside or ":" not in line:
            continue
        key_part, value = line.split(":", 1)
        key = key_part.split(";", 1)[0].strip().upper()
        if key in {"SUMMARY", "DTSTART", "DTEND", "LOCATION"}:
            current[key] = value.strip()
    return events


def _calendar_query_xml(start_utc: datetime, end_utc: datetime) -> str:
    def fmt(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    return f"""<?xml version="1.0" encoding="utf-8" ?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:getetag />
    <c:calendar-data />
  </d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VEVENT">
        <c:time-range start="{fmt(start_utc)}" end="{fmt(end_utc)}" />
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>
"""


def list_events(days: int, limit: int) -> list[dict[str, str]]:
    caldav_events, caldav_error = _list_events_caldav(days, limit)
    if caldav_events:
        return caldav_events
    if caldav_error:
        raise RuntimeError(caldav_error)
    settings = _read_settings()
    calendar = settings.get("calendar", {}) if isinstance(settings, dict) else {}
    calendar = calendar if isinstance(calendar, dict) else {}
    accounts = calendar.get("calendars", [])
    if not isinstance(accounts, list):
        accounts = []
    enabled_accounts: list[dict[str, Any]] = []
    for row in accounts:
        if not isinstance(row, dict):
            continue
        if not bool(row.get("enabled", True)):
            continue
        url = str(row.get("caldav_url", "")).strip()
        username = str(row.get("caldav_username", "")).strip()
        password = str(row.get("caldav_password", ""))
        if not url or not username or not password:
            continue
        enabled_accounts.append({"row": row, "url": url, "username": username, "password": password})
    if not enabled_accounts:
        url = str(calendar.get("caldav_url", "")).strip()
        username = str(calendar.get("caldav_username", "")).strip()
        password = str(calendar.get("caldav_password", ""))
        if url and username and password:
            enabled_accounts.append({"row": {}, "url": url, "username": username, "password": password})

    start = _now_utc()
    end = start + timedelta(days=max(1, int(days)))

    all_events: list[dict[str, str]] = []
    for account in enabled_accounts[:3]:
        url = str(account["url"])
        username = str(account["username"])
        password = str(account["password"])
        calendars = discover_calendars(url, username, password)
        if not calendars:
            continue
        # Pick the first discovered calendar collection for now.
        calendar_url = str(calendars[0].get("url", "")).strip()
        if not calendar_url:
            continue
        body = _calendar_query_xml(start, end)
        try:
            _status, xml_text = _dav_request(
                calendar_url,
                "REPORT",
                body,
                depth="1",
                username=username,
                password=password,
                timeout=6.5,
            )
        except Exception:
            continue

        try:
            root = ET.fromstring(xml_text)
        except Exception:
            continue
        dav = "DAV:"
        caldav = "urn:ietf:params:xml:ns:caldav"
        for caldata in root.findall(f".//{{{caldav}}}calendar-data"):
            ical_text = caldata.text or ""
            if not ical_text.strip():
                continue
            all_events.extend(_extract_events_from_ical(ical_text, calendars[0].get("name", "Calendar")))

    def sort_key(item: dict[str, str]) -> float:
        raw = str(item.get("start", "")).strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return float("inf")

    all_events.sort(key=sort_key)
    return all_events[: max(0, int(limit))]


def _to_iso(value: object) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat()
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        try:
            return f"{int(value.year):04d}-{int(value.month):02d}-{int(value.day):02d}"
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return str(value.isoformat())
        except Exception:
            pass
    return str(value or "").strip()


def _list_events_caldav(days: int, limit: int) -> tuple[list[dict[str, str]], str]:
    if caldav is None:
        return [], "python package 'caldav' is not installed"
    settings = _read_settings()
    calendar = settings.get("calendar", {}) if isinstance(settings, dict) else {}
    calendar = calendar if isinstance(calendar, dict) else {}
    accounts = calendar.get("calendars", [])
    if not isinstance(accounts, list):
        accounts = []
    enabled_accounts: list[dict[str, object]] = []
    for row in accounts:
        if not isinstance(row, dict):
            continue
        if not bool(row.get("enabled", True)):
            continue
        url = str(row.get("caldav_url", "")).strip()
        username = str(row.get("caldav_username", "")).strip()
        password = str(row.get("caldav_password", ""))
        if not url or not username or not password:
            continue
        enabled_accounts.append(
            {
                "row": row,
                "url": url,
                "username": username,
                "password": password,
            }
        )
    if not enabled_accounts:
        url = str(calendar.get("caldav_url", "")).strip()
        username = str(calendar.get("caldav_username", "")).strip()
        password = str(calendar.get("caldav_password", ""))
        if url and username and password:
            enabled_accounts.append(
                {"row": {}, "url": url, "username": username, "password": password}
            )

    # caldav's examples use naive datetimes; Nextcloud servers often behave
    # better with naive UTC values.
    start = datetime.now(timezone.utc).replace(tzinfo=None)
    end = start + timedelta(days=max(1, int(days)))

    events: list[dict[str, str]] = []
    debug_stats = {
        "accounts": 0,
        "calendars": 0,
        "resources": 0,
        "parsed_events": 0,
    }
    for account in enabled_accounts[:3]:
        debug_stats["accounts"] += 1
        account_row = account.get("row", {}) if isinstance(account.get("row"), dict) else {}
        remote_rows = account_row.get("remote_calendars", [])
        remote_calendars: list[dict[str, str]] = []
        if isinstance(remote_rows, list):
            for remote in remote_rows:
                if not isinstance(remote, dict):
                    continue
                remote_url = str(remote.get("url", "")).strip()
                if not remote_url:
                    continue
                remote_calendars.append(
                    {
                        "name": str(remote.get("name", "")).strip() or "Calendar",
                        "url": remote_url,
                    }
                )
        try:
            client = caldav.DAVClient(
                url=_normalize_url(str(account.get("url", ""))),
                username=str(account.get("username", "")),
                password=str(account.get("password", "")),
                timeout=3,
            )
        except Exception:
            continue
        calendars_to_query = []
        if remote_calendars:
            for remote in remote_calendars[:8]:
                try:
                    calendars_to_query.append(
                        CaldavCalendar(
                            client=client,
                            url=str(remote.get("url", "")),
                            name=str(remote.get("name", "")).strip() or None,
                        )
                    )
                except Exception:
                    continue
        else:
            try:
                principal = (
                    client.get_principal() if hasattr(client, "get_principal") else client.principal()
                )
                calendars_to_query = list(
                    principal.get_calendars()
                    if hasattr(principal, "get_calendars")
                    else principal.calendars()
                )
            except Exception as exc:
                reason = str(exc).strip() or exc.__class__.__name__
                return (
                    [],
                    "Unable to load calendars from the CalDAV server. "
                    f"({reason}) Try pressing “Discover calendars” again to cache calendar URLs.",
                )

        if not calendars_to_query:
            if remote_calendars:
                return (
                    [],
                    "Calendar URLs are cached but could not be opened. "
                    "Try “Discover calendars” again.",
                )
            return (
                [],
                "No calendars available for this CalDAV account. "
                "Try “Discover calendars” again.",
            )

        for cal in (calendars_to_query or [])[:6]:
            debug_stats["calendars"] += 1
            try:
                cal_name = ""
                if hasattr(cal, "get_display_name"):
                    cal_name = str(cal.get_display_name() or "").strip()
                if not cal_name:
                    cal_name = str(getattr(cal, "name", "") or "").strip()
                cal_name = cal_name or "Calendar"
                found = (
                    cal.date_search(start=start, end=end, expand="maybe")
                    if hasattr(cal, "date_search")
                    else []
                )
            except Exception:
                continue
            scanned = list(found or [])[: max(12, int(limit) * 4 if limit > 0 else 24)]
            for item in scanned:
                debug_stats["resources"] += 1
                try:
                    ical = getattr(item, "icalendar_instance", None)
                    if ical is None and hasattr(item, "load"):
                        try:
                            item.load(only_if_unloaded=True)
                        except Exception:
                            pass
                        ical = getattr(item, "icalendar_instance", None)
                    if ical is not None:
                        # icalendar.Calendar.walk('VEVENT') returns components with
                        # properties dtstart/dtend/summary/location.
                        vevents = []
                        try:
                            vevents = list(getattr(ical, "walk")("VEVENT"))
                        except Exception:
                            vevents = []
                        for vevent in vevents:
                            try:
                                summary = str(vevent.get("summary", "") or "").strip()
                                location = str(vevent.get("location", "") or "").strip()
                                dtstart_prop = vevent.get("dtstart")
                                dtend_prop = vevent.get("dtend")
                                start_val = getattr(dtstart_prop, "dt", "") if dtstart_prop else ""
                                end_val = getattr(dtend_prop, "dt", "") if dtend_prop else ""
                                title = summary or "Untitled event"
                                events.append(
                                    {
                                        "title": title,
                                        "start": _to_iso(start_val),
                                        "end": _to_iso(end_val),
                                        "location": location,
                                        "source": cal_name,
                                    }
                                )
                                debug_stats["parsed_events"] += 1
                            except Exception:
                                continue
                        continue

                    vobj = getattr(item, "vobject_instance", None)
                    if vobj is None and hasattr(item, "load"):
                        try:
                            item.load(only_if_unloaded=True)
                        except Exception:
                            pass
                        vobj = getattr(item, "vobject_instance", None)
                    vevent = getattr(vobj, "vevent", None) if vobj is not None else None
                    if vevent is None:
                        continue
                    summary = (
                        str(getattr(getattr(vevent, "summary", None), "value", "") or "")
                        .strip()
                    )
                    location = (
                        str(getattr(getattr(vevent, "location", None), "value", "") or "")
                        .strip()
                    )
                    start_val = getattr(getattr(vevent, "dtstart", None), "value", "")
                    end_val = getattr(getattr(vevent, "dtend", None), "value", "")
                    title = summary or "Untitled event"
                    events.append(
                        {
                            "title": title,
                            "start": _to_iso(start_val),
                            "end": _to_iso(end_val),
                            "location": location,
                            "source": cal_name,
                        }
                    )
                    debug_stats["parsed_events"] += 1
                except Exception:
                    continue
            if limit > 0 and len(events) >= max(4, int(limit) * 2):
                break
        if limit > 0 and len(events) >= max(4, int(limit) * 2):
            break

    # Second chance for recurring calendars: force server-side expansion when
    # we got resources but couldn't parse any VEVENT instances.
    if not events and debug_stats["resources"] > 0:
        for account in enabled_accounts[:1]:
            try:
                client = caldav.DAVClient(
                    url=_normalize_url(str(account.get("url", ""))),
                    username=str(account.get("username", "")),
                    password=str(account.get("password", "")),
                    timeout=3,
                )
            except Exception:
                continue
            account_row = (
                account.get("row", {}) if isinstance(account.get("row"), dict) else {}
            )
            remote_rows = account_row.get("remote_calendars", [])
            remote_calendars = []
            if isinstance(remote_rows, list):
                for remote in remote_rows:
                    if not isinstance(remote, dict):
                        continue
                    remote_url = str(remote.get("url", "")).strip()
                    if not remote_url:
                        continue
                    remote_calendars.append(
                        {
                            "name": str(remote.get("name", "")).strip() or "Calendar",
                            "url": remote_url,
                        }
                    )
            calendars_to_query = []
            if remote_calendars:
                for remote in remote_calendars[:4]:
                    try:
                        calendars_to_query.append(
                            CaldavCalendar(
                                client=client,
                                url=str(remote.get("url", "")),
                                name=str(remote.get("name", "")).strip() or None,
                            )
                        )
                    except Exception:
                        continue
            for cal in calendars_to_query[:2]:
                try:
                    cal_name = str(getattr(cal, "name", "") or "").strip() or "Calendar"
                    found = cal.date_search(start=start, end=end, expand=True)
                except Exception:
                    continue
                for item in list(found or [])[: max(10, int(limit) * 3 if limit > 0 else 18)]:
                    try:
                        ical = getattr(item, "icalendar_instance", None)
                        if ical is None and hasattr(item, "load"):
                            try:
                                item.load(only_if_unloaded=True)
                            except Exception:
                                pass
                            ical = getattr(item, "icalendar_instance", None)
                        if ical is None:
                            continue
                        vevents = []
                        try:
                            vevents = list(getattr(ical, "walk")("VEVENT"))
                        except Exception:
                            vevents = []
                        for vevent in vevents:
                            try:
                                summary = str(vevent.get("summary", "") or "").strip()
                                location = str(vevent.get("location", "") or "").strip()
                                dtstart_prop = vevent.get("dtstart")
                                dtend_prop = vevent.get("dtend")
                                start_val = getattr(dtstart_prop, "dt", "") if dtstart_prop else ""
                                end_val = getattr(dtend_prop, "dt", "") if dtend_prop else ""
                                events.append(
                                    {
                                        "title": summary or "Untitled event",
                                        "start": _to_iso(start_val),
                                        "end": _to_iso(end_val),
                                        "location": location,
                                        "source": cal_name,
                                    }
                                )
                            except Exception:
                                continue
                    except Exception:
                        continue
                if limit > 0 and len(events) >= max(2, int(limit)):
                    break
            if events:
                break

    def sort_key(item: dict[str, str]) -> float:
        raw = str(item.get("start", "")).strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return float("inf")

    events.sort(key=sort_key)
    if not events:
        return [], (
            "No upcoming events found. "
            f"(accounts={debug_stats['accounts']}, calendars={debug_stats['calendars']}, "
            f"resources={debug_stats['resources']}, parsed={debug_stats['parsed_events']})"
        )
    return events[: max(0, int(limit))], ""


def _print(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="qcal-wrapper.py")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Discover CalDAV calendars")
    discover.add_argument("url")
    discover.add_argument("username")
    discover.add_argument("password")

    list_cmd = sub.add_parser("list", help="List upcoming events")
    list_cmd.add_argument("--days", default="14")
    list_cmd.add_argument("--limit", default="8")

    args = parser.parse_args(argv)
    if args.command == "discover":
        url = str(args.url)
        username = str(args.username)
        password = str(args.password)
        if not _normalize_url(url) or not username or not password:
            _print({"success": False, "error": "Missing URL/username/password.", "calendars": []})
            return 0
        if caldav is None:
            _print(
                {
                    "success": False,
                    "error": "Python dependency 'caldav' is not installed for this environment. Run `uv sync` in ~/.config/i3 (or `pip install caldav`) and restart Hanauta Settings.",
                    "calendars": [],
                }
            )
            return 0
        try:
            calendars = discover_calendars(url, username, password)
        except error.HTTPError as exc:
            _print(
                {
                    "success": False,
                    "error": f"HTTP {exc.code}: {exc.reason} (at {getattr(exc, 'url', '')})",
                    "calendars": [],
                }
            )
            return 0
        except Exception as exc:
            _print({"success": False, "error": str(exc) or "Discovery failed.", "calendars": []})
            return 0
        if not calendars:
            _print(
                {
                    "success": False,
                    "error": "No calendars discovered.",
                    "calendars": [],
                }
            )
            return 0
        _print({"success": True, "calendars": calendars})
        return 0

    if args.command == "list":
        try:
            days = int(str(args.days).strip() or "14")
        except Exception:
            days = 14
        try:
            limit = int(str(args.limit).strip() or "8")
        except Exception:
            limit = 8
        try:
            events = list_events(days, limit)
            _print({"success": True, "events": events})
        except Exception as exc:
            _print(
                {
                    "success": False,
                    "error": str(exc).strip() or "Unable to fetch events.",
                    "events": [],
                }
            )
        return 0

    _print({"success": False, "error": "Unknown command."})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
