# SysClean — Deep Windows 11 System Cleanup Utility

```
   ____            ____ _
  / ___| _   _ ___/ ___| | ___  __ _ _ __
  \___ \| | | / __| |   | |/ _ \/ _` | '_ \
   ___) | |_| \__ \ |___| |  __/ (_| | | | |
  |____/ \__, |___/\____|_|\___|\__,_|_| |_|
         |___/
```

A powerful, interactive, CLI-based Windows 11 system cleanup utility built with Python and [Rich](https://github.com/Textualize/rich). SysClean scans for reclaimable disk space across temp files, caches, logs, old Windows installations, developer tool caches, GPU shader caches, and the Windows registry — then lets you selectively delete what you don't need.

---

## Features

| Feature | Description |
|---|---|
| **19 Built-in Scan Rules** | System cleanup + developer caches + GPU/shader caches + app caches |
| **7 Developer Profiles** | Node.js, Python, .NET, Java/Android, Rust/Go, Docker, IDE caches |
| **Deep Registry Analyzer** | Orphaned uninstalls, SharedDLLs, COM/ActiveX, dead startup entries, stale MUI cache, orphaned App Paths |
| **6 Cleanup Profiles** | `minimal`, `standard`, `frontend`, `backend`, `fullstack`, `everything` |
| **3-Phase Interactive UI** | Phase 1: category toggle → Phase 2: per-item drill-down (paginated) → Phase 3: final confirmation |
| **Risk Levels** | Every item tagged as SAFE / LOW / MEDIUM / REGISTRY so users can make informed decisions |
| **Dry-Run Mode** | See exactly what would be deleted without touching anything |
| **Age-Based Filtering** | `--min-age 7` to only target files older than N days |
| **Exclusion Lists** | Persistent + CLI path/pattern exclusions to protect important files |
| **CSV Audit Log** | Every deletion (success or failure) is logged with timestamps |
| **Admin-Aware** | Detects elevation status; runs in limited mode if not admin |
| **Multiple Modes** | `--scan-only`, `--dry-run`, `--auto`, `--profile`, or interactive (default) |

---

## Project Structure

```
SysClean/
├── main.py                  # Entry point — CLI args, banner, orchestration, filtering
├── scanner.py               # Scan engine — loads rule modules, aggregates results
├── cleaner.py               # Deletion engine — safety checks, progress bar, CSV logging
├── models.py                # Data models — CleanupItem, CleanupCategory, ScanResult, RiskLevel
├── config.py                # Profiles, exclusion lists, persistent config (JSON)
├── registry_analyzer.py     # Deep registry scanner — 6 analysis types + deletion
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
│   ├── recycle_bin.py       # $Recycle.Bin on all drives
│   ├── shader_cache.py      # DirectX, NVIDIA, AMD, Intel GPU/shader caches
│   ├── icon_cache.py        # Windows icon cache files
│   ├── teams_apps.py        # Teams, OneDrive, Store app caches
│   ├── dev_nodejs.py        # npm, Yarn, pnpm, Bun caches + stale node_modules
│   ├── dev_python.py        # pip, conda, Poetry, pipx caches + __pycache__
│   ├── dev_dotnet.py        # NuGet, Visual Studio caches + .vs folders
│   ├── dev_java.py          # Gradle, Maven, Android SDK caches
│   ├── dev_rust_go.py       # Cargo registry, Go module cache, stale target/
│   ├── dev_docker.py        # Docker Desktop WSL2 vhdx, logs, buildx cache
│   └── dev_ide.py           # VS Code, JetBrains, Sublime, Unity, Electron app caches
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

# Dry run — see what would be deleted without deleting
python main.py --dry-run

# Use a cleanup profile
python main.py --profile frontend
python main.py --profile backend
python main.py --profile fullstack
python main.py --profile everything

# List available profiles
python main.py --list-profiles

# Only target files older than 7 days
python main.py --min-age 7

# Exclude specific paths
python main.py --exclude "C:\Important" "D:\KeepThis"

# Include deep registry analysis
python main.py --include-registry

# Auto-delete everything found (no interactive prompts)
python main.py --auto

# Combine options
python main.py --profile fullstack --min-age 14 --dry-run --include-registry

