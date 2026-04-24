import sqlite3
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]

MAIL_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "email-client"
MAIL_DB_PATH = MAIL_STATE_DIR / "mail.sqlite3"
MAIL_DESKTOP_ID = "hanauta-mail.desktop"
MAIL_DESKTOP_SOURCE = ROOT / "hanauta" / "config" / "applications" / MAIL_DESKTOP_ID
MAIL_DESKTOP_LOCAL = Path.home() / ".local" / "share" / "applications" / MAIL_DESKTOP_ID
MAIL_DESKTOP_SYSTEM = Path("/usr/local/share/applications") / MAIL_DESKTOP_ID
MAIL_DESKTOP_INSTALL_SCRIPT = ROOT / "hanauta" / "scripts" / "install_mail_desktop.sh"
MAIL_DESKTOP_SYSTEM_INSTALL_SCRIPT = (
    ROOT / "hanauta" / "scripts" / "install_mail_desktop_system.sh"
)


def mail_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_mail_storage_config() -> dict[str, str]:
    import json
    default = {
        "db_path": str(MAIL_DB_PATH),
        "attachments_dir": str(MAIL_STATE_DIR / "cache"),
    }
    try:
        payload = json.loads(
            (MAIL_STATE_DIR / "storage.json").read_text(encoding="utf-8")
        )
        if not isinstance(payload, dict):
            raise ValueError("invalid storage config")
    except Exception:
        return default
    return {
        "db_path": str(payload.get("db_path", default["db_path"])).strip()
        or default["db_path"],
        "attachments_dir": str(
            payload.get("attachments_dir", default["attachments_dir"])
        ).strip()
        or default["attachments_dir"],
    }


def save_mail_storage_config(config: dict[str, str]) -> None:
    MAIL_STATE_DIR.mkdir(parents=True, exist_ok=True)
    from settings_page.settings_store import _atomic_write_json_file
    _atomic_write_json_file(MAIL_STATE_DIR / "storage.json", config)


class MailAccountStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.execute(
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
            )
            """
        )
        columns = {
            str(row["name"])
            for row in self.conn.execute("PRAGMA table_info(accounts)").fetchall()
        }
        if "avatar_path" not in columns:
            self.conn.execute(
                "ALTER TABLE accounts ADD COLUMN avatar_path TEXT NOT NULL DEFAULT ''"
            )
        self.conn.commit()

    def list_accounts(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM accounts ORDER BY lower(label), lower(email_address)"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_account(self, account_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        return dict(row) if row else None

    def save_account(self, payload: dict) -> int:
        now = mail_now_iso()
        values = (
            str(payload.get("label", "")).strip()
            or str(payload.get("email_address", "")).strip(),
            str(payload.get("email_address", "")).strip(),
            str(payload.get("display_name", "")).strip(),
            str(payload.get("avatar_path", "")).strip(),
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
            max(30, int(payload.get("poll_interval_seconds", 90) or 90)),
            now,
        )
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
            account_id = int(
                self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            )
        self.conn.commit()
        return account_id

    def delete_account(self, account_id: int) -> None:
        self.conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        try:
            self.conn.execute(
                "DELETE FROM messages WHERE account_id = ?", (account_id,)
            )
        except Exception:
            pass
        self.conn.commit()