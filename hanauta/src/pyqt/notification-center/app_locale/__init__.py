from __future__ import annotations

import json
import os
from pathlib import Path

_LOCALE_DIR = Path(__file__).resolve().parent
_CACHE: dict[str, dict[str, str]] = {}


def _detect_lang() -> str:
    lc = (
        os.environ.get("LC_ALL")
        or os.environ.get("LANG")
        or os.environ.get("LC_MESSAGES")
        or "en"
    ).lower()
    if lc.startswith("pt"):
        return "pt-br"
    if lc.startswith("ru"):
        return "ru-ru"
    if lc.startswith("es"):
        return "es-la"
    return "en-us"


def _load_locale(lang: str) -> dict[str, str]:
    if lang in _CACHE:
        return _CACHE[lang]
    path = _LOCALE_DIR / f"{lang}.json"
    if not path.exists():
        path = _LOCALE_DIR / "en-us.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _CACHE[lang] = data
        return data
    except Exception:
        fallback = _LOCALE_DIR / "en-us.json"
        data = json.loads(fallback.read_text(encoding="utf-8"))
        _CACHE[lang] = data
        return data


_LANG = _detect_lang()
_TRANSLATIONS = _load_locale(_LANG)


def t(key: str, **kwargs: object) -> str:
    text = _TRANSLATIONS.get(key, key)
    if kwargs:
        try:
            return str(text).format(**{
                k: str(v) for k, v in kwargs.items()
            })
        except (KeyError, ValueError):
            return str(text)
    return str(text)
