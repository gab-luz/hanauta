from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap


def draw_wallpaper_mode(
    painter: QPainter, source: QImage, width: int, height: int, mode: str
) -> None:
    if source.isNull() or width <= 0 or height <= 0:
        return
    src_w = source.width()
    src_h = source.height()
    if src_w <= 0 or src_h <= 0:
        return

    if mode == "stretch":
        painter.drawImage(QRect(0, 0, width, height), source)
        return

    if mode == "tile":
        scaled = source
        if src_w > width or src_h > height:
            scaled = source.scaled(
                min(src_w, width),
                min(src_h, height),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        for x in range(0, width, max(1, scaled.width())):
            for y in range(0, height, max(1, scaled.height())):
                painter.drawImage(x, y, scaled)
        return

    if mode == "center":
        x = (width - src_w) // 2
        y = (height - src_h) // 2
        painter.drawImage(x, y, source)
        return

    aspect_mode = (
        Qt.AspectRatioMode.KeepAspectRatio
        if mode == "fit"
        else Qt.AspectRatioMode.KeepAspectRatioByExpanding
    )
    scaled = source.scaled(
        width, height, aspect_mode, Qt.TransformationMode.SmoothTransformation
    )
    x = (width - scaled.width()) // 2
    y = (height - scaled.height()) // 2
    painter.drawImage(x, y, scaled)


def rounded_pixmap(path: Path, width: int, height: int, radius: int) -> QPixmap:
    source = QPixmap(str(path))
    if source.isNull():
        fallback = QPixmap(width, height)
        fallback.fill(QColor("#241d2b"))
        return fallback
    scaled = source.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    target = QPixmap(width, height)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, width, height, radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return target

