"""
SysClean — Deletion engine with safety checks, progress, and logging.
"""

from __future__ import annotations

import csv
import os
import shutil
import stat
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from models import CleanupItem, ItemType, ScanResult


def clean(
    result: ScanResult,
    log_dir: str = ".",
) -> Tuple[int, int, int, str, float]:
    """
    Delete all selected items from the scan result.

    Args:
        result: ScanResult with items marked as selected.
        log_dir: Directory to write the deletion log CSV.

    Returns:
        Tuple of (deleted_count, failed_count, bytes_freed, log_path, duration_s).
    """
    # Collect all selected items
    items: List[CleanupItem] = []
    for cat in result.categories:
        for item in cat.items:
            if item.selected:
                items.append(item)

    if not items:
        return 0, 0, 0, "", 0.0

    # Prepare log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"cleanup_log_{timestamp}.csv")

    deleted = 0
    failed = 0
    freed = 0
    log_rows: List[dict] = []

    from models import _format_duration

    clean_start = time.perf_counter()

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[timing]}[/]"),
    ) as progress:
        task = progress.add_task("Cleaning...", total=len(items), timing="")

        for i, item in enumerate(items):
            success = False
            error_msg = ""
            item_start = time.perf_counter()

            # Run deletion in background thread so we can update the
            # progress bar timing while a large item is being deleted.
            result_holder: dict = {}

            def _do_delete(itm=item):
                try:
                    if itm.item_type == ItemType.COMMAND:
                        result_holder["ok"] = _run_cleanup_command(itm.path)
                    elif itm.item_type == ItemType.REGISTRY_KEY:
                        result_holder["ok"] = _delete_registry_key(itm.path)
                    elif itm.item_type == ItemType.FILE:
                        result_holder["ok"] = _delete_file(itm.path)
                    elif itm.item_type == ItemType.DIRECTORY:
                        result_holder["ok"] = _delete_directory(itm.path)
                except Exception as exc:
                    result_holder["ok"] = False
                    result_holder["err"] = str(exc)

            worker = threading.Thread(target=_do_delete, daemon=True)
            worker.start()

            # Poll every 0.5 s so the timer keeps ticking
            while worker.is_alive():
                worker.join(timeout=0.5)
                elapsed = time.perf_counter() - clean_start
                done = i  # not yet completed
                avg_per_item = elapsed / max(done, 1)
                remaining_est = avg_per_item * (len(items) - done)
                timing_str = (f"elapsed {_format_duration(elapsed)} | "
                              f"ETA {_format_duration(remaining_est)}")
                progress.update(task, completed=i, timing=timing_str)

            success = result_holder.get("ok", False)
            error_msg = result_holder.get("err", "")

            if success:
                deleted += 1
                freed += item.size
            else:
                failed += 1
                if not error_msg:
                    error_msg = "Delete returned False"

            item_duration = time.perf_counter() - item_start
            elapsed = time.perf_counter() - clean_start
            done = i + 1
            avg_per_item = elapsed / done
            remaining_est = avg_per_item * (len(items) - done)

            log_rows.append({
                "timestamp": datetime.now().isoformat(),
                "path": item.path,
                "type": item.item_type.value,
                "category": item.category,
                "size_bytes": item.size,
                "status": "deleted" if success else "failed",
                "error": error_msg,
                "duration_ms": f"{item_duration * 1000:.1f}",
            })

            timing_str = (f"elapsed {_format_duration(elapsed)} | "
                          f"ETA {_format_duration(remaining_est)}")
            progress.update(task, completed=done, timing=timing_str)

    total_duration = time.perf_counter() - clean_start

    # Write log CSV
    _write_log(log_path, log_rows)

    return deleted, failed, freed, log_path, total_duration


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


def _run_cleanup_command(command: str) -> bool:
    """Run a cleanup command (e.g. DISM, pnputil) as a subprocess."""
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError, PermissionError):
        return False


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

    fieldnames = ["timestamp", "path", "type", "category", "size_bytes", "status", "error", "duration_ms"]
    try:
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, PermissionError):
        pass
