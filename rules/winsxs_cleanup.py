"""
Rule: WinSxS Component Store Cleanup
Uses DISM to analyze the Windows Component Store (WinSxS) and offers
to clean up superseded components via DISM /StartComponentCleanup.

WinSxS cannot be directly deleted — files are hard-linked with System32.
The only safe approach is to delegate to DISM.exe.
"""

from __future__ import annotations

import os
import subprocess

from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "winsxs_cleanup"
display_name = "WinSxS Component Store"
description = "Superseded Windows components (cleaned via DISM)"
risk = RiskLevel.MEDIUM


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    # Run DISM AnalyzeComponentStore to get reclaimable size
    reclaimable = _analyze_component_store()

    if reclaimable > 0:
        category.items.append(CleanupItem(
            path="Dism.exe /Online /Cleanup-Image /StartComponentCleanup",
            size=reclaimable,
            category=category.name,
            risk=risk,
            item_type=ItemType.COMMAND,
            description=(
                "DISM: Remove superseded components "
                "(prevents rollback of old updates)"
            ),
        ))

    return category


def _analyze_component_store() -> int:
    """
    Run DISM /AnalyzeComponentStore and parse the reclaimable space.

    Returns estimated reclaimable bytes, or 0 if analysis fails.
    """
    try:
        result = subprocess.run(
            ["Dism.exe", "/Online", "/Cleanup-Image", "/AnalyzeComponentStore"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return 0

        return _parse_reclaimable(result.stdout)

    except (subprocess.TimeoutExpired, OSError, PermissionError):
        return 0


def _parse_reclaimable(output: str) -> int:
    """
    Parse DISM output to extract reclaimable space.

    Looks for lines like:
        Reclaimable Packages : 3
        Component Store Cleanup Recommended : Yes
        Backups and Disabled Features : 1.25 GB

    We use "Backups and Disabled Features" as the reclaimable estimate.
    Falls back to a conservative estimate if the line isn't found but
    cleanup is recommended.
    """
    cleanup_recommended = False
    reclaimable_bytes = 0

    for line in output.splitlines():
        line_stripped = line.strip()

        if "Component Store Cleanup Recommended" in line_stripped:
            if "Yes" in line_stripped:
                cleanup_recommended = True

        if "Backups and Disabled Features" in line_stripped:
            reclaimable_bytes = _parse_size_value(line_stripped)

    # If cleanup is recommended but we couldn't parse a size, estimate 1 GB
    if cleanup_recommended and reclaimable_bytes == 0:
        reclaimable_bytes = 1_073_741_824  # 1 GB estimate

    return reclaimable_bytes


def _parse_size_value(line: str) -> int:
    """
    Parse a DISM size line like "Backups and Disabled Features : 1.25 GB"
    Returns bytes.
    """
    try:
        # Split on ":" and take the value part
        _, value_part = line.rsplit(":", 1)
        value_part = value_part.strip()

        # Try to extract number and unit
        parts = value_part.split()
        if len(parts) >= 2:
            number = float(parts[0].replace(",", "."))
            unit = parts[1].upper()
            multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
            return int(number * multipliers.get(unit, 1))
    except (ValueError, IndexError):
        pass
    return 0
