from __future__ import annotations

import re


def count_hashtags(text: str) -> int:
    return len(re.findall(r"#\w+", text))


def avg_sentence_length(text: str) -> float:
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0
    word_counts = [len(s.split()) for s in sentences]
    return sum(word_counts) / len(word_counts)


def contains_banned_phrase(text: str, banned: list[str]) -> list[str]:
    lower = text.lower()
    hits = []
    for phrase in banned:
        if phrase.lower() in lower:
            hits.append(phrase)
    return hits


def cta_present(text: str, cta_text: str | None) -> bool:
    if cta_text:
        return cta_text.lower() in text.lower()
    common = ["learn more", "sign up", "join", "get started", "read more", "dm us"]
    lower = text.lower()
    return any(c in lower for c in common)


def compute_metrics(
    text: str,
    *,
    banned_phrases: list[str],
    cta_required: bool,
    cta_text: str | None,
) -> dict:
    char_count = len(text)
    hashtag_count = count_hashtags(text)
    banned_hits = contains_banned_phrase(text, banned_phrases)
    avg_len = avg_sentence_length(text)

    metrics = {
        "char_count": char_count,
        "hashtag_count": hashtag_count,
        "banned_hits": banned_hits,
        "avg_sentence_length": avg_len,
        "cta_present": cta_present(text, cta_text) if cta_required else True,
    }
    return metrics
