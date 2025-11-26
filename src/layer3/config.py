"""
Configuration helpers for Layer 3 (weekly pulse generation).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_int(var_name: str, default: int) -> int:
    """Read integer configuration from environment variables."""
    try:
        return int(os.getenv(var_name, default))
    except (TypeError, ValueError):
        return default


def _env_str(var_name: str, default: str) -> str:
    """Return default when env var is unset or blank."""
    value = os.getenv(var_name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_bool(var_name: str, default: bool) -> bool:
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Layer3Config:
    """Runtime configuration for Layer 3 summarization."""

    weekly_dir: Path = field(default_factory=lambda: Path("data/raw/weekly"))
    classifications_path: Path = field(default_factory=lambda: Path("data/processed/review_classifications.json"))
    output_dir: Path = field(default_factory=lambda: Path("data/processed/weekly_pulse"))

    chunk_size: int = field(default_factory=lambda: _env_int("LAYER3_CHUNK_SIZE", 20))
    max_key_points: int = field(default_factory=lambda: _env_int("LAYER3_MAX_KEY_POINTS", 5))
    max_quotes_per_theme: int = field(default_factory=lambda: _env_int("LAYER3_MAX_QUOTES_PER_THEME", 3))
    max_themes: int = field(default_factory=lambda: _env_int("LAYER3_MAX_THEMES", 3))
    min_reviews_per_week: int = field(default_factory=lambda: _env_int("LAYER3_MIN_REVIEWS", 3))
    max_words: int = field(default_factory=lambda: _env_int("LAYER3_MAX_WORDS", 250))

    map_model_name: str = field(default_factory=lambda: _env_str("LAYER3_MAP_MODEL_NAME", _env_str("GEMINI_MODEL_NAME", "models/gemini-2.5-flash")))
    reduce_model_name: str = field(default_factory=lambda: _env_str("LAYER3_REDUCE_MODEL_NAME", _env_str("GEMINI_MODEL_NAME", "models/gemini-2.5-flash")))
    enable_chunk_cache: bool = field(default_factory=lambda: _env_bool("LAYER3_ENABLE_CACHE", True))
    cache_path: Path = field(default_factory=lambda: Path(os.getenv("LAYER3_CACHE_PATH", "data/processed/layer3_chunk_cache.json")))

    def ensure_output_dir(self) -> Path:
        """Create the output directory if it does not exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir

