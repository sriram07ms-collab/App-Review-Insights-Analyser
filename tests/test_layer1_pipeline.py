from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.layer1.scraper import GrowwReviewScraper, ScraperConfig
from src.layer1.validator import validate_reviews
from src.layer1.pii_detector import PIIDetector
from src.layer1.deduplicator import DeduplicationConfig, deduplicate_reviews


def test_layer1_pipeline_from_fixture(tmp_path):
    fixture_path = Path(__file__).parent / "fixtures" / "sample_reviews.html"

    config = ScraperConfig(
        app_id="com.nextbillion.groww",
        per_rating_target=0,
        html_fixture_path=fixture_path,
        output_dir=tmp_path / "raw",
        weekly_output_dir=tmp_path / "weekly",
        headless=True,
        sort_mode="newest",
    )

    scraper = GrowwReviewScraper(config)
    reference_date = datetime(2025, 11, 24, tzinfo=timezone.utc)

    records = scraper.fetch_reviews(reference_date=reference_date)

    assert len(records) == 4
    assert {record.rating for record in records} == {1, 2, 5}

    output_file = scraper.save_reviews(records, reference_date=reference_date)
    assert output_file.exists()
    assert any(config.weekly_output_dir.glob("week_*.json"))

    validated, summary = validate_reviews(records)
    assert summary.accepted == 4

    pii = PIIDetector(enable_presidio=False)
    cleaned_models = [
        model.model_copy(update={"text": pii.redact(model.text)})
        for model in validated
    ]

    deduped, dedup_summary = deduplicate_reviews(cleaned_models, DeduplicationConfig())
    assert dedup_summary.dropped == 1
    assert len(deduped) == 3
