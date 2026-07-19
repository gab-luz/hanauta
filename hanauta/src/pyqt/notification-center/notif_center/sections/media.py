from __future__ import annotations

from PyQt6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, QTimer, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTextCharFormat, QPalette
from PyQt6.QtWidgets import QApplication, QButtonGroup, QDialog, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget, QVBoxLayout, QWidget

from app_locale import t
from notif_center.ha import *
from notif_center.game_carousel import *
from notif_center.paths import *
from notif_center.poller import *
from notif_center.settings_io import *
from notif_center.color_utils import darken_hex, extract_cover_palette, hex_to_rgba
from notif_center.utils import *
from notif_center.widgets import *
from pyqt.shared.calendar_card import *
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family
from pyqt.shared.runtime import entry_command, entry_patterns, python_executable


class MediaMetadataWorker(QThread):
    metadata_ready = pyqtSignal(object)
    _busy = False

    def __init__(self, parent=None):
        super().__init__(parent)

    def start_fetch(self):
        if MediaMetadataWorker._busy:
            return
        MediaMetadataWorker._busy = True
        self.start()

    def run(self):
        try:
            title = run_script("mpris.sh", "title") or t("media.no_music")
            artist = run_script("mpris.sh", "artist") or t("media.no_artist")
            status = run_script("mpris.sh", "status") or "Stopped"
            player = run_script("mpris.sh", "player")
            art = run_script("mpris.sh", "coverloc")
            media_url = ""
            if player:
                media_url = run_cmd([
                    "playerctl", f"--player={player}", "metadata",
                    "--format", "{{xesam:url}}",
                ])
            result = {
                "title": title,
                "artist": artist,
                "status": status,
                "player": player,
                "art": art,
                "media_url": media_url,
            }
        except Exception:
            result = {
                "title": t("media.no_music"),
                "artist": t("media.no_artist"),
                "status": "Stopped",
                "player": "",
                "art": "",
                "media_url": "",
            }
        finally:
            MediaMetadataWorker._busy = False
        self.metadata_ready.emit(result)


class CoverPaletteWorker(QThread):
    palette_ready = pyqtSignal(object)
    _busy = False

    def __init__(self, parent=None):
        super().__init__(parent)

    def start_extract(self, cover_path):
        if CoverPaletteWorker._busy:
            return
        CoverPaletteWorker._busy = True
        self._cover_path = cover_path
        self.start()

    def run(self):
        try:
            palette = extract_cover_palette(self._cover_path)
        except Exception:
            palette = None
        finally:
            CoverPaletteWorker._busy = False
        self.palette_ready.emit(palette)


