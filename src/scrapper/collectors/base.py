"""Collector interface — the plugin point. See ARCHITECTURE.md §4."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from scrapper.models import CollectQuery, RawRecord, Review


class BaseCollector(ABC):
    """One subclass per source. The rest of the pipeline is source-agnostic."""

    source: str  # set on each subclass, e.g. "app_store"

    @abstractmethod
    def collect(self, query: CollectQuery) -> Iterator[RawRecord]:
        """Yield raw, source-native records for the given window/query."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw: RawRecord) -> Review:
        """Map one raw record to the canonical Review schema."""
        raise NotImplementedError
