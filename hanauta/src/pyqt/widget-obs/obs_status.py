#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import signal
import sys
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QTimer, QUrl
from PyQt6.QtWebSockets import QWebSocket


APP_DIR = Path(__file__).resolve().parents[2]
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))


def load_settings_state() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("obs", {})
    return payload


def obs_auth(password: str, salt: str, challenge: str) -> str:
    secret = hashlib.sha256((password + salt).encode("utf-8")).digest()
    secret_b64 = base64.b64encode(secret).decode("utf-8")
    return base64.b64encode(hashlib.sha256((secret_b64 + challenge).encode("utf-8")).digest()).decode("utf-8")


class ObsStatusProbe:
    def __init__(self, app: QCoreApplication) -> None:
        self.app = app
        self.settings = load_settings_state()
        self.socket = QWebSocket()
        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.errorOccurred.connect(self._on_error)
        self.socket.textMessageReceived.connect(self._on_message)
        self.pending_requests: dict[str, str] = {}
        self.request_counter = 0
        self.connected = False
        self.result = {"connected": False, "streaming": False, "recording": False}

        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._finish)
        self.timeout_timer.start(3500)

    def run(self) -> None:
        obs = self.settings.get("obs", {})
        host = str(obs.get("host", "127.0.0.1"))
        port = int(obs.get("port", 4455) or 4455)
        self.socket.open(QUrl(f"ws://{host}:{port}"))

    def _finish(self) -> None:
        print(json.dumps(self.result), flush=True)
        self.socket.abort()
        self.app.quit()

    def _on_connected(self) -> None:
        pass

    def _on_disconnected(self) -> None:
        if not self.connected:
            self._finish()

    def _on_error(self, _error) -> None:
        self._finish()

    def _send_request(self, request_type: str) -> None:
        if not self.connected:
            return
        self.request_counter += 1
        request_id = f"hanauta-obs-status-{self.request_counter}"
        self.pending_requests[request_id] = request_type
        payload = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": request_id,
                "requestData": {},
            },
        }
        self.socket.sendTextMessage(json.dumps(payload))

    def _on_message(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except Exception:
            return
        op = int(payload.get("op", -1))
        data = payload.get("d", {}) if isinstance(payload.get("d"), dict) else {}
        if op == 0:
            auth = data.get("authentication")
            identify = {"rpcVersion": int(data.get("rpcVersion", 1) or 1)}
            if isinstance(auth, dict):
                password = str(self.settings.get("obs", {}).get("password", ""))
                if password:
                    identify["authentication"] = obs_auth(password, str(auth.get("salt", "")), str(auth.get("challenge", "")))
            self.socket.sendTextMessage(json.dumps({"op": 1, "d": identify}))
            return
        if op == 2:
            self.connected = True
            self.result["connected"] = True
            self._send_request("GetStreamStatus")
            self._send_request("GetRecordStatus")
            return
        if op != 7:
            return
        request_id = str(data.get("requestId", ""))
        request_type = self.pending_requests.pop(request_id, "")
        request_status = data.get("requestStatus", {}) if isinstance(data.get("requestStatus"), dict) else {}
        if bool(request_status.get("result", False)):
            response = data.get("responseData", {}) if isinstance(data.get("responseData"), dict) else {}
            if request_type == "GetStreamStatus":
                self.result["streaming"] = bool(response.get("outputActive", False))
            elif request_type == "GetRecordStatus":
                self.result["recording"] = bool(response.get("outputActive", False))
        if not self.pending_requests:
            self._finish()


def main() -> int:
    app = QCoreApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    probe = ObsStatusProbe(app)
    probe.run()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
