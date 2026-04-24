import shutil
import subprocess
from pathlib import Path

from settings_page.theme_data import HANAUTA_FONT_PROFILE, THEME_LIBRARY, THEMES_HOME


def selected_theme_key(settings_state: dict) -> str:
    appearance = settings_state.get("appearance", {})
    from settings_page.theme_data import THEME_CHOICES, CUSTOM_THEME_KEYS
    choice = str(appearance.get("theme_choice", "dark")).strip().lower()
    if choice == "custom":
        custom_theme = (
            str(appearance.get("custom_theme_id", "retrowave")).strip().lower()
        )
        return custom_theme if custom_theme in CUSTOM_THEME_KEYS else "retrowave"
    if choice == "light":
        return "hanauta_light"
    return "hanauta_dark"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _copytree_clean(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", ".github", "node_modules", "__pycache__"),
        dirs_exist_ok=False,
    )


def _hanauta_gtk_css(palette: dict[str, str]) -> str:
    return (
        f"""
@define-color theme_bg_color {palette["background"]};
@define-color theme_fg_color {palette["on_surface"]};
@define-color theme_base_color {palette["surface_container"]};
@define-color theme_text_color {palette["on_surface"]};
@define-color theme_selected_bg_color {palette["primary"]};
@define-color theme_selected_fg_color {palette["on_primary"]};
@define-color borders {palette["outline"]};
@define-color accent_color {palette["primary"]};
@define-color accent_bg_color {palette["primary"]};
@define-color accent_fg_color {palette["on_primary"]};
@define-color headerbar_bg_color {palette["surface_container_high"]};
@define-color headerbar_fg_color {palette["on_surface"]};
@define-color window_bg_color {palette["background"]};
@define-color window_fg_color {palette["on_surface"]};

window, dialog, .background {{
  background-color: @theme_bg_color;
  color: @theme_fg_color;
}}

headerbar, .titlebar {{
  background-image: none;
  background-color: @headerbar_bg_color;
  color: @headerbar_fg_color;
  border-bottom: 1px solid @borders;
  box-shadow: none;
}}

button, entry, textview, spinbutton, combobox, scale trough, progressbar trough {{
  border-radius: 12px;
  border: 1px solid alpha(@borders, 0.75);
  background-image: none;
  box-shadow: none;
}}

button {{
  background-color: {palette["surface_container_high"]};
  color: {palette["on_surface"]};
}}

button:hover {{
  background-color: {palette["surface_variant"]};
}}

button.suggested-action, button:checked, switch:checked slider {{
  background-color: {palette["primary"]};
  color: {palette["on_primary"]};
}}

entry, textview, spinbutton, combobox {{
  background-color: {palette["surface_container"]};
  color: {palette["on_surface"]};
  caret-color: {palette["primary"]};
}}

selection, *:selected {{
  background-color: {palette["primary"]};
  color: {palette["on_primary"]};
}}

menu, popover {{
  background-color: {palette["surface_container_high"]};
  color: {palette["on_surface"]};
  border: 1px solid alpha(@borders, 0.85);
}}

scrollbar slider {{
  min-width: 10px;
  min-height: 10px;
  border-radius: 999px;
  background-color: alpha({palette["primary"]}, 0.65);
}}

progressbar progress, scale highlight {{
  border-radius: 999px;
  background-color: {palette["primary"]};
}}
""".strip()
        + "\n"
    )


def _write_index_theme(theme_dir: Path, display_name: str, gtk_theme: str) -> None:
    _ensure_parent(theme_dir / "index.theme")
    (theme_dir / "index.theme").write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=X-GNOME-Metatheme",
                f"Name={display_name}",
                "Comment=Hanauta managed theme",
                "Encoding=UTF-8",
                "",
                "[X-GNOME-Metatheme]",
                f"GtkTheme={gtk_theme}",
                "IconTheme=Adwaita",
                "CursorTheme=Adwaita",
                "ButtonLayout=menu:minimize,maximize,close",
                "",
            ]
        ),
        encoding="utf-8",
    )


def ensure_builtin_hanauta_gtk_theme(theme_key: str) -> str:
    metadata = THEME_LIBRARY[theme_key]
    theme_name = str(metadata["gtk_theme"])
    palette = dict(metadata["palette"])
    theme_dir = THEMES_HOME / theme_name
    for gtk_dir_name in ("gtk-3.0", "gtk-4.0"):
        gtk_dir = theme_dir / gtk_dir_name
        gtk_dir.mkdir(parents=True, exist_ok=True)
        (gtk_dir / "gtk.css").write_text(_hanauta_gtk_css(palette), encoding="utf-8")
    _write_index_theme(theme_dir, str(metadata["label"]), theme_name)
    return theme_name


