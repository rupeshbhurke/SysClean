"""
Rule: Windows Icon & Thumbnail Caches
Scans IconCache.db and related icon cache files.
These are regenerated automatically by Windows Explorer on reboot.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "icon_cache"
display_name = "Windows Icon Cache"
description = "Icon cache files (IconCache.db) — regenerated on reboot"
risk = RiskLevel.LOW


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        return category

    # ── Main IconCache.db ────────────────────────────────────────────────
    icon_cache = os.path.join(localappdata, "IconCache.db")
    _add_file(category, icon_cache, "Windows icon cache (main)")

    # ── Explorer icon cache files ────────────────────────────────────────
    explorer_dir = os.path.join(localappdata, "Microsoft", "Windows", "Explorer")
    if os.path.isdir(explorer_dir):
        try:
            for entry in os.scandir(explorer_dir):
                try:
                    if entry.is_file(follow_symlinks=False):
                        name_lower = entry.name.lower()
                        if "iconcache" in name_lower:
                            category.items.append(CleanupItem(
                                path=entry.path,
                                size=entry.stat().st_size,
                                category=category.name,
                                risk=risk,
                                item_type=ItemType.FILE,
                                description="Explorer icon cache",
                            ))
                except (OSError, PermissionError):
                    pass
        except (OSError, PermissionError):
            pass

    return category


def _add_file(category: CleanupCategory, file_path: str, label: str) -> None:
    if not os.path.isfile(file_path):
        return
    try:
        size = os.path.getsize(file_path)
        if size > 0:
            category.items.append(CleanupItem(
                path=file_path,
                size=size,
                category=category.name,
                risk=risk,
                item_type=ItemType.FILE,
                description=label,
            ))
    except (OSError, PermissionError):
        pass
