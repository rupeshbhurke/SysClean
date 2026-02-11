"""
Rule: Java / Android Developer Caches
Scans Gradle caches, Maven local repository, Android SDK caches.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "dev_java"
display_name = "Java / Android Developer Caches"
description = "Gradle caches, Maven .m2 repository, Android SDK temp"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    userprofile = os.environ.get("USERPROFILE", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    if not userprofile:
        return category

    # ── Gradle caches ────────────────────────────────────────────────────
    gradle_caches = os.path.join(userprofile, ".gradle", "caches")
    _add_dir(category, gradle_caches, "Gradle build caches (re-downloads on build)",
             RiskLevel.SAFE)

    gradle_wrapper = os.path.join(userprofile, ".gradle", "wrapper", "dists")
    _add_dir(category, gradle_wrapper, "Gradle wrapper distributions", RiskLevel.SAFE)

    gradle_daemon = os.path.join(userprofile, ".gradle", "daemon")
    _add_dir(category, gradle_daemon, "Gradle daemon logs", RiskLevel.SAFE)

    # ── Maven local repository ───────────────────────────────────────────
    m2_repo = os.path.join(userprofile, ".m2", "repository")
    _add_dir(category, m2_repo, "Maven local repository (re-downloads on build)",
             RiskLevel.LOW)

    # ── Android SDK caches ───────────────────────────────────────────────
    android_home = os.environ.get("ANDROID_HOME", "")
    if not android_home:
        android_home = os.path.join(localappdata, "Android", "Sdk")

    if os.path.isdir(android_home):
        # Android build cache
        android_cache = os.path.join(android_home, ".downloadIntermediates")
        _add_dir(category, android_cache, "Android SDK download intermediates", RiskLevel.SAFE)

        android_tmp = os.path.join(android_home, ".temp")
        _add_dir(category, android_tmp, "Android SDK temp files", RiskLevel.SAFE)

    # ── Android user-level caches ────────────────────────────────────────
    android_dot = os.path.join(userprofile, ".android", "cache")
    _add_dir(category, android_dot, "Android user cache", RiskLevel.SAFE)

    android_avd_cache = os.path.join(userprofile, ".android", "avd")
    # Only add if > 100 MB (AVDs are large and intentional)
    if os.path.isdir(android_avd_cache):
        size = _dir_size(android_avd_cache)
        if size > 100_000_000:
            category.items.append(CleanupItem(
                path=android_avd_cache,
                size=size,
                category=category.name,
                risk=RiskLevel.MEDIUM,
                item_type=ItemType.DIRECTORY,
                description="Android Virtual Devices (AVDs) — delete only if unused",
            ))

    # ── Kotlin daemon ────────────────────────────────────────────────────
    kotlin_daemon = os.path.join(localappdata, "kotlin", "daemon")
    _add_dir(category, kotlin_daemon, "Kotlin daemon data", RiskLevel.SAFE)

    return category


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
