import re


def run_text(cmd: list[str], timeout: float = 2.5) -> str:
    import subprocess
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


def parse_xrandr_state() -> list[dict]:
    output = run_text(["xrandr", "--query"])
    if not output:
        return []

    displays: list[dict] = []
    current: dict | None = None
    for line in output.splitlines():
        if not line.startswith(" "):
            current = None
            if " connected" not in line or "disconnected" in line:
                continue
            name = line.split()[0]
            primary = " connected primary" in line
            geom_match = re.search(r"(\d+x\d+)\+\d+\+\d+", line)
            orient_match = re.search(r"\b(normal|left|right|inverted)\b", line)
            current = {
                "name": name,
                "primary": primary,
                "enabled": bool(geom_match),
                "current_mode": geom_match.group(1) if geom_match else "",
                "current_refresh": "",
                "orientation": orient_match.group(1) if orient_match else "normal",
                "x": 0,
                "y": 0,
                "modes": [],
                "refresh_rates": {},
            }
            if geom_match:
                dims = geom_match.group(0)
                _, pos_x, pos_y = re.match(
                    r"(\d+x\d+)\+(-?\d+)\+(-?\d+)", dims
                ).groups()
                current["x"] = int(pos_x)
                current["y"] = int(pos_y)
            displays.append(current)
            continue
        if current is None:
            continue
        match = re.match(r"^\s+(\d+x\d+)\s+(.+)$", line)
        if not match:
            continue
        mode = match.group(1)
        current["modes"].append(mode)
        refreshes: list[str] = []
        for token in match.group(2).split():
            clean = token.replace("*", "").replace("+", "")
            if re.fullmatch(r"\d+(?:\.\d+)?", clean):
                refreshes.append(clean)
                if "*" in token:
                    current["current_refresh"] = clean
                    current["current_mode"] = mode
        current["refresh_rates"][mode] = refreshes

    for display in displays:
        if not display["current_mode"] and display["modes"]:
            display["current_mode"] = display["modes"][0]
        if display["current_mode"] and not display["enabled"]:
            display["enabled"] = True
    return displays