"""LLM-based email draft generator for Layer 4."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict
from typing import Tuple

from google import generativeai as genai

from .config import Layer4Config
from .email_models import EmailDraft, WeeklyPulseNote
from .note_sanitizer import sanitize_note
from .pii_safety import contains_pii, mask_pii
from .prompt_templates import EMAIL_BODY_PROMPT, PII_SCRUB_PROMPT

LOGGER = logging.getLogger(__name__)


class EmailDraftGenerator:
    """Uses Gemini to draft weekly email bodies."""

    def __init__(self, config: Layer4Config, api_key: str | None = None) -> None:
        self.config = config
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Layer 4.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(config.email_model_name)

    def generate(
        self,
        note: WeeklyPulseNote,
    ) -> Tuple[str, str]:
        """Return (subject, body) text for the email."""
        sanitized_note = sanitize_note(note)
        note_json = json.dumps(asdict(sanitized_note), ensure_ascii=False, indent=2)
        prompt = EMAIL_BODY_PROMPT.format(
            weekly_note_json=note_json,
            product_name=self.config.product_name,
            week_start=sanitized_note.week_start,
            week_end=sanitized_note.week_end,
        )
        try:
            body = self._invoke_model(prompt)
            body = body.strip()
            if not body:
                raise RuntimeError("Empty email body returned from LLM.")
            body = self._scrub_pii(body, allow_llm=True)
        except RuntimeError as exc:
            LOGGER.error("Gemini email generation failed (%s); using fallback template.", exc)
            body = self._render_fallback_email(sanitized_note)
            body = self._scrub_pii(body, allow_llm=False)

        if len(body.split()) > 350:
            LOGGER.warning("Email body exceeds 350 words; truncating softly.")
            words = body.split()
            body = " ".join(words[:350])

        subject = self.config.subject_template.format(
            product=self.config.product_name,
            week_start=sanitized_note.week_start,
            week_end=sanitized_note.week_end,
            title=sanitized_note.title,
        )
        return subject.strip(), body

    def _invoke_model(self, prompt: str, retry: bool = True) -> str:
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=1024,
                ),
            )
        except Exception as exc:
            message = str(exc)
            if retry and ("429" in message or "quota" in message.lower()):
                delay = 35
                LOGGER.warning("Gemini quota hit; retrying after %ss.", delay)
                time.sleep(delay)
                return self._invoke_model(prompt, retry=False)
            raise RuntimeError(f"Gemini email generation failed: {exc}") from exc

        # Check finish_reason BEFORE accessing response.text to avoid exceptions
        finish_reason = None
        candidate = None
        candidates = getattr(response, "candidates", None)
        if candidates:
            candidate = candidates[0]
            finish_reason = getattr(candidate, "finish_reason", None)

        # Handle finish_reason=2 (safety block) before trying to access text
        if finish_reason == 2:
            if retry:
                LOGGER.warning("Gemini blocked output (finish_reason=2); retrying with safe reminder.")
                safe_prompt = (
                    prompt
                    + "\n\nReminder: respond with policy-compliant, non-sensitive business content only."
                )
                return self._invoke_model(safe_prompt, retry=False)
            # If retry already attempted, raise to trigger fallback
            raise RuntimeError("Gemini blocked output (finish_reason=2) after retry.")

        # Now safe to access response.text
        try:
            text = (getattr(response, "text", "") or "").strip()
            if text:
                return text
        except Exception as exc:
            # If accessing text still fails, treat as blocked
            if finish_reason == 2:
                raise RuntimeError("Gemini blocked output (finish_reason=2).") from exc
            raise RuntimeError(f"Failed to extract response text: {exc}") from exc

        raise RuntimeError(
            f"Gemini returned empty response (finish_reason={finish_reason})."
        )

    def _render_fallback_email(self, note: WeeklyPulseNote) -> str:
        """Deterministic plain-text email used if Gemini blocks output."""
        lines = [
            f"{self.config.product_name} Weekly Pulse | {note.week_start} – {note.week_end}",
            "",
            f"Title: {note.title}",
            f"Overview: {note.overview}",
            "",
            "Top Themes:",
        ]
        for theme in note.themes[:3]:
            lines.append(f"- {theme.get('name', 'Theme')}: {theme.get('summary', '')}")
        lines.append("")
        lines.append("Representative Quotes:")
        for quote in note.quotes[:3]:
            lines.append(f"- “{quote}”")
        lines.append("")
        lines.append("Action Ideas:")
        for action in note.actions[:3]:
            lines.append(f"- {action}")
        lines.append("")
        lines.append("Reply to this email if you need deeper dives or clarifications.")
        return "\n".join(line.rstrip() for line in lines if line is not None)

    def _scrub_pii(self, body: str, allow_llm: bool = True) -> str:
        if not body:
            return body

        masked = mask_pii(body)
        detected_after_mask = contains_pii(masked)
        if not detected_after_mask:
            return masked.strip()

        if not allow_llm:
            LOGGER.warning("PII detected after regex scrub but LLM scrub disabled; masking only.")
            return mask_pii(masked).strip()

        prompt = PII_SCRUB_PROMPT.format(email_body=masked)
        try:
            scrubbed = self._invoke_model(prompt)
            scrubbed = scrubbed.strip() or masked
        except Exception as exc:
            LOGGER.warning("PII scrub prompt failed: %s", exc)
            return masked.strip()

        if contains_pii(scrubbed):
            LOGGER.warning("PII still detected after LLM scrub; applying aggressive masking.")
            return mask_pii(scrubbed).strip()

        return scrubbed

