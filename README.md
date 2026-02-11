# SysClean — Deep Windows 11 System Cleanup Utility

```
   ____            ____ _
  / ___| _   _ ___/ ___| | ___  __ _ _ __
  \___ \| | | / __| |   | |/ _ \/ _` | '_ \
   ___) | |_| \__ \ |___| |  __/ (_| | | | |
  |____/ \__, |___/\____|_|\___|\__,_|_| |_|
         |___/
```

A powerful, interactive, CLI-based Windows 11 system cleanup utility built with Python and [Rich](https://github.com/Textualize/rich). SysClean scans for reclaimable disk space across temp files, caches, logs, old Windows installations, and optionally analyzes the registry for orphaned entries — then lets you selectively delete what you don't need.

---

## Features

| Feature | Description |
|---|---|
| **9 Built-in Scan Rules** | Temp files, Windows Update cache, Prefetch, browser/font/thumbnail caches, logs & crash dumps, Delivery Optimization, Installer patch cache, old Windows installations, Recycle Bin |
| **Registry Analyzer** | Conservative orphaned-uninstall-entry detection (opt-in via `--include-registry`) |
| **3-Phase Interactive UI** | Phase 1: category toggle → Phase 2: per-item drill-down (paginated) → Phase 3: final confirmation |
| **Risk Levels** | Every item tagged as SAFE / LOW / MEDIUM / REGISTRY so users can make informed decisions |
| **CSV Audit Log** | Every deletion (success or failure) is logged with timestamps for accountability |
| **Admin-Aware** | Detects elevation status; runs in limited mode if not admin, with clear guidance |
| **Multiple Modes** | `--scan-only` (report only), `--auto` (headless batch delete), or interactive (default) |

---

## Project Structure

```
SysClean/
├── main.py                  # Entry point — CLI args, banner, orchestration
├── scanner.py               # Scan engine — loads rule modules, aggregates results
├── cleaner.py               # Deletion engine — safety checks, progress bar, CSV logging
├── models.py                # Data models — CleanupItem, CleanupCategory, ScanResult, RiskLevel
├── registry_analyzer.py     # Registry scanner — orphaned Uninstall key detection + deletion
├── ui.py                    # Rich-powered 3-phase interactive selection UI
├── requirements.txt         # Dependencies (rich>=13.0.0)
├── rules/                   # Pluggable scan rule modules
│   ├── __init__.py          # Rule registry (ALL_RULES list)
│   ├── temp_files.py        # %TEMP% and Windows\Temp
│   ├── windows_update.py    # SoftwareDistribution\Download
│   ├── prefetch.py          # Windows\Prefetch (.pf files)
│   ├── caches.py            # Thumbnail, font, browser caches (Edge, Firefox)
│   ├── logs_reports.py      # Windows logs, WER reports, crash dumps, MEMORY.DMP
│   ├── delivery_optimization.py  # Delivery Optimization peer-to-peer cache
│   ├── installer.py         # $PatchCache$ and orphaned .tmp in Windows\Installer
│   ├── old_windows.py       # Windows.old, $Windows.~BT, $Windows.~WS
│   └── recycle_bin.py       # $Recycle.Bin on all drives
└── venv/                    # Virtual environment (not committed)
```

---

## Quick Start

### Prerequisites

- **Python 3.10+** on Windows 11
- **Administrator terminal** recommended (required for system directories like `C:\Windows\Temp`, `Prefetch`, `SoftwareDistribution`)

### Installation

```powershell
cd SysClean
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Usage

```powershell
# Interactive mode (default) — scan, select, delete
python main.py

# Scan and report only — no deletions
python main.py --scan-only

# Include orphaned registry entry detection
python main.py --include-registry

# Auto-delete everything found (no interactive prompts)
python main.py --auto

# Specify log output directory
python main.py --log-dir C:\Logs
```

---

## How It Works

1. **Scan** — Each rule module in `rules/` exposes a `scan()` function that returns a `CleanupCategory` containing discovered `CleanupItem`s.
2. **Display** — The UI shows a summary, then walks the user through 3 phases: category selection → item-level review → final confirmation.
3. **Clean** — The `cleaner.py` engine iterates selected items, handles read-only attributes, logs every action to CSV, and reports results.
4. **Registry** (opt-in) — `registry_analyzer.py` reads `HKLM` and `HKCU` Uninstall keys, checks if `InstallLocation` paths still exist, and flags orphans. It never touches system components or Windows Updates.

---

## Architecture

The project follows a **pluggable rule-module** pattern:

