#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib import request


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
RSS_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "rss"
RSS_CACHE_FILE = RSS_STATE_DIR / "cache.json"


def load_settings_state() -> dict:
    default = {
        "rss": {
            "feed_urls": "",
            "opml_source": "",
            "username": "",
            "password": "",
            "item_limit": 10,
            "check_interval_minutes": 15,
            "notify_new_items": True,
        },
        "services": {
            "rss_widget": {
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
    rss = payload.get("rss", {})
    if isinstance(rss, dict):
        default["rss"].update(rss)
    services = payload.get("services", {})
    if isinstance(services, dict):
        current = services.get("rss_widget", {})
        if isinstance(current, dict):
            default["services"]["rss_widget"].update(current)
    return default


def auth_headers(username: str, password: str) -> dict[str, str]:
    if not username and not password:
        return {}
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def fetch_text(source: str, username: str = "", password: str = "") -> str:
    source = source.strip()
    if not source:
        return ""
    if source.startswith(("http://", "https://")):
        req = request.Request(
            source,
            headers={
                "User-Agent": "HanautaRSS/1.0",
                **auth_headers(username, password),
            },
        )
        with request.urlopen(req, timeout=15) as response:
            return response.read().decode("utf-8", errors="replace")
    path = Path(source).expanduser()
    return path.read_text(encoding="utf-8")


def parse_opml_urls(raw: str) -> list[str]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    urls: list[str] = []
    for outline in root.findall(".//outline"):
        url = (outline.attrib.get("xmlUrl") or "").strip()
        if url:
            urls.append(url)
    return urls


def _feed_text(node, *names: str) -> str:
    for name in names:
        value = node.findtext(name)
        if value:
            return value.strip()
        value = node.findtext(f"{{*}}{name}")
        if value:
            return value.strip()
    return ""


def parse_feed_entries(raw: str, source: str = "") -> list[dict[str, str]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    entries: list[dict[str, str]] = []
    if root.tag.lower().endswith("rss"):
        feed_title = _feed_text(root.find("channel"), "title") if root.find("channel") is not None else ""
        for item in root.findall(".//item"):
            title = _feed_text(item, "title") or "Untitled"
            link = _feed_text(item, "link")
            guid = _feed_text(item, "guid") or link or title
            detail = _feed_text(item, "pubDate", "description")
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "detail": detail,
                    "guid": guid,
                    "feed_title": feed_title or source,
                    "source": source,
                }
            )
    else:
        feed_title = _feed_text(root, "title")
        for item in root.findall(".//{*}entry"):
            title = _feed_text(item, "title") or "Untitled"
            link = ""
            for link_node in item.findall("{*}link"):
                href = (link_node.attrib.get("href") or "").strip()
                if href:
                    link = href
                    break
            guid = _feed_text(item, "id") or link or title
            detail = _feed_text(item, "updated", "published", "summary")
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "detail": detail,
                    "guid": guid,
                    "feed_title": feed_title or source,
                    "source": source,
                }
            )
    return entries


def resolve_feed_sources(settings: dict) -> list[str]:
    rss = settings.get("rss", {})
    if not isinstance(rss, dict):
        return []
    sources: list[str] = []
    raw_urls = str(rss.get("feed_urls", "")).replace("\n", ",")
    for item in raw_urls.split(","):
        url = item.strip()
        if url:
            sources.append(url)
    opml_source = str(rss.get("opml_source", "")).strip()
    if opml_source:
        try:
            opml_raw = fetch_text(opml_source, str(rss.get("username", "")), str(rss.get("password", "")))
            sources.extend(parse_opml_urls(opml_raw))
        except Exception:
            pass
    deduped: list[str] = []
    for url in sources:
        if url not in deduped:
            deduped.append(url)
    return deduped


def collect_entries(settings: dict) -> tuple[list[str], list[dict[str, str]]]:
    rss = settings.get("rss", {})
    username = str(rss.get("username", ""))
    password = str(rss.get("password", ""))
    item_limit = int(rss.get("item_limit", 10))
    sources = resolve_feed_sources(settings)
    collected: list[dict[str, str]] = []
    for source in sources:
        try:
            raw = fetch_text(source, username, password)
            collected.extend(parse_feed_entries(raw, source))
        except Exception:
            continue
        if len(collected) >= item_limit:
            break
    return sources, collected[:item_limit]


def entry_fingerprint(item: dict[str, str]) -> str:
    payload = "||".join(
        [
            str(item.get("feed_title", "")),
            str(item.get("guid", "")),
            str(item.get("link", "")),
            str(item.get("title", "")),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_cache() -> dict:
    try:
        payload = json.loads(RSS_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"seen": [], "last_checked_at": ""}
    if not isinstance(payload, dict):
        return {"seen": [], "last_checked_at": ""}
    seen = payload.get("seen", [])
    if not isinstance(seen, list):
        seen = []
    payload["seen"] = [str(item) for item in seen]
    payload["last_checked_at"] = str(payload.get("last_checked_at", ""))
    return payload


def save_cache(cache: dict) -> None:
    RSS_STATE_DIR.mkdir(parents=True, exist_ok=True)
    trimmed = dict(cache)
    seen = trimmed.get("seen", [])
    if not isinstance(seen, list):
        seen = []
    trimmed["seen"] = [str(item) for item in seen][-400:]
    RSS_CACHE_FILE.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")
