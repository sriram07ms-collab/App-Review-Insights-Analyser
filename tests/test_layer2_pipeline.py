"""Comprehensive tests for Layer 2: Theme Classification and Aggregation."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.layer1.validator import ReviewModel
from src.layer2.theme_classifier import (
    GeminiThemeClassifier,
    ReviewClassification,
    ThemeClassifierConfig,
)
from src.layer2.weekly_aggregator import (
    WeeklyThemeAggregator,
    ThemeAggregationResult,
    WeeklyThemeCounts,
)
from src.layer2.theme_config import FIXED_THEMES, DEFAULT_THEME_ID, get_theme_by_id


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_reviews():
    """Create sample reviews for testing."""
    base_date = datetime(2025, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
    return [
        ReviewModel(
            review_id="review-1",
            title="App is buggy",
            text="When placing order in intraday it place order really late and sometimes even after 20 mins order pending.",
            rating=1,
            date=base_date - timedelta(days=5),
        ),
        ReviewModel(
            review_id="review-2",
            title="Great UI",
            text="Easy and simple user interface but today I need a stock holding statement for a visa application.",
            rating=5,
            date=base_date - timedelta(days=12),
        ),
        ReviewModel(
            review_id="review-3",
            title="Profit discrepancy",
            text="You see more profit on your PL, but when you exit it will less than the first amount.",
            rating=2,
            date=base_date - timedelta(days=19),
        ),
        ReviewModel(
            review_id="review-4",
            title="Customer support unhelpful",
            text="Contacted customer care about an issue but received unhelpful responses and no resolution.",
            rating=1,
            date=base_date - timedelta(days=26),
        ),
        ReviewModel(
            review_id="review-5",
            title="App is slow",
            text="App performance issues, slow loading times, laggy interface, delayed responses.",
            rating=2,
            date=base_date - timedelta(days=33),
        ),
    ]


@pytest.fixture
def mock_gemini_model():
    """Mock Gemini model for testing."""
    mock_model = Mock()
    mock_response = Mock()
    mock_response.text = json.dumps([
        {
            "review_id": "review-1",
            "chosen_theme": "glitches",
            "short_reason": "Review mentions order delays and pending orders",
        },
        {
            "review_id": "review-2",
            "chosen_theme": "ui_ux",
            "short_reason": "User mentions UI and needs statement",
        },
        {
            "review_id": "review-3",
            "chosen_theme": "payments_statements",
            "short_reason": "Discusses profit discrepancies",
        },
        {
            "review_id": "review-4",
            "chosen_theme": "customer_support",
            "short_reason": "Mentions customer care issues",
        },
        {
            "review_id": "review-5",
            "chosen_theme": "slow",
            "short_reason": "Describes performance issues",
        },
    ])
    mock_model.generate_content.return_value = mock_response
    return mock_model


@pytest.fixture
def weekly_dir_with_files(tmp_path):
    """Create a weekly directory with sample weekly JSON files."""
    weekly_dir = tmp_path / "weekly"
    weekly_dir.mkdir()

    # Week 1: 2025-11-10 to 2025-11-16 (2 reviews)
    week1_file = weekly_dir / "week_2025-11-10.json"
    week1_file.write_text(
        json.dumps([
            {
                "review_id": "review-1",
                "title": "App is buggy",
                "text": "When placing order...",
                "rating": 1,
                "date": "2025-11-15T12:00:00+00:00",
            },
            {
                "review_id": "review-2",
                "title": "Great UI",
                "text": "Easy and simple...",
                "rating": 5,
                "date": "2025-11-12T10:00:00+00:00",
            },
        ])
    )

    # Week 2: 2025-11-03 to 2025-11-09 (1 review)
    week2_file = weekly_dir / "week_2025-11-03.json"
    week2_file.write_text(
        json.dumps([
            {
                "review_id": "review-3",
                "title": "Profit discrepancy",
                "text": "You see more profit...",
                "rating": 2,
                "date": "2025-11-05T14:00:00+00:00",
            },
        ])
    )

    # Week 3: 2025-10-27 to 2025-11-02 (2 reviews)
    week3_file = weekly_dir / "week_2025-10-27.json"
    week3_file.write_text(
        json.dumps([
            {
                "review_id": "review-4",
                "title": "Customer support unhelpful",
                "text": "Contacted customer care...",
                "rating": 1,
                "date": "2025-10-30T09:00:00+00:00",
            },
            {
                "review_id": "review-5",
                "title": "App is slow",
                "text": "App performance issues...",
                "rating": 2,
                "date": "2025-10-28T16:00:00+00:00",
            },
        ])
    )

    return weekly_dir


# ============================================================================
# Theme Classifier Tests
# ============================================================================


class TestGeminiThemeClassifier:
    """Test theme classification functionality."""

    @patch("src.layer2.theme_classifier.genai")
    def test_classify_reviews_success(self, mock_genai, sample_reviews, mock_gemini_model):
        """Test successful classification of reviews."""
        # Setup
        mock_genai.configure = Mock()
        mock_genai.GenerativeModel.return_value = mock_gemini_model

        classifier = GeminiThemeClassifier(api_key="test-key")
        classifications = classifier.classify_reviews(sample_reviews)

        # Assertions
        assert len(classifications) == 5
        assert all(isinstance(c, ReviewClassification) for c in classifications)

        # Check specific classifications
        review1_class = next(c for c in classifications if c.review_id == "review-1")
        assert review1_class.theme_id == "glitches"
        assert review1_class.theme_name == "Slow, Glitches"

        review2_class = next(c for c in classifications if c.review_id == "review-2")
        assert review2_class.theme_id == "ui_ux"
        assert review2_class.theme_name == "UI/UX"

        # Verify LLM was called
        assert mock_gemini_model.generate_content.called

    @patch("src.layer2.theme_classifier.genai")
    def test_classify_reviews_batch_processing(self, mock_genai, mock_gemini_model):
        """Test that reviews are processed in batches."""
        # Create 15 reviews (should be split into 2 batches with batch_size=8)
        reviews = [
            ReviewModel(
                review_id=f"review-{i}",
                title=f"Review {i}",
                text=f"Review text {i}",
                rating=3,
                date=datetime.now(timezone.utc),
            )
            for i in range(15)
        ]

        mock_genai.configure = Mock()
        mock_genai.GenerativeModel.return_value = mock_gemini_model

        config = ThemeClassifierConfig(batch_size=8)
        classifier = GeminiThemeClassifier(api_key="test-key", config=config)

        # Mock response for each batch
        def mock_response_side_effect(*args, **kwargs):
            mock_resp = Mock()
            # Return classifications for the batch
            batch_num = mock_gemini_model.generate_content.call_count
            if batch_num == 1:
                # First batch: 8 reviews
                mock_resp.text = json.dumps([
                    {"review_id": f"review-{i}", "chosen_theme": "ui_ux", "short_reason": "Test"}
                    for i in range(8)
                ])
            else:
                # Second batch: 7 reviews
                mock_resp.text = json.dumps([
                    {"review_id": f"review-{i}", "chosen_theme": "glitches", "short_reason": "Test"}
                    for i in range(8, 15)
                ])
            return mock_resp

        mock_gemini_model.generate_content.side_effect = mock_response_side_effect

        classifications = classifier.classify_reviews(reviews)

        # Should have 15 classifications
        assert len(classifications) == 15
        # Should have been called twice (2 batches)
        assert mock_gemini_model.generate_content.call_count == 2

    @patch("src.layer2.theme_classifier.genai")
    def test_classify_reviews_invalid_theme_fallback(self, mock_genai, sample_reviews):
        """Test that invalid theme IDs fallback to default."""
        mock_model = Mock()
        mock_response = Mock()
        # LLM returns invalid theme ID
        mock_response.text = json.dumps([
            {
                "review_id": "review-1",
                "chosen_theme": "invalid_theme",
                "short_reason": "Test",
            },
        ])
        mock_model.generate_content.return_value = mock_response

        mock_genai.configure = Mock()
        mock_genai.GenerativeModel.return_value = mock_model

        classifier = GeminiThemeClassifier(api_key="test-key")
        classifications = classifier.classify_reviews(sample_reviews[:1])

        # Should fallback to default theme
        assert len(classifications) == 1
        assert classifications[0].theme_id == DEFAULT_THEME_ID
        assert classifications[0].review_id == "review-1"

    @patch("src.layer2.theme_classifier.genai")
    def test_classify_reviews_missing_review_id(self, mock_genai, sample_reviews):
        """Test handling of missing review IDs in LLM response."""
        mock_model = Mock()
        mock_response = Mock()
        # LLM response missing review_id
        mock_response.text = json.dumps([
            {
                "chosen_theme": "glitches",
                "short_reason": "Test",
            },
            {
                "review_id": "review-2",
                "chosen_theme": "ui_ux",
                "short_reason": "Test",
            },
        ])
        mock_model.generate_content.return_value = mock_response

        mock_genai.configure = Mock()
        mock_genai.GenerativeModel.return_value = mock_model

        classifier = GeminiThemeClassifier(api_key="test-key")
        classifications = classifier.classify_reviews(sample_reviews[:2])

        # Should have 2 classifications: one from LLM, one as fallback
        assert len(classifications) == 2
        # review-1 should get default theme (missing from LLM response)
        review1_class = next(c for c in classifications if c.review_id == "review-1")
        assert review1_class.theme_id == DEFAULT_THEME_ID
        # review-2 should be classified correctly
        review2_class = next(c for c in classifications if c.review_id == "review-2")
        assert review2_class.theme_id == "ui_ux"

    @patch("src.layer2.theme_classifier.genai")
    def test_classify_reviews_llm_failure_fallback(self, mock_genai, sample_reviews):
        """Test fallback when LLM fails completely."""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API Error")

        mock_genai.configure = Mock()
        mock_genai.GenerativeModel.return_value = mock_model

        config = ThemeClassifierConfig(max_retries=1)
        classifier = GeminiThemeClassifier(api_key="test-key", config=config)
        classifications = classifier.classify_reviews(sample_reviews)

        # Should have fallback classifications for all reviews
        assert len(classifications) == 5
        assert all(c.theme_id == DEFAULT_THEME_ID for c in classifications)
        assert all("Fallback" in c.reason for c in classifications)

    @patch("src.layer2.theme_classifier.genai")
    def test_classify_reviews_json_parsing_edge_cases(self, mock_genai, sample_reviews):
        """Test JSON parsing with various edge cases."""
        test_cases = [
            # JSON wrapped in code blocks
            ("```json\n" + json.dumps([{"review_id": "review-1", "chosen_theme": "glitches", "short_reason": "Test"}]) + "\n```"),
            # Single object instead of array
            (json.dumps({"review_id": "review-1", "chosen_theme": "glitches", "short_reason": "Test"})),
            # Wrapped in object with "reviews" key
            (json.dumps({"reviews": [{"review_id": "review-1", "chosen_theme": "glitches", "short_reason": "Test"}]})),
        ]

        for response_text in test_cases:
            mock_model = Mock()
            mock_response = Mock()
            mock_response.text = response_text
            mock_model.generate_content.return_value = mock_response

            mock_genai.configure = Mock()
            mock_genai.GenerativeModel.return_value = mock_model

            classifier = GeminiThemeClassifier(api_key="test-key")
            classifications = classifier.classify_reviews(sample_reviews[:1])

            assert len(classifications) == 1
            assert classifications[0].review_id == "review-1"

    def test_classify_reviews_empty_list(self):
        """Test classification with empty review list."""
        with patch("src.layer2.theme_classifier.genai") as mock_genai:
            mock_genai.configure = Mock()
            mock_genai.GenerativeModel = Mock()

            classifier = GeminiThemeClassifier(api_key="test-key")
            classifications = classifier.classify_reviews([])

            assert classifications == []

    @patch("src.layer2.theme_classifier.genai")
    def test_validate_theme_id_fuzzy_matching(self, mock_genai, sample_reviews):
        """Test fuzzy matching for theme IDs."""
        mock_model = Mock()
        mock_response = Mock()
        # LLM returns slightly different theme ID
        mock_response.text = json.dumps([
            {
                "review_id": "review-1",
                "chosen_theme": "glitch",  # Close to "glitches"
                "short_reason": "Test",
            },
        ])
        mock_model.generate_content.return_value = mock_response

        mock_genai.configure = Mock()
        mock_genai.GenerativeModel.return_value = mock_model

        classifier = GeminiThemeClassifier(api_key="test-key")
        classifications = classifier.classify_reviews(sample_reviews[:1])

        # Should match to "glitches" via fuzzy matching
        assert classifications[0].theme_id == "glitches"


# ============================================================================
# Weekly Aggregator Tests
# ============================================================================


class TestWeeklyThemeAggregator:
    """Test weekly aggregation functionality."""

    def test_aggregate_from_weekly_files(
        self, sample_reviews, weekly_dir_with_files, tmp_path
    ):
        """Test aggregation using weekly JSON files."""
        # Create classifications
        classifications = [
            ReviewClassification(
                review_id="review-1",
                theme_id="glitches",
                theme_name="Slow, Glitches",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-2",
                theme_id="ui_ux",
                theme_name="UI/UX",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-3",
                theme_id="payments_statements",
                theme_name="Payments/Statements",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-4",
                theme_id="customer_support",
                theme_name="Customer Support",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-5",
                theme_id="slow",
                theme_name="Slow",
                reason="Test",
            ),
        ]

        aggregator = WeeklyThemeAggregator()
        result = aggregator.aggregate(sample_reviews, classifications, weekly_dir_with_files)

        # Assertions
        assert isinstance(result, ThemeAggregationResult)
        assert len(result.weekly_counts) == 3  # 3 weeks

        # Check week 1 (2025-11-10)
        week1 = next(w for w in result.weekly_counts if w.week_start_date == "2025-11-10")
        assert week1.total_reviews == 2
        assert week1.theme_counts["glitches"] == 1
        assert week1.theme_counts["ui_ux"] == 1

        # Check week 2 (2025-11-03)
        week2 = next(w for w in result.weekly_counts if w.week_start_date == "2025-11-03")
        assert week2.total_reviews == 1
        assert week2.theme_counts["payments_statements"] == 1

        # Check week 3 (2025-10-27)
        week3 = next(w for w in result.weekly_counts if w.week_start_date == "2025-10-27")
        assert week3.total_reviews == 2
        assert week3.theme_counts["customer_support"] == 1
        assert week3.theme_counts["slow"] == 1

        # Check overall counts
        assert result.overall_counts["glitches"] == 1
        assert result.overall_counts["ui_ux"] == 1
        assert result.overall_counts["payments_statements"] == 1
        assert result.overall_counts["customer_support"] == 1
        assert result.overall_counts["slow"] == 1

        # Check top themes (all should have count 1, sorted)
        assert len(result.top_themes) == 5
        # All counts are 1, so order may vary, but all should be present
        theme_ids = [tid for tid, _ in result.top_themes]
        assert set(theme_ids) == {"glitches", "ui_ux", "payments_statements", "customer_support", "slow"}

    def test_aggregate_from_review_dates(self, sample_reviews, tmp_path):
        """Test aggregation when no weekly files exist (group by date)."""
        classifications = [
            ReviewClassification(
                review_id="review-1",
                theme_id="glitches",
                theme_name="Slow, Glitches",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-2",
                theme_id="ui_ux",
                theme_name="UI/UX",
                reason="Test",
            ),
        ]

        # Use empty weekly directory
        weekly_dir = tmp_path / "weekly"
        weekly_dir.mkdir()

        aggregator = WeeklyThemeAggregator()
        result = aggregator.aggregate(sample_reviews[:2], classifications, weekly_dir)

        # Should still aggregate by week based on review dates
        assert len(result.weekly_counts) >= 1
        assert result.overall_counts["glitches"] == 1
        assert result.overall_counts["ui_ux"] == 1

    def test_aggregate_missing_classifications(self, sample_reviews, weekly_dir_with_files):
        """Test aggregation when some reviews don't have classifications."""
        # Only classify 2 out of 5 reviews
        classifications = [
            ReviewClassification(
                review_id="review-1",
                theme_id="glitches",
                theme_name="Slow, Glitches",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-2",
                theme_id="ui_ux",
                theme_name="UI/UX",
                reason="Test",
            ),
        ]

        aggregator = WeeklyThemeAggregator()
        result = aggregator.aggregate(sample_reviews, classifications, weekly_dir_with_files)

        # Should only count classified reviews
        assert result.overall_counts["glitches"] == 1
        assert result.overall_counts["ui_ux"] == 1
        # Other themes should not be present
        assert "payments_statements" not in result.overall_counts

    def test_aggregate_top_themes_sorting(self, sample_reviews, weekly_dir_with_files):
        """Test that top themes are sorted by count descending."""
        classifications = [
            ReviewClassification(
                review_id="review-1",
                theme_id="glitches",
                theme_name="Slow, Glitches",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-2",
                theme_id="glitches",
                theme_name="Slow, Glitches",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-3",
                theme_id="glitches",
                theme_name="Slow, Glitches",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-4",
                theme_id="ui_ux",
                theme_name="UI/UX",
                reason="Test",
            ),
            ReviewClassification(
                review_id="review-5",
                theme_id="ui_ux",
                theme_name="UI/UX",
                reason="Test",
            ),
        ]

        aggregator = WeeklyThemeAggregator()
        result = aggregator.aggregate(sample_reviews, classifications, weekly_dir_with_files)

        # Top theme should be glitches with count 3
        assert result.top_themes[0] == ("glitches", 3)
        assert result.top_themes[1] == ("ui_ux", 2)

    def test_save_aggregation(self, sample_reviews, weekly_dir_with_files, tmp_path):
        """Test saving aggregation result to JSON file."""
        classifications = [
            ReviewClassification(
                review_id="review-1",
                theme_id="glitches",
                theme_name="Slow, Glitches",
                reason="Test",
            ),
        ]

        aggregator = WeeklyThemeAggregator()
        result = aggregator.aggregate(sample_reviews[:1], classifications, weekly_dir_with_files)

        output_path = tmp_path / "test_aggregation.json"
        aggregator.save_aggregation(result, output_path)

        # Verify file was created and contains valid JSON
        assert output_path.exists()
        with output_path.open("r") as f:
            data = json.load(f)

        assert "weekly_counts" in data
        assert "overall_counts" in data
        assert "top_themes" in data
        assert isinstance(data["weekly_counts"], list)
        assert isinstance(data["overall_counts"], dict)
        assert isinstance(data["top_themes"], list)


