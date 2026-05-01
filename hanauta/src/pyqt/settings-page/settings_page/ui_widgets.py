from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from settings_page.wallpaper_render import rounded_pixmap


class SwitchButton(QPushButton):
    toggledValue = pyqtSignal(bool)

    def __init__(self, checked: bool = False) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(50, 28)
        self.clicked.connect(self._emit_toggled)
        self._apply_state()

    def _emit_toggled(self) -> None:
        self._apply_state()
        self.toggledValue.emit(self.isChecked())

    def _apply_state(self) -> None:
        track = "#D7C2DC" if self.isChecked() else "rgba(255,255,255,0.18)"
        knob_x = 24 if self.isChecked() else 4
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {track};
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 14px;
            }}
            QPushButton::after {{
                content: '';
            }}
            """
        )
        self._knob_x = knob_x
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#251E2D" if self.isChecked() else "#F6ECFA"))
        painter.drawEllipse(self._knob_x, 3, 22, 22)
        painter.end()


class PreviewCard(QFrame):
    def __init__(self, wallpaper_path: Path, ui_font: str, display_font: str) -> None:
        super().__init__()
        self._ui_font = ui_font
        self._display_font = display_font
        self.setObjectName("previewCard")
        self.setMinimumHeight(214)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.wallpaper_label = QLabel()
        self.wallpaper_label.setScaledContents(False)
        self.wallpaper_label.setPixmap(rounded_pixmap(wallpaper_path, 430, 214, 18))
        self.wallpaper_label.setFixedHeight(214)
        self.wallpaper_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        overlay = QWidget(self.wallpaper_label)
        overlay.setGeometry(0, 0, 430, 214)
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        ambient = QLabel(overlay)
        ambient.setGeometry(0, 0, 430, 214)
        ambient.setStyleSheet(
            """
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(31,22,38,0.14),
                stop:0.55 rgba(31,22,38,0.55),
                stop:1 rgba(24,17,31,0.84)
            );
            border-radius: 18px;
            """
        )

        chip = QLabel("Ambient preview", overlay)
        chip.move(14, 14)
        chip.setStyleSheet(
            f"""
            background: rgba(255,255,255,0.14);
            color: #F5EAF7;
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 10px;
            padding: 4px 8px;
            font-family: "{ui_font}";
            font-size: 10px;
            """
        )
        chip.adjustSize()

        title = QLabel("Wallpaper & Colors", overlay)
        title.move(14, 162)
        title.setFont(QFont(display_font, 16))
        title.setStyleSheet("color: #F8EEF7; background: transparent;")
        title.adjustSize()

        subtitle = QLabel(
            "Expressive surfaces, soft contrast, and subtle translucency.", overlay
        )
        subtitle.move(14, 186)
        subtitle.setFont(QFont(ui_font, 9))
        subtitle.setStyleSheet(
            "color: rgba(248,238,247,0.75); background: transparent;"
        )
        subtitle.adjustSize()

        layout.addWidget(self.wallpaper_label)

    def update_wallpaper(self, wallpaper_path: Path) -> None:
        self.wallpaper_label.setPixmap(rounded_pixmap(wallpaper_path, 430, 214, 18))


class ActionCard(QPushButton):
    def __init__(
        self, icon_text: str, title: str, detail: str, icon_font: str, ui_font: str
    ) -> None:
        super().__init__()
        self._icon_font = icon_font
        self._ui_font = ui_font
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("actionCard")
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("actionIconWrap")
        icon_wrap.setFixedSize(32, 32)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel(icon_text)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont(icon_font, 15))
        self.icon_label.setProperty("iconRole", True)
        icon_layout.addWidget(self.icon_label)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont(ui_font, 9, QFont.Weight.DemiBold))
        self.title_label.setWordWrap(True)
        self.title_label.setObjectName("actionCardTitle")
        self.detail_label = QLabel(detail)
        self.detail_label.setWordWrap(True)
        self.detail_label.setFont(QFont(ui_font, 8))
        self.detail_label.setObjectName("actionCardDetail")

        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.detail_label)

        layout.addWidget(icon_wrap)
        layout.addLayout(text_wrap, 1)

    def set_content(self, icon_text: str, title: str, detail: str) -> None:
        self.icon_label.setText(icon_text)
        self.title_label.setText(title)
        self.detail_label.setText(detail)


class SettingsRow(QFrame):
    def __init__(
        self,
        icon_text: str,
        title: str,
        detail: str,
        icon_font: str,
        ui_font: str,
        trailing: QWidget,
        icon_svg_path: str = "",
    ) -> None:
        super().__init__()
        self.setObjectName("settingsRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("rowIconWrap")
        icon_wrap.setFixedSize(28, 28)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel(icon_text)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont(icon_font, 14))
        icon.setProperty("iconRole", True)
        if icon_svg_path:
            svg_path = Path(icon_svg_path).expanduser()
            if svg_path.exists():
                pix = QPixmap(str(svg_path))
                if not pix.isNull():
                    icon.setText("")
                    icon.setPixmap(
                        pix.scaled(
                            16,
                            16,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
        icon_layout.addWidget(icon)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)

        title_label = QLabel(title)
        title_label.setFont(QFont(ui_font, 9))
        title_label.setObjectName("settingsRowTitle")
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_label.setMinimumWidth(0)

        detail_label = QLabel(detail)
        detail_label.setFont(QFont(ui_font, 8))
        detail_label.setObjectName("settingsRowDetail")
        detail_label.setWordWrap(True)
        detail_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        detail_label.setMinimumWidth(0)

        text_wrap.addWidget(title_label)
        text_wrap.addWidget(detail_label)

        trailing.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(icon_wrap)
        layout.addLayout(text_wrap, 1)
        layout.addWidget(
            trailing, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )


class ExpandableServiceSection(QFrame):
    def __init__(
        self,
        key: str,
        title: str,
        detail: str,
        icon_text: str,
        icon_font: str,
        ui_font: str,
        content: QWidget,
        enabled: bool,
        on_toggle_enabled,
        icon_path: str = "",
    ) -> None:
        super().__init__()
        self.key = key
        self.icon_font = icon_font
        self.ui_font = ui_font
        self._expanded = False
        self._content = content
        self.setObjectName("serviceSection")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.header_button = QPushButton()
        self.header_button.setObjectName("serviceHeaderButton")
        self.header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_button.setMinimumHeight(84)
        self.header_button.clicked.connect(self.toggle_expanded)
        header = QHBoxLayout(self.header_button)
        header.setContentsMargins(14, 14, 14, 14)
        header.setSpacing(12)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("rowIconWrap")
        icon_wrap.setFixedSize(32, 32)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel(icon_text)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont(icon_font, 16))
        self.icon_label.setProperty("iconRole", True)
        icon_file = Path(str(icon_path or "")).expanduser() if icon_path else None
        if icon_file is not None and icon_file.exists():
            icon_pixmap = QIcon(str(icon_file)).pixmap(20, 20)
            if not icon_pixmap.isNull():
                self.icon_label.setPixmap(icon_pixmap)

        icon_layout.addWidget(self.icon_label)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)

        self.title_label = QLabel(title)
        self.title_label.setFont(QFont(ui_font, 10, QFont.Weight.DemiBold))
        self.title_label.setObjectName("serviceHeaderTitle")
        self.title_label.setWordWrap(True)

        self.detail_label = QLabel(detail)
        self.detail_label.setFont(QFont(ui_font, 8))
        self.detail_label.setObjectName("serviceHeaderDetail")
        self.detail_label.setWordWrap(True)

        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.detail_label)

        self.enabled_switch = SwitchButton(checked=enabled)
        self.enabled_switch.toggledValue.connect(on_toggle_enabled)

        header.addWidget(icon_wrap)
        header.addLayout(text_wrap, 1)
        header.addWidget(self.enabled_switch)

        layout.addWidget(self.header_button)

        self.content_area = QFrame()
        self.content_area.setObjectName("serviceContentArea")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(content)
        self.content_area.setVisible(False)

        layout.addWidget(self.content_area)

    def toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self.content_area.setVisible(self._expanded)
