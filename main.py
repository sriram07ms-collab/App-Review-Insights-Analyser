"""Entrypoint orchestrating Layers 1-3 of the App Review Insights Analyzer."""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from src.layer1.cleaning import clean_text
from src.layer1.deduplicator import DeduplicationConfig, deduplicate_reviews
from src.layer1.pii_detector import PIIDetector
from src.layer1.scraper import GrowwReviewScraper, ReviewRecord, ScraperConfig
from src.layer1.validator import ReviewModel, validate_reviews
from src.layer2.theme_classifier import GeminiThemeClassifier, ThemeClassifierConfig
from src.layer2.weekly_aggregator import WeeklyThemeAggregator
from src.layer3 import Layer3Config, WeeklyPulsePipeline
from src.layer4 import Layer4Config, WeeklyEmailPipeline

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s - %(message)s")
LOGGER = logging.getLogger("pipeline")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Groww Play Store reviews (scheduler friendly, e.g., cron Mondays 09:00 IST)."
    )
    parser.add_argument("--start-date", help="Inclusive UTC date (YYYY-MM-DD) to begin fetching.")
    parser.add_argument("--end-date", help="Inclusive UTC date (YYYY-MM-DD) to stop fetching.")
    parser.add_argument(
        "--reference-date",
        help="Override 'today' for lookback calculations (YYYY-MM-DD, assumed UTC midnight).",
    )
    parser.add_argument("--max-reviews", type=int, help="Maximum number of reviews to fetch.")
    parser.add_argument("--lookback-days", type=int, help="Lookback window length (defaults to 84).")
    parser.add_argument("--min-offset-days", type=int, help="Days to skip from today (defaults to 7).")
    parser.add_argument("--app-id", help="Override Play Store app id (e.g., com.nextbillion.groww).")
    parser.add_argument("--locale", help="Play Store locale / hl parameter (e.g., en_IN).")
    parser.add_argument("--country", help="Play Store country / gl parameter (e.g., in).")
    parser.add_argument("--weekly-output-dir", help="Directory for week-level JSON files.")
    parser.add_argument("--max-scrolls", type=int, help="Max scroll iterations for Playwright fetcher.")
    parser.add_argument("--scroll-wait-ms", type=int, help="Delay between scrolls (milliseconds).")
    parser.add_argument(
        "--window-slices",
        help="Comma-separated list of ISO date ranges (start:end) to fetch and union, e.g. '2025-01-01:2025-03-31,2025-04-01:2025-06-30'.",
    )
    parser.add_argument(
        "--slice-days",
        type=int,
        help="Override automatic slice size (in days) when splitting large windows (default: 7).",
    )
    parser.add_argument(
        "--enable-rating-filters",
        action="store_true",
        help="Force-enable per-rating scraping passes (overrides env).",
    )
    parser.add_argument(
        "--disable-rating-filters",
        action="store_true",
        help="Disable per-rating scraping even if the env enables it.",
    )
    parser.add_argument(
        "--rating-filter-order",
        help="Comma-separated rating order to iterate (e.g., '5,4,3,2,1').",
    )
    parser.add_argument(
        "--browser",
        choices=["chromium", "firefox", "webkit"],
        help="Playwright browser engine (default: chromium).",
    )
    parser.add_argument(
        "--sort-mode",
        choices=["newest", "most_relevant", "highest_rating", "lowest_rating"],
        help="Sort order for Google Play reviews.",
    )
    parser.add_argument(
        "--per-rating-target",
        type=int,
        help="Number of reviews to collect per rating (1-5).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Playwright in headed mode (overrides PLAYWRIGHT_HEADLESS).",
    )
    parser.add_argument(
        "--cron-tag",
        help="Optional identifier for scheduler runs (e.g., 'monday-9am-ist') for log correlation.",
    )
    return parser.parse_args()


