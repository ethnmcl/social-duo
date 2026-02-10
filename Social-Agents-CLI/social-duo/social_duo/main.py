from __future__ import annotations

import os

import typer
from dotenv import load_dotenv

from social_duo.cli.init_cmd import init_app
from social_duo.cli.post_cmd import post_app
from social_duo.cli.reply_cmd import reply_app
from social_duo.cli.chat_cmd import chat_app
from social_duo.cli.history_cmd import history_app
from social_duo.cli.config_cmd import config_app
from social_duo.cli.discuss_cmd import discuss_app
from social_duo.cli.molt_cmd import molt_app

app = typer.Typer(add_completion=False, help="Two-agent CLI for social media content.")

app.add_typer(init_app, name="init")
app.add_typer(post_app, name="post")
app.add_typer(reply_app, name="reply")
app.add_typer(chat_app, name="chat")
app.add_typer(history_app, name="history")
app.add_typer(config_app, name="config")
app.add_typer(discuss_app, name="discuss")
app.add_typer(molt_app, name="molt")


def _load_env() -> None:
    load_dotenv(override=False)
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1")
    os.environ.setdefault("OPENAI_MODEL", "gpt-4.1-mini")


@app.callback()
def main() -> None:
    _load_env()


if __name__ == "__main__":
    app()
