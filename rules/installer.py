"""
Rule: Installer Temp & Patch Cache
Scans C:\\Windows\\Installer\\$PatchCache$ and orphaned .tmp files.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "installer"
display_name = "Installer Patch Cache"
description = "Windows Installer patch cache and orphaned temp files"
risk = RiskLevel.MEDIUM


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")

    # $PatchCache$ — contains cached patches for installed MSI applications
    patch_cache = os.path.join(windir, "Installer", "$PatchCache$")
    if os.path.isdir(patch_cache):
        size = _dir_size(patch_cache)
        if size > 0:
            category.items.append(CleanupItem(
                path=patch_cache,
                size=size,
                category=category.name,
                risk=risk,
                item_type=ItemType.DIRECTORY,
                description="MSI patch cache (may prevent repair of some apps)",
            ))

    # Orphaned .tmp files in Installer directory
    installer_dir = os.path.join(windir, "Installer")
    if os.path.isdir(installer_dir):
        try:
            for entry in os.scandir(installer_dir):
                try:
                    if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".tmp"):
                        category.items.append(CleanupItem(
                            path=entry.path,
                            size=entry.stat().st_size,
                            category=category.name,
                            risk=risk,
                            item_type=ItemType.FILE,
                            description="Orphaned installer temp file",
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
