"""
Rule: Node.js / Frontend Developer Caches
Scans npm cache, Yarn cache, pnpm store, and stale node_modules directories.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "dev_nodejs"
display_name = "Node.js / Frontend Caches"
description = "npm cache, Yarn cache, pnpm store, and stale node_modules"
risk = RiskLevel.SAFE

# node_modules older than this many days are considered stale
STALE_NODE_MODULES_DAYS = 30


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")

    # ── npm cache (%APPDATA%\npm-cache) ──────────────────────────────────
    if appdata:
        npm_cache = os.path.join(appdata, "npm-cache")
        _add_dir(category, npm_cache, "npm global cache", RiskLevel.SAFE)

    # ── Yarn v1 cache (%LOCALAPPDATA%\Yarn\Cache) ───────────────────────
    if localappdata:
        yarn_cache = os.path.join(localappdata, "Yarn", "Cache")
        _add_dir(category, yarn_cache, "Yarn v1 cache", RiskLevel.SAFE)

    # ── Yarn Berry cache (%LOCALAPPDATA%\yarn\berry\cache) ──────────────
    if localappdata:
        yarn_berry = os.path.join(localappdata, "yarn", "berry", "cache")
        _add_dir(category, yarn_berry, "Yarn Berry cache", RiskLevel.SAFE)

    # ── pnpm store (%LOCALAPPDATA%\pnpm-store) ──────────────────────────
    if localappdata:
        pnpm_store = os.path.join(localappdata, "pnpm-store")
        _add_dir(category, pnpm_store, "pnpm content-addressable store", RiskLevel.SAFE)

    # ── pnpm cache (%LOCALAPPDATA%\pnpm\store) ──────────────────────────
    if localappdata:
        pnpm_cache = os.path.join(localappdata, "pnpm", "store")
        _add_dir(category, pnpm_cache, "pnpm store", RiskLevel.SAFE)

    # ── Bun cache (%USERPROFILE%\.bun\install\cache) ────────────────────
    if userprofile:
        bun_cache = os.path.join(userprofile, ".bun", "install", "cache")
        _add_dir(category, bun_cache, "Bun install cache", RiskLevel.SAFE)

    # ── Stale node_modules in common project dirs ────────────────────────
    if userprofile:
        _scan_stale_node_modules(category, userprofile)

    return category


def _scan_stale_node_modules(category: CleanupCategory, userprofile: str) -> None:
    """Find node_modules directories that haven't been modified recently."""
    search_roots = []
    for candidate in ["Projects", "Repos", "Source", "Code", "dev", "workspace",
                       "Documents", "Desktop"]:
        path = os.path.join(userprofile, candidate)
        if os.path.isdir(path):
            search_roots.append(path)

    cutoff = time.time() - (STALE_NODE_MODULES_DAYS * 86400)

    for root in search_roots:
        try:
            for dirpath, dirnames, _filenames in os.walk(root):
                # Don't recurse into node_modules itself
                if "node_modules" in dirnames:
                    nm_path = os.path.join(dirpath, "node_modules")
                    try:
                        mtime = os.path.getmtime(nm_path)
                        if mtime < cutoff:
                            size = _dir_size(nm_path)
                            if size > 1_000_000:  # Only flag if > 1 MB
                                category.items.append(CleanupItem(
                                    path=nm_path,
                                    size=size,
                                    category=category.name,
                                    risk=RiskLevel.LOW,
                                    item_type=ItemType.DIRECTORY,
                                    description=f"Stale node_modules (>{STALE_NODE_MODULES_DAYS}d old)",
                                ))
                    except (OSError, PermissionError):
                        pass
                    dirnames.remove("node_modules")

                # Limit depth — don't go too deep
                depth = dirpath.replace(root, "").count(os.sep)
                if depth >= 4:
                    dirnames.clear()

                # Skip hidden dirs and common non-project dirs
                dirnames[:] = [d for d in dirnames
                               if not d.startswith(".")
                               and d not in {"node_modules", ".git", "dist", "build",
                                             "__pycache__", "venv", ".venv"}]
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
