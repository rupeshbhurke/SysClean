"""
Rule: Microsoft Teams & Store App Caches
Scans Teams Classic cache, OneDrive logs, and Store app temp states.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "teams_apps"
display_name = "Teams, OneDrive & Store App Caches"
description = "Microsoft Teams cache, OneDrive logs, Store app temp data"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    # ── Teams Classic cache ──────────────────────────────────────────────
    if appdata:
        teams_base = os.path.join(appdata, "Microsoft", "Teams")
        if os.path.isdir(teams_base):
            for subdir, label in [
                ("Cache", "Teams Classic cache"),
                ("blob_storage", "Teams Classic blob storage"),
                ("GPUCache", "Teams Classic GPU cache"),
                ("Code Cache", "Teams Classic code cache"),
                ("Service Worker", "Teams Classic service worker cache"),
                ("tmp", "Teams Classic temp files"),
                ("logs.txt", None),  # single file handled separately
            ]:
                path = os.path.join(teams_base, subdir)
                if label and os.path.isdir(path):
                    _add_dir(category, path, label, RiskLevel.SAFE)

    # ── New Teams (MSIX) cache ───────────────────────────────────────────
    if localappdata:
        packages_dir = os.path.join(localappdata, "Packages")
        if os.path.isdir(packages_dir):
            try:
                for entry in os.scandir(packages_dir):
                    if entry.is_dir(follow_symlinks=False) and "MSTeams" in entry.name:
                        for subdir, label in [
                            ("TempState", "New Teams temp state"),
                            (os.path.join("AC", "INetCache"), "New Teams internet cache"),
                        ]:
                            path = os.path.join(entry.path, "LocalCache", subdir)
                            _add_dir(category, path, label, RiskLevel.SAFE)
            except (OSError, PermissionError):
                pass

    # ── OneDrive logs ────────────────────────────────────────────────────
    if localappdata:
        onedrive_logs = os.path.join(localappdata, "Microsoft", "OneDrive", "logs")
        _add_dir(category, onedrive_logs, "OneDrive logs", RiskLevel.SAFE)

    # ── Store app temp states (generic) ──────────────────────────────────
    if localappdata:
        packages_dir = os.path.join(localappdata, "Packages")
        if os.path.isdir(packages_dir):
            _scan_store_app_temps(category, packages_dir)

    return category


def _scan_store_app_temps(category: CleanupCategory, packages_dir: str) -> None:
    """Scan Store app packages for TempState directories with significant size."""
    try:
        for entry in os.scandir(packages_dir):
            if not entry.is_dir(follow_symlinks=False):
                continue
            try:
                temp_state = os.path.join(entry.path, "TempState")
                if os.path.isdir(temp_state):
                    size = _dir_size(temp_state)
                    if size > 1_000_000:  # Only flag if > 1 MB
                        # Get a shorter display name
                        app_name = entry.name.split("_")[0] if "_" in entry.name else entry.name
                        category.items.append(CleanupItem(
                            path=temp_state,
                            size=size,
                            category=category.name,
                            risk=RiskLevel.SAFE,
                            item_type=ItemType.DIRECTORY,
                            description=f"Store app temp: {app_name}",
                        ))

                inet_cache = os.path.join(entry.path, "AC", "INetCache")
                if os.path.isdir(inet_cache):
                    size = _dir_size(inet_cache)
                    if size > 1_000_000:
                        app_name = entry.name.split("_")[0] if "_" in entry.name else entry.name
                        category.items.append(CleanupItem(
                            path=inet_cache,
                            size=size,
                            category=category.name,
                            risk=RiskLevel.SAFE,
                            item_type=ItemType.DIRECTORY,
                            description=f"Store app internet cache: {app_name}",
                        ))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass


def _add_dir(category: CleanupCategory, dir_path: str, label: str, risk: RiskLevel) -> None:
    if not os.path.isdir(dir_path):
        return
    size = _dir_size(dir_path)
    if size > 0:
        category.items.append(CleanupItem(
            path=dir_path,
            size=size,
            category=category.name,
            risk=risk,
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
