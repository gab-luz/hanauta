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
from notif_center.notification_icons import notification_icon_pixmap
from notif_center.utils import *
from notif_center.widgets import *
from pyqt.shared.calendar_card import *
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family
from pyqt.shared.runtime import entry_command, entry_patterns, python_executable


class NotificationsMixin:
    """Notification history and cards methods for NotificationCenter."""

    _notification_icon_cache: dict[str, QPixmap] = {}

    def _build_notifications_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("overviewSection")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title_label = QLabel(t("section.last_notifications"))
        title_label.setObjectName("sectionTitle")
        self.clear_notifications_btn = QPushButton(material_icon("delete_sweep"))
        self.clear_notifications_btn.setObjectName("compactIconAction")
        self.clear_notifications_btn.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.clear_notifications_btn.setFont(QFont(self.material_font, 16))
        self.clear_notifications_btn.setFixedSize(26, 26)
        self.clear_notifications_btn.setToolTip(t("notif.tooltip.clear_all"))
        self.clear_notifications_btn.clicked.connect(self._clear_all_notifications)
        header.addWidget(title_label)
        header.addStretch(1)
        self.view_all_notifications_btn = QPushButton()
        history_pixmap = QPixmap()
        if HISTORY_ICON.exists():
            history_pixmap = tinted_svg_pixmap(
                HISTORY_ICON, QColor(self.theme_palette.icon), 16
            )
        if not history_pixmap.isNull():
            self.view_all_notifications_btn.setIcon(QIcon(history_pixmap))
        else:
            self.view_all_notifications_btn.setText(material_icon("history"))
        self.view_all_notifications_btn.setObjectName("compactIconAction")
        self.view_all_notifications_btn.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.view_all_notifications_btn.setFont(QFont(self.material_font, 16))
        self.view_all_notifications_btn.setFixedSize(26, 26)
        self.view_all_notifications_btn.setToolTip(t("notif.tooltip.view_all"))
        self.view_all_notifications_btn.clicked.connect(self._enter_full_history_view)
        header.addWidget(self.view_all_notifications_btn)
        header.addWidget(self.clear_notifications_btn)
        layout.addLayout(header)
        (
            self.notifications_scroll,
            self.notifications_container,
            self.notifications_layout,
        ) = self._hidden_scroll("notificationsScroll")
        layout.addWidget(self.notifications_scroll, 1)
        return card


    def _clear_layout_widgets(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count():
                    child = child_layout.takeAt(0)
                    if child.widget() is not None:
                        child.widget().deleteLater()


    def _history_item_id(self, payload: dict) -> int:
        raw = payload.get("id", 0)
        if isinstance(raw, dict):
            raw = raw.get("id", raw.get("value", raw.get("data", 0)))
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0


    def _history_item_matches(self, left: dict, right: dict) -> bool:
        left_id = self._history_item_id(left)
        right_id = self._history_item_id(right)
        if left_id and right_id:
            return left_id == right_id
        return (
            str(left.get("app_name", "")) == str(right.get("app_name", ""))
            and str(left.get("summary", "")) == str(right.get("summary", ""))
            and str(left.get("body", "")) == str(right.get("body", ""))
            and str(left.get("timestamp", "")) == str(right.get("timestamp", ""))
        )


    def _write_notification_history(self, history: list[dict]) -> None:
        _atomic_write_json(NOTIFICATION_HISTORY_FILE, history)


    def _dismiss_notification(self, target: dict) -> None:
        updated: list[dict] = []
        removed = False
        for item in self._notification_history:
            if not removed and self._history_item_matches(item, target):
                removed = True
                continue
            updated.append(item)
        self._write_notification_history(updated)
        self._poll_notification_history()


    def _clear_all_notifications(self) -> None:
        self._write_notification_history([])
        self._poll_notification_history()

    @staticmethod

    def _format_relative_time(timestamp: float) -> str:
        now = time.time()
        delta = now - timestamp
        if delta < 0:
            return t("time.just_now")
        if delta < 60:
            return t("time.just_now")
        minutes = int(delta // 60)
        if minutes == 1:
            return t("time.1_minute_ago")
        if minutes < 60:
            return t("time.n_minutes_ago", n=str(minutes))
        hours = int(delta // 3600)
        if hours == 1:
            return t("time.1_hour_ago")
        if hours < 24:
            return t("time.n_hours_ago", n=str(hours))
        days = int(delta // 86400)
        if days == 1:
            return t("time.yesterday")
        if days < 7:
            return t("time.n_days_ago", n=str(days))
        return datetime.fromtimestamp(timestamp).strftime("%d %b")

    @staticmethod

    def _format_uptime(seconds: int) -> str:
        if seconds < 60:
            return t("uptime.less_than_minute")
        total_minutes = seconds // 60
        hours = total_minutes // 60
        minutes = total_minutes % 60
        parts = []
        if hours > 0:
            parts.append(t("uptime.hour", h=str(hours)))
        if minutes > 0:
            parts.append(t("uptime.minute", m=str(minutes)))
        if not parts:
            return t("uptime.less_than_minute")
        return " ".join(parts)


    def _list_item_card(
        self,
        title: str,
        subtitle: str,
        meta: str,
        kind: str,
        icon_pixmap: QPixmap | None = None,
        action_button: QPushButton | None = None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("feedCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(10, 10, 10, 10)
        row.setSpacing(10)

        icon = QLabel(
            material_icon(kind) if icon_pixmap is None or icon_pixmap.isNull() else ""
        )
        icon.setObjectName("feedCardIcon")
        icon.setFont(QFont(self.material_font, 16))
        icon.setFixedWidth(20)
        if icon_pixmap is not None and not icon_pixmap.isNull():
            icon.setPixmap(icon_pixmap)
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("feedCardTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("feedCardBody")
        subtitle_label.setWordWrap(True)
        meta_label = QLabel(meta)
        meta_label.setObjectName("feedCardMeta")
        text.addWidget(title_label)
        text.addWidget(subtitle_label)
        text.addWidget(meta_label)
        row.addLayout(text, 1)
        if action_button is not None:
            row.addWidget(action_button, 0, Qt.AlignmentFlag.AlignTop)
        return card


    def _notification_icon_pixmap(
        self,
        app_name: str,
        desktop_entry: str = "",
        icon_name: str = "",
        summary: str = "",
        body: str = "",
    ) -> QPixmap:
        cache_key = f"{app_name}\x00{desktop_entry}\x00{icon_name}\x00{summary}\x00{body}"
        cached = self._notification_icon_cache.get(cache_key)
        if cached is not None:
            return cached
        pixmap = notification_icon_pixmap(
            app_name, desktop_entry, icon_name, summary, body, self.theme_palette
        )
        self._notification_icon_cache[cache_key] = pixmap
        return pixmap


    def _enter_full_history_view(self) -> None:
        self._in_full_history_view = True
        self._poll_notification_history()


    def _exit_full_history_view(self) -> None:
        self._in_full_history_view = False
        self._notif_mtime_ns = 0
        self._poll_notification_history()


    def _poll_notification_history(self) -> None:
        try:
            mtime = NOTIFICATION_HISTORY_FILE.stat().st_mtime_ns
        except OSError:
            mtime = 0
        if not self._in_full_history_view and mtime == self._notif_mtime_ns and self._notif_mtime_ns != 0:
            return
        self._notif_mtime_ns = mtime

        if self._in_full_history_view:
            self._notification_history = load_notification_history(500)
            now = time.time()
            cutoff = now - 86400
            self._notification_history = [
                item for item in self._notification_history
                if float(item.get("timestamp", 0) or 0) >= cutoff
            ]
        else:
            self._notification_history = load_notification_history(3)

        if not hasattr(self, "_notification_ids"):
            self._notification_ids: list[str] = []

        new_ids = [
            f"{item.get('app_name', '')}\x00{item.get('summary', '')}\x00{item.get('timestamp', '')}"
            for item in self._notification_history
        ]
        if new_ids == self._notification_ids:
            return
        self._notification_ids = new_ids

        self._clear_layout_widgets(self.notifications_layout)

        if hasattr(self, "clear_notifications_btn"):
            self.clear_notifications_btn.setEnabled(bool(self._notification_history))

        if self._in_full_history_view:
            back_pixmap = QPixmap()
            if ARROW_BACK_ICON.exists():
                back_pixmap = tinted_svg_pixmap(ARROW_BACK_ICON, QColor(self.theme_palette.icon), 16)
            if not back_pixmap.isNull():
                back_btn = QPushButton(f"  {t('notif.history.back')}")
                back_btn.setIcon(QIcon(back_pixmap))
            else:
                back_btn = QPushButton(f"{material_icon('arrow_back')}  {t('notif.history.back')}")
            back_btn.setObjectName("textButton")
            back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            back_btn.setFont(QFont(self.ui_font, 11))
            back_btn.clicked.connect(self._exit_full_history_view)
            self.notifications_layout.addWidget(back_btn)
            title_row = QHBoxLayout()
            title_row.setContentsMargins(4, 2, 4, 2)
            count_label = QLabel(
                t('notif.history.header', count=str(len(self._notification_history)), plural='s' if len(self._notification_history) != 1 else '')
            )
            count_label.setObjectName("sectionSubtitle")
            count_label.setFont(QFont(self.ui_font, 10))
            title_row.addWidget(count_label)
            title_row.addStretch(1)
            self.notifications_layout.addLayout(title_row)

        if not self._notification_history:
            if self._in_full_history_view:
                self.notifications_layout.addWidget(
                    self._list_item_card(
                        t("notif.history.empty.title"),
                        t("notif.history.empty.body"),
                        t("notif.history.empty.meta"),
                        "notifications",
                    )
                )
            else:
                self.notifications_layout.addWidget(
                    self._list_item_card(
                        t("notif.empty.title"),
                        t("notif.empty.body"),
                        t("notif.empty.meta"),
                        "notifications",
                    )
                )
            self.notifications_layout.addStretch(1)
            return

        for item in self._notification_history:
            title = str(item.get("summary", t("notif.fallback.title"))).strip() or t("notif.fallback.title")
            body = str(item.get("body", "")).replace("\n", " ").strip() or str(
                item.get("app_name", t("notif.fallback.body"))
            )
            app_name = str(item.get("app_name", t("notif.fallback.app"))).strip() or t("notif.fallback.app")
            desktop_entry = str(item.get("desktop_entry", "")).strip()
            icon_name = str(item.get("icon", "")).strip()
            raw_ts = item.get("timestamp", 0)
            try:
                ts = float(raw_ts or 0)
            except (ValueError, TypeError):
                ts = 0
            if ts > 0:
                meta = f"{app_name} · {self._format_relative_time(ts)}"
            else:
                meta = app_name
            dismiss_btn = QPushButton(material_icon("close"))
            dismiss_btn.setObjectName("notificationCloseButton")
            dismiss_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            dismiss_btn.setFont(QFont(self.material_font, 14))
            dismiss_btn.setFixedSize(18, 18)
            dismiss_btn.setToolTip(t("notif.tooltip.dismiss"))
            dismiss_btn.clicked.connect(
                lambda checked=False, current=dict(item): self._dismiss_notification(
                    current
                )
            )
            self.notifications_layout.addWidget(
                self._list_item_card(
                    title,
                    body,
                    meta,
                    "notifications",
                    self._notification_icon_pixmap(
                        app_name,
                        desktop_entry,
                        icon_name,
                        title,
                        body,
                    ),
                    dismiss_btn,
                )
            )
        self.notifications_layout.addStretch(1)


