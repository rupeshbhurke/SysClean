"""
Rule: Old Windows Installations
Scans for Windows.old, $Windows.~BT, $Windows.~WS directories.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "old_windows"
display_name = "Old Windows Installations"
description = "Previous Windows installations (Windows.old, upgrade temp folders)"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    # Check on the system drive
    sys_drive = os.environ.get("SYSTEMDRIVE", "C:")

    old_dirs = [
        ("Windows.old", "Previous Windows installation"),
        ("$Windows.~BT", "Windows upgrade temporary files"),
        ("$Windows.~WS", "Windows upgrade source files"),
    ]

    for dirname, label in old_dirs:
        dir_path = os.path.join(sys_drive + os.sep, dirname)
        if os.path.isdir(dir_path):
            size = _dir_size(dir_path)
            category.items.append(CleanupItem(
                path=dir_path,
                size=size,
                category=category.name,
                risk=risk,
                item_type=ItemType.DIRECTORY,
                description=label,
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
