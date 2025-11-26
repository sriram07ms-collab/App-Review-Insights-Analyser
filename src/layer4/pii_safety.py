"""Regex-based PII detection and masking helpers."""

from __future__ import annotations

import re
from typing import Pattern

EMAIL_PATTERN: Pattern[str] = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
PHONE_PATTERN: Pattern[str] = re.compile(r"(\+?\d{1,3}[-\s]?)?\d{3}[-\s]?\d{3}[-\s]?\d{4}")
INDIA_PHONE_PATTERN: Pattern[str] = re.compile(r"\+?91[-\s]?\d{5}[-\s]?\d{5}")
ACCOUNT_PATTERN: Pattern[str] = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")

PATTERNS = [
    EMAIL_PATTERN,
    INDIA_PHONE_PATTERN,
    PHONE_PATTERN,
    ACCOUNT_PATTERN,
]

MASK_TOKEN = "***"


def contains_pii(text: str) -> bool:
    return any(pattern.search(text) for pattern in PATTERNS)


def mask_pii(text: str) -> str:
    masked = text
    for pattern in PATTERNS:
        masked = pattern.sub(MASK_TOKEN, masked)
    return masked



