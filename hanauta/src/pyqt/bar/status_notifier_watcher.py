#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal StatusNotifierWatcher service for the PyQt bar.
"""

from __future__ import annotations

import asyncio
import signal

from dbus_next import BusType, Message, Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import MessageType


WATCHER_INTERFACE = "org.kde.StatusNotifierWatcher"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
WATCHER_PATH = "/StatusNotifierWatcher"


class StatusNotifierWatcher:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._items: list[str] = []
        self._hosts: list[str] = []

    def handle_message(self, msg: Message) -> Message | None | bool:
        if msg.message_type == MessageType.SIGNAL:
            return self._handle_signal(msg)

        if msg.message_type != MessageType.METHOD_CALL or msg.path != WATCHER_PATH:
            return None

        if msg.interface == WATCHER_INTERFACE:
            if msg.member == "RegisterStatusNotifierItem":
                return self._register_item(msg)
            if msg.member == "RegisterStatusNotifierHost":
                return self._register_host(msg)

        if msg.interface == PROPERTIES_INTERFACE:
            if msg.member == "Get":
                return self._get_property(msg)
            if msg.member == "GetAll":
                return self._get_all_properties(msg)

        return None

    def _normalize_item_id(self, msg: Message) -> str:
        raw_value = str(msg.body[0]).strip() if msg.body else ""
        if not raw_value:
            return ""
        if raw_value.startswith("/"):
            sender = (msg.sender or "").strip()
            return f"{sender}{raw_value}" if sender else raw_value
        return raw_value

    def _register_item(self, msg: Message) -> Message:
        item_id = self._normalize_item_id(msg)
        if item_id and item_id not in self._items:
            self._items.append(item_id)
            self._emit_signal("StatusNotifierItemRegistered", "s", [item_id])
        return Message.new_method_return(msg)

    def _register_host(self, msg: Message) -> Message:
        host = str(msg.body[0]).strip() if msg.body else ""
        if host and host not in self._hosts:
            self._hosts.append(host)
            self._emit_signal("StatusNotifierHostRegistered")
        return Message.new_method_return(msg)

    def _get_property(self, msg: Message) -> Message:
        interface_name = str(msg.body[0]) if len(msg.body) > 0 else ""
        property_name = str(msg.body[1]) if len(msg.body) > 1 else ""
        if interface_name != WATCHER_INTERFACE:
            return Message.new_error(msg, "org.freedesktop.DBus.Error.InvalidArgs", "Unknown interface")
        if property_name == "RegisteredStatusNotifierItems":
            value = Variant("as", list(self._items))
        elif property_name == "IsStatusNotifierHostRegistered":
            value = Variant("b", bool(self._hosts))
        elif property_name == "ProtocolVersion":
            value = Variant("i", 0)
        else:
            return Message.new_error(msg, "org.freedesktop.DBus.Error.InvalidArgs", "Unknown property")
        return Message.new_method_return(msg, "v", [value])

    def _get_all_properties(self, msg: Message) -> Message:
        interface_name = str(msg.body[0]) if msg.body else ""
        if interface_name != WATCHER_INTERFACE:
            return Message.new_error(msg, "org.freedesktop.DBus.Error.InvalidArgs", "Unknown interface")
        payload = {
            "RegisteredStatusNotifierItems": Variant("as", list(self._items)),
            "IsStatusNotifierHostRegistered": Variant("b", bool(self._hosts)),
            "ProtocolVersion": Variant("i", 0),
        }
        return Message.new_method_return(msg, "a{sv}", [payload])

    def _handle_signal(self, msg: Message) -> bool | None:
        if (
            msg.interface != "org.freedesktop.DBus"
            or msg.member != "NameOwnerChanged"
            or len(msg.body) < 3
        ):
            return None

        name, _old_owner, new_owner = (str(part) for part in msg.body[:3])
        if new_owner:
            return None

        removed_items = [item_id for item_id in self._items if item_id == name or item_id.startswith(f"{name}/")]
        for item_id in removed_items:
            self._items.remove(item_id)
            self._emit_signal("StatusNotifierItemUnregistered", "s", [item_id])
        if name in self._hosts:
            self._hosts.remove(name)
        return None

    def _emit_signal(self, member: str, signature: str = "", body: list | None = None) -> None:
        self.bus.send(
            Message.new_signal(
                WATCHER_PATH,
                WATCHER_INTERFACE,
                member,
                signature,
                body or [],
            )
        )


async def _main() -> int:
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    watcher = StatusNotifierWatcher(bus)
    bus.add_message_handler(watcher.handle_message)
    await bus.request_name(WATCHER_INTERFACE)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass
    await stop_event.wait()
    bus.disconnect()
    return 0


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())
