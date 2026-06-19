"""Reddit posts/comments via the official PRAW API (OAuth). Phase 1 implementation."""

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


@register("reddit")
class RedditCollector(BaseCollector):
    source = Source.REDDIT.value

    def _get_client(self, secrets):
        try:
            import praw
        except ImportError:
            raise RuntimeError("praw not installed. Run: pip install praw")

        if not secrets.reddit_client_id or not secrets.reddit_client_secret:
            raise RuntimeError(
                "Reddit credentials missing. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env\n"
                "Create an app at: https://www.reddit.com/prefs/apps (type: script)"
            )
        return praw.Reddit(
            client_id=secrets.reddit_client_id,
            client_secret=secrets.reddit_client_secret,
            user_agent=secrets.reddit_user_agent or "scrapper/0.1 (research)",
            check_for_async=False,
        )

    def collect(self, query: CollectQuery) -> Iterator[RawRecord]:
        from scrapper.config import load_secrets
        secrets = load_secrets()
        reddit = self._get_client(secrets)

        cfg = query.extra.get("reddit", {})
        subreddits = query.subreddits or cfg.get("subreddits", ["spotify"])
        queries = query.queries or cfg.get("queries", ["discover weekly", "new music"])
        max_per_query = query.limit or cfg.get("max_per_query", 300)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=query.window_days)
        out = raw_dir("reddit")
        seen: set[str] = set()

        for sub_name in subreddits:
            subreddit = reddit.subreddit(sub_name)
            for q in queries:
                log.info("Reddit r/%s — query '%s' …", sub_name, q)
                try:
                    results = subreddit.search(
                        q,
                        sort="new",
                        time_filter="year",
                        limit=max_per_query,
                    )
                    for submission in results:
                        created = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                        if created < cutoff:
                            continue
                        if submission.id in seen:
                            continue
                        seen.add(submission.id)

                        payload = {
                            "id": submission.id,
                            "title": submission.title,
                            "selftext": submission.selftext,
                            "score": submission.score,
                            "url": submission.url,
                            "permalink": f"https://www.reddit.com{submission.permalink}",
                            "subreddit": sub_name,
                            "created_utc": submission.created_utc,
                            "author": str(submission.author) if submission.author else None,
                            "num_comments": submission.num_comments,
                            "_query": q,
                        }
                        raw = RawRecord(
                            source=Source.REDDIT,
                            native_id=submission.id,
                            payload=payload,
                        )
                        path = out / f"{submission.id}.json"
                        if not path.exists():
                            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                        yield raw

                        # Also yield top-level comments for richer signal
                        try:
                            submission.comments.replace_more(limit=0)
                            for comment in list(submission.comments)[:10]:
                                if not comment.body or comment.body in ("[deleted]", "[removed]"):
                                    continue
                                cid = f"{submission.id}_c{comment.id}"
                                if cid in seen:
                                    continue
                                seen.add(cid)
                                cpayload = {
                                    "id": cid,
                                    "title": None,
                                    "selftext": comment.body,
                                    "score": comment.score,
                                    "url": None,
                                    "permalink": f"https://www.reddit.com{comment.permalink}",
                                    "subreddit": sub_name,
                                    "created_utc": comment.created_utc,
                                    "author": str(comment.author) if comment.author else None,
                                    "num_comments": 0,
                                    "_query": q,
                                    "_parent_id": submission.id,
                                }
                                craw = RawRecord(
                                    source=Source.REDDIT,
                                    native_id=cid,
                                    payload=cpayload,
                                )
                                cpath = out / f"{cid}.json"
                                if not cpath.exists():
                                    cpath.write_text(json.dumps(cpayload, ensure_ascii=False), encoding="utf-8")
                                yield craw
                        except Exception:
                            pass

                        time.sleep(0.1)

                except Exception as exc:
                    log.warning("Reddit r/%s q='%s' failed: %s", sub_name, q, exc)
                    time.sleep(2)

    def normalize(self, raw: RawRecord) -> Review:
        p = raw.payload
        created_at = datetime.fromtimestamp(
            float(p.get("created_utc", 0)), tz=timezone.utc
        )
        text_parts = []
        if p.get("title"):
            text_parts.append(p["title"])
        body = (p.get("selftext") or "").strip()
        if body and body not in ("[deleted]", "[removed]"):
            text_parts.append(body)
        text = "\n\n".join(text_parts).strip()

        permalink = p.get("permalink", "")
        return Review(
            source=Source.REDDIT,
            source_url=permalink,
            created_at=created_at,
            text=text,
            rating=None,
            title=p.get("title"),
            lang="und",
            country=None,
            author_hash=hash_author(p.get("author")),
            raw_meta={
                "subreddit": p.get("subreddit"),
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "query": p.get("_query"),
                "native_id": raw.native_id,
            },
        )
