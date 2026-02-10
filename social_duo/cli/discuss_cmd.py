from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from social_duo.core.config import load_config
from social_duo.core.discuss_loop import DiscussLoopError, run_discuss_loop
from social_duo.core.render import render_discuss_output
from social_duo.providers.openai_compat import OpenAICompatibleClient
from social_duo.storage.history import add_output, add_step, create_run, create_session, update_session


discuss_app = typer.Typer(add_completion=False, help="Autonomous two-agent discussion.", invoke_without_command=True)
console = Console()


def _normalize_artifacts(artifacts: list[dict], platform: str) -> list[dict]:
    seen = set()
    unique: list[dict] = []
    for art in artifacts:
        key = (art.get("kind"), art.get("platform"), art.get("content"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(art)

    posts = [a for a in unique if a.get("kind") in {"post", "thread"}]
    replies = [a for a in unique if a.get("kind") == "reply"]

    if platform == "all":
        selected_posts: list[dict] = []
        for plat in ["x", "linkedin", "instagram", "threads"]:
            cand = [p for p in posts if p.get("platform") == plat]
            if cand:
                selected_posts.append(cand[-1])
    else:
        selected_posts = [p for p in posts if p.get("platform") == platform][-3:]

    return selected_posts + replies


@discuss_app.callback()
def discuss_cmd(
    platform: str = typer.Option("all", help="Platform: x|linkedin|instagram|threads|all"),
    turns: int = typer.Option(12, help="Number of turns"),
    mode: str = typer.Option("mixed", help="Mode: posts|replies|mixed"),
    risk: str = typer.Option("medium", help="Risk: low|medium|high"),
    stop_on: str = typer.Option("artifact", help="Stop: artifact|turns|manual"),
    verbose: bool = typer.Option(False, "--verbose", help="Print transcript"),
    json_mode: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    workspace = Path.cwd() / ".social-duo"
    config_path = workspace / "config.json"
    if not config_path.exists():
        console.print("Missing .social-duo/config.json. Run `social_duo init` first.")
        raise typer.Exit(code=1)

    if stop_on not in {"artifact", "turns", "manual"}:
        raise typer.BadParameter("Invalid stop-on value")

    config = load_config(config_path)
    llm = OpenAICompatibleClient()

    session_id = create_session(Path(workspace / "history.db"), cwd=str(Path.cwd()), label="discuss")
    run_id = create_run(Path(workspace / "history.db"), session_id=session_id, run_type="discuss", platform=platform, input_json={
        "platform": platform,
        "turns": turns,
        "mode": mode,
        "risk": risk,
        "stop_on": stop_on,
    })

    try:
        result = run_discuss_loop(
            llm=llm,
            config=config,
            platform=platform,
            turns=turns,
            mode=mode,
            risk=risk,
            stop_on=stop_on,
        )
    except DiscussLoopError as exc:
        for idx, step in enumerate(exc.transcript):
            add_step(
                Path(workspace / "history.db"),
                run_id=run_id,
                step_index=idx,
                agent_name=step.get("agent", "unknown"),
                role=step.get("turn", {}).get("intent", "error"),
                content=step,
            )
        raise

    for idx, step in enumerate(result.transcript):
        add_step(
            Path(workspace / "history.db"),
            run_id=run_id,
            step_index=idx,
            agent_name=step.get("agent", "unknown"),
            role=step.get("turn", {}).get("intent", "unknown"),
            content=step,
        )

    output = {
        "transcript": result.transcript,
        "artifacts": _normalize_artifacts([a.model_dump() for a in result.artifacts], platform),
        "stop_reason": result.stop_reason,
    }
    add_output(Path(workspace / "history.db"), run_id=run_id, final_json=output)
    update_session(Path(workspace / "history.db"), session_id)

    if not json_mode:
        console.print(Panel.fit("Discuss Complete", style="bold green"))
    render_discuss_output(output, json_mode=json_mode, verbose=verbose)
