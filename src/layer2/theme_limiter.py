"""Merge clusters down to at most N themes using centroid similarity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from .clustering import ClusterSummary, ClusteringResult


@dataclass(slots=True)
class ThemeLimiterConfig:
    max_themes: int = 5


class ThemeLimiter:
    def __init__(self, config: ThemeLimiterConfig | None = None) -> None:
        self.config = config or ThemeLimiterConfig()

    def enforce(self, clustering: ClusteringResult) -> List[ClusterSummary]:
        clusters = list(clustering.summaries.values())
        if len(clusters) <= self.config.max_themes:
            return clusters

        next_label = max(cluster.label for cluster in clusters) + 1
        while len(clusters) > self.config.max_themes:
            i, j = self._find_most_similar_pair(clusters)
            merged = self._merge_clusters(clusters[i], clusters[j], next_label)
            next_label += 1
            clusters = [cluster for k, cluster in enumerate(clusters) if k not in {i, j}]
            clusters.append(merged)
        return clusters

    @staticmethod
    def _find_most_similar_pair(clusters: List[ClusterSummary]) -> Tuple[int, int]:
        best_pair = (0, 1)
        best_score = -1.0
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                score = cosine_similarity(clusters[i].centroid, clusters[j].centroid)
                if score > best_score:
                    best_score = score
                    best_pair = (i, j)
        return best_pair

    @staticmethod
    def _merge_clusters(left: ClusterSummary, right: ClusterSummary, new_label: int) -> ClusterSummary:
        left_size = len(left.review_ids)
        right_size = len(right.review_ids)
        total = left_size + right_size
        centroid = (left.centroid * left_size + right.centroid * right_size) / total
        strength = (left.strength * left_size + right.strength * right_size) / total
        review_ids = left.review_ids + right.review_ids
        return ClusterSummary(
            label=new_label,
            review_ids=review_ids,
            centroid=centroid,
            strength=strength,
        )


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    denominator = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denominator == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / denominator)



