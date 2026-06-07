from __future__ import annotations

from PyQt6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTextCharFormat, QPalette
from PyQt6.QtWidgets import QApplication, QButtonGroup, QDialog, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget, QVBoxLayout, QWidget

from app_locale import t
from notif_center.ha import *
from notif_center.game_carousel import *
from notif_center.paths import *
from notif_center.poller import *
from notif_center.settings_io import *
from notif_center.utils import *
from notif_center.widgets import *
from pyqt.shared.calendar_card import *
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family
from pyqt.shared.runtime import entry_command, entry_patterns, python_executable


class HomeAssistantMixin:
    """Home Assistant entities methods for NotificationCenter."""

    def _build_home_assistant_card(self) -> QFrame:
        self.ha_card = QFrame()
        self.ha_card.setObjectName("infoCard")
        layout = QHBoxLayout(self.ha_card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        icon = QLabel()
        icon.setObjectName("sectionIcon")
        icon.setFixedWidth(20)
        icon.setPixmap(
            tinted_svg_pixmap(
                HOME_ASSISTANT_ICON, QColor(self.current_accent["accent"]), 18
            )
        )
        self.ha_summary_label = QLabel("")
        self.ha_summary_label.setObjectName("statusHint")
        self.ha_open_settings_btn = CompactIconAction(self.material_font, "settings")
        self.ha_open_settings_btn.clicked.connect(self._open_settings_homeassistant)

        tile_row = QHBoxLayout()
        tile_row.setContentsMargins(0, 0, 0, 0)
        tile_row.setSpacing(4)
        self.ha_action_tiles: list[ActionTile] = []
        for index in range(5):
            tile = ActionTile(
                self.material_font,
                f"Slot {index + 1}",
                "hub",
                lambda checked=False, i=index: self._activate_ha_tile(i),
            )
            tile.setMinimumSize(58, 64)
            tile.setMaximumSize(58, 64)
            self.ha_action_tiles.append(tile)
            tile_row.addWidget(tile)

        self.ha_status_label = QLabel(t("ha.no_entities"))
        self.ha_status_label.setObjectName("statusHint")
        self.ha_status_label.hide()
        layout.addWidget(icon)
        layout.addLayout(tile_row, 1)
        layout.addWidget(self.ha_open_settings_btn)
        return self.ha_card


    def _save_home_assistant_settings(self) -> None:
        if self.ha_url_input is None or self.ha_token_input is None:
            self._launch_settings_page("services")
            return
        self.settings_state["home_assistant"]["url"] = normalize_ha_url(
            self.ha_url_input.text()
        )
        self.settings_state["home_assistant"]["token"] = (
            self.ha_token_input.text().strip()
        )
        save_notification_settings(self.settings_state)
        if self.ha_settings_status is not None:
            self.ha_settings_status.setText(t("settings.ha.saved"))
        self._refresh_home_assistant_entities()


    def _refresh_home_assistant_entities(self) -> None:
        if not self._service_visible_in_notification_center("home_assistant"):
            self._ha_entities = []
            self._ha_entity_map = {}
            self._render_home_assistant_tiles()
            return
        base_url = normalize_ha_url(
            self.settings_state["home_assistant"].get("url", "")
        )
        token = self.settings_state["home_assistant"].get("token", "")
        payload, error_text = fetch_home_assistant_json(base_url, token, "/api/states")
        self._ha_last_error = error_text
        if error_text or not isinstance(payload, list):
            if self.ha_summary_label is not None:
                self.ha_summary_label.setText("")
            if self.ha_status_label is not None:
                self.ha_status_label.setText(error_text or "No entities available.")
            if self.ha_settings_status is not None:
                self.ha_settings_status.setText(
                    error_text or t("settings.ha.failed")
                )
            self._ha_entities = []
            self._ha_entity_map = {}
            self._rebuild_ha_entity_list()
            self._render_home_assistant_tiles()
            return
        self._ha_entities = sorted(
            [item for item in payload if isinstance(item, dict)],
            key=lambda item: str(item.get("entity_id", "")),
        )
        self._ha_entity_map = {
            str(item.get("entity_id", "")): item for item in self._ha_entities
        }
        if self.ha_summary_label is not None:
            self.ha_summary_label.setText("")
        if self.ha_status_label is not None:
            self.ha_status_label.setText("Pinned entity controls are live.")
        if self.ha_settings_status is not None:
            self.ha_settings_status.setText("Entities loaded successfully.")
        self._rebuild_ha_entity_list()
        self._render_home_assistant_tiles()


    def _rebuild_ha_entity_list(self) -> None:
        if not hasattr(self, "ha_entity_layout"):
            return
        while self.ha_entity_layout.count():
            item = self.ha_entity_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        pinned = set(self.settings_state["home_assistant"].get("pinned_entities", []))
        if not self._ha_entities:
            empty = QLabel(t("settings.ha.empty"))
            empty.setObjectName("statusHint")
            self.ha_entity_layout.addWidget(empty)
            self.ha_entity_layout.addStretch(1)
            return
        for entity in self._ha_entities[:80]:
            entity_id = str(entity.get("entity_id", ""))
            state = str(entity.get("state", "unknown"))
            attrs = entity.get("attributes", {}) or {}
            name = str(attrs.get("friendly_name", entity_id))
            row = QFrame()
            row.setObjectName("metricCard")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(2)
            title = QLabel(name)
            title.setObjectName("metricValue")
            subtitle = QLabel(f"{entity_id} • {state}")
            subtitle.setObjectName("statusHint")
            text.addWidget(title)
            text.addWidget(subtitle)
            layout.addLayout(text, 1)
            pin_button = self._soft_button(t("settings.ha.btn_unpin") if entity_id in pinned else t("settings.ha.btn_pin"))
            pin_button.clicked.connect(
                lambda checked=False, current=entity_id: self._toggle_pin_entity(
                    current
                )
            )
            layout.addWidget(pin_button)
            self.ha_entity_layout.addWidget(row)
        self.ha_entity_layout.addStretch(1)


    def _toggle_pin_entity(self, entity_id: str) -> None:
        pinned = list(self.settings_state["home_assistant"].get("pinned_entities", []))
        if entity_id in pinned:
            pinned.remove(entity_id)
        else:
            if len(pinned) >= 5:
                self.ha_settings_status.setText("You can pin up to five entities.")
                return
            pinned.append(entity_id)
        self.settings_state["home_assistant"]["pinned_entities"] = pinned
        save_notification_settings(self.settings_state)
        self.ha_settings_status.setText(f"{len(pinned)}/5 entities pinned.")
        self._rebuild_ha_entity_list()
        self._render_home_assistant_tiles()


    def _render_home_assistant_tiles(self) -> None:
        self._sync_service_card_visibility()
        if not self._service_visible_in_notification_center("home_assistant"):
            return
        pinned = self.settings_state["home_assistant"].get("pinned_entities", [])
        for index, tile in enumerate(self.ha_action_tiles):
            if index >= len(pinned):
                tile.set_content("hub", "", "")
                tile.setProperty("entity_id", "")
                tile.setEnabled(False)
                continue
            entity_id = pinned[index]
            entity = self._ha_entity_map.get(entity_id, {})
            attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
            name = str(attrs.get("friendly_name", entity_id))
            state = (
                str(entity.get("state", "Unavailable"))
                if isinstance(entity, dict)
                else "Unavailable"
            )
            domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
            icon_name = {
                "light": "lightbulb",
                "switch": "tune",
                "climate": "thermostat",
                "camera": "camera_alt",
            }.get(domain, "home")
            tile.set_content(icon_name, name[:12], state[:12])
            tile.setEnabled(True)
            tile.setProperty("entity_id", entity_id)
        self.ha_card.setVisible(True)


    def _activate_ha_tile(self, index: int) -> None:
        pinned = self.settings_state["home_assistant"].get("pinned_entities", [])
        if index >= len(pinned):
            self._open_settings_homeassistant()
            return
        entity_id = pinned[index]
        entity = self._ha_entity_map.get(entity_id)
        if not entity:
            self.ha_status_label.setText("Entity state is not loaded yet.")
            return
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        state = str(entity.get("state", ""))
        service_domain = domain
        service = ""
        payload = {"entity_id": entity_id}
        if domain in {"light", "switch", "input_boolean"}:
            service = "turn_off" if state == "on" else "turn_on"
        elif domain == "scene":
            service = "turn_on"
            service_domain = "scene"
        elif domain == "script":
            service = "turn_on"
            service_domain = "script"
        else:
            self.ha_status_label.setText(f"{entity_id} is view-only right now.")
            return
        _, error_text = post_home_assistant_json(
            self.settings_state["home_assistant"].get("url", ""),
            self.settings_state["home_assistant"].get("token", ""),
            f"/api/services/{service_domain}/{service}",
            payload,
        )
        self.ha_status_label.setText(
            error_text or f"Triggered {service} for {entity_id}."
        )
        QTimer.singleShot(900, self._refresh_home_assistant_entities)


