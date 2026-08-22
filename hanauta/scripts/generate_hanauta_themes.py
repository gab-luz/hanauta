#!/usr/bin/env python3
"""Standalone script to generate and install Hanauta native GTK + Qt themes.

Called by install.sh --hanauta-native-themes.
Can also be used directly after a Hanauta checkout.

Usage:
    python3 generate_hanauta_themes.py [--system] [--themes THEME_LIST]
                                       [--dest DIR] [--apply]

Defaults:
    --dest ~/.themes
    --themes hanauta_dark,hanauta_light
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    for candidate in [
        root / "src" / "pyqt" / "settings-page",
        root / "src",
    ]:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and install Hanauta native GTK + Qt themes"
    )
    parser.add_argument(
        "--themes",
        default="hanauta_dark,hanauta_light",
        help="Comma-separated list of theme keys to generate "
             "(default: hanauta_dark,hanauta_light)",
    )
    parser.add_argument(
        "--dest",
        default=os.path.join(os.path.expanduser("~"), ".themes"),
        help="Target directory for theme installation (default: ~/.themes)",
    )
    parser.add_argument(
        "--system",
        action="store_true",
        help="Also install system-wide to /usr/share/themes (uses sudo)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the first generated theme via gsettings immediately",
    )
    parser.add_argument(
        "--apply-qt",
        action="store_true",
        help="Generate Qt color schemes in qt5ct/qt6ct config dirs",
    )
    args = parser.parse_args()

    _ensure_src_on_path()
    from settings_page.theme_data import THEME_LIBRARY, THEMES_HOME
    from settings_page.theme_gtk import (
        _hanauta_gtk_css,
        _hanauta_gtk2_rc,
        _hanauta_qt5ct_colors,
        _hanauta_kvantum_theme,
        _write_index_theme,
        install_qt_color_scheme,
    )

    theme_keys = [k.strip() for k in args.themes.split(",") if k.strip()]
    dest_root = Path(args.dest).expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    generated = []

    for key in theme_keys:
        if key not in THEME_LIBRARY:
            print(f"Unknown theme key: {key}, skipping.")
            continue

        metadata = THEME_LIBRARY[key]
        theme_name = str(metadata["gtk_theme"])
        palette = dict(metadata["palette"])
        fonts = metadata.get("fonts", {})
        font_family = fonts.get("ui_font_family", "Rubik")
        mono_font_family = fonts.get("mono_font_family", "JetBrains Mono")
        theme_dir = dest_root / theme_name

        print(f"Generating theme: {metadata['label']} -> {theme_dir}")

        if theme_dir.exists():
            shutil.rmtree(theme_dir)

        for gtk_dir_name in ("gtk-2.0", "gtk-3.0", "gtk-4.0"):
            gtk_dir = theme_dir / gtk_dir_name
            gtk_dir.mkdir(parents=True, exist_ok=True)
            if gtk_dir_name == "gtk-2.0":
                (gtk_dir / "gtkrc").write_text(
                    _hanauta_gtk2_rc(palette,
                                    font_family=font_family,
                                    mono_font_family=mono_font_family),
                    encoding="utf-8"
                )
            else:
                (gtk_dir / "gtk.css").write_text(
                    _hanauta_gtk_css(palette,
                                    font_family=font_family,
                                    mono_font_family=mono_font_family),
                    encoding="utf-8"
                )

        icon_theme = str(metadata.get("icon_theme", "Papirus"))
        _write_index_theme(theme_dir, str(metadata["label"]), theme_name,
                           icon_theme=icon_theme)

        qt_dir = theme_dir / "qt"
        qt_dir.mkdir(parents=True, exist_ok=True)
        (qt_dir / "colors.conf").write_text(
            _hanauta_qt5ct_colors(palette), encoding="utf-8"
        )

        kvantum_dir = theme_dir / "Kvantum"
        kvantum_dir.mkdir(parents=True, exist_ok=True)
        kvantum_files = _hanauta_kvantum_theme(palette,
                                                font_family=font_family,
                                                mono_font_family=mono_font_family)
        for filename, content in kvantum_files.items():
            (kvantum_dir / filename).write_text(content, encoding="utf-8")

        generated.append((key, theme_name, palette))

        for gtk_dir_name in ("gtk-2.0", "gtk-3.0", "gtk-4.0"):
            ext = "gtkrc" if gtk_dir_name == "gtk-2.0" else "gtk.css"
            print(f"  GTK:   {gtk_dir_name}/{ext}")
        print("  Qt:    qt/colors.conf")
        print("  Kvantum: Kvantum/Kvantum.kvconfig")
        print()

    if args.system:
        for key, theme_name, palette in generated:
            theme_dir = dest_root / theme_name
            sys_dest = Path("/usr/share/themes") / theme_name
            print(f"Installing system-wide: {theme_name} -> {sys_dest}")
            subprocess.run(
                ["sudo", "rm", "-rf", str(sys_dest)], check=False
            )
            subprocess.run(
                ["sudo", "cp", "-a", str(theme_dir), str(sys_dest.parent)],
                check=False,
            )

    if args.apply_qt:
        for key, theme_name, palette in generated:
            fonts = THEME_LIBRARY[key].get("fonts", {})
            font_family = fonts.get("ui_font_family", "Rubik")
            mono_font_family = fonts.get("mono_font_family", "JetBrains Mono")
            print(f"Installing Qt color scheme for: {theme_name}")
            install_qt_color_scheme(theme_name, palette,
                                    font_family=font_family,
                                    mono_font_family=mono_font_family)

    if args.apply and generated:
        first_theme = generated[0][1]
        first_key = generated[0][0]
        color_scheme = THEME_LIBRARY[first_key].get("color_scheme", "prefer-dark")
        icon_theme = str(THEME_LIBRARY[first_key].get("icon_theme", "Papirus"))
        fonts = THEME_LIBRARY[first_key].get("fonts", {})
        font_family = fonts.get("ui_font_family", "Rubik")
        mono_font_family = fonts.get("mono_font_family", "JetBrains Mono")
        print(f"Applying GTK theme: {first_theme}")
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", first_theme],
            check=False,
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", color_scheme],
            check=False,
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", icon_theme],
            check=False,
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "font-name",
             f"{font_family} 10"],
            check=False,
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "monospace-font-name",
             f"{mono_font_family} 10"],
            check=False,
        )

        settings_ini = Path.home() / ".config" / "gtk-3.0" / "settings.ini"
        settings_ini.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_ini, "w") as f:
            f.write("[Settings]\n")
            f.write(f"gtk-theme-name={first_theme}\n")
            f.write(f"gtk-icon-theme-name={icon_theme}\n")
            f.write(f"gtk-font-name={font_family} 10\n")
            if "dark" in color_scheme:
                f.write("gtk-application-prefer-dark-theme=1\n")
            else:
                f.write("gtk-application-prefer-dark-theme=0\n")

        settings4_ini = Path.home() / ".config" / "gtk-4.0" / "settings.ini"
        settings4_ini.parent.mkdir(parents=True, exist_ok=True)
        with open(settings4_ini, "w") as f:
            f.write("[Settings]\n")
            f.write(f"gtk-theme-name={first_theme}\n")
            f.write(f"gtk-font-name={font_family} 10\n")

    print("Done.")


if __name__ == "__main__":
    main()
