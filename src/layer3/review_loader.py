"""
Load weekly review slices and merge with Layer 2 classifications.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ..layer1.validator import ReviewModel
from .models import ClassifiedReview

LOGGER = logging.getLogger(__name__)


class WeeklyReviewLoader:
    """Utility for reading weekly review files and attaching theme metadata."""

    def __init__(self, weekly_dir: Path, classifications_path: Path) -> None:
        self.weekly_dir = weekly_dir
        self.classifications_path = classifications_path
        self._classification_lookup = self._load_classifications()

    def list_week_files(self) -> List[Path]:
        if not self.weekly_dir.exists():
            LOGGER.warning("Weekly directory %s does not exist.", self.weekly_dir)
            return []
        return sorted(self.weekly_dir.glob("week_*.json"))

    def load_week(self, week_file: Path) -> Tuple[str, str, List[ClassifiedReview]]:
        """Load reviews for a given weekly file and attach classification metadata."""
        with week_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        week_start = data[0].get("week_start_date") if data else None
        week_end = data[0].get("week_end_date") if data else None

        classified_reviews: List[ClassifiedReview] = []
        for item in data:
            classification = self._classification_lookup.get(item.get("review_id"))
            if not classification:
                LOGGER.debug("Skipping review %s (missing classification).", item.get("review_id"))
                continue
            try:
                review = ReviewModel(
                    review_id=item["review_id"],
                    title=item.get("title", ""),
                    text=item["text"],
                    rating=item.get("rating", 0),
                    date=datetime.fromisoformat(item["date"].replace("Z", "+00:00")),
                )
            except Exception as exc:
                LOGGER.warning("Invalid review payload in %s: %s", week_file, exc)
                continue

            classified_reviews.append(
                ClassifiedReview(
                    review_id=review.review_id,
                    title=review.title,
                    text=review.text,
                    rating=review.rating,
                    date=review.date,
                    theme_id=classification["theme_id"],
                    theme_name=classification["theme_name"],
                )
            )

        return week_start or "", week_end or "", classified_reviews

    def _load_classifications(self) -> Dict[str, Dict[str, str]]:
        if not self.classifications_path.exists():
            LOGGER.warning("Classification file %s not found; Layer 3 will be skipped.", self.classifications_path)
            return {}

        with self.classifications_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        lookup: Dict[str, Dict[str, str]] = {}
        for item in payload:
            review_id = item.get("review_id")
            if not review_id:
                continue
            lookup[review_id] = {
                "theme_id": item.get("theme_id") or item.get("chosen_theme"),
                "theme_name": item.get("theme_name") or item.get("theme_id"),
            }
        return lookup

