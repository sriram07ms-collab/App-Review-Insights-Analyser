"""Utilities to sanitize weekly notes before passing them to Gemini."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Dict

from ..layer1.cleaning import clean_text
from .email_models import WeeklyPulseNote

# Replace highly charged phrases that frequently trigger Gemini's safety filters.
SENSITIVE_PATTERNS = [
    re.compile(r"\bemergency\b", re.IGNORECASE),
    re.compile(r"\bpanic\b", re.IGNORECASE),
    re.compile(r"\bdesperate\b", re.IGNORECASE),
    re.compile(r"\bkill\b", re.IGNORECASE),
    re.compile(r"\bsuicide\b", re.IGNORECASE),
]
SENSITIVE_TOKEN = "[customer urgency noted]"


def sanitize_note(note: WeeklyPulseNote) -> WeeklyPulseNote:
    """Return a sanitized copy of the weekly note for safer LLM prompting."""

    sanitized_overview = _sanitize_text(note.overview)
    sanitized_title = _sanitize_text(note.title)
    sanitized_themes = [_sanitize_theme(theme) for theme in note.themes]
    sanitized_quotes = [_sanitize_text(q) for q in note.quotes]
    sanitized_actions = [_sanitize_text(action) for action in note.actions]

    return replace(
        note,
        title=sanitized_title,
        overview=sanitized_overview,
        themes=sanitized_themes,
        quotes=sanitized_quotes,
        actions=sanitized_actions,
    )


def _sanitize_theme(theme: Dict[str, str]) -> Dict[str, str]:
    sanitized = dict(theme)
    sanitized["name"] = _sanitize_text(theme.get("name", ""))
    sanitized["summary"] = _sanitize_text(theme.get("summary", ""))
    return sanitized


def _sanitize_text(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    sanitized = cleaned
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(SENSITIVE_TOKEN, sanitized)
    return sanitized.strip()


