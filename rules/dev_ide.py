"""
Rule: IDE & Editor Caches
Scans VS Code, JetBrains, Unity editor caches and extensions.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "dev_ide"
display_name = "IDE & Editor Caches"
description = "VS Code, JetBrains, Unity editor caches"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")

    # ── VS Code ──────────────────────────────────────────────────────────
    if appdata:
        vscode_base = os.path.join(appdata, "Code")
        for subdir, label in [
            ("CachedExtensionVSIXs", "VS Code cached extension VSIXs"),
            ("Cache", "VS Code cache"),
            ("CachedData", "VS Code cached data"),
            ("CachedExtensions", "VS Code cached extensions metadata"),
            ("Code Cache", "VS Code code cache"),
            ("GPUCache", "VS Code GPU cache"),
            ("logs", "VS Code logs"),
        ]:
            path = os.path.join(vscode_base, subdir)
            _add_dir(category, path, label, RiskLevel.SAFE)

    # ── VS Code Insiders ─────────────────────────────────────────────────
    if appdata:
        vscode_insiders = os.path.join(appdata, "Code - Insiders")
        for subdir, label in [
            ("Cache", "VS Code Insiders cache"),
            ("CachedData", "VS Code Insiders cached data"),
            ("CachedExtensionVSIXs", "VS Code Insiders cached VSIXs"),
            ("logs", "VS Code Insiders logs"),
        ]:
            path = os.path.join(vscode_insiders, subdir)
            _add_dir(category, path, label, RiskLevel.SAFE)

    # ── Windsurf (Codeium IDE) ───────────────────────────────────────────
    if appdata:
        windsurf_base = os.path.join(appdata, "Windsurf")
        for subdir, label in [
            ("Cache", "Windsurf cache"),
            ("CachedData", "Windsurf cached data"),
            ("CachedExtensionVSIXs", "Windsurf cached extension VSIXs"),
            ("Code Cache", "Windsurf code cache"),
            ("logs", "Windsurf logs"),
        ]:
            path = os.path.join(windsurf_base, subdir)
            _add_dir(category, path, label, RiskLevel.SAFE)

    # ── JetBrains IDEs (IntelliJ, PyCharm, WebStorm, Rider, etc.) ───────
    if localappdata:
        jetbrains_base = os.path.join(localappdata, "JetBrains")
        if os.path.isdir(jetbrains_base):
            try:
                for entry in os.scandir(jetbrains_base):
                    if entry.is_dir(follow_symlinks=False):
                        # Log and cache directories
                        for subdir, label_suffix in [
                            ("log", "logs"),
                            ("caches", "caches"),
                            ("index", "index data"),
                            ("tmp", "temp files"),
                        ]:
                            path = os.path.join(entry.path, subdir)
                            _add_dir(category, path,
                                     f"JetBrains {entry.name} {label_suffix}",
                                     RiskLevel.SAFE)
            except (OSError, PermissionError):
                pass

    # ── Sublime Text cache ───────────────────────────────────────────────
    if appdata:
        sublime_cache = os.path.join(appdata, "Sublime Text", "Cache")
        _add_dir(category, sublime_cache, "Sublime Text cache", RiskLevel.SAFE)

    # ── Unity editor ─────────────────────────────────────────────────────
    if localappdata:
        unity_cache = os.path.join(localappdata, "Unity", "cache")
        _add_dir(category, unity_cache, "Unity editor cache", RiskLevel.SAFE)

    if appdata:
        unity_logs = os.path.join(appdata, "Unity", "Editor")
        if os.path.isdir(unity_logs):
            # Only target log files
            try:
                for entry in os.scandir(unity_logs):
                    if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".log"):
                        try:
                            category.items.append(CleanupItem(
                                path=entry.path,
                                size=entry.stat().st_size,
                                category=category.name,
                                risk=RiskLevel.SAFE,
                                item_type=ItemType.FILE,
                                description="Unity editor log",
                            ))
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass

    # ── Electron / Chromium-based app caches ─────────────────────────────
    if appdata:
        for app_name in ["Postman", "Slack", "Discord", "Figma"]:
            for subdir in ["Cache", "Code Cache", "GPUCache"]:
                path = os.path.join(appdata, app_name, subdir)
                _add_dir(category, path, f"{app_name} {subdir}", RiskLevel.SAFE)

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
