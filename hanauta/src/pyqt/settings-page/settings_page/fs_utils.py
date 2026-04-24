from __future__ import annotations

import os
import shutil
from pathlib import Path


def directory_size_bytes(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
    except OSError:
        return 0
    return total


def filesystem_usage_bytes(path: Path) -> tuple[int, int, int]:
    target = path.expanduser().resolve()
    while not target.exists() and target != target.parent:
        target = target.parent
    try:
        stats = os.statvfs(str(target))
        block_size = int(stats.f_frsize or stats.f_bsize or 4096)
        total = int(stats.f_blocks) * block_size
        free = int(stats.f_bavail) * block_size
        used = max(0, total - free)
        return total, used, free
    except Exception:
        usage = shutil.disk_usage(str(target))
        return int(usage.total), int(usage.used), int(usage.free)

