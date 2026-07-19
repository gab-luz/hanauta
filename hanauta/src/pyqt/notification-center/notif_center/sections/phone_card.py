from __future__ import annotations

import json

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from app_locale import t
from notif_center.paths import KDECONNECT_ICON
from notif_center.utils import render_svg_pixmap, run_script_bg
from notif_center.widgets import CompactIconAction


class PhoneCardMixin:

    def build_phone_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("infoCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        icon = QLabel()
        icon.setObjectName("sectionIcon")
        icon.setFixedWidth(20)
        icon.setPixmap(render_svg_pixmap(KDECONNECT_ICON, 18))
        self.phone_status_dot = QLabel("●")
        self.phone_status_dot.setObjectName("phoneStatusDot")
        self.phone_switch_btn = CompactIconAction(self.material_font, "chevron_right")
        self.phone_switch_btn.clicked.connect(
            lambda: run_script_bg("phone_info.sh", "--next")
        )
        self.phone_clipboard_btn = CompactIconAction(
            self.material_font, "content_paste"
        )
        self.phone_clipboard_btn.clicked.connect(
            lambda: run_script_bg("phone_info.sh", "--toggle-clip")
        )
        self.phone_name_value = QLabel(t("phone.disconnected"))
        self.phone_state_value = QLabel(t("phone.offline"))
        self.phone_battery_value = QLabel("0%")
        for label in (
            self.phone_name_value,
            self.phone_state_value,
            self.phone_battery_value,
        ):
            label.setObjectName("metricValue")
        self.phone_name_value.setObjectName("inlineMetricPrimary")
        self.phone_state_value.setObjectName("inlineMetric")
        self.phone_battery_value.setObjectName("inlineMetric")
        self.phone_name_value.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        layout.addWidget(icon)
        layout.addWidget(self.phone_name_value, 1)
        layout.addWidget(self.phone_state_value)
        layout.addWidget(self.phone_battery_value)
        layout.addWidget(self.phone_status_dot)
        layout.addWidget(self.phone_clipboard_btn)
        layout.addWidget(self.phone_switch_btn)
        return card

    def poll_phone(self) -> None:
        r = self._poll_result
        raw = r.phone_raw if r else ""
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}
        name = str(payload.get("name", t("phone.disconnected")))
        battery = str(payload.get("battery", "0"))
        status = str(payload.get("status", t("phone.offline")))
        clipboard = str(payload.get("clipboard", "off"))
        has_device = bool(payload.get("id")) and bool(payload.get("name"))
        if has_device:
            self.phone_name_value.setText(name)
            self.phone_state_value.setText(status)
            self.phone_battery_value.setText(f"{battery}%")
        else:
            self.phone_name_value.setText(t("phone.no_devices"))
            self.phone_state_value.setText("")
            self.phone_battery_value.setText("")
        self.phone_status_dot.setStyleSheet(
            f"color: {self.theme_palette.primary if has_device and status.lower() != 'offline' else self.theme_palette.workspace_empty};"
        )
        self.phone_clipboard_btn.set_active(has_device and clipboard == "on")
        self.phone_clipboard_btn.setEnabled(has_device)
        self.phone_switch_btn.setEnabled(has_device)
