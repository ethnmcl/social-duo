from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from social_duo.agents.editor import EditorAgent
from social_duo.agents.writer import WriterAgent
from social_duo.core.config import load_config
from social_duo.core.constraints import PLATFORMS, platform_constraint
from social_duo.core.loop import LoopError, run_loop
from social_duo.core.render import render_reply_output
from social_duo.providers.openai_compat import OpenAICompatibleClient
from social_duo.storage.history import add_output, add_step, create_run, create_session, update_session
from social_duo.types.schemas import RunInput

reply_app = typer.Typer(add_completion=False, help="Generate replies with two-agent iteration.", invoke_without_command=True)
console = Console()


@reply_app.callback()
def reply_cmd(
    text: str = typer.Option(None, help="Reply to this text"),
    file: str = typer.Option(None, help="Path to text file"),
    platform: str = typer.Option("x", help="Platform: x|linkedin|instagram|threads"),
    style: str = typer.Option("polite", help="Style: polite|witty|direct|supportive"),
    stance: str = typer.Option("neutral", help="Stance: agree|disagree|neutral"),
    risk: str = typer.Option("low", help="Risk level: low|medium|high"),
    rounds: int = typer.Option(2, help="Number of iterations"),
    json_mode: bool = typer.Option(False, "--json", help="JSON output"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose agent trace"),
) -> None:
    if platform not in PLATFORMS or platform == "all":
        raise typer.BadParameter("Invalid platform")

    if file:
        text = Path(file).read_text().strip()
    if not text:
        text = typer.prompt("Paste the post/comment to reply to")

    workspace = Path.cwd() / ".social-duo"
    config_path = workspace / "config.json"
    if not config_path.exists():
        console.print("Missing .social-duo/config.json. Run `social_duo init` first.")
        raise typer.Exit(code=1)

    config = load_config(config_path)
    llm = OpenAICompatibleClient()
    writer = WriterAgent(llm)
    editor = EditorAgent(llm)

    session_id = create_session(Path(workspace / "history.db"), cwd=str(Path.cwd()), label="reply")

    constraint = platform_constraint(config, platform)
    context = {
        "goal": "reply",
        "platform": platform,
        "style": style,
        "stance": stance,
        "risk": risk,
        "source_text": text,
        "cta_required": False,
        "cta_text": None,
        "tone": config.brand_voice.tone,
        "length": "short",
        "keywords": [],
        "donts": config.brand_voice.dont,
        "facts": [],
        "brand_voice": config.brand_voice.model_dump(),
        "constraints": constraint.model_dump(),
    }

    run_input = RunInput(
        type="reply",
        platform=platform,
        style=style,
        stance=stance,
        risk=risk,
        source_text=text,
    ).model_dump()

    run_id = create_run(Path(workspace / "history.db"), session_id=session_id, run_type="reply", platform=platform, input_json=run_input)

    try:
        result = run_loop(writer=writer, editor=editor, config=config, context=context, rounds=rounds)
    except LoopError as exc:
        for idx, step in enumerate(exc.trace):
            add_step(
                Path(workspace / "history.db"),
                run_id=run_id,
                step_index=idx,
                agent_name=step["agent"],
                role=step["role"],
                content=step["content"],
            )
        raise

    final = result.final.model_dump()
    if len(final["variants"]) < 3:
        final["variants"] = (final["variants"] + [final["recommended"]] * 3)[:3]

    for idx, step in enumerate(result.trace):
        add_step(
            Path(workspace / "history.db"),
            run_id=run_id,
            step_index=idx,
            agent_name=step["agent"],
            role=step["role"],
            content=step["content"],
        )

    output = {"final": final, "editor": result.editor.model_dump()}
    add_output(Path(workspace / "history.db"), run_id=run_id, final_json=output)
    update_session(Path(workspace / "history.db"), session_id)

    payload = {"final": final}
    if verbose:
        payload["trace"] = result.trace

    render_reply_output(payload, json_mode=json_mode, verbose=verbose)
