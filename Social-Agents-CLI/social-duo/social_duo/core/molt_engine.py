from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from social_duo.agents.prompts_molt import MOLT_SYSTEM
from social_duo.providers.llm import LLMClient
from social_duo.types.molt_schemas import MoltAction


@dataclass
class FeedState:
    posts: dict[str, dict] = field(default_factory=dict)
    comments: dict[str, dict] = field(default_factory=dict)
    replies: dict[str, dict] = field(default_factory=dict)
    votes: dict[str, int] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=lambda: {"post": 0, "comment": 0, "reply": 0})
    topics: set[str] = field(default_factory=set)
    max_posts: int = 1
    max_comments: int = 1
    last_reply_id: str | None = None
    last_comment_id: str | None = None
    last_reply_agent: str | None = None
    last_comment_agent: str | None = None
    last_reply_text_by_agent: dict[str, str] = field(default_factory=dict)
    post_keyword: str | None = None
    reply_agent_by_id: dict[str, str] = field(default_factory=dict)
    max_replies: int = 2
    upvotes_used: dict[str, int] = field(default_factory=dict)

    def next_id(self, kind: str) -> str:
        self.counters[kind] += 1
        prefix = {"post": "P", "comment": "C", "reply": "R"}[kind]
        return f"{prefix}{self.counters[kind]}"

    def latest_post_id(self) -> str | None:
        if not self.posts:
            return None
        return list(self.posts.keys())[-1]

    def latest_comment_id(self) -> str | None:
        if not self.comments:
            return None
        return list(self.comments.keys())[-1]


def _normalize_topic(title: str | None, content: str | None) -> str:
    text = (title or content or "").lower()
    tokens = [t.strip(".,!?:;\"'()[]") for t in text.split() if t.strip()]
    return " ".join(tokens[:6])


def _extract_keyword(text: str | None) -> str:
    if not text:
        return "that"
    tokens = [t.strip(".,!?:;\"'()[]").lower() for t in text.split()]
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "is",
        "are",
        "be",
        "as",
        "it",
        "post",
        "point",
        "your",
        "about",
        "future",
        "curious",
        "enigmatic",
        "rise",
        "evolution",
        "case",
    }
    candidates = [t for t in tokens if t and t not in stop]
    if not candidates:
        return "that"
    # Prefer the longest token to avoid generic adjectives
    return sorted(candidates, key=len, reverse=True)[0]


def _too_similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return False
    overlap = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    return overlap > 0.45


def _recent_reply_texts(state: FeedState, limit: int = 2) -> list[str]:
    if not state.replies:
        return []
    return [r.get("content", "") for r in list(state.replies.values())[-limit:]]


def _diversify_reply(content: str, *, agent: str, state: FeedState) -> str:
    starters = [
        "One angle is",
        "Another consideration is",
        "A different perspective:",
        "Building on that,",
        "Stepping back,",
        "From a practical view,",
        "A key trade-off is",
        "One question is",
    ]
    last = state.last_reply_text_by_agent.get(agent, "")
    if not last:
        return content
    last_start = " ".join(last.lower().split()[:3])
    curr_start = " ".join(content.lower().split()[:3])
    if curr_start == last_start:
        return f"{starters[len(state.replies) % len(starters)]} {content}"
    return content


def _short_followup(post_key: str) -> str:
    prompts = [
        f"What’s one risk around {post_key} you’d watch closely?",
        f"What’s a practical next step on {post_key} for cities?",
        f"Where do you see the biggest trade-off in {post_key}?",
        f"What would success for {post_key} look like?",
    ]
    return prompts[len(post_key) % len(prompts)]


