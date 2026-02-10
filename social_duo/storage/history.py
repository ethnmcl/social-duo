from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from social_duo.storage.db import connect


ISO = "%Y-%m-%dT%H:%M:%SZ"


def _now() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def create_session(db_path: Path, *, cwd: str, label: str | None) -> int:
    conn = connect(db_path)
    cur = conn.cursor()
    now = _now()
    cur.execute(
        "INSERT INTO sessions(created_at, updated_at, cwd, label) VALUES(?,?,?,?)",
        (now, now, cwd, label),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_session(db_path: Path, session_id: int) -> None:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE sessions SET updated_at=? WHERE id=?", (_now(), session_id))
    conn.commit()


def create_run(db_path: Path, *, session_id: int, run_type: str, platform: str | None, input_json: dict[str, Any]) -> int:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs(session_id, type, platform, created_at, input_json) VALUES(?,?,?,?,?)",
        (session_id, run_type, platform, _now(), json.dumps(input_json)),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_step(
    db_path: Path,
    *,
    run_id: int,
    step_index: int,
    agent_name: str,
    role: str,
    content: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO steps(run_id, step_index, agent_name, role, content, created_at, metadata_json) VALUES(?,?,?,?,?,?,?)",
        (run_id, step_index, agent_name, role, json.dumps(content), _now(), json.dumps(metadata or {})),
    )
    conn.commit()


def add_output(db_path: Path, *, run_id: int, final_json: dict[str, Any]) -> None:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO outputs(run_id, final_json, created_at) VALUES(?,?,?)",
        (run_id, json.dumps(final_json), _now()),
    )
    conn.commit()


def list_runs(db_path: Path, limit: int = 10) -> list[dict[str, Any]]:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT r.id, r.type, r.platform, r.created_at, s.label FROM runs r JOIN sessions s ON r.session_id = s.id ORDER BY r.created_at DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_run(db_path: Path, run_id: int) -> dict[str, Any] | None:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM runs WHERE id=?", (run_id,))
    run = cur.fetchone()
    if not run:
        return None
    cur.execute("SELECT * FROM steps WHERE run_id=? ORDER BY step_index ASC", (run_id,))
    steps = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM outputs WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (run_id,))
    output = cur.fetchone()
    return {
        "run": dict(run),
        "steps": steps,
        "output": dict(output) if output else None,
    }


def latest_run_id(db_path: Path) -> int | None:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM runs ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    return int(row[0]) if row else None


def export_run(db_path: Path, run_id: int, export_path: Path, fmt: str) -> None:
    data = get_run(db_path, run_id)
    if not data:
        raise ValueError("Run not found")
    if fmt == "json":
        export_path.write_text(json.dumps(data, indent=2))
        return
    if fmt == "md":
        lines = [f"# Run {run_id}", "", f"Type: {data['run']['type']}", f"Platform: {data['run']['platform']}", ""]
        if data.get("output"):
            final = json.loads(data["output"]["final_json"])
            lines.append("## Final Output")
            if data["run"]["type"] == "discuss":
                lines.append("")
                lines.append("### Artifacts")
                for artifact in final.get("artifacts", []):
                    lines.append(f"- {artifact.get('platform')} {artifact.get('kind')}: {artifact.get('content')}")
                lines.append("")
                lines.append("### Transcript")
                for item in final.get("transcript", []):
                    turn = item.get("turn", {})
                    intent = turn.get("intent", "unknown")
                    msg = turn.get("message", "")
                    lines.append(f"- {item.get('agent')} ({intent}): {msg}")
            else:
                lines.append(json.dumps(final, indent=2))
            lines.append("")
        lines.append("## Steps")
        for step in data["steps"]:
            lines.append(f"- {step['agent_name']} ({step['role']}): {step['content']}")
        export_path.write_text("\n".join(lines))
        return
    raise ValueError("Unsupported format")
