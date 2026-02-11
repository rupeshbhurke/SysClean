"""
Rule: ServiceProfiles Temp Files
Scans C:\\Windows\\ServiceProfiles\\{LocalService,NetworkService}\\AppData\\Local\\Temp
These temp folders can grow to 60+ GB and are not covered by Disk Cleanup.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "service_profiles_temp"
display_name = "Service Profiles Temp"
description = "Temp files in LocalService & NetworkService profiles (often 10-60+ GB)"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")

    profiles = [
        ("LocalService", "Local Service temp files"),
        ("NetworkService", "Network Service temp files"),
    ]

    for profile_name, label in profiles:
        temp_dir = os.path.join(
            windir, "ServiceProfiles", profile_name,
            "AppData", "Local", "Temp",
        )
        if not os.path.isdir(temp_dir):
            continue

        # Scan individual top-level entries for granular selection
        try:
            for entry in os.scandir(temp_dir):
                try:
                    if entry.is_file(follow_symlinks=False):
                        category.items.append(CleanupItem(
                            path=entry.path,
                            size=entry.stat().st_size,
                            category=category.name,
                            risk=risk,
                            item_type=ItemType.FILE,
                            description=label,
                        ))
                    elif entry.is_dir(follow_symlinks=False):
                        size = _dir_size(entry.path)
                        category.items.append(CleanupItem(
                            path=entry.path,
                            size=size,
                            category=category.name,
                            risk=risk,
                            item_type=ItemType.DIRECTORY,
                            description=label,
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
