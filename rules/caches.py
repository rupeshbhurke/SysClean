"""
Rule: Caches — Thumbnail cache, Font cache, Browser caches (Chrome, Edge, Firefox).
"""

from __future__ import annotations

import os
import glob
from pathlib import Path
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "caches"
display_name = "Caches (Thumbnails, Fonts, Browsers)"
description = "Thumbnail cache, font cache, and browser caches (Chrome, Edge, Firefox)"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    _scan_thumbnail_cache(category)
    _scan_font_cache(category)
    _scan_browser_caches(category)

    return category


# ── Thumbnail cache ──────────────────────────────────────────────────────────

def _scan_thumbnail_cache(category: CleanupCategory) -> None:
    local_app = os.environ.get("LOCALAPPDATA", "")
    if not local_app:
        return

    explorer_dir = os.path.join(local_app, "Microsoft", "Windows", "Explorer")
    if not os.path.isdir(explorer_dir):
        return

    try:
        for entry in os.scandir(explorer_dir):
            try:
                if entry.is_file(follow_symlinks=False) and "thumbcache" in entry.name.lower():
                    category.items.append(CleanupItem(
                        path=entry.path,
                        size=entry.stat().st_size,
                        category=category.name,
                        risk=RiskLevel.SAFE,
                        item_type=ItemType.FILE,
                        description="Thumbnail cache",
                    ))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass


# ── Font cache ───────────────────────────────────────────────────────────────

def _scan_font_cache(category: CleanupCategory) -> None:
    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
    font_cache_dir = os.path.join(
        windir, "ServiceProfiles", "LocalService", "AppData", "Local", "FontCache"
    )

    if not os.path.isdir(font_cache_dir):
        return

    try:
        for entry in os.scandir(font_cache_dir):
            try:
                if entry.is_file(follow_symlinks=False):
                    category.items.append(CleanupItem(
                        path=entry.path,
                        size=entry.stat().st_size,
                        category=category.name,
                        risk=RiskLevel.LOW,
                        item_type=ItemType.FILE,
                        description="Font cache file",
                    ))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass


# ── Browser caches ───────────────────────────────────────────────────────────

def _scan_browser_caches(category: CleanupCategory) -> None:
    local_app = os.environ.get("LOCALAPPDATA", "")
    if not local_app:
        return

    # Browser cache locations: (label, relative path from LOCALAPPDATA)
    browser_caches = [
        # ("Chrome cache", os.path.join("Google", "Chrome", "User Data", "Default", "Cache")),
        # ("Chrome Code Cache", os.path.join("Google", "Chrome", "User Data", "Default", "Code Cache")),
        ("Edge cache", os.path.join("Microsoft", "Edge", "User Data", "Default", "Cache")),
        ("Edge Code Cache", os.path.join("Microsoft", "Edge", "User Data", "Default", "Code Cache")),
    ]

    for label, rel_path in browser_caches:
        cache_dir = os.path.join(local_app, rel_path)
        if os.path.isdir(cache_dir):
            size = _dir_size(cache_dir)
            if size > 0:
                category.items.append(CleanupItem(
                    path=cache_dir,
                    size=size,
                    category=category.name,
                    risk=RiskLevel.SAFE,
                    item_type=ItemType.DIRECTORY,
                    description=label,
                ))

    # Firefox — profile-based cache
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        ff_profiles = os.path.join(local_app, "Mozilla", "Firefox", "Profiles")
        if os.path.isdir(ff_profiles):
            try:
                for profile_entry in os.scandir(ff_profiles):
                    if profile_entry.is_dir(follow_symlinks=False):
                        ff_cache = os.path.join(profile_entry.path, "cache2")
                        if os.path.isdir(ff_cache):
                            size = _dir_size(ff_cache)
                            if size > 0:
                                category.items.append(CleanupItem(
                                    path=ff_cache,
                                    size=size,
                                    category=category.name,
                                    risk=RiskLevel.SAFE,
                                    item_type=ItemType.DIRECTORY,
                                    description=f"Firefox cache ({profile_entry.name})",
                                ))
            except (OSError, PermissionError):
                pass


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
