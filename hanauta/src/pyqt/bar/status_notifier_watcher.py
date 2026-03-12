#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal StatusNotifierWatcher service for the PyQt bar.
"""

from __future__ import annotations

import asyncio
import signal

from dbus_next import BusType
from dbus_next.aio import MessageBus
from dbus_next.constants import PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method, signal as dbus_signal


class StatusNotifierWatcher(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.kde.StatusNotifierWatcher")
        self._items: list[str] = []
        self._hosts: list[str] = []

    @method()
    def RegisterStatusNotifierItem(self, service_or_path: "s") -> "":
        item_id = service_or_path.strip()
        if not item_id:
            return
        if item_id not in self._items:
            self._items.append(item_id)
            self.StatusNotifierItemRegistered(item_id)

    @method()
    def RegisterStatusNotifierHost(self, service: "s") -> "":
        host = service.strip()
        if host and host not in self._hosts:
            self._hosts.append(host)
        self.StatusNotifierHostRegistered()

    @dbus_property(access=PropertyAccess.READ, name="RegisteredStatusNotifierItems")
    def registered_status_notifier_items(self) -> "as":
        return list(self._items)

    @dbus_property(access=PropertyAccess.READ, name="IsStatusNotifierHostRegistered")
    def is_status_notifier_host_registered(self) -> "b":
        return bool(self._hosts)

    @dbus_property(access=PropertyAccess.READ, name="ProtocolVersion")
    def protocol_version(self) -> "i":
        return 0

    @dbus_signal()
    def StatusNotifierItemRegistered(self, service: "s") -> "s":
        return service

    @dbus_signal()
    def StatusNotifierItemUnregistered(self, service: "s") -> "s":
        return service

    @dbus_signal()
    def StatusNotifierHostRegistered(self) -> "":
        return ""


async def _main() -> int:
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    watcher = StatusNotifierWatcher()
    bus.export("/StatusNotifierWatcher", watcher)
    await bus.request_name("org.kde.StatusNotifierWatcher")

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
