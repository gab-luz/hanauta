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


class GamesMixin:
    """Game carousel methods for NotificationCenter."""

    def _build_game_carousel_card(self) -> QFrame:
        self.game_carousel = GameCarouselCard(self.ui_font, self.material_font, self.theme_palette.panel_bg)
        self.game_carousel.add_slide(
            t("carousel.loading_title"),
            [t("carousel.loading_stats")],
            Path(STEAM_ICON),
            t("carousel.loading_platform"),
            self.theme_palette.primary,
            Path(),
        )
        self.game_carousel.play_button.clicked.connect(self._on_game_play_clicked)
        self.game_carousel.stack.currentChanged.connect(
            lambda _index: self._refresh_game_play_state()
        )
        self._refresh_game_play_state()

        def kick_async_load() -> None:
            # Use the service cache when available (instant UI), and fall back to local
            # filesystem reads in a background thread.
            payload = load_cached_games_payload()
            cached = payload.get("slides", [])
            any_playing = bool(payload.get("any_playing", False))
            if isinstance(cached, list) and cached:
                self._games_any_playing = any_playing
                self._refresh_game_play_state()
                try:
                    self.gameSlidesReady.emit(
                        [item for item in cached if isinstance(item, dict)][:4]
                    )
                except Exception:
                    pass
                return

            def worker() -> None:
                slides: list[dict] = []
                try:
                    slides = load_lutris_game_slides(2)
                    slides.extend(load_steam_game_slides(2))
                except Exception:
                    slides = []
                if not slides:
                    slides = [
                        {
                            "title": "Welcome back",
                            "stats": ["No launcher telemetry yet"],
                            "logo": str(STEAM_ICON),
                            "platform": "Game library",
                            "accent": "primary",
                            "source": "library",
                            "lutris_slug": "",
                        }
                    ]
                try:
                    self.gameSlidesReady.emit(slides[:4])
                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        # Delay until after signals are connected (avoids a startup race where the
        # worker emits before `gameSlidesReady` is connected).
        QTimer.singleShot(80, kick_async_load)
        self._games_cache_timer = QTimer(self)
        self._games_cache_timer.setInterval(5000)
        self._games_cache_timer.timeout.connect(self._sync_games_cache_state)
        self._games_cache_timer.start()
        return self.game_carousel


    def _apply_game_slides(self, slides: list) -> None:
        if not hasattr(self, "game_carousel"):
            return
        carousel = self.game_carousel
        if not isinstance(carousel, GameCarouselCard):
            return
        try:
            signature = json.dumps(slides, sort_keys=True, default=str)
        except Exception:
            signature = ""
        if signature and signature == getattr(self, "_games_cache_signature", ""):
            return
        self._games_cache_signature = signature
        import shutil

        carousel.clear_slides()
        safe_slides = slides if isinstance(slides, list) else []
        self._game_slides_data = [item for item in safe_slides if isinstance(item, dict)][:4]
        for index, slide in enumerate(self._game_slides_data):
            accent = (
                self.theme_palette.primary
                if slide.get("accent") == "primary"
                else self.theme_palette.secondary
            )
            cover_value = slide.get("cover", "")
            cover_path = (
                Path(cover_value)
                if isinstance(cover_value, str) and cover_value and cover_value != "."
                else Path()
            )
            carousel.add_slide(
                str(slide.get("title", "Game")),
                list(slide.get("stats", [])),
                Path(slide.get("logo", LUTRIS_ICON)),
                str(slide.get("platform", "Library")),
                accent,
                cover_path,
            )
            if cover_path and cover_path.is_file():
                try:
                    shutil.copy2(cover_path, "/tmp/cover.png")
                    palette = self._extract_cover_palette(None)
                    if palette:
                        carousel.set_slide_palette(index, *palette)
                except Exception:
                    pass
        self._refresh_game_play_state()


    def _current_game_slide(self) -> dict:
        if not hasattr(self, "game_carousel"):
            return {}
        try:
            index = int(self.game_carousel.stack.currentIndex())
        except Exception:
            index = 0
        if index < 0:
            index = 0
        if index >= len(getattr(self, "_game_slides_data", [])):
            return {}
        slide = self._game_slides_data[index]
        return slide if isinstance(slide, dict) else {}


    def _refresh_game_play_state(self) -> None:
        if not hasattr(self, "game_carousel"):
            return
        carousel = self.game_carousel
        if not isinstance(carousel, GameCarouselCard):
            return
        slide = self._current_game_slide()
        slug = str(slide.get("lutris_slug", "") or "")
        can_launch = bool(slug)
        any_playing = bool(getattr(self, "_games_any_playing", False))
        if not can_launch:
            carousel.play_button.setText(t("btn.play"))
            carousel.play_button.setEnabled(False)
            return
        carousel.play_button.setText(t("btn.playing") if any_playing else t("btn.play"))
        carousel.play_button.setEnabled(not any_playing)


    def _sync_games_cache_state(self) -> None:
        payload = load_cached_games_payload()
        if not payload:
            return
        any_playing = bool(payload.get("any_playing", False))
        if any_playing != getattr(self, "_games_any_playing", False):
            self._games_any_playing = any_playing
            self._refresh_game_play_state()


    def _on_game_play_clicked(self) -> None:
        slide = self._current_game_slide()
        slug = str(slide.get("lutris_slug", "") or "")
        title = str(slide.get("title", "this game") or "this game")
        if not slug:
            return

        if any_game_running_fast():
            self._games_any_playing = True
            self._refresh_game_play_state()
            return

        if not self._confirm_play(title):
            return
        self._launch_lutris_game(slug)
        self._games_any_playing = True
        self._refresh_game_play_state()


    def _confirm_play(self, title: str) -> bool:
        dialog = QDialog(self)
        dialog.setWindowTitle("Confirm")
        dialog.setModal(True)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        dialog.setStyleSheet(self.styleSheet())

        shell = QFrame(dialog)
        shell.setObjectName("confirmPopup")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(16, 16, 16, 16)
        shell_layout.setSpacing(10)

        title_label = QLabel(t("dialog.play_confirm_question"))
        title_label.setObjectName("confirmTitle")
        subtitle = QLabel(f"This will start “{title}” in Lutris.")
        subtitle.setObjectName("confirmSubtitle")
        subtitle.setWordWrap(True)
        shell_layout.addWidget(title_label)
        shell_layout.addWidget(subtitle)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addStretch(1)
        cancel = QPushButton(t("btn.cancel"))
        cancel.setObjectName("softButton")
        cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        play = QPushButton(t("btn.play_confirm"))
        play.setObjectName("confirmPlayButton")
        play.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        buttons.addWidget(cancel)
        buttons.addWidget(play)
        shell_layout.addLayout(buttons)

        root = QVBoxLayout(dialog)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)

        cancel.clicked.connect(dialog.reject)
        play.clicked.connect(dialog.accept)

        dialog.adjustSize()
        dialog.move(
            self.geometry().center().x() - dialog.width() // 2,
            self.geometry().center().y() - dialog.height() // 2,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted


    def _launch_lutris_game(self, slug: str) -> None:
        try:
            subprocess.Popen(
                ["lutris", f"lutris:rungame/{slug}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass


