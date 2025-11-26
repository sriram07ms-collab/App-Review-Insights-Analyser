"""Schema validation utilities for raw Google Play reviews."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Sequence, Tuple

from pydantic import BaseModel, Field, ValidationError, field_validator

from .scraper import ReviewRecord

LOGGER = logging.getLogger(__name__)


class ReviewModel(BaseModel):
    """Pydantic representation of a validated review."""

    review_id: str = Field(min_length=1)
    title: str = Field(default="")
    text: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    date: datetime
    author: str | None = None
    product_tag: str | None = None

    @field_validator("title", "text", mode="before")
    @classmethod
    def _ensure_str(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("text")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value:
            raise ValueError("text cannot be empty")
        return value

    @field_validator("date", mode="before")
    @classmethod
    def _parse_date(cls, value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Invalid datetime string: {value}") from exc
        raise ValueError("Unsupported date format")

    def to_dict(self) -> dict:
        """Return a JSON-friendly dict."""
        payload = self.model_dump()
        payload["date"] = self.date.isoformat()
        return payload


@dataclass(slots=True)
class ValidationSummary:
    """Metadata about the validation pass."""

    total: int
    accepted: int
    rejected: int


def validate_reviews(reviews: Iterable[ReviewRecord]) -> Tuple[List[ReviewModel], ValidationSummary]:
    """
    Validate a batch of ReviewRecord instances.

    Args:
        reviews: iterable of ReviewRecord objects.

    Returns:
        (validated reviews, summary)
    """
    validated: List[ReviewModel] = []
    rejected = 0

    for record in reviews:
        try:
            model = ReviewModel(
                review_id=record.review_id,
                title=record.title or record.text[:60],
                text=record.text,
                rating=record.rating,
                date=record.date,
                author=record.author,
                product_tag=record.product_tag,
            )
            validated.append(model)
        except ValidationError as exc:
            rejected += 1
            LOGGER.warning("Dropping invalid review %s: %s", record.review_id, exc)

    summary = ValidationSummary(total=rejected + len(validated), accepted=len(validated), rejected=rejected)
    LOGGER.info("Validation summary: %s", summary)
    return validated, summary


def dump_validated_reviews(validated: Sequence[ReviewModel], output_path: str | None = None) -> List[dict]:
    """
    Convert validated models into dictionaries (and optionally write to disk).
    """
    serialised = [model.to_dict() for model in validated]
    if output_path:
        from pathlib import Path

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        import json

        with path.open("w", encoding="utf-8") as fh:
            json.dump(serialised, fh, ensure_ascii=False, indent=2)
        LOGGER.info("Wrote %s validated reviews to %s", len(serialised), path)
    return serialised



