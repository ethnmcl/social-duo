from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from social_duo.core.config import default_config, save_config
from social_duo.storage.db import connect

init_app = typer.Typer(add_completion=False, help="Initialize the local .social-duo workspace.", invoke_without_command=True)
console = Console()


@init_app.callback()
def init_cmd() -> None:
    root = Path.cwd() / ".social-duo"
    root.mkdir(exist_ok=True)

    config_path = root / "config.json"
    if not config_path.exists():
        save_config(config_path, default_config())

    db_path = root / "history.db"
    if not db_path.exists():
        connect(db_path).close()

    (root / "exports").mkdir(exist_ok=True)
    (root / "sessions").mkdir(exist_ok=True)

    console.print(Panel.fit("Initialized .social-duo workspace", style="bold green"))
    console.print("Next steps:")
    console.print("- Run `social_duo post` to generate a post")
    console.print("- Run `social_duo reply` to generate replies")
    console.print("- Use `social_duo config show` to view defaults")
