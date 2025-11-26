"""Weekly aggregation of theme classifications."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from ..layer1.validator import ReviewModel
from .theme_classifier import ReviewClassification
from .theme_config import FIXED_THEMES

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WeeklyThemeCounts:
    """Theme counts for a single week."""

    week_start_date: str
    week_end_date: str
    theme_counts: Dict[str, int]  # theme_id -> count
    total_reviews: int


@dataclass(slots=True)
class ThemeAggregationResult:
    """Complete aggregation result across all weeks."""

    weekly_counts: List[WeeklyThemeCounts]
    overall_counts: Dict[str, int]  # theme_id -> total count across all weeks
    top_themes: List[tuple[str, int]]  # (theme_id, count) sorted descending


class WeeklyThemeAggregator:
    """Aggregates theme classifications by week."""

    def aggregate(
        self,
        reviews: List[ReviewModel],
        classifications: List[ReviewClassification],
        weekly_dir: Path,
    ) -> ThemeAggregationResult:
        """Aggregate theme counts by week from weekly JSON files."""
        # Build lookup: review_id -> classification
        classification_lookup = {c.review_id: c for c in classifications}

        # Load weekly files and group reviews by week
        weekly_data: Dict[str, List[ReviewModel]] = defaultdict(list)
        if weekly_dir.exists():
            for week_file in sorted(weekly_dir.glob("week_*.json")):
                try:
                    week_reviews = self._load_weekly_file(week_file)
                    for review in week_reviews:
                        if review.review_id in classification_lookup:
                            week_key = self._extract_week_key(week_file)
                            weekly_data[week_key].append(review)
                except Exception as exc:
                    LOGGER.warning("Failed to load weekly file %s: %s", week_file, exc)

        # If no weekly files, group by review date
        if not weekly_data:
            LOGGER.info("No weekly files found; grouping reviews by date")
            for review in reviews:
                if review.review_id in classification_lookup:
                    week_key = self._week_key_from_date(review.date)
                    weekly_data[week_key].append(review)

        # Build weekly counts
        weekly_counts: List[WeeklyThemeCounts] = []
        overall_counts: Dict[str, int] = defaultdict(int)

        for week_key in sorted(weekly_data.keys()):
            week_reviews = weekly_data[week_key]
            theme_counts: Dict[str, int] = defaultdict(int)

            for review in week_reviews:
                classification = classification_lookup.get(review.review_id)
                if classification:
                    theme_counts[classification.theme_id] += 1
                    overall_counts[classification.theme_id] += 1

            # Extract week dates from first review or week_key
            week_start, week_end = self._parse_week_key(week_key)
            weekly_counts.append(
                WeeklyThemeCounts(
                    week_start_date=week_start,
                    week_end_date=week_end,
                    theme_counts=dict(theme_counts),
                    total_reviews=len(week_reviews),
                )
            )

        # Sort themes by count
        top_themes = sorted(overall_counts.items(), key=lambda x: x[1], reverse=True)

        return ThemeAggregationResult(
            weekly_counts=weekly_counts,
            overall_counts=dict(overall_counts),
            top_themes=top_themes,
        )

    def _load_weekly_file(self, week_file: Path) -> List[ReviewModel]:
        """Load reviews from a weekly JSON file."""
        with week_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        reviews = []
        for item in data:
            try:
                review = ReviewModel(
                    review_id=item["review_id"],
                    title=item.get("title", ""),
                    text=item["text"],
                    rating=item.get("rating", 3),
                    date=datetime.fromisoformat(item["date"].replace("Z", "+00:00")),
                    author=item.get("author"),
                    product_tag=item.get("product_tag"),
                )
                reviews.append(review)
            except Exception as exc:
                LOGGER.warning("Failed to parse review from weekly file: %s", exc)
        return reviews

    def _extract_week_key(self, week_file: Path) -> str:
        """Extract week key from filename (e.g., 'week_2025-11-10.json' -> '2025-11-10')."""
        stem = week_file.stem  # 'week_2025-11-10'
        if stem.startswith("week_"):
            return stem[5:]  # '2025-11-10'
        return stem

    def _week_key_from_date(self, date: datetime) -> str:
        """Generate week key from review date (Monday of that week)."""
        # Get Monday of the week
        days_since_monday = date.weekday()
        monday = date.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        return monday.strftime("%Y-%m-%d")

    def _parse_week_key(self, week_key: str) -> tuple[str, str]:
        """Parse week key into start and end dates."""
        try:
            week_start = datetime.strptime(week_key, "%Y-%m-%d")
            week_end = week_start + timedelta(days=6)
            return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")
        except Exception:
            return week_key, week_key

    def save_aggregation(self, result: ThemeAggregationResult, output_path: Path) -> None:
        """Save aggregation result to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "weekly_counts": [asdict(wc) for wc in result.weekly_counts],
            "overall_counts": result.overall_counts,
            "top_themes": [{"theme_id": tid, "count": count} for tid, count in result.top_themes],
        }
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        LOGGER.info("Saved theme aggregation to %s", output_path)