def ensure_dracula_gtk_theme() -> str:
    from settings_page.theme_data import THEME_LIBRARY
    metadata = THEME_LIBRARY["dracula"]
    target = THEMES_HOME / str(metadata["gtk_theme"])
    ROOT = Path(__file__).resolve().parents[2].parents[1]
    source = ROOT / "hanauta" / "vendor" / "themes" / "dracula-gtk"
    if not target.exists():
        _copytree_clean(source, target)
    return str(metadata["gtk_theme"])


def ensure_retrowave_gtk_theme() -> str:
    from settings_page.theme_data import THEME_LIBRARY
    metadata = THEME_LIBRARY["retrowave"]
    ROOT = Path(__file__).resolve().parents[2].parents[1]
    source = (
        ROOT / "hanauta" / "vendor" / "themes" / "retrowave-theme" / "src" / "retrowave"
    )
    target = THEMES_HOME / str(metadata["gtk_theme"])
    if target.exists() or target.is_symlink():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "index.theme", target / "index.theme")
    if (source / "gtk-2.0").exists():
        _copytree_clean(source / "gtk-2.0", target / "gtk-2.0")
    gtk3_source = source / "gtk-3.0"
    gtk3_target = target / "gtk-3.0"
    gtk3_target.mkdir(parents=True, exist_ok=True)
    if (gtk3_source / "assets").exists():
        _copytree_clean(gtk3_source / "assets", gtk3_target / "assets")
    subprocess.run(
        [
            "sassc",
            "-I",
            str(gtk3_source),
            str(gtk3_source / "gtk.scss"),
            str(gtk3_target / "gtk.css"),
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    gtk4_target = target / "gtk-4.0"
    gtk4_target.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(gtk3_target / "gtk.css", gtk4_target / "gtk.css")
    except OSError:
        pass
    return str(metadata["gtk_theme"])


def ensure_theme_installed(theme_key: str) -> str:
    THEMES_HOME.mkdir(parents=True, exist_ok=True)
    if theme_key == "retrowave":
        return ensure_retrowave_gtk_theme()
    if theme_key == "dracula":
        return ensure_dracula_gtk_theme()
    return ensure_builtin_hanauta_gtk_theme(theme_key)


def apply_gtk_theme(
    theme_name: str, color_scheme: str = "prefer-dark", icon_theme: str = ""
) -> None:
    ROOT = Path(__file__).resolve().parents[2].parents[1]
    cmd = ["bash", str(ROOT / "hanauta" / "scripts" / "set_theme.sh"), theme_name]
    if icon_theme:
        cmd.append(icon_theme)
    else:
        cmd.append("")
    cmd.append(color_scheme)
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def sync_static_theme_from_settings(
    settings_state: dict, apply_gtk: bool = False
) -> str:
    from settings_page.theme_data import THEME_LIBRARY
    from settings_page.settings_store import _atomic_write_json_file
    from settings_page.settings_store import PYQT_THEME_FILE
    theme_key = selected_theme_key(settings_state)
    metadata = THEME_LIBRARY[theme_key]
    write_pyqt_palette(
        dict(metadata["palette"]),
        use_matugen=False,
        fonts=dict(metadata.get("fonts", HANAUTA_FONT_PROFILE)),
    )
    from settings_page.settings_store import PYQT_THEME_DIR
    PYQT_THEME_DIR.mkdir(parents=True, exist_ok=True)
    if apply_gtk:
        theme_name = ensure_theme_installed(theme_key)
        apply_gtk_theme(theme_name, str(metadata.get("color_scheme", "prefer-dark")))
    return theme_key


def write_pyqt_palette(
    palette: dict[str, str],
    use_matugen: bool = False,
    fonts: dict[str, str] | None = None,
) -> None:
    from settings_page.settings_store import PYQT_THEME_FILE, _atomic_write_json_file
    from settings_page.settings_store import PYQT_THEME_DIR
    PYQT_THEME_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"use_matugen": bool(use_matugen)}
    payload.update(palette)
    if fonts:
        payload.update(fonts)
    _atomic_write_json_file(PYQT_THEME_FILE, payload)


def write_default_pyqt_palette(use_matugen: bool = False) -> None:
    from settings_page.theme_data import HANAUTA_DARK_PALETTE
    write_pyqt_palette(HANAUTA_DARK_PALETTE, use_matugen=use_matugen)