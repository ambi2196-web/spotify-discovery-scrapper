"""Canonical paths + read/write helpers. Keeps path conventions in one place."""

from __future__ import annotations

from pathlib import Path

from scrapper.config import PROJECT_ROOT

DATA = PROJECT_ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
INTERIM = DATA / "interim"
REPORTS = PROJECT_ROOT / "reports"

REVIEWS = PROCESSED / "reviews.parquet"
REVIEWS_EMBEDDED = PROCESSED / "reviews_embedded.parquet"
CLUSTERS = INTERIM / "clusters.json"
DIAGNOSIS_JSON = REPORTS / "diagnosis.json"
DIAGNOSIS_MD = REPORTS / "diagnosis.md"


def ensure_dirs() -> None:
    for d in (RAW, PROCESSED, INTERIM, REPORTS):
        d.mkdir(parents=True, exist_ok=True)


def raw_dir(source: str) -> Path:
    p = RAW / source
    p.mkdir(parents=True, exist_ok=True)
    return p
