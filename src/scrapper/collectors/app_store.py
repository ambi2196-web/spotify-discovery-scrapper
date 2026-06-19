"""Apple App Store reviews via the public iTunes RSS feed. Phase 1 implementation."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from scrapper.collectors.base import BaseCollector
from scrapper.models import CollectQuery, RawRecord, Review, Source, hash_author
from scrapper.registry import register
from scrapper.storage.io import raw_dir

log = logging.getLogger(__name__)

RSS_TEMPLATE = (
    "https://itunes.apple.com/{country}/rss/customerreviews/"
    "page={page}/id={app_id}/sortby=mostrecent/json"
)
MAX_PAGES = 10  # RSS only exposes up to ~10 pages of 50 reviews each


@register("app_store")
class AppStoreCollector(BaseCollector):
    source = Source.APP_STORE.value

    def collect(self, query: CollectQuery) -> Iterator[RawRecord]:
        cfg = query.extra.get("app_store", {})
        app_id = cfg.get("app_id", "324684580")
        countries = query.countries or cfg.get("countries", ["us"])
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=query.window_days)
        out = raw_dir("app_store")

        for country in countries:
            log.info("App Store: fetching %s …", country)
            for page in range(1, MAX_PAGES + 1):
                url = RSS_TEMPLATE.format(country=country, page=page, app_id=app_id)
                try:
                    entries = _fetch_page(url)
                except Exception as exc:
                    log.warning("App Store page %d/%s failed: %s", page, country, exc)
                    break

                if not entries:
                    break

                any_recent = False
                for entry in entries:
                    updated_str = entry.get("updated", {}).get("label", "")
                    try:
                        updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        updated = datetime.now(tz=timezone.utc)

                    if updated < cutoff:
                        continue
                    any_recent = True

                    native_id = entry.get("id", {}).get("label", f"{country}-{page}-{id(entry)}")
                    raw = RawRecord(
                        source=Source.APP_STORE,
                        native_id=native_id,
                        payload={"entry": entry, "country": country, "updated": updated.isoformat()},
                    )
                    # Persist raw for resumability
                    path = out / f"{country}_{native_id}.json"
                    if not path.exists():
                        path.write_text(json.dumps(raw.payload, ensure_ascii=False), encoding="utf-8")

                    yield raw

                if not any_recent:
                    log.info("App Store %s page %d: hit cutoff, stopping.", country, page)
                    break

                time.sleep(0.5)  # polite rate limiting

    def normalize(self, raw: RawRecord) -> Review:
        entry = raw.payload["entry"]
        country = raw.payload.get("country")
        updated_str = raw.payload.get("updated") or entry.get("updated", {}).get("label", "")
        try:
            created_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            created_at = datetime.now(tz=timezone.utc)

        rating_label = entry.get("im:rating", {}).get("label")
        try:
            rating = int(rating_label)
        except (TypeError, ValueError):
            rating = None

        title = (entry.get("title", {}).get("label") or "").strip() or None
        text = (entry.get("content", {}).get("label") or "").strip()
        author = entry.get("author", {}).get("name", {}).get("label")
        app_id = entry.get("id", {}).get("label", "")
        # Build App Store URL: best we can do without a direct link
        source_url = f"https://apps.apple.com/{country}/app/spotify/id{app_id}"

        return Review(
            source=Source.APP_STORE,
            source_url=source_url,
            created_at=created_at,
            text=text,
            rating=rating,
            title=title,
            lang="en" if country in ("us", "gb", "au", "ca", "nz") else "und",
            country=country,
            author_hash=hash_author(author),
            raw_meta={"native_id": raw.native_id},
        )


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
def _fetch_page(url: str) -> list[dict]:
    with httpx.Client(timeout=20) as client:
        resp = client.get(url, headers={"User-Agent": "scrapper/0.1 (research)"})
        resp.raise_for_status()
        data = resp.json()

    feed = data.get("feed", {})
    entries = feed.get("entry", [])
    # The first entry is often metadata — filter those without 'im:rating'
    return [e for e in entries if isinstance(e, dict) and "im:rating" in e]
