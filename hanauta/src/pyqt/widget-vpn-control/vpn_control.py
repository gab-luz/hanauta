#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compact PyQt6 WireGuard control popup.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, QTimer, QSize, QStringListModel, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


from pyqt.shared.runtime import fonts_root, scripts_root, source_root
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.button_helpers import create_close_button

APP_DIR = source_root()
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

SCRIPTS_DIR = scripts_root()
FONTS_DIR = fonts_root()
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SETTINGS_FILE = STATE_DIR / "settings.json"
SPLIT_HELPER = SCRIPTS_DIR / "vpn_bypass_helper.py"
SPLIT_LAUNCHER = SCRIPTS_DIR / "vpn_bypass_launcher.py"
LOCAL_APPLICATIONS_DIR = Path.home() / ".local" / "share" / "applications"
WRAPPER_BACKUP_DIR = STATE_DIR / "vpn-wrapper-backups"
ICON_ASSETS_DIR = APP_DIR / "assets" / "icons"
FLATPAK_ICON_PATH = ICON_ASSETS_DIR / "flatpak.svg"
TUX_ICON_PATH = ICON_ASSETS_DIR / "tux.svg"
DESKTOP_DIRS = [
    Path.home() / ".local" / "share" / "applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
]

MATERIAL_ICONS = {
    "close": "\ue5cd",
    "lock": "\ue897",
    "lock_open": "\ue898",
    "refresh": "\ue5d5",
    "shield": "\ue9e0",
    "tune": "\ue429",
    "rocket": "\ue9d0",
    "add": "\ue145",
    "delete": "\ue872",
    "delete_sweep": "\ue16c",
}


def service_enabled() -> bool:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return True
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return True
    current = services.get("vpn_control", {})
    if not isinstance(current, dict):
        return True
    return bool(current.get("enabled", True))


def load_vpn_service_settings() -> dict[str, object]:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return {}
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return {}
    current = services.get("vpn_control", {})
    return current if isinstance(current, dict) else {}


def save_vpn_service_setting(key: str, value: object) -> None:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        payload = {}
    services = payload.get("services", {})
    if not isinstance(services, dict):
        services = {}
    current = services.get("vpn_control", {})
    if not isinstance(current, dict):
        current = {}
    current[key] = value
    services["vpn_control"] = current
    payload["services"] = services
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_cmd(cmd: list[str], timeout: float = 3.0) -> str:
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
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return ""
    return run_cmd([str(script_path), *args])


