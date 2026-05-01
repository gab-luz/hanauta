#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thin entrypoint for Hanauta Settings.

The Settings window implementation lives in `settings_page/window.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    src_root = Path(__file__).resolve().parents[2]
    if str(src_root) not in sys.path:
        sys.path.append(str(src_root))


def main(argv: list[str] | None = None) -> int:
    _ensure_src_on_path()
    from settings_page.cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