class MediaMixin:
    """Media card and playback methods for NotificationCenter."""

    def _build_media_card(self) -> QFrame:
        self.media_card = QFrame()
        self.media_card.setObjectName("mediaCard")
        self.media_card.setMinimumHeight(120)
        self.media_base = QFrame(self.media_card)
        self.media_base.setObjectName("mediaBase")
        self.media_scrim = QFrame(self.media_card)
        self.media_scrim.setObjectName("mediaScrim")
        self.media_scrim.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.media_content = QWidget(self.media_card)
        self.media_content.setObjectName("mediaContent")

        layout = QVBoxLayout(self.media_content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)

        self.cover = QLabel()
        self.cover.setObjectName("cover")
        self.cover.setFixedSize(48, 48)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_wrap = QWidget()
        text_wrap.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        text = QVBoxLayout(text_wrap)
        text.setContentsMargins(0, 2, 0, 0)
        text.setSpacing(2)
        self.media_title = QLabel(t("media.no_music"))
        self.media_title.setObjectName("mediaTitle")
        self.media_title.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.media_title.setMinimumWidth(1)
        self.media_title.setWordWrap(False)
        self.media_artist = QLabel(t("media.no_artist"))
        self.media_artist.setObjectName("mediaArtist")
        self.media_artist.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.media_artist.setMinimumWidth(1)
        self.media_artist.setWordWrap(False)
        text.addWidget(self.media_title)
        text.addWidget(self.media_artist)
        text.addStretch(1)

        top.addWidget(self.cover)
        top.addWidget(text_wrap, 1)
        layout.addLayout(top)

        self.progress_track = QFrame()
        self.progress_track.setObjectName("progressTrack")
        self.progress_fill = QFrame(self.progress_track)
        self.progress_fill.setObjectName("progressFill")
        self.progress_fill.setGeometry(0, 0, 0, 4)
        self.progress_track.setFixedHeight(4)
        layout.addWidget(self.progress_track)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        self.elapsed = QLabel("0:00")
        self.elapsed.setObjectName("timeCode")
        self.elapsed.setFont(QFont(self.mono_font, 9))
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        self.prev_btn = self._plain_icon_button("skip_previous")
        self.prev_btn.clicked.connect(lambda: self._trigger_media_action("--previous"))
        self.play_btn = self._circle_icon_button("pause", accent="play")
        self.play_btn.clicked.connect(lambda: self._trigger_media_action("--toggle"))
        self.next_btn = self._plain_icon_button("skip_next")
        self.next_btn.clicked.connect(lambda: self._trigger_media_action("--next"))
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.next_btn)
        self.total = QLabel("0:00")
        self.total.setObjectName("timeCode")
        self.total.setFont(QFont(self.mono_font, 9))
        self.total.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        bottom.addWidget(self.elapsed)
        bottom.addStretch(1)
        bottom.addLayout(controls)
        bottom.addStretch(1)
        bottom.addWidget(self.total)
        layout.addLayout(bottom)
        self._sync_media_card_layers()
        return self.media_card


    def _init_media_workers(self):
        self._media_metadata_worker = MediaMetadataWorker(self)
        self._media_metadata_worker.metadata_ready.connect(self._on_media_metadata_done)
        self._cover_palette_worker = CoverPaletteWorker(self)
        self._cover_palette_worker.palette_ready.connect(self._on_cover_palette_done)

    def _poll_media_metadata(self, force_refresh: bool = False) -> None:
        if not hasattr(self, "media_title"):
            return
        if force_refresh:
            if not hasattr(self, "_media_metadata_worker"):
                self._init_media_workers()
            self._media_metadata_worker.start_fetch()
            return
        r = self._poll_result
        if r is None:
            return
        title = r.media_title or t("media.no_music")
        artist = r.media_artist or t("media.no_artist")
        status = r.media_status or "Stopped"
        player = r.media_player
        art = r.media_art
        media_url = r.media_url
        self._media_player = player
        self._media_status = status
        self._media_url = media_url
        self._apply_media_meta(title, artist, status, player, art, media_url)

    def _on_media_metadata_done(self, result):
        title = result["title"]
        artist = result["artist"]
        status = result["status"]
        player = result["player"]
        art = result["art"]
        media_url = result["media_url"]
        self._media_player = player
        self._media_status = status
        self._media_last_sync = monotonic()
        self._media_url = media_url
        self._apply_media_meta(title, artist, status, player, art, media_url)

    def _apply_media_meta(self, title, artist, status, player, art, media_url):
        self.media_title.setText(title)
        self.media_artist.setText(artist)
        self.media_title.setVisible(True)
        self.media_artist.setVisible(True)
        self.media_title.updateGeometry()
        self.media_artist.updateGeometry()
        self.media_title.repaint()
        self.media_artist.repaint()
        self.play_btn.setText(
            material_icon("pause" if status == "Playing" else "play_arrow")
        )

        track_key = f"{title}|{artist}"
        if track_key != self._media_track_key:
            self._media_track_key = track_key
            self._media_position_ms = 0
            self._media_duration_ms = 0
            self._media_estimated_progress = False
            self._render_media_progress()
            if self._is_browser_player(player) and media_url:
                self._request_media_url_duration(media_url)
            cover_path = Path(art) if art else FALLBACK_COVER
            if not cover_path.exists():
                cover_path = FALLBACK_COVER
            self._set_cover_art(cover_path)
            self._update_media_palette_from_cover(cover_path)


    def _is_browser_player(self, player: str) -> bool:
        lowered = player.lower()
        return any(
            name in lowered
            for name in (
                "firefox",
                "librewolf",
                "chromium",
                "brave",
                "chrome",
                "vivaldi",
            )
        )


    def _duration_ms_from_media_url(self, url: str) -> int | None:
        url = url.strip()
        if not url:
            return None
        cached = self._media_duration_cache.get(url)
        if cached is not None:
            return cached
        duration_raw = run_cmd(
            [
                "yt-dlp",
                "--no-playlist",
                "--skip-download",
                "--print",
                "duration",
                "--no-warnings",
                url,
            ],
            timeout=4.0,
        )
        try:
            duration_ms = max(0, int(float(duration_raw.strip()) * 1000))
        except Exception:
            return None
        self._media_duration_cache[url] = duration_ms
        return duration_ms


    def _request_media_url_duration(self, url: str) -> None:
        url = url.strip()
        if (
            not url
            or url in self._media_duration_cache
            or url in self._media_duration_pending
        ):
            return
        self._media_duration_pending.add(url)

        def worker() -> None:
            try:
                duration_ms = self._duration_ms_from_media_url(url)
                if duration_ms is not None:
                    self._media_duration_cache[url] = duration_ms
            finally:
                self._media_duration_pending.discard(url)

        threading.Thread(target=worker, daemon=True).start()


    def _trigger_media_action(self, action: str) -> None:
        run_script_bg("mpris.sh", action)
        self._schedule_media_refresh()


    def _schedule_media_refresh(self) -> None:
        self._poll_media_metadata(force_refresh=True)
        self._poll_media_progress()
        for delay in (150, 450, 900):
            QTimer.singleShot(delay, lambda: self._poll_media_metadata(force_refresh=True))
            QTimer.singleShot(delay, self._poll_media_progress)


    def _poll_media_progress(self) -> None:
        if not hasattr(self, "elapsed"):
            return
        r = self._poll_result
        if r is None:
            self._media_position_ms = 0
            self._media_duration_ms = 0
            self._media_estimated_progress = False
            self._render_media_progress()
            return

        player = self._media_player or ""
        if not player:
            self._media_position_ms = 0
            self._media_duration_ms = 0
            self._media_estimated_progress = False
            self._render_media_progress()
            return

        now = monotonic()

        self._media_duration_ms = r.media_duration_ms

        if self._is_browser_player(player):
            url_duration_ms = self._media_duration_cache.get(self._media_url)
            if url_duration_ms is not None:
                self._media_duration_ms = url_duration_ms
            else:
                self._request_media_url_duration(self._media_url)

        if r.timestamp > self._media_last_anchor_time:
            self._media_last_anchor_time = r.timestamp
            if r.media_position_ms > 0:
                if (
                    self._media_duration_ms > 0
                    and self._is_browser_player(player)
                    and r.media_position_ms >= self._media_duration_ms - 1000
                    and r.media_status in {"Playing", "Paused"}
                ):
                    self._media_estimated_progress = True
                else:
                    self._media_position_ms = max(0, r.media_position_ms)
                    self._media_estimated_progress = False

        elapsed_since_anchor = max(0.0, now - self._media_last_anchor_time)

        if r.media_status == "Playing" and self._media_duration_ms > 0:
            self._media_position_ms = min(
                self._media_duration_ms,
                max(0, self._media_position_ms + int(elapsed_since_anchor * 1000)),
            )
            self._media_last_anchor_time = now
        elif r.media_status in {"Paused", "Stopped"}:
            self._media_position_ms = max(0, self._media_position_ms)
        else:
            self._media_position_ms = max(0, self._media_position_ms)

        self._media_status = r.media_status
        self._render_media_progress()


    def _render_media_progress(self) -> None:
        if not hasattr(self, "elapsed"):
            return
        self.elapsed.setText(format_millis(self._media_position_ms))
        self.total.setText(format_millis(self._media_duration_ms))

        track_width = self.progress_track.width() or 180
        if self._media_duration_ms > 0:
            ratio = max(
                0.0, min(1.0, self._media_position_ms / self._media_duration_ms)
            )
        else:
            ratio = 0.0
        fill_width = max(0, int(track_width * ratio))
        self.progress_fill.setGeometry(0, 0, fill_width, 4)


    def _queue_slider_commit(self, kind: str, value: int) -> None:
        if self._syncing_sliders:
            return
        if kind == "brightness":
            self._pending_brightness = value
            self._brightness_commit_timer.start(90)
        else:
            self._pending_volume = value
            self._volume_commit_timer.start(90)


    def _commit_brightness(self) -> None:
        run_script_bg("brightness.sh", "set", str(self._pending_brightness))


    def _commit_volume(self) -> None:
        run_script_bg("volume.sh", "set", str(self._pending_volume))


    def _set_cover_art(self, cover_path: Path) -> None:
        if not hasattr(self, "cover"):
            return
        cache_key = f"cover:{cover_path}:{self.cover.width()}x{self.cover.height()}"
        cached = get_cached_pixmap(cache_key)
        if cached is not None and isinstance(cached, QPixmap) and not cached.isNull():
            self.cover.setPixmap(cached)
            return
        pixmap = QPixmap(str(cover_path))
        if pixmap.isNull():
            self.cover.setPixmap(QPixmap())
            return
        scaled = pixmap.scaled(
            self.cover.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - self.cover.width()) // 2)
        y = max(0, (scaled.height() - self.cover.height()) // 2)
        cropped = scaled.copy(x, y, self.cover.width(), self.cover.height())

        rounded = QPixmap(self.cover.size())
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0, float(self.cover.width()), float(self.cover.height()), 16.0, 16.0
        )
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.cover.setPixmap(rounded)
        store_pixmap(cache_key, rounded)


    def _update_media_palette_from_cover(self, cover_path: Path) -> None:
        if not hasattr(self, "media_base"):
            return
        if not hasattr(self, "_cover_palette_worker"):
            self._init_media_workers()
        self._cover_palette_worker.start_extract(cover_path)

    def _on_cover_palette_done(self, palette):
        if palette is None:
            self._apply_media_palette()
            return
        self._apply_media_palette(*palette)

    def _extract_cover_palette(
        self, cover_path: Path
    ) -> tuple[str, str, str, str] | None:
        return extract_cover_palette(cover_path)

    def _hex_to_rgba(self, color: str, alpha: float) -> str:
        return hex_to_rgba(color, alpha)

    def _darken_hex(self, color: str, amount: float) -> str:
        return darken_hex(color, amount)


