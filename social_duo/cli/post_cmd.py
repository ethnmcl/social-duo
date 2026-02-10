from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from social_duo.agents.editor import EditorAgent
from social_duo.agents.writer import WriterAgent
from social_duo.core.config import load_config
from social_duo.core.constraints import PLATFORMS, list_platforms, platform_constraint
from social_duo.core.loop import LoopError, run_loop
from social_duo.core.render import render_post_output
from social_duo.providers.openai_compat import OpenAICompatibleClient
from social_duo.storage.history import add_output, add_step, create_run, create_session, update_session
from social_duo.types.schemas import RunInput

post_app = typer.Typer(add_completion=False, help="Generate social posts with two-agent iteration.", invoke_without_command=True)
console = Console()


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _load_facts(path: str | None) -> list[str]:
    if not path:
        return []
    return [line.strip("- ") for line in Path(path).read_text().splitlines() if line.strip()]


@post_app.callback()
def post_cmd(
    goal: str = typer.Option(None, help="Goal for the post"),
    topic: str = typer.Option(None, help="Topic for the post"),
    platform: str = typer.Option("x", help="Platform: x|linkedin|instagram|threads|all"),
    audience: str = typer.Option(None, help="Target audience"),
    cta_required: bool = typer.Option(False, help="Require a call to action"),
    cta_text: str = typer.Option(None, help="CTA text"),
    tone: str = typer.Option(None, help="Tone"),
    length: str = typer.Option(None, help="Length preference"),
    keywords: str = typer.Option("", help="Comma-separated keywords"),
    donts: str = typer.Option("", help="Comma-separated banned angles/phrases"),
    facts: str = typer.Option(None, help="Path to facts file"),
    rounds: int = typer.Option(2, help="Number of iterations"),
    thread: int = typer.Option(1, help="Thread count for X/Threads"),
    voice: str = typer.Option(None, help="Voice preset name (reserved)"),
    json_mode: bool = typer.Option(False, "--json", help="JSON output"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose agent trace"),
) -> None:
    if platform not in PLATFORMS:
        raise typer.BadParameter("Invalid platform")

    if not goal:
        goal = typer.prompt("Goal (e.g., educate, convert, announce)")
    if not topic:
        topic = typer.prompt("Topic")
    if not audience:
        audience = typer.prompt("Audience")
    if not tone:
        tone = typer.prompt("Tone")
    if not length:
        length = typer.prompt("Length (short/medium/long)")

    workspace = Path.cwd() / ".social-duo"
    config_path = workspace / "config.json"
    if not config_path.exists():
        console.print("Missing .social-duo/config.json. Run `social_duo init` first.")
        raise typer.Exit(code=1)

    config = load_config(config_path)
    llm = OpenAICompatibleClient()
    writer = WriterAgent(llm)
    editor = EditorAgent(llm)

    session_id = create_session(Path(workspace / "history.db"), cwd=str(Path.cwd()), label=f"post:{topic}")

    facts_list = _load_facts(facts)
    if not facts_list:
        facts_input = typer.prompt("Facts (optional, bullet list; leave blank to skip)", default="", show_default=False)
        if facts_input:
            facts_list = [line.strip("- ") for line in facts_input.splitlines() if line.strip()]

    for plat in list_platforms(platform):
        constraint = platform_constraint(config, plat)
        context = {
            "goal": goal,
            "topic": topic,
            "platform": plat,
            "audience": audience,
            "cta_required": cta_required,
            "cta_text": cta_text,
            "tone": tone,
            "length": length,
            "keywords": _split_csv(keywords),
            "donts": _split_csv(donts),
            "facts": facts_list,
            "thread_count": thread,
            "brand_voice": config.brand_voice.model_dump(),
            "constraints": constraint.model_dump(),
        }

        run_input = RunInput(
            type="post",
            goal=goal,
            topic=topic,
            platform=plat,
            audience=audience,
            cta_required=cta_required,
            cta_text=cta_text,
            tone=tone,
            length=length,
            keywords=_split_csv(keywords),
            donts=_split_csv(donts),
            facts=facts_list,
            thread_count=thread,
        ).model_dump()

        run_id = create_run(Path(workspace / "history.db"), session_id=session_id, run_type="post", platform=plat, input_json=run_input)

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

        if platform == "all":
            console.print(Panel.fit(f"Platform: {plat}", style="bold magenta"))
        render_post_output(payload, json_mode=json_mode, verbose=verbose)

    if voice:
        console.print(Panel.fit("Note: voice presets are not implemented yet", style="bold yellow"))
