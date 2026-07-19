from __future__ import annotations
from pyqt.shared.theme import rgba


def build_stylesheet(theme, ui_font: str, material_font: str, calendar_body_text: str, calendar_body_disabled: str) -> str:
    return f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "{ui_font}", "Rubik", "Noto Sans", sans-serif;
            }}
            #glassPanel {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 22px;
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
                font-family: "{material_font}";
                border-radius: 21px;
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
                font-family: "{material_font}";
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
                font-family: "{material_font}";
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
                font-family: "{material_font}";
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
                font-family: "{material_font}";
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
                font-family: "{material_font}";
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
                min-height: 96px;
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
                font-family: "{material_font}";
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
                font-family: "{material_font}";
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
                font-family: "{material_font}";
            }}
            #plainIconButton:hover {{
                color: {theme.primary};
            }}
            #quickTileIcon {{
                font-family: "{material_font}";
            }}
            #timeCode {{
                color: {theme.inactive};
                font-size: 10px;
            }}
            """
