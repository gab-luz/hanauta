from __future__ import annotations

import json

from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "hanauta-settings"


class InstanceServer(QLocalServer):
    """Listens for incoming navigation requests from new settings.py instances."""

    def __init__(self, window):
        super().__init__()
        self._window = window
        self.newConnection.connect(self._handle)

    def _handle(self) -> None:
        sock = self.nextPendingConnection()
        if sock is not None:
            sock.readyRead.connect(lambda s=sock: self._read(s))

    def _read(self, sock: QLocalSocket) -> None:
        try:
            msg = json.loads(sock.readAll().data().decode())
        except Exception:
            sock.deleteLater()
            return
        page = str(msg.get("page", "")).strip()
        section = str(msg.get("service_section", "")).strip()
        if page:
            self._window.initial_service_section = section
            self._window._show_page(page)
        self._window.raise_()
        self._window.activateWindow()
        sock.deleteLater()


def try_send_to_existing(page: str, service_section: str) -> bool:
    """Send navigation request to an already-running settings instance.
    Returns True if the request was delivered successfully."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(300):
        return False
    payload = json.dumps({"page": page, "service_section": service_section})
    sock.write(payload.encode())
    sock.waitForBytesWritten(300)
    sock.disconnectFromServer()
    return True
