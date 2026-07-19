from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout

from notif_center.paths import (
    FALLBACK_COVER, GAMES_CACHE_PATH, LUTRIS_COVERART_DIRS, LUTRIS_DB, LUTRIS_ICON, SCRIPTS_DIR, STEAM_ICON,
)
from notif_center.utils import format_playtime_hours, material_icon, platform_icon_svg_path, render_svg_pixmap, run_cmd
from app_locale import t


def load_cached_game_slides(limit: int = 4) -> list[dict]:
    if limit <= 0:
        return []
    try:
        raw = GAMES_CACHE_PATH.read_text(encoding="utf-8", errors="ignore")
        payload = json.loads(raw or "{}")
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    slides = payload.get("slides", [])
    if not isinstance(slides, list):
        return []
    return [item for item in slides if isinstance(item, dict)][:limit]


def load_cached_games_payload() -> dict:
    try:
        raw = GAMES_CACHE_PATH.read_text(encoding="utf-8", errors="ignore")
        payload = json.loads(raw or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def any_game_running_fast() -> bool:
    needles = ("lutris-wrapper", "lutris-wrapper.sh", "steam_app_", "pressure-vessel", "gamescope")
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            cmdline_path = entry / "cmdline"
            try:
                raw = cmdline_path.read_bytes()
            except Exception:
                continue
            if not raw:
                continue
            text = raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").lower()
            if any(needle in text for needle in needles):
                return True
    except Exception:
        return False
    return False


def load_lutris_game_slides(limit: int = 2) -> list[dict]:
    if not LUTRIS_DB.exists():
        return []
    try:
        connection = sqlite3.connect(LUTRIS_DB)
        cursor = connection.cursor()
        rows = list(
            cursor.execute(
                """
                SELECT name, slug, playtime, lastplayed, runner, platform
                FROM games
                WHERE installed = 1
                ORDER BY lastplayed DESC, playtime DESC
                LIMIT ?
                """,
                (limit,),
            )
        )
    except Exception:
        rows = []
    finally:
        try:
            connection.close()
        except Exception:
            pass
    slides: list[dict] = []
    for name, slug, playtime, lastplayed, runner, platform in rows:
        hours = float(playtime or 0.0)
        platform_label = f"Lutris \u2022 {runner or platform or t('carousel.platform_lutris_label')}"
        cover_path = ""
        if slug:
            for root in LUTRIS_COVERART_DIRS:
                for ext in ("jpg", "png", "jpeg", "webp"):
                    candidate = root / f"{slug}.{ext}"
                    if candidate.is_file():
                        cover_path = str(candidate)
                        break
                if cover_path:
                    break
        slides.append({
            "title": str(name or "Lutris game"), "stats": [format_playtime_hours(hours), str(platform or runner or "Installed")],
            "logo": LUTRIS_ICON, "platform": platform_label, "accent": "primary", "source": "lutris",
            "lutris_slug": str(slug) if slug else "", "playtime_hours": hours, "cover": cover_path,
        })
    return slides


def _candidate_steam_roots() -> list[Path]:
    roots = [
        Path.home() / ".steam",
        Path.home() / ".local" / "share" / "Steam",
        Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
        Path.home() / "snap" / "steam" / "common" / ".local" / "share" / "Steam",
    ]
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def _steam_localconfig_paths() -> list[Path]:
    results: list[Path] = []
    for root in _candidate_steam_roots():
        if not root.exists():
            continue
        results.extend(root.glob("userdata/*/config/localconfig.vdf"))
    return results


def load_steam_game_slides(limit: int = 2) -> list[dict]:
    app_pattern = re.compile(
        r'"(\d+)"\s*\{[^{}]*?"name"\s*"([^"]+)"[^{}]*?"Playtime"\s*"(\d+)"', re.DOTALL
    )
    slides: list[dict] = []
    for config_path in _steam_localconfig_paths():
        try:
            raw = config_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for appid, name, minutes_text in app_pattern.findall(raw):
            minutes = int(minutes_text or "0")
            if minutes <= 0:
                continue
            hours = minutes / 60.0
            slides.append({
                "title": name, "stats": [format_playtime_hours(hours), f"App {appid}"],
                "logo": STEAM_ICON, "platform": "Steam library", "accent": "secondary",
                "source": "steam", "playtime_hours": hours, "cover": "",
            })
        if slides:
            break
    slides.sort(key=lambda item: float(item.get("playtime_hours", 0.0)), reverse=True)
    return slides[:limit]


class GameCarouselCard(QFrame):
    def __init__(self, ui_font: str, material_font: str, panel_bg: str = "rgba(31, 22, 38, 0.94)") -> None:
        super().__init__()
        self.ui_font = ui_font
        self.material_font = material_font
        self._panel_bg = panel_bg
        self._slide_palettes: list[tuple[str, str, str, str] | None] = []
        self.setObjectName("gameCarouselCard")
        self._slides: list[QFrame] = []
        self._dots: list[QLabel] = []
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(5000)
        self._auto_timer.timeout.connect(self.next_slide)
        self._auto_timer.start()

        self.game_base = QFrame(self)
        self.game_base.setObjectName("gameBase")
        self.game_base.lower()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self.kicker = QLabel(t("carousel.recently_played"))
        self.kicker.setObjectName("gameKicker")
        header.addWidget(self.kicker, 1)

        self.play_button = QPushButton(t("btn.play"))
        self.play_button.setObjectName("playButton")
        self.play_button.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.play_button)

        self.prev_button = QPushButton(material_icon("chevron_left"))
        self.prev_button.setObjectName("compactIconAction")
        self.prev_button.setFont(QFont(self.material_font, 17))
        self.prev_button.setFixedSize(28, 28)
        self.prev_button.clicked.connect(self.previous_slide)
        self.next_button = QPushButton(material_icon("chevron_right"))
        self.next_button.setObjectName("compactIconAction")
        self.next_button.setFont(QFont(self.material_font, 17))
        self.next_button.setFixedSize(28, 28)
        self.next_button.clicked.connect(self.next_slide)
        self.prev_button.clicked.connect(self._restart_autoplay)
        self.next_button.clicked.connect(self._restart_autoplay)
        header.addWidget(self.prev_button)
        header.addWidget(self.next_button)
        layout.addLayout(header)

        self.stack = QStackedWidget()
        self.stack.setObjectName("gameStack")
        self.stack.currentChanged.connect(self._on_slide_changed)
        layout.addWidget(self.stack)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(4)
        self.caption = QLabel("")
        self.caption.setObjectName("gameCaption")
        footer.addWidget(self.caption, 1)
        self.dots_wrap = QHBoxLayout()
        self.dots_wrap.setContentsMargins(0, 0, 0, 0)
        self.dots_wrap.setSpacing(4)
        footer.addLayout(self.dots_wrap)
        layout.addLayout(footer)

    def _cover_pixmap(self, path: Path, width: int = 74, height: int = 92) -> QPixmap:
        fallback = QPixmap(width, height)
        fallback.fill(Qt.GlobalColor.transparent)
        candidate = path if path is not None and path.is_file() else FALLBACK_COVER
        if not candidate.exists():
            placeholder = QPixmap(width, height)
            placeholder.fill(QColor(255, 255, 255, 18))
            painter = QPainter(placeholder)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(255, 255, 255, 38))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(0, 0, width - 1, height - 1, 18, 18)
            painter.end()
            return placeholder
        pixmap = QPixmap(str(candidate))
        if pixmap.isNull():
            placeholder = QPixmap(width, height)
            placeholder.fill(QColor(255, 255, 255, 18))
            painter = QPainter(placeholder)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(255, 255, 255, 38))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(0, 0, width - 1, height - 1, 18, 18)
            painter.end()
            return placeholder
        scaled = pixmap.scaled(
            width, height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        cropped = scaled.copy(x, y, width, height)
        rounded = QPixmap(width, height)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0.0, 0.0, float(width), float(height), 18.0, 18.0)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return rounded

    def add_slide(
        self, title: str, stats: list[str], logo_path: Path,
        platform: str, accent: str, cover_path: Path | None = None,
    ) -> None:
        slide = QFrame()
        slide.setObjectName("gameSlideInner")
        slide.setProperty("accentColor", accent)
        slide_layout = QVBoxLayout(slide)
        slide_layout.setContentsMargins(0, 0, 0, 0)
        slide_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        cover = QLabel()
        cover.setObjectName("gameCover")
        cover.setFixedSize(68, 86)
        cover.setPixmap(self._cover_pixmap(cover_path or Path()))
        top.addWidget(cover, 0, Qt.AlignmentFlag.AlignTop)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("gameSlideTitle")
        platform_label = QLabel(platform)
        platform_label.setObjectName("gameSlidePlatform")
        title_wrap.addWidget(title_label)
        title_wrap.addWidget(platform_label)
        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(6)
        stat_values = stats or [t("carousel.no_telemetry")]
        for idx, text in enumerate(stat_values):
            if idx == 1:
                svg_path = platform_icon_svg_path(text)
                icon_pix = render_svg_pixmap(svg_path, 12)
                chip = QFrame()
                chip.setObjectName("gameStatLabel")
                chip_layout = QHBoxLayout(chip)
                chip_layout.setContentsMargins(6, 2, 8, 2)
                chip_layout.setSpacing(4)
                icon_lbl = QLabel()
                icon_lbl.setFixedSize(12, 12)
                if icon_pix and not icon_pix.isNull():
                    icon_lbl.setPixmap(icon_pix)
                text_lbl = QLabel(text)
                chip_layout.addWidget(icon_lbl)
                chip_layout.addWidget(text_lbl)
            else:
                chip = QLabel(text)
                chip.setObjectName("gameStatChip")
            chip_row.addWidget(chip)
        chip_row.addStretch(1)
        title_wrap.addLayout(chip_row)
        top.addLayout(title_wrap, 1)
        slide_layout.addLayout(top)
        slide_layout.addStretch(1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(6)
        hint = QLabel(t("carousel.hint"))
        hint.setObjectName("gameSlideHint")
        bottom.addWidget(hint, 1, Qt.AlignmentFlag.AlignBottom)
        logo = QLabel()
        logo.setObjectName("gamePlatformLogo")
        logo.setPixmap(render_svg_pixmap(logo_path, 22))
        bottom.addWidget(logo, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        slide_layout.addLayout(bottom)

        self.stack.addWidget(slide)
        self._slides.append(slide)
        dot = QLabel("\u2022")
        dot.setObjectName("carouselDot")
        self._dots.append(dot)
        self.dots_wrap.addWidget(dot)
        self._refresh_state()

    def clear_slides(self) -> None:
        for widget in list(getattr(self, "_slides", [])):
            try:
                self.stack.removeWidget(widget)
            except Exception:
                pass
            try:
                widget.deleteLater()
            except Exception:
                pass
        self._slides = []
        for dot in list(getattr(self, "_dots", [])):
            try:
                dot.deleteLater()
            except Exception:
                pass
        self._dots = []
        self._slide_palettes = []
        try:
            self.caption.setText("0/0")
        except Exception:
            pass
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def _refresh_state(self) -> None:
        index = self.stack.currentIndex()
        if index < 0:
            return
        for offset, dot in enumerate(self._dots):
            dot.setProperty("active", offset == index)
            dot.style().unpolish(dot)
            dot.style().polish(dot)
        self.caption.setText(f"{index + 1}/{max(1, self.stack.count())}")
        self.prev_button.setEnabled(self.stack.count() > 1)
        self.next_button.setEnabled(self.stack.count() > 1)

    def next_slide(self) -> None:
        if self.stack.count() < 2:
            return
        self.stack.setCurrentIndex((self.stack.currentIndex() + 1) % self.stack.count())
        self._refresh_state()

    def previous_slide(self) -> None:
        if self.stack.count() < 2:
            return
        self.stack.setCurrentIndex((self.stack.currentIndex() - 1) % self.stack.count())
        self._refresh_state()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.game_base.setGeometry(self.rect())

    def set_slide_palette(
        self, index: int, start: str, end: str, border: str, accent: str
    ) -> None:
        while len(self._slide_palettes) <= index:
            self._slide_palettes.append(None)
        self._slide_palettes[index] = (start, end, border, accent)
        if index == self.stack.currentIndex():
            self._apply_current_palette()

    def _on_slide_changed(self, index: int) -> None:
        self._apply_current_palette()
        self._refresh_state()

    def _apply_current_palette(self) -> None:
        index = self.stack.currentIndex()
        if index < 0 or index >= len(self._slide_palettes):
            return
        palette = self._slide_palettes[index]
        if palette is None:
            self.game_base.setStyleSheet(
                f"background: {self._panel_bg}; border-radius: 20px;"
            )
            return
        start, end, _border, _accent = palette
        self.game_base.setStyleSheet(
            f"""
            background: qradialgradient(
                cx: 0.36, cy: 0.26, radius: 0.95, fx: 0.36, fy: 0.26,
                stop: 0 {start},
                stop: 0.38 {end},
                stop: 1 {self._panel_bg}
            );
            border-radius: 20px;
            """
        )

    def _restart_autoplay(self) -> None:
        if self.stack.count() < 2:
            return
        self._auto_timer.start()