def run_pipeline(args: Optional[argparse.Namespace] = None) -> None:
    load_dotenv()
    args = args or parse_args()
    if getattr(args, "cron_tag", None):
        LOGGER.info("Scheduler trigger: %s", args.cron_tag)

    config = _build_scraper_config(args)
    scraper = GrowwReviewScraper(config)
    window_slices = _build_window_slices(args, config)

    LOGGER.info("Running multi-window scrape: %s slice(s) detected.", len(window_slices))
    raw_reviews = _fetch_multi_window(scraper, window_slices)
    if not raw_reviews:
        LOGGER.warning("No reviews found for the configured window.")
        return
    consolidated_window = {"start_date": window_slices[0][0], "end_date": window_slices[-1][1]}
    scraper.save_reviews(raw_reviews, **consolidated_window)

    validated, validation_summary = validate_reviews(raw_reviews)
    LOGGER.info("Validated %s/%s reviews", validation_summary.accepted, validation_summary.total)

    sanitized_models = [
        model.model_copy(
            update={
                "title": _clean_or_fallback(model.title),
                "text": _clean_or_fallback(model.text),
            }
        )
        for model in validated
    ]

    pii_detector = PIIDetector(enable_presidio=False)
    redacted_models = [
        model.model_copy(
            update={
                "title": pii_detector.redact(model.title),
                "text": pii_detector.redact(model.text),
            }
        )
        for model in sanitized_models
    ]

    deduped, dedup_summary = deduplicate_reviews(redacted_models, DeduplicationConfig())
    LOGGER.info("Deduplicated reviews: kept=%s dropped=%s", dedup_summary.kept, dedup_summary.dropped)

    # Filter out extremely short/empty reviews for Layer 2
    min_text_length = 10
    filtered_reviews = [r for r in deduped if len(r.text.strip()) >= min_text_length]
    if len(filtered_reviews) < len(deduped):
        dropped = len(deduped) - len(filtered_reviews)
        LOGGER.info("Filtered out %s reviews with text length < %s characters", dropped, min_text_length)

    if len(filtered_reviews) == 0:
        LOGGER.warning("No reviews remaining after filtering; skipping Layer 2.")
        return

    # Layer 2: LLM-based theme classification
    classifier_config = ThemeClassifierConfig(
        batch_size=int(os.getenv("THEME_CLASSIFIER_BATCH_SIZE", "8")),
        temperature=float(os.getenv("THEME_CLASSIFIER_TEMPERATURE", "0.1")),
    )
    classifier = GeminiThemeClassifier(config=classifier_config)
    LOGGER.info("Classifying %s reviews into fixed themes...", len(filtered_reviews))
    classifications = classifier.classify_reviews(filtered_reviews)
    LOGGER.info("Classified %s reviews", len(classifications))

    # Aggregate by week
    output_dir = Path(os.getenv("SCRAPER_OUTPUT_DIR", "data/raw"))
    weekly_dir = _resolve_weekly_dir(args, output_dir)
    aggregator = WeeklyThemeAggregator()
    aggregation_result = aggregator.aggregate(filtered_reviews, classifications, weekly_dir)

    # Save results
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    aggregator.save_aggregation(aggregation_result, processed_dir / "theme_aggregation.json")

    # Also save classifications for reference
    classifications_data = [
        {
            "review_id": c.review_id,
            "theme_id": c.theme_id,
            "theme_name": c.theme_name,
            "reason": c.reason,
        }
        for c in classifications
    ]
    with (processed_dir / "review_classifications.json").open("w", encoding="utf-8") as fh:
        json.dump(classifications_data, fh, ensure_ascii=False, indent=2)

    LOGGER.info(
        "Theme aggregation complete. Top themes: %s",
        ", ".join(f"{tid}({count})" for tid, count in aggregation_result.top_themes[:5]),
    )

    # Layer 3: Weekly pulse generation
    notes = _run_layer3(weekly_dir, processed_dir)

    # Layer 4: Email drafting/sending
    _run_layer4(notes)


