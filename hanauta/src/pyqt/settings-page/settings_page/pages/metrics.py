from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout


def build_metric_card(window, title: str, value_label: QLabel) -> QFrame:
    card = QFrame()
    card.setObjectName("settingsRow")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)

    title_label = QLabel(title)
    title_font = QFont(window.ui_font, 8)
    title_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    title_label.setFont(title_font)
    title_label.setProperty("mutedText", True)
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    return card

