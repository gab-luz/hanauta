from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "theme"
PALETTE_FILE = STATE_DIR / "pyqt_palette.json"


def _normalize_hex(color: str, fallback: str) -> str:
    value = (color or "").strip()
    if not value.startswith("#"):
        value = f"#{value}"
    if len(value) != 7:
        return fallback
    try:
        int(value[1:], 16)
    except ValueError:
        return fallback
    return value.upper()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    normalized = _normalize_hex(color, "#000000")
    return (
        int(normalized[1:3], 16),
        int(normalized[3:5], 16),
        int(normalized[5:7], 16),
    )


def rgba(color: str, alpha: float) -> str:
    red, green, blue = _hex_to_rgb(color)
    clamped = max(0.0, min(1.0, alpha))
    return f"rgba({red}, {green}, {blue}, {clamped:.2f})"


def blend(color_a: str, color_b: str, ratio: float) -> str:
    ra, ga, ba = _hex_to_rgb(color_a)
    rb, gb, bb = _hex_to_rgb(color_b)
    t = max(0.0, min(1.0, ratio))
    red = int(ra + (rb - ra) * t)
    green = int(ga + (gb - ga) * t)
    blue = int(ba + (bb - ba) * t)
    return f"#{red:02X}{green:02X}{blue:02X}"


def relative_luminance(color: str) -> float:
    def channel(value: int) -> float:
        normalized = value / 255.0
        if normalized <= 0.03928:
            return normalized / 12.92
        return ((normalized + 0.055) / 1.055) ** 2.4

    red, green, blue = _hex_to_rgb(color)
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def pick_foreground(background: str, preferred: str, fallback: str) -> str:
    preferred_lum = relative_luminance(preferred)
    fallback_lum = relative_luminance(fallback)
    bg_lum = relative_luminance(background)
    preferred_contrast = (max(preferred_lum, bg_lum) + 0.05) / (min(preferred_lum, bg_lum) + 0.05)
    fallback_contrast = (max(fallback_lum, bg_lum) + 0.05) / (min(fallback_lum, bg_lum) + 0.05)
    return preferred if preferred_contrast >= fallback_contrast else fallback


@dataclass(frozen=True)
class ThemePalette:
    source: str
    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str
    secondary: str
    on_secondary: str
    tertiary: str
    on_tertiary: str
    background: str
    on_background: str
    surface: str
    on_surface: str
    surface_container: str
    surface_container_high: str
    surface_variant: str
    on_surface_variant: str
    outline: str
    error: str
    on_error: str
    use_matugen: bool

    @property
    def panel_bg(self) -> str:
        return rgba(self.surface_container, 0.84)

    @property
    def panel_border(self) -> str:
        return rgba(self.outline, 0.28)

    @property
    def chip_bg(self) -> str:
        return rgba(self.surface_container_high, 0.88)

    @property
    def chip_border(self) -> str:
        return rgba(self.outline, 0.24)

    @property
    def hover_bg(self) -> str:
        return rgba(self.primary, 0.14)

    @property
    def pressed_bg(self) -> str:
        return rgba(self.primary, 0.20)

    @property
    def accent_soft(self) -> str:
        return rgba(self.primary, 0.18)

    @property
    def active_text(self) -> str:
        return pick_foreground(self.primary, self.on_primary, "#101114")

    @property
    def text(self) -> str:
        return pick_foreground(self.surface_container_high, self.on_surface, "#FFFFFF")

    @property
    def text_muted(self) -> str:
        return rgba(pick_foreground(self.surface_container_high, self.on_surface_variant, self.on_surface), 0.78)

    @property
    def icon(self) -> str:
        return self.text

    @property
    def inactive(self) -> str:
        return rgba(self.on_surface_variant, 0.68)

    @property
    def tray_bg(self) -> str:
        return rgba(self.surface_container, 0.90)

    @property
    def battery_bg(self) -> str:
        return self.primary

    @property
    def battery_text(self) -> str:
        return self.active_text

    @property
    def workspace_focused(self) -> str:
        return self.primary

    @property
    def workspace_occupied(self) -> str:
        return rgba(self.on_surface, 0.32)

    @property
    def workspace_empty(self) -> str:
        return rgba(self.on_surface_variant, 0.18)

    @property
    def workspace_urgent(self) -> str:
        return self.error

    @property
    def equalizer(self) -> str:
        return self.primary

    @property
    def media_active_start(self) -> str:
        return rgba(self.primary_container, 0.96)

    @property
    def media_active_end(self) -> str:
        return rgba(blend(self.primary, self.secondary, 0.38), 0.96)

    @property
    def media_active_border(self) -> str:
        return rgba(self.primary, 0.72)

    @property
    def app_focused_bg(self) -> str:
        return rgba(self.primary, 0.18)

    @property
    def app_focused_border(self) -> str:
        return rgba(self.primary, 0.28)

    @property
    def app_running_bg(self) -> str:
        return rgba(self.on_surface, 0.06)

    @property
    def app_running_border(self) -> str:
        return rgba(self.outline, 0.16)

    @property
    def app_dot(self) -> str:
        return self.primary

    @property
    def separator(self) -> str:
        return rgba(self.outline, 0.22)


def _default_payload() -> dict[str, object]:
    return {
        "use_matugen": False,
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


def load_theme_palette() -> ThemePalette:
    defaults = _default_payload()
    payload = dict(defaults)
    try:
        payload.update(json.loads(PALETTE_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    if not bool(payload.get("use_matugen", False)):
        payload = dict(defaults)
    normalized = {
        key: (_normalize_hex(str(value), defaults[key]) if isinstance(defaults[key], str) and str(defaults[key]).startswith("#") else value)
        for key, value in payload.items()
    }
    for key, default in defaults.items():
        normalized.setdefault(key, default)
    normalized["use_matugen"] = bool(payload.get("use_matugen", False))
    return ThemePalette(**normalized)


def palette_mtime() -> float:
    try:
        return PALETTE_FILE.stat().st_mtime
    except OSError:
        return 0.0
