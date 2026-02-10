import json
from pathlib import Path

from social_duo.core.molt_engine import FeedState, reduce_event, simulate_molt
from social_duo.storage.events import add_event, list_events


class DummyLLM:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def chat(self, messages, *, temperature, max_tokens, response_format=None):
        content = self.responses[self.calls]
        self.calls += 1
        return {"choices": [{"message": {"content": content}}]}


def test_reducer_threads():
    state = FeedState()
    post_event = {
        "action": "CREATE_POST",
        "target_id": "P1",
        "payload": {"post_id": "P1", "title": "t", "content": "c"},
    }
    comment_event = {
        "action": "COMMENT",
        "target_id": "P1",
        "payload": {"comment_id": "C1", "post_id": "P1", "content": "hi"},
    }
    reply_event = {
        "action": "REPLY",
        "target_id": "C1",
        "payload": {"reply_id": "R1", "parent_id": "C1", "content": "yo"},
    }
    reduce_event(state, post_event)
    reduce_event(state, comment_event)
    reduce_event(state, reply_event)

    assert "P1" in state.posts
    assert "C1" in state.comments
    assert "R1" in state.replies


def test_retry_and_error_event():
    bad = "not json"
    good = json.dumps({
        "action": "CREATE_POST",
        "title": "Hi",
        "content": "Test",
        "target_id": None,
        "vote": None,
        "moderation": None,
    })

    llm = DummyLLM([bad, good])
    events = []

    def sink(e):
        events.append(e)

    simulate_molt(
        llm=llm,
        turns=1,
        platform="x",
        risk="low",
        topic=None,
        cadence="fast",
        stop_on="turns",
        event_cb=sink,
    )

    assert events
    assert events[0]["action"] == "CREATE_POST"


def test_events_persist_and_replay(tmp_path: Path):
    db_path = tmp_path / "history.db"
    add_event(db_path, run_id=1, agent="WRITER", action="CREATE_POST", target_id="P1", payload={"post_id": "P1", "title": "t", "content": "c"})
    add_event(db_path, run_id=1, agent="EDITOR", action="UPVOTE", target_id="P1", payload={"delta": 1})
    rows = list_events(db_path, 1)
    assert len(rows) == 2


def test_moderation_creates_rewrite():
    mod = json.dumps({
        "action": "MODERATE",
        "title": None,
        "content": None,
        "target_id": "P1",
        "vote": None,
        "moderation": {"target_id": "P1", "reason": "Too risky", "rewrite": "Safer version"},
    })
    llm = DummyLLM([mod])
    events = []

    def sink(e):
        events.append(e)

    simulate_molt(
        llm=llm,
        turns=1,
        platform="x",
        risk="medium",
        topic=None,
        cadence="fast",
        stop_on="turns",
        event_cb=sink,
    )

    actions = [e["action"] for e in events]
    assert "MODERATE" in actions
    assert "REWRITE" in actions
