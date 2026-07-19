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
from notif_center.stylesheet import build_stylesheet
from pyqt.shared.calendar_card import *
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family
from pyqt.shared.runtime import entry_command, entry_patterns, python_executable


class ThemeMixin:
    """Theme and styling methods for NotificationCenter."""

    def _is_light_theme(self, theme) -> bool:
        text_luma = self._css_color_luma(str(getattr(theme, "text", "") or ""))
        if text_luma is not None:
            return text_luma < 0.45
        surface_luma = self._css_color_luma(str(getattr(theme, "surface", "") or ""))
        if surface_luma is not None:
            return surface_luma > 0.60
        return False


    def _css_color_luma(self, value: str) -> float | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.startswith("rgba(") and text.endswith(")"):
            parts = [part.strip() for part in text[5:-1].split(",")]
            if len(parts) >= 3:
                try:
                    red = int(float(parts[0]))
                    green = int(float(parts[1]))
                    blue = int(float(parts[2]))
                except ValueError:
                    return None
                red = max(0, min(255, red))
                green = max(0, min(255, green))
                blue = max(0, min(255, blue))
                return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0
        if text.startswith("#"):
            color = QColor(text)
            if color.isValid():
                return (
                    0.2126 * color.red()
                    + 0.7152 * color.green()
                    + 0.0722 * color.blue()
                ) / 255.0
        return None


    def _apply_styles(self) -> None:
        theme = self.theme_palette
        is_light = self._is_light_theme(theme)
        calendar_body_text = "#000000" if is_light else "rgba(255,255,255,0.92)"
        calendar_body_disabled = "#6c6c6c" if is_light else "rgba(255,255,255,0.55)"
        css = build_stylesheet(theme, self.ui_font, self.material_font, calendar_body_text, calendar_body_disabled)
        self.setStyleSheet(css)
        self._apply_calendar_formats()
        for quick_button in getattr(self, "quick_buttons", {}).values():
            quick_button.apply_theme(
                theme, self.current_accent["accent"], self.current_accent["on_accent"]
            )
        for button_key, button in getattr(self, "settings_nav_buttons", {}).items():
            current_index = (
                self.settings_stack.currentIndex()
                if hasattr(self, "settings_stack")
                else 0
            )
            key_to_index = {"overview": 0, "appearance": 1, "homeassistant": 2}
            button.apply_state(
                key_to_index.get(button_key, -1) == current_index,
                self.current_accent["accent"],
                self.current_accent["on_accent"],
                theme,
            )


    def _apply_media_palette(
        self,
        start: str | None = None,
        end: str | None = None,
        border: str | None = None,
        accent: str | None = None,
    ) -> None:
        if not hasattr(self, "media_base"):
            return
        theme = self.theme_palette
        start = start or theme.media_active_start
        end = end or theme.media_active_end
        border = border or theme.media_active_border
        accent = accent or self.current_accent["accent"]
        self.media_base.setStyleSheet(
            f"""
            background: qradialgradient(
                cx: 0.36, cy: 0.26, radius: 0.95, fx: 0.36, fy: 0.26,
                stop: 0 {start},
                stop: 0.38 {end},
                stop: 1 {theme.panel_bg}
            );
            border-radius: 20px;
            """
        )
        self.media_card.setStyleSheet(
            f"""
            QFrame#mediaCard {{
                border: 1px solid {border};
                border-radius: 20px;
            }}
            """
        )
        bg_luma = self._css_color_luma(end) or self._css_color_luma(start) or 0.0
        scrim_is_light = bg_luma > 0.62
        self.media_scrim.setStyleSheet(
            f"""
            background: qradialgradient(
                cx: 0.5, cy: 0.36, radius: 1.05, fx: 0.5, fy: 0.34,
                stop: 0 {"rgba(255, 255, 255, 0.30)" if scrim_is_light else "rgba(0, 0, 0, 0.25)"},
                stop: 0.48 {"rgba(255, 255, 255, 0.72)" if scrim_is_light else "rgba(0, 0, 0, 0.58)"},
                stop: 1 {"rgba(255, 255, 255, 0.96)" if scrim_is_light else "rgba(0, 0, 0, 1.0)"}
            );
            border-radius: 20px;
            """
        )
        self.progress_fill.setStyleSheet(f"background: {accent}; border-radius: 2px;")
        media_text = "#000000" if bg_luma > 0.62 else "#ffffff"
        self.media_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {media_text};"
        )
        self.media_artist.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {media_text};"
        )
        time_style = f"font-size: 11px; font-weight: 600; color: {media_text};"
        self.elapsed.setStyleSheet(time_style)
        self.total.setStyleSheet(time_style)
        for button in (self.prev_btn, self.next_btn):
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {media_text};
                    font-family: "{self.material_font}";
                }}
                QPushButton:hover {{
                    color: {accent};
                }}
                """
            )
        self.play_btn.setStyleSheet(
            f"""
            background: {accent};
            border: none;
            border-radius: 20px;
            color: {theme.active_text};
            font-family: "{self.material_font}";
            """
        )


    def _sync_media_card_layers(self) -> None:
        if not hasattr(self, "media_card"):
            return
        media_rect = self.media_card.rect()
        self.media_base.setGeometry(media_rect)
        self.media_scrim.setGeometry(media_rect)
        self.media_content.setGeometry(media_rect)


    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme_palette = load_theme_palette()
        if self.theme_palette.use_matugen:
            self.current_accent = {
                "accent": self.theme_palette.primary,
                "on_accent": self.theme_palette.active_text,
                "soft": self.theme_palette.accent_soft,
            }
        self._apply_styles()
        self._apply_media_palette()
        self._render_home_assistant_tiles()


    def _animate_in(self) -> None:
        self._panel_animation = QPropertyAnimation(self.panel_effect, b"opacity", self)
        self._panel_animation.setDuration(260)
        self._panel_animation.setStartValue(0.0)
        self._panel_animation.setEndValue(1.0)
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.start()


