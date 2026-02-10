from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from social_duo.agents.editor import EditorAgent
from social_duo.agents.writer import WriterAgent
from social_duo.core.config import load_config
from social_duo.core.loop import LoopError, run_loop
from social_duo.core.render import render_post_output
from social_duo.providers.openai_compat import OpenAICompatibleClient
from social_duo.storage.history import add_output, add_step, create_run, create_session, get_run, latest_run_id, update_session

chat_app = typer.Typer(add_completion=False, help="Chat-style revisions for recent outputs.", invoke_without_command=True)
console = Console()


@chat_app.callback()
def chat_cmd(
    session: int = typer.Option(None, help="Run id to continue"),
) -> None:
    workspace = Path.cwd() / ".social-duo"
    config_path = workspace / "config.json"
    if not config_path.exists():
        console.print("Missing .social-duo/config.json. Run `social_duo init` first.")
        raise typer.Exit(code=1)

    db_path = workspace / "history.db"
    run_id = session or latest_run_id(db_path)
    if not run_id:
        console.print("No previous runs found.")
        raise typer.Exit(code=1)

    data = get_run(db_path, run_id)
    if not data or not data.get("output"):
        console.print("Run not found or missing output.")
        raise typer.Exit(code=1)

    final_json = data["output"]["final_json"]
    previous = None
    try:
        import json as _json
        previous = _json.loads(final_json)["final"]["recommended"]
    except Exception:  # noqa: BLE001
        previous = ""

    config = load_config(config_path)
    llm = OpenAICompatibleClient()
    writer = WriterAgent(llm)
    editor = EditorAgent(llm)

    session_id = create_session(db_path, cwd=str(Path.cwd()), label="chat")

    console.print(Panel.fit("Chat session started. Type 'exit' to quit.", style="bold green"))
    if previous:
        console.print("Latest output loaded.")

    while True:
        instruction = typer.prompt("chat>")
        if instruction.strip().lower() in {"exit", "quit"}:
            break

        context = {
            "goal": "revise",
            "topic": None,
            "platform": data["run"]["platform"],
            "audience": None,
            "cta_required": False,
            "cta_text": None,
            "tone": config.brand_voice.tone,
            "length": "short",
            "keywords": [],
            "donts": config.brand_voice.dont,
            "facts": [],
            "brand_voice": config.brand_voice.model_dump(),
            "constraints": config.platform_constraints.model_dump().get(data["run"]["platform"], {}),
            "source_text": previous,
            "instruction": instruction,
        }

        run_id = create_run(db_path, session_id=session_id, run_type="chat", platform=data["run"]["platform"], input_json=context)
        try:
            result = run_loop(writer=writer, editor=editor, config=config, context=context, rounds=2)
            final = result.final.model_dump()
        except LoopError as exc:
            for idx, step in enumerate(exc.trace):
                add_step(db_path, run_id=run_id, step_index=idx, agent_name=step["agent"], role=step["role"], content=step["content"])
            raise
        if len(final["variants"]) < 3:
            final["variants"] = (final["variants"] + [final["recommended"]] * 3)[:3]

        for idx, step in enumerate(result.trace):
            add_step(db_path, run_id=run_id, step_index=idx, agent_name=step["agent"], role=step["role"], content=step["content"])

        output = {"final": final, "editor": result.editor.model_dump()}
        add_output(db_path, run_id=run_id, final_json=output)
        update_session(db_path, session_id)

        render_post_output({"final": final}, json_mode=False, verbose=False)
        previous = final["recommended"]

    console.print(Panel.fit("Chat session ended.", style="bold green"))
