"""
Rule: .NET / C# Developer Caches
Scans NuGet package cache, NuGet temp, Visual Studio ComponentModelCache.
"""

from __future__ import annotations

import os
import glob
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "dev_dotnet"
display_name = ".NET / C# Developer Caches"
description = "NuGet packages, NuGet temp files, Visual Studio caches"
risk = RiskLevel.LOW


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    userprofile = os.environ.get("USERPROFILE", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    temp = os.environ.get("TEMP", "")

    # ── NuGet global packages cache ──────────────────────────────────────
    if userprofile:
        nuget_pkgs = os.path.join(userprofile, ".nuget", "packages")
        _add_dir(category, nuget_pkgs, "NuGet global package cache (re-downloads on restore)",
                 RiskLevel.LOW)

    # ── NuGet HTTP cache ─────────────────────────────────────────────────
    if localappdata:
        nuget_http = os.path.join(localappdata, "NuGet", "v3-cache")
        _add_dir(category, nuget_http, "NuGet HTTP v3 cache", RiskLevel.SAFE)

        nuget_plugins = os.path.join(localappdata, "NuGet", "plugins-cache")
        _add_dir(category, nuget_plugins, "NuGet plugins cache", RiskLevel.SAFE)

    # ── NuGet temp (scratch) ─────────────────────────────────────────────
    if temp:
        nuget_scratch = os.path.join(temp, "NuGetScratch")
        _add_dir(category, nuget_scratch, "NuGet scratch/temp files", RiskLevel.SAFE)

    # ── Visual Studio ComponentModelCache ────────────────────────────────
    if localappdata:
        vs_base = os.path.join(localappdata, "Microsoft", "VisualStudio")
        if os.path.isdir(vs_base):
            try:
                for entry in os.scandir(vs_base):
                    if entry.is_dir(follow_symlinks=False):
                        cmc = os.path.join(entry.path, "ComponentModelCache")
                        _add_dir(category, cmc,
                                 f"VS {entry.name} ComponentModelCache", RiskLevel.SAFE)

                        mef = os.path.join(entry.path, "MEFCacheData")
                        _add_dir(category, mef,
                                 f"VS {entry.name} MEF cache", RiskLevel.SAFE)
            except (OSError, PermissionError):
                pass

    # ── .vs folders in common project directories ────────────────────────
    if userprofile:
        _scan_vs_folders(category, userprofile)

    # ── dotnet SDK temp/workload cache ───────────────────────────────────
    if localappdata:
        dotnet_cli = os.path.join(localappdata, "Microsoft", "dotnet")
        if os.path.isdir(dotnet_cli):
            for subdir in ["NuGetFallbackFolder", "toolResolverCache"]:
                path = os.path.join(dotnet_cli, subdir)
                _add_dir(category, path, f".NET SDK {subdir}", RiskLevel.SAFE)

    return category


def _scan_vs_folders(category: CleanupCategory, userprofile: str) -> None:
    """Find .vs hidden directories in project roots (VS solution caches)."""
    search_roots = []
    for candidate in ["Projects", "Repos", "Source", "Code", "dev", "workspace",
                       "Documents"]:
        path = os.path.join(userprofile, candidate)
        if os.path.isdir(path):
            search_roots.append(path)

    for root in search_roots:
        try:
            for dirpath, dirnames, _filenames in os.walk(root):
                if ".vs" in dirnames:
                    vs_path = os.path.join(dirpath, ".vs")
                    size = _dir_size(vs_path)
                    if size > 500_000:  # Only flag if > 500 KB
                        category.items.append(CleanupItem(
                            path=vs_path,
                            size=size,
                            category=category.name,
                            risk=RiskLevel.SAFE,
                            item_type=ItemType.DIRECTORY,
                            description="Visual Studio solution cache (.vs)",
                        ))
                    dirnames.remove(".vs")

                depth = dirpath.replace(root, "").count(os.sep)
                if depth >= 4:
                    dirnames.clear()

                dirnames[:] = [d for d in dirnames
                               if not d.startswith(".")
                               and d not in {"node_modules", ".git", "bin", "obj",
                                             "packages", ".vs"}]
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
