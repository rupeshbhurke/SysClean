"""
SysClean — Registry Analyzer (conservative, read-only scan).

Only detects orphaned uninstall entries where the InstallLocation
no longer exists on disk. Never modifies system/service registry keys.
"""

from __future__ import annotations

import os
import winreg
from typing import List

from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "registry"
display_name = "Orphaned Registry Entries"
description = "Uninstall entries for programs whose install paths no longer exist"
risk = RiskLevel.REGISTRY


def scan() -> CleanupCategory:
    """Scan the Uninstall registry keys for orphaned entries."""
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    # Check both 64-bit and 32-bit uninstall keys
    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, key_path in uninstall_paths:
        _scan_uninstall_key(category, hive, key_path)

    return category


def _scan_uninstall_key(
    category: CleanupCategory,
    hive: int,
    key_path: str,
) -> None:
    """Scan a single Uninstall registry key for orphaned entries."""
    try:
        with winreg.OpenKey(hive, key_path) as key:
            subkey_count = winreg.QueryInfoKey(key)[0]

            for i in range(subkey_count):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        display_name_val = _get_string_value(subkey, "DisplayName")
                        install_location = _get_string_value(subkey, "InstallLocation")
                        uninstall_string = _get_string_value(subkey, "UninstallString")

                        # Skip entries without a display name (system components)
                        if not display_name_val:
                            continue

                        # Skip system components / updates
                        if _is_system_component(subkey):
                            continue

                        # Check if the install location is orphaned
                        is_orphaned = False
                        reason = ""

                        if install_location and install_location.strip():
                            clean_path = install_location.strip().strip('"')
                            if clean_path and len(clean_path) > 3:  # Skip bare drive roots
                                if not os.path.exists(clean_path):
                                    is_orphaned = True
                                    reason = f"Install path missing: {clean_path}"

                        if is_orphaned:
                            hive_name = _hive_name(hive)
                            full_key = f"{hive_name}\\{key_path}\\{subkey_name}"

                            category.items.append(CleanupItem(
                                path=full_key,
                                size=0,
                                category=category.name,
                                risk=RiskLevel.REGISTRY,
                                item_type=ItemType.REGISTRY_KEY,
                                description=f"{display_name_val} — {reason}",
                            ))

                except (OSError, PermissionError, WindowsError):
                    continue

    except (OSError, PermissionError, FileNotFoundError):
        pass


def _get_string_value(key, value_name: str) -> str:
    """Read a string value from a registry key, returning empty string on failure."""
    try:
        value, reg_type = winreg.QueryValueEx(key, value_name)
        if reg_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
            return str(value)
    except (OSError, FileNotFoundError):
        pass
    return ""


def _is_system_component(subkey) -> bool:
    """Check if the entry is a system component (should not be touched)."""
    try:
        val, _ = winreg.QueryValueEx(subkey, "SystemComponent")
        if val == 1:
            return True
    except (OSError, FileNotFoundError):
        pass

    # Skip Windows updates (KB entries)
    try:
        parent_name = _get_string_value(subkey, "ParentKeyName")
        if parent_name:
            return True
    except Exception:
        pass

    return False


def _hive_name(hive: int) -> str:
    """Return human-readable registry hive name."""
    mapping = {
        winreg.HKEY_LOCAL_MACHINE: "HKLM",
        winreg.HKEY_CURRENT_USER: "HKCU",
        winreg.HKEY_CLASSES_ROOT: "HKCR",
        winreg.HKEY_USERS: "HKU",
    }
    return mapping.get(hive, f"0x{hive:08X}")


def delete_registry_key(key_path: str) -> bool:
    """
    Delete a single orphaned registry key.

    Args:
        key_path: Full key path like 'HKLM\\SOFTWARE\\...\\KeyName'

    Returns:
        True if deleted successfully, False otherwise.
    """
    parts = key_path.split("\\", 1)
    if len(parts) != 2:
        return False

    hive_str, sub_path = parts
    hive_map = {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKU": winreg.HKEY_USERS,
    }
    hive = hive_map.get(hive_str)
    if hive is None:
        return False

    # Split into parent + leaf key
    parent_path, _, leaf_name = sub_path.rpartition("\\")
    if not parent_path or not leaf_name:
        return False

    try:
        with winreg.OpenKey(hive, parent_path, 0,
                            winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY) as parent:
            winreg.DeleteKey(parent, leaf_name)
        return True
    except (OSError, PermissionError):
        return False
