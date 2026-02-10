from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DiscussIntent = Literal[
    "PROPOSE_TOPIC",
    "CRITIQUE",
    "SHORTLIST",
    "DECIDE",
    "DRAFT",
    "REVISE",
    "SIMULATE_COMMENT",
    "REPLY",
    "WRAPUP",
]


class DiscussCandidate(BaseModel):
    topic: str
    angle: str
    platform: Literal["x", "linkedin", "instagram", "threads"]


class DiscussChosen(BaseModel):
    topic: str
    angle: str
    platform: Literal["x", "linkedin", "instagram", "threads"]


class DiscussArtifact(BaseModel):
    kind: Literal["post", "thread", "reply"]
    platform: Literal["x", "linkedin", "instagram", "threads"]
    content: str


class DiscussTurn(BaseModel):
    type: Literal["DISCUSS"] = "DISCUSS"
    intent: DiscussIntent
    message: str
    candidates: list[DiscussCandidate] = Field(default_factory=list)
    chosen: DiscussChosen | None = None
    artifacts: list[DiscussArtifact] = Field(default_factory=list)
    stop: bool = False


class DiscussResult(BaseModel):
    transcript: list[dict]
    artifacts: list[DiscussArtifact]
    stop_reason: str
