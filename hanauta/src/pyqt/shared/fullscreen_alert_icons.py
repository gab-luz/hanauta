#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Optional
import re

from PyQt6.QtCore import QByteArray, Qt, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer


# Icons directory
ICONS_DIR = Path(__file__).resolve().parent / "assets" / "icons"


def load_svg_file(icon_name: str) -> str:
    """Load SVG content from file."""
    svg_path = ICONS_DIR / f"{icon_name}.svg"
    if svg_path.exists():
        return svg_path.read_text(encoding="utf-8")
    # Fallback
    fallback_path = ICONS_DIR / "notification.svg"
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8")
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>'


def create_svg_pixmap(icon_name: str, size: int = 24, color: str = "#ffffff") -> QPixmap:
    """Create a QPixmap from an SVG icon with specified size and color."""
    svg_content = load_svg_file(icon_name)
    
    # Replace fill color if it's not currentColor
    if color != "currentColor" and "fill=" in svg_content:
        svg_content = re.sub(r'fill="[^"]*"', f'fill="{color}"', svg_content)
        svg_content = re.sub(r"fill='[^']*'", f"fill='{color}'", svg_content)
        svg_content = re.sub(r'fill=([^\s>]+)', f'fill="{color}"', svg_content)
    elif color != "currentColor":
        svg_content = svg_content.replace('<svg ', f'<svg fill="{color}" ')
    
    # Ensure width/height are set for the renderer
    svg_content = svg_content.replace('width="24" height="24"', f'width="{size}" height="{size}"')
    svg_content = svg_content.replace('width="24"', f'width="{size}"').replace('height="24"', f'height="{size}"')

    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    from PyQt6.QtGui import QPainter
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap


def create_svg_icon(icon_name: str, size: int = 24, color: str = "#ffffff") -> QIcon:
    """Create a QIcon from an SVG icon."""
    pixmap = create_svg_pixmap(icon_name, size, color)
    return QIcon(pixmap)


class SVGIconManager:
    """Manages SVG icons with caching for performance."""

    def __init__(self):
        self._cache: dict[str, QPixmap] = {}
        self._icon_cache: dict[str, QIcon] = {}

    def get_pixmap(self, icon_name: str, size: int = 24, color: str = "#ffffff") -> QPixmap:
        key = f"{icon_name}:{size}:{color}"
        if key not in self._cache:
            self._cache[key] = create_svg_pixmap(icon_name, size, color)
        return self._cache[key]

    def get_icon(self, icon_name: str, size: int = 24, color: str = "#ffffff") -> QIcon:
        key = f"{icon_name}:{size}:{color}"
        if key not in self._icon_cache:
            self._icon_cache[key] = create_svg_icon(icon_name, size, color)
        return self._icon_cache[key]


# Global instance
svg_icon_manager = SVGIconManager()


def get_svg_icon(icon_name: str, size: int = 24, color: Optional[str] = None) -> QIcon:
    """Get an SVG icon, using theme-aware color if not specified."""
    if color is None:
        color = "#ffffff"
    return svg_icon_manager.get_icon(icon_name, size, color)


def get_svg_pixmap(icon_name: str, size: int = 24, color: Optional[str] = None) -> QPixmap:
    """Get an SVG pixmap, using theme-aware color if not specified."""
    if color is None:
        color = "#ffffff"
    return svg_icon_manager.get_pixmap(icon_name, size, color)


def material_icon_pixmap(icon_name: str, size: int = 24, color: Optional[str] = None) -> QPixmap:
    """Drop-in replacement that returns QPixmap instead of Unicode char."""
    return get_svg_pixmap(icon_name, size, color)


# Fallback function that tries font first, then SVG
def get_icon(icon_name: str, size: int = 24, theme_color: str = "#ffffff", material_font: str = "") -> QIcon:
    """
    Get icon - tries font-based first, falls back to SVG.
    Returns QIcon that can be used with QLabel.setPixmap() or QPushButton.setIcon()
    """
    # If we have a valid material font, use it
    if material_font:
        from pyqt.shared.material_icons import MATERIAL_ICONS
        char = MATERIAL_ICONS.get(icon_name, "")
        if char:
            from PyQt6.QtGui import QFont, QFontMetrics
            font = QFont(material_font, size)
            metrics = QFontMetrics(font)
            if metrics.horizontalAdvance(char) > 0:
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                from PyQt6.QtGui import QPainter
                painter = QPainter(pixmap)
                painter.setFont(font)
                painter.setPen(QColor(theme_color))
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, char)
                painter.end()
                return QIcon(pixmap)

    # Fallback to SVG
    return get_svg_icon(icon_name, size, theme_color)