# ============================================================================
# Integration Tests
# ============================================================================


class TestLayer2Integration:
    """Test full Layer 2 pipeline integration."""

    @patch("src.layer2.theme_classifier.genai")
    def test_full_layer2_pipeline(self, mock_genai, sample_reviews, weekly_dir_with_files, tmp_path):
        """Test complete Layer 2 pipeline: classification + aggregation."""
        # Setup mock Gemini
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = json.dumps([
            {
                "review_id": "review-1",
                "chosen_theme": "glitches",
                "short_reason": "Order delays mentioned",
            },
            {
                "review_id": "review-2",
                "chosen_theme": "ui_ux",
                "short_reason": "UI mentioned",
            },
            {
                "review_id": "review-3",
                "chosen_theme": "payments_statements",
                "short_reason": "Profit discrepancy",
            },
            {
                "review_id": "review-4",
                "chosen_theme": "customer_support",
                "short_reason": "Support issue",
            },
            {
                "review_id": "review-5",
                "chosen_theme": "slow",
                "short_reason": "Performance issue",
            },
        ])
        mock_model.generate_content.return_value = mock_response

        mock_genai.configure = Mock()
        mock_genai.GenerativeModel.return_value = mock_model

        # Step 1: Classify reviews
        classifier = GeminiThemeClassifier(api_key="test-key")
        classifications = classifier.classify_reviews(sample_reviews)

        assert len(classifications) == 5
        assert all(c.review_id.startswith("review-") for c in classifications)

        # Step 2: Aggregate by week
        aggregator = WeeklyThemeAggregator()
        result = aggregator.aggregate(sample_reviews, classifications, weekly_dir_with_files)

        # Verify aggregation
        assert len(result.weekly_counts) == 3
        assert sum(result.overall_counts.values()) == 5

        # Step 3: Save aggregation
        output_path = tmp_path / "integration_test_aggregation.json"
        aggregator.save_aggregation(result, output_path)
        assert output_path.exists()

        # Verify saved data
        with output_path.open("r") as f:
            saved_data = json.load(f)

        assert len(saved_data["weekly_counts"]) == 3
        assert len(saved_data["overall_counts"]) == 5
        assert len(saved_data["top_themes"]) == 5

    @patch("src.layer2.theme_classifier.genai")
    def test_layer2_with_empty_reviews(self, mock_genai, tmp_path):
        """Test Layer 2 with empty review list."""
        mock_genai.configure = Mock()
        mock_genai.GenerativeModel = Mock()

        classifier = GeminiThemeClassifier(api_key="test-key")
        classifications = classifier.classify_reviews([])

        assert classifications == []

        aggregator = WeeklyThemeAggregator()
        weekly_dir = tmp_path / "weekly"
        weekly_dir.mkdir()
        result = aggregator.aggregate([], [], weekly_dir)

        assert len(result.weekly_counts) == 0
        assert len(result.overall_counts) == 0
        assert len(result.top_themes) == 0

