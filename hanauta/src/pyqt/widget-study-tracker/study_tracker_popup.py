#!/usr/bin/env python3
from __future__ import annotations

import json
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    QTimer,
    Qt,
    QRect,
    QByteArray,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QIcon,
    QPaintEvent,
    QPainter,
    QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.button_helpers import create_close_button
from pyqt.shared.runtime import entry_command
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba

FONTS_DIR = ROOT / "assets" / "fonts"
SETTINGS_FILE = (
    Path.home()
    / ".local"
    / "state"
    / "hanauta"
    / "notification-center"
    / "settings.json"
)
STUDY_STATE_FILE = (
    Path.home() / ".local" / "state" / "hanauta" / "study-tracker" / "state.json"
)
STUDY_TRACKER_APP = APP_DIR / "pyqt" / "study-tracker" / "study_tracker.py"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"

STUDY_ICONS_DIR = ROOT / "assets" / "study-tracker-icons"

MATERIAL_ICONS = {
    "menu_book": STUDY_ICONS_DIR / "menu_book.svg",
    "close": STUDY_ICONS_DIR / "close.svg",
    "timer": STUDY_ICONS_DIR / "timer.svg",
    "favorite": STUDY_ICONS_DIR / "favorite.svg",
    "task_alt": STUDY_ICONS_DIR / "task_alt.svg",
    "school": STUDY_ICONS_DIR / "school.svg",
    "settings": STUDY_ICONS_DIR / "settings.svg",
    "open_in_new": STUDY_ICONS_DIR / "open_in_new.svg",
    "expand_more": STUDY_ICONS_DIR / "expand_more.svg",
    "play_circle": STUDY_ICONS_DIR / "play_circle.svg",
    "auto_awesome": STUDY_ICONS_DIR / "auto_awesome.svg",
    "schedule": STUDY_ICONS_DIR / "schedule.svg",
}

MATERIAL_GLYPHS = {
    "menu_book": "\uead9",
    "close": "\ue5cd",
    "timer": "\ue425",
    "favorite": "\ue87d",
    "task_alt": "\ue2e6",
    "school": "\ue80c",
    "settings": "\ue8b8",
    "open_in_new": "\ue89e",
    "expand_more": "\ue5cf",
    "play_circle": "\ue1c4",
    "auto_awesome": "\ue65f",
    "schedule": "\ue8b5",
}


def load_svg_icon(name: str, color: QColor, size: int = 20) -> QIcon:
    path = MATERIAL_ICONS.get(name)
    if not path or not path.exists():
        return QIcon()
    renderer = QSvgRenderer()
    try:
        raw_svg = path.read_text(encoding="utf-8")
    except OSError:
        return QIcon()
    if raw_svg:
        normalized = raw_svg.replace("currentColor", color.name())
        renderer.load(QByteArray(normalized.encode("utf-8")))
    else:
        renderer.load(str(path))
    if not renderer.isValid():
        return QIcon()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def material_icon(name: str) -> str:
    return MATERIAL_GLYPHS.get(name, "")


def load_material_glyph_icon(
    name: str,
    color: QColor,
    size: int,
    icon_font_family: str,
) -> QIcon:
    glyph = material_icon(name)
    if not glyph or not icon_font_family:
        return QIcon()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(color)
    font = QFont(icon_font_family, max(10, int(size * 0.82)))
    painter.setFont(font)
    painter.drawText(QRect(0, 0, size, size), int(Qt.AlignmentFlag.AlignCenter), glyph)
    painter.end()
    return QIcon(pixmap)


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "ui_display": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
    }
    for key, path in font_map.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def run_bg(cmd: list[str]) -> None:
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def load_settings_payload() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def study_service_enabled() -> bool:
    services = load_settings_payload().get("services", {})
    if not isinstance(services, dict):
        return False
    current = services.get("study_tracker_widget", {})
    return isinstance(current, dict) and bool(current.get("enabled", False))


