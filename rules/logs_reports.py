"""
Rule: Logs & Error Reports — Windows logs, WER reports, crash dumps.
"""

from __future__ import annotations

import os
from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "logs_reports"
display_name = "Logs & Error Reports"
description = "Windows log files, error reports (WER), and crash dump files"
risk = RiskLevel.SAFE


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
    local_app = os.environ.get("LOCALAPPDATA", "")

    # ── Windows Logs directory ───────────────────────────────────────────
    logs_dir = os.path.join(windir, "Logs")
    _scan_log_dir(category, logs_dir, "Windows log")

    # ── Windows Error Reporting (user) ───────────────────────────────────
    if local_app:
        user_wer = os.path.join(local_app, "Microsoft", "Windows", "WER")
        _scan_dir_recursive(category, user_wer, "User error report")

    # ── Windows Error Reporting (system) ─────────────────────────────────
    system_wer = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                              "Microsoft", "Windows", "WER")
    _scan_dir_recursive(category, system_wer, "System error report")

    # ── Crash Dumps ──────────────────────────────────────────────────────
    minidump = os.path.join(windir, "Minidump")
    _scan_dir_flat(category, minidump, "BSOD minidump")

    if local_app:
        user_dumps = os.path.join(local_app, "CrashDumps")
        _scan_dir_flat(category, user_dumps, "User crash dump")

    # ── Memory dump ──────────────────────────────────────────────────────
    memory_dmp = os.path.join(windir, "MEMORY.DMP")
    if os.path.isfile(memory_dmp):
        try:
            size = os.path.getsize(memory_dmp)
            category.items.append(CleanupItem(
                path=memory_dmp,
                size=size,
                category=category.name,
                risk=risk,
                item_type=ItemType.FILE,
                description="Full memory dump (can be very large)",
            ))
        except (OSError, PermissionError):
            pass

    return category


def _scan_log_dir(category: CleanupCategory, log_dir: str, label: str) -> None:
    """Scan for .log, .etl, .evtx files recursively."""
    if not os.path.isdir(log_dir):
        return
    log_extensions = {".log", ".etl", ".old", ".bak"}
    try:
        for dirpath, _, filenames in os.walk(log_dir):
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in log_extensions:
                    fp = os.path.join(dirpath, f)
                    try:
                        category.items.append(CleanupItem(
                            path=fp,
                            size=os.path.getsize(fp),
                            category=category.name,
                            risk=risk,
                            item_type=ItemType.FILE,
                            description=f"{label} ({ext})",
                        ))
                    except (OSError, PermissionError):
                        pass
    except (OSError, PermissionError):
        pass


def _scan_dir_recursive(category: CleanupCategory, dir_path: str, label: str) -> None:
    """Add entire directory as a single item with computed size."""
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


def _scan_dir_flat(category: CleanupCategory, dir_path: str, label: str) -> None:
    """Add individual files from a directory."""
    if not os.path.isdir(dir_path):
        return
    try:
        for entry in os.scandir(dir_path):
            try:
                if entry.is_file(follow_symlinks=False):
                    category.items.append(CleanupItem(
                        path=entry.path,
                        size=entry.stat().st_size,
                        category=category.name,
                        risk=risk,
                        item_type=ItemType.FILE,
                        description=label,
                    ))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass


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
