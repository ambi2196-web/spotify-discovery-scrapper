# Scrapper — Architecture Design

**Phase:** 0 · **Companion to:** `REQUIREMENTS.md` · **Updated:** 2026-06-20

---

## 1. Design principles

- **Pipeline, not monolith.** Six independent stages, each readable/runnable on its own, communicating through files on disk. Any stage can be re-run without re-running the others.
- **Collectors are plugins.** Sources implement one interface. Adding a forum or social source never touches consolidation/embedding/clustering.
- **Config over code.** What to fetch, which models, which windows — all in `config/sources.yaml` + `.env`.
- **Local-first, cloud-optional.** Default runs free on a laptop (local embeddings); paid APIs are opt-in.
- **Trace everything.** Every downstream artifact carries the keys needed to link back to the source URL.

---

## 2. Pipeline overview

```
                 config/sources.yaml + .env
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌───────────┐      ┌───────────┐       ┌───────────┐
  │ AppStore  │      │ PlayStore │       │  Reddit   │     1. COLLECT
  │ collector │      │ collector │       │ collector │     (official-API-first)
  └─────┬─────┘      └─────┬─────┘       └─────┬─────┘
        │  raw json            raw json            │
        └───────────────────┬───────────────────┘
                            ▼
                    ┌───────────────┐
                    │ CONSOLIDATE   │   2. normalize → dedupe → canonical schema
                    └───────┬───────┘
                            ▼  data/processed/reviews.parquet
                    ┌───────────────┐
                    │   EMBED       │   3. vector per record
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐
                    │   CLUSTER     │   4. HDBSCAN → cluster_id per record
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐
                    │   LABEL (LLM) │   5. theme label + map to 6 questions
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐
                    │   DIAGNOSE    │   6. per-question rollup + quotes + volume
                    └───────┬───────┘
                            ▼
              reports/diagnosis.json + diagnosis.md
                            │
                            ▼
                    CLI query interface  (the reviewer-facing workflow)
```

---

## 3. Stage contracts

Each stage reads a known input and writes a known output, so stages are independently testable.

| # | Stage | Input | Output | Key module |
|---|---|---|---|---|
| 1 | Collect | config + secrets | `data/raw/<source>/*.json` | `collectors/*` |
| 2 | Consolidate | raw json | `data/processed/reviews.parquet` | `pipeline/consolidate.py` |
| 3 | Embed | reviews.parquet | `reviews_embedded.parquet` | `pipeline/embed.py` |
| 4 | Cluster | embedded | `+ cluster_id` column | `pipeline/cluster.py` |
| 5 | Label | clustered + texts | `clusters.json` (label, summary, questions) | `pipeline/label.py` |
| 6 | Diagnose | clusters + reviews | `reports/diagnosis.{json,md}` | `analysis/diagnostics.py` |

---

## 4. Collector interface (the plugin point)

All sources subclass one ABC so the rest of the pipeline is source-agnostic.

```python
class BaseCollector(ABC):
    source: str  # "app_store" | "play_store" | "reddit"

    @abstractmethod
    def collect(self, query: CollectQuery) -> Iterator[RawRecord]:
        """Yield raw, source-native records for the given window/query."""

    @abstractmethod
    def normalize(self, raw: RawRecord) -> Review:
        """Map one raw record to the canonical Review schema."""
```

- `CollectQuery` carries date window, country list, subreddit/query terms, limits.
- `RawRecord` is the untouched source payload (persisted for resumability).
- `Review` is the canonical schema from `REQUIREMENTS.md` §7.
- A registry maps source name → collector class so `sources.yaml` enables them by name.

Adding **Spotify Community forum** or **social** later = new subclass + registry entry. Nothing downstream changes.

---

## 5. Component breakdown

```
src/scrapper/
  config.py        # load + validate sources.yaml and .env (pydantic settings)
  models.py        # Review, RawRecord, CollectQuery, Cluster dataclasses
  registry.py      # source-name → collector mapping
  cli.py           # entrypoint: run all | run <stage> | query
  collectors/
    base.py        # BaseCollector ABC
    app_store.py   # iTunes RSS review feed
    play_store.py  # google-play-scraper wrapper
    reddit.py      # PRAW client
  pipeline/
    consolidate.py # normalize + dedupe → parquet
    embed.py       # sentence-transformers (default) | OpenAI (opt-in)
    cluster.py     # HDBSCAN (default) | configurable
    label.py       # LLM cluster labeling + 6-question mapping
  analysis/
    diagnostics.py # per-question rollup, representative quotes, volumes
  storage/
    io.py          # parquet/json read-write helpers, path conventions
```

---

## 6. Key technology choices & rationale

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Best scraping + NLP/embedding ecosystem. |
| Config/validation | pydantic-settings + YAML | Typed config, fails fast on bad input. |
| HTTP | httpx + tenacity | Async-capable, clean retry/backoff (NFR-5). |
| App Store | iTunes RSS feed | Public, no key, recent reviews. |
| Play Store | google-play-scraper | No official public reviews API; community standard. |
| Reddit | PRAW (OAuth) | Official, compliant API access. |
| Storage | Parquet + JSON on disk | Zero infra, fast, portable (NFR-1). |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) default | Free, local, good enough; OpenAI opt-in via env. |
| Clustering | HDBSCAN (+ UMAP optional) | No need to pre-specify k; handles noise. |
| LLM labeling | Anthropic/OpenAI via env | Short, cheap calls — one per cluster, not per record. |
| CLI | Typer | Ergonomic subcommands for stage-by-stage runs. |

---

## 7. Data & directory layout

```
data/
  raw/<source>/run=<ts>/*.json   # immutable source payloads (resumable cache)
  processed/reviews.parquet      # canonical, deduped
  processed/reviews_embedded.parquet
  interim/clusters.json
reports/
  diagnosis.json                 # machine-readable per-question rollup
  diagnosis.md                   # deck-ready, quotes hyperlinked to source_url
```

Raw is write-once; re-runs of later stages never re-hit the network unless `--refresh` is passed (NFR-5 resumability).

---

## 8. Configuration model

`config/sources.yaml` declares *what*; `.env` holds *secrets*. Example shape:

```yaml
window_days: 90
sources:
  app_store:
    enabled: true
    app_id: "324684580"        # Spotify iOS
    countries: ["us", "gb", "in"]
  play_store:
    enabled: true
    app_id: "com.spotify.music"
    lang: "en"
    countries: ["us", "gb", "in"]
  reddit:
    enabled: true
    subreddits: ["spotify", "Music", "truespotify"]
    queries: ["discover", "recommendation", "new music", "discover weekly"]
embedding:
  provider: "local"            # local | openai
  model: "all-MiniLM-L6-v2"
clustering:
  algorithm: "hdbscan"
  min_cluster_size: 15
labeling:
  provider: "anthropic"        # anthropic | openai
```

---

## 9. Failure & rate-limit handling

- All network calls wrapped with `tenacity` exponential backoff + jitter.
- Per-source rate caps configurable; collectors sleep to stay under them.
- Each run writes a manifest (counts, errors, timing) to `reports/run_manifest.json`.
- Idempotent dedupe on `id` means re-runs merge cleanly rather than duplicate.

---

## 10. Phase boundaries

- **Phase 0 (this scaffold):** interfaces, stubs, config, docs, env. No live data.
- **Phase 1:** implement collectors + consolidation against real data.
- **Phase 2:** embedding → clustering → LLM labeling → diagnosis report.
- **Phase 3:** hosted/queryable workflow link + deck artefact; optional forum/social collectors.
