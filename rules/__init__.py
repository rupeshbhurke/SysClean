"""
SysClean — Cleanup rules registry.

Each rule module exposes:
    name: str           — internal identifier
    display_name: str   — human-readable name
    description: str    — what this rule cleans
    risk: RiskLevel     — risk level
    scan() -> CleanupCategory
"""

from __future__ import annotations

from typing import List, Any

# Import all rule modules
from rules import (
    temp_files,
    windows_update,
    prefetch,
    caches,
    logs_reports,
    delivery_optimization,
    installer,
    old_windows,
    recycle_bin,
    # Phase 1a — Developer-specific
    dev_nodejs,
    dev_python,
    dev_dotnet,
    dev_java,
    dev_rust_go,
    dev_docker,
    dev_ide,
    # Phase 1b — Additional system targets
    shader_cache,
    icon_cache,
    teams_apps,
)

# Master list of all available rule modules
ALL_RULES: List[Any] = [
    # ── System cleanup ───────────────────────────────────────────────────
    temp_files,
    windows_update,
    prefetch,
    caches,
    logs_reports,
    delivery_optimization,
    installer,
    old_windows,
    recycle_bin,
    # ── System extras ────────────────────────────────────────────────────
    shader_cache,
    icon_cache,
    teams_apps,
    # ── Developer profiles ───────────────────────────────────────────────
    dev_nodejs,
    dev_python,
    dev_dotnet,
    dev_java,
    dev_rust_go,
    dev_docker,
    dev_ide,
]


def get_rule_names() -> List[str]:
    """Return list of all rule internal names."""
    return [r.name for r in ALL_RULES]
