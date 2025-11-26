"""Text-cleaning helpers for Play Store reviews."""

from __future__ import annotations

import re
from typing import Final

from bs4 import BeautifulSoup

EMOJI_PATTERN: Final = re.compile(
    "["  # common emoji ranges
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]",
    flags=re.UNICODE,
)
URL_PATTERN: Final = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
WHITESPACE_PATTERN: Final = re.compile(r"\s+", re.MULTILINE)


def strip_html(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(" ", strip=True)


def remove_emojis(text: str) -> str:
    return EMOJI_PATTERN.sub("", text)


def remove_urls(text: str) -> str:
    return URL_PATTERN.sub("", text)


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def clean_text(text: str) -> str:
    """Apply the default cleaning pipeline."""
    if not text:
        return ""
    cleaned = strip_html(text)
    cleaned = remove_urls(cleaned)
    cleaned = remove_emojis(cleaned)
    cleaned = normalize_whitespace(cleaned)
    return cleaned