def run_script_bg(script_name: str, *args: str) -> None:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return
    try:
        subprocess.Popen(
            [str(script_path), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def themed_icon(path: Path, fallback_theme_name: str = "") -> QIcon:
    if path.exists():
        return QIcon(str(path))
    if fallback_theme_name:
        icon = QIcon.fromTheme(fallback_theme_name)
        if not icon.isNull():
            return icon
    return QIcon()


def normalize_split_tunnel_apps(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "")).strip().lower()
        target = str(item.get("target", "")).strip()
        label = str(item.get("label", "")).strip()
        if kind not in {"desktop", "flatpak", "binary"} or not target:
            continue
        if not label:
            label = target
        entry = {"kind": kind, "target": target, "label": label}
        for extra_key in ("source_path", "icon_name", "comment", "wrapper_path"):
            extra_value = str(item.get(extra_key, "")).strip()
            if extra_value:
                entry[extra_key] = extra_value
        normalized.append(entry)
    return normalized


def save_split_tunnel_apps(entries: list[dict[str, str]]) -> None:
    save_vpn_service_setting("split_tunnel_apps", normalize_split_tunnel_apps(entries))


def parse_desktop_entry(path: Path) -> dict[str, str] | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    entry: dict[str, str] = {}
    in_desktop_entry = False
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_desktop_entry = line == "[Desktop Entry]"
            continue
        if not in_desktop_entry or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key not in entry:
            entry[key] = value.strip()

    if entry.get("Type") != "Application":
        return None
    if entry.get("NoDisplay", "").lower() == "true" or entry.get("Hidden", "").lower() == "true":
        return None
    if entry.get("X-HanautaSplitTunnel", "").lower() == "true":
        return None

    name = entry.get("Name", "").strip()
    if not name:
        return None
    return {
        "name": name,
        "desktop_id": path.name,
        "comment": entry.get("Comment", "").strip(),
        "icon_name": entry.get("Icon", "").strip(),
        "source_path": str(path),
    }


def scan_desktop_apps() -> list[dict[str, str]]:
    apps: list[dict[str, str]] = []
    seen: set[str] = set()
    for directory in DESKTOP_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.desktop")):
            entry = parse_desktop_entry(path)
            if entry is None:
                continue
            desktop_id = entry["desktop_id"].lower()
            if desktop_id in seen:
                continue
            seen.add(desktop_id)
            apps.append(entry)
    apps.sort(key=lambda item: item["name"].lower())
    return apps


def scan_flatpak_apps() -> list[dict[str, str]]:
    if not shutil.which("flatpak"):
        return []
    try:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application,name"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    apps: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if not parts:
            continue
        app_id = parts[0]
        name = parts[1] if len(parts) > 1 else app_id
        apps.append({"app_id": app_id, "name": name})
    apps.sort(key=lambda item: item["name"].lower())
    return apps


def launch_direct_entry(entry: dict[str, str]) -> bool:
    kind = str(entry.get("kind", "")).strip().lower()
    target = str(entry.get("target", "")).strip()
    try:
        if kind == "desktop":
            source_path = str(entry.get("source_path", "")).strip()
            if source_path:
                launched = subprocess.run(
                    ["gio", "launch", source_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if launched.returncode == 0:
                    return True
            desktop_base = target[:-8] if target.endswith(".desktop") else target
            launched = subprocess.run(["gtk-launch", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if launched.returncode != 0:
                subprocess.Popen(["gtk-launch", desktop_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if kind == "flatpak":
            subprocess.Popen(["flatpak", "run", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if kind == "binary":
            command = [part for part in shlex.split(target) if part]
            if not command:
                return False
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception:
        return False
    return False


def slugify_label(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "app"


def wrapper_desktop_path(entry: dict[str, str]) -> Path:
    kind = str(entry.get("kind", "")).strip().lower()
    target = str(entry.get("target", "")).strip()
    if kind == "desktop" and target:
        name = target if target.endswith(".desktop") else f"{target}.desktop"
        return LOCAL_APPLICATIONS_DIR / name
    if kind == "flatpak" and target:
        return LOCAL_APPLICATIONS_DIR / f"{target}.desktop"
    slug = slugify_label(str(entry.get("label", target or "app")))
    return LOCAL_APPLICATIONS_DIR / f"hanauta-split-{slug}.desktop"


def desktop_exec(script_path: Path, entry: dict[str, str]) -> str:
    command = ["/usr/bin/env", "python3", str(script_path), "--mode", str(entry.get("kind", "")), "--target", str(entry.get("target", ""))]
    source_path = str(entry.get("source_path", "")).strip()
    if source_path:
        command.extend(["--source-path", source_path])
    return shlex.join(command)


def write_wrapper_desktop(entry: dict[str, str]) -> Path:
    LOCAL_APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = wrapper_desktop_path(entry)
    base_name = str(entry.get("label", entry.get("target", "Split tunnel"))).strip() or "Split tunnel"
    name = f"{base_name} (Outside VPN)"
    comment = str(entry.get("comment", "")).strip() or "Launch outside WireGuard when the VPN is active."
    icon_name = str(entry.get("icon_name", "")).strip()
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Comment={comment}",
        f"Exec={desktop_exec(SPLIT_LAUNCHER, entry)}",
        "Terminal=false",
        "StartupNotify=true",
        "X-HanautaSplitTunnel=true",
    ]
    if icon_name:
        lines.append(f"Icon={icon_name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def prepare_wrapper_entry(entry: dict[str, str]) -> tuple[dict[str, str], Path]:
    wrapper_entry = dict(entry)
    path = wrapper_desktop_path(entry)
    source_path = Path(str(entry.get("source_path", "")).strip()) if str(entry.get("source_path", "")).strip() else None
    if source_path is not None and source_path.resolve() == path.resolve() and source_path.exists():
        WRAPPER_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = WRAPPER_BACKUP_DIR / source_path.name
        shutil.copy2(source_path, backup_path)
        wrapper_entry["source_path"] = str(backup_path)
    return wrapper_entry, path


def remove_wrapper_desktop(entry: dict[str, str]) -> None:
    path_text = str(entry.get("wrapper_path", "")).strip()
    path = Path(path_text) if path_text else wrapper_desktop_path(entry)
    source_path = Path(str(entry.get("source_path", "")).strip()) if str(entry.get("source_path", "")).strip() else None
    try:
        if source_path is not None and source_path.parent == WRAPPER_BACKUP_DIR and source_path.exists():
            shutil.copy2(source_path, path)
            source_path.unlink()
        elif path.exists():
            path.unlink()
    except Exception:
        pass


class AppSelectionDialog(QDialog):
    def __init__(
        self,
        theme,
        apps: list[dict[str, str]],
        *,
        title_text: str = "Add apps outside VPN",
        subtitle_text: str = "Search installed apps, use autocomplete, and select multiple entries at once.",
        placeholder_text: str = "Type an app name or desktop id",
        add_button_text: str = "Add selected apps",
        primary_label_key: str = "name",
        secondary_parts: tuple[str, ...] = ("comment", "desktop_id"),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.apps = apps
        self.title_text = title_text
        self.subtitle_text = subtitle_text
        self.placeholder_text = placeholder_text
        self.add_button_text = add_button_text
        self.primary_label_key = primary_label_key
        self.secondary_parts = secondary_parts
        self._label_to_items: dict[str, list[QListWidgetItem]] = {}
        self._completer_model = QStringListModel(self)
        self._setup_window()
        self._build_ui()
        self._populate_apps()
        self._apply_styles()

    def _setup_window(self) -> None:
        self.setWindowTitle(self.title_text)
        self.setModal(True)
        self.resize(520, 440)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel(self.title_text)
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QLabel(self.subtitle_text)
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText(self.placeholder_text)
        self.search_input.textChanged.connect(self._filter_items)
        layout.addWidget(self.search_input)

        self.completer = QCompleter(self._completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer.activated.connect(self._select_from_completion)
        self.search_input.setCompleter(self.completer)

        self.app_list = QListWidget()
        self.app_list.setObjectName("appList")
        self.app_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.app_list, 1)

        self.selection_label = QLabel("0 apps selected")
        self.selection_label.setObjectName("dialogSubtitle")
        layout.addWidget(self.selection_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.add_button_text)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.button_box = buttons

        self.app_list.itemSelectionChanged.connect(self._update_selection_label)

    def _populate_apps(self) -> None:
        labels: list[str] = []
        self.app_list.clear()
        self._label_to_items.clear()
        for app in self.apps:
            label = str(app.get(self.primary_label_key, "")).strip()
            detail_parts = [str(app.get(key, "")).strip() for key in self.secondary_parts]
            detail = " · ".join([part for part in detail_parts if part])
            item = QListWidgetItem(f"{label}\n{detail}")
            item.setData(Qt.ItemDataRole.UserRole, app)
            item.setData(Qt.ItemDataRole.UserRole + 1, label)
            item.setData(Qt.ItemDataRole.UserRole + 2, detail)
            self.app_list.addItem(item)
            self._label_to_items.setdefault(label, []).append(item)
            labels.append(label)
        self._completer_model.setStringList(sorted(set(labels), key=str.lower))
        self._update_selection_label()

    def _filter_items(self, text: str) -> None:
        query = text.strip().lower()
        for index in range(self.app_list.count()):
            item = self.app_list.item(index)
            haystack = " ".join(
                [
                    str(item.data(Qt.ItemDataRole.UserRole + 1) or ""),
                    str(item.data(Qt.ItemDataRole.UserRole + 2) or ""),
                ]
            ).lower()
            item.setHidden(bool(query) and query not in haystack)

    def _select_from_completion(self, label: str) -> None:
        self.search_input.setText(label)
        for item in self._label_to_items.get(label, []):
            item.setHidden(False)
            item.setSelected(True)
            self.app_list.scrollToItem(item)
        self._update_selection_label()

    def _update_selection_label(self) -> None:
        count = len(self.selected_apps())
        self.selection_label.setText(f"{count} app{'s' if count != 1 else ''} selected")

    def selected_apps(self) -> list[dict[str, str]]:
        selected: list[dict[str, str]] = []
        for item in self.app_list.selectedItems():
            payload = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(payload, dict):
                selected.append(payload)
        return selected

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {rgba(theme.surface_container_high, 0.96)};
                color: {theme.text};
            }}
            QLabel#dialogTitle {{
                color: {theme.text};
                font-size: 15px;
                font-weight: 700;
            }}
            QLabel#dialogSubtitle {{
                color: {theme.text_muted};
                font-size: 11px;
            }}
            QLineEdit#searchInput {{
                background: {rgba(theme.surface_container_high, 0.92)};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                padding: 10px 12px;
            }}
            QListWidget#appList {{
                background: {rgba(theme.surface_container_high, 0.90)};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 18px;
                outline: none;
                padding: 6px;
            }}
            QListWidget#appList::item {{
                padding: 10px 12px;
                margin: 2px 0;
                border-radius: 12px;
            }}
            QListWidget#appList::item:selected {{
                background: {theme.hover_bg};
                color: {theme.text};
            }}
            QAbstractItemView {{
                background: {rgba(theme.surface_container_high, 0.98)};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                selection-background-color: {theme.hover_bg};
                selection-color: {theme.text};
            }}
            QDialogButtonBox QPushButton {{
                background: {theme.chip_bg};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                min-height: 38px;
                padding: 0 16px;
            }}
            QDialogButtonBox QPushButton:hover {{
                background: {theme.hover_bg};
            }}
            """
        )


class BinarySelectionDialog(QDialog):
    def __init__(self, theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self._setup_window()
        self._build_ui()
        self._apply_styles()

    def _setup_window(self) -> None:
        self.setWindowTitle("Add binary outside VPN")
        self.setModal(True)
        self.resize(520, 240)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Add binary outside VPN")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QLabel("Choose an executable and optional arguments for the outside-VPN launcher.")
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)

        self.path_input = QLineEdit()
        self.path_input.setObjectName("searchInput")
        self.path_input.setPlaceholderText("Executable path")
        path_row.addWidget(self.path_input, 1)

        browse_button = QPushButton("Browse")
        browse_button.setObjectName("dialogButton")
        browse_button.clicked.connect(self._browse_path)
        path_row.addWidget(browse_button)
        layout.addLayout(path_row)

        self.args_input = QLineEdit()
        self.args_input.setObjectName("searchInput")
        self.args_input.setPlaceholderText("Optional arguments")
        layout.addWidget(self.args_input)

        self.label_input = QLineEdit()
        self.label_input.setObjectName("searchInput")
        self.label_input.setPlaceholderText("Launcher label")
        layout.addWidget(self.label_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Add binary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_path(self) -> None:
        dialog = QFileDialog(self, "Choose binary or launcher")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self._apply_file_dialog_styles(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selectedFiles()
        if not selected:
            return
        path = selected[0]
        self.path_input.setText(path)
        if not self.label_input.text().strip():
            self.label_input.setText(Path(path).name)

    def values(self) -> tuple[str, str, str]:
        return (
            self.path_input.text().strip(),
            self.args_input.text().strip(),
            self.label_input.text().strip(),
        )

    def _apply_file_dialog_styles(self, dialog: QFileDialog) -> None:
        theme = self.theme
        dialog.setStyleSheet(
            f"""
            QWidget {{
                background: {rgba(theme.surface_container_high, 0.96)};
                color: {theme.text};
            }}
            QLineEdit, QListView, QTreeView {{
                background: {rgba(theme.surface_container_high, 0.90)};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 12px;
                selection-background-color: {theme.hover_bg};
                selection-color: {theme.text};
            }}
            QPushButton {{
                background: {theme.chip_bg};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 12px;
                min-height: 34px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: {theme.hover_bg};
            }}
            """
        )

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {rgba(theme.surface_container_high, 0.96)};
                color: {theme.text};
            }}
            QLabel#dialogTitle {{
                color: {theme.text};
                font-size: 15px;
                font-weight: 700;
            }}
            QLabel#dialogSubtitle {{
                color: {theme.text_muted};
                font-size: 11px;
            }}
            QLineEdit#searchInput {{
                background: {rgba(theme.surface_container_high, 0.92)};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                padding: 10px 12px;
            }}
            QPushButton#dialogButton, QDialogButtonBox QPushButton {{
                background: {theme.chip_bg};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                min-height: 38px;
                padding: 0 16px;
            }}
            QPushButton#dialogButton:hover, QDialogButtonBox QPushButton:hover {{
                background: {theme.hover_bg};
            }}
            """
        )


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
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


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


