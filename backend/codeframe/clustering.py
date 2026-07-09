"""Embed responses and discover themes via UMAP + HDBSCAN.

Ported from notebook section 2-A. All randomness is seeded from
`cfg.random_seed` so repeated runs against the same embeddings produce
identical cluster labels.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import hdbscan
import numpy as np
import pandas as pd
import umap
from sklearn.metrics.pairwise import cosine_distances

from codeframe.config import ClusterConfig, ProjectConfig
from codeframe.llm import LLMClient

logger = logging.getLogger(__name__)


def embed(texts: list[str], project_cfg: ProjectConfig, client: LLMClient) -> np.ndarray:
    """Encode texts into dense vectors using the configured OpenAI embedding model."""
    texts = ["" if pd.isna(t) else str(t) for t in texts]
    batch_size = project_cfg.embedding_batch_size
    all_vectors: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        resp = client.embeddings.create(
            model=project_cfg.embedding_model, input=batch, timeout=project_cfg.openai_timeout_seconds
        )
        batch_vectors = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
        all_vectors.extend(batch_vectors)

    emb = np.asarray(all_vectors, dtype=np.float32)
    logger.info("Embeddings: %s | model=%s | input_texts=%s", emb.shape, project_cfg.embedding_model, len(texts))
    return emb


def _reduce_dimensions_umap(embeddings: np.ndarray, cfg: ClusterConfig) -> np.ndarray:
    n_components = min(cfg.umap_components, len(embeddings) - 2, embeddings.shape[1])
    n_neighbors = min(cfg.umap_neighbors, len(embeddings) - 1)
    reducer = umap.UMAP(
        n_components=n_components, n_neighbors=n_neighbors, min_dist=0.0, metric="cosine",
        random_state=cfg.random_seed, n_jobs=1, low_memory=True,
    )
    reduced = reducer.fit_transform(embeddings)
    logger.info("UMAP: %sD -> %sD", embeddings.shape[1], reduced.shape[1])
    return reduced


def _cluster_responses(embeddings: np.ndarray, cfg: ClusterConfig, min_cluster_size: int, metric: str = "euclidean"):
    fit_input, hdb_metric = (cosine_distances(embeddings), "precomputed") if metric == "cosine" else (embeddings, metric)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size, min_samples=cfg.min_samples,
        cluster_selection_epsilon=cfg.epsilon, metric=hdb_metric, cluster_selection_method="eom",
    )
    labels = clusterer.fit_predict(fit_input)
    logger.info("Clusters: %s Noise: %s", len(set(labels)) - (1 if -1 in labels else 0), (labels == -1).sum())
    return labels, clusterer


def _representative_samples(texts, labels, probabilities, n_samples: int) -> dict[int, list[str]]:
    reps: dict[int, list[str]] = {}
    for cid in sorted(set(labels)):
        if cid == -1:
            continue
        if probabilities is not None:
            members = [(t, p) for t, l, p in zip(texts, labels, probabilities) if l == cid]
            members.sort(key=lambda tp: tp[1], reverse=True)
            take = min(n_samples, len(members))
            reps[cid] = [t for t, _ in members[:take]]
        else:
            ct = [t for t, l in zip(texts, labels) if l == cid]
            idx = np.linspace(0, len(ct) - 1, min(n_samples, len(ct)), dtype=int)
            reps[cid] = [ct[i] for i in idx]
    return reps


@dataclass
class ClusterResult:
    labels: np.ndarray
    probabilities: np.ndarray
    representatives: dict[int, list[str]]
    cluster_column: pd.Series = field(repr=False, default=None)


def discover_themes(embeddings: np.ndarray, texts: list[str], cfg: ClusterConfig) -> ClusterResult:
    """Orchestrate UMAP -> HDBSCAN -> representative-sample selection.

    `texts` must align 1:1 with `embeddings` rows. Deterministic given the
    same embeddings, texts, and `cfg.random_seed`.
    """
    if len(texts) < 10:
        raise ValueError("Need >= 10 responses for clustering.")

    reduced = _reduce_dimensions_umap(embeddings, cfg)
    min_cluster_size = max(3, len(texts) // 50)
    labels, clusterer = _cluster_responses(reduced, cfg, min_cluster_size=min_cluster_size)
    probabilities = clusterer.probabilities_ if hasattr(clusterer, "probabilities_") else None
    reps = _representative_samples(texts, labels, probabilities, cfg.representatives)

    return ClusterResult(
        labels=labels,
        probabilities=probabilities if probabilities is not None else np.zeros(len(labels)),
        representatives=reps,
    )
