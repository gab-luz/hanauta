from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import QPushButton


def create_close_button(icon_text: str, font_family: str, font_size: int = 18, *, object_name: Optional[str] = None) -> QPushButton:
    """
    Build a standard close icon button (Material 'close') used by popup widgets.
    """
    button = QPushButton(icon_text)
    button.setObjectName(object_name or "iconButton")
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    button.setFont(QFont(font_family, font_size))
    return button
