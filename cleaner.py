"""
SysClean — Deletion engine with safety checks, progress, and logging.
"""

from __future__ import annotations

import csv
import os
import shutil
import stat
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from models import CleanupItem, ItemType, ScanResult


def clean(
    result: ScanResult,
    log_dir: str = ".",
) -> Tuple[int, int, int, str]:
    """
    Delete all selected items from the scan result.

    Args:
        result: ScanResult with items marked as selected.
        log_dir: Directory to write the deletion log CSV.

    Returns:
        Tuple of (deleted_count, failed_count, bytes_freed, log_path).
    """
    # Collect all selected items
    items: List[CleanupItem] = []
    for cat in result.categories:
        for item in cat.items:
            if item.selected:
                items.append(item)

    if not items:
        return 0, 0, 0, ""

    # Prepare log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"cleanup_log_{timestamp}.csv")

    deleted = 0
    failed = 0
    freed = 0
    log_rows: List[dict] = []

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Cleaning...", total=len(items))

        for item in items:
            success = False
            error_msg = ""

            try:
                if item.item_type == ItemType.REGISTRY_KEY:
                    success = _delete_registry_key(item.path)
                elif item.item_type == ItemType.FILE:
                    success = _delete_file(item.path)
                elif item.item_type == ItemType.DIRECTORY:
                    success = _delete_directory(item.path)

                if success:
                    deleted += 1
                    freed += item.size
                else:
                    failed += 1
                    error_msg = "Delete returned False"
            except Exception as e:
                failed += 1
                error_msg = str(e)

            log_rows.append({
                "timestamp": datetime.now().isoformat(),
                "path": item.path,
                "type": item.item_type.value,
                "category": item.category,
                "size_bytes": item.size,
                "status": "deleted" if success else "failed",
                "error": error_msg,
            })

            progress.update(task, advance=1)

    # Write log CSV
    _write_log(log_path, log_rows)

    return deleted, failed, freed, log_path


def _delete_file(path: str) -> bool:
    """Delete a single file, handling read-only attributes."""
    if not os.path.isfile(path):
        return True  # Already gone

    try:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)
        return True
    except (OSError, PermissionError):
        return False


def _delete_directory(path: str) -> bool:
    """Delete an entire directory tree."""
    if not os.path.isdir(path):
        return True  # Already gone

    try:
        shutil.rmtree(path, onerror=_on_rm_error)
        return not os.path.exists(path)
    except (OSError, PermissionError):
        return False


def _on_rm_error(func, path, exc_info):
    """Error handler for shutil.rmtree — try to fix read-only and retry."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except (OSError, PermissionError):
        pass


def _delete_registry_key(key_path: str) -> bool:
    """Delete an orphaned registry key (delegates to registry_analyzer)."""
    try:
        from registry_analyzer import delete_registry_key
        return delete_registry_key(key_path)
    except ImportError:
        return False


def _write_log(log_path: str, rows: List[dict]) -> None:
    """Write deletion log as CSV."""
    if not rows:
        return

    fieldnames = ["timestamp", "path", "type", "category", "size_bytes", "status", "error"]
    try:
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, PermissionError):
        pass
