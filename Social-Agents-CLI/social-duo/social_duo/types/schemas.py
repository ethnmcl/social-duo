from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EmojiPolicy(BaseModel):
    allowed: bool = True
    max_per_post: int = 6


class HashtagPolicy(BaseModel):
    allowed: bool = True
    min: int = 0
    max: int = 5


class BrandVoice(BaseModel):
    tone: str = "confident"
    do: list[str] = Field(default_factory=lambda: ["Be concise", "Be specific"])
    dont: list[str] = Field(default_factory=lambda: ["Avoid hype", "Avoid unverifiable claims"])
    vocabulary: list[str] = Field(default_factory=list)
    banned_phrases: list[str] = Field(default_factory=list)
    emoji_policy: EmojiPolicy = Field(default_factory=EmojiPolicy)
    hashtag_policy: HashtagPolicy = Field(default_factory=HashtagPolicy)
    claims_policy: dict[str, Any] = Field(default_factory=lambda: {"no_unverified_claims": True})


class PlatformConstraint(BaseModel):
    name: str
    char_limit: int
    typical_min: int
    typical_max: int
    hashtag_max: int
    hook_chars: int = 80
    allow_emojis: bool = True
    threadable: bool = False


class PlatformConstraints(BaseModel):
    x: PlatformConstraint
    linkedin: PlatformConstraint
    instagram: PlatformConstraint
    threads: PlatformConstraint


class Defaults(BaseModel):
    platform: str = "x"
    rounds: int = 2
    tone: str = "confident"
    length: str = "short"


class AppConfig(BaseModel):
    brand_voice: BrandVoice = Field(default_factory=BrandVoice)
    platform_constraints: PlatformConstraints
    defaults: Defaults = Field(default_factory=Defaults)


class WriterOutput(BaseModel):
    recommended: str
    variants: list[str]
    hashtags: list[str] | None = None
    rationale: list[str]


IssueType = Literal["constraint", "clarity", "tone", "risk", "facts"]


class EditorIssue(BaseModel):
    type: IssueType
    detail: str


class EditorScores(BaseModel):
    constraint_fit: int
    clarity: int
    hook: int
    risk: int


class EditorOutput(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    issues: list[EditorIssue]
    edited_version: str
    alt_suggestions: list[str]
    scores: EditorScores


class RunInput(BaseModel):
    type: Literal["post", "reply", "chat"]
    goal: str | None = None
    topic: str | None = None
    platform: str | None = None
    audience: str | None = None
    cta_required: bool | None = None
    cta_text: str | None = None
    tone: str | None = None
    length: str | None = None
    keywords: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    thread_count: int | None = None
    style: str | None = None
    stance: str | None = None
    risk: str | None = None
    source_text: str | None = None
    instruction: str | None = None
