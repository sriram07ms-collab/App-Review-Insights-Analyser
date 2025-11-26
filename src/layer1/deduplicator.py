"""Deduplication helpers for filtered, validated reviews."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Sequence, Tuple

from thefuzz import fuzz

from .validator import ReviewModel

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DeduplicationConfig:
    """Knobs for deduplicating reviews."""

    similarity_threshold: int = 92
    min_text_length: int = 40
    date_tolerance_days: int = 7


@dataclass(slots=True)
class DeduplicationSummary:
    kept: int
    dropped: int


def deduplicate_reviews(
    reviews: Sequence[ReviewModel],
    config: DeduplicationConfig | None = None,
) -> Tuple[List[ReviewModel], DeduplicationSummary]:
    """Remove duplicate reviews by ID and fuzzy text similarity."""

    config = config or DeduplicationConfig()
    seen_ids: set[str] = set()
    kept: List[ReviewModel] = []
    dropped = 0

    for review in reviews:
        if review.review_id in seen_ids:
            dropped += 1
            LOGGER.debug("Dropping duplicate review_id=%s", review.review_id)
            continue

        if _is_similar_to_existing(review, kept, config):
            dropped += 1
            LOGGER.debug("Dropping fuzzy duplicate review_id=%s", review.review_id)
            continue

        kept.append(review)
        seen_ids.add(review.review_id)

    summary = DeduplicationSummary(kept=len(kept), dropped=dropped)
    LOGGER.info("Deduplication summary: %s", summary)
    return kept, summary


def _is_similar_to_existing(
    candidate: ReviewModel,
    existing: Iterable[ReviewModel],
    config: DeduplicationConfig,
) -> bool:
    """Return True if the candidate text is similar to any existing review."""

    if len(candidate.text) < config.min_text_length:
        return False

    for review in existing:
        if abs(_days_between(candidate.date, review.date)) > config.date_tolerance_days:
            continue

        if len(review.text) < config.min_text_length:
            continue

        score = fuzz.token_set_ratio(candidate.text, review.text)
        if score >= config.similarity_threshold:
            return True
    return False


def _days_between(left: datetime, right: datetime) -> int:
    return abs((left - right).days)



