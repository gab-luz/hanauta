from __future__ import annotations

import configparser
from pathlib import Path


DEFAULT_NOTIFICATION_RULES: dict[str, object] = {
    "version": 1,
    "rules": {
        "kdeconnect_ignore_whatsapp_when_desktop_client_active": {
            "enabled": False,
            "source_app": "KDE Connect",
            "summary_contains": ["WhatsApp"],
            "body_contains": ["WhatsApp"],
            "processes": ["ferdium", "Ferdium", "whatsapp", "WhatsApp"],
            "action": "ignore",
        }
    },
}


def load_notification_rules_state_from_file(
    path: Path, defaults: dict[str, object] | None = None
) -> dict:
    rules_defaults = defaults if isinstance(defaults, dict) else DEFAULT_NOTIFICATION_RULES

    parser = configparser.ConfigParser()
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except Exception:
        parser = configparser.ConfigParser()
        parser.optionxform = str

    version = int(rules_defaults.get("version", 1) or 1)
    try:
        version = int(parser.get("meta", "version", fallback=str(version)))
    except Exception:
        version = int(rules_defaults.get("version", 1) or 1)

    defaults_rules = rules_defaults.get("rules", {})
    defaults_rules = defaults_rules if isinstance(defaults_rules, dict) else {}

    rules: dict[str, dict[str, object]] = {}
    for rule_id, defaults_row in defaults_rules.items():
        if not isinstance(defaults_row, dict):
            defaults_row = {}
        section = f"rule.{rule_id}"
        rules[str(rule_id)] = {
            "enabled": parser.getboolean(
                section, "enabled", fallback=bool(defaults_row.get("enabled", False))
            ),
            "source_app": parser.get(
                section, "source_app", fallback=str(defaults_row.get("source_app", ""))
            ).strip(),
            "summary_contains": [
                item.strip()
                for item in parser.get(
                    section,
                    "summary_contains",
                    fallback=",".join(defaults_row.get("summary_contains", [])),
                ).split(",")
                if item.strip()
            ],
            "body_contains": [
                item.strip()
                for item in parser.get(
                    section,
                    "body_contains",
                    fallback=",".join(defaults_row.get("body_contains", [])),
                ).split(",")
                if item.strip()
            ],
            "processes": [
                item.strip()
                for item in parser.get(
                    section,
                    "processes",
                    fallback=",".join(defaults_row.get("processes", [])),
                ).split(",")
                if item.strip()
            ],
            "action": parser.get(
                section, "action", fallback=str(defaults_row.get("action", "ignore"))
            ).strip()
            or "ignore",
        }

    for section in parser.sections():
        if not section.startswith("rule."):
            continue
        rule_id = section[5:]
        if rule_id in rules:
            continue
        rules[rule_id] = {
            "enabled": parser.getboolean(section, "enabled", fallback=False),
            "source_app": parser.get(section, "source_app", fallback="").strip(),
            "summary_contains": [
                item.strip()
                for item in parser.get(section, "summary_contains", fallback="").split(
                    ","
                )
                if item.strip()
            ],
            "body_contains": [
                item.strip()
                for item in parser.get(section, "body_contains", fallback="").split(",")
                if item.strip()
            ],
            "processes": [
                item.strip()
                for item in parser.get(section, "processes", fallback="").split(",")
                if item.strip()
            ],
            "action": parser.get(section, "action", fallback="ignore").strip()
            or "ignore",
        }

    return {"version": version, "rules": rules}


def save_notification_rules_state_to_file(
    path: Path, state: dict, defaults: dict[str, object] | None = None
) -> None:
    rules_defaults = defaults if isinstance(defaults, dict) else DEFAULT_NOTIFICATION_RULES

    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser["meta"] = {
        "version": str(int(state.get("version", rules_defaults.get("version", 1))))
    }
    rules = state.get("rules", {})
    if not isinstance(rules, dict):
        rules = {}
    for rule_id, rule in rules.items():
        if not isinstance(rule, dict):
            continue
        parser[f"rule.{rule_id}"] = {
            "enabled": "true" if bool(rule.get("enabled", False)) else "false",
            "source_app": str(rule.get("source_app", "")).strip(),
            "summary_contains": ",".join(
                [
                    str(item).strip()
                    for item in rule.get("summary_contains", [])
                    if str(item).strip()
                ]
            ),
            "body_contains": ",".join(
                [
                    str(item).strip()
                    for item in rule.get("body_contains", [])
                    if str(item).strip()
                ]
            ),
            "processes": ",".join(
                [
                    str(item).strip()
                    for item in rule.get("processes", [])
                    if str(item).strip()
                ]
            ),
            "action": str(rule.get("action", "ignore")).strip() or "ignore",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        parser.write(handle)