def _build_scraper_config(args: argparse.Namespace) -> ScraperConfig:
    output_dir = Path(os.getenv("SCRAPER_OUTPUT_DIR", "data/raw"))
    weekly_dir = _resolve_weekly_dir(args, output_dir)
    headless = _env_bool("PLAYWRIGHT_HEADLESS", True)
    if getattr(args, "headed", False):
        headless = False

    fallback_env = os.getenv("PLAY_STORE_SORT_FALLBACKS", "")
    fallback_modes = tuple(
        mode.strip()
        for mode in fallback_env.split(",")
        if mode.strip()
    )
    enable_filters = _env_bool("SCRAPER_ENABLE_RATING_FILTERS", False)
    if getattr(args, "enable_rating_filters", False):
        enable_filters = True
    if getattr(args, "disable_rating_filters", False):
        enable_filters = False
    rating_order_value = getattr(args, "rating_filter_order", None) or os.getenv(
        "SCRAPER_RATING_FILTER_SEQUENCE"
    )
    rating_order = _parse_rating_sequence(rating_order_value) if rating_order_value else None

    return ScraperConfig(
        app_id=getattr(args, "app_id", None) or os.getenv("PLAY_STORE_APP_ID", "com.nextbillion.groww"),
        locale=getattr(args, "locale", None) or os.getenv("PLAY_STORE_LOCALE", "en"),
        country=getattr(args, "country", None) or os.getenv("PLAY_STORE_COUNTRY", "in"),
        lookback_days=getattr(args, "lookback_days", None)
        or int(os.getenv("REVIEW_LOOKBACK_DAYS", "84")),
        min_offset_days=getattr(args, "min_offset_days", None)
        or int(os.getenv("REVIEW_MIN_OFFSET_DAYS", "7")),
        max_reviews=getattr(args, "max_reviews", None) or int(os.getenv("SCRAPER_MAX_REVIEWS", "2000")),
        max_scroll_iterations=getattr(args, "max_scrolls", None)
        or int(os.getenv("SCRAPER_MAX_SCROLLS", "1000")),
        scroll_wait_ms=getattr(args, "scroll_wait_ms", None)
        or int(os.getenv("SCRAPER_SCROLL_WAIT_MS", "1500")),
        per_rating_target=getattr(args, "per_rating_target", None)
        or int(os.getenv("SCRAPER_PER_RATING_TARGET", "20")),
        output_dir=output_dir,
        weekly_output_dir=weekly_dir,
        headless=headless,
        playwright_browser=getattr(args, "browser", None) or os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
        sort_mode=getattr(args, "sort_mode", None) or os.getenv("PLAY_STORE_SORT_MODE", "newest"),
        fallback_sort_modes=fallback_modes,
        enable_rating_filters=enable_filters,
        rating_filter_order=rating_order or (5, 4, 3, 2, 1),
    )


def _resolve_weekly_dir(args: argparse.Namespace, output_dir: Path) -> Path:
    if getattr(args, "weekly_output_dir", None):
        return Path(args.weekly_output_dir)
    weekly_env = os.getenv("SCRAPER_WEEKLY_DIR")
    if weekly_env:
        return Path(weekly_env)
    return output_dir / "weekly"


def _build_window_slices(args: argparse.Namespace, config: ScraperConfig) -> List[tuple[datetime, datetime]]:
    """Return the list of time slices to fetch for Layer 1."""
    if getattr(args, "window_slices", None):
        return _parse_window_slices(args.window_slices)

    reference_date = _parse_cli_date(getattr(args, "reference_date", None))
    start_override = _parse_cli_date(getattr(args, "start_date", None))
    end_override = _parse_cli_date(getattr(args, "end_date", None))
    window_start, window_end = config.date_window(
        reference_date=reference_date,
        start_date=start_override,
        end_date=end_override,
    )
    slice_days = getattr(args, "slice_days", None) or int(os.getenv("SCRAPER_SLICE_DAYS", "7"))
    slice_days = max(1, slice_days)
    return _split_into_slices(window_start, window_end, slice_days=slice_days)


