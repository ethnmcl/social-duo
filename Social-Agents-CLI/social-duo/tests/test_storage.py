from pathlib import Path

from social_duo.storage.history import (
    add_output,
    add_step,
    create_run,
    create_session,
    get_run,
    list_runs,
)


def test_storage_roundtrip(tmp_path: Path):
    db_path = tmp_path / "history.db"
    session_id = create_session(db_path, cwd=str(tmp_path), label="test")
    run_id = create_run(db_path, session_id=session_id, run_type="post", platform="x", input_json={"a": 1})
    add_step(db_path, run_id=run_id, step_index=0, agent_name="Writer", role="draft", content={"t": 1})
    add_output(db_path, run_id=run_id, final_json={"final": "ok"})

    runs = list_runs(db_path)
    assert runs

    data = get_run(db_path, run_id)
    assert data is not None
    assert data["run"]["id"] == run_id
    assert data["steps"][0]["agent_name"] == "Writer"
