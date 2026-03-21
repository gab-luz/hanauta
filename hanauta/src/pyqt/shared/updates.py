from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pyqt.shared.runtime import entry_command


APP_DIR = Path(__file__).resolve().parents[2]
ACTION_NOTIFICATION_SCRIPT = APP_DIR / "pyqt" / "shared" / "action_notification.py"


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def read_os_release() -> dict[str, str]:
    payload: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.exists():
        return payload
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            payload[key.strip()] = value.strip().strip('"')
    except Exception:
        return {}
    return payload


def detect_system_backend() -> tuple[str, str]:
    os_release = read_os_release()
    distro_name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Linux"
    distro_id = os_release.get("ID", "").strip().lower()
    distro_like = os_release.get("ID_LIKE", "").strip().lower()
    distro_tokens = {token for token in (distro_id + " " + distro_like).split() if token}
    if "arch" in distro_tokens and (command_exists("checkupdates") or command_exists("pacman")):
        return "arch", distro_name
    if ("debian" in distro_tokens or "ubuntu" in distro_tokens) and command_exists("apt"):
        return "apt", distro_name
    if command_exists("apt"):
        return "apt", distro_name
    if command_exists("checkupdates") or command_exists("pacman"):
        return "arch", distro_name
    return "none", distro_name


def run_command(cmd: list[str], timeout: int = 45) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except Exception as exc:
        return 1, "", str(exc)
    return result.returncode, result.stdout, result.stderr


def parse_apt_updates() -> tuple[list[str], str]:
    code, stdout, stderr = run_command(["apt", "list", "--upgradable"])
    if code != 0 and not stdout.strip():
        return [], stderr.strip() or "Unable to query apt updates."
    lines: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("Listing..."):
            continue
        lines.append(line)
    return lines, ""


def count_apt_security_updates() -> int:
    try:
        import apt  # type: ignore
    except Exception:
        return 0
    try:
        cache = apt.Cache()
        cache.open(None)
    except Exception:
        return 0
    count = 0
    for pkg in cache:
        try:
            if not pkg.is_upgradable:
                continue
            candidate = pkg.candidate
            origins = getattr(candidate, "origins", []) or []
            if any("security" in str(getattr(origin, "archive", "")).lower() for origin in origins):
                count += 1
        except Exception:
            continue
    return count


def parse_arch_updates() -> tuple[list[str], str]:
    if command_exists("checkupdates"):
        code, stdout, stderr = run_command(["checkupdates"])
        if code not in {0, 2} and not stdout.strip():
            return [], stderr.strip() or "Unable to query Arch updates."
        return [line.strip() for line in stdout.splitlines() if line.strip()], ""
    if command_exists("pacman"):
        code, stdout, stderr = run_command(["pacman", "-Qu"])
        if code not in {0, 1} and not stdout.strip():
            return [], stderr.strip() or "Unable to query pacman updates."
        return [line.strip() for line in stdout.splitlines() if line.strip()], ""
    return [], "pacman/checkupdates not available."


def parse_flatpak_updates() -> tuple[list[str], str]:
    if not command_exists("flatpak"):
        return [], ""
    code, stdout, stderr = run_command(
        ["flatpak", "remote-ls", "--updates", "--columns=application,name,version,branch"]
    )
    if code != 0 and not stdout.strip():
        return [], stderr.strip() or "Unable to query Flatpak updates."
    lines: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("application"):
            continue
        lines.append(" ".join(line.split()))
    return lines, ""


def choose_system_upgrade_command(backend: str) -> str:
    if backend == "apt":
        return "sudo apt update && sudo apt upgrade -y"
    if backend == "arch":
        if command_exists("paru"):
            return "paru -Syu"
        if command_exists("yay"):
            return "yay -Syu"
        return "sudo pacman -Syu"
    return ""


def has_system_flatpak_installation() -> bool:
    system_paths = [
        Path("/var/lib/flatpak"),
        Path("/etc/flatpak"),
    ]
    return any(path.exists() for path in system_paths)


def build_flatpak_upgrade_command() -> str:
    if not command_exists("flatpak"):
        return ""
    commands = [
        "flatpak repair --user -y || true",
        "flatpak update --user -y",
    ]
    if has_system_flatpak_installation():
        if command_exists("pkexec"):
            commands.append("pkexec flatpak repair --system -y || true")
            commands.append("pkexec flatpak update --system -y")
        else:
            commands.append("flatpak repair --system -y || true")
            commands.append("flatpak update --system -y")
    return " && ".join(commands)


def collect_update_payload() -> dict:
    backend, distro_name = detect_system_backend()
    system_updates: list[str] = []
    flatpak_updates: list[str] = []
    notes: list[str] = []

    if backend == "apt":
        system_updates, error = parse_apt_updates()
        security_updates = count_apt_security_updates()
        if error:
            notes.append(error)
    elif backend == "arch":
        system_updates, error = parse_arch_updates()
        security_updates = 0
        if error:
            notes.append(error)
    else:
        security_updates = 0
        notes.append("No supported system package backend detected.")

    flatpak_updates, flatpak_error = parse_flatpak_updates()
    if flatpak_error:
        notes.append(flatpak_error)

    return {
        "backend": backend,
        "distro_name": distro_name,
        "system_updates": system_updates,
        "flatpak_updates": flatpak_updates,
        "security_updates": int(security_updates),
        "system_command": choose_system_upgrade_command(backend),
        "flatpak_command": build_flatpak_upgrade_command(),
        "notes": notes,
    }


def updates_signature(payload: dict) -> str:
    system_updates = [str(item).strip() for item in payload.get("system_updates", []) if str(item).strip()]
    flatpak_updates = [str(item).strip() for item in payload.get("flatpak_updates", []) if str(item).strip()]
    security_updates = int(payload.get("security_updates", 0) or 0)
    backend = str(payload.get("backend", "none"))
    parts = [
        backend,
        str(security_updates),
        "|".join(system_updates),
        "|".join(flatpak_updates),
    ]
    return "||".join(parts)


def build_notification(summary_payload: dict) -> tuple[str, str]:
    system_count = len([item for item in summary_payload.get("system_updates", []) if str(item).strip()])
    flatpak_count = len([item for item in summary_payload.get("flatpak_updates", []) if str(item).strip()])
    security_count = int(summary_payload.get("security_updates", 0) or 0)
    total = system_count + flatpak_count
    summary = f"{total} update(s) pending"
    body = (
        f"System: {system_count} • Flatpak: {flatpak_count} • Security: {security_count}\n"
        "Always create a full system backup before applying updates."
    )
    return summary, body


def send_update_notification(summary: str, body: str, replace_id: int = 31001) -> bool:
    if not ACTION_NOTIFICATION_SCRIPT.exists():
        return False
    command = entry_command(
        ACTION_NOTIFICATION_SCRIPT,
        "--app-name",
        "Hanauta Updates",
        "--summary",
        summary,
        "--body",
        body,
        "--action-label",
        "",
        "--expire-ms",
        "10000",
        "--timeout",
        "12",
        "--replace-id",
        str(replace_id),
    )
    if not command:
        return False
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False
