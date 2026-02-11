"""
Rule: Windows Update Cleanup
Scans C:\\Windows\\SoftwareDistribution\\Download for cached update files.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "windows_update"
display_name = "Windows Update Cache"
description = "Downloaded Windows Update files (SoftwareDistribution\\Download)"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
    download_dir = os.path.join(windir, "SoftwareDistribution", "Download")

    if not os.path.isdir(download_dir):
        return category

    try:
        for entry in os.scandir(download_dir):
            try:
                if entry.is_file(follow_symlinks=False):
                    category.items.append(CleanupItem(
                        path=entry.path,
                        size=entry.stat().st_size,
                        category=category.name,
                        risk=risk,
                        item_type=ItemType.FILE,
                        description="Windows Update download",
                    ))
                elif entry.is_dir(follow_symlinks=False):
                    size = _dir_size(entry.path)
                    category.items.append(CleanupItem(
                        path=entry.path,
                        size=size,
                        category=category.name,
                        risk=risk,
                        item_type=ItemType.DIRECTORY,
                        description="Windows Update download folder",
                    ))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass

    return category


def _dir_size(path: str) -> int:
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total
