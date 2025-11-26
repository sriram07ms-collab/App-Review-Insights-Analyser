"""PII detection and redaction utilities for review text."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

try:  # Optional dependency
    from presidio_analyzer import AnalyzerEngine  # type: ignore
except ImportError:  # pragma: no cover - optional
    AnalyzerEngine = None  # type: ignore

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?:\\+?\\d{1,3}[-.\\s]?)?(?:\\(\\d{2,4}\\)|\\d{3,5})[-.\\s]?\\d{3}[-.\\s]?\\d{3,4}")
URL_PATTERN = re.compile(r"https?://\\S+|www\\.\\S+", re.IGNORECASE)

LOGGER = logging.getLogger(__name__)

@dataclass(slots=True)
class PIIFinding:
    """Represents a single detected PII span."""

    text: str
    start: int
    end: int
    label: str


class PIIDetector:
    """Combines regex-based and optional Presidio detection."""

    def __init__(self, enable_presidio: bool = False) -> None:
        self.enable_presidio = enable_presidio and AnalyzerEngine is not None
        self._presidio_engine = AnalyzerEngine() if self.enable_presidio else None

    def detect(self, text: str) -> List[PIIFinding]:
        findings = self._detect_with_regex(text)
        if self._presidio_engine:
            presidio_entities = self._presidio_engine.analyze(text=text, entities=[], language="en")
            for entity in presidio_entities:
                findings.append(
                    PIIFinding(text=text[entity.start : entity.end], start=entity.start, end=entity.end, label=entity.entity_type)
                )
        findings = sorted(findings, key=lambda item: item.start)
        if findings:
            labels = ", ".join(sorted({finding.label for finding in findings}))
            LOGGER.debug("Detected %s PII spans (%s)", len(findings), labels)
        return findings

    def redact(self, text: str, mask: str = "[REDACTED]") -> str:
        findings = self.detect(text)
        if not findings:
            return text

        redacted = []
        cursor = 0
        for finding in findings:
            if finding.start < cursor:
                continue
            redacted.append(text[cursor:finding.start])
            redacted.append(mask)
            cursor = finding.end
        redacted.append(text[cursor:])
        return "".join(redacted)

    @staticmethod
    def _detect_with_regex(text: str) -> List[PIIFinding]:
        findings: List[PIIFinding] = []
        for pattern, label in (
            (EMAIL_PATTERN, "EMAIL"),
            (PHONE_PATTERN, "PHONE"),
            (URL_PATTERN, "URL"),
        ):
            for match in pattern.finditer(text):
                findings.append(PIIFinding(text=match.group(), start=match.start(), end=match.end(), label=label))
        return findings


def clean_reviews_texts(texts: Iterable[str], detector: PIIDetector | None = None) -> List[str]:
    """Redact PII from a collection of review texts."""
    detector = detector or PIIDetector(enable_presidio=False)
    return [detector.redact(text) for text in texts]


