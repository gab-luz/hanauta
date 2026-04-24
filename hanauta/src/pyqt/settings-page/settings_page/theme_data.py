from pathlib import Path

THEME_CHOICES = {"light", "dark", "custom", "wallpaper_aware"}
BUILTIN_THEME_KEYS = {"hanauta_dark", "hanauta_light"}
CUSTOM_THEME_KEYS = {"retrowave", "dracula", "caelestia"}

THEMES_HOME = Path.home() / ".themes"
SYSTEM_THEMES_HOME = Path("/usr/share/themes")

HANAUTA_DARK_PALETTE = {
    "source": "#D0BCFF",
    "primary": "#D0BCFF",
    "on_primary": "#381E72",
    "primary_container": "#4F378B",
    "on_primary_container": "#EADDFF",
    "secondary": "#CCC2DC",
    "on_secondary": "#332D41",
    "tertiary": "#EFB8C8",
    "on_tertiary": "#492532",
    "background": "#141218",
    "on_background": "#E6E0E9",
    "surface": "#141218",
    "on_surface": "#E6E0E9",
    "surface_container": "#211F26",
    "surface_container_high": "#2B2930",
    "surface_variant": "#49454F",
    "on_surface_variant": "#CAC4D0",
    "outline": "#938F99",
    "error": "#F2B8B5",
    "on_error": "#601410",
}

HANAUTA_FONT_PROFILE = {
    "ui_font_family": "Rubik",
    "display_font_family": "Rubik",
    "mono_font_family": "JetBrains Mono",
    "serif_font_family": "Playfair Display",
}

HANAUTA_LIGHT_PALETTE = {
    "source": "#8E4BC3",
    "primary": "#7A3EA8",
    "on_primary": "#FFFFFF",
    "primary_container": "#F2DAFF",
    "on_primary_container": "#300047",
    "secondary": "#745A77",
    "on_secondary": "#FFFFFF",
    "tertiary": "#9D3F73",
    "on_tertiary": "#FFFFFF",
    "background": "#FFF7FB",
    "on_background": "#221925",
    "surface": "#FFF7FB",
    "on_surface": "#221925",
    "surface_container": "#F8EDF5",
    "surface_container_high": "#F2E2EC",
    "surface_variant": "#E7D8E4",
    "on_surface_variant": "#655865",
    "outline": "#968797",
    "error": "#BA1A1A",
    "on_error": "#FFFFFF",
}

RETROWAVE_PALETTE = {
    "source": "#FC29A8",
    "primary": "#FC29A8",
    "on_primary": "#25031A",
    "primary_container": "#5C1650",
    "on_primary_container": "#FFD4EF",
    "secondary": "#03EDF9",
    "on_secondary": "#001F23",
    "tertiary": "#FFF951",
    "on_tertiary": "#292500",
    "background": "#1A1326",
    "on_background": "#F4EBFF",
    "surface": "#221A30",
    "on_surface": "#F4EBFF",
    "surface_container": "#2A2139",
    "surface_container_high": "#372D4B",
    "surface_variant": "#4B4061",
    "on_surface_variant": "#D3C6E8",
    "outline": "#8C7AA7",
    "error": "#FE4450",
    "on_error": "#FFFFFF",
}

DRACULA_PALETTE = {
    "source": "#BD93F9",
    "primary": "#BD93F9",
    "on_primary": "#221534",
    "primary_container": "#4C3E6E",
    "on_primary_container": "#F1E5FF",
    "secondary": "#8BE9FD",
    "on_secondary": "#032730",
    "tertiary": "#FF79C6",
    "on_tertiary": "#3B0F2B",
    "background": "#282A36",
    "on_background": "#F8F8F2",
    "surface": "#282A36",
    "on_surface": "#F8F8F2",
    "surface_container": "#2E3140",
    "surface_container_high": "#343746",
    "surface_variant": "#44475A",
    "on_surface_variant": "#CAD0F8",
    "outline": "#6272A4",
    "error": "#FF5555",
    "on_error": "#FFFFFF",
}

CAELESTIA_PALETTE = {
    "source": "#7171AC",
    "primary": "#C2C1FF",
    "on_primary": "#2A2A60",
    "primary_container": "#7171AC",
    "on_primary_container": "#FFFFFF",
    "secondary": "#C6C4E0",
    "on_secondary": "#2E2E44",
    "tertiary": "#F5B2E0",
    "on_tertiary": "#4E1E44",
    "background": "#131317",
    "on_background": "#E5E1E7",
    "surface": "#131317",
    "on_surface": "#E5E1E7",
    "surface_container": "#201F23",
    "surface_container_high": "#2A292E",
    "surface_variant": "#47464F",
    "on_surface_variant": "#C8C5D1",
    "outline": "#918F9A",
    "error": "#FFB4AB",
    "on_error": "#690005",
}

THEME_LIBRARY = {
    "hanauta_dark": {
        "label": "Hanauta Dark",
        "palette": HANAUTA_DARK_PALETTE,
        "fonts": HANAUTA_FONT_PROFILE,
        "gtk_theme": "Hanauta-Dark",
        "color_scheme": "prefer-dark",
    },
    "hanauta_light": {
        "label": "Hanauta Light",
        "palette": HANAUTA_LIGHT_PALETTE,
        "fonts": HANAUTA_FONT_PROFILE,
        "gtk_theme": "Hanauta-Light",
        "color_scheme": "prefer-light",
    },
    "retrowave": {
        "label": "Retrowave",
        "palette": RETROWAVE_PALETTE,
        "fonts": {
            "ui_font_family": "Noto Sans Mono",
            "display_font_family": "Noto Sans Mono",
            "mono_font_family": "Noto Sans Mono",
            "serif_font_family": "Noto Serif",
        },
        "gtk_theme": "Retrowave",
        "color_scheme": "prefer-dark",
    },
    "dracula": {
        "label": "Dracula",
        "palette": DRACULA_PALETTE,
        "fonts": {
            "ui_font_family": "Cantarell",
            "display_font_family": "Cantarell",
            "mono_font_family": "JetBrains Mono",
            "serif_font_family": "Noto Serif",
        },
        "gtk_theme": "Dracula",
        "color_scheme": "prefer-dark",
    },
    "caelestia": {
        "label": "Caelestia",
        "palette": CAELESTIA_PALETTE,
        "fonts": {
            "ui_font_family": "Inter",
            "display_font_family": "Inter",
            "mono_font_family": "JetBrains Mono",
            "serif_font_family": "Inter",
        },
        "gtk_theme": "Caelestia",
        "color_scheme": "prefer-dark",
    },
}