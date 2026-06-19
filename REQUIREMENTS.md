# Scrapper — Requirements Document

**Project:** Spotify Discovery Review-Analysis Pipeline ("Scrapper")
**Phase:** 0 — Requirements, Environment, Architecture
**Owner:** Ashu (PM Fellowship, Growth case study)
**Last updated:** 2026-06-20
**Status:** Draft for review

---

## 1. Purpose

Scrapper is a live, testable, multi-source pipeline that ingests user feedback about Spotify, analyzes it with embeddings + clustering + LLM theme-labeling, and produces evidence for **one** core question:

> **Why don't Spotify users discover new music?**

It exists to ground the case study's problem statement in real user voice (not assumptions) before primary interviews, and to produce a hyperlinkable, demonstrable artefact for the deck and MVP.

This is **diagnostic infrastructure**, not a product feature. Success is measured by the quality and traceability of the insight it produces, not by scale.

---

## 2. Goals & non-goals

**Goals**

- Pull real, recent user reviews/comments from multiple independent channels.
- Normalize them into one consistent, queryable dataset.
- Surface the dominant *themes* in discovery-related feedback automatically.
- Map those themes to six specific diagnostic questions (Section 4).
- Be reproducible and runnable by a reviewer (a workflow link / demo).

**Non-goals (Phase 0)**

- No real-time / streaming ingestion — batch runs are sufficient.
- No production-grade data warehouse — local files + lightweight store.
- No paid scraping infrastructure or proxy networks.
- No sentiment dashboard polish (that's a later phase / the MVP).
- No always-on or ambient capture of any kind.

---

## 3. Data sources (Phase 0 scope)

Phase 0 architects for **three highest-signal sources**, accessed **official-API-first**. Forums and social media are designed as pluggable collectors for a later phase, not built now.

| Source | Access method | Notes / constraints |
|---|---|---|
| Apple App Store reviews | iTunes RSS / App Store review feed (public, no key) | Rate-limited; country-segmented; ~500 most recent per country/page. |
| Google Play Store reviews | `google-play-scraper` (community lib) — no official public reviews API | Treated as fallback scraping; respect rate limits & ToS. |
| Reddit | Official Reddit API via PRAW (OAuth) | Requires app credentials; query r/spotify, r/Music, etc. |
| Forums (Spotify Community) | *Pluggable — not in Phase 0* | Design collector interface so it can be added without core changes. |
| Social (X/TikTok/YouTube) | *Pluggable — not in Phase 0* | High ToS/legal fragility; deferred. |

**Legal/ToS posture:** prefer official APIs; scrape only where no API exists; store only public content; no PII enrichment; respect rate limits; cache responses to minimize repeat calls.

---

## 4. The six diagnostic questions

Every theme the pipeline surfaces must be mappable to one or more of these. These are the analytical backbone — they should be confirmed against the fellowship brief before Phase 1.

1. **Awareness** — Do users know discovery features exist (Discover Weekly, Release Radar, DJ, Radio, Smart Shuffle)?
2. **Trust** — Do users believe the recommendations are *for them*, or do they feel generic/repetitive?
3. **Effort** — How much friction is there between intent ("find something new") and outcome?
4. **Relevance** — Are recommendations perceived as too safe, too random, or stuck in a loop ("same songs again")?
5. **Context** — Do recommendations fit the moment (mood, activity, time) or ignore it?
6. **Agency** — Can users steer/correct discovery, or does it feel like a black box they can't influence?

---

## 5. Functional requirements

**FR-1 Collection.** For each enabled source, fetch recent reviews/comments for a configurable date window and query set; persist raw payloads to `data/raw/<source>/`.

**FR-2 Consolidation.** Normalize all raw records into one canonical schema (Section 7); deduplicate; persist to `data/processed/reviews.parquet`.

**FR-3 Embedding.** Generate a vector embedding per record using a configurable embedding model (local sentence-transformers default; OpenAI optional via key).

**FR-4 Clustering.** Cluster embeddings into themes (HDBSCAN default; configurable). Each record gets a cluster id; noise allowed.

**FR-5 Theme labeling.** For each cluster, an LLM produces a short human-readable label + summary, and assigns the cluster to one or more of the six diagnostic questions with a confidence note.

**FR-6 Diagnosis output.** Produce a per-question rollup: which themes map to it, representative quotes (with source + link), and relative volume. Output as a structured file (JSON + Markdown) for the deck.

**FR-7 Queryable demo.** A minimal CLI / interface to run the full pipeline end-to-end and to query "show me themes for question N" — this is the reviewer-facing workflow.

**FR-8 Reproducibility.** Single command runs the whole pipeline from config; runs are deterministic given fixed inputs and seeds where possible.

---

## 6. Non-functional requirements

- **NFR-1 Cost:** runnable on a laptop; default path uses free/local models; paid APIs strictly opt-in via env.
- **NFR-2 Config over code:** sources, queries, windows, model choices live in `config/sources.yaml` + `.env` — no code edits to re-run.
- **NFR-3 Traceability:** every quote in any output links back to its original record and source URL.
- **NFR-4 Extensibility:** adding a new source = implementing one collector interface; no changes to consolidation/embedding/clustering.
- **NFR-5 Resilience:** network failures and rate limits are retried with backoff; partial runs are resumable from cached raw data.
- **NFR-6 Privacy:** store only public content; no attempt to deanonymize authors; secrets never committed.

---

## 7. Canonical data schema

One normalized record (`Review`) across all sources:

| Field | Type | Description |
|---|---|---|
| `id` | str | Stable hash of source + native id |
| `source` | enum | `app_store` \| `play_store` \| `reddit` |
| `source_url` | str | Deep link back to the original item |
| `created_at` | datetime (UTC) | When the review/comment was posted |
| `rating` | int? | 1–5 where available (app stores); null for Reddit |
| `title` | str? | App-store review title; null otherwise |
| `text` | str | Body content (required, non-empty) |
| `lang` | str | Detected language code |
| `country` | str? | Storefront country where applicable |
| `author_hash` | str? | Hashed author handle (non-reversible) |
| `raw_meta` | json | Source-specific extras preserved as-is |

Derived/analytical fields added downstream: `embedding`, `cluster_id`, `theme_label`, `diagnostic_questions[]`.

---

## 8. Success criteria (Phase 0)

Phase 0 is done when:

1. This requirements doc and the architecture doc are reviewed and accepted.
2. The repo scaffold runs: package imports, CLI loads, config parses, no install errors.
3. `.env.example` documents every credential needed for Phase 1.
4. Each pipeline stage has a defined interface and a stub that's ready to implement.

Phase 1 (implementation) success — for reference, not built here: a single command produces a six-question diagnostic report with real quotes and a shareable workflow link.

---

## 9. Open questions to confirm before Phase 1

- Are the six diagnostic questions above the exact ones in the fellowship brief, or should they be reworded?
- Target user segment for the analysis (drives Reddit subreddit + query selection)?
- Embedding/LLM provider preference (fully local vs. OpenAI/Anthropic) and any budget cap?
- Required output format for the deck artefact (hosted link, Notion, static HTML)?
