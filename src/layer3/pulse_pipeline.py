"""
High-level orchestration for generating weekly pulse notes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import Layer3Config
from .models import ThemeInsight, WeeklyPulseNote
from .renderers import render_markdown
from .review_loader import WeeklyReviewLoader
from .theme_chunker import build_theme_chunks, select_top_theme_ids
from .topic_summarizer import GeminiTopicSummarizer
from .weekly_reducer import GeminiWeeklyReducer

LOGGER = logging.getLogger(__name__)


class WeeklyPulsePipeline:
    """Coordinates review loading, chunk summarization, and weekly note generation."""

    def __init__(
        self,
        config: Layer3Config,
        review_loader: WeeklyReviewLoader | None = None,
        topic_summarizer: GeminiTopicSummarizer | None = None,
        weekly_reducer: GeminiWeeklyReducer | None = None,
    ) -> None:
        self.config = config
        self.review_loader = review_loader or WeeklyReviewLoader(config.weekly_dir, config.classifications_path)
        self.topic_summarizer = topic_summarizer or GeminiTopicSummarizer(config)
        self.weekly_reducer = weekly_reducer or GeminiWeeklyReducer(config)

    def run(self) -> List[WeeklyPulseNote]:
        """Process every available week file and persist results."""
        self.config.ensure_output_dir()
        notes: List[WeeklyPulseNote] = []
        week_files = self.review_loader.list_week_files()
        if not week_files:
            LOGGER.warning("No week files found under %s; skipping Layer 3.", self.config.weekly_dir)
            return notes

        for week_file in week_files:
            if self.config.skip_existing_notes and self._note_exists(week_file):
                LOGGER.info("Skipping %s because weekly pulse already exists.", week_file.name)
                continue
            note = self._process_week_file(week_file)
            if note:
                notes.append(note)
                self._save_note(week_file, note)
        flush = getattr(self.topic_summarizer, "flush_cache", None)
        if callable(flush):
            flush()
        return notes

    def _process_week_file(self, week_file: Path) -> Optional[WeeklyPulseNote]:
        week_start, week_end, reviews = self.review_loader.load_week(week_file)
        LOGGER.info("Layer 3: %s has %s classified reviews.", week_file.name, len(reviews))
        if len(reviews) < self.config.min_reviews_per_week:
            LOGGER.info("Skipping %s (%s reviews < min %s).", week_file, len(reviews), self.config.min_reviews_per_week)
            return None

        top_theme_ids = select_top_theme_ids(reviews, self.config.max_themes)
        if not top_theme_ids:
            LOGGER.info("No classified themes for %s; skipping.", week_file)
            return None
        LOGGER.info("Selected top themes for %s: %s", week_file.name, ", ".join(top_theme_ids))

        chunks = build_theme_chunks(reviews, top_theme_ids, self.config.chunk_size)
        if not chunks:
            LOGGER.info("No chunks generated for %s; skipping.", week_file)
            return None
        LOGGER.info("Built %s chunk(s) for %s.", len(chunks), week_file.name)

        insights_dict = self.topic_summarizer.summarize_chunks(chunks)
        insights = [insights_dict[theme_id] for theme_id in top_theme_ids if theme_id in insights_dict]
        insights = self._filter_insights(insights)
        if not insights:
            LOGGER.info("No insights generated for %s; skipping.", week_file)
            return None

        note = self.weekly_reducer.build_weekly_note(week_start, week_end, insights)
        if note:
            LOGGER.info("Generated weekly pulse for %s-%s (word_count=%s).", week_start, week_end, note.word_count)
        return note

    def _save_note(self, week_file: Path, note: WeeklyPulseNote) -> Path:
        output_path = self._note_json_path(week_file)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(note.as_dict(), fh, ensure_ascii=False, indent=2)
        markdown = render_markdown(note)
        markdown_path = output_path.with_suffix(".md")
        with markdown_path.open("w", encoding="utf-8") as fh:
            fh.write(markdown)
        LOGGER.info("Saved weekly pulse to %s (JSON) and %s (Markdown)", output_path, markdown_path)
        return output_path

    def _note_json_path(self, week_file: Path) -> Path:
        output_filename = week_file.stem.replace("week_", "pulse_") + ".json"
        return self.config.output_dir / output_filename

    def _note_exists(self, week_file: Path) -> bool:
        json_path = self._note_json_path(week_file)
        markdown_path = json_path.with_suffix(".md")
        return json_path.exists() and markdown_path.exists()

    def _filter_insights(self, insights: List[ThemeInsight]) -> List[ThemeInsight]:
        filtered: List[ThemeInsight] = []
        for insight in insights:
            if not insight.key_points:
                LOGGER.info("Dropping theme %s: no key points.", insight.theme_name)
                continue
            if not insight.quotes:
                LOGGER.info("Dropping theme %s: no quotes.", insight.theme_name)
                continue
            filtered.append(insight)
        return filtered

