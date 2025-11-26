"""
Utilities for selecting top themes and chunking reviews for map-stage prompts.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from .models import ClassifiedReview, ThemeChunk


def select_top_theme_ids(reviews: List[ClassifiedReview], max_themes: int) -> List[str]:
    """Return theme IDs ordered by frequency (desc)."""
    counter = Counter(review.theme_id for review in reviews)
    most_common = counter.most_common(max_themes)
    return [theme_id for theme_id, _ in most_common]


def group_reviews_by_theme(reviews: List[ClassifiedReview]) -> Dict[str, List[ClassifiedReview]]:
    grouped: Dict[str, List[ClassifiedReview]] = defaultdict(list)
    for review in reviews:
        grouped[review.theme_id].append(review)
    return grouped


def build_theme_chunks(
    reviews: List[ClassifiedReview],
    selected_theme_ids: List[str],
    chunk_size: int,
) -> List[ThemeChunk]:
    """Split reviews for selected themes into manageable chunks."""
    grouped = group_reviews_by_theme(reviews)
    chunks: List[ThemeChunk] = []

    for theme_id in selected_theme_ids:
        theme_reviews = grouped.get(theme_id, [])
        if not theme_reviews:
            continue

        theme_name = theme_reviews[0].theme_name
        for start in range(0, len(theme_reviews), chunk_size):
            chunk_reviews = theme_reviews[start : start + chunk_size]
            chunks.append(ThemeChunk(theme_id=theme_id, theme_name=theme_name, reviews=chunk_reviews))

    return chunks

