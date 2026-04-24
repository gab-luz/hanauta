from __future__ import annotations


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