- Each file in `rules/` is a self-contained module that exports `name`, `display_name`, `description`, `risk`, and `scan()`.
- `rules/__init__.py` registers them in `ALL_RULES`.
- `scanner.py` iterates `ALL_RULES`, calling each `scan()` and aggregating into a `ScanResult`.
- Adding a new cleanup category = adding a new file in `rules/` and registering it in `__init__.py`.

---

## Current Scan Rules

| Rule | Paths Scanned | Risk |
|---|---|---|
| **Temporary Files** | `%TEMP%`, `C:\Windows\Temp` | SAFE |
| **Windows Update Cache** | `SoftwareDistribution\Download` | SAFE |
| **Prefetch Files** | `C:\Windows\Prefetch\*.pf` | LOW |
| **Caches** | Thumbnail cache, Font cache, Edge cache, Firefox cache | SAFE |
| **Logs & Error Reports** | `Windows\Logs`, WER (user & system), Minidumps, `MEMORY.DMP` | SAFE |
| **Delivery Optimization** | DO cache directories | SAFE |
| **Installer Patch Cache** | `$PatchCache$`, orphaned `.tmp` in `Windows\Installer` | MEDIUM |
| **Old Windows Installations** | `Windows.old`, `$Windows.~BT`, `$Windows.~WS` | SAFE |
| **Recycle Bin** | `$Recycle.Bin` on all drives | SAFE |
| **Orphaned Registry Entries** | Uninstall keys (HKLM + HKCU, 64-bit + 32-bit) | REGISTRY |

---

## Suggested Upgrades & Roadmap

### Phase 1 — Expand Core Cleanup Rules

#### 1. Developer-Specific Profiles
Add scan rule modules targeting developer tool caches. These can accumulate **tens of GB** on active dev machines:

| Profile | Paths to Scan | Safe? |
|---|---|---|
| **Node.js / Frontend** | `%APPDATA%\npm-cache`, stale `node_modules` (via age heuristic or project staleness), `%LOCALAPPDATA%\Yarn\Cache`, `%LOCALAPPDATA%\pnpm-store` | Yes |
| **Python** | `%LOCALAPPDATA%\pip\Cache`, `%USERPROFILE%\.cache\pip`, `__pycache__` directories, `.pyc` files, `%USERPROFILE%\.conda\pkgs` | Yes |
| **.NET / C#** | `%USERPROFILE%\.nuget\packages` (with caution), `%TEMP%\NuGetScratch`, Visual Studio `ComponentModelCache`, `MEFCacheData` | Caution |
| **Java / Android** | `%USERPROFILE%\.gradle\caches`, `%USERPROFILE%\.m2\repository`, `%USERPROFILE%\.android\cache`, Android SDK temp | Yes |
| **Rust** | `%USERPROFILE%\.cargo\registry\cache`, `target/` directories in projects | Yes |
| **Go** | `%USERPROFILE%\go\pkg\mod\cache` | Yes |
| **Docker** | Docker Desktop `ext4.vhdx` compaction, dangling images/volumes (via `docker system prune`) | Caution |
| **VS Code** | `%APPDATA%\Code\CachedExtensionVSIXs`, `%APPDATA%\Code\Cache`, `%APPDATA%\Code\CachedData` | Yes |
| **Visual Studio** | `%LOCALAPPDATA%\Microsoft\VisualStudio\*\ComponentModelCache`, `.vs` folders | Yes |
| **Unity** | `%LOCALAPPDATA%\Unity\cache`, `Library/` in Unity projects | Yes |

#### 2. Additional System Cleanup Targets

| Target | Path / Method | Notes |
|---|---|---|
| **DirectX Shader Cache** | `%LOCALAPPDATA%\D3DSCache` | Auto-regenerated; safe to delete |
| **Windows Icon Cache** | `%LOCALAPPDATA%\IconCache.db`, `%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache_*.db` | Regenerated on reboot |
| **DNS Resolver Cache** | `ipconfig /flushdns` (command, not file) | Frees memory, resolves stale DNS |
| **Windows Search Index** | `%PROGRAMDATA%\Microsoft\Search\Data` | Rebuilds automatically; can be large |
| **Cortana / Copilot Cache** | `%LOCALAPPDATA%\Packages\Microsoft.Windows.Cortana_*\LocalState` | Safe |
| **Teams Classic Cache** | `%APPDATA%\Microsoft\Teams\Cache`, `blob_storage`, `GPUCache` | If Teams Classic installed |
| **OneDrive Cache** | `%LOCALAPPDATA%\Microsoft\OneDrive\logs` | Logs only |
| **Store App Cache** | `%LOCALAPPDATA%\Packages\*\TempState`, `\AC\INetCache` | Safe per-app temp |
| **System Restore Points** | `vssadmin delete shadows` | Frees significant space; MEDIUM risk |
| **Hibernate File** | `powercfg /hibernate off` (deletes `hiberfil.sys`) | Can free RAM-sized space |

