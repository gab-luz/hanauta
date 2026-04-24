from __future__ import annotations

import subprocess
from pathlib import Path
import shutil


def _run_text(cmd: list[str], *, timeout: float = 2.5) -> str:
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


def list_audio_devices(kind: str) -> list[tuple[str, str]]:
    if kind not in {"sinks", "sources"}:
        return []
    if not shutil.which("pactl"):
        return []
    output = _run_text(["pactl", "list", "short", kind])
    devices: list[tuple[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        device_name = parts[1].strip()
        if device_name:
            devices.append((device_name, device_name))
    return devices


def default_audio_device(kind: str) -> str:
    if not shutil.which("pactl"):
        return ""
    command = "get-default-sink" if kind == "sink" else "get-default-source"
    return _run_text(["pactl", command]).strip()


def list_wifi_interfaces() -> list[str]:
    net_dir = Path("/sys/class/net")
    if not net_dir.exists():
        return []
    interfaces: list[str] = []
    for candidate in sorted(net_dir.iterdir()):
        if (candidate / "wireless").exists():
            interfaces.append(candidate.name)
    return interfaces


def list_wireguard_interfaces(root: Path) -> list[str]:
    vpn_script = root / "hanauta" / "scripts" / "vpn.sh"
    if not vpn_script.exists():
        return []
    return [
        line.strip()
        for line in _run_text([str(vpn_script), "--interfaces"]).splitlines()
        if line.strip()
    ]


def startup_exec_lines(root: Path) -> list[str]:
    startup_file = root / "startup.sh"
    if not startup_file.exists():
        return []
    try:
        lines = startup_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [
        line.strip()
        for line in lines
        if line.strip().startswith(("exec", "python3", "bash", "setsid"))
    ]

