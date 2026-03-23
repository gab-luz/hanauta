#!/usr/bin/env python3
from __future__ import annotations

import html
import imaplib
import json
import os
import base64
import shutil
import signal
import smtplib
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage, Message
from email.utils import formataddr, parsedate_to_datetime, parseaddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QFileDialog, QVBoxLayout, QWidget
from pyqt.shared.runtime import entry_command
from pyqt.shared.theme import ThemePalette, load_theme_palette, palette_mtime

try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except Exception:
    Fernet = Any  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]
    CRYPTO_AVAILABLE = False

_chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
for _flag in ("--disable-logging", "--log-level=3"):
    if _flag not in _chromium_flags:
        _chromium_flags = f"{_chromium_flags} {_flag}".strip()
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _chromium_flags
_logging_rules = os.environ.get("QT_LOGGING_RULES", "").strip()
if "qt.qpa.gl=false" not in _logging_rules:
    _logging_rules = f"{_logging_rules};qt.qpa.gl=false".strip(";")
if "qt.rhi.*=false" not in _logging_rules:
    _logging_rules = f"{_logging_rules};qt.rhi.*=false".strip(";")
os.environ["QT_LOGGING_RULES"] = _logging_rules

try:
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    WEBENGINE_AVAILABLE = True
    WEBENGINE_ERROR = ""
except Exception as exc:  # pragma: no cover
    QWebChannel = Any  # type: ignore[assignment]
    QWebEngineSettings = Any  # type: ignore[assignment]
    QWebEngineView = Any  # type: ignore[assignment]
    WEBENGINE_AVAILABLE = False
    WEBENGINE_ERROR = str(exc)


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = APP_DIR.parents[1]
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "email-client"
STORAGE_CONFIG_PATH = STATE_DIR / "storage.json"
KEY_PATH = STATE_DIR / "storage.key"
HTML_PATH = HERE / "code.html"
APP_NAME = "Hanauta Mail"
DEFAULT_SOUND_PATHS = (
    Path("/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"),
    Path("/usr/share/sounds/freedesktop/stereo/message.oga"),
    Path("/usr/share/sounds/freedesktop/stereo/complete.oga"),
)
FOLDER_PREFERENCES = ("INBOX", "Sent", "Drafts", "Archive", "Spam", "Trash")
POLL_FALLBACK_SECONDS = 90
SPAM_FOLDERS = {"spam", "junk", "bulk mail", "bulk", "quarantine"}
SPAM_KEYWORDS = (
    "winner",
    "won",
    "claim now",
    "act now",
    "urgent response",
    "crypto giveaway",
    "double your",
    "guaranteed income",
    "make money fast",
    "loan approved",
    "no credit check",
    "casino",
    "bet now",
    "free gift",
    "gift card",
    "viagra",
    "bitcoin",
    "wallet suspended",
    "password expires",
    "confirm account immediately",
)
REAL_SPAM_THRESHOLD = 5.0
TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_name",
    "utm_reader",
    "gclid",
    "gclsrc",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "vero_conv",
    "vero_id",
    "rb_clickid",
    "s_cid",
    "igshid",
    "si",
}
TRANSPARENT_PIXEL_DATA_URL = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_storage_config() -> dict[str, Any]:
    return {
        "db_path": str(STATE_DIR / "mail.sqlite3"),
        "attachments_dir": str(STATE_DIR / "cache"),
    }


def load_storage_config() -> dict[str, Any]:
    try:
        payload = json.loads(STORAGE_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid storage config")
    except Exception:
        payload = {}
    config = default_storage_config()
    config["db_path"] = str(payload.get("db_path", config["db_path"])).strip() or config["db_path"]
    config["attachments_dir"] = str(payload.get("attachments_dir", config["attachments_dir"])).strip() or config["attachments_dir"]
    return config


def save_storage_config(config: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def resolved_db_path() -> Path:
    return Path(load_storage_config()["db_path"]).expanduser()


DB_PATH = resolved_db_path()


class MailCipher:
    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.enabled = CRYPTO_AVAILABLE
        self._fernet = Fernet(self._load_key()) if self.enabled else None

    def _load_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key + b"\n")
        try:
            os.chmod(self.key_path, 0o600)
        except Exception:
            pass
        return key

    def encrypt_text(self, value: str) -> str:
        if not self._fernet:
            return value
        if not value:
            return ""
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt_text(self, value: str) -> str:
        if not value or not self._fernet:
            return value
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8", errors="ignore")
        except (InvalidToken, ValueError):
            return value

    def encrypt_bytes(self, value: bytes) -> bytes:
        if not self._fernet:
            return value
        if not value:
            return b""
        return self._fernet.encrypt(value)

    def decrypt_bytes(self, value: bytes | str | None) -> bytes:
        if value is None:
            return b""
        if isinstance(value, str):
            value = value.encode("utf-8", errors="ignore")
        if not value or not self._fernet:
            return value
        try:
            return self._fernet.decrypt(value)
        except (InvalidToken, ValueError):
            return value


def json_ready(value: Any) -> Any:
    if isinstance(value, bytes):
        return ""
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    return value


def decode_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "latin-1"):
            try:
                return value.decode(encoding)
            except Exception:
                continue
        return value.decode("utf-8", errors="ignore")
    if not isinstance(value, str):
        value = str(value)
    parts: list[str] = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            for codec in (encoding, "utf-8", "latin-1"):
                if not codec:
                    continue
                try:
                    parts.append(chunk.decode(codec))
                    break
                except Exception:
                    continue
            else:
                parts.append(chunk.decode("utf-8", errors="ignore"))
        else:
            parts.append(chunk)
    return "".join(parts).strip()


def html_to_text(value: str) -> str:
    text = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("</p>", "\n\n").replace("</div>", "\n")
    text = text.replace("&nbsp;", " ")
    text = re_sub(r"<style[\s\S]*?</style>", "", text)
    text = re_sub(r"<script[\s\S]*?</script>", "", text)
    text = re_sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re_sub(r"\r\n?", "\n", text)
    text = re_sub(r"[ \t]+", " ", text)
    text = re_sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def re_sub(pattern: str, replacement: str, value: str) -> str:
    import re

    return re.sub(pattern, replacement, value, flags=re.IGNORECASE)


def clean_tracking_url(url_text: str) -> str:
    raw = str(url_text or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return raw

    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    lowered_host = parsed.netloc.lower()

    for wrapped_key in ("url", "u", "target", "dest", "destination", "redir", "redirect"):
        wrapped_values = query.get(wrapped_key, [])
        if wrapped_values and lowered_host:
            candidate = urllib.parse.unquote(wrapped_values[0])
            if candidate.startswith(("http://", "https://")):
                raw = candidate
                try:
                    parsed = urllib.parse.urlparse(raw)
                    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
                    lowered_host = parsed.netloc.lower()
                except Exception:
                    return raw
                break

    clean_query = [
        (key, value)
        for key, values in query.items()
        for value in values
        if key.lower() not in TRACKING_QUERY_KEYS
    ]
    clean_fragment = "" if parsed.fragment.lower().startswith(("msdynmkt_tracking",)) else parsed.fragment
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urllib.parse.urlencode(clean_query, doseq=True),
            clean_fragment,
        )
    )


def parse_mailto_draft(url_text: str) -> dict[str, Any] | None:
    raw = str(url_text or "").strip()
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception:
        return None
    if parsed.scheme.lower() != "mailto":
        return None

    def _parse_addresses(values: list[str]) -> list[str]:
        addresses: list[str] = []
        for value in values:
            for item in str(value or "").split(","):
                normalized = normalize_email(item)
                if normalized:
                    addresses.append(normalized)
        return addresses

    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    to_values = [urllib.parse.unquote(parsed.path)] if parsed.path else []
    to_values.extend(query.get("to", []))
    subject = str(query.get("subject", [""])[0] or "")
    body = str(query.get("body", [""])[0] or "").replace("\r\n", "\n").replace("\r", "\n")
    return {
        "to": _parse_addresses(to_values),
        "cc": _parse_addresses(query.get("cc", [])),
        "bcc": _parse_addresses(query.get("bcc", [])),
        "subject": subject,
        "body": body,
    }


def email_domain(address: str) -> str:
    value = normalize_email(address)
    if "@" not in value:
        return ""
    return value.rsplit("@", 1)[-1].strip().lower()


def inline_asset_map(msg: Message) -> dict[str, str]:
    assets: dict[str, str] = {}
    for part in msg.walk():
        content_id = str(part.get("Content-ID", "")).strip()
        payload = part.get_payload(decode=True) or b""
        if not content_id or not payload:
            continue
        content_type = (part.get_content_type() or "application/octet-stream").lower()
        token = content_id.strip("<>").strip()
        assets[token] = f"data:{content_type};base64,{base64.b64encode(payload).decode('ascii')}"
    return assets


def prepare_message_html(
    html_body: str,
    msg: Message | None,
    *,
    allow_remote_images: bool = False,
    allow_scripts: bool = False,
) -> tuple[str, dict[str, bool]]:
    if not html_body.strip():
        return "", {"has_remote_images": False, "has_active_content": False}

    import re

    cid_assets = inline_asset_map(msg) if msg is not None else {}
    flags = {
        "has_remote_images": False,
        "has_active_content": bool(
            re.search(r"<script[\s\S]*?</script>|<iframe\b|<object\b|<embed\b|\son[a-z-]+\s*=", html_body, flags=re.IGNORECASE)
        ),
    }
    content = html_body

    def replace_cid(match) -> str:
        quote = match.group(1)
        src = match.group(2).strip()
        if src.lower().startswith("cid:"):
            token = src[4:].strip("<>").strip()
            replacement = cid_assets.get(token, "")
            if replacement:
                return f'src={quote}{replacement}{quote}'
        lowered = src.lower()
        if lowered.startswith(("http://", "https://")):
            flags["has_remote_images"] = True
            if not allow_remote_images:
                safe = html.escape(src, quote=True)
                return (
                    f'src={quote}{TRANSPARENT_PIXEL_DATA_URL}{quote} '
                    f'data-remote-src={quote}{safe}{quote} '
                    f'data-blocked-image={quote}1{quote}'
                )
        return f'src={quote}{html.escape(src, quote=True)}{quote}'

    def replace_href(match) -> str:
        quote = match.group(1)
        href = html.unescape(match.group(2).strip())
        if not href or href.startswith(("#", "mailto:", "tel:")):
            return f'href={quote}{html.escape(href, quote=True)}{quote}'
        cleaned = clean_tracking_url(href)
        return (
            f'href={quote}{html.escape(cleaned, quote=True)}{quote} '
            f'data-original-href={quote}{html.escape(href, quote=True)}{quote} '
            f'data-clean-href={quote}{html.escape(cleaned, quote=True)}{quote}'
        )

    if not allow_scripts:
        content = re_sub(r"<script[\s\S]*?</script>", "", content)
        content = re_sub(r"\son[a-z-]+\s*=\s*(['\"]).*?\1", "", content)
        content = re_sub(r"</?(iframe|object|embed|meta|base)\b[^>]*>", "", content)

    content = re_sub(r'src=(["\'])(.*?)\1', lambda match: replace_cid(match), content)
    content = re_sub(r'href=(["\'])(.*?)\1', lambda match: replace_href(match), content)
    content = re_sub(r"<img\b", '<img loading="lazy" decoding="async" referrerpolicy="no-referrer" ', content)
    return content.strip(), flags


