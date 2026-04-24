from __future__ import annotations

import json
from pathlib import Path


SETTINGS_FILE = (
    Path.home()
    / ".local"
    / "state"
    / "hanauta"
    / "notification-center"
    / "settings.json"
)


def _normalize_lang(lang: str) -> str:
    value = str(lang or "").strip()
    if not value:
        return ""
    return value.replace("_", "-").strip()


def load_settings_state() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_profile_state(settings: dict | None = None) -> dict:
    payload = settings if isinstance(settings, dict) else load_settings_state()
    raw = payload.get("profile", {}) if isinstance(payload, dict) else {}
    profile = dict(raw) if isinstance(raw, dict) else {}

    profile["first_name"] = str(profile.get("first_name", "")).strip()
    profile["nickname"] = str(profile.get("nickname", "")).strip()

    pronunciations_raw = profile.get("pronunciations", [])
    pronunciations: list[dict[str, str]] = []
    if isinstance(pronunciations_raw, list):
        for row in pronunciations_raw:
            if not isinstance(row, dict):
                continue
            lang = _normalize_lang(str(row.get("lang", row.get("language", ""))))
            spoken_name = str(row.get("spoken_name", row.get("spoken", ""))).strip()
            new_email_phrase = str(
                row.get("new_email_phrase", row.get("email_new_phrase", ""))
            ).strip()
            pronunciations.append(
                {
                    "lang": lang,
                    "spoken_name": spoken_name,
                    "new_email_phrase": new_email_phrase,
                }
            )
    profile["pronunciations"] = pronunciations
    return profile


def preferred_user_name(profile: dict | None) -> str:
    if not isinstance(profile, dict):
        return ""
    nickname = str(profile.get("nickname", "")).strip()
    if nickname:
        return nickname
    return str(profile.get("first_name", "")).strip()


def profile_entry_for_language(
    profile: dict | None, language_code: str
) -> dict[str, str] | None:
    if not isinstance(profile, dict):
        return None
    pronunciations = profile.get("pronunciations", [])
    if not isinstance(pronunciations, list):
        return None
    wanted = _normalize_lang(language_code).lower()
    if not wanted:
        return None
    wanted_prefix = wanted.split("-", 1)[0]

    best_prefix_match: dict[str, str] | None = None
    for row in pronunciations:
        if not isinstance(row, dict):
            continue
        lang = _normalize_lang(str(row.get("lang", ""))).lower()
        if not lang:
            continue
        if lang == wanted:
            return {
                "lang": lang,
                "spoken_name": str(row.get("spoken_name", "")).strip(),
                "new_email_phrase": str(row.get("new_email_phrase", "")).strip(),
            }
        if best_prefix_match is None and lang.split("-", 1)[0] == wanted_prefix:
            best_prefix_match = {
                "lang": lang,
                "spoken_name": str(row.get("spoken_name", "")).strip(),
                "new_email_phrase": str(row.get("new_email_phrase", "")).strip(),
            }
    return best_prefix_match


def spoken_name(profile: dict | None, *, language_code: str = "") -> str:
    entry = profile_entry_for_language(profile, language_code) if language_code else None
    if entry and entry.get("spoken_name", "").strip():
        return str(entry.get("spoken_name", "")).strip()
    return preferred_user_name(profile)


def format_new_email_interrupt_phrase(
    profile: dict | None,
    *,
    language_code: str = "en",
    fallback_template: str = "{user}, sorry to interrupt you — you got a new email.",
) -> str:
    user = preferred_user_name(profile)
    entry = profile_entry_for_language(profile, language_code) if language_code else None
    template = str(entry.get("new_email_phrase", "")).strip() if entry else ""
    if not template:
        template = fallback_template
    try:
        return template.format(user=user)
    except Exception:
        return fallback_template.format(user=user)
