from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from settings_page.material_icons import material_icon
from settings_page.ui_widgets import SettingsRow, SwitchButton
from settings_page.widgets import IconLabel


def build_audio_page(window) -> QWidget:
    return window._scroll_page(build_audio_card(window))


def build_audio_card(window) -> QWidget:
    card = QFrame()
    card.setObjectName("contentCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    icon = IconLabel(material_icon("music_note"), window.icon_font, 15, "#F4EAF7")
    icon.setFixedSize(22, 22)
    title = QLabel("Audio")
    title.setFont(QFont(window.display_font, 13))
    title.setStyleSheet("color: rgba(246,235,247,0.72);")
    subtitle = QLabel(
        "Default output, mic input, alert sounds, and how Hanauta should behave when audio focus changes."
    )
    subtitle.setFont(QFont(window.ui_font, 9))
    subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
    title_wrap = QVBoxLayout()
    title_wrap.setContentsMargins(0, 0, 0, 0)
    title_wrap.setSpacing(2)
    title_wrap.addWidget(title)
    title_wrap.addWidget(subtitle)
    header.addWidget(icon)
    header.addLayout(title_wrap)
    header.addStretch(1)
    layout.addLayout(header)

    window.audio_sink_combo = QComboBox()
    window.audio_sink_combo.setObjectName("settingsCombo")
    layout.addWidget(
        SettingsRow(
            material_icon("music_note"),
            "Default sink",
            "Choose the default playback device for new apps.",
            window.icon_font,
            window.ui_font,
            window.audio_sink_combo,
        )
    )

    window.audio_source_combo = QComboBox()
    window.audio_source_combo.setObjectName("settingsCombo")
    layout.addWidget(
        SettingsRow(
            material_icon("monitor_heart"),
            "Microphone source",
            "Choose the default capture device for voice apps and recordings.",
            window.icon_font,
            window.ui_font,
            window.audio_source_combo,
        )
    )

    window.audio_alert_sounds_switch = SwitchButton(
        bool(window.settings_state["audio"].get("alert_sounds_enabled", True))
    )
    layout.addWidget(
        SettingsRow(
            material_icon("notifications"),
            "Alert sounds",
            "Allow notification and reminder sounds when supported by the widget or daemon.",
            window.icon_font,
            window.ui_font,
            window.audio_alert_sounds_switch,
        )
    )

    window.audio_route_switch = SwitchButton(
        bool(window.settings_state["audio"].get("route_new_apps_to_default_sink", True))
    )
    layout.addWidget(
        SettingsRow(
            material_icon("hub"),
            "Route new apps to default sink",
            "Prefer the selected sink for fresh app launches instead of leaving routing entirely to PulseAudio defaults.",
            window.icon_font,
            window.ui_font,
            window.audio_route_switch,
        )
    )

    window.audio_mute_behavior_combo = QComboBox()
    window.audio_mute_behavior_combo.setObjectName("settingsCombo")
    window.audio_mute_behavior_combo.addItem("Leave as is", "leave_as_is")
    window.audio_mute_behavior_combo.addItem("Mute on lock", "mute_on_lock")
    window.audio_mute_behavior_combo.addItem("Mute on suspend", "mute_on_suspend")
    mute_behavior = str(window.settings_state["audio"].get("mute_behavior", "leave_as_is"))
    mute_index = window.audio_mute_behavior_combo.findData(mute_behavior)
    window.audio_mute_behavior_combo.setCurrentIndex(max(0, mute_index))
    layout.addWidget(
        SettingsRow(
            material_icon("lock"),
            "Mute behavior",
            "What Hanauta should prefer to do when you lock or suspend the session.",
            window.icon_font,
            window.ui_font,
            window.audio_mute_behavior_combo,
        )
    )

    window.audio_status = QLabel("Audio routing is ready.")
    window.audio_status.setWordWrap(True)
    window.audio_status.setStyleSheet("color: rgba(246,235,247,0.72);")
    layout.addWidget(window.audio_status)

    buttons = QHBoxLayout()
    buttons.setSpacing(8)
    window.audio_refresh_button = QPushButton("Refresh devices")
    window.audio_refresh_button.setObjectName("secondaryButton")
    window.audio_refresh_button.clicked.connect(window._refresh_audio_devices)
    window.audio_save_button = QPushButton("Apply audio settings")
    window.audio_save_button.setObjectName("primaryButton")
    window.audio_save_button.clicked.connect(window._save_audio_settings)
    for button in (window.audio_refresh_button, window.audio_save_button):
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    buttons.addWidget(window.audio_refresh_button)
    buttons.addWidget(window.audio_save_button)
    buttons.addStretch(1)
    layout.addLayout(buttons)

    window._refresh_audio_devices()
    return card

