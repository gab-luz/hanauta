from __future__ import annotations

from pathlib import Path

from notif_center.utils import run_script


def hex_to_rgba(color: str, alpha: float) -> str:
    color = color.lstrip("#")
    if len(color) != 6:
        return f"rgba(208, 188, 255, {alpha:.2f})"
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.2f})"


def darken_hex(color: str, amount: float) -> str:
    color = color.lstrip("#")
    if len(color) != 6:
        return "#4d4458"
    red = max(0, min(255, int(int(color[0:2], 16) * (1.0 - amount))))
    green = max(0, min(255, int(int(color[2:4], 16) * (1.0 - amount))))
    blue = max(0, min(255, int(int(color[4:6], 16) * (1.0 - amount))))
    return f"#{red:02X}{green:02X}{blue:02X}"


def extract_cover_palette(
    cover_path: Path, fallback_color: str = "#D0BCFF"
) -> tuple[str, str, str, str] | None:
    colors_raw = run_script("cover_colors.sh", "colors")
    colors = [color for color in colors_raw.split() if color.startswith("#")][:6]
    if len(colors) < 3:
        return None
    center = hex_to_rgba(colors[0], 0.26)
    mid = hex_to_rgba(colors[min(2, len(colors) - 1)], 0.58)
    border = darken_hex(colors[1], 0.12)
    accent = colors[min(4, len(colors) - 1)]
    return center, mid, border, accent
