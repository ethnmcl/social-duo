from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from social_duo.storage.history import export_run, get_run, list_runs

history_app = typer.Typer(add_completion=False, help="View and export history.", invoke_without_command=True)
console = Console()


@history_app.callback()
def history_cmd(
    list_recent: bool = typer.Option(False, "--list", help="List recent runs"),
    show: int = typer.Option(None, "--show", help="Show run details"),
    export: int = typer.Option(None, "--export", help="Export run"),
    fmt: str = typer.Option("md", "--format", help="Export format: md|json"),
) -> None:
    workspace = Path.cwd() / ".social-duo"
    db_path = workspace / "history.db"
    if not db_path.exists():
        console.print("Missing history. Run `social_duo init` first.")
        raise typer.Exit(code=1)

    if list_recent:
        rows = list_runs(db_path, limit=10)
        table = Table(title="Recent Runs")
        table.add_column("ID")
        table.add_column("Type")
        table.add_column("Platform")
        table.add_column("Created")
        table.add_column("Label")
        for row in rows:
            table.add_row(str(row["id"]), row["type"], str(row["platform"]), row["created_at"], str(row["label"]))
        console.print(table)
        return

    if show:
        data = get_run(db_path, show)
        if not data:
            console.print("Run not found")
            raise typer.Exit(code=1)
        console.print_json(json.dumps(data, indent=2))
        return

    if export:
        if fmt not in {"md", "json"}:
            raise typer.BadParameter("format must be md or json")
        exports = workspace / "exports"
        exports.mkdir(exist_ok=True)
        export_path = exports / f"run_{export}.{fmt}"
        export_run(db_path, export, export_path, fmt)
        console.print(f"Exported to {export_path}")
        return

    console.print("Use --list, --show, or --export.")