def reduce_event(state: FeedState, event: dict[str, Any]) -> None:
    action = event["action"]
    payload = event.get("payload", {})
    target_id = event.get("target_id")

    if action == "CREATE_POST":
        post_id = payload["post_id"]
        state.posts[post_id] = payload
        state.votes[post_id] = 0
        topic_key = _normalize_topic(payload.get("title"), payload.get("content"))
        if topic_key:
            state.topics.add(topic_key)
        title = payload.get("title")
        state.post_keyword = _extract_keyword(title or payload.get("content"))
    elif action == "COMMENT":
        comment_id = payload["comment_id"]
        state.comments[comment_id] = payload
        state.votes[comment_id] = 0
        state.last_comment_id = comment_id
        state.last_comment_agent = event.get("agent")
    elif action == "REPLY":
        reply_id = payload["reply_id"]
        state.replies[reply_id] = payload
        state.votes[reply_id] = 0
        state.last_reply_id = reply_id
        state.last_reply_agent = event.get("agent")
        if event.get("agent"):
            state.reply_agent_by_id[reply_id] = event.get("agent")
        if event.get("agent") and payload.get("content"):
            state.last_reply_text_by_agent[event.get("agent")] = payload.get("content")
    elif action == "UPVOTE":
        if target_id:
            state.votes[target_id] = state.votes.get(target_id, 0) + int(payload.get("delta", 1))
    elif action == "MODERATE":
        pass
    elif action == "REWRITE":
        pass


def _build_context(state: FeedState, platform: str, risk: str, topic: str | None) -> str:
    recent_posts = list(state.posts.values())[-5:]
    recent_comments = list(state.comments.values())[-5:]
    remaining_comments = max(0, state.max_comments - len(state.comments))
    last_comment = recent_comments[-1] if recent_comments else None
    last_post = recent_posts[-1] if recent_posts else None
    last_reply = state.replies.get(state.last_reply_id or "", {})
    return "\n".join(
        [
            f"Platform: {platform}",
            f"Risk level: {risk}",
            f"Topic constraint: {topic or 'any'}",
            f"Recent posts: {json.dumps(recent_posts)}",
            f"Recent comments: {json.dumps(recent_comments)}",
            f"Last comment to reply to: {json.dumps(last_comment)}",
            f"Last reply to address (if any): {json.dumps(last_reply)}",
            f"Current post to discuss: {json.dumps(last_post)}",
            f"Post keyword: {state.post_keyword}",
            f"Used topics: {sorted(state.topics)}",
            "Rule: Create ONE post, then exactly ONE comment. After that, only replies between AgentA and AgentB.",
            f"Allowed actions: CREATE_POST, COMMENT, REPLY, UPVOTE. Max posts: {state.max_posts}. Comments remaining: {remaining_comments}. Max replies: {state.max_replies}.",
            "Replies must directly address the last comment or reply.",
            "Comments and replies must directly reference the current post topic (use its key terms).",
            "Choose ONE action. Avoid repeating identical topics.",
        ]
    )


def _call_agent(
    llm: LLMClient,
    *,
    agent: str,
    context: str,
    temperature: float,
) -> MoltAction:
    messages = [
        {"role": "system", "content": MOLT_SYSTEM + f"\nYou are {agent}."},
        {"role": "user", "content": context},
    ]

    resp = llm.chat(messages, temperature=temperature, max_tokens=500, response_format={"type": "json_object"})
    content = resp["choices"][0]["message"]["content"]

    try:
        data = json.loads(content)
        return MoltAction.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        correction = messages + [{"role": "user", "content": "Return ONLY valid JSON matching schema."}]
        resp = llm.chat(correction, temperature=temperature, max_tokens=500, response_format={"type": "json_object"})
        content = resp["choices"][0]["message"]["content"]
        data = json.loads(content)
        return MoltAction.model_validate(data)


def simulate_molt(
    *,
    llm: LLMClient,
    turns: int,
    platform: str,
    risk: str,
    topic: str | None,
    cadence: str,
    stop_on: str,
    event_cb,
) -> dict[str, Any]:
    state = FeedState()
    events: list[dict[str, Any]] = []

    delay = {"fast": 0.0, "normal": 0.2, "slow": 0.6}.get(cadence, 0.0)

    for idx in range(turns):
        agent = "AgentA" if idx % 2 == 0 else "AgentB"
        context = _build_context(state, platform, risk, topic)
        try:
            action = _call_agent(llm, agent=agent, context=context, temperature=0.6)
        except Exception as exc:  # noqa: BLE001
            event = {
                "agent": "ERROR",
                "action": "ERROR",
                "target_id": None,
                "payload": {"error": str(exc)},
            }
            event_cb(event)
            events.append(event)
            continue

        event = _action_to_event(action, state, agent)
        if event:
            event_cb(event)
            events.append(event)
            reduce_event(state, event)
            if event["action"] == "WRAPUP":
                break

        if action.action == "MODERATE" and action.moderation:
            rewrite_event = {
                "agent": "SYSTEM",
                "action": "REWRITE",
                "target_id": action.moderation.target_id,
                "payload": {"rewrite": action.moderation.rewrite},
            }
            event_cb(rewrite_event)
            events.append(rewrite_event)

        if action.action == "WRAPUP":
            continue

        if delay:
            time.sleep(delay)

    return {"events": events, "state": state}


