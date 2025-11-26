"""HDBSCAN clustering helpers for review embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import hdbscan
import numpy as np

from .embeddings import EmbeddingBatch


@dataclass(slots=True)
class ClusteringConfig:
    min_cluster_size: int = 8
    min_samples: int | None = None
    cluster_selection_epsilon: float = 0.0


@dataclass(slots=True)
class ClusterSummary:
    label: int
    review_ids: List[str]
    centroid: np.ndarray
    strength: float


@dataclass(slots=True)
class ClusteringResult:
    labels: np.ndarray
    probabilities: np.ndarray
    summaries: Dict[int, ClusterSummary]


class ReviewClusterer:
    """Clusters embedding vectors into coherent themes."""

    def __init__(self, config: ClusteringConfig | None = None) -> None:
        self.config = config or ClusteringConfig()

    def cluster(self, batch: EmbeddingBatch) -> ClusteringResult:
        if batch.vectors.size == 0:
            return ClusteringResult(
                labels=np.array([], dtype=int),
                probabilities=np.array([], dtype=float),
                summaries={},
            )

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.config.min_cluster_size,
            min_samples=self.config.min_samples,
            cluster_selection_epsilon=self.config.cluster_selection_epsilon,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(batch.vectors)
        probabilities = getattr(clusterer, "probabilities_", None)
        if probabilities is None:
            probabilities = np.ones_like(labels, dtype=float)

        summaries = self._build_summaries(labels, probabilities, batch)
        return ClusteringResult(labels=labels, probabilities=probabilities, summaries=summaries)

    @staticmethod
    def _build_summaries(
        labels: np.ndarray,
        probabilities: np.ndarray,
        batch: EmbeddingBatch,
    ) -> Dict[int, ClusterSummary]:
        summaries: Dict[int, ClusterSummary] = {}
        for cluster_id in sorted(set(labels)):
            if cluster_id == -1:
                continue  # skip noise
            indices = np.where(labels == cluster_id)[0]
            centroid = batch.vectors[indices].mean(axis=0)
            strength = float(probabilities[indices].mean())
            review_ids = [batch.review_ids[idx] for idx in indices]
            summaries[cluster_id] = ClusterSummary(
                label=cluster_id,
                review_ids=review_ids,
                centroid=centroid,
                strength=strength,
            )
        return summaries



