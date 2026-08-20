#!/usr/bin/env python3
"""Collect system state for hanauta-service with timeouts on each script."""

import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path.home() / ".config" / "i3" / "hanauta" / "scripts"
TIMEOUT = 2.0


def run_script(name: str, *args: str) -> str:
    path = SCRIPTS_DIR / name
    if not path.exists():
        return ""
    try:
        res = subprocess.run(
            [str(path), *args], capture_output=True, text=True, timeout=TIMEOUT,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def main() -> None:
    bt = run_script("bluetooth", "state")
    rs = run_script("redshift", "state")
    cf = run_script("caffeine.sh", "status")
    br = run_script("brightness.sh", "br")
    vol = run_script("volume.sh", "vol")
    ph = run_script("phone_info.sh")
    cs = run_script("color_scheme.sh")

    state = {
        "bluetooth": bt if bt == "on" else "off",
        "redshift": rs if rs == "on" else "off",
        "caffeine": cf if cf == "on" else "off",
        "brightness": int(br) if br and br.isdigit() else 0,
        "volume": int(vol) if vol and vol.isdigit() else 0,
        "color_scheme": cs if cs in ("dark", "light") else "dark",
    }

    if ph:
        try:
            state["phone"] = json.loads(ph)
        except Exception:
            state["phone"] = {}
    else:
        state["phone"] = {}

    json.dump(state, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
