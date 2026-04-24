import subprocess
from pathlib import Path

from pyqt.shared.plugin_runtime import resolve_plugin_script


ROOT = Path(__file__).resolve().parents[2].parents[1]


def resolve_qcal_wrapper() -> Path | None:
    resolved = resolve_plugin_script("qcal-wrapper.py", ["calendar"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-calendar" / "qcal-wrapper.py",
        Path.home() / "dev" / "hanauta-plugin-calendar" / "qcal-wrapper.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None


def resolve_desktop_clock_widget() -> Path | None:
    resolved = resolve_plugin_script("desktop_clock_widget.py", ["desktop-clock", "clock"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-desktop-clock" / "desktop_clock_widget.py",
        Path.home() / "dev" / "hanauta-plugin-desktop-clock" / "desktop_clock_widget.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None


def resolve_study_tracker_app() -> Path | None:
    return resolve_plugin_script("study_tracker.py", ["study-tracker"])


def resolve_virtualization_daemon() -> Path | None:
    return resolve_plugin_script("virtualization_daemon.py", ["virtualization"])


def resolve_email_client_app() -> Path | None:
    return resolve_plugin_script("email_client.py", ["email-client", "mail"])


SERVICE_CACHE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
BAR_SERVICE_CACHE_FILE = SERVICE_CACHE_DIR / "plugins" / "bar-services.json"
SERVICES_SECTION_CACHE_FILE = SERVICE_CACHE_DIR / "plugins" / "services-sections.json"


def load_service_cache_json(name: str) -> dict:
    import json
    path = SERVICE_CACHE_DIR / name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_bg(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    try:
        subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
        )
    except Exception:
        pass


def run_text(cmd: list[str], timeout: float = 2.5) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""