from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SETTINGS_FILE = STATE_DIR / "settings.json"

PYQT_THEME_DIR = Path.home() / ".local" / "state" / "hanauta" / "theme"
PYQT_THEME_FILE = PYQT_THEME_DIR / "pyqt_palette.json"


def _atomic_write_json_file(path: Path, payload_obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(payload_obj, indent=2)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f"{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(str(temp_path), str(path))
    except OSError as exc:
        raise OSError(f"failed to write {path.name} ({exc})") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def save_settings_state(settings: dict) -> None:
    _atomic_write_json_file(SETTINGS_FILE, settings)

