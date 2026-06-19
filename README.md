# Scrapper

Multi-source review-analysis pipeline for the Spotify Growth case study. Ingests user feedback (App Store, Play Store, Reddit), then **embeds → clusters → LLM-labels** it to diagnose **why users don't discover new music**, mapped to six diagnostic questions.

See [`REQUIREMENTS.md`](./REQUIREMENTS.md) and [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

## Pipeline

`collect → consolidate → embed → cluster → label → diagnose`

Each stage reads/writes files on disk and can run independently.

## Quickstart (Phase 1+)

```bash
# 1. create env
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

# 2. configure
cp .env.example .env        # fill in Reddit + (optional) LLM keys
#   edit config/sources.yaml for app ids, subreddits, queries, window

# 3. run
scrapper run all            # full pipeline
scrapper run collect        # a single stage
scrapper query --question 4 # themes for diagnostic question N
```

## Status

**Phase 0 complete** — requirements, architecture, environment scaffold, and stage interfaces are in place. Stage logic is stubbed and ready to implement in Phase 1.

## Layout

```
scrapper/
├── REQUIREMENTS.md
├── docs/ARCHITECTURE.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── config/sources.yaml
├── src/scrapper/        # package: collectors, pipeline, analysis, storage
├── data/                # raw + processed (gitignored)
├── reports/             # diagnosis outputs (gitignored)
└── tests/
```
