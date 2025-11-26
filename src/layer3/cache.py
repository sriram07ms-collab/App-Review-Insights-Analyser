"""
Simple JSON-backed cache for Layer 3 chunk summaries.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from .models import ChunkSummary

LOGGER = logging.getLogger(__name__)


class ChunkSummaryCache:
    """Stores chunk summaries keyed by hash to avoid repeated LLM calls."""

    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self._store: Dict[str, Dict] = {}
        self._dirty = False
        self._load()

    def get(self, key: str) -> Optional[ChunkSummary]:
        payload = self._store.get(key)
        if not payload:
            return None
        return ChunkSummary(
            theme_id=payload["theme_id"],
            theme_name=payload["theme_name"],
            key_points=payload.get("key_points", []),
            candidate_quotes=payload.get("candidate_quotes", []),
        )

    def set(self, key: str, summary: ChunkSummary) -> None:
        self._store[key] = {
            "theme_id": summary.theme_id,
            "theme_name": summary.theme_name,
            "key_points": summary.key_points,
            "candidate_quotes": summary.candidate_quotes,
        }
        self._dirty = True

    def persist(self) -> None:
        if not self._dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("w", encoding="utf-8") as fh:
            json.dump(self._store, fh, ensure_ascii=False, indent=2)
        LOGGER.debug("Persisted Layer 3 chunk cache to %s", self.cache_path)
        self._dirty = False

    def _load(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            with self.cache_path.open("r", encoding="utf-8") as fh:
                self._store = json.load(fh)
        except Exception as exc:
            LOGGER.warning("Failed to load chunk cache %s: %s", self.cache_path, exc)
            self._store = {}