def _action_to_event(action: MoltAction, state: FeedState, agent: str) -> dict[str, Any] | None:
    comments_remaining = max(0, state.max_comments - len(state.comments))

    def _upvote_event(target_id: str | None, *, delta: int = 1, allow_reply_fallback: bool = False) -> dict[str, Any] | None:
        if not target_id:
            return None
        if state.upvotes_used.get(agent, 0) >= 1:
            if allow_reply_fallback and state.last_comment_id:
                target = state.last_reply_id or state.last_comment_id
                reply_id = state.next_id("reply")
                content = action.content or "I agree with your point."
                last_reply = state.replies.get(state.last_reply_id or "", {}).get("content", "")
                if _too_similar(content, last_reply):
                    content = f"Another angle: {content}"
                return {
                    "agent": agent,
                    "action": "REPLY",
                    "target_id": target,
                    "payload": {
                        "reply_id": reply_id,
                        "parent_id": target,
                        "content": content,
                    },
                }
            return None
        state.upvotes_used[agent] = state.upvotes_used.get(agent, 0) + 1
        return {
            "agent": agent,
            "action": "UPVOTE",
            "target_id": target_id,
            "payload": {"delta": delta},
        }

    if action.action == "UPVOTE" and state.last_comment_id:
        target = state.last_reply_id or state.last_comment_id
        reply_id = state.next_id("reply")
        content = action.content or "I agree with your point."
        last_reply = state.replies.get(state.last_reply_id or "", {}).get("content", "")
        if _too_similar(content, last_reply):
            content = f"Another angle: {content}"
        return {
            "agent": agent,
            "action": "REPLY",
            "target_id": target,
            "payload": {
                "reply_id": reply_id,
                "parent_id": target,
                "content": content,
            },
        }

    if action.action == "CREATE_POST":
        if len(state.posts) >= state.max_posts:
            target_post = state.latest_post_id()
            if not target_post:
                return None
            # Redirect extra posts into comments when the single post already exists
            if comments_remaining > 0 and action.content:
                comment_id = state.next_id("comment")
                return {
                    "agent": agent,
                    "action": "COMMENT",
                    "target_id": target_post,
                    "payload": {
                        "comment_id": comment_id,
                        "post_id": target_post,
                        "content": action.content,
                    },
                }
            if state.last_comment_id:
                target = state.last_reply_id or state.last_comment_id
                reply_id = state.next_id("reply")
                content = action.content or "I agree with your point."
                last_reply = state.replies.get(state.last_reply_id or "", {}).get("content", "")
                if _too_similar(content, last_reply):
                    content = f"Another angle: {content}"
                return {
                    "agent": agent,
                    "action": "REPLY",
                    "target_id": target,
                    "payload": {
                        "reply_id": reply_id,
                        "parent_id": target,
                        "content": content,
                    },
                }
            return _upvote_event(target_post)
        topic_key = _normalize_topic(action.title, action.content)
        if topic_key and topic_key in state.topics:
            # Avoid duplicate topics; fallback to upvote
            target = state.latest_post_id()
            if not target:
                return None
            if state.last_comment_id:
                target = state.last_reply_id or state.last_comment_id
                reply_id = state.next_id("reply")
                content = action.content or "I agree with your point."
                last_reply = state.replies.get(state.last_reply_id or "", {}).get("content", "")
                if _too_similar(content, last_reply):
                    content = f"Another angle: {content}"
                return {
                    "agent": agent,
                    "action": "REPLY",
                    "target_id": target,
                    "payload": {
                        "reply_id": reply_id,
                        "parent_id": target,
                        "content": content,
                    },
                }
            return _upvote_event(target)
        post_id = state.next_id("post")
        return {
            "agent": agent,
            "action": "CREATE_POST",
            "target_id": post_id,
            "payload": {
                "post_id": post_id,
                "title": action.title,
                "content": action.content,
            },
        }

    if action.action == "COMMENT":
        if comments_remaining <= 0:
            return None
        target_post = action.target_id or state.latest_post_id()
        if not target_post or not action.content:
            return None
        post_content = state.posts.get(target_post, {}).get("content", "")
        post_title = state.posts.get(target_post, {}).get("title", "")
        key = _extract_keyword(post_title or post_content)
        if key and key not in action.content.lower():
            action.content = f"On the post about {key}, {action.content}"
        comment_id = state.next_id("comment")
        return {
            "agent": agent,
            "action": "COMMENT",
            "target_id": target_post,
            "payload": {
                "comment_id": comment_id,
                "post_id": target_post,
                "content": action.content,
            },
        }
    if action.action == "REPLY":
        target_comment = state.last_reply_id or state.last_comment_id
        if not target_comment or not action.content:
            return None
        if len(state.replies) >= state.max_replies:
            return None
        if state.last_reply_id is None and state.last_comment_agent == agent:
            # First reply must come from the other agent (not the commenter)
            return None
        if state.last_reply_agent == agent:
            return None
        if target_comment in state.reply_agent_by_id and state.reply_agent_by_id[target_comment] == agent:
            return None
        last_comment = state.comments.get(target_comment, {}).get("content", "")
        if target_comment in state.replies:
            last_comment = state.replies.get(target_comment, {}).get("content", "")
        post_id = state.latest_post_id()
        post_title = state.posts.get(post_id or "", {}).get("title", "")
        post_key = state.post_keyword or _extract_keyword(post_title)
        last_key = _extract_keyword(last_comment)
        if post_key and post_key not in action.content.lower():
            action.content = f"On {post_key}, {action.content}"
        if last_key and last_key not in action.content.lower():
            action.content = f"On your point about {last_key}, {action.content}"
        if post_key and post_key not in action.content.lower():
            action.content = f"On {post_key}, how do you see this evolving?"
        recent_replies = _recent_reply_texts(state, limit=2)
        if any(_too_similar(action.content, r) for r in recent_replies):
            focus = post_key or last_key or "this"
            action.content = _short_followup(focus)
        # Per-agent starter diversification
        action.content = _diversify_reply(action.content, agent=agent, state=state)
        reply_id = state.next_id("reply")
        return {
            "agent": agent,
            "action": "REPLY",
            "target_id": target_comment,
            "payload": {
                "reply_id": reply_id,
                "parent_id": target_comment,
                "content": action.content,
            },
        }
    if action.action == "UPVOTE" and action.vote:
        if state.last_comment_id:
            # After the comment exists, always reply instead of upvoting
            target = state.last_reply_id or state.last_comment_id
            reply_id = state.next_id("reply")
            content = action.content or "I agree with your point."
            last_reply = state.replies.get(state.last_reply_id or "", {}).get("content", "")
            if _too_similar(content, last_reply):
                content = f"Another angle: {content}"
            return {
                "agent": agent,
                "action": "REPLY",
                "target_id": target,
                "payload": {
                    "reply_id": reply_id,
                    "parent_id": target,
                    "content": content,
                },
            }
        return _upvote_event(action.vote.target_id, delta=action.vote.delta)
    if action.action == "UPVOTE" and not action.vote:
        target = state.latest_post_id()
        if state.last_comment_id:
            # After the comment exists, always reply instead of upvoting
            target = state.last_reply_id or state.last_comment_id
            reply_id = state.next_id("reply")
            content = action.content or "I agree with your point."
            last_reply = state.replies.get(state.last_reply_id or "", {}).get("content", "")
            if _too_similar(content, last_reply):
                content = f"Another angle: {content}"
            return {
                "agent": agent,
                "action": "REPLY",
                "target_id": target,
                "payload": {
                    "reply_id": reply_id,
                    "parent_id": target,
                    "content": content,
                },
            }
        return _upvote_event(target)
    if action.action == "MODERATE" and action.moderation:
        return {
            "agent": agent,
            "action": "MODERATE",
            "target_id": action.moderation.target_id,
            "payload": action.moderation.model_dump(),
        }
    if action.action == "WRAPUP":
        return None
    return None
