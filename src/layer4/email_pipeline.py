"""Pipeline that turns Layer 3 notes into Layer 4 emails."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from .config import Layer4Config
from .draft_generator import EmailDraftGenerator
from .email_models import EmailDraft, WeeklyPulseNote
from .email_sender import EmailSender

LOGGER = logging.getLogger(__name__)


class WeeklyEmailPipeline:
    """Reads weekly pulse notes and sends emails."""

    def __init__(
        self,
        config: Layer4Config,
        draft_generator: EmailDraftGenerator | None = None,
        sender: EmailSender | None = None,
        pulses_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.draft_generator = draft_generator or EmailDraftGenerator(config)
        self.sender = sender or EmailSender(config)
        self.pulses_dir = pulses_dir or config.pulses_dir

    def run(
        self,
        notes: List[WeeklyPulseNote] | None = None,
        single_latest: bool = False,
    ) -> List[EmailDraft]:
        notes = notes or self._load_notes()
        if not notes:
            LOGGER.info("No weekly pulse notes found; skipping Layer 4.")
            return []

        if single_latest and notes:
            notes = [self._select_latest_note(notes)]
            LOGGER.info(
                "Single-email mode enabled; sending only week %s-%s",
                notes[0].week_start,
                notes[0].week_end,
            )

        drafts: List[EmailDraft] = []
        for note in notes:
            subject, body = self.draft_generator.generate(note)
            draft = EmailDraft(
                subject=subject,
                body=body,
                recipient=self.config.email_recipient,
                week_start=note.week_start,
                week_end=note.week_end,
                product_name=self.config.product_name,
            )
            drafts.append(draft)
            self.sender.send(draft)
        LOGGER.info("Layer 4 completed: drafted/sent %s emails.", len(drafts))
        return drafts

    def _load_notes(self) -> List[WeeklyPulseNote]:
        if not self.pulses_dir.exists():
            LOGGER.warning("Pulse directory %s does not exist.", self.pulses_dir)
            return []
        notes: List[WeeklyPulseNote] = []
        for json_file in sorted(self.pulses_dir.glob("pulse_*.json")):
            try:
                with json_file.open("r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                note = WeeklyPulseNote(
                    week_start=payload["week_start"],
                    week_end=payload["week_end"],
                    title=payload["title"],
                    overview=payload["overview"],
                    themes=payload.get("themes", []),
                    quotes=payload.get("quotes", []),
                    actions=payload.get("actions", []),
                )
                notes.append(note)
            except Exception as exc:
                LOGGER.warning("Failed to parse weekly pulse %s: %s", json_file, exc)
        return notes

    @staticmethod
    def _select_latest_note(notes: List[WeeklyPulseNote]) -> WeeklyPulseNote:
        from datetime import datetime

        def _parse(date_str: str) -> datetime:
            try:
                return datetime.fromisoformat(date_str)
            except ValueError:
                return datetime.min

        return max(notes, key=lambda note: _parse(note.week_end))

