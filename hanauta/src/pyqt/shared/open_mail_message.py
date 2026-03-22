#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from pyqt.shared.runtime import entry_command


STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "email-client"
STORAGE_CONFIG_PATH = STATE_DIR / "storage.json"
DEFAULT_DB_PATH = STATE_DIR / "mail.sqlite3"
EMAIL_CLIENT = Path(__file__).resolve().parents[1] / "email-client" / "email_client.py"


def load_storage_config() -> dict[str, str]:
    try:
        payload = json.loads(STORAGE_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid storage config")
    except Exception:
        payload = {}
    return {
        "db_path": str(payload.get("db_path", DEFAULT_DB_PATH)).strip() or str(DEFAULT_DB_PATH),
    }


def set_app_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_settings(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def prepare_mail_state(message_key: str, account_id: int, folder: str) -> None:
    db_path = Path(load_storage_config()["db_path"]).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                account_id INTEGER NOT NULL,
                folder TEXT NOT NULL,
                uid TEXT NOT NULL,
                seen INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (account_id, folder, uid)
            )
            """
        )
        if message_key:
            conn.execute("UPDATE messages SET seen = 1 WHERE account_id = ? AND folder = ? AND uid = ?", _parse_message_key(message_key))
        set_app_setting(conn, "selected_account_id", str(account_id) if account_id > 0 else "")
        set_app_setting(conn, "selected_folder", folder)
        set_app_setting(conn, "selected_message_key", message_key)
        conn.commit()
    finally:
        conn.close()


def _parse_message_key(value: str) -> tuple[int, str, str]:
    account_text, folder_text, uid = value.split("|", 2)
    return int(account_text), _decode_folder(folder_text), uid


def _decode_folder(value: str) -> str:
    from urllib.parse import unquote

    return unquote(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open Hanauta Mail on a selected message.")
    parser.add_argument("--message-key", default="")
    parser.add_argument("--account-id", type=int, default=0)
    parser.add_argument("--folder", default="INBOX")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.message_key:
        account_id, folder, _uid = _parse_message_key(args.message_key)
    else:
        account_id = max(0, int(args.account_id))
        folder = str(args.folder or "INBOX").strip() or "INBOX"
    prepare_mail_state(args.message_key, account_id, folder)
    command = entry_command(EMAIL_CLIENT)
    if not command:
        return 1
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
