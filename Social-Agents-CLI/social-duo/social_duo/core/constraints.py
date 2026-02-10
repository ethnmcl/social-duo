from __future__ import annotations

from typing import Iterable

from social_duo.types.schemas import AppConfig, PlatformConstraint
from social_duo.core.scoring import compute_metrics


DEFAULT_PLATFORM_CONSTRAINTS = {
    "x": {
        "name": "x",
        "char_limit": 280,
        "typical_min": 80,
        "typical_max": 260,
        "hashtag_max": 2,
        "hook_chars": 80,
        "allow_emojis": True,
        "threadable": True,
    },
    "linkedin": {
        "name": "linkedin",
        "char_limit": 3000,
        "typical_min": 800,
        "typical_max": 1500,
        "hashtag_max": 3,
        "hook_chars": 120,
        "allow_emojis": True,
        "threadable": False,
    },
    "instagram": {
        "name": "instagram",
        "char_limit": 2200,
        "typical_min": 150,
        "typical_max": 400,
        "hashtag_max": 8,
        "hook_chars": 100,
        "allow_emojis": True,
        "threadable": False,
    },
    "threads": {
        "name": "threads",
        "char_limit": 500,
        "typical_min": 100,
        "typical_max": 400,
        "hashtag_max": 3,
        "hook_chars": 80,
        "allow_emojis": True,
        "threadable": True,
    },
}


PLATFORMS = ["x", "linkedin", "instagram", "threads", "all"]


def platform_constraint(config: AppConfig, platform: str) -> PlatformConstraint:
    if platform not in PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")
    return getattr(config.platform_constraints, platform)


def validate_text(
    text: str,
    *,
    config: AppConfig,
    platform: str,
    cta_required: bool,
    cta_text: str | None,
) -> tuple[list[str], dict]:
    constraint = platform_constraint(config, platform)
    metrics = compute_metrics(
        text,
        banned_phrases=config.brand_voice.banned_phrases,
        cta_required=cta_required,
        cta_text=cta_text,
    )
    issues: list[str] = []

    if metrics["char_count"] > constraint.char_limit:
        issues.append(f"Exceeds character limit ({metrics['char_count']}/{constraint.char_limit}).")
    if metrics["hashtag_count"] > constraint.hashtag_max:
        issues.append(f"Too many hashtags ({metrics['hashtag_count']}/{constraint.hashtag_max}).")
    if metrics["banned_hits"]:
        issues.append(f"Contains banned phrases: {', '.join(metrics['banned_hits'])}.")
    if cta_required and not metrics["cta_present"]:
        issues.append("CTA required but missing.")
    if metrics["avg_sentence_length"] > 26:
        issues.append("Sentences are too long on average.")

    return issues, metrics


def list_platforms(platform: str) -> Iterable[str]:
    if platform == "all":
        return ["x", "linkedin", "instagram", "threads"]
    return [platform]
