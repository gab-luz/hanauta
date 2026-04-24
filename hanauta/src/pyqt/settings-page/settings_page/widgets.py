from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QVBoxLayout

from settings_page.theme_data import HANAUTA_FONT_PROFILE


class IconLabel(QLabel):
    def __init__(self, glyph: str, font_family: str, size: int, color: str) -> None:
        super().__init__(glyph)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont(font_family, pointSize=size))
        self.setStyleSheet(f"color: {color}; background: transparent;")
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)


class NavPillButton(QPushButton):
    def __init__(self, glyph: str, text: str, icon_font: str, text_font: str) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("navPill")
        self._compact = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.icon_label = QLabel(glyph)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont(icon_font, 17))
        self.icon_label.setProperty("iconRole", True)
        self.icon_label.setFixedWidth(22)

        self.text_label = QLabel(text)
        self.text_label.setObjectName("navPillText")
        self.text_label.setProperty("iconRole", False)
        self.text_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.text_label.setWordWrap(False)
        nav_font = QFont(text_font, 10, QFont.Weight.DemiBold)
        nav_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self.text_label.setFont(nav_font)
        self.text_label.setStyleSheet(
            "color: rgba(246,235,247,0.92); background: transparent;"
        )

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.text_label, 1, Qt.AlignmentFlag.AlignVCenter)

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)
        self.text_label.setVisible(not self._compact)
        self.setProperty("compact", self._compact)
        self.style().unpolish(self)
        self.style().polish(self)


class SegmentedChip(QPushButton):
    def __init__(self, text: str, checked: bool = False) -> None:
        super().__init__(text)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(30)
        self.setObjectName("segmentedChip")


class ThemeModeCard(QPushButton):
    def __init__(
        self, icon_text: str, title: str, icon_font: str, ui_font: str
    ) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("themeModeCard")
        self.setMinimumSize(112, 90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        icon = QLabel(icon_text)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont(icon_font, 18))
        icon.setProperty("iconRole", True)
        icon.setStyleSheet("color: #FFFFFF; background: transparent;")

        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont(ui_font, 10))
        label.setStyleSheet("color: #FFFFFF; background: transparent;")

        layout.addStretch(1)
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch(1)