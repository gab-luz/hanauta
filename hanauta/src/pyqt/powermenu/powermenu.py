#!/usr/bin/env python3
import os
import sys
import getpass
import shutil
import subprocess
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QTimer, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _read_uptime_seconds() -> int | None:
    # Linux: /proc/uptime -> "<seconds> <idle>"
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            first = f.read().strip().split()[0]
        return int(float(first))
    except Exception:
        return None


def _format_uptime(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"

    # Format similar to "2 days, 4 hours"
    days = seconds // 86400
    rem = seconds % 86400
    hours = rem // 3600
    rem %= 3600
    minutes = rem // 60

    parts: list[str] = []
    if days:
        parts.append(f"{days} day" + ("s" if days != 1 else ""))
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if not parts:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))

    return ", ".join(parts)


def _spawn(cmd: list[str]) -> tuple[bool, str]:
    """
    Fire-and-forget spawn. Returns (ok, message).
    """
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True, "Command executed."
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, f"Failed to run: {' '.join(cmd)} ({e})"


class Backend(QObject):
    notify = pyqtSignal(str)

    usernameChanged = pyqtSignal()
    uptimeChanged = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._username = getpass.getuser()
        self._uptime = _format_uptime(_read_uptime_seconds())

        self._timer = QTimer(self)
        self._timer.setInterval(30_000)  # update every 30s
        self._timer.timeout.connect(self._refresh_uptime)
        self._timer.start()

    def _refresh_uptime(self) -> None:
        new_val = _format_uptime(_read_uptime_seconds())
        if new_val != self._uptime:
            self._uptime = new_val
            self.uptimeChanged.emit()

    @pyqtProperty(str, notify=usernameChanged)
    def username(self) -> str:
        return self._username

    @pyqtProperty(str, notify=uptimeChanged)
    def uptime(self) -> str:
        return self._uptime

    @pyqtSlot()
    def close(self) -> None:
        QGuiApplication.quit()

    @pyqtSlot(str)
    def perform(self, action: str) -> None:
        action = (action or "").strip().lower()
        if not action:
            self.notify.emit("Invalid action.")
            return

        ok = False
        msg = ""

        if action == "shutdown":
            ok, msg = self._shutdown()
        elif action == "restart":
            ok, msg = self._restart()
        elif action == "sleep":
            ok, msg = self._sleep()
        elif action == "logout":
            ok, msg = self._logout()
        else:
            self.notify.emit(f"Unknown action: {action}")
            return

        if ok:
            # For power actions, quit UI immediately to feel snappy.
            self.notify.emit("Done.")
            QTimer.singleShot(200, QGuiApplication.quit)
        else:
            self.notify.emit(msg)

    def _shutdown(self) -> tuple[bool, str]:
        # Prefer systemctl, then fallback poweroff
        candidates = []
        if _which("systemctl"):
            candidates.append(["systemctl", "poweroff"])
        if _which("loginctl"):
            candidates.append(["loginctl", "poweroff"])
        if _which("poweroff"):
            candidates.append(["poweroff"])

        for cmd in candidates:
            ok, msg = _spawn(cmd)
            if ok:
                return True, "Shutting down..."
        return False, "Unable to shutdown (no supported command found)."

    def _restart(self) -> tuple[bool, str]:
        candidates = []
        if _which("systemctl"):
            candidates.append(["systemctl", "reboot"])
        if _which("loginctl"):
            candidates.append(["loginctl", "reboot"])
        if _which("reboot"):
            candidates.append(["reboot"])

        for cmd in candidates:
            ok, msg = _spawn(cmd)
            if ok:
                return True, "Restarting..."
        return False, "Unable to restart (no supported command found)."

    def _sleep(self) -> tuple[bool, str]:
        candidates = []
        if _which("systemctl"):
            candidates.append(["systemctl", "suspend"])
        if _which("loginctl"):
            candidates.append(["loginctl", "suspend"])

        for cmd in candidates:
            ok, msg = _spawn(cmd)
            if ok:
                return True, "Suspending..."
        return False, "Unable to sleep (no supported command found)."

    def _logout(self) -> tuple[bool, str]:
        # Best effort for i3 / bspwm. (Your environment.)
        candidates: list[list[str]] = []
        if _which("i3-msg"):
            candidates.append(["i3-msg", "exit"])
        if _which("bspc"):
            candidates.append(["bspc", "quit"])

        # systemd session fallback (if available)
        xdg_session_id = os.environ.get("XDG_SESSION_ID", "").strip()
        if xdg_session_id and _which("loginctl"):
            candidates.append(["loginctl", "terminate-session", xdg_session_id])

        for cmd in candidates:
            ok, msg = _spawn(cmd)
            if ok:
                return True, "Logging out..."
        return False, "Unable to logout (no supported command found)."


def main() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Hanauta Power Menu")
    app.setDesktopFileName("HanautaPowerMenu")

    base_dir = Path(__file__).resolve().parent
    qml_path = base_dir / "powermenu.qml"
    if not qml_path.exists():
        print(f"ERROR: QML file not found: {qml_path}", file=sys.stderr)
        return 2

    engine = QQmlApplicationEngine()

    backend = Backend()
    engine.rootContext().setContextProperty("backend", backend)

    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        print("ERROR: failed to load QML (no root objects).", file=sys.stderr)
        return 3

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
