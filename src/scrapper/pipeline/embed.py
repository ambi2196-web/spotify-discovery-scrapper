"""Stage 3: add an embedding vector per review. Local default (sentence-transformers); OpenAI opt-in.
Phase 1 implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BATCH_SIZE = 64


def run(
    in_path: Path,
    out_path: Path,
    provider: str = "local",
    model: str = "all-MiniLM-L6-v2",
) -> int:
    """Read reviews.parquet, compute embeddings, write reviews_embedded.parquet.
    Returns record count."""
    df = pd.read_parquet(in_path)
    if df.empty:
        log.warning("No records to embed.")
        df.to_parquet(out_path, index=False)
        return 0

    texts = df["text"].fillna("").tolist()
    log.info("Embedding %d records with provider='%s', model='%s' …", len(texts), provider, model)

    if provider == "local":
        embeddings = _embed_local(texts, model)
    elif provider == "openai":
        embeddings = _embed_openai(texts, model)
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}. Use 'local' or 'openai'.")

    # Store as a list of lists (parquet-serialisable)
    df["embedding"] = [emb.tolist() for emb in embeddings]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    log.info("Wrote %d records with embeddings to %s", len(df), out_path)
    return len(df)


def _embed_local(texts: list[str], model_name: str) -> list[np.ndarray]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "sentence-transformers not installed.\n"
            "Run: pip install -e \".[ml]\"  or  pip install sentence-transformers"
        )
    log.info("Loading local model '%s' (first run downloads it) …", model_name)
    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    return list(embeddings)


def _embed_openai(texts: list[str], model_name: str) -> list[np.ndarray]:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai not installed. Run: pip install openai")

    import os
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        response = client.embeddings.create(input=batch, model=model_name)
        for item in response.data:
            embeddings.append(np.array(item.embedding))
        log.info("OpenAI embeddings: %d / %d", min(i + BATCH_SIZE, len(texts)), len(texts))
    return embeddings
