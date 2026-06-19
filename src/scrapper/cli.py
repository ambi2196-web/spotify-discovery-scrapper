"""Scrapper CLI. `scrapper run all | run <stage> | query --question N | sources`."""

from __future__ import annotations

import logging
import sys

import typer

import scrapper.collectors  # noqa: F401  (registers collectors on import)
from scrapper import DIAGNOSTIC_QUESTIONS, __version__
from scrapper.config import load_config
from scrapper.registry import available
from scrapper.storage import io as sio

app = typer.Typer(add_completion=False, help="Spotify discovery review-analysis pipeline.")

STAGES = ["collect", "consolidate", "embed", "cluster", "label", "diagnose", "all"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scrapper.cli")


@app.command()
def version() -> None:
    """Print version."""
    typer.echo(f"scrapper {__version__}")


@app.command()
def sources() -> None:
    """List registered collectors and which are enabled in config."""
    cfg = load_config()
    typer.echo(f"Registered: {', '.join(available())}")
    typer.echo(f"Enabled:    {', '.join(cfg.enabled_sources()) or '(none)'}")


@app.command()
def questions() -> None:
    """Print the six diagnostic questions."""
    for k, v in DIAGNOSTIC_QUESTIONS.items():
        typer.echo(f"  {k}. {v}")


@app.command()
def run(
    stage: str = typer.Argument("all", help=f"One of: {', '.join(STAGES)}"),
    refresh: bool = typer.Option(False, "--refresh", help="Re-fetch raw data even if cached."),
) -> None:
    """Run a pipeline stage (or all stages in sequence)."""
    if stage not in STAGES:
        typer.echo(f"[error] stage must be one of {STAGES}", err=True)
        raise typer.Exit(code=1)

    cfg = load_config()
    sio.ensure_dirs()

    def _header(s: str) -> None:
        typer.echo(f"\n{'─'*50}\n▶ {s}\n{'─'*50}")

    run_collect = stage in ("collect", "all")
    run_consolidate = stage in ("consolidate", "all")
    run_embed = stage in ("embed", "all")
    run_cluster = stage in ("cluster", "all")
    run_label = stage in ("label", "all")
    run_diagnose = stage in ("diagnose", "all")

    # ── 1. COLLECT ────────────────────────────────────────────────────────────
    if run_collect:
        _header("Stage 1 · Collect")
        from scrapper.models import CollectQuery
        from scrapper.registry import get_collector
        import json

        query = CollectQuery(
            window_days=cfg.window_days,
            countries=["us", "gb", "in"],
            subreddits=cfg.sources.get("reddit", {}).get("subreddits", []),
            queries=cfg.sources.get("reddit", {}).get("queries", []),
            limit=None,
            extra=cfg.sources,
        )

        for source_name in cfg.enabled_sources():
            try:
                collector_cls = get_collector(source_name)
            except KeyError:
                log.warning("No collector for '%s'", source_name)
                continue

            collector = collector_cls()
            out = sio.raw_dir(source_name)

            if not refresh and any(out.iterdir() if out.exists() else []):
                log.info("  %s: cached raw data found (use --refresh to re-fetch)", source_name)
                continue

            count = 0
            try:
                for raw in collector.collect(query):
                    count += 1
                    if count % 50 == 0:
                        log.info("  %s: %d records …", source_name, count)
            except Exception as exc:
                log.error("  %s collect failed: %s", source_name, exc)
                continue
            log.info("  %s: collected %d records total.", source_name, count)

    # ── 2. CONSOLIDATE ────────────────────────────────────────────────────────
    if run_consolidate:
        _header("Stage 2 · Consolidate")
        from scrapper.pipeline.consolidate import run as consolidate_run
        n = consolidate_run(sio.RAW, sio.REVIEWS)
        typer.echo(f"  → {n:,} canonical reviews written to {sio.REVIEWS.name}")

    # ── 3. EMBED ──────────────────────────────────────────────────────────────
    if run_embed:
        _header("Stage 3 · Embed")
        if not sio.REVIEWS.exists():
            typer.echo("[error] reviews.parquet not found. Run consolidate first.", err=True)
            raise typer.Exit(1)
        from scrapper.pipeline.embed import run as embed_run
        n = embed_run(
            sio.REVIEWS,
            sio.REVIEWS_EMBEDDED,
            provider=cfg.embedding.provider,
            model=cfg.embedding.model,
        )
        typer.echo(f"  → {n:,} records embedded.")

    # ── 4. CLUSTER ────────────────────────────────────────────────────────────
    if run_cluster:
        _header("Stage 4 · Cluster")
        if not sio.REVIEWS_EMBEDDED.exists():
            typer.echo("[error] reviews_embedded.parquet not found. Run embed first.", err=True)
            raise typer.Exit(1)
        from scrapper.pipeline.cluster import run as cluster_run
        n = cluster_run(
            sio.REVIEWS_EMBEDDED,
            sio.REVIEWS_EMBEDDED,  # in-place (adds cluster_id column)
            min_cluster_size=cfg.clustering.min_cluster_size,
            use_umap=cfg.clustering.use_umap,
        )
        typer.echo(f"  → {n} clusters found.")

    # ── 5. LABEL ──────────────────────────────────────────────────────────────
    if run_label:
        _header("Stage 5 · Label")
        if not sio.REVIEWS_EMBEDDED.exists():
            typer.echo("[error] reviews_embedded.parquet not found. Run cluster first.", err=True)
            raise typer.Exit(1)
        from scrapper.pipeline.label import run as label_run
        n = label_run(
            sio.REVIEWS_EMBEDDED,
            sio.CLUSTERS,
            provider=cfg.labeling.provider,
            model=cfg.labeling.model,
            max_quotes=cfg.labeling.max_quotes_per_cluster,
        )
        typer.echo(f"  → {n} clusters labeled.")

    # ── 6. DIAGNOSE ───────────────────────────────────────────────────────────
    if run_diagnose:
        _header("Stage 6 · Diagnose")
        if not sio.CLUSTERS.exists():
            typer.echo("[error] clusters.json not found. Run label first.", err=True)
            raise typer.Exit(1)
        from scrapper.analysis.diagnostics import run as diagnose_run
        diagnose_run(sio.CLUSTERS, sio.REVIEWS_EMBEDDED, sio.REPORTS)
        typer.echo(f"  → Report written to {sio.REPORTS}/")
        typer.echo(f"     {sio.DIAGNOSIS_JSON.name}")
        typer.echo(f"     {sio.DIAGNOSIS_MD.name}")

    if stage == "all":
        typer.echo("\n✓ Pipeline complete. Run `scrapper query --question 1` to explore results.")


@app.command()
def query(
    question: int = typer.Option(..., "--question", "-q", min=1, max=6, help="Question number 1-6"),
) -> None:
    """Show themes + representative quotes for a diagnostic question."""
    from scrapper.analysis.diagnostics import query as diag_query

    typer.echo(f"\nQ{question}: {DIAGNOSTIC_QUESTIONS[question]}\n{'─'*60}")
    try:
        result = diag_query(question, sio.REPORTS)
    except FileNotFoundError as e:
        typer.echo(f"[error] {e}", err=True)
        raise typer.Exit(1)

    for theme in result.get("themes", []):
        typer.echo(f"\n■ {theme['theme_label']}  (n={theme['volume']})")
        typer.echo(f"  {theme['summary']}")
        for q in theme.get("quotes", [])[:2]:
            source = q["source"].replace("_", " ").title()
            typer.echo(f"  › \"{q['text'][:200]}\"")
            typer.echo(f"    — {source}  {q.get('source_url', '')}")


if __name__ == "__main__":
    app()
