"""
SysClean — Registry Analyzer (conservative, read-only scan).

Detects:
  1. Orphaned Uninstall entries (install path no longer exists)
  2. Invalid Shared DLLs (DLL path no longer exists)
  3. Orphaned COM/ActiveX CLSIDs (InProcServer32 DLL missing)
  4. Dead Startup entries (Run/RunOnce pointing to missing executables)
  5. Stale MUI Cache entries (executables no longer exist)
  6. Orphaned App Paths (application paths for uninstalled programs)

Never modifies system/service registry keys. All scans are read-only.
"""

from __future__ import annotations

import os
import re
import winreg
from typing import List

from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

name = "registry"
display_name = "Orphaned Registry Entries"
description = "Orphaned uninstall, COM, startup, SharedDLL, MUI cache, and App Path entries"
risk = RiskLevel.REGISTRY


def scan() -> CleanupCategory:
    """Scan multiple registry locations for orphaned entries."""
    category = CleanupCategory(
        name=display_name,
        description=description,
        risk=risk,
    )

    # 1. Orphaned Uninstall entries
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

    # 2. Invalid Shared DLLs
    _scan_shared_dlls(category)

    # 3. Orphaned COM/ActiveX CLSIDs
    _scan_orphaned_com(category)

    # 4. Dead Startup entries
    _scan_dead_startup(category)

    # 5. Stale MUI Cache
    _scan_mui_cache(category)

    # 6. Orphaned App Paths
    _scan_app_paths(category)

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


# ── 2. Invalid Shared DLLs ──────────────────────────────────────────────────

def _scan_shared_dlls(category: CleanupCategory) -> None:
    """Detect SharedDLLs entries where the DLL file no longer exists on disk."""
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\SharedDLLs"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path,
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            num_values = winreg.QueryInfoKey(key)[1]
            for i in range(num_values):
                try:
                    value_name, value_data, value_type = winreg.EnumValue(key, i)
                    # value_name is the DLL path, value_data is the reference count
                    if value_name and len(value_name) > 3:
                        clean_path = value_name.strip().strip('"')
                        if clean_path and not os.path.exists(clean_path):
                            full_key = f"HKLM\\{key_path}\\{value_name}"
                            category.items.append(CleanupItem(
                                path=full_key,
                                size=0,
                                category=category.name,
                                risk=RiskLevel.REGISTRY,
                                item_type=ItemType.REGISTRY_KEY,
                                description=f"SharedDLL missing: {os.path.basename(clean_path)}",
                            ))
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError, FileNotFoundError):
        pass


# ── 3. Orphaned COM/ActiveX CLSIDs ──────────────────────────────────────────

# System CLSIDs that should never be flagged
_SYSTEM_CLSID_PREFIXES = {
    "{00000", "{0000001",  # Common system CLSIDs
}

def _scan_orphaned_com(category: CleanupCategory) -> None:
    """Detect CLSID entries whose InProcServer32 DLL no longer exists."""
    clsid_path = r"CLSID"
    max_check = 2000  # Safety limit — HKCR\CLSID can have thousands of entries

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, clsid_path) as clsid_key:
            subkey_count = winreg.QueryInfoKey(clsid_key)[0]
            checked = 0

            for i in range(subkey_count):
                if checked >= max_check:
                    break
                try:
                    clsid_name = winreg.EnumKey(clsid_key, i)

                    # Skip non-GUID entries
                    if not clsid_name.startswith("{") or not clsid_name.endswith("}"):
                        continue

                    checked += 1

                    # Try InProcServer32
                    inproc_path = f"{clsid_name}\\InProcServer32"
                    try:
                        with winreg.OpenKey(clsid_key, inproc_path) as inproc_key:
                            dll_path = _get_string_value(inproc_key, "")
                            if dll_path and len(dll_path) > 3:
                                clean = _extract_exe_path(dll_path)
                                if clean and not _is_system_path(clean) and not os.path.exists(clean):
                                    full_key = f"HKCR\\CLSID\\{clsid_name}"
                                    # Try to get a friendly name
                                    friendly = ""
                                    try:
                                        with winreg.OpenKey(clsid_key, clsid_name) as name_key:
                                            friendly = _get_string_value(name_key, "")
                                    except (OSError, PermissionError):
                                        pass
                                    desc = f"COM object missing DLL: {os.path.basename(clean)}"
                                    if friendly:
                                        desc = f"{friendly} — {desc}"
                                    category.items.append(CleanupItem(
                                        path=full_key,
                                        size=0,
                                        category=category.name,
                                        risk=RiskLevel.REGISTRY,
                                        item_type=ItemType.REGISTRY_KEY,
                                        description=desc,
                                    ))
                    except (OSError, PermissionError, FileNotFoundError):
                        pass

                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError, FileNotFoundError):
        pass


# ── 4. Dead Startup Entries ──────────────────────────────────────────────────

