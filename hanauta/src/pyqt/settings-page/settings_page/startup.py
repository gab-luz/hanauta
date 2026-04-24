import shutil
import subprocess
import time
from pathlib import Path

from settings_page.settings_defaults import load_settings_state
from settings_page.xrandr import parse_xrandr_state
from settings_page.display_utils import build_display_command, normalize_display_orientation, resolution_area
from settings_page.wallpaper_sources import recursive_wallpaper_candidates as recursive_wallpaper_candidates_impl
from settings_page.wallpaper_sources import sync_wallpaper_source_preset as sync_wallpaper_source_preset_impl
from settings_page.wallpaper_render import draw_wallpaper_mode
from settings_page.i3_utils import sanitize_output_name
from settings_page.settings_store import _atomic_write_json_file

from PyQt6.QtGui import QImage, QColor, QPainter

ROOT = Path(__file__).resolve().parents[2].parents[1]
WALLPAPER_SCRIPT = ROOT / "hanauta" / "scripts" / "set_wallpaper.sh"
MATUGEN_SCRIPT = ROOT / "hanauta" / "scripts" / "run_matugen.sh"
CURRENT_WALLPAPER = Path.home() / ".wallpapers" / "wallpaper.png"
RENDERED_WALLPAPER_DIR = Path.home() / ".wallpapers" / "rendered"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def run_bg(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    try:
        subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
        )
    except Exception:
        pass


