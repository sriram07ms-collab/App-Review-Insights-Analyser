"""Maps discovered themes to predefined themes."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from .theme_config import FIXED_THEMES, ThemeDefinition
from .theme_discovery import DiscoveredTheme

LOGGER = logging.getLogger(__name__)


class ThemeMapper:
    """Maps discovered themes to predefined themes using multiple strategies."""

    def __init__(self, predefined_themes: Dict[str, ThemeDefinition]) -> None:
        self.predefined = predefined_themes
        # Build keyword indexes for faster matching
        self._build_keyword_indexes()

    def _build_keyword_indexes(self) -> None:
        """Build keyword indexes from predefined theme descriptions."""
        self.keyword_indexes: Dict[str, List[str]] = {}
        for theme_id, theme in self.predefined.items():
            # Extract keywords from description and name
            text = f"{theme.name} {theme.description}".lower()
            # Simple keyword extraction (words of 3+ characters)
            words = re.findall(r"\b\w{3,}\b", text)
            # Remove common stop words
            stop_words = {
                "the", "and", "for", "are", "but", "not", "you", "all", "can", "her", "was",
                "one", "our", "out", "day", "get", "has", "him", "his", "how", "its", "may",
                "new", "now", "old", "see", "two", "way", "who", "boy", "did", "she", "use",
            }
            keywords = [w for w in words if w not in stop_words]
            # Take top 10 most relevant keywords
            self.keyword_indexes[theme_id] = keywords[:10]

    def map_theme(self, discovered: DiscoveredTheme) -> Tuple[Optional[str], float]:
        """
        Map discovered theme to predefined theme.

        Args:
            discovered: Discovered theme to map

        Returns:
            Tuple of (predefined_theme_id, confidence_score) or (None, 0.0)
        """
        # Strategy 1: Keyword matching (highest priority)
        keyword_match = self._match_by_keywords(discovered)
        if keyword_match and keyword_match[1] > 0.7:
            LOGGER.debug(
                "Mapped '%s' to '%s' via keywords (confidence: %.2f)",
                discovered.theme_id, keyword_match[0], keyword_match[1]
            )
            return keyword_match

        # Strategy 2: Description similarity
        desc_match = self._match_by_description(discovered)
        if desc_match and desc_match[1] > 0.6:
            LOGGER.debug(
                "Mapped '%s' to '%s' via description (confidence: %.2f)",
                discovered.theme_id, desc_match[0], desc_match[1]
            )
            return desc_match

        # Strategy 3: Fuzzy string matching on theme names
        name_match = self._match_by_name_fuzzy(discovered)
        if name_match and name_match[1] > 0.5:
            LOGGER.debug(
                "Mapped '%s' to '%s' via name fuzzy match (confidence: %.2f)",
                discovered.theme_id, name_match[0], name_match[1]
            )
            return name_match

        LOGGER.debug("No mapping found for discovered theme '%s'", discovered.theme_id)
        return None, 0.0

    def _match_by_keywords(self, discovered: DiscoveredTheme) -> Tuple[Optional[str], float]:
        """Match discovered theme to predefined theme using keywords."""
        best_match: Optional[str] = None
        best_score = 0.0

        discovered_keywords = [kw.lower() for kw in discovered.keywords]
        discovered_text = f"{discovered.theme_name} {discovered.description}".lower()
        discovered_words = set(re.findall(r"\b\w{3,}\b", discovered_text))
        discovered_words.update(discovered_keywords)

        for theme_id, theme in self.predefined.items():
            # Count keyword overlaps
            predefined_keywords = set(self.keyword_indexes.get(theme_id, []))
            overlap = len(discovered_words.intersection(predefined_keywords))
            if overlap == 0:
                continue

            # Calculate confidence score (0.0 to 1.0)
            # Based on overlap ratio and keyword importance
            max_possible = max(len(discovered_words), len(predefined_keywords))
            score = overlap / max_possible if max_possible > 0 else 0.0

            # Boost score if discovered keywords directly match
            keyword_boost = sum(1 for kw in discovered_keywords if kw in predefined_keywords)
            if keyword_boost > 0:
                score = min(1.0, score + (keyword_boost * 0.1))

            if score > best_score:
                best_score = score
                best_match = theme_id

        return best_match, best_score

    def _match_by_description(self, discovered: DiscoveredTheme) -> Tuple[Optional[str], float]:
        """Match discovered theme to predefined theme using description similarity."""
        best_match: Optional[str] = None
        best_score = 0.0

        discovered_text = f"{discovered.theme_name} {discovered.description}".lower()
        discovered_words = set(re.findall(r"\b\w{3,}\b", discovered_text))

        for theme_id, theme in self.predefined.items():
            predefined_text = f"{theme.name} {theme.description}".lower()
            predefined_words = set(re.findall(r"\b\w{3,}\b", predefined_text))

            # Calculate Jaccard similarity
            intersection = len(discovered_words.intersection(predefined_words))
            union = len(discovered_words.union(predefined_words))
            score = intersection / union if union > 0 else 0.0

            if score > best_score:
                best_score = score
                best_match = theme_id

        return best_match, best_score

    def _match_by_name_fuzzy(self, discovered: DiscoveredTheme) -> Tuple[Optional[str], float]:
        """Match discovered theme to predefined theme using fuzzy name matching."""
        best_match: Optional[str] = None
        best_score = 0.0

        discovered_name = discovered.theme_name.lower()
        discovered_words = set(discovered_name.split())

        for theme_id, theme in self.predefined.items():
            predefined_name = theme.name.lower()
            predefined_words = set(predefined_name.split())

            # Check for exact word matches
            word_overlap = len(discovered_words.intersection(predefined_words))
            if word_overlap == 0:
                continue

            # Calculate score based on word overlap
            max_words = max(len(discovered_words), len(predefined_words))
            score = word_overlap / max_words if max_words > 0 else 0.0

            # Check for substring matches (e.g., "ui_ux" contains "ui")
            if any(word in predefined_name for word in discovered_words):
                score = min(1.0, score + 0.2)
            if any(word in discovered_name for word in predefined_words):
                score = min(1.0, score + 0.2)

            if score > best_score:
                best_score = score
                best_match = theme_id

        return best_match, best_score

    def map_all_themes(self, discovered_themes: List[DiscoveredTheme]) -> List[DiscoveredTheme]:
        """
        Map all discovered themes to predefined themes.

        Args:
            discovered_themes: List of discovered themes

        Returns:
            List of discovered themes with mapping information populated
        """
        for theme in discovered_themes:
            mapped_id, confidence = self.map_theme(theme)
            theme.mapped_to_predefined = mapped_id
            theme.confidence = confidence

        return discovered_themes

