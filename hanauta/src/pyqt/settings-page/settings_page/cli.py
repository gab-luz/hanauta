from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from settings_page.settings_defaults import ensure_settings_state, load_settings_state
from settings_page.startup import (
    restore_saved_displays,
    restore_saved_wallpaper,
    restore_saved_vpn,
)
from settings_page.marketplace import (
    marketplace_api_refresh_catalog_cache,
    marketplace_api_installed_plugins,
    marketplace_api_update_plugin,
    marketplace_api_update_all_plugins,
)
from settings_page.window import SettingsWindow

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--page",
        choices=(
            "overview",
            "appearance",
            "marketplace",
            "display",
            "energy",
            "audio",
            "notifications",
            "input",
            "startup",
            "privacy",
            "networking",
            "storage",
            "region",
            "bar",
            "services",
            "picom",
        ),
        default="appearance",
    )
    parser.add_argument("--service-section", default="")
    parser.add_argument("--ensure-settings", action="store_true")
    parser.add_argument("--restore-displays", action="store_true")
    parser.add_argument("--restore-wallpaper", action="store_true")
    parser.add_argument("--restore-vpn", action="store_true")
    parser.add_argument("--marketplace-refresh-catalog", action="store_true")
    parser.add_argument("--marketplace-update-all", action="store_true")
    parser.add_argument("--marketplace-update-plugin", default="")
    parser.add_argument("--marketplace-list-installed", action="store_true")
    parser.add_argument("--marketplace-list-catalog", action="store_true")
    args, _ = parser.parse_known_args(argv if argv is not None else sys.argv[1:])
    if args.ensure_settings:
        ensure_settings_state()
        return 0
    if args.restore_displays:
        restore_saved_displays()
        return 0
    if args.restore_wallpaper:
        restore_saved_wallpaper()
        return 0
    if args.restore_vpn:
        restore_saved_vpn()
        return 0
    if (
        args.marketplace_refresh_catalog
        or args.marketplace_update_all
        or str(args.marketplace_update_plugin).strip()
        or args.marketplace_list_installed
        or args.marketplace_list_catalog
    ):
        settings = load_settings_state()
        if args.marketplace_refresh_catalog:
            catalog, errors = marketplace_api_refresh_catalog_cache(settings)
            print(f"catalog entries: {len(catalog)}")
            if errors:
                print("catalog errors:")
                for row in errors:
                    print(f"- {row}")
        if args.marketplace_list_catalog:
            catalog_rows = (
                settings.get("marketplace", {}).get("catalog_cache", [])
                if isinstance(settings, dict)
                else []
            )
            if not isinstance(catalog_rows, list):
                catalog_rows = []
            for row in catalog_rows:
                if not isinstance(row, dict):
                    continue
                plugin_id = str(row.get("id", "")).strip()
                name = str(row.get("name", plugin_id)).strip() or plugin_id
                repo = str(row.get("repo", "")).strip()
                print(f"{plugin_id}\t{name}\t{repo}")
        if args.marketplace_list_installed:
            for row in marketplace_api_installed_plugins(settings):
                plugin_id = str(row.get("id", "")).strip()
                name = str(row.get("name", plugin_id)).strip() or plugin_id
                path = str(row.get("install_path", "")).strip()
                print(f"{plugin_id}\t{name}\t{path}")
        update_one = str(args.marketplace_update_plugin).strip()
        if update_one:
            ok, detail = marketplace_api_update_plugin(settings, update_one)
            print(detail)
            if not ok:
                return 1
        if args.marketplace_update_all:
            results = marketplace_api_update_all_plugins(settings)
            failures = 0
            for plugin_id, ok, detail in results:
                print(detail)
                if not ok:
                    failures += 1
            print(f"updated plugins: {len(results)} (failures: {failures})")
            return 1 if failures > 0 else 0
        return 0
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)
    window = SettingsWindow(
        initial_page=args.page, initial_service_section=str(args.service_section or "")
    )
    window.show()
    return app.exec()
