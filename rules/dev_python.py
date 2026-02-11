"""
Rule: Python Developer Caches
Scans pip cache, conda packages, __pycache__ directories, and .pyc files.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "dev_python"
display_name = "Python Developer Caches"
description = "pip cache, conda packages, __pycache__ directories"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    localappdata = os.environ.get("LOCALAPPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")

    # ── pip cache (%LOCALAPPDATA%\pip\Cache) ─────────────────────────────
    if localappdata:
        pip_cache = os.path.join(localappdata, "pip", "Cache")
        _add_dir(category, pip_cache, "pip download cache", RiskLevel.SAFE)

    # ── pip http cache (alternate location) ──────────────────────────────
    if userprofile:
        pip_http = os.path.join(userprofile, ".cache", "pip")
        _add_dir(category, pip_http, "pip HTTP cache", RiskLevel.SAFE)

    # ── conda package cache ──────────────────────────────────────────────
    if userprofile:
        conda_pkgs = os.path.join(userprofile, ".conda", "pkgs")
        _add_dir(category, conda_pkgs, "Conda package cache", RiskLevel.SAFE)

        # Miniconda/Anaconda default location
        for conda_dir in ["Miniconda3", "Anaconda3", "miniconda3", "anaconda3"]:
            conda_path = os.path.join(userprofile, conda_dir, "pkgs")
            _add_dir(category, conda_path, f"{conda_dir} package cache", RiskLevel.SAFE)

    # ── Poetry cache ─────────────────────────────────────────────────────
    if localappdata:
        poetry_cache = os.path.join(localappdata, "pypoetry", "Cache")
        _add_dir(category, poetry_cache, "Poetry cache", RiskLevel.SAFE)

    # ── pipx cache ───────────────────────────────────────────────────────
    if localappdata:
        pipx_cache = os.path.join(localappdata, "pipx", ".cache")
        _add_dir(category, pipx_cache, "pipx cache", RiskLevel.SAFE)

    # ── __pycache__ in common project directories ────────────────────────
    if userprofile:
        _scan_pycache_dirs(category, userprofile)

    return category


def _scan_pycache_dirs(category: CleanupCategory, userprofile: str) -> None:
    """Find __pycache__ directories in common project locations."""
    search_roots = []
    for candidate in ["Projects", "Repos", "Source", "Code", "dev", "workspace",
                       "Documents", "Desktop"]:
        path = os.path.join(userprofile, candidate)
        if os.path.isdir(path):
            search_roots.append(path)

    for root in search_roots:
        try:
            for dirpath, dirnames, _filenames in os.walk(root):
                if "__pycache__" in dirnames:
                    pc_path = os.path.join(dirpath, "__pycache__")
                    size = _dir_size(pc_path)
                    if size > 0:
                        category.items.append(CleanupItem(
                            path=pc_path,
                            size=size,
                            category=category.name,
                            risk=RiskLevel.SAFE,
                            item_type=ItemType.DIRECTORY,
                            description="Python bytecode cache (__pycache__)",
                        ))
                    dirnames.remove("__pycache__")

                # Limit depth
                depth = dirpath.replace(root, "").count(os.sep)
                if depth >= 5:
                    dirnames.clear()

                # Skip unneeded dirs
                dirnames[:] = [d for d in dirnames
                               if not d.startswith(".")
                               and d not in {"node_modules", ".git", "venv", ".venv",
                                             "env", "__pycache__", "site-packages"}]
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
