"""
Rule: Orphaned MSI/MSP Installer Files
Detects .msi and .msp files in C:\\Windows\\Installer that are no longer
referenced by any installed product in the registry.

Detection method: enumerate all registered product packages from
HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Installer\\UserData
and compare against actual files in the Installer directory. Files not
referenced are considered orphaned.
"""

from __future__ import annotations

import os
import winreg
from typing import Set

from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "orphaned_installers"
display_name = "Orphaned Installer Packages"
description = "Unreferenced .msi/.msp files in C:\\Windows\\Installer"
risk = RiskLevel.MEDIUM


def scan() -> CleanupCategory:
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
    installer_dir = os.path.join(windir, "Installer")

    if not os.path.isdir(installer_dir):
        return category

    # Step 1: Collect all .msi/.msp filenames currently referenced in the registry
    referenced = _get_referenced_packages()

    # Step 2: Scan the Installer directory for .msi and .msp files
    try:
        for entry in os.scandir(installer_dir):
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                lower = entry.name.lower()
                if not (lower.endswith(".msi") or lower.endswith(".msp")):
                    continue

                # Check if this file is referenced
                if entry.name.lower() in referenced:
                    continue

                size = entry.stat().st_size
                if size == 0:
                    continue

                ext = os.path.splitext(entry.name)[1].lower()
                label = "Orphaned MSI package" if ext == ".msi" else "Orphaned MSP patch"

                category.items.append(CleanupItem(
                    path=entry.path,
                    size=size,
                    category=category.name,
                    risk=risk,
                    item_type=ItemType.FILE,
                    description=label,
                ))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass

    return category


def _get_referenced_packages() -> Set[str]:
    """
    Query the registry to find all .msi/.msp filenames currently referenced
    by installed products.

    Checks:
      HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Installer\\UserData\\<SID>\\Products\\<ProductCode>\\InstallProperties
        -> LocalPackage value
      HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Installer\\UserData\\<SID>\\Patches\\<PatchCode>\\Properties
        -> LocalPackage value
    """
    referenced: Set[str] = set()

    base_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UserData"

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_key) as ud_key:
            sid_count = winreg.QueryInfoKey(ud_key)[0]
            for i in range(sid_count):
                try:
                    sid = winreg.EnumKey(ud_key, i)
                except OSError:
                    continue

                # Products
                _collect_local_packages(
                    referenced,
                    f"{base_key}\\{sid}\\Products",
                    "InstallProperties",
                )

                # Patches
                _collect_local_packages(
                    referenced,
                    f"{base_key}\\{sid}\\Patches",
                    "Properties",
                )

    except OSError:
        pass

    return referenced


def _collect_local_packages(
    referenced: Set[str],
    sub_path: str,
    props_subkey: str,
) -> None:
    """Walk product/patch subkeys and extract LocalPackage filenames."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path) as parent:
            count = winreg.QueryInfoKey(parent)[0]
            for i in range(count):
                try:
                    code = winreg.EnumKey(parent, i)
                    props_path = f"{sub_path}\\{code}\\{props_subkey}"
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, props_path) as pk:
                        val, _ = winreg.QueryValueEx(pk, "LocalPackage")
                        if val:
                            referenced.add(os.path.basename(val).lower())
                except OSError:
                    continue
    except OSError:
        pass
