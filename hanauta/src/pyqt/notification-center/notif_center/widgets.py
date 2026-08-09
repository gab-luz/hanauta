from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from pyqt.shared.theme import rgba

from notif_center.utils import material_icon


class QuickSettingButton(QFrame):
    def __init__(self, material_font: str, title: str, icon: str, callback):
        super().__init__()
        self.material_font = material_font
        self.title = title
        self.callback = callback
        self.theme = None
        self.accent = "#D0BCFF"
        self.on_accent = "#381E72"
        self.active = False
        self._icon_text = icon
        self._subtitle = "Off"
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("quickTile")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setFont(QFont(self.material_font, 18))
        self.icon_label.setObjectName("quickTileIcon")

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("quickTileTitle")
        self.subtitle_label = QLabel("Off")
        self.subtitle_label.setObjectName("quickTileSubtitle")
        self.icon_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.subtitle_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.subtitle_label)

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_wrap, 1)
        self._render()

    def apply_theme(self, theme, accent: str, on_accent: str) -> None:
        self.theme = theme
        self.accent = accent
        self.on_accent = on_accent
        self._render()

    def set_state(self, active: bool, icon: str, subtitle: str) -> None:
        self.active = active
        self._icon_text = icon
        self._subtitle = subtitle
        self._render()

    def _render(self) -> None:
        theme = self.theme
        if theme is not None:
            icon_color = self.on_accent if self.active else theme.icon
            title_color = self.on_accent if self.active else theme.text
            sub_color = rgba(self.on_accent, 0.78) if self.active else theme.text_muted
            bg = self.accent if self.active else theme.app_running_bg
            hover = theme.accent_soft if self.active else theme.hover_bg
        else:
            icon_color = "#381E72" if self.active else "rgba(255,255,255,0.82)"
            title_color = "#381E72" if self.active else "#ffffff"
            sub_color = (
                "rgba(56,30,114,0.78)" if self.active else "rgba(255,255,255,0.54)"
            )
            bg = "#D0BCFF" if self.active else "rgba(255,255,255,0.05)"
            hover = "#ddcbff" if self.active else "rgba(255,255,255,0.10)"
        self.setStyleSheet(
            f"""
            QFrame#quickTile {{
                background: {bg};
                border: none;
                border-radius: 18px;
            }}
            QFrame#quickTile:hover {{
                background: {hover};
            }}
            """
        )
        self.icon_label.setText(material_icon(self._icon_text))
        self.icon_label.setStyleSheet(f"color: {icon_color};")
        self.title_label.setText(self.title)
        self.title_label.setStyleSheet(f"color: {title_color}; font-weight: 600;")
        self.subtitle_label.setText(self._subtitle)
        self.subtitle_label.setStyleSheet(f"color: {sub_color}; font-size: 10px;")

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SidebarItemButton(QPushButton):
    def __init__(self, material_font: str, key: str, title: str, icon: str) -> None:
        super().__init__()
        self.key = key
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("sidebarItem")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setObjectName("sidebarItemIcon")
        self.icon_label.setFont(QFont(material_font, 18))
        self.text_label = QLabel(title)
        self.text_label.setObjectName("sidebarItemText")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)
        self.apply_state(False, "#D0BCFF", "#381E72")

    def apply_state(
        self, active: bool, accent: str, on_accent: str, theme=None
    ) -> None:
        self.setChecked(active)
        if active:
            self.setStyleSheet(
                f"""
                QPushButton#sidebarItem {{
                    background: {accent};
                    border: none;
                    border-radius: 16px;
                }}
                QLabel#sidebarItemIcon, QLabel#sidebarItemText {{
                    color: {on_accent};
                    font-weight: 600;
                }}
                """
            )
        else:
            inactive_bg = (
                theme.app_running_bg if theme is not None else "rgba(255,255,255,0.04)"
            )
            hover_bg = theme.hover_bg if theme is not None else "rgba(255,255,255,0.08)"
            icon_color = theme.icon if theme is not None else "rgba(255,255,255,0.80)"
            text_color = theme.text if theme is not None else "rgba(255,255,255,0.90)"
            self.setStyleSheet(
                f"""
                QPushButton#sidebarItem {{
                    background: {inactive_bg};
                    border: none;
                    border-radius: 16px;
                }}
                QPushButton#sidebarItem:hover {{
                    background: {hover_bg};
                }}
                QLabel#sidebarItemIcon {{
                    color: {icon_color};
                }}
                QLabel#sidebarItemText {{
                    color: {text_color};
                    font-weight: 500;
                }}
                """
            )


class ActionTile(QFrame):
    def __init__(self, material_font: str, title: str, icon: str, callback) -> None:
        super().__init__()
        self.callback = callback
        self.setObjectName("actionTile")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setObjectName("actionTileIcon")
        self.icon_label.setFont(QFont(material_font, 18))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("actionTileTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("actionTileSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.icon_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.subtitle_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

    def set_content(self, icon: str, title: str, subtitle: str) -> None:
        self.icon_label.setText(material_icon(icon))
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CompactIconAction(QPushButton):
    def __init__(self, material_font: str, icon: str) -> None:
        super().__init__()
        self.setObjectName("compactIconAction")
        self.setFont(QFont(material_font, 16))
        self.setFixedSize(28, 28)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setText(material_icon(icon))

    def set_icon(self, icon: str) -> None:
        self.setText(material_icon(icon))

    def set_active(self, active: bool) -> None:
        if active:
            self.setProperty("active", True)
        else:
            self.setProperty("active", False)
        self.style().unpolish(self)
        self.style().polish(self)


class ServiceLauncherCard(QFrame):
    def __init__(
        self,
        material_font: str,
        title: str,
        detail: str,
        icon: str,
        action_label: str,
        callback,
    ) -> None:
        super().__init__()
        self.callback = callback
        self.setObjectName("infoCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        icon_label = QLabel(material_icon(icon))
        icon_label.setObjectName("sectionIcon")
        icon_label.setFixedWidth(20)
        icon_label.setFont(QFont(material_font, 18))

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("metricValue")
        subtitle_label = QLabel(detail)
        subtitle_label.setObjectName("statusHint")
        subtitle_label.setWordWrap(True)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        subtitle_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        text.addWidget(title_label)
        text.addWidget(subtitle_label)

        action = QPushButton(action_label)
        action.setObjectName("softButton")
        action.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        action.clicked.connect(callback)

        layout.addWidget(icon_label)
        layout.addLayout(text, 1)
        layout.addWidget(action)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ElidedLabel(QLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:
        super().setText(text)
        self._apply_elision()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_elision()

    def _apply_elision(self) -> None:
        fm = self.fontMetrics()
        elided = fm.elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        if elided != self.text():
            super().setText(elided)


class ClickableLabel(QLabel):
    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.callback()
