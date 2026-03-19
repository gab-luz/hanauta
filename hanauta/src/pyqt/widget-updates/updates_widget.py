#!/usr/bin/env python3
from __future__ import annotations

import signal
import shlex
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import blend, load_theme_palette, palette_mtime, rgba
from pyqt.shared.updates import collect_update_payload, command_exists


MATERIAL_ICONS = {
    "close": "\ue5cd",
    "refresh": "\ue5d5",
    "system_update": "\ue8d7",
    "terminal": "\ue31c",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for key, path in {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
    }.items():
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
class UpdateWorker(QThread):
    finished_payload = pyqtSignal(dict)

    def run(self) -> None:
        self.finished_payload.emit(collect_update_payload())


class UpgradeWorker(QThread):
    finished_payload = pyqtSignal(dict)

    def __init__(self, command: list[str], label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.command = list(command)
        self.label = label

    def run(self) -> None:
        try:
            result = subprocess.run(
                self.command,
                capture_output=True,
                text=True,
                check=False,
                timeout=7200,
            )
            payload = {
                "ok": result.returncode == 0,
                "label": self.label,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "label": self.label,
                "stdout": "",
                "stderr": str(exc),
                "returncode": 1,
            }
        self.finished_payload.emit(payload)


class UpdatesWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        fonts = load_app_fonts()
        self.ui_font = detect_font("Rubik", fonts.get("ui_sans", ""), "Inter", "Noto Sans", "Sans Serif")
        self.display_font = detect_font("Rubik", fonts.get("ui_display", ""), "Outfit", self.ui_font)
        self.icon_font = detect_font(fonts.get("material_icons", ""), "Material Icons", self.ui_font)
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._fade: QPropertyAnimation | None = None
        self._worker: UpdateWorker | None = None
        self._upgrade_worker: UpgradeWorker | None = None
        self._latest_payload: dict = {}

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hanauta Updates")
        self.setFixedSize(404, 812)

        self._build_ui()
        self._apply_styles()
        self._apply_shadow()
        self._place_window()
        self._animate_in()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        QTimer.singleShot(120, self.refresh_updates)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)

        titles = QVBoxLayout()
        titles.setSpacing(4)
        eyebrow = QLabel("UPDATE CHECKER")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.subtitle = QLabel("Inspect Debian, Arch, and Flatpak updates without leaving the desktop.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        titles.addWidget(eyebrow)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.refresh_button = self._icon_button("refresh")
        self.refresh_button.clicked.connect(self.refresh_updates)
        self.close_button = self._icon_button("close")
        self.close_button.clicked.connect(self.close)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.close_button)
        header.addLayout(actions, 0)
        layout.addLayout(header)

        self.hero = QFrame()
        self.hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(8)
        self.hero_badge = QLabel("SYSTEM")
        self.hero_badge.setObjectName("metaChip")
        self.hero_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_badge.setFixedWidth(84)
        self.hero_badge.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.hero_title = QLabel("Scanning package managers")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setFont(QFont(self.display_font, 21, QFont.Weight.DemiBold))
        self.hero_detail = QLabel("Collecting pending updates from the available backends.")
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setWordWrap(True)
        hero_layout.addWidget(self.hero_badge, 0)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_detail)
        layout.addWidget(self.hero)

        stats = QGridLayout()
        stats.setHorizontalSpacing(10)
        stats.setVerticalSpacing(10)
        self.backend_card = self._stat_card("Backend", "Detecting", "System package source")
        self.system_card = self._stat_card("System", "0", "Pending distro packages")
        self.flatpak_card = self._stat_card("Flatpak", "0", "Pending sandbox updates")
        self.security_card = self._stat_card("Security", "0", "Priority updates")
        stats.addWidget(self.backend_card, 0, 0)
        stats.addWidget(self.system_card, 0, 1)
        stats.addWidget(self.flatpak_card, 1, 0)
        stats.addWidget(self.security_card, 1, 1)
        layout.addLayout(stats)

        actions_card = QFrame()
        actions_card.setObjectName("sectionCard")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(12)
        actions_title = QLabel("ACTIONS")
        actions_title.setObjectName("eyebrow")
        actions_title.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        actions_layout.addWidget(actions_title)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        self.system_upgrade_button = QPushButton("Run system upgrade")
        self.system_upgrade_button.setObjectName("primaryButton")
        self.system_upgrade_button.clicked.connect(self._run_system_upgrade)
        self.flatpak_upgrade_button = QPushButton("Run Flatpak update")
        self.flatpak_upgrade_button.setObjectName("secondaryButton")
        self.flatpak_upgrade_button.clicked.connect(self._run_flatpak_upgrade)
        buttons_row.addWidget(self.system_upgrade_button, 1)
        buttons_row.addWidget(self.flatpak_upgrade_button, 1)
        actions_layout.addLayout(buttons_row)
        layout.addWidget(actions_card)

        output_card = QFrame()
        output_card.setObjectName("sectionCard")
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(16, 16, 16, 16)
        output_layout.setSpacing(10)
        output_title = QLabel("AVAILABLE UPDATES")
        output_title.setObjectName("eyebrow")
        output_title.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("output")
        self.output.setMinimumHeight(280)
        output_layout.addWidget(output_title)
        output_layout.addWidget(self.output, 1)
        layout.addWidget(output_card, 1)

        self.status_label = QLabel("Update checker is idle.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _stat_card(self, label: str, value: str, note: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(4)
        title = QLabel(label.upper())
        title.setObjectName("eyebrow")
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        value_label.setWordWrap(True)
        note_label = QLabel(note)
        note_label.setObjectName("statNote")
        note_label.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(value_label)
        card_layout.addWidget(note_label)
        card._value_label = value_label  # type: ignore[attr-defined]
        card._note_label = note_label  # type: ignore[attr-defined]
        return card

    def _set_stat(self, card: QFrame, value: str, note: str | None = None) -> None:
        value_label = getattr(card, "_value_label", None)
        note_label = getattr(card, "_note_label", None)
        if isinstance(value_label, QLabel):
            value_label.setText(value)
        if note is not None and isinstance(note_label, QLabel):
            note_label.setText(note)

    def _icon_button(self, name: str) -> QPushButton:
        button = QPushButton(material_icon(name))
        button.setObjectName("iconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(38, 38)
        button.setFont(QFont(self.icon_font, 18))
        return button

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 132))
        self.panel.setGraphicsEffect(shadow)

    def _place_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(available.x() + available.width() - self.width() - 48, available.y() + 92)

    def _animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#panel {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.surface_container_high, 0.97)},
                    stop: 0.55 {rgba(theme.surface_container, 0.94)},
                    stop: 1 {rgba(blend(theme.surface_container, theme.surface, 0.42), 0.90)}
                );
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 30px;
            }}
            QLabel#eyebrow {{
                color: {theme.primary};
                letter-spacing: 1.8px;
            }}
            QLabel#heroTitle, QLabel#statValue {{
                color: {theme.text};
            }}
            QLabel#subtitle, QLabel#heroDetail, QLabel#statNote {{
                color: {theme.text_muted};
            }}
            QLabel#statValue {{
                font-size: 19px;
                font-weight: 700;
            }}
            QFrame#heroCard {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {rgba(theme.primary_container, 0.44)},
                    stop: 0.40 {rgba(theme.secondary, 0.18)},
                    stop: 1 {rgba(theme.surface_container_high, 0.94)}
                );
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 26px;
            }}
            QFrame#statCard, QFrame#sectionCard {{
                background: {rgba(theme.surface_container_high, 0.84)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 24px;
            }}
            QPushButton#iconButton, QPushButton#secondaryButton {{
                background: {rgba(theme.surface_container_high, 0.90)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
                padding: 10px 12px;
                text-align: left;
            }}
            QPushButton#iconButton {{
                color: {theme.primary};
                font-family: "{self.icon_font}";
                min-width: 38px;
                max-width: 38px;
                min-height: 38px;
                max-height: 38px;
                padding: 0;
                border-radius: 19px;
                text-align: center;
            }}
            QPushButton#iconButton:hover, QPushButton#secondaryButton:hover {{
                background: {rgba(theme.primary, 0.10)};
                border: 1px solid {rgba(theme.primary, 0.24)};
            }}
            QPushButton#primaryButton {{
                background: {theme.primary};
                color: {theme.on_primary_container};
                border: none;
                border-radius: 18px;
                padding: 12px 14px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton#primaryButton:hover {{
                background: {rgba(theme.primary, 0.92)};
            }}
            QPushButton#primaryButton:disabled,
            QPushButton#secondaryButton:disabled {{
                background: {rgba(theme.surface_container_high, 0.55)};
                color: {rgba(theme.text, 0.45)};
                border: 1px solid {rgba(theme.outline, 0.10)};
            }}
            QLabel#metaChip {{
                background: {rgba(theme.primary, 0.12)};
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 999px;
                color: {theme.primary};
                padding: 7px 12px;
            }}
            QLabel#statusLabel {{
                background: {rgba(theme.on_surface, 0.035)};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 18px;
                padding: 12px 14px;
                color: {theme.text};
            }}
            QPlainTextEdit#output {{
                background: {rgba(theme.surface, 0.38)};
                color: {theme.text};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 18px;
                padding: 10px 12px;
                selection-background-color: {rgba(theme.primary, 0.20)};
            }}
            """
        )

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()

    def refresh_updates(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.refresh_button.setDisabled(True)
        self.system_upgrade_button.setDisabled(True)
        self.flatpak_upgrade_button.setDisabled(True)
        self.hero_title.setText("Checking for updates")
        self.hero_detail.setText("Querying system package manager and Flatpak backends.")
        self.status_label.setText("Update check in progress...")
        self.output.setPlainText("Scanning package managers...")
        self._worker = UpdateWorker(self)
        self._worker.finished_payload.connect(self._apply_payload)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _apply_payload(self, payload: dict) -> None:
        self._latest_payload = dict(payload)
        backend = str(payload.get("backend", "none"))
        distro_name = str(payload.get("distro_name", "Linux"))
        system_updates = [str(item) for item in payload.get("system_updates", []) if str(item).strip()]
        flatpak_updates = [str(item) for item in payload.get("flatpak_updates", []) if str(item).strip()]
        security_updates = int(payload.get("security_updates", 0) or 0)
        notes = [str(item) for item in payload.get("notes", []) if str(item).strip()]

        summary_bits: list[str] = []
        if backend != "none":
            summary_bits.append(f"{len(system_updates)} system")
        if payload.get("flatpak_command", ""):
            summary_bits.append(f"{len(flatpak_updates)} flatpak")
        summary_text = ", ".join(summary_bits) if summary_bits else "no supported backends"

        self.hero_badge.setText(backend.upper() if backend != "none" else "NONE")
        self.hero_title.setText(distro_name)
        self.hero_detail.setText(f"Pending updates: {summary_text}.")
        self._set_stat(self.backend_card, backend.upper() if backend != "none" else "NONE", "System package source")
        self._set_stat(self.system_card, str(len(system_updates)), "Pending distro packages")
        self._set_stat(self.flatpak_card, str(len(flatpak_updates)), "Pending sandbox updates")
        self._set_stat(self.security_card, str(security_updates), "Priority updates")

        chunks: list[str] = []
        chunks.append("SYSTEM UPDATES")
        chunks.append("None pending." if not system_updates else "\n".join(system_updates))
        chunks.append("")
        chunks.append("FLATPAK UPDATES")
        chunks.append("None pending." if not flatpak_updates else "\n".join(flatpak_updates))
        if notes:
            chunks.append("")
            chunks.append("NOTES")
            chunks.append("\n".join(notes))
        self.output.setPlainText("\n".join(chunks).strip())

        self.system_upgrade_button.setDisabled(not bool(payload.get("system_command", "")))
        self.flatpak_upgrade_button.setDisabled(not bool(payload.get("flatpak_command", "")))
        if notes:
            self.status_label.setText(notes[0])
        elif not system_updates and not flatpak_updates:
            self.status_label.setText("Everything looks up to date.")
        else:
            self.status_label.setText(
                f"Found {len(system_updates) + len(flatpak_updates)} pending update(s). Backup the system before upgrading."
            )
        self.refresh_button.setDisabled(False)
        self._worker = None

    def _run_system_upgrade(self) -> None:
        command = str(self._latest_payload.get("system_command", "")).strip()
        if not command:
            self.status_label.setText("No supported system upgrade command is available.")
            return
        if self._upgrade_worker is not None and self._upgrade_worker.isRunning():
            return
        if command_exists("pkexec"):
            exec_command = ["pkexec", "bash", "-lc", command]
        else:
            exec_command = ["bash", "-lc", command]
        self.status_label.setText("Starting privileged system upgrade. A polkit dialog may appear.")
        self.system_upgrade_button.setDisabled(True)
        self.flatpak_upgrade_button.setDisabled(True)
        self.output.setPlainText(f"$ {' '.join(shlex.quote(part) for part in exec_command)}\n\nWaiting for completion...")
        self._upgrade_worker = UpgradeWorker(exec_command, "system", self)
        self._upgrade_worker.finished_payload.connect(self._finish_upgrade)
        self._upgrade_worker.finished.connect(self._upgrade_worker.deleteLater)
        self._upgrade_worker.start()

    def _run_flatpak_upgrade(self) -> None:
        command = str(self._latest_payload.get("flatpak_command", "")).strip()
        if not command:
            self.status_label.setText("Flatpak is not available on this system.")
            return
        if self._upgrade_worker is not None and self._upgrade_worker.isRunning():
            return
        exec_command = ["bash", "-lc", command]
        self.status_label.setText("Starting Flatpak update. A polkit dialog may appear if system permissions are required.")
        self.system_upgrade_button.setDisabled(True)
        self.flatpak_upgrade_button.setDisabled(True)
        self.output.setPlainText(f"$ {' '.join(shlex.quote(part) for part in exec_command)}\n\nWaiting for completion...")
        self._upgrade_worker = UpgradeWorker(exec_command, "flatpak", self)
        self._upgrade_worker.finished_payload.connect(self._finish_upgrade)
        self._upgrade_worker.finished.connect(self._upgrade_worker.deleteLater)
        self._upgrade_worker.start()

    def _finish_upgrade(self, payload: dict) -> None:
        ok = bool(payload.get("ok", False))
        stdout = str(payload.get("stdout", "")).strip()
        stderr = str(payload.get("stderr", "")).strip()
        label = str(payload.get("label", "update"))
        combined = stdout
        if stderr:
            combined = f"{combined}\n\n{stderr}".strip()
        self.output.setPlainText(combined or "No command output was captured.")
        combined_lower = combined.lower()
        if ok:
            self.status_label.setText(f"{label.capitalize()} update finished. Refresh to verify the new state.")
        elif label == "flatpak" and "too many fuse filesystems mounted" in combined_lower:
            self.status_label.setText(
                "Flatpak hit the FUSE mount limit. Try cleaning stale Flatpak/FUSE mounts or increasing mount_max in /etc/fuse.conf."
            )
        elif label == "flatpak" and "g_propagate_error" in combined_lower:
            self.status_label.setText(
                "Flatpak failed in revokefs/FUSE cleanup. The widget now runs repair first, but stale mounts still need attention."
            )
        else:
            self.status_label.setText(f"{label.capitalize()} update failed or was cancelled.")
        self.system_upgrade_button.setDisabled(False)
        self.flatpak_upgrade_button.setDisabled(False)
        self._upgrade_worker = None


def main() -> int:
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    widget = UpdatesWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
