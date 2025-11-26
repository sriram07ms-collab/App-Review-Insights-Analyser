"""
Map-stage summarizer that processes theme chunks via Gemini LLM.
"""

from __future__ import annotations

import json
import logging
import os
import hashlib
from typing import Dict, List

from google import generativeai as genai

from .cache import ChunkSummaryCache
from .config import Layer3Config
from .models import ChunkSummary, ThemeChunk, ThemeInsight

LOGGER = logging.getLogger(__name__)

MAP_PROMPT_TEMPLATE = """You are summarizing feedback about Slow, Glitches, UI/UX, Payments/Statements, customer support, slow.

Theme: {theme_name}
Reviews (already cleaned, no direct PII):
{reviews_block}

Tasks:
1. Extract 3-5 key points about this theme in a neutral, factual tone.
2. Identify up to 3 short, vivid quotes that capture the sentiment.
   - Do NOT include names, usernames, emails, or IDs.
   - If a quote contains PII, rewrite it to keep meaning but remove the PII.
3. Return JSON:
{{
  "theme": "{theme_name}",
  "key_points": ["...", "..."],
  "candidate_quotes": ["...", "...", "..."]
}}

Keep everything concise. Avoid marketing fluff. Return only JSON."""


class GeminiTopicSummarizer:
    """Runs map-stage prompts per theme chunk."""

    def __init__(self, config: Layer3Config, api_key: str | None = None, model_name: str | None = None) -> None:
        self.config = config
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set for Layer 3 summarizer.")
        genai.configure(api_key=api_key)
        model_to_use = model_name or config.map_model_name
        self.model = genai.GenerativeModel(model_to_use)
        self.cache = ChunkSummaryCache(config.cache_path) if config.enable_chunk_cache else None

    def summarize_chunks(self, chunks: List[ThemeChunk]) -> Dict[str, ThemeInsight]:
        """Summarize each chunk and aggregate per theme."""
        aggregated: Dict[str, ThemeInsight] = {}

        for chunk in chunks:
            chunk_summary = self._summarize_chunk(chunk)
            if chunk_summary is None:
                continue
            if chunk.theme_id not in aggregated:
                aggregated[chunk.theme_id] = ThemeInsight(theme_id=chunk.theme_id, theme_name=chunk.theme_name)

            insight = aggregated[chunk.theme_id]
            insight.key_points.extend(chunk_summary.key_points)
            insight.quotes.extend(chunk_summary.candidate_quotes)

            # Trim to configured limits
            insight.key_points = dedupe_and_trim(insight.key_points, self.config.max_key_points)
            insight.quotes = dedupe_and_trim(insight.quotes, self.config.max_quotes_per_theme)

        if self.cache:
            self.cache.persist()
        return aggregated

    def _summarize_chunk(self, chunk: ThemeChunk) -> ChunkSummary | None:
        reviews_block = "\n\n".join(review.to_prompt_text() for review in chunk.reviews)
        cache_key = self._chunk_cache_key(chunk) if self.cache else None
        if cache_key and (cached := self.cache.get(cache_key)):
            LOGGER.debug("Chunk cache hit for theme %s (%s reviews).", chunk.theme_name, len(chunk.reviews))
            return cached
        prompt = MAP_PROMPT_TEMPLATE.format(theme_name=chunk.theme_name, reviews_block=reviews_block)
        try:
            response = self.model.generate_content(prompt, generation_config=genai.GenerationConfig(response_mime_type="application/json"))
        except Exception as exc:
            LOGGER.warning("Failed to summarize chunk for theme %s: %s", chunk.theme_id, exc)
            return None

        try:
            payload = json.loads(response.text or "{}")
        except json.JSONDecodeError as exc:
            LOGGER.warning("Invalid JSON from map-stage response: %s", exc)
            return None

        if not isinstance(payload, dict):
            LOGGER.warning("Unexpected map-stage payload type: %s", type(payload))
            return None

        key_points = [point.strip() for point in payload.get("key_points", []) if point]
        quotes = [quote.strip() for quote in payload.get("candidate_quotes", []) if quote]
        summary = ChunkSummary(theme_id=chunk.theme_id, theme_name=chunk.theme_name, key_points=key_points, candidate_quotes=quotes)
        if cache_key and self.cache and (key_points or quotes):
            self.cache.set(cache_key, summary)
        return summary

    def flush_cache(self) -> None:
        if self.cache:
            self.cache.persist()

    @staticmethod
    def _chunk_cache_key(chunk: ThemeChunk) -> str:
        material = "|".join(f"{review.review_id}:{review.text.strip()}" for review in chunk.reviews)
        raw = f"{chunk.theme_id}|{material}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dedupe_and_trim(items: List[str], max_items: int) -> List[str]:
    """Helper to enforce uniqueness and truncate lists deterministically."""
    seen = set()
    unique_items: List[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized:
            continue
        lowercase = normalized.lower()
        if lowercase in seen:
            continue
        seen.add(lowercase)
        unique_items.append(normalized)
        if len(unique_items) >= max_items:
            break
    return unique_items

