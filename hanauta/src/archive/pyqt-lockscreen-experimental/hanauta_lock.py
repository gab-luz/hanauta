#!/usr/bin/env python3
"""
Hanauta Lock

Secure X11/i3 flow:
- PyQt renders the themed lock artwork using the current wallpaper and Matugen.
- i3lock performs the actual screen lock, keyboard grab, and authentication.

This keeps the Hanauta look while delegating real locking to a proper locker.
"""

from __future__ import annotations

import getpass
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

CURRENT_WALLPAPER = os.path.expanduser("~/.wallpapers/wallpaper.png")
ROOT = Path(__file__).resolve().parents[4]
MATUGEN_SCRIPT = ROOT / "hanauta" / "src" / "eww" / "scripts" / "run_matugen.sh"
MATUGEN_COLORS = ROOT / "hanauta" / "src" / "eww" / "colors.scss"


BG_TINT = QColor("#0b0911")
CARD_BG = QColor(21, 18, 30, 228)
CARD_EDGE = QColor(121, 105, 156, 120)
TEXT_MAIN = QColor("#f1e8ff")
TEXT_SUB = QColor("#cdbfe5")
TEXT_DIM = QColor("#9a8fb4")
ACCENT = QColor("#c8b6ff")
ACCENT_2 = QColor("#8ec5ff")
SHAPE_COLORS = [QColor("#c8b6ff"), QColor("#8ec5ff"), QColor("#93e9be"), QColor("#ffcf90")]
SHAPE_KINDS = ["square", "circle", "triangle", "diamond"]


def _parse_scss_var(text: str, name: str) -> str:
    prefix = f"${name}:"
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(prefix):
            continue
        value = line.split(":", 1)[1].strip().rstrip(";")
        if value.startswith("#") and len(value) >= 7:
            return value
    return ""


def _sample_wallpaper_color(path: str) -> str:
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return "#c8b6ff"
    image = pixmap.toImage().scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return image.pixelColor(0, 0).name()


