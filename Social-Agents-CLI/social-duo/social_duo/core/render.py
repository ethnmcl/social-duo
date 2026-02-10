from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def render_post_output(output: dict[str, Any], *, json_mode: bool, verbose: bool) -> None:
    if json_mode:
        console.print_json(json.dumps(output))
        return

    console.print(Panel.fit("Final Recommended Post", style="bold green"))
    console.print(output["final"]["recommended"])
    console.print()

    table = Table(title="Variants")
    table.add_column("#")
    table.add_column("Variant")
    for idx, variant in enumerate(output["final"]["variants"], start=1):
        table.add_row(str(idx), variant)
    console.print(table)

    rationale = output["final"].get("rationale", [])
    if rationale:
        console.print(Panel.fit("Rationale", style="bold blue"))
        for r in rationale:
            console.print(f"- {r}")

    if verbose and output.get("trace"):
        console.print(Panel.fit("Trace", style="bold yellow"))
        for step in output["trace"]:
            console.print(f"[{step['agent']} {step['role']}] {step['content']}")


def render_reply_output(output: dict[str, Any], *, json_mode: bool, verbose: bool) -> None:
    if json_mode:
        console.print_json(json.dumps(output))
        return

    console.print(Panel.fit("Recommended Reply", style="bold green"))
    console.print(output["final"]["recommended"])
    console.print()

    table = Table(title="Reply Options")
    table.add_column("#")
    table.add_column("Reply")
    for idx, variant in enumerate(output["final"]["variants"], start=1):
        table.add_row(str(idx), variant)
    console.print(table)

    rationale = output["final"].get("rationale", [])
    if rationale:
        console.print(Panel.fit("Rationale", style="bold blue"))
        for r in rationale:
            console.print(f"- {r}")

    if verbose and output.get("trace"):
        console.print(Panel.fit("Trace", style="bold yellow"))
        for step in output["trace"]:
            console.print(f"[{step['agent']} {step['role']}] {step['content']}")


def render_discuss_output(output: dict[str, Any], *, json_mode: bool, verbose: bool) -> None:
    if json_mode:
        console.print_json(json.dumps(output))
        return

    if verbose:
        console.print(Panel.fit("Transcript", style="bold yellow"))
        for item in output.get("transcript", []):
            turn = item.get("turn", {})
            intent = turn.get("intent", "unknown")
            msg = turn.get("message", "")
            console.print(f"[{item.get('agent', 'agent')} {intent}] {msg}")

    console.print(Panel.fit("Artifacts", style="bold green"))
    artifacts = output.get("artifacts", [])
    if not artifacts:
        console.print("No artifacts generated.")
        return

    posts = [a for a in artifacts if a.get("kind") in {"post", "thread"}]
    replies = [a for a in artifacts if a.get("kind") == "reply"]

    if posts:
        console.print(Panel.fit("Posts/Threads", style="bold cyan"))
        for artifact in posts:
            console.print(Panel.fit(f"{artifact['platform']} - {artifact['kind']}", style="bold blue"))
            console.print(artifact["content"])

    if replies:
        console.print(Panel.fit("Replies/Comments", style="bold cyan"))
        for artifact in replies:
            console.print(Panel.fit(f"{artifact['platform']} - {artifact['kind']}", style="bold blue"))
            console.print(artifact["content"])


def render_molt_event(event: dict[str, Any], *, verbose: bool) -> None:
    action = event.get("action")
    agent = event.get("agent")
    payload = event.get("payload", {})
    target_id = event.get("target_id")

    if verbose and action not in {"ERROR"}:
        console.print(f"[MyVillage meta] {agent} -> {action}")

    if action == "CREATE_POST":
        title = payload.get("title") or ""
        content = payload.get("content") or ""
        label = f"[MyVillage POST {payload.get('post_id')}] (Agent: {agent})"
        console.print(Panel.fit(label, style="bold green"))
        if title:
            console.print(title)
        console.print(content)
    elif action == "COMMENT":
        label = f"[MyVillage COMMENT {payload.get('comment_id')}] on {payload.get('post_id')} (Agent: {agent})"
        console.print(Panel.fit(label, style="bold blue"))
        console.print(payload.get("content", ""))
    elif action == "REPLY":
        label = f"[MyVillage REPLY {payload.get('reply_id')}] on {payload.get('parent_id')} (Agent: {agent})"
        console.print(Panel.fit(label, style="bold cyan"))
        console.print(payload.get("content", ""))
    elif action == "UPVOTE":
        console.print(f"[MyVillage UPVOTE] {agent} upvoted {target_id} (+{payload.get('delta', 1)})")
    elif action == "MODERATE":
        console.print(Panel.fit(f"[MyVillage MODERATE] {agent} flagged {target_id}", style="bold red"))
        console.print(payload.get("reason", ""))
        console.print(f"Rewrite: {payload.get('rewrite', '')}")
    elif action == "REWRITE":
        console.print(Panel.fit(f"[MyVillage REWRITE] {target_id}", style="bold yellow"))
        console.print(payload.get("rewrite", ""))
    elif action == "WRAPUP":
        console.print(Panel.fit("[MyVillage WRAPUP]", style="bold magenta"))
    elif action == "ERROR":
        console.print(Panel.fit("[MyVillage ERROR]", style="bold red"))
        console.print(payload.get("error", ""))
