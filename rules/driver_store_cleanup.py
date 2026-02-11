"""
Rule: DriverStore Old Drivers
Enumerates third-party drivers via pnputil, identifies old versions
(same OriginalFileName with an older version), and offers to remove
them via pnputil /delete-driver.

This can reclaim 5-20+ GB especially on systems with NVIDIA updates.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import defaultdict
from typing import Dict, List, Tuple

from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "driver_store_cleanup"
display_name = "Old Driver Packages"
description = "Superseded driver versions in DriverStore\\FileRepository"
risk = RiskLevel.MEDIUM


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    drivers = _enumerate_drivers()
    if not drivers:
        return category

    # Group drivers by OriginalFileName (the "real" driver identity)
    groups: Dict[str, List[dict]] = defaultdict(list)
    for drv in drivers:
        key = drv.get("original_name", "").lower()
        if key:
            groups[key].append(drv)

    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
    repo_dir = os.path.join(windir, "System32", "DriverStore", "FileRepository")

    for orig_name, drv_list in groups.items():
        if len(drv_list) < 2:
            continue  # Only one version, nothing to clean

        # Sort by version descending, then date descending — keep the first (newest)
        drv_list.sort(key=lambda d: (d.get("version", ""), d.get("date", "")), reverse=True)

        # All except the newest are candidates for removal
        for drv in drv_list[1:]:
            published_name = drv.get("published_name", "")
            if not published_name:
                continue

            # Estimate size from the FileRepository folder
            # Driver folders are named like: <inf_name_without_ext>.inf_<arch>_<hash>
            folder_size = _estimate_driver_folder_size(repo_dir, published_name)

            provider = drv.get("provider", "Unknown")
            class_name = drv.get("class_name", "Unknown")
            version = drv.get("version", "?")

            category.items.append(CleanupItem(
                path=f"pnputil /delete-driver {published_name}",
                size=folder_size,
                category=category.name,
                risk=risk,
                item_type=ItemType.COMMAND,
                description=(
                    f"Old {class_name} driver v{version} "
                    f"by {provider} ({published_name})"
                ),
            ))

    return category


def _enumerate_drivers() -> List[dict]:
    """
    Run pnputil /enum-drivers and parse the output into a list of dicts.

    Each dict has keys: published_name, original_name, provider,
    class_name, version, date, signer.
    """
    try:
        result = subprocess.run(
            ["pnputil", "/enum-drivers"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []

        return _parse_pnputil_output(result.stdout)

    except (subprocess.TimeoutExpired, OSError, PermissionError):
        return []


def _parse_pnputil_output(output: str) -> List[dict]:
    """Parse pnputil /enum-drivers output into structured records."""
    drivers: List[dict] = []
    current: dict = {}

    # Mapping of pnputil field labels to our dict keys
    field_map = {
        "published name": "published_name",
        "original name": "original_name",
        "provider name": "provider",
        "class name": "class_name",
        "class guid": "class_guid",
        "driver version": "version",
        "signer name": "signer",
    }

    for line in output.splitlines():
        line = line.strip()
        if not line:
            if current:
                drivers.append(current)
                current = {}
            continue

        # Lines are like "Published Name : oem42.inf"
        match = re.match(r"^(.+?)\s*:\s*(.+)$", line)
        if match:
            label = match.group(1).strip().lower()
            value = match.group(2).strip()

            # "Driver Version and Date" is special: "mm/dd/yyyy version"
            if label == "driver version and date":
                parts = value.split()
                if len(parts) >= 2:
                    current["date"] = parts[0]
                    current["version"] = parts[1]
                elif parts:
                    current["version"] = parts[0]
            else:
                key = field_map.get(label)
                if key:
                    current[key] = value

    if current:
        drivers.append(current)

    return drivers


def _estimate_driver_folder_size(repo_dir: str, published_name: str) -> int:
    """
    Estimate the size of a driver package folder in FileRepository.

    Driver folders are named like: <inf_basename>.inf_<arch>_<hash>
    We look for folders starting with the published inf name prefix.
    """
    if not os.path.isdir(repo_dir):
        return 0

    # published_name is like "oem42.inf" — look for folders starting with "oem42.inf_"
    prefix = published_name.lower()
    total = 0

    try:
        for entry in os.scandir(repo_dir):
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower().startswith(prefix):
                        total += _dir_size(entry.path)
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass

    return total


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
