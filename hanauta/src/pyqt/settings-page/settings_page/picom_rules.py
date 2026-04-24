from __future__ import annotations

from pathlib import Path
import re


def ensure_picom_rule_files(
    picom_rules_dir: Path, rule_file_defaults: dict[Path, str]
) -> None:
    picom_rules_dir.mkdir(parents=True, exist_ok=True)
    for path, default_text in rule_file_defaults.items():
        if path.exists():
            continue
        path.write_text(default_text, encoding="utf-8")


def _escape_picom_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _parse_picom_matcher(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()
    prefixes = {
        "window_name_contains:": lambda value: (
            f"name *= '{_escape_picom_string(value)}'"
        ),
        "window_name:": lambda value: f"name = '{_escape_picom_string(value)}'",
        "class:": lambda value: f"class_g = '{_escape_picom_string(value)}'",
        "window_type:": lambda value: f"window_type = '{_escape_picom_string(value)}'",
        "raw:": lambda value: value,
    }
    for prefix, builder in prefixes.items():
        if lowered.startswith(prefix):
            return builder(stripped[len(prefix) :].strip())
    return stripped


def _load_picom_rule_list(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    parsed: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        matcher = _parse_picom_matcher(stripped)
        if matcher:
            parsed.append(matcher)
    return parsed


def _load_picom_opacity_rules(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    parsed: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lowered = stripped.lower()
        if lowered.startswith("opacity "):
            payload = stripped[len("opacity ") :].strip()
            amount_text, separator, matcher_text = payload.partition(":")
            if not separator:
                continue
            try:
                amount = int(float(amount_text.strip()))
            except ValueError:
                continue
            matcher = _parse_picom_matcher(matcher_text.strip())
            if matcher:
                parsed.append(f"{amount}:{matcher}")
            continue
        parsed.append(stripped)
    return parsed


def _format_picom_rule_block(key: str, entries: list[str]) -> str:
    lines = [f"{key} = ["]
    lines.extend(f'  "{entry}",' for entry in entries)
    lines.append("];")
    return "\n".join(lines)


def render_picom_rule_blocks(
    rule_files: dict[str, Path],
    picom_rules_dir: Path,
    rule_file_defaults: dict[Path, str],
) -> str:
    ensure_picom_rule_files(picom_rules_dir, rule_file_defaults)
    order = ("shadow-exclude", "rounded-corners-exclude", "opacity-rule", "fade-exclude")
    blocks: list[str] = []
    for key in order:
        path = rule_files.get(key)
        if path is None:
            continue
        entries = (
            _load_picom_opacity_rules(path)
            if key == "opacity-rule"
            else _load_picom_rule_list(path)
        )
        blocks.append(_format_picom_rule_block(key, entries))
    return "\n\n".join(blocks)


def build_default_picom_config(
    default_template: str,
    rule_files: dict[str, Path],
    picom_rules_dir: Path,
    rule_file_defaults: dict[Path, str],
) -> str:
    return default_template.format(
        picom_rule_blocks=render_picom_rule_blocks(
            rule_files, picom_rules_dir, rule_file_defaults
        )
    )


def sync_picom_rule_blocks(
    text: str,
    rule_files: dict[str, Path],
    picom_rules_dir: Path,
    rule_file_defaults: dict[Path, str],
) -> str:
    ensure_picom_rule_files(picom_rules_dir, rule_file_defaults)
    updated = text
    for key, path in rule_files.items():
        entries = (
            _load_picom_opacity_rules(path)
            if key == "opacity-rule"
            else _load_picom_rule_list(path)
        )
        block = _format_picom_rule_block(key, entries)
        pattern = re.compile(rf"(?ms)^\s*{re.escape(key)}\s*=\s*\[.*?^\s*\];")
        if pattern.search(updated):
            updated = pattern.sub(block, updated, count=1)
        else:
            anchor = "corner-radius-rules = [\n  \"88:name = 'PyQt Notification Center'\"\n];"
            if anchor in updated:
                updated = updated.replace(anchor, f"{anchor}\n{block}", 1)
            else:
                updated = f"{updated.rstrip()}\n\n{block}\n"
    return updated

