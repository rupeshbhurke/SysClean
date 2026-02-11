r"""
SysClean - Deep Windows 11 System Cleanup Utility

Entry point: orchestrates scanning -> interactive selection -> cleanup.

Usage:
    python main.py                      Interactive full cleanup
    python main.py --scan-only          Scan and report only (no deletion)
    python main.py --include-registry   Include orphaned registry entry detection
    python main.py --auto               Auto-select all and delete (skip UI)
    python main.py --dry-run            Show what would be deleted (no actual deletion)
    python main.py --profile frontend   Use a cleanup profile
    python main.py --min-age 7          Only target files older than 7 days
    python main.py --exclude C:\\Keep    Exclude a path from cleanup
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

BANNER = r"""
   ____            ____ _
  / ___| _   _ ___/ ___| | ___  __ _ _ __
  \___ \| | | / __| |   | |/ _ \/ _` | '_ \
   ___) | |_| \__ \ |___| |  __/ (_| | | | |
  |____/ \__, |___/\____|_|\___|\__,_|_| |_|
         |___/
  Deep Windows 11 System Cleanup Utility v2.0
"""


def is_admin() -> bool:
    """Check if the script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_elevation() -> None:
    """Show message about needing admin rights."""
    console.print(Panel(
        "[bold red](!!) Administrator privileges required![/]\n\n"
        "SysClean needs admin rights to access system directories like:\n"
        "  - C:\\Windows\\Temp\n"
        "  - C:\\Windows\\Prefetch\n"
        "  - C:\\Windows\\SoftwareDistribution\n\n"
        "Please right-click your terminal and select\n"
        "[bold]'Run as administrator'[/], then try again.",
        border_style="red",
        title="[bold]Elevation Required[/]",
    ))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SysClean - Deep Windows 11 System Cleanup Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Scan and display results without deleting anything",
    )
    parser.add_argument(
        "--include-registry",
        action="store_true",
        help="Include orphaned registry entry detection",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-select all items and delete without interactive UI",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=".",
        help="Directory to save the cleanup log CSV (default: current dir)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting anything",
    )
    parser.add_argument(
        "--min-age",
        type=int,
        default=0,
        metavar="DAYS",
        help="Only target files older than DAYS days (default: 0 = no filter)",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        metavar="NAME",
        help="Use a cleanup profile: minimal, standard, frontend, backend, fullstack, everything",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=[],
        metavar="PATH",
        help="Paths to exclude from cleanup",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available cleanup profiles and exit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Print banner
    console.print(f"[bold cyan]{BANNER}[/]")

    # -- LIST PROFILES --
    if args.list_profiles:
        from config import BUILTIN_PROFILES
        console.print("[bold cyan]Available Cleanup Profiles:[/]\n")
        for name, profile in BUILTIN_PROFILES.items():
            console.print(f"  [bold]{name:12s}[/] — {profile.description}")
            console.print(f"               [dim]Rules: {', '.join(profile.rules)}[/]")
        return 0

    # Check admin
    if not is_admin():
        request_elevation()
        console.print("\n[dim]Running in limited mode -- some system directories may be inaccessible.[/]\n")
        proceed = console.input("[yellow]Continue anyway? (y/n): [/]").strip().lower()
        if proceed not in ("y", "yes"):
            return 1

    # -- DRY-RUN banner --
    if args.dry_run:
        console.print(Panel(
            "[bold yellow]DRY-RUN MODE[/] — No files will be deleted.",
            border_style="yellow",
        ))

    # -- PROFILE handling --
    profile_rules = None
    if args.profile:
        from config import BUILTIN_PROFILES
        profile = BUILTIN_PROFILES.get(args.profile.lower())
        if not profile:
            console.print(f"[red]Unknown profile '{args.profile}'. "
                          f"Use --list-profiles to see options.[/]")
            return 1
        profile_rules = set(profile.rules)
        console.print(f"[cyan]Using profile: [bold]{profile.name}[/] — {profile.description}[/]")
        # If profile includes registry, auto-enable it
        if "registry" in profile_rules:
            args.include_registry = True

    # -- EXCLUSIONS --
    from config import load_exclusions, is_excluded, ExclusionConfig
    exclusions = load_exclusions()
    # Add CLI-provided exclusions
    for excl_path in args.exclude:
        exclusions.paths.add(os.path.abspath(excl_path))

    console.print("[bold]Starting deep system scan...[/]\n")

    # -- SCAN --
    from scanner import scan_all

    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold blue]Scanning: {task.description}"),
        BarColumn(bar_width=30),
        TextColumn("{task.percentage:>3.0f}%"),
        TextColumn("[cyan]({task.completed}/{task.total})[/]"),
        TextColumn("[dim]{task.fields[timing]}[/]"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=100, timing="")

        def on_progress(name: str, current: int, total: int,
                        elapsed: float = 0.0, remaining: float = 0.0):
            if total > 0:
                from models import _format_duration
                timing_str = (f"elapsed {_format_duration(elapsed)} | "
                              f"ETA {_format_duration(remaining)}")
                progress.update(task, description=name,
                                total=total, completed=current,
                                timing=timing_str)

        result = scan_all(
            include_registry=args.include_registry,
            progress_cb=on_progress,
            profile_rules=profile_rules,
        )
        progress.update(task, description="Done!", timing="")

    # -- POST-SCAN FILTERING --
    _apply_filters(result, args, exclusions)

    # -- TIMING SUMMARY --
    _show_scan_timing(result)

    # Import UI functions
    from ui import (
        show_scan_summary,
        phase1_category_selection,
        phase2_item_drilldown,
        phase3_final_confirmation,
        show_cleanup_report,
    )

    # -- DISPLAY RESULTS --
    show_scan_summary(result)

    if result.total_items == 0:
        console.print("[green]Your system is already clean! No items found to delete.[/]")
        return 0

    # -- SCAN-ONLY or DRY-RUN MODE --
    if args.scan_only or args.dry_run:
        _show_detailed_scan(result)
        if args.dry_run:
            console.print("[yellow]Dry-run mode. No files were deleted.[/]")
        else:
            console.print("[dim]Scan-only mode. No files were deleted.[/]")
        return 0

    # -- AUTO MODE --
    if args.auto:
        console.print("[yellow]Auto mode: all items selected for deletion.[/]")
        for cat in result.categories:
            cat.enabled = True
            for item in cat.items:
                item.selected = True

        from cleaner import clean
        deleted, failed, freed, log_path, clean_duration = clean(result, log_dir=args.log_dir)
        show_cleanup_report(deleted, failed, freed, log_path, clean_duration)
        return 0

    # -- INTERACTIVE MODE --
    while True:
        # Phase 1: Category selection
        proceed = phase1_category_selection(result)
        if not proceed:
            console.print("[yellow]Cleanup cancelled.[/]")
            return 0

        # Phase 2: Item drill-down
        proceed = phase2_item_drilldown(result)
        if not proceed:
            continue  # Go back to Phase 1

        # Phase 3: Final confirmation
        confirmed = phase3_final_confirmation(result)
        if not confirmed:
            continue  # Go back to Phase 1

        # -- DELETE --
        from cleaner import clean
        deleted, failed, freed, log_path, clean_duration = clean(result, log_dir=args.log_dir)
        show_cleanup_report(deleted, failed, freed, log_path, clean_duration)

        if failed > 0:
            console.print(
                f"[yellow]Note: {failed} items could not be deleted "
                f"(likely locked by the OS or another process). "
                f"Check the log for details.[/]"
            )

        return 0


def _apply_filters(result, args, exclusions) -> None:
    """Apply age-based filtering and exclusion rules to scan results."""
    import time as _time
    from config import is_excluded

    min_age_seconds = args.min_age * 86400 if args.min_age > 0 else 0
    cutoff = _time.time() - min_age_seconds if min_age_seconds > 0 else 0

    for cat in result.categories:
        if not cat.items:
            continue

        filtered = []
        for item in cat.items:
            # Check exclusions
            if is_excluded(item.path, exclusions):
                continue

            # Check age filter (only for files/directories, not registry)
            if cutoff > 0 and item.item_type.value != "registry_key":
                try:
                    mtime = os.path.getmtime(item.path)
                    if mtime >= cutoff:
                        continue  # Too new, skip
                except (OSError, PermissionError):
                    pass  # Can't stat — keep it in the list

            filtered.append(item)

        cat.items = filtered


def _show_scan_timing(result) -> None:
    """Show a table of time spent per scan rule with totals."""
    from rich.table import Table
    from rich import box
    from models import _format_duration, _format_size

    if not result.categories:
        return

    table = Table(
        box=box.ROUNDED,
        title="[bold]Scan Timing Summary[/]",
        title_style="bold cyan",
        show_lines=False,
    )
    table.add_column("#", justify="center", width=4)
    table.add_column("Category", min_width=30)
    table.add_column("Items", justify="right", width=8)
    table.add_column("Size", justify="right", width=12)
    table.add_column("Time Spent", justify="right", width=12)
    table.add_column("% of Total", justify="right", width=10)

    total_dur = result.total_scan_duration_s if result.total_scan_duration_s > 0 else 1.0

    for idx, cat in enumerate(result.categories, 1):
        pct = (cat.scan_duration_s / total_dur) * 100
        time_style = "bold red" if pct > 30 else ("yellow" if pct > 15 else "green")

        if cat.scan_error:
            table.add_row(
                str(idx), cat.name, "ERR", "-",
                f"[{time_style}]{_format_duration(cat.scan_duration_s)}[/]",
                f"[{time_style}]{pct:.1f}%[/]",
            )
        else:
            table.add_row(
                str(idx), cat.name,
                f"{cat.item_count:,}",
                cat.total_size_human,
                f"[{time_style}]{_format_duration(cat.scan_duration_s)}[/]",
                f"[{time_style}]{pct:.1f}%[/]",
            )

    # Totals row
    table.add_section()
    table.add_row(
        "", "[bold]TOTAL[/]",
        f"[bold]{result.total_items:,}[/]",
        f"[bold]{result.total_size_human}[/]",
        f"[bold]{_format_duration(result.total_scan_duration_s)}[/]",
        "[bold]100%[/]",
    )

    console.print()
    console.print(table)
    console.print()


def _show_detailed_scan(result) -> None:
    """Show a detailed breakdown of all scan results (scan-only mode)."""
    from rich.table import Table
    from rich import box
    from models import _format_size

    for cat in result.categories:
        if cat.scan_error:
            console.print(f"\n[red]X {cat.name}: SCAN ERROR[/]")
            console.print(f"  [dim]{cat.scan_error[:200]}[/]")
            continue

        console.print(f"\n[bold cyan]> {cat.name}[/] -- "
                      f"{cat.item_count:,} items, {cat.total_size_human}")

        if cat.item_count <= 20:
            table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            table.add_column("Path", max_width=75)
            table.add_column("Size", justify="right", width=12)
            for item in cat.items:
                table.add_row(item.path, item.size_human)
            console.print(table)
        else:
            # Show top 10 largest items
            sorted_items = sorted(cat.items, key=lambda x: x.size, reverse=True)
            table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            table.add_column("Path", max_width=75)
            table.add_column("Size", justify="right", width=12)
            for item in sorted_items[:10]:
                table.add_row(item.path, item.size_human)
            console.print(table)
            remaining = cat.item_count - 10
            remaining_size = sum(it.size for it in sorted_items[10:])
            console.print(f"  [dim]... and {remaining:,} more items "
                          f"({_format_size(remaining_size)})[/]")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. No changes made.[/]")
        sys.exit(130)
