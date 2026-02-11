"""
Rule: Docker Desktop Caches
Scans Docker Desktop data (WSL2 vhdx, image layers, build cache).
Reports sizes but recommends using `docker system prune` for actual cleanup.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "dev_docker"
display_name = "Docker Desktop Caches"
description = "Docker Desktop WSL2 disk, image layers, build cache"
risk = RiskLevel.MEDIUM


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    localappdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")

    # ── Docker Desktop WSL2 virtual disk ─────────────────────────────────
    # This is the main disk space consumer — the ext4.vhdx for Docker
    if localappdata:
        docker_wsl_data = os.path.join(localappdata, "Docker", "wsl", "data")
        if os.path.isdir(docker_wsl_data):
            for fname in os.listdir(docker_wsl_data):
                if fname.lower().endswith(".vhdx"):
                    fpath = os.path.join(docker_wsl_data, fname)
                    try:
                        size = os.path.getsize(fpath)
                        if size > 0:
                            category.items.append(CleanupItem(
                                path=fpath,
                                size=size,
                                category=category.name,
                                risk=RiskLevel.MEDIUM,
                                item_type=ItemType.FILE,
                                description="Docker WSL2 virtual disk (use 'docker system prune' first)",
                            ))
                    except (OSError, PermissionError):
                        pass

    # ── Docker Desktop distro disk ───────────────────────────────────────
    if localappdata:
        docker_distro = os.path.join(localappdata, "Docker", "wsl", "distro")
        _add_dir(category, docker_distro,
                 "Docker Desktop WSL distro data", RiskLevel.MEDIUM)

    # ── Docker Desktop cache/logs ────────────────────────────────────────
    if localappdata:
        docker_log = os.path.join(localappdata, "Docker", "log")
        _add_dir(category, docker_log, "Docker Desktop logs", RiskLevel.SAFE)

    if appdata:
        docker_desktop = os.path.join(appdata, "Docker Desktop")
        if os.path.isdir(docker_desktop):
            # Only scan specific safe subdirs
            for subdir, label in [
                ("Local Storage", "Docker Desktop local storage"),
                ("Cache", "Docker Desktop cache"),
                ("GPUCache", "Docker Desktop GPU cache"),
                ("blob_storage", "Docker Desktop blob storage"),
            ]:
                path = os.path.join(docker_desktop, subdir)
                _add_dir(category, path, label, RiskLevel.SAFE)

    # ── Docker buildx cache ──────────────────────────────────────────────
    if userprofile:
        buildx = os.path.join(userprofile, ".docker", "buildx")
        _add_dir(category, buildx, "Docker buildx cache", RiskLevel.SAFE)

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
