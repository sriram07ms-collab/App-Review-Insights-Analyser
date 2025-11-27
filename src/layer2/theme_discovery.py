"""LLM-based theme discovery from review samples."""

from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from google import generativeai as genai

from ..layer1.validator import ReviewModel

LOGGER = logging.getLogger(__name__)

THEME_DISCOVERY_PROMPT = """Analyze the following app reviews and identify exactly 4 distinct themes/categories.

Reviews sample:
{reviews_sample}

For each theme, provide:
- theme_id: short lowercase identifier (e.g., "app_crashes", "payment_delays", "ui_navigation")
- theme_name: human-readable name (2-4 words)
- description: 1-2 sentences explaining what this theme covers
- keywords: list of 3-5 keywords that indicate this theme

Return JSON:
{{
  "themes": [
    {{
      "theme_id": "...",
      "theme_name": "...",
      "description": "...",
      "keywords": ["...", "..."]
    }}
  ]
}}

Important constraints:
- Return exactly 4 themes (no more, no less)
- Themes must be distinct and non-overlapping
- Focus on the most common and impactful issues
- Prioritize themes that appear frequently in the reviews

Focus on:
- Distinct, non-overlapping themes
- Common issues/problems mentioned
- Feature requests or improvements
- User experience categories
- Technical issues vs. business logic issues

Return only the JSON object, no additional text."""


@dataclass(slots=True)
class DiscoveredTheme:
    """A theme discovered by LLM analysis."""

    theme_id: str
    theme_name: str
    description: str
    keywords: List[str]
    mapped_to_predefined: Optional[str] = None  # Predefined theme_id if mapped
    confidence: float = 0.0  # Mapping confidence score

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class ThemeDiscovery:
    """Discovers themes from review samples using LLM."""

    MAX_THEMES = 4  # Limit to top 4 themes

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set for theme discovery.")
        genai.configure(api_key=api_key)
        model_name = model_name or os.getenv("THEME_DISCOVERY_MODEL", "models/gemini-2.5-flash")
        self.model = genai.GenerativeModel(model_name)
        LOGGER.info("Initialized ThemeDiscovery with model: %s", model_name)

    def discover_themes(
        self,
        reviews: List[ReviewModel],
        sample_size: int = 50,
    ) -> List[DiscoveredTheme]:
        """
        Discover themes from a sample of reviews.

        Args:
            reviews: List of reviews to analyze
            sample_size: Number of reviews to sample for discovery

        Returns:
            List of discovered themes (max 4)
        """
        if not reviews:
            LOGGER.warning("No reviews provided for theme discovery")
            return []

        # Sample reviews (stratified by rating if possible)
        sampled = self._sample_reviews(reviews, sample_size)
        LOGGER.info("Sampled %s reviews for theme discovery (from %s total)", len(sampled), len(reviews))

        # Format reviews for prompt
        reviews_text = self._format_reviews(sampled)

        # Call LLM with discovery prompt
        prompt = THEME_DISCOVERY_PROMPT.format(reviews_sample=reviews_text)
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # Slightly higher for creativity
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            LOGGER.error("Theme discovery LLM call failed: %s", exc)
            return []

        # Parse and validate discovered themes
        discovered = self._parse_themes(response.text or "")
        if not discovered:
            LOGGER.warning("No themes discovered from LLM response")
            return []

        # Ensure exactly 4 themes (or fewer if LLM returns less)
        if len(discovered) > self.MAX_THEMES:
            LOGGER.warning(
                "LLM returned %s themes, limiting to top %s",
                len(discovered), self.MAX_THEMES
            )
            discovered = discovered[:self.MAX_THEMES]
        elif len(discovered) < self.MAX_THEMES:
            LOGGER.info(
                "LLM returned %s themes (requested %s)",
                len(discovered), self.MAX_THEMES
            )

        LOGGER.info("Discovered %s themes (max allowed: %s)", len(discovered), self.MAX_THEMES)
        return discovered

    def _sample_reviews(self, reviews: List[ReviewModel], sample_size: int) -> List[ReviewModel]:
        """Sample reviews, attempting to stratify by rating."""
        if len(reviews) <= sample_size:
            return reviews

        # Group by rating
        by_rating: dict[int, List[ReviewModel]] = {}
        for review in reviews:
            rating = review.rating
            if rating not in by_rating:
                by_rating[rating] = []
            by_rating[rating].append(review)

        # Sample proportionally from each rating
        sampled: List[ReviewModel] = []
        for rating in sorted(by_rating.keys()):
            rating_reviews = by_rating[rating]
            proportion = len(rating_reviews) / len(reviews)
            count = max(1, int(sample_size * proportion))
            count = min(count, len(rating_reviews))
            sampled.extend(random.sample(rating_reviews, count))

        # If we still need more, fill randomly
        if len(sampled) < sample_size:
            remaining = [r for r in reviews if r not in sampled]
            needed = sample_size - len(sampled)
            if remaining:
                sampled.extend(random.sample(remaining, min(needed, len(remaining))))

        return sampled[:sample_size]

    def _format_reviews(self, reviews: List[ReviewModel]) -> str:
        """Format reviews as text for the discovery prompt."""
        lines = []
        for idx, review in enumerate(reviews, start=1):
            # Truncate text to avoid token limits
            text_preview = review.text[:300] + ("..." if len(review.text) > 300 else "")
            lines.append(f"Review {idx} (Rating: {review.rating}/5):\n{text_preview}")
        return "\n\n".join(lines)

    def _parse_themes(self, payload: str) -> List[DiscoveredTheme]:
        """Parse LLM JSON response into DiscoveredTheme objects."""
        cleaned = payload.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            # Remove first line if it's just "json"
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[-1]

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            LOGGER.error("Failed to parse theme discovery JSON: %s. Raw: %s", exc, cleaned[:200])
            return []

        if not isinstance(data, dict):
            LOGGER.error("Theme discovery response is not a dict: %s", type(data))
            return []

        themes_list = data.get("themes", [])
        if not isinstance(themes_list, list):
            LOGGER.error("Themes field is not a list: %s", type(themes_list))
            return []

        discovered: List[DiscoveredTheme] = []
        for item in themes_list:
            if not isinstance(item, dict):
                LOGGER.warning("Skipping invalid theme item: %s", type(item))
                continue

            theme_id = item.get("theme_id", "").strip().lower()
            theme_name = item.get("theme_name", "").strip()
            description = item.get("description", "").strip()
            keywords = item.get("keywords", [])

            if not theme_id or not theme_name:
                LOGGER.warning("Skipping theme with missing theme_id or theme_name")
                continue

            # Normalize theme_id (replace spaces with underscores, remove special chars)
            theme_id = theme_id.replace(" ", "_").replace("-", "_")
            theme_id = "".join(c for c in theme_id if c.isalnum() or c == "_")
            if not theme_id:
                theme_id = f"theme_{len(discovered) + 1}"

            # Ensure keywords is a list
            if not isinstance(keywords, list):
                keywords = []

            discovered.append(
                DiscoveredTheme(
                    theme_id=theme_id,
                    theme_name=theme_name,
                    description=description,
                    keywords=keywords,
                )
            )

        return discovered

    def save_discovered_themes(self, themes: List[DiscoveredTheme], output_path: Path) -> None:
        """Save discovered themes for analysis."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "theme_count": len(themes),
            "themes": [theme.to_dict() for theme in themes],
        }
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        LOGGER.info("Saved %s discovered themes to %s", len(themes), output_path)

