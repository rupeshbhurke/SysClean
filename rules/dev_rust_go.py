"""
Rule: Rust & Go Developer Caches
Scans Cargo registry cache, target directories, Go module cache.
"""

from __future__ import annotations

import os
import time
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "dev_rust_go"
display_name = "Rust & Go Developer Caches"
description = "Cargo registry cache, Go module cache"
risk = RiskLevel.SAFE

STALE_TARGET_DAYS = 30


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    userprofile = os.environ.get("USERPROFILE", "")
    if not userprofile:
        return category

    # ── Rust / Cargo ─────────────────────────────────────────────────────
    cargo_home = os.environ.get("CARGO_HOME", os.path.join(userprofile, ".cargo"))

    cargo_registry_cache = os.path.join(cargo_home, "registry", "cache")
    _add_dir(category, cargo_registry_cache, "Cargo registry cache (compressed crates)",
             RiskLevel.SAFE)

    cargo_registry_src = os.path.join(cargo_home, "registry", "src")
    _add_dir(category, cargo_registry_src, "Cargo registry source (extracted crates)",
             RiskLevel.SAFE)

    cargo_git_db = os.path.join(cargo_home, "git", "db")
    _add_dir(category, cargo_git_db, "Cargo git dependency cache", RiskLevel.SAFE)

    cargo_git_co = os.path.join(cargo_home, "git", "checkouts")
    _add_dir(category, cargo_git_co, "Cargo git checkouts", RiskLevel.SAFE)

    # ── Stale Rust target/ directories ───────────────────────────────────
    _scan_stale_target_dirs(category, userprofile)

    # ── Go module cache ──────────────────────────────────────────────────
    gopath = os.environ.get("GOPATH", os.path.join(userprofile, "go"))
    go_mod_cache = os.path.join(gopath, "pkg", "mod", "cache")
    _add_dir(category, go_mod_cache, "Go module cache", RiskLevel.SAFE)

    go_build_cache = os.environ.get("GOCACHE", "")
    if not go_build_cache:
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            go_build_cache = os.path.join(localappdata, "go-build")
    _add_dir(category, go_build_cache, "Go build cache", RiskLevel.SAFE)

    return category


def _scan_stale_target_dirs(category: CleanupCategory, userprofile: str) -> None:
    """Find Rust target/ directories that haven't been modified recently."""
    search_roots = []
    for candidate in ["Projects", "Repos", "Source", "Code", "dev", "workspace"]:
        path = os.path.join(userprofile, candidate)
        if os.path.isdir(path):
            search_roots.append(path)

    cutoff = time.time() - (STALE_TARGET_DAYS * 86400)

    for root in search_roots:
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Look for Cargo.toml + target/ combo
                if "Cargo.toml" in filenames and "target" in dirnames:
                    target_path = os.path.join(dirpath, "target")
                    try:
                        mtime = os.path.getmtime(target_path)
                        if mtime < cutoff:
                            size = _dir_size(target_path)
                            if size > 10_000_000:  # Only flag if > 10 MB
                                category.items.append(CleanupItem(
                                    path=target_path,
                                    size=size,
                                    category=category.name,
                                    risk=RiskLevel.SAFE,
                                    item_type=ItemType.DIRECTORY,
                                    description=f"Stale Rust target/ (>{STALE_TARGET_DAYS}d old)",
                                ))
                    except (OSError, PermissionError):
                        pass
                    dirnames[:] = [d for d in dirnames if d != "target"]

                depth = dirpath.replace(root, "").count(os.sep)
                if depth >= 4:
                    dirnames.clear()

                dirnames[:] = [d for d in dirnames
                               if not d.startswith(".")
                               and d not in {"node_modules", ".git", "target",
                                             "vendor", "__pycache__"}]
        except (OSError, PermissionError):
            pass


def _add_dir(category: CleanupCategory, dir_path: str, label: str, risk: RiskLevel) -> None:
    if not dir_path or not os.path.isdir(dir_path):
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