def _run_layer3(weekly_dir: Path, processed_dir: Path):
    try:
        layer3_output_dir = Path(os.getenv("LAYER3_OUTPUT_DIR", "data/processed/weekly_pulse"))
        layer3_config = Layer3Config(
            weekly_dir=weekly_dir,
            classifications_path=processed_dir / "review_classifications.json",
            output_dir=layer3_output_dir,
        )
        pulse_pipeline = WeeklyPulsePipeline(layer3_config)
        notes = pulse_pipeline.run()
        if notes:
            LOGGER.info("Generated %s weekly pulse notes (Layer 3).", len(notes))
        else:
            LOGGER.info("Layer 3 produced no weekly pulses (insufficient data).")
        return notes
    except Exception as exc:
        LOGGER.error("Layer 3 failed: %s", exc)
        return []


def _run_layer4(notes) -> None:
    if not notes:
        LOGGER.info("Skipping Layer 4 (no weekly notes).")
        return
    try:
        config = Layer4Config()
        pipeline = WeeklyEmailPipeline(config)
        pipeline.run()
    except Exception as exc:
        LOGGER.error("Layer 4 failed: %s", exc)


def _parse_window_slices(raw: Optional[str]) -> List[tuple[datetime, datetime]]:
    if not raw:
        return []
    slices: List[tuple[datetime, datetime]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise SystemExit(f"Invalid window slice '{chunk}'. Expected format START:END.")
        start_str, end_str = chunk.split(":", 1)
        start_dt = _parse_cli_date(start_str.strip())
        end_dt = _parse_cli_date(end_str.strip())
        if not start_dt or not end_dt:
            raise SystemExit(f"Unable to parse window slice '{chunk}'.")
        if start_dt > end_dt:
            raise SystemExit(f"Window slice start {start_dt} is after end {end_dt}.")
        slices.append((start_dt, end_dt))
    return slices


def _parse_rating_sequence(raw: str) -> Tuple[int, ...]:
    values: List[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            rating = int(chunk)
        except ValueError:
            LOGGER.warning("Invalid rating '%s' in SCRAPER_RATING_FILTER_SEQUENCE; skipping.", chunk)
            continue
        if rating in {1, 2, 3, 4, 5}:
            values.append(rating)
        else:
            LOGGER.warning("Rating %s is out of range (1-5); skipping.", rating)
    return tuple(values)


def _split_into_slices(start: datetime, end: datetime, slice_days: int = 7) -> List[tuple[datetime, datetime]]:
    """Split a window into evenly sized slices (default weekly)."""
    slices: List[tuple[datetime, datetime]] = []
    cursor = start
    step = timedelta(days=slice_days - 1)
    while cursor <= end:
        slice_end = min(cursor + step, end)
        slices.append((cursor, slice_end))
        cursor = slice_end + timedelta(days=1)
    return slices


def _fetch_multi_window(
    scraper: GrowwReviewScraper,
    window_slices: List[tuple[datetime, datetime]],
) -> List[ReviewRecord]:
    combined: dict[str, ReviewRecord] = {}
    for idx, (start, end) in enumerate(window_slices, start=1):
        LOGGER.info("Fetching slice %s/%s: %s -> %s", idx, len(window_slices), start.date(), end.date())
        segment = scraper.fetch_reviews(start_date=start, end_date=end)
        LOGGER.info("Slice %s yielded %s reviews.", idx, len(segment))
        for record in segment:
            combined[record.review_id] = record
    LOGGER.info("Combined %s unique reviews across %s slices.", len(combined), len(window_slices))
    return list(combined.values())


def _parse_cli_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise SystemExit(f"Invalid date format '{value}'. Use YYYY-MM-DD.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean_or_fallback(value: str) -> str:
    cleaned = clean_text(value)
    return cleaned or value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _persist_themes(themes) -> None:
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "themes.json"
    with output_file.open("w", encoding="utf-8") as fh:
        json.dump([theme.__dict__ for theme in themes], fh, ensure_ascii=False, indent=2)
    LOGGER.info("Saved theme summaries to %s", output_file)


def main() -> None:
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()


