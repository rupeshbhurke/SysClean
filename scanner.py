"""
SysClean — Scanner engine that orchestrates rule modules to collect cleanup items.
"""

from __future__ import annotations

import os
import time
import traceback
from pathlib import Path
from typing import Callable, List, Optional
import threading

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

    def emit_progress(label: str, completed_count: int):
        if not progress_cb:
            return
        elapsed = time.perf_counter() - scan_start
        divisor = completed_count if completed_count > 0 else 1
        avg_per_rule = elapsed / divisor
        remaining = avg_per_rule * max(total - completed_count, 0)
        progress_cb(label, completed_count, total, elapsed, remaining)

    for idx, rule_module in enumerate(rules):
        label = f"{rule_module.display_name} ({idx + 1}/{total})"
        emit_progress(label, idx)

        rule_start = time.perf_counter()
        result_holder: dict[str, CleanupCategory] = {}
        error_holder: dict[str, str] = {}

        def _run_rule() -> None:
            try:
                category = rule_module.scan()
                if category:
                    result_holder["category"] = category
            except Exception:
                error_holder["trace"] = traceback.format_exc()

        worker = threading.Thread(
            target=_run_rule,
            name=f"SysCleanRule-{rule_module.name}",
            daemon=True,
        )
        worker.start()

        while worker.is_alive():
            worker.join(timeout=0.2)
            if worker.is_alive():
                emit_progress(label, idx)

        worker.join()
        rule_duration = time.perf_counter() - rule_start

        if error_holder:
            error_cat = CleanupCategory(
                name=rule_module.display_name,
                description=rule_module.description,
                risk=rule_module.risk,
                scan_error=error_holder["trace"],
                scan_duration_s=rule_duration,
            )
            result.categories.append(error_cat)
            emit_progress(f"{rule_module.display_name} ✗ ({idx + 1}/{total})", idx + 1)
            continue

        category = result_holder.get("category")
        if category:
            category.scan_duration_s = rule_duration
            if category.item_count > 0:
                result.categories.append(category)

        emit_progress(f"{rule_module.display_name} ✓ ({idx + 1}/{total})", idx + 1)

    result.total_scan_duration_s = time.perf_counter() - scan_start

    emit_progress("Done", total)

    return result
