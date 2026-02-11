"""
SysClean - Interactive selection UI using InquirerPy + Rich.

Uses arrow-key driven checkbox prompts for category and item selection,
with Rich panels and tables for summaries and reports.
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

from InquirerPy import inquirer
from InquirerPy.separator import Separator

from models import CleanupCategory, CleanupItem, ScanResult, RiskLevel, ItemType, _format_size, _format_duration

console = Console()

RISK_TAGS = {
    RiskLevel.SAFE: "SAFE",
    RiskLevel.LOW: "LOW",
    RiskLevel.MEDIUM: "MED",
    RiskLevel.REGISTRY: "REG",
}

RISK_COLORS = {
    RiskLevel.SAFE: "green",
    RiskLevel.LOW: "yellow",
    RiskLevel.MEDIUM: "red",
    RiskLevel.REGISTRY: "magenta",
}


def show_scan_summary(result: ScanResult) -> None:
    """Display a summary panel after scanning."""
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Scan Complete[/]\n"
        f"Found [bold]{result.total_items:,}[/] items across "
        f"[bold]{len(result.categories)}[/] categories\n"
        f"Total reclaimable space: [bold green]{result.total_size_human}[/]",
        border_style="cyan",
    ))
    console.print()


def select_categories(result: ScanResult) -> bool:
    """
    Arrow-key checkbox prompt for category selection.

    Returns True if user selected at least one category, False to abort.
    """
    choices = []
    for cat in result.categories:
        if cat.scan_error:
            continue
        tag = RISK_TAGS.get(cat.risk, "?")
        label = (
            f"{cat.name:<38s}  {cat.item_count:>5,} items  "
            f"{cat.total_size_human:>10s}  [{tag}]"
        )
        choices.append({
            "name": label,
            "value": cat.name,
            "enabled": cat.enabled,
        })

    if not choices:
        console.print("[yellow]No scannable categories found.[/]")
        return False

    console.print("[bold cyan]Select categories to clean[/]")
    console.print("[dim]  ↑/↓ navigate  ·  Space toggle  ·  "
                  "Ctrl+A select all  ·  Enter confirm  ·  Ctrl+C cancel[/]\n")

    try:
        selected = inquirer.checkbox(
            message="Categories:",
            choices=choices,
            cycle=True,
            instruction="",
        ).execute()
    except KeyboardInterrupt:
        return False

    if selected is None:
        return False

    selected_set = set(selected)

    for cat in result.categories:
        cat.enabled = cat.name in selected_set

    if not selected_set:
        console.print("[red]No categories selected.[/]")
        return False

    return True


def review_items(result: ScanResult) -> bool:
    """
    Offer to drill down into each selected category to toggle individual items.

    Returns True to proceed to confirmation, False to go back.
    """
    selected_cats = [c for c in result.categories if c.enabled and not c.scan_error and c.item_count > 0]

    if not selected_cats:
        return True

    console.print()
    try:
        want_review = inquirer.confirm(
            message="Review individual items per category?",
            default=False,
        ).execute()
    except KeyboardInterrupt:
        return False

    if not want_review:
        return True

    for cat in selected_cats:
        if not _review_category_items(cat):
            return False

    return True


def _review_category_items(cat: CleanupCategory) -> bool:
    """Arrow-key checkbox for items within one category."""
    items = cat.items
    if not items:
        return True

    # Sort by size descending for better UX
    sorted_items = sorted(items, key=lambda x: x.size, reverse=True)

    choices = []
    for item in sorted_items:
        type_label = "DIR" if item.item_type == ItemType.DIRECTORY else (
            "REG" if item.item_type == ItemType.REGISTRY_KEY else "FILE"
        )
        # Shorten path for display
        display_path = item.path
        if len(display_path) > 60:
            display_path = "..." + display_path[-57:]

        label = f"{display_path:<63s}  {item.size_human:>10s}  {type_label}"
        choices.append({
            "name": label,
            "value": item.path,
            "enabled": item.selected,
        })

    console.print(f"\n[bold cyan]{cat.name}[/] — "
                  f"{cat.item_count:,} items, {cat.total_size_human}")
    console.print("[dim]  ↑/↓ navigate  ·  Space toggle  ·  Enter confirm[/]\n")

    try:
        selected = inquirer.checkbox(
            message=f"Items in {cat.name}:",
            choices=choices,
            cycle=True,
            instruction="",
        ).execute()
    except KeyboardInterrupt:
        return False

    if selected is None:
        return False

    selected_paths = set(selected)
    for item in items:
        item.selected = item.path in selected_paths

    return True


def confirm_deletion(result: ScanResult) -> bool:
    """
    Show final summary table and ask for confirmation.

    Returns True if user confirms deletion, False to go back.
    """
    console.print()

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
        risk_tag = RISK_TAGS.get(cat.risk, str(cat.risk.value))

        table.add_row(
            cat.name,
            f"{sel_count:,}",
            cat.selected_size_human,
            f"[{risk_color}][{risk_tag}][/]",
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

    try:
        answer = inquirer.text(
            message="Type DELETE to confirm, or anything else to cancel:",
        ).execute()
    except KeyboardInterrupt:
        return False

    if answer and answer.strip() == "DELETE":
        return True

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
