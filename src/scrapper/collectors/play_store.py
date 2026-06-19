"""Google Play Store reviews via google-play-scraper (no official public API). Phase 1 implementation."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Iterator

from scrapper.collectors.base import BaseCollector
from scrapper.models import CollectQuery, RawRecord, Review, Source, hash_author
from scrapper.registry import register
from scrapper.storage.io import raw_dir

log = logging.getLogger(__name__)

PLAY_BASE_URL = "https://play.google.com/store/apps/details?id={app_id}"


@register("play_store")
class PlayStoreCollector(BaseCollector):
    source = Source.PLAY_STORE.value

    def collect(self, query: CollectQuery) -> Iterator[RawRecord]:
        try:
            from google_play_scraper import Sort, reviews as gps_reviews
        except ImportError:
            raise RuntimeError("google-play-scraper not installed. Run: pip install google-play-scraper")

        cfg = query.extra.get("play_store", {})
        app_id = cfg.get("app_id", "com.spotify.music")
        countries = query.countries or cfg.get("countries", ["us"])
        lang = cfg.get("lang", "en")
        max_per_country = query.limit or cfg.get("max_per_country", 500)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=query.window_days)
        out = raw_dir("play_store")

        for country in countries:
            log.info("Play Store: fetching %s …", country)
            continuation_token = None
            fetched = 0

            while fetched < max_per_country:
                batch_size = min(200, max_per_country - fetched)
                try:
                    result, continuation_token = gps_reviews(
                        app_id,
                        lang=lang,
                        country=country,
                        sort=Sort.NEWEST,
                        count=batch_size,
                        continuation_token=continuation_token,
                    )
                except Exception as exc:
                    log.warning("Play Store %s batch failed: %s", country, exc)
                    break

                if not result:
                    break

                any_recent = False
                for review in result:
                    at: datetime = review.get("at")
                    if at and at.tzinfo is None:
                        at = at.replace(tzinfo=timezone.utc)
                    if at and at < cutoff:
                        continue
                    any_recent = True

                    native_id = review.get("reviewId") or f"{country}-{id(review)}"
                    payload = {k: str(v) if isinstance(v, datetime) else v for k, v in review.items()}
                    payload["_country"] = country

                    raw = RawRecord(
                        source=Source.PLAY_STORE,
                        native_id=native_id,
                        payload=payload,
                    )
                    path = out / f"{country}_{native_id}.json"
                    if not path.exists():
                        path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")

                    yield raw
                    fetched += 1

                if not any_recent or not continuation_token:
                    break

                time.sleep(1.0)  # polite rate limiting

    def normalize(self, raw: RawRecord) -> Review:
        p = raw.payload
        country = p.get("_country", "us")

        at_raw = p.get("at")
        if isinstance(at_raw, str):
            try:
                created_at = datetime.fromisoformat(at_raw)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except ValueError:
                created_at = datetime.now(tz=timezone.utc)
        elif isinstance(at_raw, datetime):
            created_at = at_raw if at_raw.tzinfo else at_raw.replace(tzinfo=timezone.utc)
        else:
            created_at = datetime.now(tz=timezone.utc)

        rating = p.get("score")
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            rating = None

        text = (p.get("content") or "").strip()
        author = p.get("userName")
        app_id = p.get("appId", "com.spotify.music")
        review_id = raw.native_id
        source_url = f"{PLAY_BASE_URL.format(app_id=app_id)}&reviewId={review_id}"

        return Review(
            source=Source.PLAY_STORE,
            source_url=source_url,
            created_at=created_at,
            text=text,
            rating=rating,
            title=None,  # Play Store has no title field
            lang="en",
            country=country,
            author_hash=hash_author(author),
            raw_meta={"native_id": raw.native_id, "thumbsUp": p.get("thumbsUpCount", 0)},
        )
