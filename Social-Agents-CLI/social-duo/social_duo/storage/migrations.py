from __future__ import annotations

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        cwd TEXT NOT NULL,
        label TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        platform TEXT,
        created_at TEXT NOT NULL,
        input_json TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        step_index INTEGER NOT NULL,
        agent_name TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        metadata_json TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS outputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        final_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        agent TEXT NOT NULL,
        action TEXT NOT NULL,
        target_id TEXT,
        payload_json TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    );
    """,
]
