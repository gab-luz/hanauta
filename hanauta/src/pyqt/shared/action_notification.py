#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import subprocess
import sys

from dbus_next import Variant
from dbus_next.aio import MessageBus


def auth_token(password: str, salt: str, challenge: str) -> str:
    secret = hashlib.sha256((password + salt).encode("utf-8")).digest()
    return hashlib.sha256((secret.hex() + challenge).encode("utf-8")).hexdigest()


async def send_action_notification(args: argparse.Namespace) -> int:
    bus = await MessageBus().connect()
    introspection = await bus.introspect("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
    obj = bus.get_proxy_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications", introspection)
    interface = obj.get_interface("org.freedesktop.Notifications")

    done = asyncio.Event()
    state = {"id": 0}

    def on_action(notification_id: int, action_key: str) -> None:
        if int(notification_id) != int(state["id"]):
            return
        if action_key == args.action_key:
            if args.command:
                try:
                    subprocess.Popen(
                        [args.command, *args.command_arg],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except Exception:
                    pass
            elif args.open_url:
                try:
                    subprocess.Popen(
                        ["xdg-open", args.open_url],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except Exception:
                    pass
        done.set()

    def on_closed(notification_id: int, _reason: int) -> None:
        if int(notification_id) == int(state["id"]):
            done.set()

    interface.on_action_invoked(on_action)
    interface.on_notification_closed(on_closed)
    hints = {}
    if args.replace_id > 0:
        hints["x-canonical-private-synchronous"] = Variant("s", f"hanauta-{args.replace_id}")
    state["id"] = await interface.call_notify(
        args.app_name,
        int(args.replace_id),
        "",
        args.summary,
        args.body,
        [args.action_key, args.action_label] if args.action_label else [],
        hints,
        int(args.expire_ms),
    )
    try:
        await asyncio.wait_for(done.wait(), timeout=max(5.0, args.timeout))
    except asyncio.TimeoutError:
        pass
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send a Hanauta notification with a clickable action.")
    parser.add_argument("--app-name", default="Hanauta")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--action-key", default="open")
    parser.add_argument("--action-label", default="Open")
    parser.add_argument("--open-url", default="")
    parser.add_argument("--command", default="")
    parser.add_argument("--command-arg", action="append", default=[])
    parser.add_argument("--expire-ms", type=int, default=15000)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--replace-id", type=int, default=0)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(send_action_notification(args))


if __name__ == "__main__":
    raise SystemExit(main())
