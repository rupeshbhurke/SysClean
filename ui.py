"""
SysClean - Multi-phase interactive selection UI using Rich.

Phase 1: Category selection (toggle entire categories)
Phase 2: Drill-down into individual items (paginated)
Phase 3: Final confirmation before deletion
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from models import CleanupCategory, CleanupItem, ScanResult, RiskLevel, ItemType, _format_size, _format_duration

console = Console()

ITEMS_PER_PAGE = 40

RISK_COLORS = {
    RiskLevel.SAFE: "green",
    RiskLevel.LOW: "yellow",
    RiskLevel.MEDIUM: "red",
    RiskLevel.REGISTRY: "magenta",
}

RISK_LABELS = {
    RiskLevel.SAFE: "[SAFE]",
    RiskLevel.LOW: "[LOW]",
    RiskLevel.MEDIUM: "[MED]",
    RiskLevel.REGISTRY: "[REG]",
}


def show_scan_summary(result: ScanResult) -> None:
    """Display a summary table after scanning."""
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Scan Complete[/]\n"
        f"Found [bold]{result.total_items:,}[/] items across "
        f"[bold]{len(result.categories)}[/] categories\n"
        f"Total reclaimable space: [bold green]{result.total_size_human}[/]",
        border_style="cyan",
    ))
    console.print()


def phase1_category_selection(result: ScanResult) -> bool:
    """
    Phase 1: Let the user toggle entire categories on/off.

    Returns True if user wants to proceed, False to abort.
    """
    while True:
        console.print()
        console.print("[bold cyan]=== PHASE 1: Category Selection ===[/]")
        console.print("[dim]Toggle categories by entering their number. "
                      "Type 'all' to select all, 'none' to deselect all, "
                      "'next' to proceed, 'quit' to exit.[/]\n")

        table = Table(
            box=box.ROUNDED,
            title="Cleanup Categories",
            title_style="bold white",
            show_lines=True,
        )
        table.add_column("#", justify="center", style="bold", width=4)
        table.add_column("Selected", justify="center", width=8)
        table.add_column("Category", min_width=30)
        table.add_column("Items", justify="right", width=8)
        table.add_column("Size", justify="right", width=12)
        table.add_column("Risk", justify="center", width=12)

        for idx, cat in enumerate(result.categories, 1):
            selected = "[x]" if cat.enabled else "[ ]"
            sel_style = "green" if cat.enabled else "dim"
            risk_color = RISK_COLORS.get(cat.risk, "white")
            risk_label = RISK_LABELS.get(cat.risk, str(cat.risk.value))

            if cat.scan_error:
                table.add_row(
                    str(idx), "ERR", cat.name, "ERROR", "-",
                    "[red]Error[/]",
                )
            else:
                table.add_row(
                    str(idx),
                    f"[{sel_style}]{selected}[/]",
                    cat.name,
                    f"{cat.item_count:,}",
                    cat.total_size_human,
                    f"[{risk_color}]{risk_label}[/]",
                )

        console.print(table)

        # Show selected total
        selected_cats = [c for c in result.categories if c.enabled and not c.scan_error]
        total_sel_size = sum(c.total_size for c in selected_cats)
        total_sel_items = sum(c.item_count for c in selected_cats)
        console.print(
            f"\n  [bold]Selected:[/] {len(selected_cats)} categories, "
            f"{total_sel_items:,} items, [green]{_format_size(total_sel_size)}[/]\n"
        )

        choice = console.input("[bold yellow]>> Enter choice: [/]").strip().lower()

        if choice == "quit" or choice == "q":
            return False
        elif choice == "next" or choice == "n":
            if not any(c.enabled for c in result.categories):
                console.print("[red]No categories selected. Select at least one or quit.[/]")
                continue
            return True
        elif choice == "all" or choice == "a":
            for c in result.categories:
                if not c.scan_error:
                    c.enabled = True
        elif choice == "none":
            for c in result.categories:
                c.enabled = False
        else:
            # Try to parse as number(s)
            _toggle_by_input(choice, result.categories)


def phase2_item_drilldown(result: ScanResult) -> bool:
    """
    Phase 2: Let the user review and deselect individual items within
    selected categories. Paginated for large lists.

    Returns True to proceed, False to go back to Phase 1.
    """
    selected_cats = [c for c in result.categories if c.enabled and not c.scan_error]

    for cat_idx, cat in enumerate(selected_cats):
        if not _review_category_items(cat, cat_idx + 1, len(selected_cats)):
            return False

    return True


def _review_category_items(
    cat: CleanupCategory,
    cat_num: int,
    total_cats: int,
) -> bool:
    """Review items in a single category with pagination."""
    items = cat.items
    if not items:
        return True

    # Initially all items are selected
    page = 0
    total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    while True:
        console.print()
        console.print(f"[bold cyan]=== PHASE 2: Review Items -- "
                      f"{cat.name} ({cat_num}/{total_cats}) ===[/]")
        console.print(f"[dim]Page {page + 1}/{total_pages} | "
                      f"Toggle items by number, 'sa' select all, 'da' deselect all, "
                      f"'pg N' go to page, 'next' accept & move on, 'back' go to Phase 1[/]\n")

        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, len(items))
        page_items = items[start:end]

        table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
        table.add_column("#", justify="right", width=6)
        table.add_column("Sel", justify="center", width=5)
        table.add_column("Path", max_width=70, overflow="ellipsis")
        table.add_column("Size", justify="right", width=12)
        table.add_column("Type", width=5)

        for i, item in enumerate(page_items, start + 1):
            sel = "[x]" if item.selected else "[ ]"
            sel_style = "green" if item.selected else "dim"
            type_label = "DIR" if item.item_type == ItemType.DIRECTORY else (
                "REG" if item.item_type == ItemType.REGISTRY_KEY else "FILE"
            )

            # Shorten long paths
            display_path = item.path
            if len(display_path) > 68:
                display_path = "..." + display_path[-65:]

            table.add_row(
                str(i),
                f"[{sel_style}]{sel}[/]",
                display_path,
                item.size_human,
                type_label,
            )

        console.print(table)

        sel_count = sum(1 for it in items if it.selected)
        sel_size = sum(it.size for it in items if it.selected)
        console.print(
            f"\n  [bold]Selected:[/] {sel_count:,}/{len(items):,} items, "
            f"[green]{_format_size(sel_size)}[/]"
        )

        choice = console.input("[bold yellow]>> Enter choice: [/]").strip().lower()

        if choice in ("next", "n"):
            return True
        elif choice in ("back", "b"):
            return False
        elif choice in ("sa",):
            for it in items:
                it.selected = True
        elif choice in ("da",):
            for it in items:
                it.selected = False
        elif choice.startswith("pg "):
            try:
                pg = int(choice.split()[1]) - 1
                if 0 <= pg < total_pages:
                    page = pg
                else:
                    console.print(f"[red]Page must be 1-{total_pages}[/]")
            except (ValueError, IndexError):
                console.print("[red]Invalid page number[/]")
        elif choice == ">" or choice == "pn":
            if page < total_pages - 1:
                page += 1
        elif choice == "<" or choice == "pp":
            if page > 0:
                page -= 1
        else:
            _toggle_items_by_input(choice, items)


def phase3_final_confirmation(result: ScanResult) -> bool:
    """
    Phase 3: Show final summary and ask for confirmation.

    Returns True if user confirms deletion, False to go back.
    """
    console.print()
    console.print("[bold cyan]=== PHASE 3: Final Confirmation ===[/]\n")

    table = Table(
        box=box.ROUNDED,
        title="Items Selected for Deletion",
        title_style="bold red",
        show_lines=True,
    )
    table.add_column("Category", min_width=25)
    table.add_column("Items", justify="right", width=8)
    table.add_column("Size", justify="right", width=12)
    table.add_column("Risk", justify="center", width=12)

    total_items = 0
    total_size = 0

    for cat in result.categories:
        if not cat.enabled or cat.scan_error:
            continue

        sel_count = cat.selected_count
        sel_size = cat.selected_size
        if sel_count == 0:
            continue

        total_items += sel_count
        total_size += sel_size

        risk_color = RISK_COLORS.get(cat.risk, "white")
        risk_label = RISK_LABELS.get(cat.risk, str(cat.risk.value))

        table.add_row(
            cat.name,
            f"{sel_count:,}",
            cat.selected_size_human,
            f"[{risk_color}]{risk_label}[/]",
        )

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/]",
        f"[bold]{total_items:,}[/]",
        f"[bold green]{_format_size(total_size)}[/]",
        "",
    )

    console.print(table)
    console.print()

    if total_items == 0:
        console.print("[yellow]No items selected for deletion.[/]")
        return False

    console.print(Panel(
        f"[bold red]WARNING: This will permanently delete {total_items:,} items "
        f"({_format_size(total_size)}).\n"
        f"Deleted files are NOT sent to the Recycle Bin and CANNOT be recovered.[/]",
        border_style="red",
    ))

    answer = console.input(
        "[bold red]>> Type 'DELETE' to confirm, 'back' to review, 'quit' to exit: [/]"
    ).strip()

    if answer == "DELETE":
        return True
    elif answer.lower() in ("back", "b"):
        return False
    else:
        console.print("[yellow]Aborted.[/]")
        return False


def show_cleanup_report(
    deleted: int,
    failed: int,
    freed: int,
    log_path: str,
    duration_s: float = 0.0,
) -> None:
    """Display the final cleanup report."""
    duration_line = ""
    if duration_s > 0:
        duration_line = f"\n  Duration: [bold cyan]{_format_duration(duration_s)}[/]"

    console.print()
    console.print(Panel.fit(
        f"[bold green]Cleanup Complete![/]\n\n"
        f"  Deleted:  [bold green]{deleted:,}[/] items\n"
        f"  Failed:   [bold {'red' if failed else 'dim'}]{failed:,}[/] items\n"
        f"  Freed:    [bold green]{_format_size(freed)}[/]"
        f"{duration_line}\n\n"
        f"  Log file: [cyan]{log_path}[/]",
        border_style="green",
        title="[bold]SysClean Report[/]",
    ))
    console.print()


# -- Helpers --

def _toggle_by_input(choice: str, categories: List[CleanupCategory]) -> None:
    """Parse user input and toggle categories by number."""
    nums = _parse_numbers(choice)
    for n in nums:
        idx = n - 1
        if 0 <= idx < len(categories) and not categories[idx].scan_error:
            categories[idx].enabled = not categories[idx].enabled
        else:
            console.print(f"[red]Invalid category number: {n}[/]")


def _toggle_items_by_input(choice: str, items: List[CleanupItem]) -> None:
    """Parse user input and toggle items by number."""
    nums = _parse_numbers(choice)
    for n in nums:
        idx = n - 1
        if 0 <= idx < len(items):
            items[idx].selected = not items[idx].selected
        else:
            console.print(f"[red]Invalid item number: {n}[/]")


def _parse_numbers(text: str) -> List[int]:
    """
    Parse a string of numbers and ranges like '1 3 5-8 12'.
    Returns sorted list of integers.
    """
    numbers = []
    for part in text.replace(",", " ").split():
        part = part.strip()
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                a, b = int(a), int(b)
                numbers.extend(range(min(a, b), max(a, b) + 1))
            except ValueError:
                pass
        else:
            try:
                numbers.append(int(part))
            except ValueError:
                pass
    return sorted(set(numbers))
