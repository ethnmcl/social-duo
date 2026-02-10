from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from social_duo.core.config import load_config, save_config, update_config_value

config_app = typer.Typer(add_completion=False, help="View or update config.")
console = Console()


def _config_path() -> Path:
    workspace = Path.cwd() / ".social-duo"
    path = workspace / "config.json"
    if not path.exists():
        console.print("Missing .social-duo/config.json. Run `social_duo init` first.")
        raise typer.Exit(code=1)
    return path


@config_app.command("show")
def show_cmd() -> None:
    config = load_config(_config_path())
    console.print_json(config.model_dump_json(indent=2))


@config_app.command("set")
def set_cmd(key: str, value: str) -> None:
    config_path = _config_path()
    config = load_config(config_path)
    updated = update_config_value(config, key, value)
    save_config(config_path, updated)
    console.print("Config updated")