def message_parts(msg: Message) -> tuple[str, str]:
    html_body = ""
    text_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            content_type = (part.get_content_type() or "").lower()
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="ignore")
            except Exception:
                decoded = payload.decode("utf-8", errors="ignore")
            if content_type == "text/html" and not html_body:
                html_body = decoded
            elif content_type == "text/plain" and not text_body:
                text_body = decoded
    else:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        try:
            decoded = payload.decode(charset, errors="ignore")
        except Exception:
            decoded = payload.decode("utf-8", errors="ignore")
        if (msg.get_content_type() or "").lower() == "text/html":
            html_body = decoded
        else:
            text_body = decoded
    if html_body:
        html_body = html_body.strip()
    if not html_body and text_body:
        html_body = "<pre>" + html.escape(text_body) + "</pre>"
    if not text_body and html_body:
        text_body = html_to_text(html_body)
    return html_body.strip(), text_body.strip()


def snippet(text_body: str, html_body: str, limit: int = 180) -> str:
    source = text_body or html_to_text(html_body)
    source = " ".join(source.split())
    if len(source) <= limit:
        return source
    return source[: limit - 1].rstrip() + "..."


def normalize_email(value: str) -> str:
    return parseaddr(value)[1].strip().lower()


def sender_display(name: str, address: str) -> str:
    return name or address or "Unknown Sender"


def parse_date(value: str) -> str:
    raw = decode_text(value)
    if not raw:
        return now_iso()
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        return now_iso()