### Phase 2 — Enhanced Registry Analysis

| Feature | Description | Registry Keys |
|---|---|---|
| **Invalid Shared DLLs** | Detect entries in `SharedDLLs` where the DLL path no longer exists | `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\SharedDLLs` |
| **Orphaned COM/ActiveX** | Detect `CLSID` entries pointing to missing InProcServer32 DLLs | `HKCR\CLSID\{...}\InProcServer32` |
| **Dead Startup Entries** | Detect Run/RunOnce values pointing to missing executables | `HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run`, `RunOnce` (+ HKLM equivalents) |
| **Stale MUI Cache** | Entries for executables that no longer exist | `HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache` |
| **Orphaned App Paths** | `App Paths` entries for uninstalled programs | `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths` |
| **Dead File Associations** | File type handlers pointing to missing executables | `HKCR\*\shell\open\command` entries |
| **Registry Backup** | Always export affected keys before deletion | Critical safety requirement |

### Phase 3 — Safety & UX Improvements

- **Recycle Bin soft-delete** — Move files to Recycle Bin instead of permanent delete (configurable)
- **Dry-run mode** — Show exactly what would be deleted with byte-accurate totals before committing
- **Snapshot/Restore** — Take a snapshot of all paths before cleanup; offer one-click restore from CSV log
- **Age-based filtering** — Only delete temp files older than N days (configurable, default 7)
- **Size threshold** — Highlight items above a configurable size (e.g., >100 MB)
- **Scheduled cleanup** — Windows Task Scheduler integration for periodic automated runs
- **Profile system** — Save/load cleanup profiles (e.g., "Frontend Dev", "Minimal", "Full Clean")
- **TUI upgrade** — Replace prompt-based UI with a [Textual](https://github.com/Textualize/textual) full-screen TUI with checkbox trees and real-time stats
- **JSON/HTML report** — Export scan results as styled HTML or machine-readable JSON
- **Exclusion lists** — User-configurable allow/deny lists for paths and patterns
- **Undo log** — Record what was deleted with enough metadata to warn user what's non-recoverable

### Phase 4 — Advanced Features

- **Disk space visualization** — Treemap or bar chart of space usage per category
- **Duplicate file finder** — Hash-based detection of duplicate files across drives
- **Large file finder** — Scan for files above a threshold (e.g., >500 MB) that aren't system-critical
- **Windows component cleanup** — Invoke `DISM /Online /Cleanup-Image /StartComponentCleanup` programmatically
- **Event log cleanup** — Clear old Windows Event Logs (`wevtutil cl`)
- **Service audit** — Identify disabled/broken services with orphaned registry entries
- **Browser data cleanup** — Cookies, history, saved passwords (with explicit user consent)
- **WMIC/PowerShell integration** — Use WMI queries for more reliable system state detection
- **Plugin system** — Allow third-party rule modules dropped into `rules/` to be auto-discovered

---

## Known Limitations

- **No Recycle Bin safety net** — Deleted files are permanently removed (not sent to Recycle Bin)
- **Chrome cache commented out** — Chrome cache scanning is present in `caches.py` but disabled
- **No age filtering** — All temp files are flagged regardless of age
- **`_dir_size` duplicated** — The same helper function is copy-pasted across multiple rule files
- **Registry analysis is opt-in only** — Only scans orphaned Uninstall entries; does not cover COM, DLLs, startup, or file associations
- **No backup before delete** — No automatic snapshot or backup mechanism
- **Windows-only** — Uses `winreg`, `ctypes.windll`; no cross-platform support (by design)

---

## Contributing

To add a new cleanup rule:

1. Create a new file in `rules/` (e.g., `rules/my_rule.py`)
2. Export the required interface:
   ```python
   from models import CleanupCategory, CleanupItem, RiskLevel, ItemType

   name = "my_rule"
   display_name = "My Rule Display Name"
   description = "What this rule cleans"
   risk = RiskLevel.SAFE  # SAFE | LOW | MEDIUM | REGISTRY

   def scan() -> CleanupCategory:
       category = CleanupCategory(name=display_name, description=description, risk=risk)
       # ... discover items and append to category.items ...
       return category
   ```
3. Register it in `rules/__init__.py` by importing and adding to `ALL_RULES`.

---

## License

Internal R&D project. Not licensed for external distribution.

---

## Disclaimer

**Use at your own risk.** SysClean permanently deletes files and registry entries. Always run `--scan-only` first to review what will be affected. Run with administrator privileges for full system access. The authors are not responsible for data loss resulting from use of this tool.
