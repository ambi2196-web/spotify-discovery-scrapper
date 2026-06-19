"""Source-name -> collector class registry. Adding a source = register here. (ARCHITECTURE.md §4)"""

from __future__ import annotations

from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from scrapper.collectors.base import BaseCollector

_REGISTRY: dict[str, "Type[BaseCollector]"] = {}


def register(name: str):
    def _wrap(cls: "Type[BaseCollector]") -> "Type[BaseCollector]":
        _REGISTRY[name] = cls
        return cls

    return _wrap


def get_collector(name: str) -> "Type[BaseCollector]":
    if name not in _REGISTRY:
        raise KeyError(f"No collector registered for source '{name}'. Known: {list(_REGISTRY)}")
    return _REGISTRY[name]


def available() -> list[str]:
    return sorted(_REGISTRY)