def load_study_state() -> dict:
    try:
        payload = json.loads(STUDY_STATE_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def compute_streak_days(state: dict) -> int:
    values = sorted(
        {str(item) for item in state.get("activity_dates", []) if str(item).strip()},
        reverse=True,
    )
    if not values:
        return 0
    streak = 0
    cursor = datetime.now().date()
    value_set = set(values)
    while cursor.isoformat() in value_set:
        streak += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
    return streak


def active_task(state: dict) -> dict | None:
    tasks = state.get("tasks", [])
    if not isinstance(tasks, list):
        return None
    for task in tasks:
        if isinstance(task, dict) and task.get("active") and not task.get("done"):
            return task
    for task in tasks:
        if isinstance(task, dict) and not task.get("done"):
            return task
    return None


def upcoming_blocks(state: dict, limit: int = 3) -> list[dict]:
    now = datetime.now()
    blocks = state.get("schedule_blocks", [])
    if not isinstance(blocks, list):
        return []
    parsed: list[tuple[datetime, dict]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        date_text = str(block.get("date", "")).strip()
        start_text = str(block.get("start_time", "08:00")).strip() or "08:00"
        try:
            dt = datetime.strptime(f"{date_text} {start_text}", "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if dt >= now:
            parsed.append((dt, block))
    parsed.sort(key=lambda item: item[0])
    return [item[1] for item in parsed[:limit]]


def format_minutes(value: int) -> str:
    minutes = max(0, int(value or 0))
    if minutes >= 60:
        hours, rem = divmod(minutes, 60)
        if rem == 0:
            return f"{hours}h"
        return f"{hours}h {rem}m"
    return f"{minutes}m"


def build_stats_snapshot() -> dict[str, str | int | list[str]]:
    state = load_study_state()
    task = active_task(state)
    today_minutes = max(0, int(state.get("today_minutes", 0) or 0))
    streak_days = compute_streak_days(state)
    tasks = state.get("tasks", []) if isinstance(state.get("tasks"), list) else []
    done_count = sum(
        1 for item in tasks if isinstance(item, dict) and bool(item.get("done", False))
    )
    total_count = sum(1 for item in tasks if isinstance(item, dict))
    if isinstance(task, dict):
        completed = max(0, int(task.get("sessions_completed", 0) or 0))
        target = max(1, int(task.get("target_sessions", 1) or 1))
        progress_pct = max(0, min(100, int((completed / target) * 100)))
        focus_title = str(task.get("title", "Focused Study")).strip() or "Focused Study"
        focus_meta = f"{completed}/{target} sessions"
    else:
        progress_pct = 0
        focus_title = "No active plan"
        focus_meta = "Create a task in Study Tracker"

    session = (
        state.get("active_session", {})
        if isinstance(state.get("active_session"), dict)
        else {}
    )
    running = bool(session.get("running", False))
    elapsed_seconds = max(0, int(session.get("elapsed_seconds", 0) or 0))
    target_seconds = max(1, int(session.get("target_seconds", 25 * 60) or 25 * 60))
    session_text = (
        f"Live focus: {format_minutes(elapsed_seconds // 60)} / {format_minutes(target_seconds // 60)}"
        if running
        else "No live timer running"
    )

    blocks = upcoming_blocks(state)
    block_lines: list[str] = []
    for block in blocks:
        title = str(block.get("title", "Study block") or "Study block")
        date_text = str(block.get("date", "")).strip()
        time_text = str(block.get("start_time", "08:00")).strip() or "08:00"
        label = title
        try:
            when = datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")
            label = f"{when.strftime('%a %H:%M')} • {title}"
        except Exception:
            pass
        block_lines.append(label)

    if not block_lines:
        block_lines = ["No upcoming scheduled study blocks"]

    return {
        "today_minutes": today_minutes,
        "streak_days": streak_days,
        "done_count": done_count,
        "total_count": total_count,
        "focus_title": focus_title,
        "focus_meta": focus_meta,
        "progress_pct": progress_pct,
        "session_text": session_text,
        "block_lines": block_lines,
    }


class MetricCard(QFrame):
    def __init__(
        self,
        icon_name: str,
        title: str,
        value: str,
        icon_font: str,
        ui_font: str,
        display_font: str,
        state: str = "idle",
    ) -> None:
        super().__init__()
        self.setObjectName("studyMetricCard")
        self._icon_name = icon_name
        self._icon_font = icon_font
        self._ui_font = ui_font
        self._display_font = display_font
        self._state = state
        self._is_hovered = False
        self._hover_opacity = 0.0
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(88)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        layout.addWidget(self.icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("studyMetricTitle")
        title_label.setFont(QFont(ui_font, 10, QFont.Weight.Medium))
        layout.addWidget(title_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("studyMetricValue")
        self.value_label.setFont(QFont(display_font, 14, QFont.Weight.DemiBold))
        layout.addWidget(self.value_label)

    def set_icon(self, icon: QIcon) -> None:
        self.icon_label.setPixmap(icon.pixmap(24, 24))

    def set_icon_by_name(self, name: str, color: QColor, icon_font: str) -> None:
        self._icon_name = name
        icon = load_material_glyph_icon(name, color, 20, icon_font)
        if icon.isNull():
            icon = load_svg_icon(name, color, 20)
        self.set_icon(icon)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)

    def set_state(self, state: str) -> None:
        self._state = state

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def _animate_hover(self, target: float) -> None:
        self._hover_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(target)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.start()
        self._hover_opacity = target
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self._hover_opacity > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            color = QColor(255, 255, 255, int(12 * self._hover_opacity))
            painter.fillRect(self.rect(), color)


class StudyTrackerPopup(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._fade: QPropertyAnimation | None = None

        self.ui_font = detect_font(
            self.loaded_fonts.get("ui_sans", ""),
            "Rubik",
            "Inter",
            "Noto Sans",
            "Sans Serif",
        )
        self.display_font = detect_font(
            self.loaded_fonts.get("ui_display", ""), "Rubik", self.ui_font
        )
        self.icon_font = detect_font(
            self.loaded_fonts.get("material_icons", ""),
            self.loaded_fonts.get("material_symbols_rounded", ""),
            "Material Icons",
            "Material Symbols Rounded",
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("Hanauta Study Tracker")
        self.setFixedSize(460, 520)
        self._focus_title_raw = "No active plan"
        self._focus_meta_raw = "Create a task in Study Tracker"
        self._session_text_raw = "No live timer running"
        self._agenda_raw: list[str] = ["No upcoming scheduled study blocks", "", ""]
        self._study_state = "idle"

        self._build_ui()
        self._apply_styles()
        self._apply_icons()
        self._apply_shadow()
        self._place_window()
        self._animate_in()
        self._refresh()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh)
        self.refresh_timer.start(5000)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        panel = QFrame()
        panel.setObjectName("studyShell")
        root.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.header_icon = QLabel()
        self.header_icon.setFixedSize(28, 28)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(1)
        title = QLabel("Study Tracker")
        title.setObjectName("studyTitle")
        title.setFont(QFont(self.display_font, 15, QFont.Weight.DemiBold))
        subtitle = QLabel("Focus sessions, tasks & schedule")
        subtitle.setObjectName("studySubtitle")
        subtitle.setFont(QFont(self.ui_font, 10))
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        close_button = QPushButton()
        close_button.setObjectName("studyCloseButton")
        close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_button.setFixedSize(36, 36)
        close_button.clicked.connect(self.close)
        header.addWidget(self.header_icon)
        header.addLayout(title_wrap, 1)
        header.addWidget(close_button)
        layout.addLayout(header)

        self.hero_card = QFrame()
        self.hero_card.setObjectName("studyEntityCard")
        self.hero_card.setFixedHeight(148)
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.status_icon = QLabel()
        self.status_icon.setFixedSize(24, 24)
        header_row.addWidget(self.status_icon)

        self.status_pill = QLabel("Ready")
        self.status_pill.setObjectName("studyStatusPill")
        self.status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_pill.setFixedHeight(28)
        header_row.addWidget(self.status_pill, 1, Qt.AlignmentFlag.AlignLeft)

        self.expand_indicator = QLabel()
        self.expand_indicator.setFixedSize(24, 24)
        self.expand_indicator.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header_row.addWidget(self.expand_indicator)
        hero_layout.addLayout(header_row)

        self.focus_title = QLabel("No active plan")
        self.focus_title.setObjectName("studyFocusTitle")
        self.focus_title.setFont(QFont(self.display_font, 14, QFont.Weight.Medium))
        self.focus_title.setWordWrap(False)
        hero_layout.addWidget(self.focus_title)

        self.focus_meta = QLabel("Create a task in Study Tracker")
        self.focus_meta.setObjectName("studyFocusMeta")
        self.focus_meta.setFont(QFont(self.ui_font, 10))
        self.focus_meta.setWordWrap(False)
        hero_layout.addWidget(self.focus_meta)

        self.progress_track = QFrame()
        self.progress_track.setObjectName("studyProgressTrack")
        self.progress_track.setFixedHeight(8)
        progress_layout = QVBoxLayout(self.progress_track)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_fill = QFrame(self.progress_track)
        self.progress_fill.setObjectName("studyProgressFill")
        self.progress_fill.setGeometry(0, 0, 1, 8)
        hero_layout.addWidget(self.progress_track)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.session_icon = QLabel()
        self.session_icon.setFixedSize(16, 16)
        bottom_row.addWidget(self.session_icon)

        self.session_label = QLabel("No live timer running")
        self.session_label.setObjectName("studySessionLabel")
        self.session_label.setFont(QFont(self.ui_font, 10, QFont.Weight.Medium))
        self.session_label.setWordWrap(False)
        bottom_row.addWidget(self.session_label, 1)
        hero_layout.addLayout(bottom_row)

        layout.addWidget(self.hero_card)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self.today_card = MetricCard(
            "timer",
            "Today",
            "0m",
            self.icon_font,
            self.ui_font,
            self.display_font,
            "active",
        )
        self.streak_card = MetricCard(
            "favorite",
            "Streak",
            "0 days",
            self.icon_font,
            self.ui_font,
            self.display_font,
            "idle",
        )
        self.tasks_card = MetricCard(
            "task_alt",
            "Tasks",
            "0 / 0",
            self.icon_font,
            self.ui_font,
            self.display_font,
            "idle",
        )
        metrics.addWidget(self.today_card, 1)
        metrics.addWidget(self.streak_card, 1)
        metrics.addWidget(self.tasks_card, 1)
        layout.addLayout(metrics)

        self.agenda_card = QFrame()
        self.agenda_card.setObjectName("studyAgendaCard")
        self.agenda_card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        agenda_layout = QVBoxLayout(self.agenda_card)
        agenda_layout.setContentsMargins(14, 12, 14, 12)
        agenda_layout.setSpacing(6)

        agenda_header = QHBoxLayout()
        agenda_header.setSpacing(8)

        self.agenda_icon = QLabel()
        self.agenda_icon.setFixedSize(20, 20)
        agenda_header.addWidget(self.agenda_icon)

        agenda_title = QLabel("Upcoming Study Blocks")
        agenda_title.setObjectName("studyAgendaTitle")
        agenda_title.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        agenda_header.addWidget(agenda_title, 1)

        self.agenda_count = QLabel("")
        self.agenda_count.setObjectName("studyAgendaCount")
        self.agenda_count.setFont(QFont(self.ui_font, 9, QFont.Weight.Medium))
        agenda_header.addWidget(self.agenda_count)
        agenda_layout.addLayout(agenda_header)

        self.agenda_line_1 = QLabel("No upcoming scheduled study blocks")
        self.agenda_line_1.setObjectName("studyAgendaLine")
        self.agenda_line_1.setFont(QFont(self.ui_font, 10))
        self.agenda_line_1.setWordWrap(False)
        self.agenda_line_2 = QLabel("")
        self.agenda_line_2.setObjectName("studyAgendaLine")
        self.agenda_line_2.setFont(QFont(self.ui_font, 10))
        self.agenda_line_2.setWordWrap(False)
        self.agenda_line_3 = QLabel("")
        self.agenda_line_3.setObjectName("studyAgendaLine")
        self.agenda_line_3.setFont(QFont(self.ui_font, 10))
        self.agenda_line_3.setWordWrap(False)
        agenda_layout.addWidget(self.agenda_line_1)
        agenda_layout.addWidget(self.agenda_line_2)
        agenda_layout.addWidget(self.agenda_line_3)
        layout.addWidget(self.agenda_card)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        open_button = QPushButton("Open Tracker")
        open_button.setObjectName("studyPrimaryButton")
        open_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_button.setMinimumHeight(42)
        open_button.setFont(QFont(self.ui_font, 11, QFont.Weight.DemiBold))
        open_button.clicked.connect(self._open_tracker)

        self.settings_button = QPushButton()
        self.settings_button.setObjectName("studySecondaryButton")
        self.settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.settings_button.setFixedSize(42, 42)
        self.settings_button.clicked.connect(self._open_settings)
        actions.addWidget(open_button, 1)
        actions.addWidget(self.settings_button)
        layout.addLayout(actions)

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(44)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(4, 8, 18, 190))
        self.setGraphicsEffect(shadow)

    def _apply_icons(self) -> None:
        primary = QColor(self.theme.primary)

        header_icon = load_material_glyph_icon("menu_book", primary, 28, self.icon_font)
        if header_icon.isNull():
            header_icon = load_svg_icon("menu_book", primary, 28)
        self.header_icon.setPixmap(header_icon.pixmap(28, 28))

        close_icon = load_material_glyph_icon("close", QColor(self.theme.text), 18, self.icon_font)
        if close_icon.isNull():
            close_icon = load_svg_icon("close", QColor(self.theme.text), 18)
        close_btn = self.findChild(QPushButton, "studyCloseButton")
        close_btn.setIcon(close_icon)
        avail = close_icon.availableSizes()
        close_btn.setIconSize(
            close_icon.actualSize(avail[0] if avail else QSize(18, 18))
        )

        agenda_icon = load_material_glyph_icon("schedule", primary, 20, self.icon_font)
        if agenda_icon.isNull():
            agenda_icon = load_svg_icon("schedule", primary, 20)
        self.agenda_icon.setPixmap(agenda_icon.pixmap(20, 20))
        settings_icon = load_material_glyph_icon("settings", QColor(self.theme.text), 20, self.icon_font)
        if settings_icon.isNull():
            settings_icon = load_svg_icon("settings", QColor(self.theme.text), 20)
        self.settings_button.setIcon(settings_icon)
        avail = settings_icon.availableSizes()
        self.settings_button.setIconSize(
            settings_icon.actualSize(avail[0] if avail else QSize(20, 20))
        )

        self._update_status_icon()

    def _update_status_icon(self) -> None:
        primary = QColor(self.theme.primary)
        status_icon = load_material_glyph_icon("school", primary, 24, self.icon_font)
        if status_icon.isNull():
            status_icon = load_svg_icon("school", primary, 24)
        self.status_icon.setPixmap(status_icon.pixmap(24, 24))

        expand_icon = load_material_glyph_icon("expand_more", primary, 24, self.icon_font)
        if expand_icon.isNull():
            expand_icon = load_svg_icon("expand_more", primary, 24)
        self.expand_indicator.setPixmap(expand_icon.pixmap(24, 24))

        timer_icon = load_material_glyph_icon("timer", primary, 16, self.icon_font)
        if timer_icon.isNull():
            timer_icon = load_svg_icon("timer", primary, 16)
        self.session_icon.setPixmap(timer_icon.pixmap(16, 16))

        self.today_card.set_icon_by_name("timer", primary, self.icon_font)
        self.streak_card.set_icon_by_name("favorite", primary, self.icon_font)
        self.tasks_card.set_icon_by_name("task_alt", primary, self.icon_font)

    def _place_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        margin = 18
        x = geo.x() + geo.width() - self.width() - margin
        y = geo.y() + 58
        self.move(x, y)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _reload_theme_if_needed(self) -> None:
        current = palette_mtime()
        if current == self._theme_mtime:
            return
        self._theme_mtime = current
        self.theme = load_theme_palette()
        self._apply_styles()
        self._apply_icons()

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: \"{self.ui_font}\";
            }}
            QFrame#studyShell {{
                background: {rgba(theme.surface_container, 0.97)};
                border: 1px solid {rgba(theme.outline, 0.18)};
                border-radius: 20px;
            }}
            QLabel#studyTitle {{ color: {theme.text}; }}
            QLabel#studySubtitle {{ color: {theme.text_muted}; }}
            QPushButton#studyCloseButton {{
                background: {rgba(theme.surface_container_high, 0.70)};
                border: none;
                border-radius: 18px;
            }}
            QPushButton#studyCloseButton:hover {{
                background: {rgba(theme.error, 0.15)};
            }}
            QFrame#studyEntityCard {{
                background: {theme.surface_container_high};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 16px;
            }}
            QFrame#studyEntityCard:hover {{
                border-color: {rgba(theme.primary, 0.30)};
            }}
            QLabel#studyStatusPill {{
                color: {theme.primary};
                background: {rgba(theme.primary, 0.12)};
                border: none;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 10px;
                font-weight: 600;
            }}
            QLabel#studyFocusTitle {{ color: {theme.text}; }}
            QLabel#studyFocusMeta {{ color: {theme.text_muted}; font-size: 11px; }}
            QLabel#studySessionLabel {{ color: {theme.secondary}; font-size: 10px; }}
            QFrame#studyProgressTrack {{
                background: {rgba(theme.surface, 0.60)};
                border: none;
                border-radius: 4px;
            }}
            QFrame#studyProgressFill {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {theme.primary},
                    stop:1 {theme.tertiary}
                );
                border-radius: 4px;
            }}
            QFrame#studyMetricCard {{
                background: {theme.surface_container_high};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 14px;
            }}
            QFrame#studyMetricCard:hover {{
                border-color: {rgba(theme.primary, 0.25)};
            }}
            QLabel#studyMetricTitle {{ color: {theme.text_muted}; font-size: 10px; }}
            QLabel#studyMetricValue {{ color: {theme.text}; font-size: 15px; font-weight: 600; }}
            QFrame#studyAgendaCard {{
                background: {theme.surface_container_high};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 14px;
            }}
            QFrame#studyAgendaCard:hover {{
                border-color: {rgba(theme.primary, 0.25)};
            }}
            QLabel#studyAgendaTitle {{ color: {theme.text}; font-size: 11px; }}
            QLabel#studyAgendaCount {{
                color: {theme.primary};
                background: {rgba(theme.primary, 0.10)};
                border-radius: 10px;
                padding: 2px 8px;
                font-size: 9px;
                font-weight: 600;
            }}
            QLabel#studyAgendaLine {{ color: {theme.text_muted}; font-size: 11px; }}
            QPushButton#studyPrimaryButton {{
                color: {theme.active_text};
                background-color: {theme.primary};
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {theme.primary},
                    stop:1 {theme.tertiary}
                );
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 700;
            }}
            QPushButton#studyPrimaryButton:hover {{
                background-color: {rgba(theme.primary, 0.92)};
            }}
            QPushButton#studyPrimaryButton:pressed {{
                background-color: {rgba(theme.primary, 0.78)};
            }}
            QPushButton#studySecondaryButton {{
                color: {theme.text};
                background: {theme.surface_container_high};
                border: 1px solid {rgba(theme.outline, 0.14)};
                border-radius: 12px;
                font-family: \"{self.icon_font}\";
            }}
            QPushButton#studySecondaryButton:hover {{
                background: {theme.hover_bg};
                border-color: {rgba(theme.primary, 0.20)};
            }}
            """
        )

    def _set_progress_percent(self, percent: int) -> None:
        width = max(1, self.progress_track.width())
        fill = max(1, int(width * (max(0, min(100, percent)) / 100.0)))
        self.progress_fill.setGeometry(0, 0, fill, self.progress_track.height())

    def _clean_line(self, value: str) -> str:
        return " ".join(str(value).replace("\n", " ").split())

    def _set_elided_label(self, label: QLabel, text: str, pad: int = 8) -> None:
        cleaned = self._clean_line(text)
        width = max(60, label.width() - pad)
        metrics = QFontMetrics(label.font())
        elided = metrics.elidedText(cleaned, Qt.TextElideMode.ElideRight, width)
        label.setText(elided)
        label.setToolTip(cleaned if elided != cleaned else "")

    def _apply_elided_texts(self) -> None:
        self._set_elided_label(self.focus_title, self._focus_title_raw)
        self._set_elided_label(self.focus_meta, self._focus_meta_raw)
        self._set_elided_label(self.session_label, self._session_text_raw)
        rows = (self._agenda_raw + ["", ""])[:3]
        labels = (self.agenda_line_1, self.agenda_line_2, self.agenda_line_3)
        for index, label in enumerate(labels):
            raw = rows[index]
            self._set_elided_label(label, raw)
            label.setVisible(bool(raw))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._set_progress_percent(int(self.progress_fill.property("percent") or 0))
        self._apply_elided_texts()

    def _refresh(self) -> None:
        stats = build_stats_snapshot()
        self.today_card.set_value(format_minutes(int(stats["today_minutes"])))
        streak = int(stats["streak_days"])
        self.streak_card.set_value(f"{streak}d")
        self.tasks_card.set_value(
            f"{int(stats['done_count'])}/{int(stats['total_count'])}"
        )

        focus_title = self._clean_line(str(stats["focus_title"]))
        focus_meta = self._clean_line(str(stats["focus_meta"]))
        progress_pct = int(stats["progress_pct"])
        block_lines = (
            list(stats["block_lines"]) if isinstance(stats["block_lines"], list) else []
        )
        session_text = self._clean_line(str(stats["session_text"]))

        self._focus_title_raw = focus_title
        self._focus_meta_raw = focus_meta
        self._session_text_raw = session_text

        pill_text = "Ready"
        session_running = "Live focus" in session_text
        if session_running:
            pill_text = "Live Session"
            self._study_state = "active"
            icon = load_material_glyph_icon("play_circle", QColor(self.theme.primary), 24, self.icon_font)
            if icon.isNull():
                icon = load_svg_icon("play_circle", QColor(self.theme.primary), 24)
            self.status_icon.setPixmap(icon.pixmap(24, 24))
        elif progress_pct > 0:
            pill_text = "In Progress"
            self._study_state = "active"
            icon = load_material_glyph_icon("auto_awesome", QColor(self.theme.primary), 24, self.icon_font)
            if icon.isNull():
                icon = load_svg_icon("auto_awesome", QColor(self.theme.primary), 24)
            self.status_icon.setPixmap(icon.pixmap(24, 24))
        else:
            self._study_state = "idle"
            icon = load_material_glyph_icon("school", QColor(self.theme.primary), 24, self.icon_font)
            if icon.isNull():
                icon = load_svg_icon("school", QColor(self.theme.primary), 24)
            self.status_icon.setPixmap(icon.pixmap(24, 24))

        self.status_pill.setText(pill_text)

        self.progress_fill.setProperty("percent", progress_pct)
        self._set_progress_percent(progress_pct)

        self._agenda_raw = [self._clean_line(str(line)) for line in block_lines[:3]]
        self._apply_elided_texts()

        block_count = len([l for l in block_lines if l and "No upcoming" not in l])
        self.agenda_count.setText(f"{block_count}" if block_count > 0 else "")
        self.agenda_count.setVisible(block_count > 0)

    def _open_tracker(self) -> None:
        if not STUDY_TRACKER_APP.exists():
            return
        command = entry_command(STUDY_TRACKER_APP)
        if command:
            run_bg(command)

    def _open_settings(self) -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        command = entry_command(
            SETTINGS_PAGE_SCRIPT,
            "--page",
            "services",
            "--service-section",
            "study_tracker_widget",
        )
        if command:
            run_bg(command)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        app = QApplication.instance()
        if app is not None:
            app.quit()
        super().closeEvent(event)


def main() -> int:
    if not study_service_enabled():
        return 0
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    widget = StudyTrackerPopup()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
