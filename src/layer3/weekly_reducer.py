"""
Reduce-stage prompt to produce the weekly pulse note.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from typing import Dict, List, Sequence

from google import generativeai as genai

from .config import Layer3Config
from .models import ThemeInsight, WeeklyPulseNote

LOGGER = logging.getLogger(__name__)

REDUCE_PROMPT_TEMPLATE = """You are creating a weekly product pulse for internal stakeholders (Product/Growth, Support, Leadership).

Input:
- Time window: {week_start} to {week_end}
- Candidate themes with key points and quotes:
{themes_blob}

Constraints:
- Select the Top 3 themes that matter most based on frequency & impact.
- Produce:
  1) A short title for the pulse.
  2) A one-paragraph overview (max 60 words).
  3) A bullet list of the Top 3 themes:
     - For each, 1 sentence with sentiment + key insight.
  4) 3 short quotes (1–2 lines each), clearly marked with theme.
  5) 3 specific action ideas (bullets), each linked to a theme.

Style & limits:
- Total length: ≤250 words.
- Use clear bullets and sub-bullets where needed.
- Executive-friendly, neutral tone. Do not overpraise.
- No names, emails, IDs, or any PII.

Output strictly in this JSON structure:
{{
  "title": "...",
  "overview": "...",
  "themes": [
    {{"name": "...", "summary": "..."}},
    ...
  ],
  "quotes": ["...", "...", "..."],
  "actions": ["...", "...", "..."]
}}
"""

COMPRESS_PROMPT_TEMPLATE = """Compress this note to at most {max_words} words, preserving:
- 3 themes, 3 quotes, 3 actions.
- Bullet-based, scannable structure.
- No PII.

{note_payload}
"""


class GeminiWeeklyReducer:
    """Runs the reduce-stage prompt and enforces word limits."""

    def __init__(self, config: Layer3Config, api_key: str | None = None, model_name: str | None = None) -> None:
        self.config = config
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set for Layer 3 reducer.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name or config.reduce_model_name)

    def build_weekly_note(
        self,
        week_start: str,
        week_end: str,
        insights: List[ThemeInsight],
    ) -> WeeklyPulseNote | None:
        themes_blob = json.dumps([insight.as_dict() for insight in insights], ensure_ascii=False, indent=2)
        prompt = REDUCE_PROMPT_TEMPLATE.format(week_start=week_start, week_end=week_end, themes_blob=themes_blob)
        note_dict = self._invoke_model(prompt)
        if not note_dict:
            return None

        word_count = calculate_word_count(note_dict)
        if word_count > self.config.max_words:
            compressed = self._compress_note(note_dict)
            if compressed:
                note_dict = compressed
                word_count = calculate_word_count(note_dict)

        return WeeklyPulseNote(
            week_start=week_start,
            week_end=week_end,
            title=note_dict.get("title", "").strip(),
            overview=note_dict.get("overview", "").strip(),
            themes=note_dict.get("themes", []),
            quotes=note_dict.get("quotes", []),
            actions=note_dict.get("actions", []),
            word_count=word_count,
        )

    def _compress_note(self, note_dict: Dict) -> Dict | None:
        prompt = COMPRESS_PROMPT_TEMPLATE.format(max_words=self.config.max_words, note_payload=json.dumps(note_dict, ensure_ascii=False))
        return self._invoke_model(prompt)

    def _invoke_model(self, prompt: str) -> Dict | None:
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(response_mime_type="application/json"),
            )
        except Exception as exc:
            LOGGER.error("Layer 3 reducer prompt failed: %s", exc)
            return None

        payload = self._extract_json_payload(response)
        if payload is None:
            LOGGER.error(
                "Reducer JSON parse error: unable to decode response snippet=%s",
                getattr(response, "text", "")[:200],
            )
            return None
        if not isinstance(payload, dict):
            LOGGER.warning("Unexpected reducer payload type: %s", type(payload))
            return None
        return payload

    def _extract_json_payload(self, response) -> Dict | None:
        for candidate_text in self._iter_candidate_texts(response):
            parsed = self._try_parse_json(candidate_text)
            if parsed is not None:
                return parsed
        return None

    def _iter_candidate_texts(self, response) -> Sequence[str]:
        texts: List[str] = []
        text = (getattr(response, "text", "") or "").strip()
        if text:
            texts.append(text)
        for candidate in getattr(response, "candidates", []) or []:
            parts = getattr(getattr(candidate, "content", None), "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", "") or ""
                if part_text.strip():
                    texts.append(part_text.strip())
        return texts

    def _try_parse_json(self, blob: str) -> Dict | None:
        candidate = blob.strip()
        if not candidate:
            return None
        if candidate.startswith("```"):
            lines = [
                line
                for line in candidate.splitlines()
                if not line.strip().startswith("```")
            ]
            candidate = "\n".join(lines).strip()
        if not candidate.startswith("{"):
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = candidate[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None


def calculate_word_count(note_dict: Dict) -> int:
    """Count total words across overview, themes, quotes, and actions."""
    sections: List[str] = []
    sections.append(note_dict.get("overview", ""))
    for theme in note_dict.get("themes", []):
        sections.append(theme.get("summary", ""))
    sections.extend(note_dict.get("quotes", []))
    sections.extend(note_dict.get("actions", []))

    words = []
    for text in sections:
        words.extend(text.strip().split())
    return len(words)

