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
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}", "Rubik", "Noto Sans", sans-serif;
            }}
            #glassPanel {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 28px;
            }}
            #pageStack {{
                background: transparent;
            }}
            #overviewSection, #infoCard, #settingsContentWrap, #sidebar, #gameCarouselCard {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 22px;
            }}
            #avatar {{
                background: qlineargradient(x1:0, y1:1, x2:1, y2:0, stop:0 {theme.primary}, stop:1 {theme.tertiary});
                color: {theme.active_text};
                font-family: "{self.material_font}";
                border-radius: 23px;
                border: none;
                padding: 0px;
            }}
            #avatar[hasPhoto="true"] {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
            #userLabel {{
                font-size: 17px;
                font-weight: 600;
                color: {theme.text};
            }}
            #uptimeLabel {{
                color: {theme.text_muted};
            }}
            #circleIconButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: none;
                border-radius: 999px;
                color: {theme.icon};
                font-family: "{self.material_font}";
            }}
            #circleIconButton[roundedRect="true"] {{
                border-radius: 14px;
            }}
            #circleIconButton:hover {{
                background: {theme.hover_bg};
            }}
            #circleIconButton[accent="power"] {{
                background: {theme.error};
                color: {theme.on_error};
            }}
            #circleIconButton[accent="power"]:hover {{
                background: {theme.error};
            }}
            #sliderWrap, #compactSliderWrap {{
                background: transparent;
            }}
            #sectionIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #sectionTitle, #settingsTitle, #settingsSectionTitle {{
                font-size: 15px;
                font-weight: 600;
                color: {theme.text};
            }}
            #sectionSubtitle, #settingsSectionSubtitle, #statusHint {{
                color: {theme.text_muted};
                font-size: 10px;
            }}
            #metricCard {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
            }}
            #metricLabel {{
                color: {theme.inactive};
                font-size: 10px;
                text-transform: uppercase;
            }}
            #metricValue {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 600;
            }}
            #inlineMetricPrimary {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 600;
            }}
            #inlineMetric {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 500;
            }}
            #softButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.text};
                padding: 8px 12px;
                font-weight: 500;
            }}
            #softButton:hover {{
                background: {theme.hover_bg};
            }}
            #actionTile {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 14px;
            }}
            #actionTile:hover {{
                background: {theme.hover_bg};
            }}
            #actionTileIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #actionTileTitle {{
                color: {theme.text};
                font-size: 10px;
                font-weight: 600;
            }}
            #actionTileSubtitle {{
                color: {theme.text_muted};
                font-size: 9px;
            }}
            #compactIconAction {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: none;
                border-radius: 999px;
                color: {theme.icon};
                font-family: "{self.material_font}";
            }}
            #compactIconAction:hover {{
                background: {theme.hover_bg};
            }}
            #compactIconAction[active="true"] {{
                background: {theme.accent_soft};
                color: {theme.primary};
            }}
            #compactIconAction:disabled {{
                color: {theme.inactive};
                background: {rgba(theme.surface_container_high, 0.44)};
            }}
            #playButton {{
                background: {theme.primary};
                border: none;
                border-radius: 999px;
                color: {theme.active_text};
                padding: 6px 14px;
                font-weight: 700;
                letter-spacing: 0.6px;
            }}
            #playButton:hover {{
                background: {rgba(theme.primary, 0.88)};
            }}
            #playButton:disabled {{
                background: {rgba(theme.surface_container_high, 0.44)};
                color: {theme.inactive};
            }}
            #confirmPopup {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 22px;
            }}
            #confirmTitle {{
                color: {theme.text};
                font-size: 13px;
                font-weight: 700;
            }}
            #confirmSubtitle {{
                color: {theme.text_muted};
                font-size: 11px;
            }}
            #confirmPlayButton {{
                background: {theme.primary};
                border: none;
                border-radius: 14px;
                color: {theme.active_text};
                padding: 8px 12px;
                font-weight: 700;
            }}
            #confirmPlayButton:hover {{
                background: {rgba(theme.primary, 0.88)};
            }}
            #settingsInput {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.text};
                padding: 12px 14px;
            }}
            #fieldLabel {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 600;
            }}
            #entityScroll {{
                background: transparent;
            }}
            #phoneStatusDot {{
                color: {theme.primary};
                font-size: 16px;
            }}
            #appearancePreset {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
                color: {theme.text};
                padding: 16px 18px;
                font-weight: 600;
            }}
            #appearancePreset:hover {{
                background: {theme.hover_bg};
            }}
            #sliderIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #compactSliderWrap {{
                background: {rgba(theme.surface_container_high, 0.34)};
                border: none;
                border-radius: 14px;
            }}
            #wideSlider::groove:horizontal, #compactSlider::groove:horizontal {{
                background: {rgba(theme.on_surface_variant, 0.12)};
                border-radius: 999px;
                margin: 0px;
            }}
            #wideSlider, #compactSlider {{
                background: transparent;
                border: none;
            }}
            #wideSlider::groove:horizontal {{
                height: 42px;
            }}
            #compactSlider::groove:horizontal {{
                height: 16px;
            }}
            #wideSlider::sub-page:horizontal, #compactSlider::sub-page:horizontal {{
                background: {theme.primary};
                border-radius: 999px;
                margin: 0px;
            }}
            #wideSlider::add-page:horizontal, #compactSlider::add-page:horizontal {{
                background: {rgba(theme.on_surface_variant, 0.12)};
                border-radius: 999px;
                margin: 0px;
            }}
            #wideSlider::handle:horizontal, #compactSlider::handle:horizontal {{
                background: transparent;
                width: 0px;
                margin: 0;
            }}
            #gameStack {{
                background: transparent;
                border: none;
            }}
            #gameCarouselCard {{
                background: qlineargradient(x1:0, y1:1, x2:1, y2:0,
                    stop:0 {rgba(theme.surface_container_high, 0.92)},
                    stop:1 {rgba(theme.primary_container, 0.72)});
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 20px;
            }}
            #gameSlideInner {{
                background: transparent;
                border: none;
                min-height: 104px;
            }}
            #gameKicker {{
                color: {theme.text};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
                text-transform: uppercase;
            }}
            #gameCarouselTitle, #gameSlideTitle {{
                color: {theme.text};
                font-size: 14px;
                font-weight: 600;
            }}
            #gameSlidePlatform, #gameCaption, #feedCardMeta {{
                color: {theme.text_muted};
                font-size: 9px;
                font-weight: 500;
            }}
            #gameStatChip {{
                background: {theme.primary};
                color: {theme.active_text};
                border-radius: 10px;
                padding: 3px 8px;
                font-size: 9px;
                font-weight: 600;
            }}
            #gameStatLabel {{
                color: {theme.primary};
                background: {rgba(theme.primary, 0.14)};
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 10px;
                padding: 4px 8px;
                font-size: 9px;
                font-weight: 500;
            }}
            #gameSlideHint {{
                color: {theme.inactive};
                font-size: 9px;
            }}
            #carouselDot {{
                color: {rgba(theme.on_surface_variant, 0.30)};
                font-size: 14px;
            }}
            #carouselDot[active="true"] {{
                color: {theme.primary};
            }}
            #miniCalendar {{
                background: transparent;
                border: none;
                border-radius: 16px;
                selection-background-color: {theme.primary};
                selection-color: {theme.active_text};
                alternate-background-color: transparent;
                color: {theme.text};
            }}
            #miniCalendar QWidget {{
                background: transparent;
                outline: none;
            }}
            #miniCalendar QAbstractItemView:focus,
            #miniCalendar QTableView:focus,
            #miniCalendar QSpinBox:focus,
            #miniCalendar QToolButton:focus {{
                outline: none;
            }}
            #miniCalendar QToolButton {{
                color: {theme.text};
                font-weight: 600;
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 4px 6px;
            }}
            #miniCalendar QToolButton:hover {{
                background: {rgba(theme.surface_container_high, 0.56)};
            }}
            #miniCalendar QToolButton#qt_calendar_monthbutton,
            #miniCalendar QToolButton#qt_calendar_yearbutton {{
                font-size: 12px;
            }}
            #miniCalendar QToolButton::menu-indicator {{
                image: none;
                width: 0px;
            }}
            #miniCalendar QMenu {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                color: {theme.text};
            }}
            #miniCalendar QAbstractItemView:enabled {{
                color: {calendar_body_text};
                background: {rgba(theme.surface_container_high, 0.18)};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 12px;
                selection-background-color: {theme.primary};
                selection-color: {theme.active_text};
                alternate-background-color: transparent;
                gridline-color: transparent;
                outline: 0;
            }}
            #miniCalendar QAbstractItemView::item:disabled {{
                color: {calendar_body_disabled};
            }}
            #miniCalendar QWidget#qt_calendar_navigationbar {{
                background: transparent;
            }}
            #miniCalendar QSpinBox {{
                background: transparent;
                color: {theme.text};
                border: none;
                border-radius: 10px;
                padding: 2px 4px;
                selection-background-color: {theme.primary};
            }}
            #miniCalendar QAbstractItemView {{
                background: {theme.chip_bg};
                color: {calendar_body_text};
                border: 1px solid {theme.chip_border};
                selection-background-color: {theme.primary};
                selection-color: {theme.active_text};
            }}
            #miniCalendar QTableView {{
                background: transparent;
                border: none;
            }}
            #feedCard {{
                background: {rgba(theme.surface_container_high, 0.76)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 14px;
            }}
            #feedCardIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #feedCardTitle {{
                color: {theme.text};
                font-size: 11px;
                font-weight: 600;
            }}
            #feedCardBody {{
                color: {theme.text_muted};
                font-size: 10px;
            }}
            #notificationCloseButton {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: none;
                border-radius: 10px;
                color: {theme.text_muted};
                font-family: "{self.material_font}";
            }}
            #notificationCloseButton:hover {{
                background: {theme.hover_bg};
                color: {theme.text};
            }}
            #eventsScroll, #notificationsScroll {{
                background: transparent;
                border: none;
            }}
            #eventsScroll QScrollBar:vertical, #notificationsScroll QScrollBar:vertical {{
                width: 0px;
                background: transparent;
            }}
            #eventsScroll QScrollBar::handle:vertical, #notificationsScroll QScrollBar::handle:vertical {{
                background: transparent;
            }}
            #eventsScroll QScrollBar:horizontal, #notificationsScroll QScrollBar:horizontal {{
                height: 4px;
                background: transparent;
            }}
            #eventsScroll QScrollBar::handle:horizontal, #notificationsScroll QScrollBar::handle:horizontal {{
                background: {rgba(theme.primary, 0.5)};
                border-radius: 2px;
                min-width: 20px;
            }}
            #eventsScroll QScrollBar::handle:horizontal:hover, #notificationsScroll QScrollBar::handle:horizontal:hover {{
                background: {theme.primary};
            }}
            #eventsScroll QScrollBar::add-line:horizontal, #notificationsScroll QScrollBar::add-line:horizontal,
            #eventsScroll QScrollBar::sub-line:horizontal, #notificationsScroll QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            #eventsScroll QScrollBar::add-page:horizontal, #notificationsScroll QScrollBar::add-page:horizontal,
            #eventsScroll QScrollBar::sub-page:horizontal, #notificationsScroll QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            #mediaCard {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            #cover {{
                background: {theme.surface_container_high};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
            }}
            #mediaTitle {{
                font-size: 13px;
                font-weight: 500;
                color: {theme.text};
            }}
            #mediaArtist {{
                font-size: 11px;
                color: {theme.primary};
            }}
            #progressTrack {{
                background: {theme.app_running_border};
                border-radius: 2px;
            }}
            #progressFill {{
                background: {theme.primary};
                border-radius: 2px;
            }}
            #plainIconButton {{
                background: transparent;
                border: none;
                color: {theme.text_muted};
                font-family: "{self.material_font}";
            }}
            #plainIconButton:hover {{
                color: {theme.primary};
            }}
            #quickTileIcon {{
                font-family: "{self.material_font}";
            }}
            #timeCode {{
                color: {theme.inactive};
                font-size: 10px;
            }}
            """
        )
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


