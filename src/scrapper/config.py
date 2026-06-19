"""Typed configuration: sources.yaml (what) + .env (secrets). See ARCHITECTURE.md §8."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "sources.yaml"


class Secrets(BaseSettings):
    """Loaded from environment / .env. Missing values are allowed in Phase 0."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


class EmbeddingConfig(BaseModel):
    provider: str = "local"
    model: str = "all-MiniLM-L6-v2"


class ClusteringConfig(BaseModel):
    algorithm: str = "hdbscan"
    min_cluster_size: int = 15
    use_umap: bool = True


class LabelingConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-haiku-4-5"
    max_quotes_per_cluster: int = 5


class Config(BaseModel):
    window_days: int = 90
    sources: dict[str, dict[str, Any]] = {}
    embedding: EmbeddingConfig = EmbeddingConfig()
    clustering: ClusteringConfig = ClusteringConfig()
    labeling: LabelingConfig = LabelingConfig()

    def enabled_sources(self) -> list[str]:
        return [name for name, cfg in self.sources.items() if cfg.get("enabled")]


@lru_cache
def load_config(path: str | Path = DEFAULT_CONFIG) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config(**raw)


@lru_cache
def load_secrets() -> Secrets:
    return Secrets()
