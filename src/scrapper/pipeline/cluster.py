"""Stage 4: cluster embeddings into themes (HDBSCAN default). Phase 1 implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def run(
    in_path: Path,
    out_path: Path,
    min_cluster_size: int = 15,
    use_umap: bool = True,
) -> int:
    """Read reviews_embedded.parquet, optionally UMAP-reduce, run HDBSCAN,
    write back with a cluster_id column. Returns number of clusters found."""
    df = pd.read_parquet(in_path)
    if df.empty or "embedding" not in df.columns:
        log.warning("No embeddings found. Run embed stage first.")
        df.to_parquet(out_path, index=False)
        return 0

    matrix = np.array(df["embedding"].tolist(), dtype=np.float32)
    log.info("Clustering %d records (dim=%d) …", len(matrix), matrix.shape[1])

    if use_umap and len(matrix) >= min_cluster_size * 2:
        matrix = _umap_reduce(matrix)

    labels = _hdbscan_cluster(matrix, min_cluster_size)
    df["cluster_id"] = labels

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    log.info("Found %d clusters, %d noise points.", n_clusters, n_noise)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return n_clusters


def _umap_reduce(matrix: np.ndarray, n_components: int = 10) -> np.ndarray:
    try:
        import umap
    except ImportError:
        log.warning("umap-learn not installed; skipping UMAP reduction. Install with: pip install umap-learn")
        return matrix

    reducer = umap.UMAP(
        n_components=min(n_components, matrix.shape[1]),
        n_neighbors=15,
        min_dist=0.0,
        metric="cosine",
        random_state=42,
        low_memory=True,
    )
    log.info("UMAP: reducing %d-dim embeddings to %d dims …", matrix.shape[1], n_components)
    return reducer.fit_transform(matrix).astype(np.float32)


def _hdbscan_cluster(matrix: np.ndarray, min_cluster_size: int) -> np.ndarray:
    try:
        import hdbscan
    except ImportError:
        raise RuntimeError(
            "hdbscan not installed.\n"
            "Run: pip install -e \".[ml]\"  or  pip install hdbscan"
        )

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=5,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=False,
    )
    clusterer.fit(matrix)
    return clusterer.labels_
