#!/usr/bin/env python3
from __future__ import annotations

import argparse
import grp
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

GROUP_NAME = "hanauta-vpn-bypass"
IPTABLES_CANDIDATES = (
    Path("/usr/sbin/iptables"),
    Path("/sbin/iptables"),
    Path("/usr/bin/iptables"),
)
IP6TABLES_CANDIDATES = (
    Path("/usr/sbin/ip6tables"),
    Path("/sbin/ip6tables"),
    Path("/usr/bin/ip6tables"),
)
GROUPADD_CANDIDATES = (
    Path("/usr/sbin/groupadd"),
    Path("/sbin/groupadd"),
    Path("/usr/bin/groupadd"),
)


def command_path(candidates: tuple[Path, ...], fallback: str) -> str:
    for path in candidates:
        if path.exists():
            return str(path)
    found = shutil.which(fallback)
    if found:
        return found
    raise RuntimeError(f"Missing required command: {fallback}")


def parse_group_ids(raw: str) -> list[int]:
    values: list[int] = []
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            values.append(int(chunk))
        except ValueError:
            continue
    return values


def ensure_group() -> grp.struct_group:
    try:
        return grp.getgrnam(GROUP_NAME)
    except KeyError:
        groupadd = command_path(GROUPADD_CANDIDATES, "groupadd")
        result = subprocess.run(
            [groupadd, "--system", GROUP_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(stderr or f"Failed to create {GROUP_NAME}.")
        return grp.getgrnam(GROUP_NAME)


def current_fwmark(interface: str) -> str:
    result = subprocess.run(
        ["wg", "show", interface, "fwmark"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = (result.stdout or "").strip()
    if result.returncode != 0 or not value or value == "off":
        raise RuntimeError(f"WireGuard interface {interface} is not active.")
    return value


def ensure_mark_rule(binary: str, group_id: int, fwmark: str) -> None:
    rule = [
        binary,
        "-t",
        "mangle",
        "-m",
        "owner",
        "--gid-owner",
        str(group_id),
        "--suppl-groups",
        "-j",
        "MARK",
        "--set-mark",
        fwmark,
    ]
    check = subprocess.run(
        rule[:3] + ["-C", "OUTPUT"] + rule[3:],
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode == 0:
        return
    add = subprocess.run(
        rule[:3] + ["-A", "OUTPUT"] + rule[3:],
        capture_output=True,
        text=True,
        check=False,
    )
    if add.returncode != 0:
        stderr = (add.stderr or "").strip()
        raise RuntimeError(stderr or "Failed to configure split-tunnel packet marking.")


def ensure_mark_rules(group_id: int, fwmark: str) -> None:
    ensure_mark_rule(command_path(IPTABLES_CANDIDATES, "iptables"), group_id, fwmark)
    ensure_mark_rule(command_path(IP6TABLES_CANDIDATES, "ip6tables"), group_id, fwmark)


def ensure_cgroup_mark_rule(binary: str, cgroup_path: str, fwmark: str) -> None:
    rule = [
        binary,
        "-t",
        "mangle",
        "-m",
        "cgroup",
        "--path",
        cgroup_path,
        "-j",
        "MARK",
        "--set-mark",
        fwmark,
    ]
    check = subprocess.run(
        rule[:3] + ["-C", "OUTPUT"] + rule[3:],
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode == 0:
        return
    add = subprocess.run(
        rule[:3] + ["-A", "OUTPUT"] + rule[3:],
        capture_output=True,
        text=True,
        check=False,
    )
    if add.returncode != 0:
        stderr = (add.stderr or "").strip()
        raise RuntimeError(stderr or "Failed to configure split-tunnel cgroup marking.")


def ensure_cgroup_mark_rules(cgroup_path: str, fwmark: str) -> None:
    ensure_cgroup_mark_rule(command_path(IPTABLES_CANDIDATES, "iptables"), cgroup_path, fwmark)
    ensure_cgroup_mark_rule(command_path(IP6TABLES_CANDIDATES, "ip6tables"), cgroup_path, fwmark)


def _desktop_exec_from_file(source_path: str) -> list[str] | None:
    path = Path(source_path).expanduser()
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    in_entry = False
    exec_line = ""
    app_name = ""
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
            continue
        if not in_entry or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "Exec" and not exec_line:
            exec_line = value
        elif key == "Name" and not app_name:
            app_name = value
        if exec_line and app_name:
            break

    if not exec_line:
        return None
    # Remove desktop entry placeholders so we can execute directly.
    sanitized = re.sub(r"%[fFuUdDnNickvm]", "", exec_line).strip()
    if "%c" in sanitized:
        sanitized = sanitized.replace("%c", app_name or path.stem)
    if "%k" in sanitized:
        sanitized = sanitized.replace("%k", str(path))
    command = [part for part in shlex.split(sanitized) if part]
    return command or None


def build_command(mode: str, target: str, source_path: str = "") -> list[str]:
    if mode == "desktop":
        source = source_path.strip()
        if source:
            direct = _desktop_exec_from_file(source)
            if direct:
                return direct
            return ["gio", "launch", source]
        desktop_id = target.strip()
        desktop_base = desktop_id[:-8] if desktop_id.endswith(".desktop") else target.strip()
        return ["bash", "-lc", f"gtk-launch {shlex.quote(desktop_id)} || gtk-launch {shlex.quote(desktop_base)}"]
    if mode == "flatpak":
        return ["flatpak", "run", target.strip()]
    if mode == "binary":
        command = [part for part in shlex.split(target.strip()) if part]
        if command:
            return command
    raise RuntimeError("Unsupported split-tunnel target.")


def launch_target(args: argparse.Namespace) -> None:
    if os.geteuid() != 0:
        raise RuntimeError("vpn_bypass_helper.py must be started through pkexec.")

    bypass_group = ensure_group()
    if args.interface:
        ensure_mark_rules(bypass_group.gr_gid, current_fwmark(args.interface))

    user_groups = parse_group_ids(args.groups)
    merged_groups: list[int] = []
    for group_id in user_groups + [bypass_group.gr_gid]:
        if group_id not in merged_groups:
            merged_groups.append(group_id)

    env_vars = {
        "HOME": args.home,
        "USER": args.user,
        "LOGNAME": args.user,
        "PATH": args.path or os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "XDG_RUNTIME_DIR": args.runtime_dir or f"/run/user/{args.uid}",
    }
    optional_env = {
        "DISPLAY": args.display,
        "DBUS_SESSION_BUS_ADDRESS": args.dbus_address,
        "XAUTHORITY": args.xauthority,
        "WAYLAND_DISPLAY": args.wayland_display,
        "XDG_CURRENT_DESKTOP": args.current_desktop,
        "DESKTOP_SESSION": args.desktop_session,
    }
    for key, value in optional_env.items():
        if value:
            env_vars[key] = value

    command = build_command(args.mode, args.target, args.source_path)
    prefix = [
        "setpriv",
        f"--reuid={args.uid}",
        f"--regid={args.gid}",
        f"--groups={','.join(str(group_id) for group_id in merged_groups)}",
        "--reset-env",
        "env",
    ]
    for key, value in env_vars.items():
        prefix.append(f"{key}={value}")

    subprocess.Popen(
        prefix + command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def ensure_cgroup_target(args: argparse.Namespace) -> None:
    if os.geteuid() != 0:
        raise RuntimeError("vpn_bypass_helper.py must be started through pkexec.")
    if not args.interface:
        raise RuntimeError("Missing WireGuard interface for cgroup rule setup.")
    if not args.cgroup_path.strip():
        raise RuntimeError("Missing cgroup path for split tunneling.")
    ensure_cgroup_mark_rules(args.cgroup_path.strip(), current_fwmark(args.interface))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--ensure-cgroup-rule", action="store_true")
    parser.add_argument("--mode", choices=("desktop", "flatpak", "binary"), default="desktop")
    parser.add_argument("--target", default="")
    parser.add_argument("--source-path", default="")
    parser.add_argument("--cgroup-path", default="")
    parser.add_argument("--interface", default="")
    parser.add_argument("--uid", type=int, default=0)
    parser.add_argument("--gid", type=int, default=0)
    parser.add_argument("--groups", default="")
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--user", default=os.environ.get("USER", "user"))
    parser.add_argument("--display", default=os.environ.get("DISPLAY", ""))
    parser.add_argument("--dbus-address", default=os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""))
    parser.add_argument("--xauthority", default=os.environ.get("XAUTHORITY", ""))
    parser.add_argument("--runtime-dir", default=os.environ.get("XDG_RUNTIME_DIR", ""))
    parser.add_argument("--wayland-display", default=os.environ.get("WAYLAND_DISPLAY", ""))
    parser.add_argument("--current-desktop", default=os.environ.get("XDG_CURRENT_DESKTOP", ""))
    parser.add_argument("--desktop-session", default=os.environ.get("DESKTOP_SESSION", ""))
    parser.add_argument("--path", default=os.environ.get("PATH", ""))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not args.launch and not args.ensure_cgroup_rule:
        parser.print_usage(sys.stderr)
        return 2
    try:
        if args.ensure_cgroup_rule:
            ensure_cgroup_target(args)
        else:
            launch_target(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