def _scan_dead_startup(category: CleanupCategory) -> None:
    """Detect Run/RunOnce values pointing to missing executables."""
    startup_keys = [
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
    ]

    for hive, key_path in startup_keys:
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                num_values = winreg.QueryInfoKey(key)[1]
                for i in range(num_values):
                    try:
                        value_name, value_data, value_type = winreg.EnumValue(key, i)
                        if value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                            continue
                        if not value_data:
                            continue

                        exe_path = _extract_exe_path(str(value_data))
                        if exe_path and len(exe_path) > 3 and not os.path.exists(exe_path):
                            hive_str = _hive_name(hive)
                            full_key = f"{hive_str}\\{key_path}\\{value_name}"
                            category.items.append(CleanupItem(
                                path=full_key,
                                size=0,
                                category=category.name,
                                risk=RiskLevel.REGISTRY,
                                item_type=ItemType.REGISTRY_KEY,
                                description=f"Dead startup: {value_name} → {exe_path}",
                            ))
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError, FileNotFoundError):
            pass


# ── 5. Stale MUI Cache ──────────────────────────────────────────────────────

def _scan_mui_cache(category: CleanupCategory) -> None:
    """Detect MUI Cache entries for executables that no longer exist."""
    mui_path = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
    max_check = 1000

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, mui_path) as key:
            num_values = winreg.QueryInfoKey(key)[1]
            orphaned = 0

            for i in range(num_values):
                if orphaned >= max_check:
                    break
                try:
                    value_name, value_data, value_type = winreg.EnumValue(key, i)

                    # MUI Cache value names are like "C:\path\app.exe.FriendlyAppName"
                    # or "C:\path\app.exe.ApplicationCompany"
                    if not value_name or "\\" not in value_name:
                        continue

                    # Extract the exe path (before .FriendlyAppName suffix)
                    # Pattern: path.exe.SomeSuffix
                    exe_match = re.match(r'^(.+\.exe)', value_name, re.IGNORECASE)
                    if not exe_match:
                        continue

                    exe_path = exe_match.group(1)
                    if len(exe_path) > 3 and not _is_system_path(exe_path) and not os.path.exists(exe_path):
                        orphaned += 1
                        full_key = f"HKCU\\{mui_path}\\{value_name}"
                        category.items.append(CleanupItem(
                            path=full_key,
                            size=0,
                            category=category.name,
                            risk=RiskLevel.REGISTRY,
                            item_type=ItemType.REGISTRY_KEY,
                            description=f"Stale MUI cache: {os.path.basename(exe_path)}",
                        ))
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError, FileNotFoundError):
        pass


# ── 6. Orphaned App Paths ───────────────────────────────────────────────────

def _scan_app_paths(category: CleanupCategory) -> None:
    """Detect App Paths entries for programs whose executables no longer exist."""
    app_paths_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, app_paths_key,
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            subkey_count = winreg.QueryInfoKey(key)[0]

            for i in range(subkey_count):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        # Default value is the full path to the executable
                        exe_path = _get_string_value(subkey, "")
                        if not exe_path:
                            continue

                        clean = _extract_exe_path(exe_path)
                        if clean and len(clean) > 3 and not _is_system_path(clean):
                            if not os.path.exists(clean):
                                full_key = f"HKLM\\{app_paths_key}\\{subkey_name}"
                                category.items.append(CleanupItem(
                                    path=full_key,
                                    size=0,
                                    category=category.name,
                                    risk=RiskLevel.REGISTRY,
                                    item_type=ItemType.REGISTRY_KEY,
                                    description=f"Orphaned App Path: {subkey_name} → {clean}",
                                ))
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError, FileNotFoundError):
        pass


# ── Shared helpers ───────────────────────────────────────────────────────────

def _extract_exe_path(raw: str) -> str:
    """
    Extract a file path from a registry value that may contain arguments,
    quotes, or environment variables.
    """
    if not raw:
        return ""

    s = raw.strip()

    # Handle quoted paths: "C:\path\app.exe" /args
    if s.startswith('"'):
        end = s.find('"', 1)
        if end != -1:
            s = s[1:end]
        else:
            s = s[1:]
    else:
        # Take everything before the first space that looks like an argument
        # but be careful with paths containing spaces
        parts = s.split()
        candidate = ""
        for part in parts:
            if candidate:
                test = candidate + " " + part
            else:
                test = part
            if os.path.exists(test):
                candidate = test
            elif not candidate:
                candidate = part
            else:
                break
        s = candidate if candidate else parts[0] if parts else s

    # Expand environment variables
    s = os.path.expandvars(s)

    return s.strip().strip('"')


def _is_system_path(path: str) -> bool:
    """Check if a path is a core Windows system file that should never be flagged."""
    path_lower = path.lower()
    # Never flag core Windows components
    system_dirs = [
        os.environ.get("SYSTEMROOT", r"C:\Windows").lower() + "\\system32",
        os.environ.get("SYSTEMROOT", r"C:\Windows").lower() + "\\syswow64",
    ]
    for sd in system_dirs:
        if path_lower.startswith(sd):
            return True
    return False


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
