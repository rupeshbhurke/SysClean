"""
Rule: Recycle Bin
Scans $Recycle.Bin on all available drives.
"""

from __future__ import annotations

import os
import string
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "recycle_bin"
display_name = "Recycle Bin"
description = "Deleted files in the Recycle Bin on all drives"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    # Iterate all drive letters
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if not os.path.isdir(drive):
            continue

        recycle_path = os.path.join(drive, "$Recycle.Bin")
        if os.path.isdir(recycle_path):
            size = _dir_size(recycle_path)
            if size > 0:
                category.items.append(CleanupItem(
                    path=recycle_path,
                    size=size,
                    category=category.name,
                    risk=risk,
                    item_type=ItemType.DIRECTORY,
                    description=f"Recycle Bin ({letter}:)",
                ))

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
