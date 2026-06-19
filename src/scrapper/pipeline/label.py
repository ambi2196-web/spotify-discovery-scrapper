"""Stage 5: LLM labels each cluster + maps it to the six diagnostic questions.
Phase 1 implementation."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from scrapper import DIAGNOSTIC_QUESTIONS
from scrapper.models import Cluster

log = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
You are a product analyst studying why Spotify users struggle to discover new music.

Below are representative user quotes from ONE cluster of reviews/comments.
Analyze them and respond with a JSON object with EXACTLY these fields:
- "label": a short theme name (4-7 words, noun phrase)
- "summary": one sentence describing what users are saying (max 25 words)
- "diagnostic_questions": list of 1-3 integers from 1-6 this theme maps to
- "confidence": "high" | "medium" | "low"

The six diagnostic questions are:
{questions}

QUOTES:
{quotes}

Respond ONLY with valid JSON. No explanation, no markdown fences."""


def run(
    in_path: Path,
    out_path: Path,
    provider: str = "anthropic",
    model: str = "claude-haiku-4-5-20251001",
    max_quotes: int = 5,
) -> int:
    """Label each cluster with LLM, write clusters.json. Returns number of clusters labeled."""
    df = pd.read_parquet(in_path)
    if df.empty or "cluster_id" not in df.columns:
        log.warning("No clustered data found. Run cluster stage first.")
        return 0

    cluster_ids = sorted(df["cluster_id"].unique())
    # -1 = noise; we label everything except noise
    cluster_ids = [c for c in cluster_ids if c != -1]
    log.info("Labeling %d clusters with %s/%s …", len(cluster_ids), provider, model)

    questions_str = "\n".join(f"{k}. {v}" for k, v in DIAGNOSTIC_QUESTIONS.items())
    llm = _build_llm(provider, model)
    clusters: list[Cluster] = []

    for cid in cluster_ids:
        subset = df[df["cluster_id"] == cid]
        # Sample representative quotes (prefer longer, more informative texts)
        subset_sorted = subset.copy()
        subset_sorted["_len"] = subset_sorted["text"].str.len()
        sample = subset_sorted.nlargest(max_quotes, "_len")[["id", "text"]].to_dict("records")

        quotes_str = "\n\n".join(f'- "{r["text"][:400]}"' for r in sample)
        prompt = PROMPT_TEMPLATE.format(questions=questions_str, quotes=quotes_str)

        try:
            raw_response = llm(prompt)
            parsed = _parse_llm_response(raw_response)
        except Exception as exc:
            log.warning("Cluster %d labeling failed: %s", cid, exc)
            parsed = {
                "label": f"Theme {cid}",
                "summary": "Could not label automatically.",
                "diagnostic_questions": [],
                "confidence": "low",
            }

        cluster = Cluster(
            cluster_id=int(cid),
            label=parsed.get("label", f"Theme {cid}"),
            summary=parsed.get("summary", ""),
            diagnostic_questions=parsed.get("diagnostic_questions", []),
            size=len(subset),
            representative_quote_ids=[r["id"] for r in sample],
        )
        clusters.append(cluster)
        log.info(
            "Cluster %d → '%s' (Q%s, n=%d)",
            cid, cluster.label,
            cluster.diagnostic_questions, cluster.size,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([asdict(c) for c in clusters], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Wrote %d cluster labels to %s", len(clusters), out_path)
    return len(clusters)


def _build_llm(provider: str, model: str):
    """Return a callable: prompt -> str."""
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic not installed. Run: pip install anthropic")
        import os
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        def call(prompt: str) -> str:
            msg = client.messages.create(
                model=model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text

        return call

    elif provider == "openai":
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")
        import os
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        def call(prompt: str) -> str:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            return resp.choices[0].message.content

        return call

    else:
        raise ValueError(f"Unknown LLM provider: {provider!r}. Use 'anthropic' or 'openai'.")


def _parse_llm_response(text: str) -> dict:
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    data = json.loads(text)
    # Validate diagnostic_questions are ints in 1-6
    dqs = data.get("diagnostic_questions", [])
    data["diagnostic_questions"] = [int(q) for q in dqs if 1 <= int(q) <= 6]
    return data
