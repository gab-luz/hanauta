import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]

from settings_page.settings_store import _atomic_write_json_file

PICOM_CONFIG_FILE = ROOT / "picom.conf"
PICOM_RULES_DIR = ROOT / "hanauta" / "config" / "picom"
PICOM_SHADOW_EXCLUDE_FILE = PICOM_RULES_DIR / "shadow-exclude.rules"
PICOM_ROUNDED_EXCLUDE_FILE = PICOM_RULES_DIR / "rounded-corners-exclude.rules"
PICOM_OPACITY_RULE_FILE = PICOM_RULES_DIR / "opacity.rules"
PICOM_FADE_EXCLUDE_FILE = PICOM_RULES_DIR / "fade-exclude.rules"

from settings_page.picom_presets import PICOM_DEFAULT_TEMPLATE, picom_rule_file_defaults

PICOM_RULE_FILE_DEFAULTS: dict[Path, str] = picom_rule_file_defaults(
    PICOM_SHADOW_EXCLUDE_FILE,
    PICOM_ROUNDED_EXCLUDE_FILE,
    PICOM_OPACITY_RULE_FILE,
    PICOM_FADE_EXCLUDE_FILE,
)


def _picom_rule_files() -> dict[str, Path]:
    return {
        "shadow-exclude": PICOM_SHADOW_EXCLUDE_FILE,
        "rounded-corners-exclude": PICOM_ROUNDED_EXCLUDE_FILE,
        "opacity-rule": PICOM_OPACITY_RULE_FILE,
        "fade-exclude": PICOM_FADE_EXCLUDE_FILE,
    }


def ensure_picom_rule_files() -> None:
    from settings_page.picom_rules import ensure_picom_rule_files as ensure_picom_rule_files_impl
    ensure_picom_rule_files_impl(PICOM_RULES_DIR, PICOM_RULE_FILE_DEFAULTS)


def render_picom_rule_blocks() -> str:
    from settings_page.picom_rules import render_picom_rule_blocks as render_picom_rule_blocks_impl
    return render_picom_rule_blocks_impl(
        _picom_rule_files(), PICOM_RULES_DIR, PICOM_RULE_FILE_DEFAULTS
    )


def build_default_picom_config() -> str:
    from settings_page.picom_rules import build_default_picom_config as build_default_picom_config_impl
    return build_default_picom_config_impl(
        PICOM_DEFAULT_TEMPLATE,
        _picom_rule_files(),
        PICOM_RULES_DIR,
        PICOM_RULE_FILE_DEFAULTS,
    )


def sync_picom_rule_blocks(text: str) -> str:
    from settings_page.picom_rules import sync_picom_rule_blocks as sync_picom_rule_blocks_impl
    return sync_picom_rule_blocks_impl(
        text, _picom_rule_files(), PICOM_RULES_DIR, PICOM_RULE_FILE_DEFAULTS
    )


def read_picom_text() -> str:
    ensure_picom_rule_files()
    try:
        return sync_picom_rule_blocks(PICOM_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return build_default_picom_config()


def parse_picom_settings(text: str) -> dict[str, object]:
    defaults: dict[str, object] = {
        "backend": "glx",
        "vsync": True,
        "use-damage": True,
        "shadow": True,
        "shadow-radius": 18,
        "shadow-opacity": 0.18,
        "shadow-offset-x": -12,
        "shadow-offset-y": -12,
        "fading": False,
        "active-opacity": 1.0,
        "inactive-opacity": 1.0,
        "corner-radius": 18,
        "transparent-clipping": False,
        "detect-rounded-corners": True,
    }

    def find_value(key: str) -> str | None:
        pattern = rf"(?m)^\s*{re.escape(key)}\s*=\s*(.+?);\s*$"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    parsed = dict(defaults)
    for key, default in defaults.items():
        value = find_value(key)
        if value is None:
            continue
        if isinstance(default, bool):
            parsed[key] = value.lower() == "true"
        elif isinstance(default, int):
            try:
                parsed[key] = int(float(value))
            except Exception:
                parsed[key] = default
        elif isinstance(default, float):
            try:
                parsed[key] = float(value)
            except Exception:
                parsed[key] = default
        else:
            parsed[key] = value.strip('"')
    return parsed


def format_picom_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, float):
        return (
            f"{value:.2f}".rstrip("0").rstrip(".")
            if "." in f"{value:.2f}"
            else str(value)
        )
    return str(value)


def update_picom_config(text: str, values: dict[str, object]) -> str:
    updated = text
    for key, value in values.items():
        line = f"{key} = {format_picom_value(value)};"
        pattern = rf"(?m)^\s*{re.escape(key)}\s*=\s*.+?;\s*$"
        if re.search(pattern, updated):
            updated = re.sub(pattern, line, updated)
        else:
            updated = f"{line}\n{updated}"
    return updated