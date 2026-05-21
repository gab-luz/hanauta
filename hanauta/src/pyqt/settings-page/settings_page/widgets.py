from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt6.QtSvg import QSvgRenderer

from settings_page.theme_data import HANAUTA_FONT_PROFILE


class IconLabel(QLabel):
    def __init__(self, glyph: str, font_family: str, size: int, color: str) -> None:
        super().__init__(glyph)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont(font_family, pointSize=size))
        self.setStyleSheet(f"color: {color}; background: transparent;")
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)


def _tint_pixmap(source: QPixmap, color: QColor) -> QPixmap:
    if source.isNull():
        return QPixmap()
    src = source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    out = QImage(src.size(), QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(out.rect(), color)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, src)
    painter.end()
    return QPixmap.fromImage(out)


class NavPillButton(QPushButton):
    def __init__(
        self,
        glyph: str,
        text: str,
        icon_font: str,
        text_font: str,
        icon_svg_path: str = "",
        tint_color: str | None = None,
    ) -> None:
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
        if icon_svg_path:
            svg_path = Path(icon_svg_path).expanduser()
            if svg_path.exists():
                icon_pix = self._load_icon_pixmap(svg_path, tint_color)
                if icon_pix is not None and not icon_pix.isNull():
                    self.icon_label.setText("")
                    self.icon_label.setPixmap(icon_pix)

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

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.text_label, 1, Qt.AlignmentFlag.AlignVCenter)

    @staticmethod
    def _load_icon_pixmap(path: Path, tint_color: str | None = None) -> QPixmap | None:
        size = 18
        if path.suffix.lower() == ".svg":
            renderer = QSvgRenderer(str(path))
            if renderer.isValid():
                pix = QPixmap(size, size)
                pix.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pix)
                renderer.render(painter)
                painter.end()
                if tint_color:
                    pix = _tint_pixmap(pix, QColor(tint_color))
                return pix
        pix = QPixmap(str(path))
        if pix.isNull():
            return None
        if tint_color:
            pix = _tint_pixmap(pix, QColor(tint_color))
        return pix.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

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

        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont(ui_font, 10))

        layout.addStretch(1)
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch(1)
