from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_locale import t
from notif_center.utils import material_icon


def _calendar_event_meta(event: dict) -> str:
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


def show_calendar_day_events(
    parent,
    date,
    events,
    material_font,
    ui_font,
    theme_palette,
    on_open_url,
    on_dismiss,
):
    dialog = QDialog(parent)
    dialog.setWindowTitle(t("dialog.calendar_events"))
    dialog.setModal(False)
    dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    dialog.setStyleSheet(parent.styleSheet())

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
    close_button.setFont(QFont(material_font, 16))
    close_button.setFixedSize(26, 26)
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
        meta = QLabel(_calendar_event_meta(event))
        meta.setObjectName("feedCardMeta")
        item_layout.addWidget(event_title)
        item_layout.addWidget(meta)

        location = str(event.get("location", "")).strip()
        source = str(event.get("source", "")).strip()
        detail_parts = [part for part in (location, source) if part]
        if detail_parts:
            details = QLabel(" \u2022 ".join(detail_parts))
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
        parent.geometry().center().x() - dialog.width() // 2,
        parent.geometry().center().y() - dialog.height() // 2,
    )
    dialog.show()
    return dialog
