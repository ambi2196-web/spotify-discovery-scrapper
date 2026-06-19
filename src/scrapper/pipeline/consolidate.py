"""Stage 2: normalize raw payloads -> canonical, deduped reviews.parquet. Phase 1 implementation."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from scrapper.registry import get_collector
from scrapper.storage.io import ensure_dirs

log = logging.getLogger(__name__)


def run(raw_dir: Path, out_path: Path) -> int:
    """Load all data/raw/<source>/*.json, normalize via each collector, dedupe on Review.id,
    write reviews.parquet. Returns record count."""
    ensure_dirs()
    records: dict[str, dict] = {}  # id -> record dict (dedupe on id)

    for source_dir in sorted(raw_dir.iterdir()):
        if not source_dir.is_dir():
            continue
        source_name = source_dir.name
        try:
            collector_cls = get_collector(source_name)
        except KeyError:
            log.warning("No collector registered for '%s', skipping.", source_name)
            continue

        collector = collector_cls()
        json_files = list(source_dir.glob("*.json"))
        log.info("Consolidating %s: %d files …", source_name, len(json_files))

        for fpath in json_files:
            try:
                payload = json.loads(fpath.read_text(encoding="utf-8"))
                from scrapper.models import RawRecord, Source
                raw = RawRecord(
                    source=Source(source_name),
                    native_id=fpath.stem,
                    payload=payload,
                )
                review = collector.normalize(raw)
                if not review.text or len(review.text.strip()) < 10:
                    continue
                if review.id not in records:
                    records[review.id] = _review_to_dict(review)
            except Exception as exc:
                log.debug("Skipping %s: %s", fpath.name, exc)

    if not records:
        log.warning("No records found to consolidate.")
        df = pd.DataFrame()
    else:
        df = pd.DataFrame(list(records.values()))
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
        df = df.sort_values("created_at", ascending=False).reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    log.info("Wrote %d records to %s", len(df), out_path)
    return len(df)


def _review_to_dict(review) -> dict:
    d = asdict(review)
    # source is an enum; convert to string
    d["source"] = review.source.value
    # drop large derived fields not yet computed
    d.pop("embedding", None)
    d["cluster_id"] = None
    d["theme_label"] = None
    d["diagnostic_questions"] = []
    return d
