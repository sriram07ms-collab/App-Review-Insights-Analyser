"""Gemini-powered theme labeling for clustered reviews."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Mapping

from google import generativeai as genai

from ..layer1.validator import ReviewModel
from .clustering import ClusterSummary

PROMPT_TEMPLATE = """You are an insights analyst. Summarize the core theme expressed in the user feedback below.
Speak in concise business language (max 25 words per field).
Return valid JSON with fields:
- theme_name: 1-3 words
- summary: one sentence describing the sentiment and issue
- action_hint: short suggestion (<=12 words)
- supporting_quotes: array of up to {quote_count} short quotes directly copied from the reviews (<=18 words each)

Reviews:
{review_bullets}
"""


@dataclass(slots=True)
class ThemeLabel:
    cluster_id: int
    theme_name: str
    summary: str
    action_hint: str
    supporting_quotes: List[str]
    strength: float


@dataclass(slots=True)
class ThemeLabelerConfig:
    model_name: str = "gemini-1.5-flash"
    quote_count: int = 5
    temperature: float = 0.2


class GeminiThemeLabeler:
    """Calls Gemini to generate concise theme metadata per cluster."""

    def __init__(
        self,
        api_key: str | None = None,
        config: ThemeLabelerConfig | None = None,
    ) -> None:
        self.config = config or ThemeLabelerConfig()
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.config.model_name)

    def label_cluster(
        self,
        cluster: ClusterSummary,
        review_lookup: Mapping[str, ReviewModel],
    ) -> ThemeLabel:
        reviews = [review_lookup[rid] for rid in cluster.review_ids if rid in review_lookup]
        bullets = self._build_review_bullets(reviews)
        prompt = PROMPT_TEMPLATE.format(quote_count=self.config.quote_count, review_bullets=bullets)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=self.config.temperature,
                response_mime_type="application/json",
            ),
        )
        data = self._parse_response(response.text or "")
        return ThemeLabel(
            cluster_id=cluster.label,
            theme_name=data.get("theme_name", "Unnamed Theme"),
            summary=data.get("summary", ""),
            action_hint=data.get("action_hint", ""),
            supporting_quotes=data.get("supporting_quotes", []),
            strength=cluster.strength,
        )

    @staticmethod
    def _build_review_bullets(reviews: List[ReviewModel]) -> str:
        if not reviews:
            return "- (no reviews provided)"
        selected = reviews[:5]
        return "\n".join(f"- {review.text[:280]}" for review in selected)

    @staticmethod
    def _parse_response(payload: str) -> Dict:
        cleaned = payload.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.split("\n", 1)[-1]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "theme_name": cleaned[:50],
                "summary": cleaned[:150],
                "action_hint": "",
                "supporting_quotes": [],
            }



