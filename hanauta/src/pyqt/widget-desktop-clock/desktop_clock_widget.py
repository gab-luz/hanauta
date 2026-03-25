#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, QRectF, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen, QPolygonF, QRegion
from PyQt6.QtWidgets import QApplication, QWidget


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
BAR_HEIGHT = 45

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for key, path in {
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "ui_display": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
    }.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def load_settings_state() -> dict:
    default = {
        "clock": {
            "size": 320,
            "show_seconds": True,
            "position_x": -1,
            "position_y": -1,
        },
        "region": {
            "use_24_hour": False,
        },
    }
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default
    clock = payload.get("clock", {})
    if isinstance(clock, dict):
        default["clock"].update(clock)
    region = payload.get("region", {})
    if isinstance(region, dict):
        default["region"].update(region)
    return default


def save_clock_position(x: int, y: int) -> None:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    clock = payload.setdefault("clock", {})
    if not isinstance(clock, dict):
        clock = {}
        payload["clock"] = clock
    clock["position_x"] = int(x)
    clock["position_y"] = int(y)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_cmd(cmd: list[str], timeout: float = 2.0) -> str:
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


def load_bar_height() -> int:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return BAR_HEIGHT
    bar = payload.get("bar", {})
    if not isinstance(bar, dict):
        return BAR_HEIGHT
    try:
        return max(32, min(72, int(bar.get("bar_height", BAR_HEIGHT))))
    except Exception:
        return BAR_HEIGHT


def focused_workspace_rect() -> dict | None:
    raw = run_cmd(["i3-msg", "-t", "get_workspaces"], timeout=2.0)
    if not raw:
        return None
    try:
        workspaces = json.loads(raw)
    except Exception:
        return None
    if not isinstance(workspaces, list):
        return None
    for item in workspaces:
        if isinstance(item, dict) and bool(item.get("focused", False)):
            rect = item.get("rect", {})
            return rect if isinstance(rect, dict) else None
    return None


def focused_workspace_name() -> str:
    raw = run_cmd(["i3-msg", "-t", "get_workspaces"], timeout=2.0)
    if not raw:
        return ""
    try:
        workspaces = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(workspaces, list):
        return ""
    for item in workspaces:
        if isinstance(item, dict) and bool(item.get("focused", False)):
            return str(item.get("name", "")).strip()
    return ""
    bar = payload.get("bar", {})
    if not isinstance(bar, dict):
        return BAR_HEIGHT
    try:
        return max(32, min(72, int(bar.get("bar_height", BAR_HEIGHT))))
    except Exception:
        return BAR_HEIGHT


def _collect_leaf_windows(node: dict, visible_windows: list[dict]) -> None:
    if not isinstance(node, dict):
        return
    nodes = node.get("nodes", [])
    floating_nodes = node.get("floating_nodes", [])
    if isinstance(nodes, list):
        for child in nodes:
            _collect_leaf_windows(child, visible_windows)
    if isinstance(floating_nodes, list):
        for child in floating_nodes:
            _collect_leaf_windows(child, visible_windows)
    window = node.get("window")
    if not window:
        return
    visible_windows.append(node)


def focused_workspace_has_real_windows() -> bool:
    workspace_raw = run_cmd(["i3-msg", "-t", "get_workspaces"], timeout=2.0)
    tree_raw = run_cmd(["i3-msg", "-t", "get_tree"], timeout=3.0)
    if not workspace_raw or not tree_raw:
        return False
    try:
        workspaces = json.loads(workspace_raw)
        tree = json.loads(tree_raw)
    except Exception:
        return False
    if not isinstance(workspaces, list):
        return False
    focused_workspace_name = ""
    for item in workspaces:
        if isinstance(item, dict) and bool(item.get("focused", False)):
            focused_workspace_name = str(item.get("name", "")).strip()
            break
    if not focused_workspace_name:
        return False

    def find_workspace(node: dict) -> dict | None:
        if not isinstance(node, dict):
            return None
        if node.get("type") == "workspace" and str(node.get("name", "")).strip() == focused_workspace_name:
            return node
        for key in ("nodes", "floating_nodes"):
            children = node.get(key, [])
            if not isinstance(children, list):
                continue
            for child in children:
                found = find_workspace(child)
                if found is not None:
                    return found
        return None

    workspace = find_workspace(tree)
    if workspace is None:
        return False
    windows: list[dict] = []
    _collect_leaf_windows(workspace, windows)
    ignored_classes = {
        "CyberBar",
        "CyberDock",
        "HanautaDesktopClock",
        "HanautaHotkeys",
    }
    ignored_titles = {
        "CyberBar",
        "Hanauta Desktop Clock",
    }
    for item in windows:
        props = item.get("window_properties", {})
        if not isinstance(props, dict):
            props = {}
        wm_class = str(props.get("class", "")).strip()
        title = str(item.get("name", "")).strip()
        if wm_class in ignored_classes or title in ignored_titles:
            continue
        return True
    return False


class DesktopClockWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.settings_state = load_settings_state()
        self.drag_offset = QPoint()
        self.dragging = False
        self._drag_moved = False
        self._suspend_position_persist = False
        self.preview_mode = bool(sys.stdin.isatty() or sys.stdout.isatty())
        self._desktop_visible = True
        self._last_workspace_name = ""

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnBottomHint
        )
        self.setWindowTitle("Hanauta Desktop Clock")

        self._apply_size()
        self._place_window()
        self._update_window_mask()

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.update)
        self.tick_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self.workspace_timer = QTimer(self)
        self.workspace_timer.timeout.connect(self._sync_workspace_visibility)
        self.workspace_timer.start(1200)

    def _apply_size(self) -> None:
        size = max(220, min(520, int(self.settings_state.get("clock", {}).get("size", 320) or 320)))
        self.setFixedSize(size, size)

    def _place_window(self) -> None:
        workspace_rect = focused_workspace_rect()
        clock_settings = self.settings_state.get("clock", {})
        pos_x = int(clock_settings.get("position_x", -1) or -1)
        pos_y = int(clock_settings.get("position_y", -1) or -1)
        self._suspend_position_persist = True
        if pos_x >= 0 and pos_y >= 0:
            self.move(pos_x, pos_y)
            self._suspend_position_persist = False
            return
        if workspace_rect is not None:
            area_x = int(workspace_rect.get("x", 0))
            area_y = int(workspace_rect.get("y", 0))
            area_width = int(workspace_rect.get("width", self.width()))
        else:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                self._suspend_position_persist = False
                return
            available = screen.availableGeometry()
            area_x = available.x()
            area_y = available.y()
            area_width = available.width()
        bar_height = load_bar_height()
        self.move(
            area_x + (area_width - self.width()) // 2,
            area_y + bar_height + 24,
        )
        self._suspend_position_persist = False

    def _persist_current_position(self) -> None:
        if self._suspend_position_persist:
            return
        save_clock_position(self.x(), self.y())

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime != self._theme_mtime:
            self._theme_mtime = current_mtime
            self.theme = load_theme_palette()
        current_settings = load_settings_state()
        if current_settings.get("clock", {}) != self.settings_state.get("clock", {}):
            self.settings_state = current_settings
            self._apply_size()
            self._place_window()
            self._update_window_mask()
        else:
            self.settings_state = current_settings
        clock_settings = self.settings_state.get("clock", {})
        if int(clock_settings.get("position_x", -1) or -1) < 0 or int(clock_settings.get("position_y", -1) or -1) < 0:
            self._place_window()
        self._sync_workspace_visibility()
        self.update()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._set_window_class()
        QTimer.singleShot(150, self._apply_i3_window_rules)
        QTimer.singleShot(200, self._sync_workspace_visibility)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_window_mask()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self._drag_moved = False
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self._drag_moved = True
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self.dragging and event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            if self._drag_moved:
                self._persist_current_position()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def moveEvent(self, event) -> None:  # type: ignore[override]
        super().moveEvent(event)
        if self.dragging and self._drag_moved:
            self._persist_current_position()

    def _format_hour(self, moment: datetime) -> str:
        if bool(self.settings_state.get("region", {}).get("use_24_hour", False)):
            return moment.strftime("%H")
        return moment.strftime("%I")

    def _face_path(self) -> tuple[QPainterPath, QPointF, float, float]:
        rect = self.rect().adjusted(10, 10, -10, -10)
        center = QPointF(rect.center())
        outer_radius = min(rect.width(), rect.height()) / 2.0 - 6.0
        inner_radius = outer_radius * 0.90
        face_path = QPainterPath()
        scallops = 18
        for index in range(scallops * 6 + 1):
            angle = (math.tau * index) / (scallops * 6)
            pulse = math.sin(angle * scallops)
            radius = outer_radius + pulse * (outer_radius * 0.045)
            point = QPointF(
                center.x() + math.cos(angle - math.pi / 2) * radius,
                center.y() + math.sin(angle - math.pi / 2) * radius,
            )
            if index == 0:
                face_path.moveTo(point)
            else:
                face_path.lineTo(point)
        face_path.closeSubpath()
        return face_path, center, outer_radius, inner_radius

    def _update_window_mask(self) -> None:
        face_path, _, _, _ = self._face_path()
        polygon = QPolygonF(face_path.toFillPolygon())
        self.setMask(QRegion(polygon.toPolygon()))

    def _set_window_class(self) -> None:
        try:
            wid = int(self.winId())
            subprocess.run(
                ["xprop", "-id", hex(wid), "-f", "_NET_WM_NAME", "8t", "-set", "_NET_WM_NAME", "Hanauta Desktop Clock"],
                check=False,
            )
            subprocess.run(
                ["xprop", "-id", hex(wid), "-f", "WM_CLASS", "8s", "-set", "WM_CLASS", "HanautaDesktopClock"],
                check=False,
            )
        except Exception:
            pass

    def _apply_i3_window_rules(self) -> None:
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="Hanauta Desktop Clock"]',
                    "floating enable, border pixel 0",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def _sync_workspace_visibility(self) -> None:
        if self.preview_mode:
            if not self.isVisible():
                self.show()
            return
        current_workspace = focused_workspace_name()
        if current_workspace and current_workspace != self._last_workspace_name:
            self._last_workspace_name = current_workspace
            self._move_to_current_workspace()
        services = self.settings_state.get("services", {})
        if isinstance(services, dict):
            service = services.get("desktop_clock_widget", {})
            if isinstance(service, dict) and not bool(service.get("enabled", True)):
                self._shutdown()
                return
        if focused_workspace_has_real_windows():
            self._shutdown()
            return
        if not self.isVisible():
            self.show()

    def _shutdown(self) -> None:
        app = QApplication.instance()
        self.close()
        if app is not None:
            app.quit()

    def _move_to_current_workspace(self) -> None:
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="Hanauta Desktop Clock"]',
                    "move container to workspace current",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        face_path, center, outer_radius, inner_radius = self._face_path()
        if self.theme.use_matugen:
            face_fill = QColor(self.theme.secondary)
            face_fill.setAlphaF(0.92)
            dial_color = QColor(self.theme.on_secondary)
            dial_color.setAlphaF(0.42)
            digital_color = QColor(self.theme.on_secondary)
            digital_color.setAlphaF(0.28)
            hour_hand_color = QColor(self.theme.on_secondary)
            hour_hand_color.setAlphaF(0.70)
            minute_hand_color = QColor(self.theme.primary)
            minute_hand_color.setAlphaF(0.96)
            second_hand_color = QColor(self.theme.error)
            second_hand_color.setAlphaF(0.82)
            center_outer = QColor(self.theme.primary)
            center_outer.setAlphaF(0.95)
            center_inner = QColor(self.theme.primary_container)
            center_inner.setAlphaF(0.96)
        else:
            face_fill = QColor("#415050")
            face_fill.setAlphaF(0.96)
            dial_color = QColor("#EEF6F4")
            dial_color.setAlphaF(0.62)
            digital_color = QColor("#D6DFDC")
            digital_color.setAlphaF(0.32)
            hour_hand_color = QColor("#C8D0CF")
            hour_hand_color.setAlphaF(0.78)
            minute_hand_color = QColor("#DFF7F2")
            minute_hand_color.setAlphaF(0.98)
            second_hand_color = QColor("#E8A4A0")
            second_hand_color.setAlphaF(0.94)
            center_outer = QColor("#BFE5E0")
            center_outer.setAlphaF(0.98)
            center_inner = QColor("#F3FCFA")
            center_inner.setAlphaF(0.98)

        painter.fillPath(face_path, face_fill)

        tick_pen = QPen(dial_color, max(2.0, outer_radius * 0.012))
        tick_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(tick_pen)
        for index in range(60):
            angle = (math.tau * index) / 60.0 - math.pi / 2
            is_major = index % 5 == 0
            tick_length = inner_radius * (0.105 if is_major else 0.055)
            outer = inner_radius * 0.92
            inner = outer - tick_length
            start = QPointF(center.x() + math.cos(angle) * inner, center.y() + math.sin(angle) * inner)
            end = QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer)
            painter.drawLine(start, end)

        now = datetime.now()
        hour_text = self._format_hour(now)
        minute_text = now.strftime("%M")
        painter.setPen(digital_color)
        # Tweak the multiplier below if the stacked hour/minute text still feels too tight.
        digital_font = QFont(self.display_font, max(38, int(outer_radius * 0.40)), QFont.Weight.Bold)
        painter.setFont(digital_font)
        metrics = QFontMetrics(digital_font)
        digital_rect = QRectF(
            center.x() - inner_radius * 0.52,
            center.y() - inner_radius * 0.36,
            inner_radius * 1.04,
            inner_radius * 0.72,
        )
        line_height = float(metrics.height())
        # This directly controls the visible distance between the hour and minute.
        # Lower it to bring them closer together, raise it to push them farther apart.
        line_offset = max(33.0, outer_radius * 0.14)
        hour_center_y = center.y() - line_offset
        minute_center_y = center.y() + line_offset
        hour_rect = QRectF(digital_rect.x(), hour_center_y - (line_height / 2.0), digital_rect.width(), line_height)
        minute_rect = QRectF(digital_rect.x(), minute_center_y - (line_height / 2.0), digital_rect.width(), line_height)
        painter.drawText(hour_rect, int(Qt.AlignmentFlag.AlignCenter), hour_text)
        painter.drawText(minute_rect, int(Qt.AlignmentFlag.AlignCenter), minute_text)

        hour_angle = ((now.hour % 12) + now.minute / 60.0) * (math.tau / 12.0) - math.pi / 2
        minute_angle = (now.minute + now.second / 60.0) * (math.tau / 60.0) - math.pi / 2
        second_angle = now.second * (math.tau / 60.0) - math.pi / 2

        painter.setPen(QPen(hour_hand_color, max(10.0, outer_radius * 0.072), cap=Qt.PenCapStyle.RoundCap))
        painter.drawLine(center, QPointF(center.x() + math.cos(hour_angle) * inner_radius * 0.42, center.y() + math.sin(hour_angle) * inner_radius * 0.42))

        painter.setPen(QPen(minute_hand_color, max(8.0, outer_radius * 0.052), cap=Qt.PenCapStyle.RoundCap))
        painter.drawLine(center, QPointF(center.x() + math.cos(minute_angle) * inner_radius * 0.62, center.y() + math.sin(minute_angle) * inner_radius * 0.62))

        if bool(self.settings_state.get("clock", {}).get("show_seconds", True)):
            painter.setPen(QPen(second_hand_color, max(3.0, outer_radius * 0.018), cap=Qt.PenCapStyle.RoundCap))
            painter.drawLine(center, QPointF(center.x() + math.cos(second_angle) * inner_radius * 0.70, center.y() + math.sin(second_angle) * inner_radius * 0.70))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(center_outer)
        painter.drawEllipse(center, max(8.0, outer_radius * 0.05), max(8.0, outer_radius * 0.05))
        painter.setBrush(center_inner)
        painter.drawEllipse(center, max(3.0, outer_radius * 0.018), max(3.0, outer_radius * 0.018))


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    widget = DesktopClockWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
