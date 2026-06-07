from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from app_locale import t
from notif_center.paths import (
    AIRPLANE_NOTIFICATION_ICON,
    BLUETOOTH_NOTIFICATION_ICON,
    CAFFEINE_NOTIFICATION_ICON,
    NIGHT_LIGHT_NOTIFICATION_ICON,
    SCRIPTS_DIR,
    STATE_DIR,
    WIFI_NOTIFICATION_ICON,
)
from notif_center.poller import PollResult
from notif_center.utils import (
    material_icon,
    notification_control_command,
    parse_bool_text,
    run_bg,
    run_cmd,
    run_script_bg,
)
from notif_center.widgets import QuickSettingButton
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba


class QuickActionsPanel(QFrame):
    """Standalone quick actions panel with wifi, bluetooth, dnd, airplane,
    night light, caffeine toggles plus brightness/volume sliders."""

    def __init__(
        self,
        material_font: str,
        ui_font: str,
        is_light_checker: Callable[[object], bool],
        theme_palette: object,
        compact: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.material_font = material_font
        self.ui_font = ui_font
        self._is_light_theme = is_light_checker
        self.theme_palette = theme_palette
        self.compact = compact
        self._syncing_sliders = False
        self.quick_buttons: dict[str, QuickSettingButton] = {}
        self.brightness_slider: dict = {}
        self.volume_slider: dict = {}

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._build_toggles_grid())
        layout.addWidget(self._build_sliders_row())

    def _build_toggles_grid(self) -> QFrame:
        card = QFrame()
        grid = QGridLayout(card)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        self.quick_buttons = {
            "wifi": QuickSettingButton(
                self.material_font, t("quick.wifi"), "wifi", self._toggle_wifi
            ),
            "bluetooth": QuickSettingButton(
                self.material_font, t("quick.bluetooth"), "bluetooth", self._toggle_bluetooth
            ),
            "dnd": QuickSettingButton(
                self.material_font, t("quick.dnd"), "do_not_disturb_on", self._toggle_dnd
            ),
            "airplane": QuickSettingButton(
                self.material_font,
                t("quick.airplane"),
                "airplanemode_active",
                self._toggle_airplane,
            ),
            "night": QuickSettingButton(
                self.material_font, t("quick.night_light"), "nightlight", self._toggle_night
            ),
            "caffeine": QuickSettingButton(
                self.material_font, t("quick.caffeine"), "coffee", self._toggle_caffeine
            ),
        }
        positions = [
            ("wifi", 0, 0), ("bluetooth", 0, 1), ("dnd", 0, 2),
            ("airplane", 1, 0), ("night", 1, 1), ("caffeine", 1, 2),
        ]
        for key, row, col in positions:
            button = self.quick_buttons[key]
            button.setMinimumHeight(62)
            grid.addWidget(button, row, col)
        return card

    def _build_sliders_row(self) -> QFrame:
        card = QFrame()
        row = QHBoxLayout(card)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.brightness_slider = self._make_slider("brightness_medium", "brightness")
        self.volume_slider = self._make_slider("volume_up", "volume")

        row.addWidget(self.brightness_slider["wrap"], 1)
        row.addWidget(self.volume_slider["wrap"], 1)
        return card

    def _make_slider(self, icon: str, kind: str) -> dict:
        wrap = QFrame()
        wrap.setObjectName("compactSliderWrap")
        row_layout = QHBoxLayout(wrap)
        row_layout.setContentsMargins(10, 0, 10, 0)
        row_layout.setSpacing(6)

        icon_label = QLabel(material_icon(icon))
        icon_label.setObjectName("sliderIcon")
        icon_label.setFont(QFont(self.material_font, 16))
        icon_label.setFixedWidth(22)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setObjectName("compactSlider")
        slider.valueChanged.connect(
            lambda value, k=kind: self._commit_slider(k, value)
        )

        row_layout.addWidget(icon_label)
        row_layout.addWidget(slider, 1)
        return {"wrap": wrap, "slider": slider}

    def _commit_slider(self, kind: str, value: int) -> None:
        if self._syncing_sliders:
            return
        if kind == "brightness":
            run_script_bg("brightness.sh", "set", str(value))
        elif kind == "volume":
            run_script_bg("volume.sh", "set", str(value))

    def update_states(self, result: PollResult | None) -> None:
        if result is None:
            return
        r = result
        self.quick_buttons["wifi"].set_state(r.wifi_on, "wifi", r.wifi_ssid)
        self.quick_buttons["bluetooth"].set_state(
            r.bt_on, "bluetooth", t("status.connected") if r.bt_on else t("status.off")
        )
        self.quick_buttons["dnd"].set_state(
            r.dnd_on, "do_not_disturb_on", t("status.on") if r.dnd_on else t("status.off")
        )
        self.quick_buttons["airplane"].set_state(
            r.airplane_on, "airplanemode_active", t("status.on") if r.airplane_on else t("status.off")
        )
        self.quick_buttons["night"].set_state(
            r.night_on, "nightlight", t("status.on") if r.night_on else t("status.off")
        )
        self.quick_buttons["caffeine"].set_state(
            r.caffeine_on, "coffee", t("status.on") if r.caffeine_on else t("status.off")
        )

        self._syncing_sliders = True
        self.brightness_slider["slider"].setValue(r.brightness)
        self.volume_slider["slider"].setValue(r.volume)
        self._syncing_sliders = False

    def _toggle_wifi(self) -> None:
        run_script_bg("network.sh", "toggle")
        self._delayed_notify(
            "wifi", t("quick.wifi"),
            t("notify.wifi.connected"), t("notify.wifi.disconnected"),
            WIFI_NOTIFICATION_ICON if Path(WIFI_NOTIFICATION_ICON).exists() else "network-wireless",
        )

    def _toggle_bluetooth(self) -> None:
        run_script_bg("bluetooth", "toggle")
        self._delayed_notify(
            "bluetooth", t("quick.bluetooth"),
            t("notify.bt.enabled"), t("notify.bt.disabled"),
            BLUETOOTH_NOTIFICATION_ICON if Path(BLUETOOTH_NOTIFICATION_ICON).exists() else "bluetooth",
        )

    def _toggle_airplane(self) -> None:
        run_script_bg("network.sh", "toggle-radio")
        self._delayed_notify(
            "airplane", t("notify.airplane_mode"),
            t("notify.airplane.enabled"), t("notify.airplane.disabled"),
            AIRPLANE_NOTIFICATION_ICON if Path(AIRPLANE_NOTIFICATION_ICON).exists() else "airplane-mode-symbolic",
        )

    def _toggle_night(self) -> None:
        button = self.quick_buttons.get("night")
        if button is not None:
            new_state = not button.active
            button.set_state(new_state, "nightlight", t("status.on") if new_state else t("status.off"))
        run_script_bg("redshift", "toggle")
        self._delayed_notify(
            "night", t("quick.night_light"),
            t("notify.night.enabled"), t("notify.night.disabled"),
            self._night_light_notification_icon(),
        )

    def _toggle_caffeine(self) -> None:
        caffeine_script = SCRIPTS_DIR / "caffeine.sh"
        if caffeine_script.exists():
            run_bg(["env", "HANAUTA_QUIET=1", str(caffeine_script), "toggle"])
        self._delayed_notify(
            "caffeine", t("quick.caffeine"),
            t("notify.caffeine.enabled"), t("notify.caffeine.disabled"),
            CAFFEINE_NOTIFICATION_ICON if Path(CAFFEINE_NOTIFICATION_ICON).exists() else "coffee",
        )

    def _toggle_dnd(self) -> None:
        dnd_on = parse_bool_text(run_cmd(notification_control_command("is-paused")))
        if dnd_on:
            run_cmd(notification_control_command("set-paused", "false"))
            run_bg(["notify-send", t("notify.dnd.enabled_summary"), t("notify.dnd.enabled_body")])
            return
        run_bg(["notify-send", t("notify.dnd.disabling_summary"), t("notify.dnd.disabling_body")])
        QTimer.singleShot(350, self._enable_dnd)

    def _enable_dnd(self) -> None:
        run_cmd(notification_control_command("set-paused", "true"))
        run_bg(["notify-send", t("notify.dnd.enabled_summary"), t("notify.dnd.enabled_body")])

    def _delayed_notify(self, key: str, title: str, enabled_msg: str, disabled_msg: str, icon: str) -> None:
        QTimer.singleShot(300, lambda: self._notify(key, title, enabled_msg, disabled_msg, icon))

    def _notify(self, key: str, title: str, enabled_msg: str, disabled_msg: str, icon: str) -> None:
        button = self.quick_buttons.get(key)
        if button is None:
            return
        body = enabled_msg if button.active else disabled_msg
        run_bg([
            "gdbus", "call", "--session",
            "--dest", "org.freedesktop.Notifications",
            "--object-path", "/org/freedesktop/Notifications",
            "--method", "org.freedesktop.Notifications.Notify",
            t("notify.app_name"), "0", icon, title, body, "[]", "{}", "3000",
        ])

    def _night_light_notification_icon(self) -> str:
        try:
            current_mtime = palette_mtime()
        except Exception:
            current_mtime = None
        if current_mtime is not None and current_mtime != getattr(self, "_theme_mtime", None):
            try:
                self._theme_mtime = current_mtime
                self.theme_palette = load_theme_palette()
            except Exception:
                pass

        is_light = self._is_light_theme(self.theme_palette)
        color = QColor("#000000") if is_light else QColor("#ffffff")
        suffix = "dark" if is_light else "light"
        target = STATE_DIR / f"notify-nightlight-{suffix}.png"
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setPen(color)
            painter.setFont(QFont(self.material_font, 44))
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, material_icon("nightlight"))
            painter.end()
            pixmap.save(str(target), "PNG")
            if target.exists():
                return target.resolve().as_uri()
        except Exception:
            pass
        return "nightlight"