def display_time(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return ""
    local_dt = dt.astimezone()
    now_local = datetime.now().astimezone()
    if local_dt.date() == now_local.date():
        return local_dt.strftime("%H:%M")
    if local_dt.year == now_local.year:
        return local_dt.strftime("%b %d")
    return local_dt.strftime("%Y-%m-%d")


def build_message_key(account_id: int, folder: str, uid: str) -> str:
    return f"{account_id}|{urllib.parse.quote(folder, safe='')}|{uid}"


def parse_message_key(value: str) -> tuple[int, str, str]:
    account_text, folder_text, uid = value.split("|", 2)
    return int(account_text), urllib.parse.unquote(folder_text), uid


def preferred_sound_path(path_text: str) -> Path | None:
    candidate = Path(path_text).expanduser() if path_text else None
    if candidate and candidate.exists() and candidate.is_file():
        return candidate
    for path in DEFAULT_SOUND_PATHS:
        if path.exists() and path.is_file():
            return path
    return None


def spam_assessment(
    *,
    folder: str,
    subject: str,
    from_email: str,
    body_text: str,
    body_html: str,
) -> tuple[float, bool]:
    lowered_folder = folder.strip().lower()
    if lowered_folder in SPAM_FOLDERS:
        return 1.0, True

    score = 0.0
    haystack = " ".join(
        [
            subject.lower(),
            from_email.lower(),
            body_text.lower(),
            html_to_text(body_html).lower(),
        ]
    )
    for keyword in SPAM_KEYWORDS:
        if keyword in haystack:
            score += 0.12
    if "http://" in haystack:
        score += 0.08
    if len(re_sub(r"[^A-Z]", "", subject)) >= 8 and subject:
        score += 0.14
    if "$" in haystack or "usd" in haystack:
        score += 0.08
    if from_email and any(from_email.lower().endswith(suffix) for suffix in (".ru", ".top", ".xyz", ".click")):
        score += 0.18
    text_len = len((body_text or "").strip())
    html_len = len((body_html or "").strip())
    if html_len > max(400, text_len * 3):
        score += 0.12
    score = max(0.0, min(1.0, score))
    return score, score >= 0.46


def _parse_spamc_score(output: bytes | str) -> tuple[float, bool] | None:
    text = decode_text(output).strip()
    if "/" not in text:
        return None
    left, right = text.split("/", 1)
    try:
        score = float(left.strip())
        threshold = max(0.1, float(right.strip().split()[0]))
    except Exception:
        return None
    return max(0.0, min(1.0, score / threshold)), score >= threshold


def _parse_spamassassin_score(output: bytes | str) -> tuple[float, bool] | None:
    import re

    text = decode_text(output)
    match = re.search(
        r"X-Spam-Status:\s*(Yes|No).*?score=([-\d.]+).*?required=([-\d.]+)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    try:
        score = float(match.group(2))
        threshold = max(0.1, float(match.group(3)))
    except Exception:
        return None
    return max(0.0, min(1.0, score / threshold)), match.group(1).lower() == "yes"


def real_spam_assessment(raw_message: bytes) -> tuple[float, bool] | None:
    if not raw_message:
        return None

    spamc = shutil.which("spamc")
    if spamc:
        try:
            result = subprocess.run(
                [spamc, "-c"],
                input=raw_message,
                capture_output=True,
                timeout=8,
                check=False,
            )
            parsed = _parse_spamc_score(result.stdout or result.stderr)
            if parsed is not None:
                return parsed
        except Exception:
            pass

    spamassassin = shutil.which("spamassassin")
    if spamassassin:
        try:
            result = subprocess.run(
                [spamassassin, "-t"],
                input=raw_message,
                capture_output=True,
                timeout=12,
                check=False,
            )
            parsed = _parse_spamassassin_score(result.stdout or result.stderr)
            if parsed is not None:
                return parsed
        except Exception:
            pass

    return None


@dataclass
class SyncSummary:
    had_new_mail: bool = False
    notifications: list[tuple[str, str]] | None = None


class MailStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.cipher = MailCipher(KEY_PATH)
        self._init_db()

    def _init_db(self) -> None:
        with self.lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    email_address TEXT NOT NULL,
                    display_name TEXT NOT NULL DEFAULT '',
                    avatar_path TEXT NOT NULL DEFAULT '',
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    imap_host TEXT NOT NULL,
                    imap_port INTEGER NOT NULL DEFAULT 993,
                    imap_ssl INTEGER NOT NULL DEFAULT 1,
                    smtp_host TEXT NOT NULL,
                    smtp_port INTEGER NOT NULL DEFAULT 587,
                    smtp_starttls INTEGER NOT NULL DEFAULT 1,
                    smtp_ssl INTEGER NOT NULL DEFAULT 0,
                    folders_json TEXT NOT NULL DEFAULT '[]',
                    folder_state_json TEXT NOT NULL DEFAULT '{}',
                    signature TEXT NOT NULL DEFAULT '',
                    notify_enabled INTEGER NOT NULL DEFAULT 1,
                    poll_interval_seconds INTEGER NOT NULL DEFAULT 90,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    account_id INTEGER NOT NULL,
                    folder TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    message_id TEXT NOT NULL DEFAULT '',
                    in_reply_to TEXT NOT NULL DEFAULT '',
                    references_json TEXT NOT NULL DEFAULT '[]',
                    subject TEXT NOT NULL DEFAULT '',
                    from_name TEXT NOT NULL DEFAULT '',
                    from_email TEXT NOT NULL DEFAULT '',
                    to_line TEXT NOT NULL DEFAULT '',
                    cc_line TEXT NOT NULL DEFAULT '',
                    date_iso TEXT NOT NULL,
                    snippet TEXT NOT NULL DEFAULT '',
                    body_html TEXT NOT NULL DEFAULT '',
                    body_text TEXT NOT NULL DEFAULT '',
                    raw_source BLOB,
                    seen INTEGER NOT NULL DEFAULT 0,
                    flagged INTEGER NOT NULL DEFAULT 0,
                    has_attachments INTEGER NOT NULL DEFAULT 0,
                    spam_score REAL NOT NULL DEFAULT 0.0,
                    is_spam INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (account_id, folder, uid)
                );
                CREATE TABLE IF NOT EXISTS contacts (
                    email TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    usage_count INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self.conn.commit()
            self._ensure_account_column("avatar_path", "TEXT NOT NULL DEFAULT ''")
            self._ensure_message_column("raw_source", "BLOB")
            self._ensure_message_column("spam_score", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_message_column("is_spam", "INTEGER NOT NULL DEFAULT 0")
        self.ensure_setting("selected_account_id", "")
        self.ensure_setting("selected_folder", "INBOX")
        self.ensure_setting("selected_message_key", "")
        self.ensure_setting("search_query", "")
        self.ensure_setting("sound_enabled", "1")
        self.ensure_setting("sound_path", "")
        self.ensure_setting("image_policy_rules", json.dumps({"messages": [], "senders": [], "domains": []}))
        self.ensure_setting("script_policy_rules", json.dumps({"messages": [], "senders": [], "domains": []}))

    def _ensure_message_column(self, column_name: str, definition: str) -> None:
        try:
            columns = {
                str(row["name"])
                for row in self.conn.execute("PRAGMA table_info(messages)").fetchall()
            }
            if column_name not in columns:
                self.conn.execute(f"ALTER TABLE messages ADD COLUMN {column_name} {definition}")
                self.conn.commit()
        except Exception:
            return

    def _ensure_account_column(self, column_name: str, definition: str) -> None:
        try:
            columns = {
                str(row["name"])
                for row in self.conn.execute("PRAGMA table_info(accounts)").fetchall()
            }
            if column_name not in columns:
                self.conn.execute(f"ALTER TABLE accounts ADD COLUMN {column_name} {definition}")
                self.conn.commit()
        except Exception:
            return

    def ensure_setting(self, key: str, value: str) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR IGNORE INTO app_settings(key, value) VALUES(?, ?)",
                (key, value),
            )
            self.conn.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        with self.lock:
            row = self.conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self.conn.commit()

    def get_json_setting(self, key: str, default: dict[str, Any]) -> dict[str, Any]:
        raw = self.get_setting(key, "")
        try:
            payload = json.loads(raw) if raw else default
        except Exception:
            payload = default
        if not isinstance(payload, dict):
            return dict(default)
        return payload

    def set_json_setting(self, key: str, value: dict[str, Any]) -> None:
        self.set_setting(key, json.dumps(value, sort_keys=True))

    def list_accounts(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM accounts ORDER BY lower(label), lower(email_address)"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_account(self, account_id: int) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not row:
            return None
        account = dict(row)
        account["password"] = self.cipher.decrypt_text(str(account.get("password", "")))
        return account

    def save_account(self, payload: dict[str, Any]) -> int:
        now = now_iso()
        values = (
            str(payload.get("label", "")).strip() or str(payload.get("email_address", "")).strip(),
            str(payload.get("email_address", "")).strip(),
            str(payload.get("display_name", "")).strip(),
            str(payload.get("avatar_path", "")).strip(),
            str(payload.get("username", "")).strip(),
            self.cipher.encrypt_text(str(payload.get("password", ""))),
            str(payload.get("imap_host", "")).strip(),
            int(payload.get("imap_port", 993) or 993),
            1 if bool(payload.get("imap_ssl", True)) else 0,
            str(payload.get("smtp_host", "")).strip(),
            int(payload.get("smtp_port", 587) or 587),
            1 if bool(payload.get("smtp_starttls", True)) else 0,
            1 if bool(payload.get("smtp_ssl", False)) else 0,
            str(payload.get("folders_json", "[]")),
            str(payload.get("folder_state_json", "{}")),
            str(payload.get("signature", "")),
            1 if bool(payload.get("notify_enabled", True)) else 0,
            max(30, int(payload.get("poll_interval_seconds", POLL_FALLBACK_SECONDS) or POLL_FALLBACK_SECONDS)),
            now,
        )
        with self.lock:
            account_id = int(payload.get("id", 0) or 0)
            if account_id > 0:
                self.conn.execute(
                    """
                    UPDATE accounts
                    SET label=?, email_address=?, display_name=?, avatar_path=?, username=?, password=?,
                        imap_host=?, imap_port=?, imap_ssl=?, smtp_host=?, smtp_port=?,
                        smtp_starttls=?, smtp_ssl=?, folders_json=?, folder_state_json=?,
                        signature=?, notify_enabled=?, poll_interval_seconds=?, updated_at=?
                    WHERE id=?
                    """,
                    (*values, account_id),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO accounts(
                        label, email_address, display_name, avatar_path, username, password,
                        imap_host, imap_port, imap_ssl, smtp_host, smtp_port,
                        smtp_starttls, smtp_ssl, folders_json, folder_state_json,
                        signature, notify_enabled, poll_interval_seconds, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*values, now),
                )
                account_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            self.conn.commit()
        return account_id

    def delete_account(self, account_id: int) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM messages WHERE account_id = ?", (account_id,))
            self.conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            self.conn.commit()

    def update_account_sync_state(self, account_id: int, folders: list[str], folder_state: dict[str, Any]) -> None:
        with self.lock:
            self.conn.execute(
                "UPDATE accounts SET folders_json = ?, folder_state_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(folders), json.dumps(folder_state), now_iso(), account_id),
            )
            self.conn.commit()

    def store_message(self, account_id: int, folder: str, uid: str, payload: dict[str, Any]) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO messages(
                    account_id, folder, uid, message_id, in_reply_to, references_json,
                    subject, from_name, from_email, to_line, cc_line, date_iso, snippet,
                    body_html, body_text, raw_source, seen, flagged, has_attachments, spam_score, is_spam
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, folder, uid) DO UPDATE SET
                    message_id=excluded.message_id,
                    in_reply_to=excluded.in_reply_to,
                    references_json=excluded.references_json,
                    subject=excluded.subject,
                    from_name=excluded.from_name,
                    from_email=excluded.from_email,
                    to_line=excluded.to_line,
                    cc_line=excluded.cc_line,
                    date_iso=excluded.date_iso,
                    snippet=excluded.snippet,
                    body_html=excluded.body_html,
                    body_text=excluded.body_text,
                    raw_source=excluded.raw_source,
                    seen=excluded.seen,
                    flagged=excluded.flagged,
                    has_attachments=excluded.has_attachments,
                    spam_score=excluded.spam_score,
                    is_spam=excluded.is_spam
                """,
                (
                    account_id,
                    folder,
                    uid,
                    str(payload.get("message_id", "")),
                    str(payload.get("in_reply_to", "")),
                    json.dumps(payload.get("references", [])),
                    str(payload.get("subject", "")),
                    str(payload.get("from_name", "")),
                    str(payload.get("from_email", "")),
                    str(payload.get("to_line", "")),
                    str(payload.get("cc_line", "")),
                    str(payload.get("date_iso", now_iso())),
                    str(payload.get("snippet", "")),
                    self.cipher.encrypt_text(str(payload.get("body_html", ""))),
                    self.cipher.encrypt_text(str(payload.get("body_text", ""))),
                    self.cipher.encrypt_bytes(payload.get("raw_source") or b""),
                    1 if bool(payload.get("seen", False)) else 0,
                    1 if bool(payload.get("flagged", False)) else 0,
                    1 if bool(payload.get("has_attachments", False)) else 0,
                    float(payload.get("spam_score", 0.0) or 0.0),
                    1 if bool(payload.get("is_spam", False)) else 0,
                ),
            )
            self.conn.commit()

    def list_messages(self, account_id: int, folder: str, search: str, limit: int | None = 60) -> list[dict[str, Any]]:
        query = """
            SELECT account_id, folder, uid, subject, from_name, from_email, date_iso, snippet,
                   seen, flagged, has_attachments, is_spam, spam_score
            FROM messages
            WHERE 1 = 1
        """
        params: list[Any] = []
        normalized_folder = folder.strip().lower()
        if account_id > 0:
            query += " AND account_id = ?"
            params.append(account_id)
        if normalized_folder == "spam":
            query += " AND (lower(folder) IN (?, ?, ?, ?, ?) OR is_spam = 1)"
            params.extend(sorted(SPAM_FOLDERS))
        else:
            query += " AND lower(folder) = ?"
            params.append(normalized_folder)
            if normalized_folder == "inbox":
                query += " AND is_spam = 0"
        if search.strip():
            like = f"%{search.strip().lower()}%"
            query += (
                " AND (lower(subject) LIKE ? OR lower(from_name) LIKE ? OR lower(from_email) LIKE ? "
                " OR lower(snippet) LIKE ?)"
            )
            params.extend([like, like, like, like])
        query += " ORDER BY datetime(date_iso) DESC"
        if limit is not None:
            query += f" LIMIT {max(1, int(limit))}"
        with self.lock:
            rows = self.conn.execute(query, params).fetchall()
            account_map = {
                int(row["id"]): str(row["label"])
                for row in self.conn.execute("SELECT id, label FROM accounts").fetchall()
            }
        messages: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["key"] = build_message_key(int(item["account_id"]), str(item["folder"]), str(item["uid"]))
            item["display_time"] = display_time(str(item.get("date_iso", "")))
            item["sender"] = sender_display(str(item.get("from_name", "")), str(item.get("from_email", "")))
            item["account_label"] = account_map.get(int(item["account_id"]), "Mailbox")
            messages.append(item)
        return messages

    def get_message(self, key: str) -> dict[str, Any] | None:
        account_id, folder, uid = parse_message_key(key)
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM messages WHERE account_id = ? AND folder = ? AND uid = ?",
                (account_id, folder, uid),
            ).fetchone()
        if not row:
            return None
        message = dict(row)
        message.pop("raw_source", None)
        message["body_html"] = self.cipher.decrypt_text(str(message.get("body_html", "")))
        message["body_text"] = self.cipher.decrypt_text(str(message.get("body_text", "")))
        message["key"] = key
        message["display_time"] = display_time(str(message.get("date_iso", "")))
        message["sender"] = sender_display(str(message.get("from_name", "")), str(message.get("from_email", "")))
        try:
            message["references"] = json.loads(str(message.get("references_json", "[]")))
        except Exception:
            message["references"] = []
        return message

    def raw_source_for_key(self, key: str) -> bytes:
        account_id, folder, uid = parse_message_key(key)
        with self.lock:
            row = self.conn.execute(
                "SELECT raw_source, subject, from_name, from_email, to_line, cc_line, date_iso, body_text FROM messages WHERE account_id = ? AND folder = ? AND uid = ?",
                (account_id, folder, uid),
            ).fetchone()
        if not row:
            return b""
        raw_source = row["raw_source"]
        if raw_source:
            decrypted = self.cipher.decrypt_bytes(raw_source)
            if decrypted:
                return decrypted
        eml = EmailMessage()
        eml["Subject"] = str(row["subject"] or "")
        if str(row["from_email"] or "").strip():
            eml["From"] = formataddr((str(row["from_name"] or ""), str(row["from_email"] or "")))
        if str(row["to_line"] or "").strip():
            eml["To"] = str(row["to_line"])
        if str(row["cc_line"] or "").strip():
            eml["Cc"] = str(row["cc_line"])
        eml["Date"] = str(row["date_iso"] or "")
        eml.set_content(self.cipher.decrypt_text(str(row["body_text"] or "")))
        return eml.as_bytes()

    def mark_local_seen(self, key: str, seen: bool) -> None:
        account_id, folder, uid = parse_message_key(key)
        with self.lock:
            self.conn.execute(
                "UPDATE messages SET seen = ? WHERE account_id = ? AND folder = ? AND uid = ?",
                (1 if seen else 0, account_id, folder, uid),
            )
            self.conn.commit()

    def delete_local_message(self, key: str) -> None:
        account_id, folder, uid = parse_message_key(key)
        with self.lock:
            self.conn.execute(
                "DELETE FROM messages WHERE account_id = ? AND folder = ? AND uid = ?",
                (account_id, folder, uid),
            )
            self.conn.commit()

    def move_local_message(self, key: str, folder: str) -> str:
        account_id, old_folder, uid = parse_message_key(key)
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM messages WHERE account_id = ? AND folder = ? AND uid = ?",
                (account_id, old_folder, uid),
            ).fetchone()
            if not row:
                return key
            payload = dict(row)
            payload["folder"] = folder
            self.conn.execute(
                "DELETE FROM messages WHERE account_id = ? AND folder = ? AND uid = ?",
                (account_id, old_folder, uid),
            )
            self.conn.execute(
                """
                INSERT INTO messages(account_id, folder, uid, message_id, in_reply_to, references_json,
                                     subject, from_name, from_email, to_line, cc_line, date_iso, snippet,
                                     body_html, body_text, raw_source, seen, flagged, has_attachments, spam_score, is_spam)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    folder,
                    uid,
                    payload["message_id"],
                    payload["in_reply_to"],
                    payload["references_json"],
                    payload["subject"],
                    payload["from_name"],
                    payload["from_email"],
                    payload["to_line"],
                    payload["cc_line"],
                    payload["date_iso"],
                    payload["snippet"],
                    payload["body_html"],
                    payload["body_text"],
                    payload["raw_source"],
                    payload["seen"],
                    payload["flagged"],
                    payload["has_attachments"],
                    payload["spam_score"],
                    payload["is_spam"],
                ),
            )
            self.conn.commit()
        return build_message_key(account_id, folder, uid)

    def upsert_contact(self, name: str, address: str) -> None:
        email_address = normalize_email(address)
        if not email_address:
            return
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO contacts(email, name, usage_count, updated_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(email) DO UPDATE SET
                    name = CASE WHEN excluded.name != '' THEN excluded.name ELSE contacts.name END,
                    usage_count = contacts.usage_count + 1,
                    updated_at = excluded.updated_at
                """,
                (email_address, name.strip(), now_iso()),
            )
            self.conn.commit()

    def list_contacts(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT email, name, usage_count FROM contacts ORDER BY usage_count DESC, lower(name), lower(email) LIMIT 200"
            ).fetchall()
        return [dict(row) for row in rows]

    def unread_counts(self) -> dict[int, dict[str, int]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT account_id, folder, COUNT(*) AS unread_count FROM messages WHERE seen = 0 GROUP BY account_id, folder"
            ).fetchall()
        result: dict[int, dict[str, int]] = {}
        for row in rows:
            result.setdefault(int(row["account_id"]), {})[str(row["folder"])] = int(row["unread_count"])
        return result


class MailBridge(QObject):
    bootstrapRequested = pyqtSignal()
    accountSaveRequested = pyqtSignal(str)
    accountDeleteRequested = pyqtSignal(int)
    searchRequested = pyqtSignal(str)
    selectionRequested = pyqtSignal(str, str, str)
    refreshRequested = pyqtSignal()
    sendRequested = pyqtSignal(str)
    replyRequested = pyqtSignal(str)
    archiveRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)
    seenRequested = pyqtSignal(str, bool)
    settingsRequested = pyqtSignal()
    exportSelectedRequested = pyqtSignal(str)
    exportVisibleRequested = pyqtSignal()
    externalLinkRequested = pyqtSignal(str)
    contentPolicyRequested = pyqtSignal(str, str, str)
    stateChanged = pyqtSignal(str)
    toastRequested = pyqtSignal(str, str)

    @pyqtSlot()
    def bootstrap(self) -> None:
        self.bootstrapRequested.emit()

    @pyqtSlot(str)
    def saveAccount(self, payload_json: str) -> None:
        self.accountSaveRequested.emit(payload_json)

    @pyqtSlot(int)
    def deleteAccount(self, account_id: int) -> None:
        self.accountDeleteRequested.emit(account_id)

    @pyqtSlot(str)
    def setSearch(self, query: str) -> None:
        self.searchRequested.emit(query)

    @pyqtSlot(str, str, str)
    def setSelection(self, account_id: str, folder: str, message_key: str) -> None:
        self.selectionRequested.emit(account_id, folder, message_key)

    @pyqtSlot()
    def refreshNow(self) -> None:
        self.refreshRequested.emit()

    @pyqtSlot(str)
    def sendCompose(self, payload_json: str) -> None:
        self.sendRequested.emit(payload_json)

    @pyqtSlot(str)
    def startReply(self, message_key: str) -> None:
        self.replyRequested.emit(message_key)

    @pyqtSlot(str)
    def archiveMessage(self, message_key: str) -> None:
        self.archiveRequested.emit(message_key)

    @pyqtSlot(str)
    def deleteMessage(self, message_key: str) -> None:
        self.deleteRequested.emit(message_key)

    @pyqtSlot(str, bool)
    def setSeen(self, message_key: str, seen: bool) -> None:
        self.seenRequested.emit(message_key, seen)

    @pyqtSlot()
    def openSettings(self) -> None:
        self.settingsRequested.emit()

    @pyqtSlot(str)
    def exportSelected(self, message_key: str) -> None:
        self.exportSelectedRequested.emit(message_key)

    @pyqtSlot()
    def exportVisible(self) -> None:
        self.exportVisibleRequested.emit()

    @pyqtSlot(str)
    def openExternalLink(self, url: str) -> None:
        self.externalLinkRequested.emit(url)

    @pyqtSlot(str, str, str)
    def setContentPolicy(self, kind: str, scope: str, message_key: str) -> None:
        self.contentPolicyRequested.emit(kind, scope, message_key)


class FragmentServer:
    def __init__(self, app: "EmailClientWindow") -> None:
        self.app = app
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        app = self.app

        class Handler(BaseHTTPRequestHandler):
            def _send_cors_headers(self) -> None:
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")

            def do_OPTIONS(self) -> None:  # type: ignore[override]
                self.send_response(204)
                self._send_cors_headers()
                self.end_headers()

            def do_GET(self) -> None:  # type: ignore[override]
                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                body = app.render_fragment(parsed.path, query)
                if body is None:
                    self.send_error(404)
                    return
                encoded = body.encode("utf-8")
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        return Handler

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class EmailClientWindow(QWidget):
    syncCompleted = pyqtSignal(str, str)

    def __init__(self, launch_targets: list[str] | None = None) -> None:
        super().__init__()
        if not WEBENGINE_AVAILABLE:
            raise RuntimeError(f"QtWebEngine is unavailable: {WEBENGINE_ERROR}")
        self.store = MailStore(DB_PATH)
        self.state_lock = threading.RLock()
        self.selected_account_id = int(self.store.get_setting("selected_account_id", "0") or 0)
        self.selected_folder = self.store.get_setting("selected_folder", "INBOX") or "INBOX"
        self.selected_message_key = self.store.get_setting("selected_message_key", "")
        self.search_query = self.store.get_setting("search_query", "")
        self._theme_mtime = palette_mtime()
        self._page_ready = False
        self._sync_busy = False
        self._reply_draft: dict[str, Any] | None = None
        self.account_status: dict[int, dict[str, Any]] = {}
        self._pending_status_toasts: list[tuple[str, str]] = []
        self._message_render_cache: dict[tuple[str, bool, bool], dict[str, Any]] = {}
        self._open_compose_after_load = False
        self.fragment_server = FragmentServer(self)

        self.setWindowTitle(APP_NAME)
        self.resize(1580, 980)
        self.setMinimumSize(1220, 760)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        self.view.page().setBackgroundColor(QColor("#12131d"))
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        layout.addWidget(self.view)

        self.channel = QWebChannel(self.view.page())
        self.bridge = MailBridge()
        self.channel.registerObject("mailBridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.loadFinished.connect(self._handle_load_finished)

        self.bridge.bootstrapRequested.connect(self.push_state)
        self.bridge.accountSaveRequested.connect(self.save_account)
        self.bridge.accountDeleteRequested.connect(self.delete_account)
        self.bridge.searchRequested.connect(self.set_search)
        self.bridge.selectionRequested.connect(self.set_selection)
        self.bridge.refreshRequested.connect(lambda: self.schedule_sync("Manual refresh requested.", send_notifications=False))
        self.bridge.sendRequested.connect(self.send_compose)
        self.bridge.replyRequested.connect(self.start_reply)
        self.bridge.archiveRequested.connect(self.archive_message)
        self.bridge.deleteRequested.connect(self.delete_message)
        self.bridge.seenRequested.connect(self.set_seen)
        self.bridge.settingsRequested.connect(self.open_settings_app)
        self.bridge.exportSelectedRequested.connect(self.export_selected_message)
        self.bridge.exportVisibleRequested.connect(self.export_visible_messages_zip)
        self.bridge.externalLinkRequested.connect(self.open_external_link)
        self.bridge.contentPolicyRequested.connect(self.set_content_policy)
        self.bridge.toastRequested.connect(self.push_toast)
        self.syncCompleted.connect(self._finish_sync)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(lambda: self.schedule_sync("Background sync completed.", send_notifications=True))
        self.poll_timer.start(15000)
        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self._apply_launch_targets(launch_targets or [])
        self._load_page()
        QTimer.singleShot(1000, lambda: self.schedule_sync("Initial sync completed.", send_notifications=False))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.fragment_server.close()
        super().closeEvent(event)

    def _load_page(self) -> None:
        self._page_ready = False
        self.view.load(QUrl.fromLocalFile(str(HTML_PATH)))

    def _handle_load_finished(self, ok: bool) -> None:
        self._page_ready = ok
        if ok:
            self.push_state()
            if self._open_compose_after_load and self._reply_draft:
                QTimer.singleShot(120, lambda: self._run_js("window.openComposeFromReply();"))
                self._open_compose_after_load = False

    def _run_js(self, script: str) -> None:
        if not self._page_ready:
            return
        self.view.page().runJavaScript(script)

    def push_state(self) -> None:
        payload = json_ready(self._build_state_payload())
        self._push_payload(payload)

    def _push_payload(self, payload: dict[str, Any]) -> None:
        payload_json = json.dumps(json_ready(payload))
        self.bridge.stateChanged.emit(payload_json)
        self._run_js(f"window.setMailState({payload_json});")

    def push_toast(self, title: str, body: str) -> None:
        safe_title = json.dumps(title)
        safe_body = json.dumps(body)
        self._run_js(f"window.showToast({safe_title}, {safe_body});")

    def _default_compose_account_id(self) -> int:
        account = self.store.get_account(self.selected_account_id) if self.selected_account_id > 0 else None
        if account:
            return int(account["id"])
        accounts = self.store.list_accounts()
        if accounts:
            return int(accounts[0].get("id", 0) or 0)
        return 0

    def _queue_compose_draft(self, draft: dict[str, Any]) -> None:
        prepared = {
            "account_id": int(draft.get("account_id", self._default_compose_account_id()) or self._default_compose_account_id()),
            "to": [normalize_email(item) for item in draft.get("to", []) if normalize_email(item)],
            "cc": [normalize_email(item) for item in draft.get("cc", []) if normalize_email(item)],
            "bcc": [normalize_email(item) for item in draft.get("bcc", []) if normalize_email(item)],
            "subject": str(draft.get("subject", "") or ""),
            "body": str(draft.get("body", "") or ""),
            "in_reply_to": str(draft.get("in_reply_to", "") or ""),
            "references": [str(item) for item in draft.get("references", []) if str(item).strip()],
        }
        self._reply_draft = prepared
        self._open_compose_after_load = True
        if self._page_ready:
            self.push_state()
            self._run_js("window.openComposeFromReply();")
            self._open_compose_after_load = False

    def _apply_launch_targets(self, launch_targets: list[str]) -> None:
        for target in launch_targets:
            draft = parse_mailto_draft(target)
            if draft is not None:
                self._queue_compose_draft(draft)
                break

    def _prune_message_render_cache(self, *, max_items: int = 256) -> None:
        overflow = len(self._message_render_cache) - max_items
        if overflow <= 0:
            return
        for key in list(self._message_render_cache.keys())[:overflow]:
            self._message_render_cache.pop(key, None)

    def _invalidate_message_render_cache(self, message_key: str = "") -> None:
        if not message_key:
            self._message_render_cache.clear()
            return
        prefix = str(message_key)
        for key in list(self._message_render_cache.keys()):
            if key[0] == prefix:
                self._message_render_cache.pop(key, None)

    def _policy_setting_key(self, kind: str) -> str:
        return "script_policy_rules" if kind == "scripts" else "image_policy_rules"

    def _policy_rules(self, kind: str) -> dict[str, list[str]]:
        payload = self.store.get_json_setting(self._policy_setting_key(kind), {"messages": [], "senders": [], "domains": []})
        return {
            "messages": [str(item) for item in payload.get("messages", []) if str(item).strip()],
            "senders": [normalize_email(str(item)) for item in payload.get("senders", []) if normalize_email(str(item))],
            "domains": [str(item).strip().lower() for item in payload.get("domains", []) if str(item).strip()],
        }

    def _effective_policy_scope(self, kind: str, message: dict[str, Any]) -> str:
        rules = self._policy_rules(kind)
        message_key = str(message.get("key", ""))
        sender = normalize_email(str(message.get("from_email", "")))
        domain = email_domain(sender)
        if message_key and message_key in rules["messages"]:
            return "message"
        if sender and sender in rules["senders"]:
            return "sender"
        if domain and domain in rules["domains"]:
            return "domain"
        return "none"

    def _permission_state(self, kind: str, message: dict[str, Any]) -> dict[str, Any]:
        scope = self._effective_policy_scope(kind, message)
        sender = normalize_email(str(message.get("from_email", "")))
        domain = email_domain(sender)
        return {
            "effective": scope != "none",
            "scope": scope,
            "sender": sender,
            "domain": domain,
        }

    def _message_render_data(self, message: dict[str, Any]) -> tuple[str, dict[str, bool], dict[str, Any], dict[str, Any]]:
        raw_html = str(message.get("body_html", "") or "")
        image_policy = self._permission_state("images", message)
        script_policy = self._permission_state("scripts", message)
        cache_key = (
            str(message.get("key", "")),
            bool(image_policy["effective"]),
            bool(script_policy["effective"]),
        )
        cached = self._message_render_cache.get(cache_key)
        if cached is not None:
            if cached.get("body_text"):
                message["body_text"] = str(cached["body_text"])
            return (
                str(cached["html"]),
                dict(cached["detected"]),
                image_policy,
                script_policy,
            )
        raw_source = self.store.raw_source_for_key(str(message.get("key", "")))
        parsed_msg = message_from_bytes(raw_source) if raw_source else None
        if parsed_msg:
            extracted_html, extracted_text = message_parts(parsed_msg)
            if extracted_html.strip():
                raw_html = extracted_html
            if extracted_text.strip():
                message["body_text"] = extracted_text
        rendered_html, detected = prepare_message_html(
            raw_html,
            parsed_msg,
            allow_remote_images=bool(image_policy["effective"]),
            allow_scripts=bool(script_policy["effective"]),
        )
        self._message_render_cache[cache_key] = {
            "html": rendered_html,
            "detected": dict(detected),
            "body_text": str(message.get("body_text", "") or ""),
        }
        self._prune_message_render_cache()
        return rendered_html, detected, image_policy, script_policy

    def _decorate_message_for_display(self, message: dict[str, Any] | None) -> dict[str, Any] | None:
        if not message:
            return None
        payload = dict(message)
        rendered_html, detected, image_policy, script_policy = self._message_render_data(payload)
        payload["body_html_raw"] = str(payload.get("body_html", "") or "")
        payload["body_html"] = rendered_html
        payload["content_policy"] = {
            "images_allowed": bool(image_policy["effective"]),
            "images_scope": str(image_policy["scope"]),
            "scripts_allowed": bool(script_policy["effective"]),
            "scripts_scope": str(script_policy["scope"]),
            "sender": str(image_policy["sender"]),
            "domain": str(image_policy["domain"]),
            "has_remote_images": bool(detected["has_remote_images"]),
            "has_active_content": bool(detected["has_active_content"]),
        }
        return payload

    def _build_state_payload(self) -> dict[str, Any]:
        with self.state_lock:
            stored_accounts = self.store.list_accounts()
            unread_map = self.store.unread_counts()
            selected_account = self.selected_account_id
            if not stored_accounts:
                selected_account = 0
            elif selected_account not in {0, *{int(item["id"]) for item in stored_accounts}}:
                selected_account = 0
                self.selected_account_id = selected_account
                self.store.set_setting("selected_account_id", str(selected_account))
            folders: list[str] = []
            accounts: list[dict[str, Any]] = []
            all_unread_total = 0
            all_folder_unread: dict[str, int] = {}
            for account in stored_accounts:
                account_id = int(account["id"])
                try:
                    folder_list = json.loads(str(account.get("folders_json", "[]")))
                except Exception:
                    folder_list = []
                if not folder_list:
                    folder_list = list(FOLDER_PREFERENCES)
                account["folders"] = folder_list
                account["unread_by_folder"] = unread_map.get(account_id, {})
                account["unread_total"] = sum(account["unread_by_folder"].values())
                all_unread_total += int(account["unread_total"])
                for folder_name, unread_count in account["unread_by_folder"].items():
                    all_folder_unread[str(folder_name)] = all_folder_unread.get(str(folder_name), 0) + int(unread_count)
                account["selected"] = account_id == selected_account
                if account_id == selected_account and selected_account > 0:
                    folders = folder_list
                accounts.append(account)
            all_account = {
                "id": 0,
                "label": "All Accounts",
                "email_address": "Mixed inbox",
                "display_name": "All Accounts",
                "avatar_path": "",
                "username": "",
                "imap_host": "",
                "imap_port": 0,
                "imap_ssl": True,
                "smtp_host": "",
                "smtp_port": 0,
                "smtp_starttls": True,
                "smtp_ssl": False,
                "notify_enabled": False,
                "poll_interval_seconds": POLL_FALLBACK_SECONDS,
                "signature": "",
                "folders": list(FOLDER_PREFERENCES),
                "selected": selected_account == 0,
                "unread_total": all_unread_total,
                "unread_by_folder": all_folder_unread,
            }
            accounts.insert(0, all_account)
            if selected_account == 0:
                folders = list(FOLDER_PREFERENCES)
            if self.selected_folder not in folders and folders:
                self.selected_folder = folders[0]
                self.store.set_setting("selected_folder", self.selected_folder)
            messages = self.store.list_messages(selected_account, self.selected_folder, self.search_query)
            valid_keys = {item["key"] for item in messages}
            if self.selected_message_key not in valid_keys:
                self.selected_message_key = messages[0]["key"] if messages else ""
                self.store.set_setting("selected_message_key", self.selected_message_key)
            selected_message = self.store.get_message(self.selected_message_key) if self.selected_message_key else None
            selected_message = self._decorate_message_for_display(selected_message)
            contacts = self.store.list_contacts()
            theme = load_theme_palette()
            status = self.account_status.get(selected_account, {})
            if selected_account == 0:
                online_accounts = [item for key, item in self.account_status.items() if bool(item.get("online"))]
                offline_accounts = [item for key, item in self.account_status.items() if not bool(item.get("online"))]
                status = {
                    "online": bool(online_accounts) and not bool(offline_accounts),
                    "detail": "All mail servers reachable." if online_accounts and not offline_accounts else (
                        "Some mail servers are unreachable." if offline_accounts else "Waiting for the first sync."
                    ),
                }
            state = {
                "server_base": self.fragment_server.base_url,
                "accounts": [
                    {
                        "id": int(item["id"]),
                        "label": str(item["label"]),
                        "email_address": str(item["email_address"]),
                        "display_name": str(item["display_name"]),
                        "avatar_path": str(item.get("avatar_path", "")),
                        "username": str(item["username"]),
                        "imap_host": str(item["imap_host"]),
                        "imap_port": int(item["imap_port"]),
                        "imap_ssl": bool(item["imap_ssl"]),
                        "smtp_host": str(item["smtp_host"]),
                        "smtp_port": int(item["smtp_port"]),
                        "smtp_starttls": bool(item["smtp_starttls"]),
                        "smtp_ssl": bool(item["smtp_ssl"]),
                        "notify_enabled": bool(item["notify_enabled"]),
                        "poll_interval_seconds": int(item["poll_interval_seconds"]),
                        "signature": str(item["signature"]),
                        "folders": item["folders"],
                        "selected": bool(item["selected"]),
                        "unread_total": int(item["unread_total"]),
                        "unread_by_folder": item["unread_by_folder"],
                    }
                    for item in accounts
                ],
                "theme": {
                    "use_matugen": bool(theme.use_matugen),
                    "primary": theme.primary,
                    "primary_container": theme.primary_container,
                    "secondary": theme.secondary,
                    "background": theme.background,
                    "surface": theme.surface,
                    "surface_container": theme.surface_container,
                    "surface_container_high": theme.surface_container_high,
                    "surface_variant": theme.surface_variant,
                    "outline": theme.outline,
                    "on_surface": theme.on_surface,
                    "on_surface_variant": theme.on_surface_variant,
                    "error": theme.error,
                    "ui_font_family": theme.ui_font_family,
                    "display_font_family": theme.display_font_family,
                    "mono_font_family": theme.mono_font_family,
                },
                "selected_account_id": selected_account,
                "selected_folder": self.selected_folder,
                "selected_message_key": self.selected_message_key,
                "messages": messages,
                "selected_message": selected_message,
                "message_count": len(messages),
                "search_query": self.search_query,
                "contacts": contacts,
                "sound_enabled": self.store.get_setting("sound_enabled", "1") == "1",
                "sound_path": self.store.get_setting("sound_path", ""),
                "reply_draft": self._reply_draft,
                "mail_online": bool(status.get("online", False)),
                "mail_status_text": str(status.get("detail", "Waiting for the first sync.")),
            }
            return state

    def _build_selection_payload(self) -> dict[str, Any]:
        selected_message = self.store.get_message(self.selected_message_key) if self.selected_message_key else None
        return {
            "selected_account_id": self.selected_account_id,
            "selected_folder": self.selected_folder,
            "selected_message_key": self.selected_message_key,
            "selected_message": self._decorate_message_for_display(selected_message),
        }

    def _reload_theme_if_needed(self) -> None:
        current = palette_mtime()
        if current == self._theme_mtime:
            return
        self._theme_mtime = current
        self.push_state()

    def open_settings_app(self) -> None:
        command = entry_command(APP_DIR / "pyqt" / "settings-page" / "settings.py")
        if not command:
            self.push_toast("Settings unavailable", "Could not find Hanauta Settings.")
            return
        command = [*command, "--page", "services", "--service-section", "mail"]
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def export_selected_message(self, message_key: str) -> None:
        if not message_key:
            self.push_toast("Export failed", "No message is selected.")
            return
        path_text, _ = QFileDialog.getSaveFileName(self, "Export message", str(Path.home() / "Downloads" / "message.eml"), "Email files (*.eml)")
        if not path_text:
            return
        target = Path(path_text)
        try:
            target.write_bytes(self.store.raw_source_for_key(message_key))
        except Exception as exc:
            self.push_toast("Export failed", str(exc))
            return
        self.push_toast("Message exported", target.name)

    def export_visible_messages_zip(self) -> None:
        path_text, _ = QFileDialog.getSaveFileName(self, "Export visible messages", str(Path.home() / "Downloads" / "hanauta-mail-export.zip"), "Zip archives (*.zip)")
        if not path_text:
            return
        messages = self.store.list_messages(self.selected_account_id, self.selected_folder, self.search_query, limit=None)
        target = Path(path_text)
        try:
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for index, message in enumerate(messages, start=1):
                    safe_subject = re_sub(r"[^A-Za-z0-9._-]+", "_", str(message.get("subject") or "message")).strip("_") or "message"
                    archive.writestr(f"{index:03d}-{safe_subject}.eml", self.store.raw_source_for_key(str(message["key"])))
        except Exception as exc:
            self.push_toast("Export failed", str(exc))
            return
        self.push_toast("Messages exported", target.name)

    def set_content_policy(self, kind: str, scope: str, message_key: str) -> None:
        normalized_kind = "scripts" if str(kind).strip().lower() == "scripts" else "images"
        normalized_scope = str(scope).strip().lower()
        message = self.store.get_message(message_key)
        if not message:
            self.push_toast("Preference not saved", "The selected message could not be found.")
            return
        sender = normalize_email(str(message.get("from_email", "")))
        domain = email_domain(sender)
        if normalized_scope == "message":
            value = str(message.get("key", ""))
            scope_label = "this message"
        elif normalized_scope == "sender":
            value = sender
            scope_label = sender or "this sender"
        elif normalized_scope == "domain":
            value = domain
            scope_label = domain or "this domain"
        else:
            self.push_toast("Preference not saved", "That trust scope is not supported.")
            return
        if not value:
            self.push_toast("Preference not saved", "That message does not expose a sender or domain for this trust rule.")
            return
        rules = self._policy_rules(normalized_kind)
        bucket = "messages" if normalized_scope == "message" else f"{normalized_scope}s"
        if value not in rules[bucket]:
            rules[bucket].append(value)
        for key in ("messages", "senders", "domains"):
            rules[key] = sorted(set(rules[key]))
        self.store.set_json_setting(self._policy_setting_key(normalized_kind), rules)
        self._invalidate_message_render_cache(str(message.get("key", "")))
        label = "Active content" if normalized_kind == "scripts" else "Remote images"
        self.push_toast("Trust preference saved", f"{label} will now load for {scope_label}.")
        self._push_payload(self._build_selection_payload())

    def open_external_link(self, url: str) -> None:
        cleaned = clean_tracking_url(url)
        target = cleaned or str(url or "").strip()
        if not target:
            return
        subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def _record_account_status(self, account: dict[str, Any], online: bool, detail: str = "") -> None:
        account_id = int(account["id"])
        label = str(account.get("label") or account.get("email_address") or "Mail")
        previous = self.account_status.get(account_id, {})
        changed = previous.get("online") is not None and bool(previous.get("online")) != bool(online)
        self.account_status[account_id] = {"online": bool(online), "detail": detail, "label": label}
        if changed:
            title = f"{label} is {'online' if online else 'offline'}"
            body = "Mail sync reached the server again." if online else (detail or "The mail server is unreachable right now.")
            self._pending_status_toasts.append((title, body))

    def render_fragment(self, path: str, query: dict[str, list[str]]) -> str | None:
        self._apply_fragment_query_state(query)
        state = self._build_state_payload()
        if path == "/fragment/messages":
            return self._render_messages_fragment(state)
        if path == "/fragment/detail":
            return self._render_detail_fragment(state)
        if path == "/fragment/sidebar":
            return self._render_sidebar_fragment(state)
        return None

    def _query_value(self, query: dict[str, list[str]], key: str) -> str:
        values = query.get(key, [])
        if not values:
            return ""
        return str(values[0]).strip()

    def _apply_fragment_query_state(self, query: dict[str, list[str]]) -> None:
        search_query = self._query_value(query, "q")
        account_id = self._query_value(query, "account_id")
        folder = self._query_value(query, "folder")
        message_key = self._query_value(query, "message_key")

        if search_query != "" or "q" in query:
            self.search_query = search_query
            self.store.set_setting("search_query", self.search_query)

        if account_id:
            self.selected_account_id = int(account_id)
            self.store.set_setting("selected_account_id", account_id)

        if folder:
            self.selected_folder = folder
            self.store.set_setting("selected_folder", folder)
            self.selected_message_key = ""
            self.store.set_setting("selected_message_key", "")

        if message_key:
            self.selected_message_key = message_key
            self.store.set_setting("selected_message_key", message_key)
            self.store.mark_local_seen(message_key, True)
            self._set_remote_seen(message_key, True)

    def _fragment_messages_url(
        self,
        state: dict[str, Any],
        *,
        account_id: int | None = None,
        folder: str | None = None,
        message_key: str | None = None,
        search_query: str | None = None,
    ) -> str:
        params: dict[str, str] = {}
        chosen_account_id = account_id if account_id is not None else int(state.get("selected_account_id") or 0)
        chosen_folder = folder if folder is not None else str(state.get("selected_folder", "INBOX"))
        chosen_query = search_query if search_query is not None else str(state.get("search_query", ""))
        if chosen_account_id:
            params["account_id"] = str(chosen_account_id)
        if chosen_folder:
            params["folder"] = chosen_folder
        if message_key:
            params["message_key"] = message_key
        if chosen_query:
            params["q"] = chosen_query
        encoded = urllib.parse.urlencode(params)
        return f"{state['server_base']}/fragment/messages" + (f"?{encoded}" if encoded else "")

    def _render_account_list_markup(self, state: dict[str, Any]) -> str:
        accounts = state["accounts"]
        if not accounts:
            return '<div class="empty-card"><h3>No accounts</h3><p>Add an account in Python when you are ready to wire up live sync.</p></div>'
        cards: list[str] = []
        for account in accounts:
            cards.append(
                f"""
                <button
                    class="account-card {'active' if account['selected'] else ''}"
                    type="button"
                    hx-get="{html.escape(self._fragment_messages_url(state, account_id=int(account['id']), folder=str(account['folders'][0]) if account['folders'] else 'INBOX', message_key=''))}"
                    hx-target="#messageList"
                    hx-swap="innerHTML"
                >
                    <div>
                        <div>{html.escape(account['label'])}</div>
                        <div style="font-size:12px; color: var(--text-dim); margin-top:4px;">{html.escape(account['email_address'])}</div>
                    </div>
                    <span class="badge">{int(account['unread_total'])}</span>
                </button>
                """
            )
        return "".join(cards)

    def _render_folder_list_markup(self, state: dict[str, Any]) -> str:
        accounts = state["accounts"]
        selected_account = next((item for item in accounts if item["selected"]), None)
        if not selected_account:
            return ""
        items: list[str] = []
        for folder in selected_account["folders"]:
            unread = int(selected_account["unread_by_folder"].get(folder, 0))
            items.append(
                f"""
                <button
                    class="folder-button {'active' if folder == state['selected_folder'] else ''}"
                    type="button"
                    hx-get="{html.escape(self._fragment_messages_url(state, folder=folder, message_key=''))}"
                    hx-target="#messageList"
                    hx-swap="innerHTML"
                >
                    <span>{html.escape(folder)}</span>
                    {'<span class="badge">' + str(unread) + '</span>' if unread else ''}
                </button>
                """
            )
        return "".join(items)

    def _render_sidebar_fragment(self, state: dict[str, Any]) -> str:
        return (
            f'<div id="accountList" hx-swap-oob="innerHTML">{self._render_account_list_markup(state)}</div>'
            f'<div id="folderList" hx-swap-oob="innerHTML">{self._render_folder_list_markup(state)}</div>'
        )

    def _render_message_list_markup(self, state: dict[str, Any]) -> str:
        account_id = int(state.get("selected_account_id") or 0)
        folder = str(state.get("selected_folder", "INBOX"))
        search_query = str(state.get("search_query", ""))
        messages = self.store.list_messages(account_id, folder, search_query)
        if not messages:
            return """
            <div class="empty-state">
              <div class="empty-card">
                <h3>Nothing to show</h3>
                <p>This folder is empty for the current search, or no mail has been synced yet.</p>
              </div>
            </div>
            """
        items: list[str] = []
        for item in messages:
            items.append(
                f"""
                <button
                    class="message-card {'active' if item['key'] == state.get('selected_message_key') else ''} {'unread' if not bool(item['seen']) else ''}"
                    type="button"
                    hx-get="{html.escape(self._fragment_messages_url(state, message_key=str(item['key'])))}"
                    hx-target="#messageList"
                    hx-swap="innerHTML"
                >
                    <div class="message-row">
                        <span class="sender">{html.escape(item['sender'])}</span>
                        <span class="time">{html.escape(item['display_time'])}</span>
                    </div>
                    <div class="subject">{html.escape(item['subject'] or '(No subject)')}</div>
                    <div class="snippet">{html.escape(item['snippet'])}</div>
                    <div class="tags">
                        {'<span class="tag">Attachment</span>' if bool(item['has_attachments']) else ''}
                        {'<span class="tag">Starred</span>' if bool(item['flagged']) else ''}
                        {'<span class="tag">Unread</span>' if not bool(item['seen']) else ''}
                    </div>
                </button>
                """
            )
        return "".join(items)

    def _render_messages_fragment(self, state: dict[str, Any]) -> str:
        messages_markup = self._render_message_list_markup(state)
        selected_account = next((item for item in state["accounts"] if item["selected"]), None)
        unread_total = int(selected_account["unread_total"]) if selected_account else 0
        folder = html.escape(str(state.get("selected_folder", "Inbox")))
        message_count = len(
            self.store.list_messages(
                int(state.get("selected_account_id") or 0),
                str(state.get("selected_folder", "INBOX")),
                str(state.get("search_query", "")),
            )
        )
        selected = selected_account or {}
        initials = "".join(part[:1].upper() for part in str(selected.get("display_name") or selected.get("label") or "HM").split()[:2]) or "HM"
        return (
            messages_markup
            + f'<div id="detailView" hx-swap-oob="innerHTML">{self._render_detail_content(state)}</div>'
            + f'<p id="detailSubtitle" hx-swap-oob="outerHTML">{html.escape(self._detail_subtitle(state))}</p>'
            + f'<h2 id="folderTitle" hx-swap-oob="outerHTML">{folder}</h2>'
            + f'<p id="folderSubtitle" hx-swap-oob="outerHTML">{message_count} conversation{"s" if message_count != 1 else ""} in view</p>'
            + f'<strong id="unreadStat" hx-swap-oob="outerHTML">{unread_total}</strong>'
            + f'<strong id="accountStat" hx-swap-oob="outerHTML">{html.escape(str(selected.get("label", "Preview")))}</strong>'
            + f'<div class="avatar" id="profileAvatar" hx-swap-oob="outerHTML">{html.escape(initials)}</div>'
            + f'<div id="accountList" hx-swap-oob="innerHTML">{self._render_account_list_markup(state)}</div>'
            + f'<div id="folderList" hx-swap-oob="innerHTML">{self._render_folder_list_markup(state)}</div>'
            + f'<select id="composeAccount" hx-swap-oob="outerHTML">{self._render_compose_accounts_markup(state)}</select>'
        )

    def _detail_subtitle(self, state: dict[str, Any]) -> str:
        message = state.get("selected_message")
        if not message:
            return "Select a message to inspect the full thread"
        display_name = str(message.get("from_name") or message.get("sender") or "Unknown Sender")
        sent_at = str(message.get("display_time") or "")
        return f"{display_name} · {sent_at}"

    def _render_compose_accounts_markup(self, state: dict[str, Any]) -> str:
        selected_account_id = int(state.get("selected_account_id") or 0)
        return "".join(
            f'<option value="{int(account["id"])}"{" selected" if int(account["id"]) == selected_account_id else ""}>{html.escape(str(account["label"]))} · {html.escape(str(account["email_address"]))}</option>'
            for account in state["accounts"]
            if int(account["id"]) > 0
        )

    def _render_detail_content(self, state: dict[str, Any]) -> str:
        message = state.get("selected_message")
        if not message:
            return """
            <div class="empty-state">
              <div class="empty-card">
                <h3>Conversation detail</h3>
                <p>The selected message will open here with sender context, quick actions, and the full body.</p>
              </div>
            </div>
            """
        display_name = html.escape(str(message.get("from_name") or message.get("sender") or "Unknown Sender"))
        avatar = html.escape(display_name[:1].upper() or "H")
        sent_at = html.escape(str(message.get("display_time") or ""))
        body_html = str(message.get("body_html", "")).strip() or "<pre>" + html.escape(str(message.get("body_text", "") or str(message.get("snippet", "")))) + "</pre>"
        content_policy = message.get("content_policy") or {}
        pills = [f'<span class="pill">{html.escape(str(state.get("selected_folder", "Inbox")))}</span>']
        if bool(message.get("flagged")):
            pills.append('<span class="pill">Starred</span>')
        if bool(message.get("has_attachments")):
            pills.append('<span class="pill">Has attachments</span>')
        if bool(message.get("is_spam")):
            pills.append('<span class="pill">Spam risk</span>')
        trust_actions: list[str] = []
        trust_notes: list[str] = []
        sender_email = html.escape(str(content_policy.get("sender") or message.get("from_email") or "this sender"))
        sender_domain = html.escape(str(content_policy.get("domain") or email_domain(str(message.get("from_email", ""))) or "this domain"))
        if bool(content_policy.get("has_remote_images")):
            if bool(content_policy.get("images_allowed")):
                trust_notes.append(f'<p>Remote images are allowed for {html.escape(str(content_policy.get("images_scope") or "this message"))}.</p>')
            else:
                trust_actions.extend(
                    [
                        f'<button class="ghost-button trust-button" type="button" data-policy-kind="images" data-policy-scope="message" data-message-key="{html.escape(str(message.get("key", "")))}">Show images for this message</button>',
                        f'<button class="ghost-button trust-button" type="button" data-policy-kind="images" data-policy-scope="sender" data-message-key="{html.escape(str(message.get("key", "")))}">Always show images from {sender_email}</button>',
                        f'<button class="ghost-button trust-button" type="button" data-policy-kind="images" data-policy-scope="domain" data-message-key="{html.escape(str(message.get("key", "")))}">Always show images from {sender_domain}</button>',
                    ]
                )
                trust_notes.append("<p>Remote images are blocked until you trust this message, sender, or domain.</p>")
        if bool(content_policy.get("has_active_content")):
            if bool(content_policy.get("scripts_allowed")):
                trust_notes.append(f'<p>Active content is allowed for {html.escape(str(content_policy.get("scripts_scope") or "this message"))}.</p>')
            else:
                trust_actions.extend(
                    [
                        f'<button class="ghost-button trust-button" type="button" data-policy-kind="scripts" data-policy-scope="message" data-message-key="{html.escape(str(message.get("key", "")))}">Allow active content for this message</button>',
                        f'<button class="ghost-button trust-button" type="button" data-policy-kind="scripts" data-policy-scope="sender" data-message-key="{html.escape(str(message.get("key", "")))}">Always allow active content from {sender_email}</button>',
                        f'<button class="ghost-button trust-button" type="button" data-policy-kind="scripts" data-policy-scope="domain" data-message-key="{html.escape(str(message.get("key", "")))}">Always allow active content from {sender_domain}</button>',
                    ]
                )
                trust_notes.append("<p>Active content is disabled by default, similar to a NoScript-style allow list.</p>")
        trust_markup = ""
        if trust_actions or trust_notes:
            trust_markup = f"""
            <section class="detail-security">
              <div class="section-head">
                <h3>Content Controls</h3>
              </div>
              <div class="trust-note">{''.join(trust_notes)}</div>
              <div class="trust-actions">{''.join(trust_actions)}</div>
            </section>
            """
        return f"""
        <div class="detail-hero">
          <div>
            <div class="pill-row">{''.join(pills)}</div>
            <h1 class="detail-title">{html.escape(str(message.get("subject") or "(No subject)"))}</h1>
          </div>
        </div>
        <div class="detail-meta">
          <div class="sender-block">
            <div class="sender-avatar">{avatar}</div>
            <div class="sender-copy">
              <h3>{display_name}</h3>
              <p>{html.escape(str(message.get("from_email") or ""))}</p>
              <p>To: {html.escape(str(message.get("to_line") or "You"))}</p>
            </div>
          </div>
          <div class="pill-row">
            <span class="pill">{sent_at}</span>
            <span class="pill">{'Read' if bool(message.get('seen')) else 'Unread'}</span>
          </div>
        </div>
        {trust_markup}
        <article class="message-content">{body_html}</article>
        """

    def _render_detail_fragment(self, state: dict[str, Any]) -> str:
        return self._render_detail_content(state)

    def save_account(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except Exception as exc:
            self.push_toast("Invalid account payload", str(exc))
            return
        account_id = int(payload.get("id", 0) or 0)
        existing = self.store.get_account(account_id) if account_id else None
        if existing and not str(payload.get("password", "")):
            payload["password"] = str(existing.get("password", ""))
        required = ("label", "email_address", "username", "imap_host", "smtp_host")
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if not str(payload.get("password", "")).strip():
            missing.append("password")
        if missing:
            self.push_toast("Missing account fields", ", ".join(missing))
            return
        self.store.set_setting("sound_enabled", "1" if bool(payload.get("sound_enabled", True)) else "0")
        self.store.set_setting("sound_path", str(payload.get("sound_path", "")).strip())
        account_id = self.store.save_account(payload)
        self.selected_account_id = account_id
        self.store.set_setting("selected_account_id", str(account_id))
        self.push_state()
        self.schedule_sync("Account saved and synced.", send_notifications=False)

    def delete_account(self, account_id: int) -> None:
        self.store.delete_account(account_id)
        if self.selected_account_id == account_id:
            self.selected_account_id = 0
            self.selected_message_key = ""
        self.push_state()

    def set_search(self, query: str) -> None:
        self.search_query = query
        self.store.set_setting("search_query", query)
        self.push_state()

    def set_selection(self, account_id: str, folder: str, message_key: str) -> None:
        selection_only = bool(message_key.strip()) and not bool(folder.strip()) and not bool(account_id.strip())
        if account_id.strip():
            self.selected_account_id = int(account_id)
            self.store.set_setting("selected_account_id", account_id)
        if folder.strip():
            self.selected_folder = folder
            self.store.set_setting("selected_folder", folder)
            self.selected_message_key = ""
            self.store.set_setting("selected_message_key", "")
        if message_key.strip():
            self.selected_message_key = message_key
            self.store.set_setting("selected_message_key", message_key)
            self.store.mark_local_seen(message_key, True)
            self._set_remote_seen(message_key, True)
        if selection_only:
            self._push_payload(self._build_selection_payload())
            return
        self.push_state()

    def schedule_sync(self, message: str, *, send_notifications: bool) -> None:
        if self._sync_busy:
            return
        self._sync_busy = True

        def worker() -> None:
            error_message = ""
            try:
                self._sync_all_accounts(send_notifications=send_notifications)
            except Exception as exc:
                error_message = str(exc)
            self.syncCompleted.emit(message, error_message)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_sync(self, message: str, error_message: str) -> None:
        self._sync_busy = False
        self._invalidate_message_render_cache()
        self.push_state()
        while self._pending_status_toasts:
            title, body = self._pending_status_toasts.pop(0)
            self.push_toast(title, body)
        if error_message:
            self.push_toast("Mail sync failed", error_message)
        elif message:
            self.push_toast("Mail sync", message)

    def _connect_imap(self, account: dict[str, Any]) -> imaplib.IMAP4:
        host = str(account["imap_host"])
        port = int(account["imap_port"] or 993)
        if bool(account["imap_ssl"]):
            client: imaplib.IMAP4 = imaplib.IMAP4_SSL(host, port)
        else:
            client = imaplib.IMAP4(host, port)
        client.login(str(account["username"]), self.store.cipher.decrypt_text(str(account["password"])))
        return client

    def _connect_smtp(self, account: dict[str, Any]) -> smtplib.SMTP:
        host = str(account["smtp_host"])
        port = int(account["smtp_port"] or 587)
        if bool(account["smtp_ssl"]):
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            smtp = smtplib.SMTP(host, port, timeout=20)
            smtp.ehlo()
            if bool(account["smtp_starttls"]):
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
        smtp.login(str(account["username"]), self.store.cipher.decrypt_text(str(account["password"])))
        return smtp

    def _sync_all_accounts(self, *, send_notifications: bool) -> None:
        errors: list[str] = []
        for account in self.store.list_accounts():
            try:
                self._sync_account(account, send_notifications=send_notifications)
                self._record_account_status(account, True, "Mail server reachable.")
            except Exception as exc:
                self._record_account_status(account, False, str(exc))
                errors.append(f"{account.get('label') or account.get('email_address')}: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors[:3]))

    def _sync_account(self, account: dict[str, Any], *, send_notifications: bool) -> None:
        account_id = int(account["id"])
        client = self._connect_imap(account)
        try:
            folders = self._list_folders(client)
            if not folders:
                folders = list(FOLDER_PREFERENCES)
            folder_state = self._parse_json(str(account.get("folder_state_json", "{}")), {})
            for folder in folders[:]:
                self._sync_folder(account_id, client, folder)
            self._detect_new_mail(account, client, folders, folder_state, send_notifications=send_notifications)
            self.store.update_account_sync_state(account_id, folders, folder_state)
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def _list_folders(self, client: imaplib.IMAP4) -> list[str]:
        folders: list[str] = []
        status, data = client.list()
        if status != "OK":
            return folders
        for row in data or []:
            text = decode_text(row)
            if ' "/" ' in text:
                folder = text.rsplit(' "/" ', 1)[-1]
            else:
                folder = text.split()[-1] if text.split() else ""
            folder = folder.strip('"')
            if folder:
                folders.append(folder)
        ordered: list[str] = []
        seen: set[str] = set()
        for name in FOLDER_PREFERENCES:
            for folder in folders:
                if folder.lower() == name.lower() and folder not in seen:
                    ordered.append(folder)
                    seen.add(folder)
        for folder in folders:
            if folder not in seen:
                ordered.append(folder)
        return ordered

    def _sync_folder(self, account_id: int, client: imaplib.IMAP4, folder: str) -> None:
        status, _ = client.select(f'"{folder}"', readonly=True)
        if status != "OK":
            return
        status, data = client.uid("search", None, "ALL")
        if status != "OK" or not data or not data[0]:
            return
        uids = [item for item in decode_text(data[0]).split() if item.strip()]
        latest_uids = uids[-25:]
        if not latest_uids:
            return
        status, fetch_data = client.uid("fetch", ",".join(latest_uids), "(RFC822 FLAGS)")
        if status != "OK":
            return
        for i in range(0, len(fetch_data or []), 2):
            item = fetch_data[i]
            if not item or not isinstance(item, tuple):
                continue
            header_blob = decode_text(item[0])
            raw_bytes = item[1]
            uid = ""
            for token in header_blob.split():
                if token.isdigit():
                    uid = token
            if not uid:
                continue
            msg = message_from_bytes(raw_bytes)
            from_name, from_email = parseaddr(decode_text(msg.get("From", "")))
            body_html, body_text = message_parts(msg)
            flags_seen = "\\Seen" in header_blob
            flags_flagged = "\\Flagged" in header_blob
            has_attachments = any("attachment" in (part.get("Content-Disposition") or "").lower() for part in msg.walk())
            payload = {
                "message_id": decode_text(msg.get("Message-ID", "")),
                "in_reply_to": decode_text(msg.get("In-Reply-To", "")),
                "references": [decode_text(item) for item in decode_text(msg.get("References", "")).split() if item],
                "subject": decode_text(msg.get("Subject", "")),
                "from_name": from_name,
                "from_email": from_email,
                "to_line": decode_text(msg.get("To", "")),
                "cc_line": decode_text(msg.get("Cc", "")),
                "date_iso": parse_date(decode_text(msg.get("Date", ""))),
                "snippet": snippet(body_text, body_html),
                "body_html": body_html,
                "body_text": body_text,
                "raw_source": raw_bytes,
                "seen": flags_seen,
                "flagged": flags_flagged,
                "has_attachments": has_attachments,
            }
            spam_score, is_spam = spam_assessment(
                folder=folder,
                subject=str(payload["subject"]),
                from_email=str(payload["from_email"]),
                body_text=str(payload["body_text"]),
                body_html=str(payload["body_html"]),
            )
            real_spam = real_spam_assessment(raw_bytes)
            if real_spam is not None:
                spam_score, is_spam = real_spam
            payload["spam_score"] = spam_score
            payload["is_spam"] = is_spam
            self.store.store_message(account_id, folder, uid, payload)
            self.store.upsert_contact(from_name, from_email)

    def _detect_new_mail(
        self,
        account: dict[str, Any],
        client: imaplib.IMAP4,
        folders: list[str],
        folder_state: dict[str, Any],
        *,
        send_notifications: bool,
    ) -> None:
        if not bool(account.get("notify_enabled", True)):
            return
        inbox = next((item for item in folders if item.lower() == "inbox"), folders[0] if folders else "")
        if not inbox:
            return
        status, _ = client.select(f'"{inbox}"', readonly=True)
        if status != "OK":
            return
        status, data = client.uid("search", None, "ALL")
        if status != "OK" or not data or not data[0]:
            return
        uids = [item for item in decode_text(data[0]).split() if item.strip()]
        if not uids:
            return
        latest_uid = uids[-1]
        last_uid = str(folder_state.get(inbox, ""))
        if not last_uid:
            folder_state[inbox] = latest_uid
            return
        if int(latest_uid) <= int(last_uid):
            folder_state[inbox] = latest_uid
            return
        new_uids = [uid for uid in uids if int(uid) > int(last_uid)][-3:]
        folder_state[inbox] = latest_uid
        if not send_notifications:
            return
        status, fetch_data = client.uid("fetch", ",".join(new_uids), "(RFC822)")
        if status != "OK":
            return
        notifications: list[tuple[str, str]] = []
        for i in range(0, len(fetch_data or []), 2):
            item = fetch_data[i]
            if not item or not isinstance(item, tuple):
                continue
            msg = message_from_bytes(item[1])
            from_name, from_email = parseaddr(decode_text(msg.get("From", "")))
            subject = decode_text(msg.get("Subject", "")) or "(No subject)"
            notifications.append((f"{account['label']}: {sender_display(from_name, from_email)}", subject))
        for title, body in notifications:
            self._desktop_notify(title, body)
        if notifications:
            self._play_notification_sound()

    def _desktop_notify(self, title: str, body: str) -> None:
        subprocess.run(["notify-send", "-a", APP_NAME, title, body], capture_output=True, text=True, check=False)

    def _play_notification_sound(self) -> None:
        if self.store.get_setting("sound_enabled", "1") != "1":
            return
        sound_path = preferred_sound_path(self.store.get_setting("sound_path", ""))
        if not sound_path or not shutil.which("paplay"):
            return
        subprocess.Popen(
            ["paplay", "--volume=15000", str(sound_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def start_reply(self, message_key: str) -> None:
        message = self.store.get_message(message_key)
        if not message:
            return
        subject = str(message.get("subject", "") or "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        quoted = str(message.get("body_text", "") or "")
        quoted_text = "\n".join(f"> {line}" if line.strip() else ">" for line in quoted.splitlines())
        self._reply_draft = {
            "account_id": int(message["account_id"]),
            "to": [str(message.get("from_email", ""))],
            "cc": [],
            "bcc": [],
            "subject": subject,
            "body": f"\n\nOn {message.get('date_iso', '')}, {sender_display(str(message.get('from_name', '')), str(message.get('from_email', '')))} wrote:\n{quoted_text}",
            "in_reply_to": str(message.get("message_id", "")),
            "references": list(message.get("references", [])) + ([str(message.get("message_id", ""))] if message.get("message_id") else []),
        }
        self.push_state()
        self._run_js("window.openComposeFromReply();")

    def send_compose(self, payload_json: str) -> None:
        try:
            payload = json.loads(payload_json)
        except Exception as exc:
            self.push_toast("Invalid compose payload", str(exc))
            return
        account_id = int(payload.get("account_id", 0) or 0)
        account = self.store.get_account(account_id)
        if not account:
            self.push_toast("Missing account", "Choose a valid account before sending.")
            return
        recipients = [normalize_email(item) for item in payload.get("to", []) if normalize_email(item)]
        cc_list = [normalize_email(item) for item in payload.get("cc", []) if normalize_email(item)]
        bcc_list = [normalize_email(item) for item in payload.get("bcc", []) if normalize_email(item)]
        if not recipients and not cc_list and not bcc_list:
            self.push_toast("Missing recipients", "Add at least one email address.")
            return
        message = EmailMessage()
        message["From"] = formataddr((str(account.get("display_name", "")), str(account.get("email_address", ""))))
        message["To"] = ", ".join(recipients)
        if cc_list:
            message["Cc"] = ", ".join(cc_list)
        message["Subject"] = str(payload.get("subject", "")).strip() or "(No subject)"
        if str(payload.get("in_reply_to", "")).strip():
            message["In-Reply-To"] = str(payload.get("in_reply_to", "")).strip()
        references = [item for item in payload.get("references", []) if str(item).strip()]
        if references:
            message["References"] = " ".join(str(item).strip() for item in references)
        body_text = str(payload.get("body", ""))
        signature = str(account.get("signature", "") or "")
        if signature.strip():
            body_text = body_text.rstrip() + "\n\n-- \n" + signature.strip()
        message.set_content(body_text)
        try:
            smtp = self._connect_smtp(account)
            try:
                smtp.send_message(message, to_addrs=recipients + cc_list + bcc_list)
            finally:
                smtp.quit()
        except Exception as exc:
            self.push_toast("Send failed", str(exc))
            return
        for address in recipients + cc_list + bcc_list:
            self.store.upsert_contact("", address)
        self._reply_draft = None
        self.push_state()
        self.push_toast("Message sent", f"Sent from {account['label']}.")
        self.schedule_sync("Sent folder refreshed.", send_notifications=False)

    def _set_remote_seen(self, message_key: str, seen: bool) -> None:
        try:
            account_id, folder, uid = parse_message_key(message_key)
            account = self.store.get_account(account_id)
            if not account:
                return
            client = self._connect_imap(account)
            try:
                status, _ = client.select(f'"{folder}"')
                if status != "OK":
                    return
                flag_command = "+FLAGS" if seen else "-FLAGS"
                client.uid("store", uid, flag_command, "(\\Seen)")
            finally:
                client.logout()
        except Exception:
            return

    def set_seen(self, message_key: str, seen: bool) -> None:
        self.store.mark_local_seen(message_key, seen)
        self._set_remote_seen(message_key, seen)
        self.push_state()

    def archive_message(self, message_key: str) -> None:
        self._move_message(message_key, "Archive")

    def delete_message(self, message_key: str) -> None:
        try:
            account_id, folder, uid = parse_message_key(message_key)
            account = self.store.get_account(account_id)
            if not account:
                return
            client = self._connect_imap(account)
            try:
                status, _ = client.select(f'"{folder}"')
                if status == "OK":
                    client.uid("store", uid, "+FLAGS", "(\\Deleted)")
                    client.expunge()
            finally:
                client.logout()
        except Exception:
            pass
        self.store.delete_local_message(message_key)
        self._invalidate_message_render_cache(message_key)
        if self.selected_message_key == message_key:
            self.selected_message_key = ""
            self.store.set_setting("selected_message_key", "")
        self.push_state()

    def _move_message(self, message_key: str, target_folder_hint: str) -> None:
        try:
            account_id, folder, uid = parse_message_key(message_key)
            account = self.store.get_account(account_id)
            if not account:
                return
            folders = self._parse_json(str(account.get("folders_json", "[]")), list(FOLDER_PREFERENCES))
            target_folder = next((item for item in folders if item.lower() == target_folder_hint.lower()), "")
            if not target_folder:
                self.push_toast("Archive unavailable", "This account does not expose an Archive folder.")
                return
            client = self._connect_imap(account)
            try:
                status, _ = client.select(f'"{folder}"')
                if status == "OK":
                    client.uid("copy", uid, f'"{target_folder}"')
                    client.uid("store", uid, "+FLAGS", "(\\Deleted)")
                    client.expunge()
            finally:
                client.logout()
            new_key = self.store.move_local_message(message_key, target_folder)
            self._invalidate_message_render_cache(message_key)
            if new_key:
                self._invalidate_message_render_cache(str(new_key))
            if self.selected_message_key == message_key:
                self.selected_message_key = ""
                self.store.set_setting("selected_message_key", "")
            self.push_state()
            self.push_toast("Message moved", f"Moved to {target_folder}.")
            return new_key
        except Exception as exc:
            self.push_toast("Move failed", str(exc))
            return None

    def _parse_json(self, value: str, fallback: Any) -> Any:
        try:
            return json.loads(value)
        except Exception:
            return fallback


def main() -> int:
    if not WEBENGINE_AVAILABLE:
        raise RuntimeError(f"QtWebEngine is unavailable: {WEBENGINE_ERROR}")
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    window = EmailClientWindow(sys.argv[1:])
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
