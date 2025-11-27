"""Utilities to sanitize weekly notes before passing them to Gemini."""

from __future__ import annotations

import re
import logging
from dataclasses import replace
from typing import Dict, List

from ..layer1.cleaning import clean_text
from .email_models import WeeklyPulseNote

LOGGER = logging.getLogger(__name__)

# Replace highly charged phrases that frequently trigger Gemini's safety filters.
SENSITIVE_PATTERNS = [
    re.compile(r"\bemergency\b", re.IGNORECASE),
    re.compile(r"\bpanic\b", re.IGNORECASE),
    re.compile(r"\bdesperate\b", re.IGNORECASE),
    re.compile(r"\bkill\b", re.IGNORECASE),
    re.compile(r"\bsuicide\b", re.IGNORECASE),
    re.compile(r"\bscam\b", re.IGNORECASE),
    re.compile(r"\bfraud\b", re.IGNORECASE),
    re.compile(r"\bscammer\b", re.IGNORECASE),
    re.compile(r"\bcheat\b", re.IGNORECASE),
    re.compile(r"\bloot(ed)?\b", re.IGNORECASE),
    re.compile(r"\brobbed\b", re.IGNORECASE),
    re.compile(r"\bthreat(en|ening)?\b", re.IGNORECASE),
]
SENSITIVE_TOKEN = "[customer urgency noted]"

MONETARY_PATTERN = re.compile(r"(?:₹|rs\.?|inr|\$)\s*\d[\d,]*(?:\.\d+)?", re.IGNORECASE)
PERCENT_PATTERN = re.compile(r"\b\d{1,3}%\b")
ACCOUNT_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")

# Quotes that still include highly charged wording will be dropped entirely.
BLOCKED_QUOTE_PATTERNS = [
    re.compile(r"\b(?:fraud|scam|cheated|robbed|looted)\b", re.IGNORECASE),
    re.compile(r"\b(?:police|legal case|court|lawsuit)\b", re.IGNORECASE),
    re.compile(r"\b(?:lost|loss)\s+\d", re.IGNORECASE),
    re.compile(r"\b(?:deducted|debited)\s+\d", re.IGNORECASE),
]
MAX_QUOTES = 3


def sanitize_note(note: WeeklyPulseNote) -> WeeklyPulseNote:
    """Return a sanitized copy of the weekly note for safer LLM prompting."""

    sanitized_overview = _sanitize_text(note.overview)
    sanitized_title = _sanitize_text(note.title)
    sanitized_themes = [_sanitize_theme(theme) for theme in note.themes]
    sanitized_quotes = _sanitize_quotes(note.quotes)
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
    sanitized = _aggressive_scrub(cleaned)
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(SENSITIVE_TOKEN, sanitized)
    return sanitized.strip()


def _sanitize_quotes(quotes: List[str]) -> List[str]:
    sanitized_quotes: List[str] = []
    for quote in quotes:
        sanitized = _sanitize_text(quote)
        if not sanitized:
            continue
        if any(pattern.search(sanitized) for pattern in BLOCKED_QUOTE_PATTERNS):
            LOGGER.debug("Dropping quote for safety reasons: %s", sanitized[:80])
            continue
        sanitized_quotes.append(sanitized)
        if len(sanitized_quotes) >= MAX_QUOTES:
            break
    return sanitized_quotes


def _aggressive_scrub(text: str) -> str:
    scrubbed = MONETARY_PATTERN.sub("[amount redacted]", text)
    scrubbed = PERCENT_PATTERN.sub("[value redacted]", scrubbed)
    scrubbed = ACCOUNT_PATTERN.sub("[account redacted]", scrubbed)
    return scrubbed


