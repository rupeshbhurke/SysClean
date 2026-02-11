"""
Rule: User Temp Files & System Temp Files
Scans %TEMP%, AppData\\Local\\Temp, and C:\\Windows\\Temp.
"""

from __future__ import annotations

import os
import glob
from pathlib import Path

from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "temp_files"
display_name = "Temporary Files"
description = "User and system temporary files (%TEMP%, Windows\\Temp)"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    # User temp directory
    user_temp = os.environ.get("TEMP", os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Temp"))
    _scan_temp_dir(category, user_temp, "User temp")

    # System temp directory
    sys_temp = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "Temp")
    if os.path.normpath(sys_temp).lower() != os.path.normpath(user_temp).lower():
        _scan_temp_dir(category, sys_temp, "System temp")

    return category


def _scan_temp_dir(category: CleanupCategory, temp_dir: str, label: str) -> None:
    """Scan a temp directory and add items to the category."""
    if not os.path.isdir(temp_dir):
        return

    try:
        for entry in os.scandir(temp_dir):
            try:
                if entry.is_file(follow_symlinks=False):
                    size = entry.stat().st_size
                    category.items.append(CleanupItem(
                        path=entry.path,
                        size=size,
                        category=category.name,
                        risk=risk,
                        item_type=ItemType.FILE,
                        description=f"{label} file",
                    ))
                elif entry.is_dir(follow_symlinks=False):
                    size = _dir_size(entry.path)
                    category.items.append(CleanupItem(
                        path=entry.path,
                        size=size,
                        category=category.name,
                        risk=risk,
                        item_type=ItemType.DIRECTORY,
                        description=f"{label} folder",
                    ))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass


def _dir_size(path: str) -> int:
    """Calculate total directory size."""
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