def restore_saved_wallpaper() -> None:
    settings = load_settings_state()
    appearance = settings.get("appearance", {})
    wallpaper_path = Path(str(appearance.get("wallpaper_path", ""))).expanduser()
    if not wallpaper_path.exists() or not wallpaper_path.is_file():
        wallpaper_path = CURRENT_WALLPAPER
    if not wallpaper_path.exists() or not wallpaper_path.is_file():
        return

    active_displays = [
        display for display in parse_xrandr_state() if display.get("enabled")
    ]
    if not active_displays:
        if WALLPAPER_SCRIPT.exists():
            run_bg([str(WALLPAPER_SCRIPT), str(wallpaper_path)])
        else:
            run_bg(["feh", "--bg-fill", str(wallpaper_path)])
        return

    source = QImage(str(wallpaper_path))
    if source.isNull():
        if WALLPAPER_SCRIPT.exists():
            run_bg([str(WALLPAPER_SCRIPT), str(wallpaper_path)])
        else:
            run_bg(["feh", "--bg-fill", str(wallpaper_path)])
        return

    fit_modes = appearance.get("wallpaper_fit_modes", {})
    if not isinstance(fit_modes, dict):
        fit_modes = {}

    rendered_paths: list[Path] = []
    RENDERED_WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
    for display in active_displays:
        mode_text = str(display.get("current_mode", ""))
        if "x" not in mode_text:
            continue
        try:
            width_text, height_text = mode_text.split("x", 1)
            width = int(width_text)
            height = int(height_text)
        except Exception:
            continue
        canvas = QImage(width, height, QImage.Format.Format_RGB32)
        canvas.fill(QColor("#0E0C12"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        draw_wallpaper_mode(
            painter,
            source,
            width,
            height,
            str(fit_modes.get(str(display.get("name", "")), "fill")),
        )
        painter.end()
        target = (
            RENDERED_WALLPAPER_DIR
            / f"{sanitize_output_name(str(display.get('name', 'display')))}.png"
        )
        canvas.save(str(target), "PNG")
        rendered_paths.append(target)

    if rendered_paths:
        run_bg(["feh", "--bg-fill", *[str(path) for path in rendered_paths]])
    elif WALLPAPER_SCRIPT.exists():
        run_bg([str(WALLPAPER_SCRIPT), str(wallpaper_path)])
    else:
        run_bg(["feh", "--bg-fill", str(wallpaper_path)])

    if bool(appearance.get("use_matugen_palette", False)) and MATUGEN_SCRIPT.exists():
        matugen_env = dict(os.environ)
        matugen_env["HANAUTA_SUPPRESS_MATUGEN_NOTIFY"] = "1"
        run_bg([str(MATUGEN_SCRIPT), str(wallpaper_path)], env=matugen_env)


def restore_saved_vpn() -> None:
    settings = load_settings_state()
    services = settings.get("services", {})
    if not isinstance(services, dict):
        return
    vpn = services.get("vpn_control", {})
    if not isinstance(vpn, dict):
        return
    if not bool(vpn.get("enabled", True)) or not bool(
        vpn.get("reconnect_on_login", False)
    ):
        return
    iface = str(vpn.get("preferred_interface", "")).strip() or "wg0"
    if not iface:
        return
    autoconnect_unit = "hanauta-wireguard-autoconnect.service"
    if shutil.which("systemctl") is not None:
        try:
            active = subprocess.run(
                ["systemctl", "is-active", "--quiet", autoconnect_unit],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            if active.returncode == 0:
                run_bg(
                    [
                        "notify-send",
                        "WireGuard",
                        f"{iface} active (via {autoconnect_unit})",
                    ]
                )
                return
            failed = subprocess.run(
                ["systemctl", "is-failed", "--quiet", autoconnect_unit],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            if failed.returncode == 0:
                run_bg(
                    [
                        "notify-send",
                        "WireGuard",
                        f"Auto-connect failed (check: sudo systemctl status {autoconnect_unit})",
                    ]
                )
                return
        except Exception:
            pass
    vpn_script = ROOT / "hanauta" / "scripts" / "vpn.sh"
    if not vpn_script.exists():
        return

    def run_text(cmd: list[str], timeout: float = 2.5) -> str:
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

    status_raw = run_text([str(vpn_script), "--status"])
    import json
    try:
        status = json.loads(status_raw) if status_raw else {}
    except Exception:
        status = {}
    if (
        isinstance(status, dict)
        and str(status.get("wireguard", "")).strip() == "on"
        and str(status.get("wg_selected", "")).strip() == iface
    ):
        run_bg(["notify-send", "WireGuard", f"{iface} active"])
        return
    run_bg([str(vpn_script), "--toggle-wg", iface])


def restore_saved_displays() -> None:
    settings = load_settings_state()
    startup_state = settings.get("startup", {})
    if isinstance(startup_state, dict) and not bool(
        startup_state.get("restore_displays", True)
    ):
        return

    display_state = settings.get("display", {})
    if not isinstance(display_state, dict):
        return
    saved_outputs = display_state.get("outputs", [])
    if not isinstance(saved_outputs, list) or not saved_outputs:
        return

    required_enabled_outputs = {
        str(item.get("name", "")).strip()
        for item in saved_outputs
        if isinstance(item, dict) and bool(item.get("enabled", True))
    }
    required_enabled_outputs.discard("")
    if not required_enabled_outputs:
        return

    max_attempts = 10
    retry_delay_sec = 1.2
    for _attempt in range(max_attempts):
        current = parse_xrandr_state()
        if not current:
            time.sleep(retry_delay_sec)
            continue
        available = {str(item.get("name", "")): item for item in current}
        if required_enabled_outputs - set(available):
            time.sleep(retry_delay_sec)
            continue

        restored: list[dict] = []
        for saved in saved_outputs:
            if not isinstance(saved, dict):
                continue
            name = str(saved.get("name", "")).strip()
            if not name or name not in available:
                continue
            current_item = available[name]
            restored.append(
                {
                    "name": name,
                    "enabled": bool(
                        saved.get("enabled", current_item.get("enabled", True))
                    ),
                    "resolution": str(
                        saved.get("resolution", current_item.get("current_mode", ""))
                    ),
                    "refresh": str(saved.get("refresh", "Auto")),
                    "orientation": normalize_display_orientation(
                        saved.get(
                            "orientation", current_item.get("orientation", "normal")
                        )
                    ),
                    "modes": list(current_item.get("modes", [])),
                }
            )
            if restored and restored[-1]["resolution"] not in restored[-1]["modes"]:
                modes = [str(mode) for mode in restored[-1]["modes"]]
                restored[-1]["resolution"] = (
                    sorted(modes, key=resolution_area, reverse=True)[0] if modes else ""
                )
        if not restored:
            time.sleep(retry_delay_sec)
            continue

        enabled = [display for display in restored if display.get("enabled")]
        if not enabled:
            return
        primary_name = str(display_state.get("primary", "")).strip() or str(
            enabled[0]["name"]
        )
        if primary_name not in {str(display["name"]) for display in enabled}:
            primary_name = str(enabled[0]["name"])
        layout_mode = str(display_state.get("layout_mode", "extend"))
        if layout_mode not in {"extend", "duplicate"}:
            layout_mode = "extend"

        if layout_mode == "duplicate" and len(enabled) > 1:
            common_modes = set(str(mode) for mode in enabled[0].get("modes", []))
            for display in enabled[1:]:
                common_modes &= set(str(mode) for mode in display.get("modes", []))
            if not common_modes:
                layout_mode = "extend"
            else:
                primary_display = next(
                    display
                    for display in enabled
                    if str(display["name"]) == primary_name
                )
                if str(primary_display.get("resolution", "")) not in common_modes:
                    primary_display["resolution"] = sorted(
                        common_modes, key=resolution_area, reverse=True
                    )[0]
                for display in enabled:
                    display["resolution"] = primary_display["resolution"]
                    if str(display["name"]) != primary_name:
                        display["refresh"] = "Auto"

        import subprocess
        cmd = build_display_command(restored, primary_name, layout_mode)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            time.sleep(retry_delay_sec)
            continue

        time.sleep(0.35)
        applied = {str(item.get("name", "")): item for item in parse_xrandr_state()}
        if not applied:
            return
        mismatch = False
        for display in enabled:
            name = str(display["name"])
            if name not in applied:
                mismatch = True
                break
            want = normalize_display_orientation(display.get("orientation", "normal"))
            got = normalize_display_orientation(
                applied[name].get("orientation", "normal")
            )
            if got != want:
                mismatch = True
                break
        if not mismatch:
            return
        time.sleep(retry_delay_sec)


def wallpaper_candidates(folder: Path) -> list[Path]:
    return recursive_wallpaper_candidates_impl(folder, IMAGE_SUFFIXES)


def sync_wallpaper_source_preset(source_key: str) -> tuple[bool, str, Path | None]:
    return sync_wallpaper_source_preset_impl(
        source_key,
        cache_root=ROOT / "hanauta" / "vendor" / "wallpaper-sources",
        community_root=ROOT / "hanauta" / "walls" / "community",
        image_suffixes=IMAGE_SUFFIXES,
    ).split("/", 1)