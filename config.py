"""
SysClean — Configuration, exclusion lists, and cleanup profiles.

Provides:
  - Exclusion patterns (paths/globs that should never be deleted)
  - Cleanup profiles (predefined sets of rules for different user types)
  - Persistent config loading/saving from JSON
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", "."), "SysClean")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
EXCLUSIONS_FILE = os.path.join(CONFIG_DIR, "exclusions.json")


# ── Cleanup Profiles ─────────────────────────────────────────────────────────

@dataclass
class CleanupProfile:
    """A named set of rule modules to enable."""
    name: str
    description: str
    rules: List[str]  # List of rule module `name` values


BUILTIN_PROFILES: Dict[str, CleanupProfile] = {
    "minimal": CleanupProfile(
        name="minimal",
        description="Safe system cleanup only (temp files, logs, recycle bin)",
        rules=["temp_files", "logs_reports", "recycle_bin"],
    ),
    "standard": CleanupProfile(
        name="standard",
        description="Standard cleanup (all system rules, no developer or registry)",
        rules=[
            "temp_files", "windows_update", "prefetch", "caches",
            "logs_reports", "delivery_optimization", "installer",
            "old_windows", "recycle_bin", "shader_cache", "icon_cache",
            "teams_apps",
        ],
    ),
    "frontend": CleanupProfile(
        name="frontend",
        description="Frontend developer — standard + Node.js/IDE caches",
        rules=[
            "temp_files", "windows_update", "prefetch", "caches",
            "logs_reports", "delivery_optimization", "installer",
            "old_windows", "recycle_bin", "shader_cache", "icon_cache",
            "teams_apps", "dev_nodejs", "dev_ide",
        ],
    ),
    "backend": CleanupProfile(
        name="backend",
        description="Backend developer — standard + Python/.NET/Java/Docker caches",
        rules=[
            "temp_files", "windows_update", "prefetch", "caches",
            "logs_reports", "delivery_optimization", "installer",
            "old_windows", "recycle_bin", "shader_cache", "icon_cache",
            "teams_apps", "dev_python", "dev_dotnet", "dev_java",
            "dev_docker", "dev_ide",
        ],
    ),
    "fullstack": CleanupProfile(
        name="fullstack",
        description="Full-stack developer — standard + all developer caches",
        rules=[
            "temp_files", "windows_update", "prefetch", "caches",
            "logs_reports", "delivery_optimization", "installer",
            "old_windows", "recycle_bin", "shader_cache", "icon_cache",
            "teams_apps", "dev_nodejs", "dev_python", "dev_dotnet",
            "dev_java", "dev_rust_go", "dev_docker", "dev_ide",
        ],
    ),
    "everything": CleanupProfile(
        name="everything",
        description="All rules including registry analysis",
        rules=[
            "temp_files", "windows_update", "prefetch", "caches",
            "logs_reports", "delivery_optimization", "installer",
            "old_windows", "recycle_bin", "shader_cache", "icon_cache",
            "teams_apps", "dev_nodejs", "dev_python", "dev_dotnet",
            "dev_java", "dev_rust_go", "dev_docker", "dev_ide",
            "registry",
        ],
    ),
}


# ── Exclusion List ───────────────────────────────────────────────────────────

@dataclass
class ExclusionConfig:
    """Paths and patterns that should be excluded from cleanup."""
    # Exact paths to exclude (case-insensitive on Windows)
    paths: Set[str] = field(default_factory=set)
    # Glob patterns to exclude (e.g., "*.important", "C:\\MyData\\**")
    patterns: List[str] = field(default_factory=list)
    # Rule names to always skip
    skip_rules: Set[str] = field(default_factory=set)


def load_exclusions() -> ExclusionConfig:
    """Load exclusion config from disk, or return defaults."""
    config = ExclusionConfig()
    try:
        if os.path.isfile(EXCLUSIONS_FILE):
            with open(EXCLUSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            config.paths = set(data.get("paths", []))
            config.patterns = data.get("patterns", [])
            config.skip_rules = set(data.get("skip_rules", []))
    except (json.JSONDecodeError, OSError, PermissionError):
        pass
    return config


def save_exclusions(config: ExclusionConfig) -> None:
    """Save exclusion config to disk."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "paths": sorted(config.paths),
            "patterns": config.patterns,
            "skip_rules": sorted(config.skip_rules),
        }
        with open(EXCLUSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except (OSError, PermissionError):
        pass


def is_excluded(path: str, exclusions: ExclusionConfig) -> bool:
    """Check if a path matches any exclusion rule."""
    import fnmatch

    path_lower = os.path.normpath(path).lower()

    # Check exact path matches
    for excl in exclusions.paths:
        if os.path.normpath(excl).lower() == path_lower:
            return True

    # Check glob patterns
    for pattern in exclusions.patterns:
        if fnmatch.fnmatch(path_lower, pattern.lower()):
            return True

    return False


# ── General Config ───────────────────────────────────────────────────────────

@dataclass
class AppConfig:
    """Application-wide configuration."""
    min_age_days: int = 0           # Only delete files older than N days (0 = no filter)
    min_size_bytes: int = 0         # Only show items larger than N bytes (0 = no filter)
    default_profile: str = "standard"
    log_dir: str = "."
    dry_run: bool = False


def load_config() -> AppConfig:
    """Load app config from disk, or return defaults."""
    config = AppConfig()
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            config.min_age_days = data.get("min_age_days", 0)
            config.min_size_bytes = data.get("min_size_bytes", 0)
            config.default_profile = data.get("default_profile", "standard")
            config.log_dir = data.get("log_dir", ".")
            config.dry_run = data.get("dry_run", False)
    except (json.JSONDecodeError, OSError, PermissionError):
        pass
    return config


def save_config(config: AppConfig) -> None:
    """Save app config to disk."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "min_age_days": config.min_age_days,
            "min_size_bytes": config.min_size_bytes,
            "default_profile": config.default_profile,
            "log_dir": config.log_dir,
            "dry_run": config.dry_run,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except (OSError, PermissionError):
        pass
