#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


ROOT = Path(__file__).resolve().parents[3]
FONTS_DIR = ROOT / "assets" / "fonts"
PLUGIN_DIR = Path.home() / ".config" / "i3" / "hanauta" / "plugins" / "hanauta-plugin-vpn-control"
INSTALL_SCRIPT = PLUGIN_DIR / "bin" / "install_root_service.sh"
VPN_ICON = PLUGIN_DIR / "assets" / "wireguard_brand.svg"


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def load_fonts() -> tuple[str, str]:
    rubik = ""
    material = ""
    for key, path in {
        "rubik": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "material": FONTS_DIR / "MaterialIcons-Regular.ttf",
    }.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            continue
        if key == "rubik":
            rubik = families[0]
        else:
            material = families[0]
    return detect_font(rubik, "Rubik", "Sans Serif"), detect_font(
        material, "Material Icons", "Sans Serif"
    )


def tinted_svg(path: Path, color: QColor, size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    if not path.exists():
        return pix
    renderer = QSvgRenderer(str(path))
    painter = QPainter(pix)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pix.rect(), color)
    painter.end()
    return pix


class Prompt(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.ui_font, _icon_font = load_fonts()
        self._build()

    def _build(self) -> None:
        self.setWindowTitle("Hanauta VPN Setup")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.showFullScreen()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        backdrop = QFrame()
        backdrop.setStyleSheet("background: rgba(8, 10, 16, 0.94);")
        root.addWidget(backdrop)

        wrap = QVBoxLayout(backdrop)
        wrap.setContentsMargins(40, 40, 40, 40)
        wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedWidth(680)
        card.setStyleSheet(
            """
            QFrame { background: rgba(29, 33, 43, 0.96); border: 1px solid rgba(164, 198, 255, 0.28); border-radius: 20px; }
            QLabel#title { color: #F4F6FB; font-size: 30px; font-weight: 700; }
            QLabel#body { color: #C6CFDF; font-size: 14px; }
            QPushButton { min-height: 48px; border-radius: 14px; font-size: 14px; font-weight: 600; padding: 0 16px; }
            QPushButton#primary { background: #6DA9FF; color: #0D1320; border: none; }
            QPushButton#secondary { background: rgba(53, 61, 77, 0.94); color: #E6EBF4; border: 1px solid rgba(145, 158, 182, 0.35); }
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(tinted_svg(VPN_ICON, QColor("#7CB4FF"), 92))
        layout.addWidget(icon)

        title = QLabel("WireGuard Root Agent Not Running")
        title.setObjectName("title")
        title.setFont(QFont(self.ui_font, 18, QFont.Weight.DemiBold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            "Install/start the Hanauta WireGuard root agent now?\n\n"
            "If systemd is available, this enables and starts the agent services so they keep running automatically. "
            "On OpenRC systems, install script support may be limited."
        )
        body.setObjectName("body")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setFont(QFont(self.ui_font, 11))
        layout.addWidget(body)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        yes_btn = QPushButton("Yes")
        yes_btn.setObjectName("primary")
        yes_btn.clicked.connect(self._install_agent)
        no_btn = QPushButton("No")
        no_btn.setObjectName("secondary")
        no_btn.clicked.connect(self.close)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.close)
        actions.addWidget(yes_btn)
        actions.addWidget(no_btn)
        actions.addWidget(cancel_btn)
        layout.addLayout(actions)

        wrap.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)

    def _install_agent(self) -> None:
        if not INSTALL_SCRIPT.exists():
            QMessageBox.warning(self, "VPN Setup", f"Installer not found:\n{INSTALL_SCRIPT}")
            return
        try:
            if shutil.which("pkexec"):
                result = subprocess.run(
                    ["pkexec", str(INSTALL_SCRIPT)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            elif shutil.which("sudo"):
                result = subprocess.run(
                    ["sudo", str(INSTALL_SCRIPT)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            else:
                QMessageBox.warning(self, "VPN Setup", "Neither pkexec nor sudo is available.")
                return
        except Exception as exc:
            QMessageBox.critical(self, "VPN Setup", f"Failed to start installer:\n{exc}")
            return

        if result.returncode == 0:
            QMessageBox.information(
                self,
                "VPN Setup",
                "WireGuard root agent installed and started.\n\nIt will auto-start via init service.",
            )
            self.close()
            return

        detail = (result.stderr or result.stdout or "").strip() or "Unknown error."
        QMessageBox.critical(self, "VPN Setup Failed", detail)


def main() -> int:
    app = QApplication(sys.argv)
    prompt = Prompt()
    prompt.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