class VpnToggleWorker(QThread):
    completed = pyqtSignal(bool, str)

    def __init__(self, interface: str) -> None:
        super().__init__()
        self.interface = interface

    def run(self) -> None:
        script_path = SCRIPTS_DIR / "vpn.sh"
        if not script_path.exists():
            self.completed.emit(False, "Missing vpn.sh helper.")
            return

        try:
            result = subprocess.run(
                [str(script_path), "--toggle-wg", self.interface],
                capture_output=True,
                text=True,
                timeout=45.0,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.completed.emit(False, "Timed out waiting for WireGuard.")
            return
        except Exception as exc:
            self.completed.emit(False, f"WireGuard toggle failed: {exc}")
            return

        payload = {}
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if stdout:
            try:
                payload = json.loads(stdout)
            except Exception:
                payload = {}

        if payload:
            ok = bool(payload.get("ok", result.returncode == 0))
            message = str(payload.get("message", "")).strip()
        else:
            ok = result.returncode == 0
            message = stdout or stderr

        if not message:
            message = "WireGuard updated." if ok else "WireGuard command failed."

        self.completed.emit(ok, message)


class VpnControlPopup(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.material_font = detect_font(
            self.loaded_fonts.get("material_icons", ""),
            self.loaded_fonts.get("material_icons_outlined", ""),
            self.loaded_fonts.get("material_symbols_outlined", ""),
            self.loaded_fonts.get("material_symbols_rounded", ""),
            "Material Icons",
            "Material Icons Outlined",
            "Material Symbols Outlined",
            "Material Symbols Rounded",
        )
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._building_combo = False
        self._building_switch = False
        self._toggle_worker: VpnToggleWorker | None = None
        self._desktop_apps_cache: list[dict[str, str]] | None = None
        self._flatpak_apps_cache: list[dict[str, str]] | None = None
        self._split_tunnel_apps = normalize_split_tunnel_apps(
            load_vpn_service_settings().get("split_tunnel_apps", [])
        )
        self._setup_window()
        self._build_ui()
        self._apply_styles()
        self.refresh_state()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_state)
        self.poll_timer.start(5000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

    def _setup_window(self) -> None:
        self.setWindowTitle("WireGuard")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(420, 560)

        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.move(geo.x() + geo.width() - self.width() - 14, geo.y() + 50)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._toggle_worker is not None and self._toggle_worker.isRunning():
            self._toggle_worker.quit()
            self._toggle_worker.wait(250)
        app = QApplication.instance()
        if app is not None:
            app.quit()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        icon = QLabel(material_icon("shield"))
        icon.setObjectName("headerIcon")
        icon.setFont(QFont(self.material_font, 20))
        header_text = QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(2)
        title = QLabel("WireGuard")
        title.setObjectName("title")
        subtitle = QLabel("Select a tunnel and bring it up or down.")
        subtitle.setObjectName("subtitle")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(header_text, 1)

        self.close_button = create_close_button(material_icon("close"), self.material_font, font_size=18)
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.state_chip = QFrame()
        self.state_chip.setObjectName("stateChip")
        chip_layout = QHBoxLayout(self.state_chip)
        chip_layout.setContentsMargins(12, 12, 12, 12)
        chip_layout.setSpacing(10)

        self.state_icon = QLabel(material_icon("lock_open"))
        self.state_icon.setObjectName("stateIcon")
        self.state_icon.setFont(QFont(self.material_font, 18))
        chip_text = QVBoxLayout()
        chip_text.setContentsMargins(0, 0, 0, 0)
        chip_text.setSpacing(2)
        self.state_label = QLabel("Checking tunnel state…")
        self.state_label.setObjectName("stateLabel")
        self.detail_label = QLabel("No interface selected")
        self.detail_label.setObjectName("detailLabel")
        chip_text.addWidget(self.state_label)
        chip_text.addWidget(self.detail_label)
        chip_layout.addWidget(self.state_icon)
        chip_layout.addLayout(chip_text, 1)
        layout.addWidget(self.state_chip)

        combo_row = QHBoxLayout()
        combo_row.setContentsMargins(0, 0, 0, 0)
        combo_row.setSpacing(8)
        combo_icon = QLabel(material_icon("tune"))
        combo_icon.setObjectName("rowIcon")
        combo_icon.setFont(QFont(self.material_font, 18))
        self.interface_combo = QComboBox()
        self.interface_combo.setObjectName("interfaceCombo")
        self.interface_combo.setView(QListView())
        self.interface_combo.currentTextChanged.connect(self._set_interface)
        combo_row.addWidget(combo_icon)
        combo_row.addWidget(self.interface_combo, 1)
        layout.addLayout(combo_row)

        self.auto_start_checkbox = QCheckBox("Auto-enable selected tunnel on session start")
        self.auto_start_checkbox.setObjectName("settingCheck")
        self.auto_start_checkbox.toggled.connect(self._toggle_auto_start)
        layout.addWidget(self.auto_start_checkbox)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self.refresh_button = QPushButton(material_icon("refresh"))
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_button.setFont(QFont(self.material_font, 18))
        self.refresh_button.clicked.connect(self.refresh_state)

        self.toggle_button = QPushButton("Enable")
        self.toggle_button.setObjectName("primaryButton")
        self.toggle_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_button.clicked.connect(self._toggle_selected)

        actions.addWidget(self.refresh_button)
        actions.addWidget(self.toggle_button, 1)
        layout.addLayout(actions)

        split_header = QLabel("Split tunnel launchers")
        split_header.setObjectName("sectionTitle")
        layout.addWidget(split_header)

        split_subtitle = QLabel("Launch selected apps outside WireGuard. Existing processes are not re-routed.")
        split_subtitle.setObjectName("sectionSubtitle")
        split_subtitle.setWordWrap(True)
        layout.addWidget(split_subtitle)

        split_actions = QHBoxLayout()
        split_actions.setContentsMargins(0, 0, 0, 0)
        split_actions.setSpacing(8)

        self.add_app_button = QPushButton(material_icon("add"))
        self.add_app_button.setObjectName("iconButton")
        self.add_app_button.setFont(QFont(self.material_font, 18))
        self.add_app_button.setToolTip("Add desktop app")
        self.add_app_button.clicked.connect(self._add_desktop_app)
        split_actions.addWidget(self.add_app_button)

        self.add_flatpak_button = QPushButton()
        self.add_flatpak_button.setObjectName("iconButton")
        self.add_flatpak_button.setIcon(themed_icon(FLATPAK_ICON_PATH, "flatpak"))
        self.add_flatpak_button.setIconSize(QSize(18, 18))
        self.add_flatpak_button.setToolTip("Add Flatpak app")
        self.add_flatpak_button.clicked.connect(self._add_flatpak_app)
        split_actions.addWidget(self.add_flatpak_button)

        self.add_binary_button = QPushButton()
        self.add_binary_button.setObjectName("iconButton")
        self.add_binary_button.setIcon(themed_icon(TUX_ICON_PATH, "application-x-executable"))
        self.add_binary_button.setIconSize(QSize(18, 18))
        self.add_binary_button.setToolTip("Add custom binary")
        self.add_binary_button.clicked.connect(self._add_binary_app)
        split_actions.addWidget(self.add_binary_button)

        layout.addLayout(split_actions)

        self.split_list = QListWidget()
        self.split_list.setObjectName("splitList")
        self.split_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.split_list)

        split_footer = QHBoxLayout()
        split_footer.setContentsMargins(0, 0, 0, 0)
        split_footer.setSpacing(8)

        self.launch_bypass_button = QPushButton("Launch outside VPN")
        self.launch_bypass_button.setObjectName("primaryButton")
        self.launch_bypass_button.clicked.connect(self._launch_selected_split_app)
        split_footer.addWidget(self.launch_bypass_button, 1)

        self.remove_bypass_button = QPushButton(material_icon("delete"))
        self.remove_bypass_button.setObjectName("iconButton")
        self.remove_bypass_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.remove_bypass_button.setFont(QFont(self.material_font, 18))
        self.remove_bypass_button.setToolTip("Remove selected app")
        self.remove_bypass_button.clicked.connect(self._remove_selected_split_app)
        split_footer.addWidget(self.remove_bypass_button)

        self.clear_bypass_button = QPushButton(material_icon("delete_sweep"))
        self.clear_bypass_button.setObjectName("iconButton")
        self.clear_bypass_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_bypass_button.setFont(QFont(self.material_font, 18))
        self.clear_bypass_button.setToolTip("Clear all apps")
        self.clear_bypass_button.clicked.connect(self._clear_split_apps)
        split_footer.addWidget(self.clear_bypass_button)

        layout.addLayout(split_footer)

        self.footer_label = QLabel("Available configurations update automatically.")
        self.footer_label.setObjectName("footerLabel")
        self.footer_label.setWordWrap(True)
        layout.addWidget(self.footer_label)

        root.addWidget(card)
        self._reload_split_tunnel_list()
        self.split_list.itemSelectionChanged.connect(self._sync_split_actions)

    def _apply_styles(self) -> None:
        theme = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
                font-size: 12px;
            }}
            QFrame#card {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 24px;
            }}
            QLabel#headerIcon, QLabel#rowIcon, QLabel#stateIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            QLabel#title {{
                color: {theme.text};
                font-size: 14px;
                font-weight: 700;
            }}
            QLabel#sectionTitle {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#sectionSubtitle {{
                color: {theme.text_muted};
                font-size: 10px;
            }}
            QLabel#subtitle, QLabel#detailLabel, QLabel#footerLabel {{
                color: {theme.text_muted};
                font-size: 10px;
            }}
            QLabel#stateLabel {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 700;
            }}
            QFrame#stateChip {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 20px;
            }}
            QComboBox#interfaceCombo {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                padding: 10px 12px;
                min-height: 20px;
                color: {theme.text};
                selection-background-color: {theme.hover_bg};
            }}
            QComboBox#interfaceCombo::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox#interfaceCombo::down-arrow {{
                image: none;
                width: 0;
                height: 0;
            }}
            QComboBox#interfaceCombo QAbstractItemView {{
                background: {theme.surface_container_high};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                outline: none;
                padding: 6px;
                selection-background-color: {theme.hover_bg};
                selection-color: {theme.text};
            }}
            QPushButton#iconButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
                color: {theme.icon};
                font-family: "{self.material_font}";
                min-width: 42px;
                max-width: 42px;
                min-height: 42px;
                max-height: 42px;
            }}
            QPushButton#iconButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#primaryButton {{
                background: {theme.primary};
                border: none;
                border-radius: 14px;
                color: {theme.active_text};
                font-size: 12px;
                font-weight: 700;
                min-height: 42px;
                padding: 0 18px;
            }}
            QPushButton#primaryButton:hover {{
                background: {theme.primary_container};
                color: {theme.on_primary_container};
            }}
            QPushButton#secondaryButton, QPushButton#secondaryTextButton {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
                color: {theme.text};
                min-height: 38px;
                padding: 0 14px;
            }}
            QPushButton#secondaryButton:hover, QPushButton#secondaryTextButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#primaryButton:disabled, QPushButton#iconButton:disabled {{
                background: {theme.app_running_bg};
                color: {theme.inactive};
                border: 1px solid {theme.app_running_border};
            }}
            QCheckBox#settingCheck {{
                color: {theme.text};
                spacing: 10px;
            }}
            QCheckBox#settingCheck::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 1px solid {theme.chip_border};
                background: {theme.chip_bg};
            }}
            QCheckBox#settingCheck::indicator:checked {{
                background: {theme.primary};
                border: 1px solid {theme.primary};
            }}
            QListWidget#splitList {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 16px;
                padding: 6px;
                outline: none;
            }}
            QListWidget#splitList::item {{
                padding: 10px 10px;
                margin: 2px 0;
                border-radius: 12px;
            }}
            QListWidget#splitList::item:selected {{
                background: {theme.hover_bg};
                color: {theme.text};
            }}
            QFrame#stateChip[state="active"] {{
                background: {rgba(theme.primary_container, 0.74)};
                border: 1px solid {rgba(theme.primary, 0.36)};
            }}
            QFrame#stateChip[state="error"] {{
                background: {rgba(theme.error, 0.16)};
                border: 1px solid {rgba(theme.error, 0.30)};
            }}
            """
        )
        self.style().unpolish(self.state_chip)
        self.style().polish(self.state_chip)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()

    def _load_status(self) -> dict[str, str]:
        raw = run_script("vpn.sh", "--status")
        if not raw:
            return {"wireguard": "off", "wg_selected": ""}
        try:
            payload = json.loads(raw)
        except Exception:
            return {"wireguard": "off", "wg_selected": ""}
        return {
            "wireguard": str(payload.get("wireguard", "off")),
            "wg_selected": str(payload.get("wg_selected", "")),
        }

    def _load_interfaces(self) -> list[str]:
        raw = run_script("vpn.sh", "--interfaces")
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def refresh_state(self) -> None:
        if self._toggle_worker is not None and self._toggle_worker.isRunning():
            return
        status = self._load_status()
        interfaces = self._load_interfaces()
        service = load_vpn_service_settings()
        selected = (
            status.get("wg_selected", "")
            or str(service.get("preferred_interface", "")).strip()
            or ("wg0" if "wg0" in interfaces else (interfaces[0] if interfaces else ""))
        )
        active = status.get("wireguard") == "on"

        if selected and selected not in interfaces:
            interfaces.insert(0, selected)

        self._building_combo = True
        self.interface_combo.clear()
        self.interface_combo.addItems(interfaces)
        if selected:
            index = self.interface_combo.findText(selected)
            if index >= 0:
                self.interface_combo.setCurrentIndex(index)
        self.interface_combo.setEnabled(bool(interfaces))
        self._building_combo = False

        self._building_switch = True
        self.auto_start_checkbox.setChecked(bool(service.get("reconnect_on_login", False)))
        self._building_switch = False

        if not interfaces:
            self.state_icon.setText(material_icon("lock_open"))
            self.state_label.setText("No WireGuard configs found")
            self.detail_label.setText("Expected `.conf` files in /etc/wireguard.")
            self.state_chip.setProperty("state", "inactive")
            self.toggle_button.setEnabled(False)
            self.toggle_button.setText("Enable")
            return

        self.state_icon.setText(material_icon("lock" if active else "lock_open"))
        self.state_label.setText("Tunnel active" if active else "Tunnel inactive")
        self.detail_label.setText(f"Selected interface: {selected or interfaces[0]}")
        self.state_chip.setProperty("state", "active" if active else "inactive")
        self.toggle_button.setEnabled(True)
        self.toggle_button.setText("Disable" if active else "Enable")
        self._sync_split_actions()
        self.style().unpolish(self.state_chip)
        self.style().polish(self.state_chip)

    def _set_interface(self, iface: str) -> None:
        if self._building_combo or not iface:
            return
        save_vpn_service_setting("preferred_interface", iface)
        run_script_bg("vpn.sh", "--set-wg", iface)
        QTimer.singleShot(250, self.refresh_state)

    def _toggle_auto_start(self, enabled: bool) -> None:
        if self._building_switch:
            return
        iface = self.interface_combo.currentText().strip()
        if enabled and not iface:
            iface = "wg0"
        if iface:
            save_vpn_service_setting("preferred_interface", iface)
        save_vpn_service_setting("reconnect_on_login", bool(enabled))
        self.footer_label.setText(
            f"{iface or 'wg0'} will be enabled on session start."
            if enabled
            else "Automatic WireGuard startup disabled."
        )

    def _reload_split_tunnel_list(self) -> None:
        self.split_list.clear()
        if not self._split_tunnel_apps:
            placeholder = QListWidgetItem("No split-tunnel launchers yet.\nAdd an app, Flatpak, or custom binary.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.split_list.addItem(placeholder)
            self._sync_split_actions()
            return
        for entry in self._split_tunnel_apps:
            label = str(entry.get("label", "")).strip() or str(entry.get("target", "")).strip()
            kind = str(entry.get("kind", "")).strip()
            target = str(entry.get("target", "")).strip()
            item = QListWidgetItem(f"{label}\n{kind}: {target}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.split_list.addItem(item)
        self.split_list.setCurrentRow(0)
        self._sync_split_actions()

    def _sync_split_actions(self) -> None:
        has_apps = bool(self._split_tunnel_apps)
        has_selection = self._selected_split_tunnel_entry() is not None
        self.launch_bypass_button.setEnabled(has_selection)
        self.remove_bypass_button.setEnabled(has_selection)
        self.clear_bypass_button.setEnabled(has_apps)

    def _persist_split_tunnel_apps(self) -> None:
        self._split_tunnel_apps = normalize_split_tunnel_apps(self._split_tunnel_apps)
        save_split_tunnel_apps(self._split_tunnel_apps)
        self._reload_split_tunnel_list()

    def _add_split_tunnel_entry(
        self,
        kind: str,
        target: str,
        label: str,
        *,
        source_path: str = "",
        icon_name: str = "",
        comment: str = "",
        install_wrapper: bool = False,
    ) -> None:
        normalized_kind = kind.strip().lower()
        normalized_target = target.strip()
        normalized_label = label.strip() or normalized_target
        if not normalized_target:
            return
        wrapper_path = ""
        effective_source_path = source_path.strip()
        if install_wrapper and SPLIT_LAUNCHER.exists():
            wrapper_entry = {
                "kind": normalized_kind,
                "target": normalized_target,
                "label": normalized_label,
                "source_path": effective_source_path,
                "icon_name": icon_name.strip(),
                "comment": comment.strip(),
            }
            wrapper_entry, _ = prepare_wrapper_entry(wrapper_entry)
            effective_source_path = str(wrapper_entry.get("source_path", "")).strip()
            wrapper_path = str(write_wrapper_desktop(wrapper_entry))
        for index, entry in enumerate(self._split_tunnel_apps):
            if entry.get("kind") == normalized_kind and entry.get("target") == normalized_target:
                updated = {
                    "kind": normalized_kind,
                    "target": normalized_target,
                    "label": normalized_label,
                }
                if effective_source_path:
                    updated["source_path"] = effective_source_path
                if icon_name.strip():
                    updated["icon_name"] = icon_name.strip()
                if comment.strip():
                    updated["comment"] = comment.strip()
                if wrapper_path:
                    updated["wrapper_path"] = wrapper_path
                self._split_tunnel_apps[index] = updated
                self._persist_split_tunnel_apps()
                self.footer_label.setText(f"Updated split-tunnel launcher for {normalized_label}.")
                return
        added = {"kind": normalized_kind, "target": normalized_target, "label": normalized_label}
        if effective_source_path:
            added["source_path"] = effective_source_path
        if icon_name.strip():
            added["icon_name"] = icon_name.strip()
        if comment.strip():
            added["comment"] = comment.strip()
        if wrapper_path:
            added["wrapper_path"] = wrapper_path
        self._split_tunnel_apps.append(added)
        self._persist_split_tunnel_apps()
        self.footer_label.setText(f"Added split-tunnel launcher for {normalized_label}.")

    def _add_desktop_app(self) -> None:
        if self._desktop_apps_cache is None:
            self._desktop_apps_cache = scan_desktop_apps()
        if not self._desktop_apps_cache:
            QMessageBox.warning(self, "WireGuard", "No desktop applications were found.")
            return
        dialog = AppSelectionDialog(self.theme, self._desktop_apps_cache, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        apps = dialog.selected_apps()
        if not apps:
            return
        for app in apps:
            self._add_split_tunnel_entry(
                "desktop",
                app["desktop_id"],
                app["name"],
                source_path=str(app.get("source_path", "")),
                icon_name=str(app.get("icon_name", "")),
                comment=str(app.get("comment", "")),
                install_wrapper=True,
            )
        self.footer_label.setText(
            f"Installed {len(apps)} local app launcher{'s' if len(apps) != 1 else ''} in ~/.local/share/applications."
        )

    def _add_flatpak_app(self) -> None:
        if self._flatpak_apps_cache is None:
            self._flatpak_apps_cache = scan_flatpak_apps()
        if not self._flatpak_apps_cache:
            QMessageBox.warning(self, "WireGuard", "No Flatpak apps were found.")
            return
        dialog = AppSelectionDialog(
            self.theme,
            self._flatpak_apps_cache,
            title_text="Add Flatpak outside VPN",
            subtitle_text="Search installed Flatpaks and choose one or more entries to wrap.",
            placeholder_text="Type a Flatpak name or app id",
            add_button_text="Add selected Flatpaks",
            primary_label_key="name",
            secondary_parts=("app_id",),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        apps = dialog.selected_apps()
        if not apps:
            return
        for app in apps:
            self._add_split_tunnel_entry("flatpak", app["app_id"], app["name"], install_wrapper=True)
        self.footer_label.setText(
            f"Installed {len(apps)} local Flatpak launcher{'s' if len(apps) != 1 else ''} in ~/.local/share/applications."
        )

    def _add_binary_app(self) -> None:
        dialog = BinarySelectionDialog(self.theme, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        path, args_text, label = dialog.values()
        if not path:
            return
        command = shlex.join([path, *([part for part in shlex.split(args_text) if part] if args_text else [])])
        self._add_split_tunnel_entry("binary", command, label or Path(path).name, install_wrapper=True)

    def _selected_split_tunnel_entry(self) -> dict[str, str] | None:
        item = self.split_list.currentItem()
        if item is None:
            return None
        payload = item.data(Qt.ItemDataRole.UserRole)
        return payload if isinstance(payload, dict) else None

    def _remove_selected_split_app(self) -> None:
        entry = self._selected_split_tunnel_entry()
        if entry is None:
            return
        remove_wrapper_desktop(entry)
        self._split_tunnel_apps = [
            current
            for current in self._split_tunnel_apps
            if not (
                current.get("kind") == entry.get("kind")
                and current.get("target") == entry.get("target")
            )
        ]
        self._persist_split_tunnel_apps()
        self.footer_label.setText(f"Removed {entry.get('label', entry.get('target', 'launcher'))}.")

    def _clear_split_apps(self) -> None:
        if not self._split_tunnel_apps:
            return
        for entry in list(self._split_tunnel_apps):
            remove_wrapper_desktop(entry)
        removed_count = len(self._split_tunnel_apps)
        self._split_tunnel_apps = []
        self._persist_split_tunnel_apps()
        self.footer_label.setText(f"Removed {removed_count} split-tunnel app{'s' if removed_count != 1 else ''}.")

    def _launch_selected_split_app(self) -> None:
        entry = self._selected_split_tunnel_entry()
        if entry is None:
            return
        status = self._load_status()
        active = status.get("wireguard") == "on"
        iface = self.interface_combo.currentText().strip() or status.get("wg_selected", "").strip()
        label = str(entry.get("label", entry.get("target", "launcher"))).strip()
        if not active:
            if launch_direct_entry(entry):
                self.footer_label.setText(f"Launched {label}. WireGuard is currently inactive.")
            else:
                self.footer_label.setText(f"Failed to launch {label}.")
            return
        if not SPLIT_HELPER.exists():
            self.footer_label.setText("Missing vpn_bypass_helper.py helper.")
            return
        if shutil.which("pkexec") is None:
            self.footer_label.setText("pkexec is required to launch apps outside the tunnel.")
            return

        command = [
            "pkexec",
            sys.executable,
            str(SPLIT_HELPER),
            "--launch",
            "--mode",
            str(entry.get("kind", "desktop")),
            "--target",
            str(entry.get("target", "")),
            "--interface",
            iface,
            "--uid",
            str(os.getuid()),
            "--gid",
            str(os.getgid()),
            "--groups",
            ",".join(str(group_id) for group_id in os.getgroups()),
            "--home",
            str(Path.home()),
            "--user",
            os.environ.get("USER", "user"),
            "--display",
            os.environ.get("DISPLAY", ""),
            "--dbus-address",
            os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
            "--xauthority",
            os.environ.get("XAUTHORITY", ""),
            "--runtime-dir",
            os.environ.get("XDG_RUNTIME_DIR", ""),
            "--wayland-display",
            os.environ.get("WAYLAND_DISPLAY", ""),
            "--current-desktop",
            os.environ.get("XDG_CURRENT_DESKTOP", ""),
            "--desktop-session",
            os.environ.get("DESKTOP_SESSION", ""),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=45.0,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.footer_label.setText("Timed out waiting for the split-tunnel helper.")
            return
        except Exception as exc:
            self.footer_label.setText(f"Split-tunnel launch failed: {exc}")
            return

        if result.returncode == 0:
            self.footer_label.setText(f"Launched {label} outside WireGuard.")
            return
        message = (result.stderr or result.stdout).strip() or "Authentication may have been cancelled."
        self.footer_label.setText(message)

    def _toggle_selected(self) -> None:
        iface = self.interface_combo.currentText().strip()
        if not iface or (self._toggle_worker is not None and self._toggle_worker.isRunning()):
            return
        self.toggle_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.interface_combo.setEnabled(False)
        self.state_chip.setProperty("state", "inactive")
        self.state_icon.setText(material_icon("refresh"))
        self.state_label.setText("Waiting for authentication…")
        self.detail_label.setText(f"Applying changes for {iface}")
        self.footer_label.setText("Authenticate in the polkit dialog if prompted.")
        self.style().unpolish(self.state_chip)
        self.style().polish(self.state_chip)

        self._toggle_worker = VpnToggleWorker(iface)
        self._toggle_worker.completed.connect(self._handle_toggle_finished)
        self._toggle_worker.start()

    def _handle_toggle_finished(self, ok: bool, message: str) -> None:
        self._toggle_worker = None
        self.refresh_button.setEnabled(True)
        self.footer_label.setText(message)
        self.refresh_state()
        self.interface_combo.setEnabled(bool(self.interface_combo.count()))
        if not ok:
            self.state_chip.setProperty("state", "error")
            self.state_icon.setText(material_icon("lock_open"))
            self.state_label.setText("WireGuard command failed")
            self.detail_label.setText(message)
            self.style().unpolish(self.state_chip)
            self.style().polish(self.state_chip)
        self.toggle_button.setEnabled(bool(self.interface_combo.count()))


def main() -> int:
    if not service_enabled():
        return 0
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    app.setPalette(palette)

    popup = VpnControlPopup()
    popup.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
