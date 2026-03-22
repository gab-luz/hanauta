#!/usr/bin/env python3
from __future__ import annotations

import html
import imaplib
import json
import os
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
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

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
DB_PATH = STATE_DIR / "mail.sqlite3"
HTML_PATH = HERE / "code.html"
APP_NAME = "Hanauta Mail"
DEFAULT_SOUND_PATHS = (
    Path("/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"),
    Path("/usr/share/sounds/freedesktop/stereo/message.oga"),
    Path("/usr/share/sounds/freedesktop/stereo/complete.oga"),
)
FOLDER_PREFERENCES = ("INBOX", "Sent", "Drafts", "Archive", "Spam", "Trash")
POLL_FALLBACK_SECONDS = 90


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
                    seen INTEGER NOT NULL DEFAULT 0,
                    flagged INTEGER NOT NULL DEFAULT 0,
                    has_attachments INTEGER NOT NULL DEFAULT 0,
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
        self.ensure_setting("selected_account_id", "")
        self.ensure_setting("selected_folder", "INBOX")
        self.ensure_setting("selected_message_key", "")
        self.ensure_setting("search_query", "")
        self.ensure_setting("sound_enabled", "1")
        self.ensure_setting("sound_path", "")

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

    def list_accounts(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM accounts ORDER BY lower(label), lower(email_address)"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_account(self, account_id: int) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return dict(row) if row else None

    def save_account(self, payload: dict[str, Any]) -> int:
        now = now_iso()
        values = (
            str(payload.get("label", "")).strip() or str(payload.get("email_address", "")).strip(),
            str(payload.get("email_address", "")).strip(),
            str(payload.get("display_name", "")).strip(),
            str(payload.get("username", "")).strip(),
            str(payload.get("password", "")),
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
                    SET label=?, email_address=?, display_name=?, username=?, password=?,
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
                        label, email_address, display_name, username, password,
                        imap_host, imap_port, imap_ssl, smtp_host, smtp_port,
                        smtp_starttls, smtp_ssl, folders_json, folder_state_json,
                        signature, notify_enabled, poll_interval_seconds, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    body_html, body_text, seen, flagged, has_attachments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    seen=excluded.seen,
                    flagged=excluded.flagged,
                    has_attachments=excluded.has_attachments
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
                    str(payload.get("body_html", "")),
                    str(payload.get("body_text", "")),
                    1 if bool(payload.get("seen", False)) else 0,
                    1 if bool(payload.get("flagged", False)) else 0,
                    1 if bool(payload.get("has_attachments", False)) else 0,
                ),
            )
            self.conn.commit()

    def list_messages(self, account_id: int, folder: str, search: str) -> list[dict[str, Any]]:
        query = """
            SELECT account_id, folder, uid, subject, from_name, from_email, date_iso, snippet,
                   seen, flagged, has_attachments
            FROM messages
            WHERE account_id = ? AND folder = ?
        """
        params: list[Any] = [account_id, folder]
        if search.strip():
            like = f"%{search.strip().lower()}%"
            query += (
                " AND (lower(subject) LIKE ? OR lower(from_name) LIKE ? OR lower(from_email) LIKE ? "
                " OR lower(snippet) LIKE ? OR lower(body_text) LIKE ?)"
            )
            params.extend([like, like, like, like, like])
        query += " ORDER BY datetime(date_iso) DESC LIMIT 60"
        with self.lock:
            rows = self.conn.execute(query, params).fetchall()
        messages: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["key"] = build_message_key(int(item["account_id"]), str(item["folder"]), str(item["uid"]))
            item["display_time"] = display_time(str(item.get("date_iso", "")))
            item["sender"] = sender_display(str(item.get("from_name", "")), str(item.get("from_email", "")))
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
        message["key"] = key
        message["display_time"] = display_time(str(message.get("date_iso", "")))
        message["sender"] = sender_display(str(message.get("from_name", "")), str(message.get("from_email", "")))
        try:
            message["references"] = json.loads(str(message.get("references_json", "[]")))
        except Exception:
            message["references"] = []
        return message

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
                                     body_html, body_text, seen, flagged, has_attachments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    payload["seen"],
                    payload["flagged"],
                    payload["has_attachments"],
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

    def __init__(self) -> None:
        super().__init__()
        if not WEBENGINE_AVAILABLE:
            raise RuntimeError(f"QtWebEngine is unavailable: {WEBENGINE_ERROR}")
        self.store = MailStore(DB_PATH)
        self.state_lock = threading.RLock()
        self.selected_account_id = int(self.store.get_setting("selected_account_id", "0") or 0)
        self.selected_folder = self.store.get_setting("selected_folder", "INBOX") or "INBOX"
        self.selected_message_key = self.store.get_setting("selected_message_key", "")
        self.search_query = self.store.get_setting("search_query", "")
        self._page_ready = False
        self._sync_busy = False
        self._reply_draft: dict[str, Any] | None = None
        self.fragment_server = FragmentServer(self)

        self.setWindowTitle(APP_NAME)
        self.resize(1580, 980)
        self.setMinimumSize(1220, 760)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
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
        self.bridge.toastRequested.connect(self.push_toast)
        self.syncCompleted.connect(self._finish_sync)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(lambda: self.schedule_sync("Background sync completed.", send_notifications=True))
        self.poll_timer.start(15000)

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

    def _run_js(self, script: str) -> None:
        if not self._page_ready:
            return
        self.view.page().runJavaScript(script)

    def push_state(self) -> None:
        payload = self._build_state_payload()
        self.bridge.stateChanged.emit(json.dumps(payload))
        self._run_js(f"window.setMailState({json.dumps(json.dumps(payload))});")

    def push_toast(self, title: str, body: str) -> None:
        safe_title = json.dumps(title)
        safe_body = json.dumps(body)
        self._run_js(f"window.showToast({safe_title}, {safe_body});")

    def _build_state_payload(self) -> dict[str, Any]:
        with self.state_lock:
            accounts = self.store.list_accounts()
            unread_map = self.store.unread_counts()
            selected_account = self.selected_account_id
            if not accounts:
                selected_account = 0
            elif selected_account not in {int(item["id"]) for item in accounts}:
                selected_account = int(accounts[0]["id"])
                self.selected_account_id = selected_account
                self.store.set_setting("selected_account_id", str(selected_account))
            folders: list[str] = []
            selected_account_payload: dict[str, Any] | None = None
            for account in accounts:
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
                account["selected"] = account_id == selected_account
                if account_id == selected_account:
                    selected_account_payload = account
                    folders = folder_list
            if selected_account and self.selected_folder not in folders and folders:
                self.selected_folder = folders[0]
                self.store.set_setting("selected_folder", self.selected_folder)
            messages = self.store.list_messages(selected_account, self.selected_folder, self.search_query) if selected_account else []
            valid_keys = {item["key"] for item in messages}
            if self.selected_message_key not in valid_keys:
                self.selected_message_key = messages[0]["key"] if messages else ""
                self.store.set_setting("selected_message_key", self.selected_message_key)
            selected_message = self.store.get_message(self.selected_message_key) if self.selected_message_key else None
            contacts = self.store.list_contacts()
            state = {
                "server_base": self.fragment_server.base_url,
                "accounts": [
                    {
                        "id": int(item["id"]),
                        "label": str(item["label"]),
                        "email_address": str(item["email_address"]),
                        "display_name": str(item["display_name"]),
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
            }
            return state

    def render_fragment(self, path: str, query: dict[str, list[str]]) -> str | None:
        state = self._build_state_payload()
        if path == "/fragment/sidebar":
            return self._render_sidebar_fragment(state)
        if path == "/fragment/messages":
            return self._render_messages_fragment(state)
        if path == "/fragment/detail":
            return self._render_detail_fragment(state)
        return None

    def _render_sidebar_fragment(self, state: dict[str, Any]) -> str:
        accounts = state["accounts"]
        folder_items: list[str] = []
        selected_account = next((item for item in accounts if item["selected"]), None)
        if selected_account:
            for folder in selected_account["folders"]:
                unread = int(selected_account["unread_by_folder"].get(folder, 0))
                is_selected = folder == state["selected_folder"]
                classes = "mail-nav-item active" if is_selected else "mail-nav-item"
                badge = f"<span class='mail-badge'>{unread}</span>" if unread else ""
                folder_items.append(
                    f"""
                    <button class="{classes}" data-action="select-folder" data-folder="{html.escape(folder)}">
                        <span>{html.escape(folder)}</span>
                        {badge}
                    </button>
                    """
                )
        account_cards = []
        for account in accounts:
            classes = "account-chip active" if account["selected"] else "account-chip"
            account_cards.append(
                f"""
                <button class="{classes}" data-action="select-account" data-account="{account['id']}">
                    <span class="account-chip-title">{html.escape(account['label'])}</span>
                    <span class="account-chip-sub">{html.escape(account['email_address'])}</span>
                    <span class="account-chip-badge">{int(account['unread_total'])}</span>
                </button>
                """
            )
        return f"""
        <section class="side-section">
            <div class="side-title-row">
                <h3>Accounts</h3>
                <button class="ghost-button" data-action="open-account-settings">Manage</button>
            </div>
            <div class="account-stack">{''.join(account_cards) or '<div class="empty-copy">Add an account to start syncing mail.</div>'}</div>
        </section>
        <section class="side-section">
            <div class="side-title-row">
                <h3>Folders</h3>
                <button class="ghost-button" data-action="refresh">Sync</button>
            </div>
            <div class="folder-stack">{''.join(folder_items) or '<div class="empty-copy">No folders available.</div>'}</div>
        </section>
        """

    def _render_messages_fragment(self, state: dict[str, Any]) -> str:
        account_id = int(state.get("selected_account_id") or 0)
        folder = str(state.get("selected_folder", "INBOX"))
        search_query = str(state.get("search_query", ""))
        messages = self.store.list_messages(account_id, folder, search_query) if account_id else []
        if not messages:
            return """
            <div class="empty-state">
                <h3>No mail here yet</h3>
                <p>Sync the selected account, change folders, or clear the current search query.</p>
            </div>
            """
        items = []
        for item in messages:
            classes = ["mail-row"]
            if item["key"] == state.get("selected_message_key"):
                classes.append("active")
            if not bool(item["seen"]):
                classes.append("unread")
            attachment = "<span class='mail-tag'>Attachment</span>" if bool(item["has_attachments"]) else ""
            flag = "<span class='mail-tag'>Starred</span>" if bool(item["flagged"]) else ""
            items.append(
                f"""
                <button class="{' '.join(classes)}" data-action="select-message" data-message="{html.escape(item['key'])}">
                    <div class="mail-row-top">
                        <span class="mail-row-sender">{html.escape(item['sender'])}</span>
                        <span class="mail-row-time">{html.escape(item['display_time'])}</span>
                    </div>
                    <div class="mail-row-subject">{html.escape(item['subject'] or '(No subject)')}</div>
                    <div class="mail-row-snippet">{html.escape(item['snippet'])}</div>
                    <div class="mail-row-tags">{attachment}{flag}</div>
                </button>
                """
            )
        return "".join(items)

    def _render_detail_fragment(self, state: dict[str, Any]) -> str:
        message = state.get("selected_message")
        if not message:
            return """
            <div class="empty-detail">
                <div class="focus-badge">Inbox Focus</div>
                <h2>Pick a conversation</h2>
                <p>Your mail body, sender context, and quick actions will appear here.</p>
            </div>
            """
        action_bar = f"""
        <div class="detail-actions">
            <button class="action-pill" data-action="reply" data-message="{html.escape(message['key'])}">Reply</button>
            <button class="action-pill" data-action="toggle-seen" data-message="{html.escape(message['key'])}" data-seen="{0 if bool(message['seen']) else 1}">
                {'Mark unread' if bool(message['seen']) else 'Mark read'}
            </button>
            <button class="action-pill" data-action="archive" data-message="{html.escape(message['key'])}">Archive</button>
            <button class="action-pill danger" data-action="delete" data-message="{html.escape(message['key'])}">Delete</button>
        </div>
        """
        subject = html.escape(str(message.get("subject", "") or "(No subject)"))
        from_line = html.escape(formataddr((str(message.get("from_name", "")), str(message.get("from_email", "")))))
        to_line = html.escape(str(message.get("to_line", "")))
        body_html = str(message.get("body_html", "")).strip() or "<pre>" + html.escape(str(message.get("body_text", ""))) + "</pre>"
        return f"""
        <article class="detail-shell">
            <header class="detail-header">
                <div class="detail-meta">
                    <span class="focus-badge">{html.escape(str(message.get('folder', 'INBOX')))}</span>
                    <span class="detail-time">{html.escape(str(message.get('display_time', '')))}</span>
                </div>
                <h1>{subject}</h1>
                <p class="detail-from">{from_line}</p>
                <p class="detail-to">To: {to_line}</p>
                {action_bar}
            </header>
            <section class="detail-body">{body_html}</section>
        </article>
        """

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
        self.push_state()
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
        client.login(str(account["username"]), str(account["password"]))
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
        smtp.login(str(account["username"]), str(account["password"]))
        return smtp

    def _sync_all_accounts(self, *, send_notifications: bool) -> None:
        for account in self.store.list_accounts():
            self._sync_account(account, send_notifications=send_notifications)

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
                "seen": flags_seen,
                "flagged": flags_flagged,
                "has_attachments": has_attachments,
            }
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
    window = EmailClientWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
