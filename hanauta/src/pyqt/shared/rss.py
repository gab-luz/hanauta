#!/usr/bin/env python3
from __future__ import annotations

import base64
import email.utils
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib import request


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
RSS_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "rss"
RSS_CACHE_FILE = RSS_STATE_DIR / "cache.json"


def load_settings_state() -> dict:
    default = {
        "rss": {
            "feeds": [],
            "feed_urls": "",
            "opml_source": "",
            "username": "",
            "password": "",
            "item_limit": 10,
            "check_interval_minutes": 15,
            "notify_new_items": True,
            "play_notification_sound": False,
            "show_feed_name": True,
            "open_in_browser": True,
            "show_images": True,
            "sort_mode": "newest",
            "max_per_feed": 5,
            "view_mode": "expanded",
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
    feeds = default["rss"].get("feeds", [])
    if not isinstance(feeds, list):
        feeds = []
    normalized_feeds: list[dict[str, str]] = []
    for item in feeds:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        normalized_feeds.append(
            {
                "name": str(item.get("name", "")).strip() or url,
                "url": url,
            }
        )
    default["rss"]["feeds"] = normalized_feeds
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


def parse_opml_feeds(raw: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    feeds: list[dict[str, str]] = []
    for outline in root.findall(".//outline"):
        url = (outline.attrib.get("xmlUrl") or "").strip()
        if not url:
            continue
        name = (outline.attrib.get("title") or outline.attrib.get("text") or url).strip()
        feeds.append({"name": name, "url": url})
    return feeds


def _feed_text(node, *names: str) -> str:
    for name in names:
        value = node.findtext(name)
        if value:
            return value.strip()
        value = node.findtext(f"{{*}}{name}")
        if value:
            return value.strip()
    return ""


def _first_attr(node, tag_names: tuple[str, ...], attr: str) -> str:
    for tag_name in tag_names:
        for child in node.findall(f".//{tag_name}"):
            value = (child.attrib.get(attr) or "").strip()
            if value:
                return value
        for child in node.findall(f".//{{*}}{tag_name}"):
            value = (child.attrib.get(attr) or "").strip()
            if value:
                return value
    return ""


def _extract_inline_image(html: str) -> str:
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html or "", re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_rss_image(item, description: str) -> str:
    enclosure = ""
    for child in item.findall("enclosure"):
        url = (child.attrib.get("url") or "").strip()
        if url:
            enclosure = url
            break
    if not enclosure:
        for child in item.findall("{*}content"):
            url = (child.attrib.get("url") or "").strip()
            if url:
                enclosure = url
                break
    if not enclosure:
        for child in item.findall("{*}thumbnail"):
            url = (child.attrib.get("url") or "").strip()
            if url:
                enclosure = url
                break
    return enclosure or _extract_inline_image(description)


def parse_timestamp(raw: str) -> int:
    value = str(raw or "").strip()
    if not value:
        return 0
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed is not None:
            return int(parsed.timestamp())
    except Exception:
        pass
    try:
        normalized = value.replace("Z", "+00:00")
        return int(datetime.fromisoformat(normalized).timestamp())
    except Exception:
        return 0


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
            description = _feed_text(item, "description")
            timestamp = parse_timestamp(_feed_text(item, "pubDate"))
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "detail": detail,
                    "guid": guid,
                    "feed_title": feed_title or source,
                    "source": source,
                    "image_url": _extract_rss_image(item, description),
                    "timestamp": str(timestamp),
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
            updated = _feed_text(item, "updated", "published")
            timestamp = parse_timestamp(updated)
            image_url = _first_attr(item, ("thumbnail", "content"), "url") or _extract_inline_image(_feed_text(item, "summary", "content"))
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "detail": detail,
                    "guid": guid,
                    "feed_title": feed_title or source,
                    "source": source,
                    "image_url": image_url,
                    "timestamp": str(timestamp),
                }
            )
    return entries


def resolve_feed_sources(settings: dict) -> list[dict[str, str]]:
    rss = settings.get("rss", {})
    if not isinstance(rss, dict):
        return []
    sources: list[dict[str, str]] = []
    structured = rss.get("feeds", [])
    if isinstance(structured, list):
        for item in structured:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            sources.append({"name": str(item.get("name", "")).strip() or url, "url": url})
    raw_urls = str(rss.get("feed_urls", "")).replace("\n", ",")
    for item in raw_urls.split(","):
        url = item.strip()
        if url:
            sources.append({"name": url, "url": url})
    opml_source = str(rss.get("opml_source", "")).strip()
    if opml_source:
        try:
            opml_raw = fetch_text(opml_source, str(rss.get("username", "")), str(rss.get("password", "")))
            sources.extend(parse_opml_feeds(opml_raw))
        except Exception:
            pass
    deduped: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in sources:
        url = str(item.get("url", "")).strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append({"name": str(item.get("name", "")).strip() or url, "url": url})
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
            source_url = str(source.get("url", ""))
            source_name = str(source.get("name", "")).strip() or source_url
            raw = fetch_text(source_url, username, password)
            entries = parse_feed_entries(raw, source_name)
            for entry in entries:
                entry["source_url"] = source_url
            collected.extend(entries)
        except Exception:
            continue
        if len(collected) >= item_limit:
            break
    return [str(item.get("url", "")) for item in sources], collected[:item_limit]


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
