from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QWidget

from app_locale import t
from notif_center.poller import PollResult
from notif_center.quick_actions import QuickActionsPanel


class QuickSettingsMixin:
    """Delegates quick settings UI and actions to QuickActionsPanel."""

    quick_actions_panel: QuickActionsPanel

    def _build_quick_settings_card(self) -> QFrame:
        card, layout = self._section_shell(t("section.connectivity"), "")
        self.quick_actions_panel = QuickActionsPanel(
            material_font=self.material_font,
            ui_font=self.ui_font,
            is_light_checker=self._is_light_theme,
            theme_palette=self.theme_palette,
            compact=True,
            parent=card,
        )
        layout.addWidget(self.quick_actions_panel)
        self.quick_buttons = self.quick_actions_panel.quick_buttons
        self.brightness_slider = self.quick_actions_panel.brightness_slider
        self.volume_slider = self.quick_actions_panel.volume_slider
        return card

    def _build_compact_sliders_card(self) -> QFrame:
        card = QFrame()
        return card

    def _build_quick_settings(self) -> None:
        pass

    def _build_sliders(self) -> None:
        pass

    def _slider_row(self, *args, **kwargs) -> None:
        pass

    def _poll_quick_settings(self) -> None:
        r: PollResult | None = getattr(self, "_poll_result", None)
        if r is not None and hasattr(self, "quick_actions_panel"):
            self.quick_actions_panel.update_states(r)

    def _poll_sliders(self) -> None:
        pass

    def _toggle_wifi(self) -> None:
        pass

    def _toggle_bluetooth(self) -> None:
        pass

    def _toggle_airplane(self) -> None:
        pass

    def _toggle_night(self) -> None:
        pass

    def _toggle_caffeine(self) -> None:
        pass

    def _toggle_dnd(self) -> None:
        pass

    def _refresh_quick_settings_and_notify(self, *args, **kwargs) -> None:
        pass

    def _show_system_notification(self, *args, **kwargs) -> None:
        pass

    def _night_light_notification_icon(self) -> str:
        return "nightlight"
