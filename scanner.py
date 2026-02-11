"""
SysClean — Scanner engine that orchestrates rule modules to collect cleanup items.
"""

from __future__ import annotations

import os
import time
import traceback
from pathlib import Path
from typing import Callable, List, Optional

from models import CleanupCategory, ScanResult
from rules import ALL_RULES


ProgressCallback = Optional[Callable[[str, int, int], None]]
# callback(category_name, current_index, total_categories)


def get_dir_size(path: str) -> int:
    """Recursively calculate directory size in bytes, handling permission errors."""
    total = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def get_file_size(path: str) -> int:
    """Get file size, returning 0 on error."""
    try:
        return os.path.getsize(path)
    except (OSError, PermissionError):
        return 0


def scan_all(
    include_registry: bool = False,
    progress_cb: ProgressCallback = None,
    profile_rules: Optional[set] = None,
) -> ScanResult:
    """
    Run all enabled cleanup rules and return aggregated results.

    Args:
        include_registry: If True, include registry analysis rules.
        progress_cb: Optional callback for progress reporting.
        profile_rules: If provided, only run rules whose `name` is in this set.

    Returns:
        ScanResult with all discovered cleanup items grouped by category.
    """
    result = ScanResult()

    if profile_rules is not None:
        rules = [r for r in ALL_RULES if r.name in profile_rules]
    else:
        rules = [r for r in ALL_RULES if include_registry or r.name != "registry"]

    total = len(rules)
    scan_start = time.perf_counter()

    for idx, rule_module in enumerate(rules):
        if progress_cb:
            elapsed = time.perf_counter() - scan_start
            avg_per_rule = elapsed / max(idx, 1)
            remaining = avg_per_rule * (total - idx)
            progress_cb(rule_module.display_name, idx, total, elapsed, remaining)

        rule_start = time.perf_counter()
        try:
            category = rule_module.scan()
            rule_duration = time.perf_counter() - rule_start
            if category:
                category.scan_duration_s = rule_duration
                if category.item_count > 0:
                    result.categories.append(category)
        except Exception:
            rule_duration = time.perf_counter() - rule_start
            # Create an empty category with error info
            error_cat = CleanupCategory(
                name=rule_module.display_name,
                description=rule_module.description,
                risk=rule_module.risk,
                scan_error=traceback.format_exc(),
                scan_duration_s=rule_duration,
            )
            result.categories.append(error_cat)

    result.total_scan_duration_s = time.perf_counter() - scan_start

    if progress_cb:
        progress_cb("Done", total, total, result.total_scan_duration_s, 0.0)

    return result
