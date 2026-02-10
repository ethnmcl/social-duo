from __future__ import annotations

import sqlite3
from pathlib import Path

from social_duo.storage.migrations import MIGRATIONS


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _apply_migrations(conn)
    return conn


def _apply_migrations(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for sql in MIGRATIONS:
        cur.executescript(sql)
    conn.commit()
