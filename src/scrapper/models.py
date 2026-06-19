"""Canonical data models shared across all stages. Stdlib-only so it imports anywhere.

See REQUIREMENTS.md §7 for the schema and ARCHITECTURE.md §4 for usage.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class Source(str, Enum):
    APP_STORE = "app_store"
    PLAY_STORE = "play_store"
    REDDIT = "reddit"


@dataclass
class CollectQuery:
    """Parameters a collector needs for one fetch run."""

    window_days: int
    countries: list[str] = field(default_factory=list)
    subreddits: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    limit: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawRecord:
    """Untouched source payload, persisted to data/raw for resumability."""

    source: Source
    native_id: str
    payload: dict[str, Any]


@dataclass
class Review:
    """Canonical, source-agnostic record. One per user comment/review."""

    source: Source
    source_url: str
    created_at: datetime
    text: str
    id: str = ""
    rating: Optional[int] = None
    title: Optional[str] = None
    lang: str = "und"
    country: Optional[str] = None
    author_hash: Optional[str] = None
    raw_meta: dict[str, Any] = field(default_factory=dict)

    # Derived downstream
    embedding: Optional[list[float]] = None
    cluster_id: Optional[int] = None
    theme_label: Optional[str] = None
    diagnostic_questions: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            key = f"{self.source.value}:{self.source_url}:{self.text[:64]}"
            self.id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


@dataclass
class Cluster:
    """Output of clustering + LLM labeling."""

    cluster_id: int
    label: str
    summary: str
    diagnostic_questions: list[int]
    size: int
    representative_quote_ids: list[str] = field(default_factory=list)


def hash_author(handle: Optional[str]) -> Optional[str]:
    """Non-reversible author hash; never store raw handles (NFR-6)."""
    if not handle:
        return None
    return hashlib.sha256(handle.encode("utf-8")).hexdigest()[:12]
