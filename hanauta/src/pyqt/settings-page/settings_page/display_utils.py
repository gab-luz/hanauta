from __future__ import annotations


def resolution_area(mode: str) -> int:
    try:
        width, height = mode.split("x", 1)
        return int(width) * int(height)
    except Exception:
        return 0


def build_display_command(
    displays: list[dict], primary_name: str, layout_mode: str
) -> list[str]:
    cmd = ["xrandr"]
    ordered = sorted(
        displays, key=lambda item: (item["name"] != primary_name, item["name"])
    )
    previous_enabled: str | None = None
    for display in ordered:
        cmd.extend(["--output", str(display["name"])])
        if not display.get("enabled"):
            cmd.append("--off")
            continue
        resolution = str(display.get("resolution", "")).strip()
        modes = [str(mode) for mode in display.get("modes", [])]
        if resolution and modes and resolution not in modes:
            resolution = ""
        if not resolution and modes:
            resolution = sorted(modes, key=resolution_area, reverse=True)[0]
        if resolution:
            cmd.extend(["--mode", resolution])
        refresh = str(display.get("refresh", "")).strip()
        if refresh and refresh != "Auto":
            cmd.extend(["--rate", refresh])
        cmd.extend(["--rotate", str(display.get("orientation", "normal")) or "normal"])
        if display["name"] == primary_name:
            cmd.append("--primary")
        if previous_enabled and layout_mode == "extend":
            cmd.extend(["--right-of", previous_enabled])
        elif previous_enabled and layout_mode == "duplicate":
            cmd.extend(["--same-as", primary_name])
        previous_enabled = str(display["name"])
    return cmd


def normalize_display_orientation(value: object) -> str:
    orientation = str(value or "normal").strip().lower()
    if orientation in {"normal", "left", "right", "inverted"}:
        return orientation
    return "normal"

