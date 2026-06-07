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


class ProfileMixin:
    """Profile avatar methods for NotificationCenter."""

    def _profile_photo_path(self) -> Path | None:
        for candidate in PROFILE_PHOTO_CANDIDATES:
            if candidate.exists():
                return candidate
        return None


    def _rounded_avatar_pixmap(self, path: Path, size: int = 42) -> QPixmap:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QPixmap()
        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - size) // 2)
        y = max(0, (scaled.height() - size) // 2)
        cropped = scaled.copy(x, y, size, size)
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0.0, 0.0, float(size), float(size), 14.0, 14.0)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return rounded


    def _refresh_profile_avatar(self, force: bool = False) -> None:
        if not hasattr(self, "avatar"):
            return
        photo_path = self._profile_photo_path()
        if photo_path is None:
            if force or self._avatar_source is not None:
                self.avatar.setPixmap(QPixmap())
                self.avatar.setText(material_icon("person"))
                self.avatar.setProperty("hasPhoto", False)
                self.avatar.style().unpolish(self.avatar)
                self.avatar.style().polish(self.avatar)
                self._avatar_source = None
                self._avatar_mtime_ns = -1
            return
        try:
            mtime_ns = photo_path.stat().st_mtime_ns
        except OSError:
            mtime_ns = -1
        if (
            not force
            and self._avatar_source == photo_path
            and self._avatar_mtime_ns == mtime_ns
        ):
            return
        rounded = self._rounded_avatar_pixmap(photo_path, self.avatar.width())
        if rounded.isNull():
            self.avatar.setPixmap(QPixmap())
            self.avatar.setText(material_icon("person"))
            self.avatar.setProperty("hasPhoto", False)
            self.avatar.style().unpolish(self.avatar)
            self.avatar.style().polish(self.avatar)
            return
        self.avatar.setText("")
        self.avatar.setPixmap(rounded)
        self.avatar.setProperty("hasPhoto", True)
        self.avatar.style().unpolish(self.avatar)
        self.avatar.style().polish(self.avatar)
        self._avatar_source = photo_path
        self._avatar_mtime_ns = mtime_ns


    def _open_profile_photo_picker(self) -> None:
        run_script_bg("chpfp.sh")
        for delay in (1200, 3000, 7000):
            QTimer.singleShot(
                delay, lambda force=True: self._refresh_profile_avatar(force=force)
            )


