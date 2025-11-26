from datetime import datetime, timezone
from pathlib import Path

import json
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.layer3.config import Layer3Config
from src.layer3.models import ThemeInsight, WeeklyPulseNote
from src.layer3.pulse_pipeline import WeeklyPulsePipeline
from src.layer3.renderers import render_markdown
from src.layer3.review_loader import WeeklyReviewLoader
from src.layer3.theme_chunker import select_top_theme_ids
from src.layer3.topic_summarizer import dedupe_and_trim
from src.layer3.weekly_reducer import calculate_word_count


@pytest.fixture
def sample_reviews(tmp_path):
    weekly_dir = tmp_path / "weekly"
    weekly_dir.mkdir()
    week_file = weekly_dir / "week_2025-11-10.json"
    week_data = [
        {
            "review_id": "r1",
            "title": "Slow orders",
            "text": "Orders take 20 minutes to execute.",
            "rating": 1,
            "date": "2025-11-15T12:00:00+00:00",
            "week_start_date": "2025-11-10",
            "week_end_date": "2025-11-16",
        },
        {
            "review_id": "r2",
            "title": "UI issue",
            "text": "Need statement download button on portfolio page.",
            "rating": 4,
            "date": "2025-11-12T10:00:00+00:00",
            "week_start_date": "2025-11-10",
            "week_end_date": "2025-11-16",
        },
        {
            "review_id": "r3",
            "title": "Payment bug",
            "text": "Payout stuck even after 24 hours.",
            "rating": 2,
            "date": "2025-11-11T09:00:00+00:00",
            "week_start_date": "2025-11-10",
            "week_end_date": "2025-11-16",
        },
    ]
    week_file.write_text(json.dumps(week_data))

    classifications_path = tmp_path / "review_classifications.json"
    classifications = [
        {"review_id": "r1", "theme_id": "glitches", "theme_name": "Slow, Glitches"},
        {"review_id": "r2", "theme_id": "ui_ux", "theme_name": "UI/UX"},
        {"review_id": "r3", "theme_id": "payments_statements", "theme_name": "Payments/Statements"},
    ]
    classifications_path.write_text(json.dumps(classifications))

    return weekly_dir, classifications_path


def test_select_top_theme_ids(sample_reviews):
    weekly_dir, classifications_path = sample_reviews
    loader = WeeklyReviewLoader(weekly_dir, classifications_path)
    _, _, reviews = loader.load_week(next(iter(loader.list_week_files())))

    top_theme_ids = select_top_theme_ids(reviews, max_themes=2)
    assert len(top_theme_ids) == 2
    assert set(top_theme_ids).issubset({"glitches", "ui_ux", "payments_statements"})


def test_dedupe_and_trim():
    values = ["Point A", "point a ", "Point B", "", "Point C", "Point D"]
    trimmed = dedupe_and_trim(values, max_items=3)
    assert trimmed == ["Point A", "Point B", "Point C"]


def test_calculate_word_count():
    note = {
        "overview": "Summary text here.",
        "themes": [{"name": "Theme A", "summary": "Insight about A."}],
        "quotes": ["Quote one."],
        "actions": ["Action item."],
    }
    assert calculate_word_count(note) == 10


class DummySummarizer:
    def __init__(self, insights):
        self._insights = insights

    def summarize_chunks(self, chunks):
        return self._insights

    def flush_cache(self):
        pass


class DummyReducer:
    def build_weekly_note(self, week_start, week_end, insights):
        return WeeklyPulseNote(
            week_start=week_start,
            week_end=week_end,
            title="Weekly Pulse",
            overview="Overview text",
            themes=[{"name": i.theme_name, "summary": "; ".join(i.key_points)} for i in insights],
            quotes=["Quote 1", "Quote 2", "Quote 3"],
            actions=["Action 1", "Action 2", "Action 3"],
            word_count=42,
        )


def test_weekly_pulse_pipeline_with_stubs(sample_reviews, tmp_path):
    weekly_dir, classifications_path = sample_reviews
    output_dir = tmp_path / "pulse"

    # Pre-built insights to avoid LLM dependency
    insights = {
        "glitches": ThemeInsight(theme_id="glitches", theme_name="Slow, Glitches", key_points=["Orders lag"], quotes=["Orders lag quote"]),
        "ui_ux": ThemeInsight(theme_id="ui_ux", theme_name="UI/UX", key_points=["Missing button"], quotes=["UI quote"]),
        "payments_statements": ThemeInsight(theme_id="payments_statements", theme_name="Payments/Statements", key_points=["Payout stuck"], quotes=["Payment quote"]),
    }

    config = Layer3Config(
        weekly_dir=weekly_dir,
        classifications_path=classifications_path,
        output_dir=output_dir,
        chunk_size=2,
        max_key_points=3,
        max_quotes_per_theme=2,
        max_themes=3,
        min_reviews_per_week=1,
        max_words=250,
        enable_chunk_cache=False,
    )

    loader = WeeklyReviewLoader(weekly_dir, classifications_path)
    pipeline = WeeklyPulsePipeline(
        config=config,
        review_loader=loader,
        topic_summarizer=DummySummarizer(insights),
        weekly_reducer=DummyReducer(),
    )

    notes = pipeline.run()
    assert len(notes) == 1
    note = notes[0]
    assert note.title == "Weekly Pulse"
    assert note.word_count == 42
    json_path = output_dir / "pulse_2025-11-10.json"
    md_path = output_dir / "pulse_2025-11-10.md"
    assert json_path.exists()
    assert md_path.exists()


def test_render_markdown():
    note = WeeklyPulseNote(
        week_start="2025-11-10",
        week_end="2025-11-16",
        title="Pulse",
        overview="Overview text",
        themes=[{"name": "Theme A", "summary": "Summary A"}],
        quotes=["Quote A"],
        actions=["Action A"],
        word_count=120,
    )
    md = render_markdown(note)
    assert "# Pulse" in md
    assert "- **Theme A**" in md
    assert "Word count: 120" in md

