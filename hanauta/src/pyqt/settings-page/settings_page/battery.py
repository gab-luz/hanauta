from __future__ import annotations

from pathlib import Path


def detect_battery_base() -> Path | None:
    power_supply = Path("/sys/class/power_supply")
    if not power_supply.exists():
        return None
    for candidate in sorted(power_supply.iterdir()):
        if not candidate.is_dir() or not candidate.name.startswith("BAT"):
            continue
        type_path = candidate / "type"
        try:
            if (
                not type_path.exists()
                or type_path.read_text(encoding="utf-8").strip().lower() == "battery"
            ):
                return candidate
        except OSError:
            continue
    return None


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_int_file(path: Path) -> int | None:
    text = _read_text_file(path)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _first_available_int(base: Path, names: tuple[str, ...]) -> int | None:
    for name in names:
        value = _read_int_file(base / name)
        if value is not None:
            return value
    return None


def read_battery_snapshot() -> dict[str, object] | None:
    base = detect_battery_base()
    if base is None:
        return None
    capacity = _read_int_file(base / "capacity")
    status = _read_text_file(base / "status") or "Unknown"
    technology = _read_text_file(base / "technology") or "Unknown"
    manufacturer = _read_text_file(base / "manufacturer")
    model_name = _read_text_file(base / "model_name")
    cycle_count = _read_int_file(base / "cycle_count")
    full_now = _first_available_int(base, ("energy_full", "charge_full"))
    full_design = _first_available_int(
        base, ("energy_full_design", "charge_full_design")
    )
    health_percent: int | None = None
    if full_now is not None and full_design and full_design > 0:
        try:
            health_percent = max(
                1, min(100, int(round((full_now / full_design) * 100)))
            )
        except Exception:
            health_percent = None

    return {
        "path": str(base),
        "capacity": capacity if capacity is not None else 0,
        "status": status,
        "technology": technology,
        "manufacturer": manufacturer,
        "model_name": model_name,
        "cycle_count": cycle_count,
        "health_percent": health_percent,
    }
