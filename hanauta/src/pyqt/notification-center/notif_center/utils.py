from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QWidget

from notif_center.paths import (
    ASSETS_DIR,
    BIN_DIR,
    DESKTOP_CLOCK_BINARY,
    FONTS_DIR,
    ROOT,
    SCRIPTS_DIR,
    STATE_DIR,
    preferred_icon_path,
)
from pyqt.shared.runtime import entry_command, entry_patterns


def run_cmd(cmd: list[str], timeout: float = 2.0) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def run_script(script_name: str, *args: str) -> str:
    path = SCRIPTS_DIR / script_name
    if not path.exists():
        return ""
    return run_cmd([str(path), *args])


def run_script_bg(script_name: str, *args: str) -> None:
    path = SCRIPTS_DIR / script_name
    if not path.exists():
        return
    try:
        subprocess.Popen(
            [str(path), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def run_bg_detached(cmd: list[str]) -> bool:
    if not cmd:
        return False
    try:
        if QProcess.startDetached(cmd[0], cmd[1:]):
            return True
    except Exception:
        pass
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def run_bg(cmd: list[str]) -> None:
    run_bg_detached(cmd)


def _process_pattern(pattern: str) -> str:
    return re.escape(pattern)


def terminate_background_matches(pattern: str) -> None:
    try:
        subprocess.run(
            ["pkill", "-f", _process_pattern(pattern)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


def apply_antialias_font(widget: QWidget) -> None:
    font = widget.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child_font = child.font()
        child_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        child.setFont(child_font)


def run_bg_singleton(script_path: Path, *args: str) -> None:
    command = entry_command(script_path, *args)
    if not command:
        return
    for pattern in entry_patterns(script_path):
        terminate_background_matches(pattern)
    run_bg_detached(command)


def desktop_clock_command() -> list[str]:
    from pyqt.shared.plugin_runtime import resolve_plugin_script
    script = resolve_plugin_script("desktop_clock_widget.py", ["desktop-clock", "clock"])
    if script is not None and script.exists():
        return entry_command(script)
    if DESKTOP_CLOCK_BINARY.exists():
        return [str(DESKTOP_CLOCK_BINARY)]
    for candidate in (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-desktop-clock" / "desktop_clock_widget.py",
        Path.home() / "dev" / "hanauta-plugin-desktop-clock" / "desktop_clock_widget.py",
    ):
        if candidate.exists():
            return entry_command(candidate)
    return []


def notification_control_command(*args: str) -> list[str]:
    local = BIN_DIR / "hanauta-notifyctl"
    if local.exists():
        return [str(local), *args]
    return ["hanauta-notifyctl", *args]


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


MATERIAL_ICONS: dict[str, str] = {
    "airplanemode_active": "\ue195",
    "arrow_back": "\ue5c4",
    "bluetooth": "\ue1a7",
    "brightness_medium": "\ue1ae",
    "camera_alt": "\ue3b0",
    "calendar_today": "\ue935",
    "check_circle": "\ue86c",
    "chevron_left": "\ue5cb",
    "chevron_right": "\ue5cc",
    "content_paste": "\ue14f",
    "close": "\ue5cd",
    "coffee": "\uefef",
    "delete_sweep": "\ue16c",
    "do_not_disturb_on": "\ue644",
    "home": "\ue88a",
    "hub": "\uee20",
    "invert_colors": "\ue891",
    "lightbulb": "\ue0f0",
    "nightlight": "\uf03d",
    "pause": "\ue034",
    "person": "\ue7fd",
    "phone_android": "\ue324",
    "play_arrow": "\ue037",
    "power_settings_new": "\ue8ac",
    "smartphone": "\ue32c",
    "save": "\ue161",
    "settings": "\ue8b8",
    "skip_next": "\ue044",
    "skip_previous": "\ue045",
    "thermostat": "\ue1ff",
    "tune": "\ue429",
    "volume_up": "\ue050",
    "wifi": "\ue63e",
    "lock": "\ue897",
    "auto_awesome": "\ue65f",
    "timer": "\ue425",
    "public": "\ue80b",
    "videocam": "\ue04b",
    "show_chart": "\ue6e1",
    "storage": "\ue1db",
    "watch": "\ue334",
    "sports_esports": "\uea28",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "material_symbols_outlined": FONTS_DIR / "MaterialSymbolsOutlined.ttf",
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


def format_playtime_hours(hours: float) -> str:
    if hours <= 0:
        return "0m total"
    whole_hours = int(hours)
    minutes = int(round((hours - whole_hours) * 60))
    if whole_hours <= 0:
        return f"{minutes}m total"
    if minutes <= 0:
        return f"{whole_hours}h total"
    return f"{whole_hours}h {minutes}m total"


def format_millis(ms: int) -> str:
    ms = max(0, ms)
    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def parse_bool_text(value: str) -> bool:
    return value.strip().lower() == "true"


def tinted_svg_pixmap(path: Path, color: QColor, size: int = 18) -> QPixmap:
    if not path.exists():
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return pixmap


def render_svg_pixmap(path: Path, size: int = 18) -> QPixmap:
    if not path.exists():
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def render_theme_icon_pixmap(names: list[str], size: int = 18) -> QPixmap:
    for name in names:
        if not name:
            continue
        icon = QIcon.fromTheme(name)
        if icon.isNull():
            continue
        pixmap = icon.pixmap(size, size)
        if not pixmap.isNull():
            return pixmap
    return QPixmap()


def accent_palette(name: str) -> dict[str, str]:
    palettes = {
        "orchid": {
            "accent": "#D0BCFF",
            "on_accent": "#381E72",
            "soft": "rgba(208,188,255,0.18)",
        },
        "mint": {
            "accent": "#8FE3CF",
            "on_accent": "#11352D",
            "soft": "rgba(143,227,207,0.18)",
        },
        "sunset": {
            "accent": "#FFB59E",
            "on_accent": "#4D2418",
            "soft": "rgba(255,181,158,0.18)",
        },
    }
    return palettes.get(name, palettes["orchid"])


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f"{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(json.dumps(payload, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(str(temp_path), str(path))
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
