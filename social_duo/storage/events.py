from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from social_duo.storage.db import connect


ISO = "%Y-%m-%dT%H:%M:%SZ"


def _now() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def add_event(
    db_path: Path,
    *,
    run_id: int,
    agent: str,
    action: str,
    target_id: str | None,
    payload: dict[str, Any],
) -> int:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO events(run_id, created_at, agent, action, target_id, payload_json) VALUES(?,?,?,?,?,?)",
        (run_id, _now(), agent, action, target_id, json.dumps(payload)),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_events(db_path: Path, run_id: int) -> list[dict[str, Any]]:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE run_id=? ORDER BY id ASC", (run_id,))
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def export_events(db_path: Path, run_id: int) -> dict[str, Any]:
    return {"run_id": run_id, "events": list_events(db_path, run_id)}
