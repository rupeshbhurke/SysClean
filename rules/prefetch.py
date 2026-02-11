"""
Rule: Prefetch Files
Scans C:\\Windows\\Prefetch for .pf files.
These are safe to delete — Windows recreates them as needed.
"""

from __future__ import annotations

import os
import glob
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "prefetch"
display_name = "Prefetch Files"
description = "Windows Prefetch cache files (.pf) — auto-regenerated on use"
risk = RiskLevel.LOW


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
    prefetch_dir = os.path.join(windir, "Prefetch")

    if not os.path.isdir(prefetch_dir):
        return category

    try:
        for entry in os.scandir(prefetch_dir):
            try:
                if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".pf"):
                    category.items.append(CleanupItem(
                        path=entry.path,
                        size=entry.stat().st_size,
                        category=category.name,
                        risk=risk,
                        item_type=ItemType.FILE,
                        description="Prefetch file",
                    ))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass

    return category