def apply_matugen_palette() -> None:
    wallpaper_path = CURRENT_WALLPAPER if os.path.exists(CURRENT_WALLPAPER) else ""
    if wallpaper_path and MATUGEN_SCRIPT.exists():
        try:
            subprocess.run(
                [str(MATUGEN_SCRIPT), wallpaper_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    try:
        scss = MATUGEN_COLORS.read_text(encoding="utf-8")
    except Exception:
        scss = ""

    sampled = _sample_wallpaper_color(wallpaper_path) if wallpaper_path else "#c8b6ff"
    bg = _parse_scss_var(scss, "bg") or sampled
    fg = _parse_scss_var(scss, "fg") or "#f1e8ff"
    surface = _parse_scss_var(scss, "bgSecondary") or bg
    surface_variant = _parse_scss_var(scss, "bgSecondaryAlt") or bg
    accent = _parse_scss_var(scss, "accent") or sampled
    blue = _parse_scss_var(scss, "blue") or "#8ec5ff"
    green = _parse_scss_var(scss, "green") or "#93e9be"
    yellow = _parse_scss_var(scss, "yellow") or "#ffcf90"
    outline = _parse_scss_var(scss, "fgDim") or "#9a8fb4"

    global CARD_BG, CARD_EDGE, TEXT_MAIN, TEXT_SUB, TEXT_DIM, ACCENT, ACCENT_2, SHAPE_COLORS
    CARD_BG = QColor(surface)
    CARD_BG.setAlpha(226)
    CARD_EDGE = QColor(surface_variant)
    CARD_EDGE.setAlpha(150)
    TEXT_MAIN = QColor(fg)
    TEXT_SUB = QColor(outline if outline else fg)
    TEXT_DIM = QColor(outline if outline else fg)
    ACCENT = QColor(accent)
    ACCENT_2 = QColor(blue)
    SHAPE_COLORS = [QColor(accent), QColor(blue), QColor(green), QColor(yellow)]


class WallpaperBackdrop(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()

    def set_wallpaper(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._pixmap.isNull():
            painter.fillRect(self.rect(), BG_TINT)
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class ShapePasswordWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _paint_magic_intro(self, p: QPainter, center: QPointF, base_size: float, color: QColor) -> None:
        outer = QColor(color)
        outer.setAlpha(52)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(outer)
        glow_size = base_size * 1.45
        p.drawEllipse(QRectF(center.x() - glow_size / 2, center.y() - glow_size / 2, glow_size, glow_size))

        spark = QColor("#f8efff")
        spark.setAlpha(88)
        p.setPen(QPen(spark, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        ring = base_size * 1.22
        p.drawEllipse(QRectF(center.x() - ring / 2, center.y() - ring / 2, ring, ring))

    def _paint_token(self, p: QPainter, kind: str, center: QPointF, size: float, color: QColor) -> None:
        half = size / 2
        rect = QRectF(center.x() - half, center.y() - half, size, size)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)

        if kind == "circle":
            p.drawEllipse(rect)
            return

        if kind == "square":
            p.drawRoundedRect(rect, size * 0.22, size * 0.22)
            return

        path = QPainterPath()
        if kind == "triangle":
            path.moveTo(center.x(), center.y() - half)
            path.lineTo(center.x() + half, center.y() + half * 0.85)
            path.lineTo(center.x() - half, center.y() + half * 0.85)
            path.closeSubpath()
        else:
            path.moveTo(center.x(), center.y() - half)
            path.lineTo(center.x() + half, center.y())
            path.lineTo(center.x(), center.y() + half)
            path.lineTo(center.x() - half, center.y())
            path.closeSubpath()
        p.drawPath(path)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        token_size = 14.0
        gap = 14.0
        total = 4
        total_w = total * token_size + (total - 1) * gap
        x = (self.width() - total_w) / 2
        y = self.height() / 2

        for index in range(total):
            center = QPointF(x + token_size / 2, y)
            color = SHAPE_COLORS[index % len(SHAPE_COLORS)]
            self._paint_magic_intro(p, center, token_size, color)
            p.save()
            p.translate(center)
            p.rotate(12.0 * (index % 2) - 6.0)
            self._paint_token(p, SHAPE_KINDS[index % len(SHAPE_KINDS)], QPointF(0.0, 0.0), token_size, color)
            p.restore()
            x += token_size + gap


class LockCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lockCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(560)
        self.setMinimumHeight(430)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

        self.time_label = QLabel()
        self.date_label = QLabel()
        self.user_label = QLabel(getpass.getuser())
        self.message_label = QLabel("Authentication handled by i3lock")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)

        self.avatar = QLabel("◈")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFixedSize(108, 108)

        self.shapes = ShapePasswordWidget()
        self.hint_label = QLabel("Type your password anywhere to unlock")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._build_ui()
        self._apply_fonts()
        self.update_clock()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 32)
        root.setSpacing(14)

        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        avatar_wrap = QWidget()
        avatar_layout = QHBoxLayout(avatar_wrap)
        avatar_layout.setContentsMargins(0, 6, 0, 6)
        avatar_layout.addStretch(1)
        avatar_layout.addWidget(self.avatar)
        avatar_layout.addStretch(1)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(255,255,255,0.08);")

        root.addWidget(self.time_label)
        root.addWidget(self.date_label)
        root.addSpacing(8)
        root.addWidget(avatar_wrap)
        root.addWidget(self.user_label)
        root.addSpacing(4)
        root.addWidget(line)
        root.addSpacing(12)
        root.addWidget(self.shapes)
        root.addWidget(self.message_label)
        root.addStretch(1)
        root.addWidget(self.hint_label)

        self.setStyleSheet(
            f"""
            QFrame#lockCard {{
                background: rgba({CARD_BG.red()}, {CARD_BG.green()}, {CARD_BG.blue()}, 0.89);
                border: 1px solid rgba({CARD_EDGE.red()}, {CARD_EDGE.green()}, {CARD_EDGE.blue()}, 0.68);
                border-radius: 28px;
            }}
            QLabel {{
                color: {TEXT_MAIN.name()};
                background: transparent;
            }}
            """
        )

        self.avatar.setStyleSheet(
            f"""
            QLabel {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba({ACCENT.red()}, {ACCENT.green()}, {ACCENT.blue()}, 0.28),
                    stop: 1 rgba({ACCENT_2.red()}, {ACCENT_2.green()}, {ACCENT_2.blue()}, 0.18)
                );
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 54px;
                color: {ACCENT.name()};
            }}
            """
        )

    def _apply_fonts(self) -> None:
        clock_font = QFont("Inter")
        clock_font.setPointSize(34)
        clock_font.setBold(True)
        self.time_label.setFont(clock_font)
        self.time_label.setStyleSheet(f"color: {TEXT_MAIN.name()};")

        mono_font = QFont("JetBrains Mono")
        mono_font.setPointSize(11)
        self.date_label.setFont(mono_font)
        self.date_label.setStyleSheet(f"color: {TEXT_SUB.name()};")

        user_font = QFont("Inter")
        user_font.setPointSize(14)
        user_font.setBold(True)
        self.user_label.setFont(user_font)
        self.user_label.setStyleSheet(f"color: {ACCENT.name()};")

        avatar_font = QFont("Inter")
        avatar_font.setPointSize(28)
        avatar_font.setBold(True)
        self.avatar.setFont(avatar_font)

        msg_font = QFont("JetBrains Mono")
        msg_font.setPointSize(10)
        self.message_label.setFont(msg_font)
        self.message_label.setStyleSheet(f"color: {TEXT_DIM.name()};")

        hint_font = QFont("JetBrains Mono")
        hint_font.setPointSize(9)
        self.hint_label.setFont(hint_font)
        self.hint_label.setStyleSheet(
            f"color: rgba({TEXT_MAIN.red()}, {TEXT_MAIN.green()}, {TEXT_MAIN.blue()}, 0.56);"
        )

    def update_clock(self) -> None:
        now = time.localtime()
        self.time_label.setText(time.strftime("%H:%M", now))
        self.date_label.setText(time.strftime("%A • %d %B %Y", now))


class LockScene(QWidget):
    def __init__(self, geometry) -> None:
        super().__init__(None, Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setGeometry(0, 0, geometry.width(), geometry.height())

        self.background = WallpaperBackdrop(self)
        self.background.setGeometry(self.rect())

        self.card = LockCard(self)
        self._apply_wallpaper()
        self._position_card()

    def _apply_wallpaper(self) -> None:
        pixmap = QPixmap(CURRENT_WALLPAPER)
        if pixmap.isNull():
            pixmap = QPixmap(self.size())
            pixmap.fill(BG_TINT)
        self.background.set_wallpaper(pixmap)

    def _position_card(self) -> None:
        self.card.move((self.width() - self.card.width()) // 2, (self.height() - self.card.height()) // 2)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.background.setGeometry(self.rect())
        self._position_card()


def render_lock_image(app: QApplication) -> Path:
    apply_matugen_palette()
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        raise RuntimeError("No screen available")

    geometry = screen.virtualGeometry()
    scene = LockScene(geometry)
    scene.ensurePolished()
    scene.resize(geometry.size())
    app.processEvents()

    canvas = QPixmap(scene.size())
    canvas.fill(Qt.GlobalColor.transparent)
    scene.render(canvas)

    tmp = tempfile.NamedTemporaryFile(prefix="hanauta-lock-", suffix=".png", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    if not canvas.save(str(tmp_path), "PNG"):
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError("Failed to write i3lock background image")
    return tmp_path


def find_locker() -> str:
    for name in ("i3lock-color", "i3lock"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("No supported locker found. Install i3lock or i3lock-color.")


def run_locker(image_path: Path) -> int:
    locker = find_locker()
    command = [locker, "-n", "-e", "-i", str(image_path)]
    return subprocess.run(command, check=False).returncode


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("HanautaLock")
    app.setQuitOnLastWindowClosed(False)

    image_path: Path | None = None

    def _cleanup(*_args) -> None:
        if image_path is not None:
            image_path.unlink(missing_ok=True)
        raise SystemExit(1)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    try:
        image_path = render_lock_image(app)
        return run_locker(image_path)
    finally:
        if image_path is not None:
            image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
