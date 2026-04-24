from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QFrame,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QWidget,
)


class SwitchButton(QPushButton):
    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, width: int = 52) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self._width = width
        self.setFixedSize(width, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("switchButton")
        self.toggled.connect(self.emit_toggled)

    def emit_toggled(self, checked: bool) -> None:
        self.toggled.emit(checked)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        track = QPainterPath()
        track.addRoundedRect(rect, 14, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        if self.isChecked():
            painter.fillPath(
                track,
                self.palette().color(self.styleStateIconColorRole()),
            )
        else:
            painter.fillPath(track, self.palette().color("window").darker(140))
        thumb = QPainterPath()
        thumb_offset = 4 if self.isChecked() else rect.width() - 24
        thumb.addEllipse(
            thumb_offset,
            rect.y() + 4,
            20,
            rect.height() - 8,
        )
        if self.isChecked():
            painter.fillPath(
                thumb,
                self.palette().color("window"),
            )
        else:
            painter.fillPath(thumb, self.palette().color("window").lighter(160))


class PreviewCard(QFrame):
    def __init__(
        self,
        icon: str = "",
        title: str = "",
        subtitle: str = "",
        icon_font_family: str = "",
    ) -> None:
        super().__init__()
        self.setObjectName("previewCard")
        self.setFixedHeight(80)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        if icon:
            icon_label = QLabel(icon)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFont(QFont(icon_font_family, 22))
            icon_label.setStyleSheet("color: #FFFFFF; background: transparent;")
            icon_label.setFixedWidth(32)
            layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_label.setFont(QFont("Sans Serif", 10, QFont.Weight.DemiBold))
        title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        text_layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setFont(QFont("Sans Serif", 9))
            subtitle_label.setStyleSheet(
                "color: rgba(255,255,255,0.58); background: transparent;"
            )
            text_layout.addWidget(subtitle_label)

        layout.addLayout(text_layout, 1)
        layout.addStretch(0)


class ActionCard(QPushButton):
    def __init__(
        self,
        icon: str = "",
        title: str = "",
        subtitle: str = "",
        icon_font_family: str = "",
    ) -> None:
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("actionCard")
        self.setMinimumHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        if icon:
            icon_label = QLabel(icon)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFont(QFont(icon_font_family, 18))
            icon_label.setStyleSheet("color: #FFFFFF; background: transparent;")
            icon_label.setFixedWidth(28)
            layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_label.setFont(QFont("Sans Serif", 10, QFont.Weight.Medium))
        title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        text_layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setFont(QFont("Sans Serif", 8))
            subtitle_label.setStyleSheet(
                "color: rgba(255,255,255,0.54); background: transparent;"
            )
            text_layout.addWidget(subtitle_label)

        layout.addLayout(text_layout, 1)
        layout.addStretch(0)


class SettingsRow(QFrame):
    def __init__(
        self,
        label: str = "",
        subtitle: str = "",
        icon: str = "",
        icon_font_family: str = "",
    ) -> None:
        super().__init__()
        self.setObjectName("settingsRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(16)

        if icon:
            icon_label = QLabel(icon)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFont(QFont(icon_font_family, 18))
            icon_label.setStyleSheet("color: #FFFFFF; background: transparent;")
            icon_label.setFixedWidth(28)
            layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setContentsMargins(0, 0, 0, 0)

        label_widget = QLabel(label)
        label_widget.setFont(QFont("Sans Serif", 10, QFont.Weight.DemiBold))
        label_widget.setStyleSheet("color: #FFFFFF; background: transparent;")
        text_layout.addWidget(label_widget)

        if subtitle:
            subtitle_widget = QLabel(subtitle)
            subtitle_widget.setFont(QFont("Sans Serif", 9))
            subtitle_widget.setStyleSheet(
                "color: rgba(255,255,255,0.58); background: transparent;"
            )
            subtitle_widget.setWordWrap(True)
            text_layout.addWidget(subtitle_widget)

        layout.addLayout(text_layout, 1)


class ExpandableServiceSection(QFrame):
    toggled = pyqtSignal(bool)

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        icon: str = "",
        icon_font_family: str = "",
    ) -> None:
        super().__init__()
        self._expanded = False
        self.setObjectName("expandableServiceSection")
        self.setMinimumHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        if icon:
            self.icon_label = QLabel(icon)
            self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.icon_label.setFont(QFont(icon_font_family, 18))
            self.icon_label.setStyleSheet("color: #FFFFFF; background: transparent;")
            self.icon_label.setFixedWidth(28)
            layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Sans Serif", 10, QFont.Weight.DemiBold))
        self.title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        text_layout.addWidget(self.title_label)

        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setFont(QFont("Sans Serif", 9))
            self.subtitle_label.setStyleSheet(
                "color: rgba(255,255,255,0.58); background: transparent;"
            )
            self.subtitle_label.setWordWrap(True)
            text_layout.addWidget(self.subtitle_label)

        layout.addLayout(text_layout, 1)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.toggled.emit(expanded)