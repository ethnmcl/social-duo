from __future__ import annotations

import json
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from social_duo.core.molt_engine import FeedState, reduce_event, simulate_molt
from social_duo.core.render import render_molt_event
from social_duo.providers.openai_compat import OpenAICompatibleClient
from social_duo.storage.events import add_event, export_events, list_events
from social_duo.storage.history import add_output, create_run, create_session


molt_app = typer.Typer(add_completion=False, help="MyVillage Network autonomous simulation.")
console = Console()


@molt_app.command("run")
def molt_run(
    turns: int = typer.Option(30, help="Number of turns"),
    platform: str = typer.Option("all", help="Platform: x|linkedin|instagram|threads|all"),
    cadence: str = typer.Option("normal", help="Cadence: fast|normal|slow"),
    risk: str = typer.Option("medium", help="Risk: low|medium|high"),
    topic: str = typer.Option("any", help="Topic constraint"),
    stop_on: str = typer.Option("turns", help="Stop: turns|manual"),
    verbose: bool = typer.Option(False, "--verbose", help="Print meta lines"),
    json_mode: bool = typer.Option(False, "--json", help="JSON summary"),
) -> None:
    workspace = Path.cwd() / ".social-duo"
    if not (workspace / "config.json").exists():
        console.print("Missing .social-duo/config.json. Run `social_duo init` first.")
        raise typer.Exit(code=1)

    llm = OpenAICompatibleClient()

    session_id = create_session(workspace / "history.db", cwd=str(Path.cwd()), label="molt")
    run_id = create_run(workspace / "history.db", session_id=session_id, run_type="molt", platform=platform, input_json={
        "turns": turns,
        "platform": platform,
        "cadence": cadence,
        "risk": risk,
        "topic": topic,
        "stop_on": stop_on,
    })

    def _event_sink(event: dict) -> None:
        add_event(
            workspace / "history.db",
            run_id=run_id,
            agent=event["agent"],
            action=event["action"],
            target_id=event.get("target_id"),
            payload=event.get("payload", {}),
        )
        render_molt_event(event, verbose=verbose)

    result = simulate_molt(
        llm=llm,
        turns=turns,
        platform=platform,
        risk=risk,
        topic=None if topic == "any" else topic,
        cadence=cadence,
        stop_on=stop_on,
        event_cb=_event_sink,
    )

    summary = {
        "run_id": run_id,
        "events": len(result["events"]),
        "turns": turns,
        "platform": platform,
    }
    add_output(workspace / "history.db", run_id=run_id, final_json=summary)

    if json_mode:
        console.print_json(json.dumps(summary))
    else:
        console.print(Panel.fit(f"MyVillage Network run complete: {run_id}", style="bold green"))


@molt_app.command("watch")
def molt_watch(
    run_id: int = typer.Option(..., "--run-id", help="Run id to replay"),
    cadence: str = typer.Option("normal", help="Cadence: fast|normal|slow"),
) -> None:
    workspace = Path.cwd() / ".social-duo"
    events = list_events(workspace / "history.db", run_id)
    delay = {"fast": 0.0, "normal": 0.2, "slow": 0.6}.get(cadence, 0.0)

    for row in events:
        payload = json.loads(row["payload_json"])
        event = {
            "agent": row["agent"],
            "action": row["action"],
            "target_id": row["target_id"],
            "payload": payload,
        }
        render_molt_event(event, verbose=False)
        if delay:
            time.sleep(delay)


@molt_app.command("export")
def molt_export(
    run_id: int = typer.Option(..., "--run-id", help="Run id"),
    fmt: str = typer.Option("md", "--format", help="Export format: md|json"),
) -> None:
    workspace = Path.cwd() / ".social-duo"
    exports = workspace / "exports"
    exports.mkdir(exist_ok=True)
    data = export_events(workspace / "history.db", run_id)
    out_path = exports / f"molt_{run_id}.{fmt}"

    if fmt == "json":
        out_path.write_text(json.dumps(data, indent=2))
    elif fmt == "md":
        lines = [f"# MOLT Run {run_id}", ""]
        for event in data["events"]:
            payload = json.loads(event["payload_json"])
            lines.append(f"- {event['agent']} {event['action']} {event['target_id'] or ''}: {payload}")
        out_path.write_text("\n".join(lines))
    else:
        raise typer.BadParameter("format must be md or json")

    console.print(f"Exported to {out_path}")
