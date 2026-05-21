from __future__ import annotations

from typing import Any


def marketplace_api_installed_plugins(settings: Any) -> list[dict[str, Any]]:
    return []


def marketplace_api_refresh_catalog_cache(
    settings: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    return [], []


def marketplace_api_update_plugin(
    settings: Any, plugin_id: str
) -> tuple[bool, str]:
    return False, "no-op stub"


def marketplace_api_update_all_plugins(
    settings: Any,
) -> list[tuple[str, bool, str]]:
    return []
