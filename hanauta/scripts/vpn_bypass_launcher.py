#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
VPN_SCRIPT = ROOT / "scripts" / "vpn.sh"
HELPER_SCRIPT = ROOT / "scripts" / "vpn_bypass_helper.py"


def run_text(command: list[str], timeout: float = 8.0) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def load_vpn_settings() -> dict[str, object]:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return {}
    vpn = services.get("vpn_control", {})
    return vpn if isinstance(vpn, dict) else {}


def load_vpn_status() -> dict[str, str]:
    raw = run_text([str(VPN_SCRIPT), "--status"])
    if not raw:
        return {"wireguard": "off", "wg_selected": ""}
    try:
        payload = json.loads(raw)
    except Exception:
        return {"wireguard": "off", "wg_selected": ""}
    return {
        "wireguard": str(payload.get("wireguard", "off")),
        "wg_selected": str(payload.get("wg_selected", "")),
    }


def direct_launch(args: argparse.Namespace) -> int:
    try:
        if args.mode == "desktop":
            if args.source_path:
                result = subprocess.run(
                    ["gio", "launch", args.source_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if result.returncode == 0:
                    return 0
            desktop_id = args.target.strip()
            desktop_base = desktop_id[:-8] if desktop_id.endswith(".desktop") else desktop_id
            result = subprocess.run(["gtk-launch", desktop_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if result.returncode != 0:
                subprocess.Popen(["gtk-launch", desktop_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
        if args.mode == "flatpak":
            subprocess.Popen(["flatpak", "run", args.target.strip()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
        if args.mode == "binary":
            command = [part for part in shlex.split(args.target.strip()) if part]
            if not command:
                return 1
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
    except Exception:
        return 1
    return 1


def flatpak_slice_name(target: str) -> str:
    slug = "".join(ch.lower() for ch in target if ch.isalnum())
    digest = hashlib.sha1(target.encode("utf-8")).hexdigest()[:8]
    return f"hanautaflatpak{slug[:24]}{digest}.slice"


def flatpak_cgroup_path(uid: int, slice_name: str) -> str:
    return f"/user.slice/user-{uid}.slice/user@{uid}.service/{slice_name}"


def bypass_flatpak_launch(args: argparse.Namespace, interface: str) -> int:
    uid = os.getuid()
    slice_name = flatpak_slice_name(args.target)
    setup_command = [
        "pkexec",
        sys.executable,
        str(HELPER_SCRIPT),
        "--ensure-cgroup-rule",
        "--interface",
        interface,
        "--cgroup-path",
        flatpak_cgroup_path(uid, slice_name),
    ]
    setup = subprocess.run(setup_command, check=False)
    if setup.returncode != 0:
        return int(setup.returncode)
    launch_command = [
        "systemd-run",
        "--user",
        "--scope",
        f"--slice={slice_name}",
        "flatpak",
        "run",
        args.target,
    ]
    launched = subprocess.run(launch_command, check=False)
    return int(launched.returncode)


def bypass_launch(args: argparse.Namespace, interface: str) -> int:
    if args.mode == "flatpak":
        return bypass_flatpak_launch(args, interface)
    command = [
        "pkexec",
        sys.executable,
        str(HELPER_SCRIPT),
        "--launch",
        "--mode",
        args.mode,
        "--target",
        args.target,
        "--interface",
        interface,
        "--uid",
        str(os.getuid()),
        "--gid",
        str(os.getgid()),
        "--groups",
        ",".join(str(group_id) for group_id in os.getgroups()),
        "--home",
        str(Path.home()),
        "--user",
        os.environ.get("USER", "user"),
        "--display",
        os.environ.get("DISPLAY", ""),
        "--dbus-address",
        os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
        "--xauthority",
        os.environ.get("XAUTHORITY", ""),
        "--runtime-dir",
        os.environ.get("XDG_RUNTIME_DIR", ""),
        "--wayland-display",
        os.environ.get("WAYLAND_DISPLAY", ""),
        "--current-desktop",
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        "--desktop-session",
        os.environ.get("DESKTOP_SESSION", ""),
    ]
    if args.source_path:
        command.extend(["--source-path", args.source_path])
    result = subprocess.run(command, check=False)
    return int(result.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=("desktop", "flatpak", "binary"), required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--source-path", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    settings = load_vpn_settings()
    status = load_vpn_status()
    active = status.get("wireguard") == "on"
    interface = (
        status.get("wg_selected", "").strip()
        or str(settings.get("preferred_interface", "")).strip()
        or "wg0"
    )
    if not active:
        return direct_launch(args)
    if not HELPER_SCRIPT.exists():
        return direct_launch(args)
    return bypass_launch(args, interface)


if __name__ == "__main__":
    raise SystemExit(main())
