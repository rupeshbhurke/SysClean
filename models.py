"""
SysClean — Data models for cleanup items and categories.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


class RiskLevel(enum.Enum):
    """Risk level associated with deleting a cleanup item."""
    SAFE = "safe"           # No risk — temp files, caches
    LOW = "low"             # Minimal risk — font cache, prefetch
    MEDIUM = "medium"       # Some risk — installer patches
    REGISTRY = "registry"   # Registry key removal


class ItemType(enum.Enum):
    """Type of cleanup item."""
    FILE = "file"
    DIRECTORY = "directory"
    REGISTRY_KEY = "registry_key"


@dataclass
class CleanupItem:
    """A single file, folder, or registry key eligible for cleanup."""
    path: str                           # Full path or registry key path
    size: int                           # Size in bytes (0 for registry keys)
    category: str                       # Category name
    risk: RiskLevel                     # Risk level
    item_type: ItemType                 # File, directory, or registry key
    description: str = ""               # Human-readable description
    selected: bool = True               # Whether the user selected it for deletion

    @property
    def size_human(self) -> str:
        """Return human-readable file size."""
        if self.size <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(self.size)
        idx = 0
        while size >= 1024.0 and idx < len(units) - 1:
            size /= 1024.0
            idx += 1
        return f"{size:.1f} {units[idx]}"


@dataclass
class CleanupCategory:
    """A category grouping related cleanup items."""
    name: str
    description: str
    risk: RiskLevel
    items: List[CleanupItem] = field(default_factory=list)
    enabled: bool = True        # User can toggle entire category
    scan_error: Optional[str] = None  # Error message if scan failed

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.items)

    @property
    def selected_size(self) -> int:
        return sum(item.size for item in self.items if item.selected)

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def selected_count(self) -> int:
        return sum(1 for item in self.items if item.selected)

    @property
    def total_size_human(self) -> str:
        return _format_size(self.total_size)

    @property
    def selected_size_human(self) -> str:
        return _format_size(self.selected_size)


@dataclass
class ScanResult:
    """Aggregated result of a full system scan."""
    categories: List[CleanupCategory] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(c.total_size for c in self.categories)

    @property
    def selected_size(self) -> int:
        return sum(c.selected_size for c in self.categories)

    @property
    def total_items(self) -> int:
        return sum(c.item_count for c in self.categories)

    @property
    def selected_items(self) -> int:
        return sum(c.selected_count for c in self.categories)

    @property
    def total_size_human(self) -> str:
        return _format_size(self.total_size)

    @property
    def selected_size_human(self) -> str:
        return _format_size(self.selected_size)


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    idx = 0
    while size >= 1024.0 and idx < len(units) - 1:
        size /= 1024.0
        idx += 1
    return f"{size:.1f} {units[idx]}"
