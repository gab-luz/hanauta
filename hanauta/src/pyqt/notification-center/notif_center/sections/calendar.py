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


class CalendarMixin:
    """Calendar card and events methods for NotificationCenter."""

    def _build_calendar_card(self) -> QFrame:
        card, calendar, settings_btn = build_calendar_card(
            material_font=self.material_font,
            settings_glyph=material_icon("settings"),
            on_open_settings=lambda: self._launch_settings_page(
                "services", "calendar_widget"
            ),
            title=t("section.calendar"),
        )
        self.calendar_widget = calendar
        self.calendar_settings_btn = settings_btn
        if hasattr(self.calendar_widget, "eventDateClicked"):
            self.calendar_widget.eventDateClicked.connect(self._show_calendar_day_events)
        return card


    def _hidden_scroll(self, name: str) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setObjectName(name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(6)
        scroll.setWidget(container)
        return scroll, container, inner


    def _build_events_card(self) -> QFrame:
        card, layout = self._section_shell(t("section.upcoming_events"), "")
        self.events_scroll, self.events_container, self.events_layout = (
            self._hidden_scroll("eventsScroll")
        )
        layout.addWidget(self.events_scroll, 1)
        return card


    def _apply_calendar_events(self, events: list) -> None:
        self._calendar_fetch_in_progress = False
        self._calendar_events = (
            [item for item in events if isinstance(item, dict)]
            if isinstance(events, list)
            else []
        )
        self._sync_calendar_event_dates()
        self._render_calendar_events(force=True)


    def _calendar_event_date(self, event: dict) -> QDate | None:
        start_text = str(event.get("start", "")).strip()
        if not start_text:
            return None
        try:
            moment = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
            return QDate(moment.year, moment.month, moment.day)
        except Exception:
            date = QDate.fromString(start_text[:10], Qt.DateFormat.ISODate)
            return date if date.isValid() else None


    def _sync_calendar_event_dates(self) -> None:
        if not hasattr(self, "calendar_widget"):
            return
        dates = []
        for event in self._calendar_events:
            if str(event.get("title", "")).strip() == t("events.sync_failed.meta"):
                continue
            date = self._calendar_event_date(event)
            if date is not None and date.isValid():
                dates.append(date)
        if hasattr(self.calendar_widget, "set_event_dates"):
            self.calendar_widget.set_event_dates(dates)


    def _calendar_events_for_date(self, date: QDate) -> list[dict]:
        events = []
        for event in self._calendar_events:
            event_date = self._calendar_event_date(event)
            if event_date is not None and event_date == date:
                events.append(event)
        return events


    def _calendar_event_meta(self, event: dict) -> str:
        start_text = str(event.get("start", "")).strip()
        end_text = str(event.get("end", "")).strip()
        try:
            start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
            if end_text:
                end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
                return f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
            return start.strftime("%H:%M")
        except Exception:
            return start_text or t("events.calendar_event")


    def _show_calendar_day_events(self, date: QDate) -> None:
        events = self._calendar_events_for_date(date)
        if not events:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(t("dialog.calendar_events"))
        dialog.setModal(False)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        dialog.setStyleSheet(self.styleSheet())

        shell = QFrame(dialog)
        shell.setObjectName("confirmPopup")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(16, 16, 16, 16)
        shell_layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(date.toString("dddd, d MMMM"))
        title_label.setObjectName("confirmTitle")
        close_button = QPushButton(material_icon("close"))
        close_button.setObjectName("compactIconAction")
        close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_button.setFont(QFont(self.material_font, 16))
        close_button.setFixedSize(28, 28)
        close_button.clicked.connect(dialog.accept)
        header.addWidget(title_label, 1)
        header.addWidget(close_button)
        shell_layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("eventsPopupScroll")
        scroll.setMinimumWidth(420)
        scroll.setMaximumHeight(420 if len(events) > 2 else 320)

        content = QWidget()
        content.setObjectName("eventsPopupContent")
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        for event in events:
            item = QFrame()
            item.setObjectName("feedCard")
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(12, 10, 12, 10)
            item_layout.setSpacing(4)

            event_title = QLabel(str(event.get("title", t("events.untitled"))).strip())
            event_title.setObjectName("feedCardTitle")
            event_title.setWordWrap(True)
            meta = QLabel(self._calendar_event_meta(event))
            meta.setObjectName("feedCardMeta")
            item_layout.addWidget(event_title)
            item_layout.addWidget(meta)

            location = str(event.get("location", "")).strip()
            source = str(event.get("source", "")).strip()
            detail_parts = [part for part in (location, source) if part]
            if detail_parts:
                details = QLabel(" • ".join(detail_parts))
                details.setObjectName("feedCardBody")
                details.setWordWrap(True)
                item_layout.addWidget(details)

            description = str(
                event.get("description", event.get("body", event.get("notes", "")))
            ).strip()
            if description:
                desc = QLabel(description)
                desc.setObjectName("feedCardBody")
                desc.setWordWrap(True)
                item_layout.addWidget(desc)

            content_layout.addWidget(item)
        content_layout.addStretch(1)
        shell_layout.addWidget(scroll)

        root = QVBoxLayout(dialog)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)
        dialog.adjustSize()
        dialog.move(
            self.geometry().center().x() - dialog.width() // 2,
            self.geometry().center().y() - dialog.height() // 2,
        )
        self._calendar_event_dialogs.append(dialog)
        dialog.destroyed.connect(
            lambda _obj=None, popup=dialog: self._calendar_event_dialogs.remove(popup)
            if popup in self._calendar_event_dialogs
            else None
        )
        dialog.show()


    def _apply_calendar_formats(self) -> None:
        if not hasattr(self, "calendar_widget"):
            return
        theme = self.theme_palette
        is_light = self._is_light_theme(theme)
        apply_calendar_theme(
            self.calendar_widget,
            theme_primary=theme.primary,
            theme_active_text=theme.active_text,
            theme_text=theme.text,
            theme_surface_container_high=theme.surface_container_high,
            is_light=is_light,
        )


    def _request_calendar_refresh(self) -> None:
        if self._calendar_fetch_in_progress:
            return
        self._calendar_fetch_in_progress = True
        self._calendar_last_fetch = monotonic()

        def worker() -> None:
            events = load_calendar_events(30)
            try:
                self.calendarEventsReady.emit(events)
            except Exception:
                pass

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()


    def _render_calendar_events(self, *, force: bool = False) -> None:
        try:
            signature = json.dumps(self._calendar_events, sort_keys=True)
        except Exception:
            signature = str(self._calendar_events)
        if not force and signature == self._calendar_render_signature:
            return
        self._calendar_render_signature = signature

        if self._calendar_events:
            title = str(self._calendar_events[0].get("title", "")).strip()
            if title == t("events.sync_failed.meta"):
                err = str(self._calendar_events[0].get("start", "")).strip()
                if err and err != self._calendar_last_error:
                    self._calendar_last_error = err
                    try:
                        print(f"[hanauta] calendar error: {err}", file=sys.stderr)
                    except Exception:
                        pass
            elif self._calendar_last_error:
                self._calendar_last_error = ""
                try:
                    print("[hanauta] calendar recovered", file=sys.stderr)
                except Exception:
                    pass
        self._clear_layout_widgets(self.events_layout)

        calendar_icon_pixmap = QPixmap()
        calendar_icon_path = Path(CALENDAR_NOTIFICATION_ICON).expanduser()
        if calendar_icon_path.exists():
            calendar_icon_pixmap = tinted_svg_pixmap(
                calendar_icon_path, QColor(self.theme_palette.primary), 18
            )

        calendar_configured = self._is_calendar_configured()

        if not calendar_configured:
            settings_btn = QPushButton(t("btn.add_calendar"))
            settings_btn.setObjectName("tonalButton")
            settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            settings_btn.setFont(QFont(self.ui_font, 10))
            settings_btn.clicked.connect(
                lambda: self._launch_settings_page("services", "calendar_widget")
            )
            self.events_layout.addWidget(
                self._list_item_card(
                    t("events.no_account.title"),
                    t("events.no_account.body"),
                    t("events.no_account.meta"),
                    "calendar_today",
                    calendar_icon_pixmap,
                    settings_btn,
                )
            )
            self.events_layout.addStretch(1)
            return

        if not self._calendar_events:
            self.events_layout.addWidget(
                self._list_item_card(
                    t("events.no_upcoming.title"),
                    t("events.no_upcoming.body"),
                    t("events.no_upcoming.meta"),
                    "calendar_today",
                    calendar_icon_pixmap,
                )
            )
            self.events_layout.addStretch(1)
            return

        first_title = str(self._calendar_events[0].get("title", "")).strip()
        if first_title == t("events.sync_failed.meta"):
            err = str(self._calendar_events[0].get("start", "")).strip()
            settings_btn = QPushButton(t("btn.open_settings"))
            settings_btn.setObjectName("tonalButton")
            settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            settings_btn.setFont(QFont(self.ui_font, 10))
            settings_btn.clicked.connect(
                lambda: self._launch_settings_page("services", "calendar_widget")
            )
            self.events_layout.addWidget(
                self._list_item_card(
                    t("events.sync_failed.title"),
                    err or t("events.sync_failed.body"),
                    t("events.sync_failed.meta"),
                    "calendar_today",
                    calendar_icon_pixmap,
                    settings_btn,
                )
            )
            self.events_layout.addStretch(1)
            return

        for event in self._calendar_events:
            title = str(event.get("title", t("events.untitled")))
            start_text = str(event.get("start", ""))
            try:
                moment = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
                meta = moment.strftime("%a • %d %b • %H:%M")
            except Exception:
                meta = start_text or t("events.upcoming_fallback")
            location = str(event.get("location", "")).strip()
            subtitle = location or t("events.calendar_event")
            self.events_layout.addWidget(
                self._list_item_card(
                    title,
                    subtitle,
                    meta,
                    "calendar_today",
                    calendar_icon_pixmap,
                )
            )
        self.events_layout.addStretch(1)


    def _is_calendar_configured(self) -> bool:
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            cal = settings.get("calendar", {}) if isinstance(settings, dict) else {}
            url = str(cal.get("caldav_url", "")).strip()
            username = str(cal.get("caldav_username", "")).strip()
            return bool(url and username)
        except Exception:
            return False


