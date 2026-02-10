import json
from pathlib import Path

from social_duo.core.config import default_config
from social_duo.core.discuss_loop import DiscussLoopError, run_discuss_loop
from social_duo.storage.history import add_output, add_step, create_run, create_session, get_run


class DummyLLM:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def chat(self, messages, *, temperature, max_tokens, response_format=None):
        content = self.responses[self.calls]
        self.calls += 1
        return {"choices": [{"message": {"content": content}}]}


def _turn(intent, message, candidates=None, chosen=None, artifacts=None, stop=False):
    return json.dumps(
        {
            "type": "DISCUSS",
            "intent": intent,
            "message": message,
            "candidates": candidates or [],
            "chosen": chosen,
            "artifacts": artifacts or [],
            "stop": stop,
        }
    )


def test_discuss_converges_and_stops():
    responses = [
        _turn(
            "PROPOSE_TOPIC",
            "Three topic ideas.",
            candidates=[{"topic": "Remote work rituals", "angle": "practical tips", "platform": "linkedin"}],
        ),
        _turn(
            "DECIDE",
            "Pick remote work rituals.",
            chosen={"topic": "Remote work rituals", "angle": "practical tips", "platform": "linkedin"},
        ),
        _turn(
            "DRAFT",
            "Drafting post.",
            artifacts=[{"kind": "post", "platform": "linkedin", "content": "Short post about remote work rituals."}],
        ),
        _turn(
            "WRAPUP",
            "Wrap up.",
            stop=True,
        ),
    ]
    llm = DummyLLM(responses)
    config = default_config()

    result = run_discuss_loop(
        llm=llm,
        config=config,
        platform="linkedin",
        turns=10,
        mode="posts",
        risk="medium",
        stop_on="artifact",
    )

    assert result.artifacts
    assert result.stop_reason == "artifact"


def test_discuss_json_retry():
    bad = "not json"
    good = _turn("PROPOSE_TOPIC", "Ok", candidates=[{"topic": "Habits", "angle": "micro", "platform": "x"}])
    next_turn = _turn("WRAPUP", "Done", stop=True)
    llm = DummyLLM([bad, good, next_turn])
    config = default_config()

    result = run_discuss_loop(
        llm=llm,
        config=config,
        platform="x",
        turns=2,
        mode="mixed",
        risk="low",
        stop_on="manual",
    )

    assert len(result.transcript) == 2


def test_discuss_persists_steps_and_output(tmp_path: Path):
    responses = [
        _turn(
            "PROPOSE_TOPIC",
            "Idea",
            candidates=[{"topic": "Focus blocks", "angle": "workflow", "platform": "x"}],
        ),
        _turn(
            "WRAPUP",
            "Stop",
            artifacts=[{"kind": "post", "platform": "x", "content": "Focus blocks help."}],
            stop=True,
        ),
    ]
    llm = DummyLLM(responses)
    config = default_config()

    result = run_discuss_loop(
        llm=llm,
        config=config,
        platform="x",
        turns=2,
        mode="posts",
        risk="low",
        stop_on="manual",
    )

    db_path = tmp_path / "history.db"
    session_id = create_session(db_path, cwd=str(tmp_path), label="discuss")
    run_id = create_run(db_path, session_id=session_id, run_type="discuss", platform="x", input_json={})
    for idx, step in enumerate(result.transcript):
        add_step(db_path, run_id=run_id, step_index=idx, agent_name=step["agent"], role=step["turn"]["intent"], content=step)
    add_output(db_path, run_id=run_id, final_json={"transcript": result.transcript, "artifacts": [a.model_dump() for a in result.artifacts]})

    stored = get_run(db_path, run_id)
    assert stored is not None
    assert stored["steps"]
    assert stored["output"]