# Specify log output directory
python main.py --log-dir C:\Logs
```

---

## Cleanup Profiles

| Profile | Description | Rules Included |
|---|---|---|
| **minimal** | Safe system cleanup only | temp_files, logs_reports, recycle_bin |
| **standard** | All system rules (default) | All 12 system rules |
| **frontend** | Standard + frontend dev caches | Standard + dev_nodejs, dev_ide |
| **backend** | Standard + backend dev caches | Standard + dev_python, dev_dotnet, dev_java, dev_docker, dev_ide |
| **fullstack** | Standard + all developer caches | Standard + all 7 dev rules |
| **everything** | All rules including registry | All 19 rules + registry |

---

## How It Works

1. **Scan** — Each rule module in `rules/` exposes a `scan()` function that returns a `CleanupCategory` containing discovered `CleanupItem`s. If a `--profile` is selected, only matching rules run.
2. **Filter** — Post-scan filtering applies `--min-age` (skip files newer than N days) and `--exclude` (skip specific paths/patterns).
3. **Display** — The UI shows a summary, then walks the user through 3 phases: category selection → item-level review → final confirmation.
4. **Clean** — The `cleaner.py` engine iterates selected items, handles read-only attributes, logs every action to CSV, and reports results.
5. **Registry** (opt-in) — `registry_analyzer.py` scans 6 registry areas: orphaned Uninstall entries, invalid SharedDLLs, orphaned COM/ActiveX CLSIDs, dead startup entries, stale MUI cache, and orphaned App Paths. System32/SysWOW64 paths are always excluded.

---

## Architecture

The project follows a **pluggable rule-module** pattern:

- Each file in `rules/` is a self-contained module that exports `name`, `display_name`, `description`, `risk`, and `scan()`.
- `rules/__init__.py` registers them in `ALL_RULES`.
- `scanner.py` iterates `ALL_RULES`, calling each `scan()` and aggregating into a `ScanResult`.
- `config.py` provides cleanup profiles, exclusion lists, and persistent settings.
- Adding a new cleanup category = adding a new file in `rules/` and registering it in `__init__.py`.

---

## All Scan Rules

### System Cleanup

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
| **GPU & Shader Caches** | DirectX D3DSCache, NVIDIA GL/DX cache, AMD GL/DX cache, Intel shader cache | SAFE |
| **Windows Icon Cache** | `IconCache.db`, Explorer `iconcache_*.db` | LOW |
| **Teams, OneDrive & Store Apps** | Teams Classic cache, OneDrive logs, Store app TempState/INetCache | SAFE |

### Developer Caches

| Rule | Paths Scanned | Risk |
|---|---|---|
| **Node.js / Frontend** | npm-cache, Yarn v1/Berry cache, pnpm store, Bun cache, stale node_modules (>30d) | SAFE |
| **Python** | pip cache, conda pkgs, Poetry cache, pipx cache, `__pycache__` dirs | SAFE |
| **.NET / C#** | NuGet packages/HTTP cache/scratch, VS ComponentModelCache/MEF, `.vs` folders, dotnet SDK cache | LOW |
| **Java / Android** | Gradle caches/wrapper/daemon, Maven .m2, Android SDK cache/AVDs, Kotlin daemon | SAFE |
| **Rust & Go** | Cargo registry cache/src/git, stale `target/` dirs (>30d), Go module cache, Go build cache | SAFE |
| **Docker** | Docker Desktop WSL2 vhdx, distro, logs, buildx cache | MEDIUM |
| **IDE & Editors** | VS Code/Insiders/Windsurf cache, JetBrains caches/logs, Sublime cache, Unity cache, Postman/Slack/Discord/Figma caches | SAFE |

### Registry Analysis (opt-in)

| Analysis | What It Detects | Registry Location |
|---|---|---|
| **Orphaned Uninstall** | Programs whose InstallLocation no longer exists | `HKLM/HKCU\...\Uninstall` |
| **Invalid Shared DLLs** | SharedDLLs entries pointing to missing files | `HKLM\...\SharedDLLs` |
| **Orphaned COM/ActiveX** | CLSID entries with missing InProcServer32 DLLs | `HKCR\CLSID\{...}\InProcServer32` |
| **Dead Startup Entries** | Run/RunOnce values pointing to missing executables | `HKCU/HKLM\...\Run`, `RunOnce` |
| **Stale MUI Cache** | Entries for executables that no longer exist | `HKCU\...\Shell\MuiCache` |
| **Orphaned App Paths** | App Paths for uninstalled programs | `HKLM\...\App Paths` |

---

## Configuration

SysClean stores persistent configuration in `%APPDATA%\SysClean\`:

- **`config.json`** — Default profile, min age, log directory
- **`exclusions.json`** — Excluded paths, glob patterns, skipped rules

### Exclusion Example

```json
{
  "paths": ["C:\\Important\\Data", "D:\\Projects\\active-project\\node_modules"],
  "patterns": ["*.important", "C:\\MyData\\**"],
  "skip_rules": ["dev_docker"]
}
```

---

## Future Roadmap

### Planned

- **Recycle Bin soft-delete** — Move files to Recycle Bin instead of permanent delete (configurable)
- **Scheduled cleanup** — Windows Task Scheduler integration for periodic automated runs
- **TUI upgrade** — Replace prompt-based UI with a [Textual](https://github.com/Textualize/textual) full-screen TUI with checkbox trees
- **JSON/HTML report** — Export scan results as styled HTML or machine-readable JSON
- **Registry backup** — Auto-export affected registry keys before deletion

### Advanced (Future)

- **Disk space visualization** — Treemap or bar chart of space usage per category
- **Duplicate file finder** — Hash-based detection of duplicate files across drives
- **Large file finder** — Scan for files above a threshold (e.g., >500 MB) that aren't system-critical
- **Windows component cleanup** — Invoke `DISM /Online /Cleanup-Image /StartComponentCleanup` programmatically
- **Event log cleanup** — Clear old Windows Event Logs (`wevtutil cl`)
- **Browser data cleanup** — Cookies, history, saved passwords (with explicit user consent)
- **Plugin system** — Allow third-party rule modules dropped into `rules/` to be auto-discovered

---

## Known Limitations

- **No Recycle Bin safety net** — Deleted files are permanently removed (not sent to Recycle Bin)
- **Chrome cache commented out** — Chrome cache scanning is present in `caches.py` but disabled
- **`_dir_size` duplicated** — The same helper function is copy-pasted across multiple rule files
- **No registry backup before delete** — No automatic `.reg` export before deletion
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
4. Optionally add the rule name to relevant profiles in `config.py`.

---

## License

MIT License — see [LICENSE](./LICENSE) for full text.

---

## Disclaimer

**Use at your own risk.** SysClean permanently deletes files and registry entries. Always run `--scan-only` or `--dry-run` first to review what will be affected. Run with administrator privileges for full system access. The authors are not responsible for data loss resulting from use of this tool.
