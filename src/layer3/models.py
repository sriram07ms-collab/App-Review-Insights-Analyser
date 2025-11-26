"""
Dataclasses for Layer 3 summarization pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List


@dataclass(slots=True)
class ClassifiedReview:
    """Review enriched with assigned theme metadata."""

    review_id: str
    title: str
    text: str
    rating: int
    date: datetime
    theme_id: str
    theme_name: str

    def to_prompt_text(self) -> str:
        """Format review for LLM prompts."""
        title_part = f"Title: {self.title}\n" if self.title else ""
        rating_part = f"Rating: {self.rating}\n"
        return f"{title_part}{rating_part}Review: {self.text.strip()}"


@dataclass(slots=True)
class ThemeChunk:
    """Batch of reviews for a specific theme."""

    theme_id: str
    theme_name: str
    reviews: List[ClassifiedReview]


@dataclass(slots=True)
class ChunkSummary:
    """LLM output for a single chunk."""

    theme_id: str
    theme_name: str
    key_points: List[str] = field(default_factory=list)
    candidate_quotes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ThemeInsight:
    """Aggregated insights for a theme after merging chunk summaries."""

    theme_id: str
    theme_name: str
    key_points: List[str] = field(default_factory=list)
    quotes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict:
        return {
            "theme_id": self.theme_id,
            "theme_name": self.theme_name,
            "key_points": self.key_points,
            "quotes": self.quotes,
        }


@dataclass(slots=True)
class WeeklyPulseNote:
    """Final structured note per week."""

    week_start: str
    week_end: str
    title: str
    overview: str
    themes: List[Dict[str, str]]
    quotes: List[str]
    actions: List[str]
    word_count: int

    def as_dict(self) -> Dict:
        return asdict(self)

