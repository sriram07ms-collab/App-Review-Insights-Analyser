"""Local embedding utilities backed by sentence-transformers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from ..layer1.validator import ReviewModel


@dataclass(slots=True)
class EmbeddingConfig:
    model_name: str = "all-mpnet-base-v2"
    batch_size: int = 32
    cache_path: Path = Path("data/processed/embeddings_cache.json")


@dataclass(slots=True)
class EmbeddingBatch:
    review_ids: List[str]
    vectors: np.ndarray


class EmbeddingCache:
    """Very small JSON-based cache for embeddings."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: Dict[str, List[float]] = {}
        self._load()

    def get(self, key: str) -> List[float] | None:
        return self._data.get(key)

    def set(self, key: str, vector: np.ndarray) -> None:
        self._data[key] = vector.tolist()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh)

    def _load(self) -> None:
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))


class EmbeddingService:
    """Encodes cleaned review texts into dense vectors."""

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig()
        self.model = SentenceTransformer(self.config.model_name)
        self.cache = EmbeddingCache(self.config.cache_path)

    def embed_reviews(self, reviews: Sequence[ReviewModel]) -> EmbeddingBatch:
        """
        Generate embeddings for the supplied reviews, reusing cached vectors where possible.
        """
        pending_texts: List[str] = []
        pending_indices: List[Tuple[int, str]] = []
        collected: Dict[int, np.ndarray] = {}

        for idx, review in enumerate(reviews):
            cache_key = self._cache_key(review)
            cached_vector = self.cache.get(cache_key)
            if cached_vector is not None:
                collected[idx] = np.array(cached_vector, dtype=np.float32)
                continue

            pending_texts.append(review.text)
            pending_indices.append((idx, cache_key))

        if pending_texts:
            new_vectors = self.model.encode(
                pending_texts,
                batch_size=self.config.batch_size,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            for (idx, cache_key), vector in zip(pending_indices, new_vectors, strict=True):
                collected[idx] = vector
                self.cache.set(cache_key, vector)
            self.cache.flush()

        if not collected:
            return EmbeddingBatch(review_ids=[], vectors=np.empty((0, self.model.get_sentence_embedding_dimension())))

        ordered_indices = sorted(collected)
        ordered_vectors = np.vstack([collected[idx] for idx in ordered_indices])
        review_ids = [reviews[idx].review_id for idx in ordered_indices]
        return EmbeddingBatch(review_ids=review_ids, vectors=ordered_vectors)

    @staticmethod
    def _cache_key(review: ReviewModel) -> str:
        digest = hashlib.sha256(review.text.encode("utf-8")).hexdigest()
        return f"{review.review_id}:{digest}"


