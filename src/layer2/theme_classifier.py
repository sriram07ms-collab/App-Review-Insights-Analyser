"""LLM-based review classification into fixed themes."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Mapping

from google import generativeai as genai

from ..layer1.validator import ReviewModel
from .theme_config import DEFAULT_THEME_ID, FIXED_THEMES, get_theme_by_id, get_all_theme_ids
from .theme_discovery import DiscoveredTheme

LOGGER = logging.getLogger(__name__)

CLASSIFICATION_PROMPT_TEMPLATE = """You are tagging reviews into at most {max_themes} themes.

Allowed themes:
{themes_list}

For each review, output:
- review_id: the exact review_id from the input
- chosen_theme: exactly one theme ID from the list above (must be one of: {theme_ids})
- short_reason: 1 sentence explaining why this theme was chosen (no PII, no personal information)

Return valid JSON array with one object per review. Format:
[
  {{"review_id": "...", "chosen_theme": "...", "short_reason": "..."}},
  {{"review_id": "...", "chosen_theme": "...", "short_reason": "..."}}
]

Reviews:
{reviews_batch}

Return only the JSON array, no additional text."""


@dataclass(slots=True)
class ReviewClassification:
    """Classification result for a single review."""

    review_id: str
    theme_id: str
    theme_name: str
    reason: str


@dataclass(slots=True)
class ThemeClassifierConfig:
    """Configuration for theme classifier."""

    model_name: str = "models/gemini-2.5-flash"  # Latest stable flash model for fast classification
    batch_size: int = 8  # Process 8 reviews per LLM call
    temperature: float = 0.1  # Low temperature for consistent classification
    max_retries: int = 2
    use_discovery: bool = True  # Enable theme discovery mode
    discovery_sample_size: int = 50  # Reviews to sample for discovery
    min_discovery_confidence: float = 0.6  # Minimum mapping confidence
    max_discovered_themes: int = 4  # Maximum discovered themes to use


class GeminiThemeClassifier:
    """Classifies reviews into fixed themes using Gemini LLM."""

    def __init__(
        self,
        api_key: str | None = None,
        config: ThemeClassifierConfig | None = None,
        discovered_themes: List[DiscoveredTheme] | None = None,
    ) -> None:
        self.config = config or ThemeClassifierConfig()
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        genai.configure(api_key=api_key)
        # Use model from env or config, with fallback to stable models
        configured_name = os.getenv("GEMINI_MODEL_NAME", self.config.model_name)
        candidates = [
            configured_name,
            self.config.model_name,
            "models/gemini-2.5-flash",  # Latest stable flash - best for classification
            "models/gemini-2.0-flash",  # Stable flash fallback
            "models/gemini-2.5-pro",    # Pro version if flash unavailable
        ]
        for candidate in candidates:
            try:
                self.model = genai.GenerativeModel(candidate)
                LOGGER.info("Using Gemini model: %s", candidate)
                break
            except Exception as exc:
                LOGGER.debug("Model %s failed: %s", candidate, exc)
                continue
        else:
            raise RuntimeError(f"Could not initialize any Gemini model. Tried candidates: {candidates}")
        
        # Handle discovered themes
        self.discovered_themes = discovered_themes or []
        self.use_discovered = (
            self.config.use_discovery
            and self.discovered_themes
            and len(self.discovered_themes) > 0
        )
        
        if self.use_discovered:
            # Limit to max_discovered_themes
            self.discovered_themes = self.discovered_themes[:self.config.max_discovered_themes]
            LOGGER.info(
                "Using %s discovered themes for classification",
                len(self.discovered_themes)
            )
            self.themes_list = self._build_discovered_themes_list()
            self.theme_ids_str = ", ".join(t.theme_id for t in self.discovered_themes)
        else:
            LOGGER.info("Using predefined themes for classification")
            self.themes_list = self._build_themes_list()
            self.theme_ids_str = ", ".join(get_all_theme_ids())

    def _build_themes_list(self) -> str:
        """Build formatted themes list for prompt (predefined themes)."""
        lines = []
        for idx, (theme_id, theme) in enumerate(FIXED_THEMES.items(), start=1):
            lines.append(f"{idx}. {theme.name} ({theme_id}) – {theme.description}")
        return "\n".join(lines)

    def _build_discovered_themes_list(self) -> str:
        """Build formatted themes list for prompt (discovered themes)."""
        lines = []
        for idx, theme in enumerate(self.discovered_themes, start=1):
            keywords_str = ", ".join(theme.keywords[:3]) if theme.keywords else "N/A"
            lines.append(
                f"{idx}. {theme.theme_name} ({theme.theme_id}) – {theme.description} "
                f"[Keywords: {keywords_str}]"
            )
        return "\n".join(lines)

    def classify_reviews(
        self,
        reviews: List[ReviewModel],
    ) -> List[ReviewClassification]:
        """Classify a list of reviews into fixed themes."""
        if not reviews:
            return []

        classifications: List[ReviewClassification] = []
        batches = [
            reviews[i : i + self.config.batch_size]
            for i in range(0, len(reviews), self.config.batch_size)
        ]

        for batch_idx, batch in enumerate(batches, start=1):
            LOGGER.debug("Classifying batch %s/%s (%s reviews)", batch_idx, len(batches), len(batch))
            batch_classifications = self._classify_batch(batch)
            classifications.extend(batch_classifications)

        return classifications

    def _classify_batch(self, reviews: List[ReviewModel]) -> List[ReviewClassification]:
        """Classify a single batch of reviews."""
        reviews_text = self._format_reviews_for_prompt(reviews)
        max_themes = (
            min(len(self.discovered_themes), self.config.max_discovered_themes)
            if self.use_discovered
            else len(FIXED_THEMES)
        )
        prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
            max_themes=max_themes,
            themes_list=self.themes_list,
            theme_ids=self.theme_ids_str,
            reviews_batch=reviews_text,
        )

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=self.config.temperature,
                        response_mime_type="application/json",
                    ),
                )
                parsed = self._parse_response(response.text or "")
                return self._build_classifications(parsed, reviews)
            except Exception as exc:
                if attempt < self.config.max_retries:
                    LOGGER.warning("Classification attempt %s failed: %s. Retrying...", attempt + 1, exc)
                else:
                    LOGGER.error("Classification failed after %s attempts: %s", self.config.max_retries + 1, exc)
                    return self._fallback_classifications(reviews)

    def _format_reviews_for_prompt(self, reviews: List[ReviewModel]) -> str:
        """Format reviews as text for prompt."""
        lines = []
        for review in reviews:
            # Truncate text to avoid token limits
            text_preview = review.text[:400] + ("..." if len(review.text) > 400 else "")
            lines.append(f"review_id: {review.review_id}\ntitle: {review.title}\ntext: {text_preview}")
        return "\n\n---\n\n".join(lines)

    def _parse_response(self, payload: str) -> List[Dict]:
        """Parse LLM JSON response."""
        cleaned = payload.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned

        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "reviews" in data:
                return data["reviews"]
            return [data]  # Single object wrapped
        except json.JSONDecodeError as exc:
            LOGGER.warning("Failed to parse JSON response: %s. Raw: %s", exc, cleaned[:200])
            return []

    def _build_classifications(
        self,
        parsed: List[Dict],
        original_reviews: List[ReviewModel],
    ) -> List[ReviewClassification]:
        """Build ReviewClassification objects from parsed LLM response."""
        review_lookup = {r.review_id: r for r in original_reviews}
        classifications: List[ReviewClassification] = []

        for item in parsed:
            review_id = item.get("review_id", "")
            if not review_id or review_id not in review_lookup:
                LOGGER.warning("Skipping classification with invalid review_id: %s", review_id)
                continue

            theme_id_raw = item.get("chosen_theme", "").lower().strip()
            theme_id = self._validate_theme_id(theme_id_raw)
            
            # Get theme definition (discovered or predefined)
            if self.use_discovered:
                discovered = next(
                    (t for t in self.discovered_themes if t.theme_id.lower() == theme_id),
                    None
                )
                if discovered:
                    # Use discovered theme if not mapped, otherwise use predefined
                    if discovered.mapped_to_predefined:
                        theme = get_theme_by_id(discovered.mapped_to_predefined)
                    else:
                        # Create a temporary theme definition from discovered theme
                        from .theme_config import ThemeDefinition
                        theme = ThemeDefinition(
                            id=discovered.theme_id,
                            name=discovered.theme_name,
                            description=discovered.description
                        )
                else:
                    theme = get_theme_by_id(theme_id)
            else:
                theme = get_theme_by_id(theme_id)
            
            reason = item.get("short_reason", "No reason provided")

            classifications.append(
                ReviewClassification(
                    review_id=review_id,
                    theme_id=theme_id,
                    theme_name=theme.name,
                    reason=reason,
                )
            )

        # Handle reviews that weren't classified
        classified_ids = {c.review_id for c in classifications}
        for review in original_reviews:
            if review.review_id not in classified_ids:
                LOGGER.warning("Review %s not classified; using default theme", review.review_id)
                default_theme = get_theme_by_id(DEFAULT_THEME_ID)
                classifications.append(
                    ReviewClassification(
                        review_id=review.review_id,
                        theme_id=DEFAULT_THEME_ID,
                        theme_name=default_theme.name,
                        reason="Default assignment (classification failed)",
                    )
                )

        return classifications

    def _validate_theme_id(self, theme_id: str) -> str:
        """Validate and normalize theme ID, with fallback to default."""
        theme_id = theme_id.lower().strip()
        
        if self.use_discovered:
            # Check if it's a discovered theme
            discovered = next(
                (t for t in self.discovered_themes if t.theme_id.lower() == theme_id),
                None
            )
            if discovered:
                # If mapped to predefined, return predefined theme_id
                if discovered.mapped_to_predefined:
                    LOGGER.debug(
                        "Mapped discovered theme '%s' to predefined '%s'",
                        theme_id, discovered.mapped_to_predefined
                    )
                    return discovered.mapped_to_predefined
                # Use discovered theme_id even if unmapped (it's a valid discovered theme)
                LOGGER.debug(
                    "Using discovered theme '%s' (unmapped, confidence: %.2f)",
                    theme_id, discovered.confidence
                )
                return theme_id
            
            # Try fuzzy matching with discovered themes
            for discovered_theme in self.discovered_themes:
                if theme_id in discovered_theme.theme_id or discovered_theme.theme_id in theme_id:
                    if discovered_theme.mapped_to_predefined:
                        return discovered_theme.mapped_to_predefined
                    # Return discovered theme_id even if unmapped
                    return discovered_theme.theme_id
        
        # Fallback to predefined themes
        if theme_id in FIXED_THEMES:
            return theme_id

        # Try fuzzy matching with predefined themes
        for valid_id in FIXED_THEMES.keys():
            if valid_id in theme_id or theme_id in valid_id:
                LOGGER.debug("Fuzzy matched theme_id '%s' to '%s'", theme_id, valid_id)
                return valid_id

        LOGGER.warning("Invalid theme_id '%s'; using default '%s'", theme_id, DEFAULT_THEME_ID)
        return DEFAULT_THEME_ID

    def _fallback_classifications(self, reviews: List[ReviewModel]) -> List[ReviewClassification]:
        """Generate fallback classifications when LLM fails."""
        default_theme = get_theme_by_id(DEFAULT_THEME_ID)
        return [
            ReviewClassification(
                review_id=review.review_id,
                theme_id=DEFAULT_THEME_ID,
                theme_name=default_theme.name,
                reason="Fallback assignment (LLM classification failed)",
            )
            for review in reviews
        ]

