from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


ActionType = Literal["CREATE_POST", "COMMENT", "REPLY", "UPVOTE", "MODERATE", "WRAPUP"]


class Vote(BaseModel):
    target_id: str
    delta: int = 1


class Moderation(BaseModel):
    target_id: str
    reason: str
    rewrite: str


class MoltAction(BaseModel):
    action: ActionType
    title: str | None = None
    content: str | None = None
    target_id: str | None = None
    vote: Vote | None = None
    moderation: Moderation | None = None


class MoltEvent(BaseModel):
    run_id: int
    agent: Literal["WRITER", "EDITOR", "SYSTEM", "ERROR"]
    action: str
    target_id: str | None = None
    payload: dict
