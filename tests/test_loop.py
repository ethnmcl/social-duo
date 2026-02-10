import json

from social_duo.agents.editor import EditorAgent
from social_duo.agents.writer import WriterAgent
from social_duo.core.config import default_config
from social_duo.core.loop import run_loop


class DummyLLM:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def chat(self, messages, *, temperature, max_tokens, response_format=None):
        content = self.responses[self.calls]
        self.calls += 1
        return {"choices": [{"message": {"content": content}}]}


def test_loop_passes():
    writer_json = json.dumps(
        {
            "recommended": "Hello world",
            "variants": ["Hello world 1", "Hello world 2", "Hello world 3"],
            "hashtags": [],
            "rationale": ["Concise"],
        }
    )
    editor_json = json.dumps(
        {
            "verdict": "PASS",
            "issues": [],
            "edited_version": "Hello world",
            "alt_suggestions": ["Alt 1", "Alt 2"],
            "scores": {"constraint_fit": 90, "clarity": 90, "hook": 80, "risk": 10},
        }
    )

    llm = DummyLLM([writer_json, editor_json])
    writer = WriterAgent(llm)
    editor = EditorAgent(llm)
    config = default_config()

    context = {
        "goal": "announce",
        "topic": "test",
        "platform": "x",
        "audience": "devs",
        "cta_required": False,
        "cta_text": None,
        "tone": "confident",
        "length": "short",
        "keywords": [],
        "donts": [],
        "facts": [],
        "brand_voice": config.brand_voice.model_dump(),
        "constraints": config.platform_constraints.x.model_dump(),
    }

    result = run_loop(writer=writer, editor=editor, config=config, context=context, rounds=2)
    assert result.final.recommended == "Hello world"
    assert result.editor.verdict == "PASS"
    assert len(result.trace) == 2
