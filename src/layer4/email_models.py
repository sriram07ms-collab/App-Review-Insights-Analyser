"""Dataclasses for Layer 4 email drafting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass(slots=True)
class WeeklyPulseNote:
    """Subset of Layer 3 note fields needed for email drafting."""

    week_start: str
    week_end: str
    title: str
    overview: str
    themes: List[Dict[str, str]]
    quotes: List[str]
    actions: List[str]


@dataclass(slots=True)
class EmailDraft:
    """Represents the drafted email body and metadata."""

    subject: str
    body: str
    recipient: str
    week_start: str
    week_end: str
    product_name: str


@dataclass(slots=True)
class EmailLogEntry:
    """Single log entry for a sent (or attempted) email."""

    timestamp: datetime
    week_start: str
    week_end: str
    recipient: str
    subject: str
    status: str
    transport: str

