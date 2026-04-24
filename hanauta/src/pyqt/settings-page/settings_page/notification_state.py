from pathlib import Path
from settings_page.settings_store import save_settings_state
from settings_page.settings_defaults import load_settings_state
from settings_page.notification_rules import (
    DEFAULT_NOTIFICATION_RULES,
    load_notification_rules_state_from_file,
    save_notification_rules_state_to_file,
)


NOTIFICATION_RULES_FILE = (
    Path.home() / ".local" / "state" / "hanauta" / "notification-rules.ini"
)


def load_notification_rules_state() -> dict:
    return load_notification_rules_state_from_file(
        NOTIFICATION_RULES_FILE, defaults=DEFAULT_NOTIFICATION_RULES
    )


def save_notification_rules_state(state: dict) -> None:
    save_notification_rules_state_to_file(
        NOTIFICATION_RULES_FILE, state, defaults=DEFAULT_NOTIFICATION_RULES
    )


def ensure_settings_state() -> None:
    save_settings_state(load_settings_state())