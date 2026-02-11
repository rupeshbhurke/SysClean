"""
Rule: Delivery Optimization Cache
Scans the Delivery Optimization cache used for Windows Update distribution.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "delivery_optimization"
display_name = "Delivery Optimization Cache"
description = "Windows Update Delivery Optimization peer-to-peer cache"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")

    # Primary location
    do_cache = os.path.join(windir, "SoftwareDistribution", "DeliveryOptimization")
    _add_dir_if_exists(category, do_cache, "Delivery Optimization cache")

    # Alternate location used by some builds
    do_cache2 = os.path.join(windir, "ServiceProfiles", "NetworkService",
                             "AppData", "Local", "Microsoft", "Windows",
                             "DeliveryOptimization", "Cache")
    _add_dir_if_exists(category, do_cache2, "Delivery Optimization network cache")

    return category


def _add_dir_if_exists(category: CleanupCategory, dir_path: str, label: str) -> None:
    if not os.path.isdir(dir_path):
        return
    size = _dir_size(dir_path)
    if size > 0:
        category.items.append(CleanupItem(
            path=dir_path,
            size=size,
            category=category.name,
            risk=RiskLevel.SAFE,
            item_type=ItemType.DIRECTORY,
            description=label,
        ))


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
