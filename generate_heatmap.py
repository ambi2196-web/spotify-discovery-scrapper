"""
Generate the heatmap dashboard by injecting real pipeline data into heatmap_template.html.
Embeds the full catalogued review set (reviews -> cluster -> theme -> diagnostic question)
so every cell/theme/question in the dashboard is backed by browsable reviews.
Run: python generate_heatmap.py
"""
import json, sys
from pathlib import Path
from collections import defaultdict

ROOT      = Path(__file__).parent
DIAGNOSIS = ROOT / "reports" / "diagnosis.json"
CLUSTERS  = ROOT / "data" / "interim" / "clusters.json"
REVIEWS   = ROOT / "data" / "processed" / "reviews_embedded.parquet"
TEMPLATE  = ROOT / "heatmap_template.html"
OUT       = ROOT / "reports" / "heatmap_dashboard.html"

if not DIAGNOSIS.exists():
    sys.exit("ERROR: reports/diagnosis.json not found.")
if not TEMPLATE.exists():
    sys.exit("ERROR: heatmap_template.html not found.")

diagnosis = json.loads(DIAGNOSIS.read_text(encoding="utf-8"))
clusters  = json.loads(CLUSTERS.read_text(encoding="utf-8")) if CLUSTERS.exists() else []

source_counts = {"app_store": 0, "play_store": 0, "reddit": 0}
total_reviews = 0
reviews_payload = []
cluster_meta = {}
for c in clusters:
    cluster_meta[c["cluster_id"]] = {
        "label": c.get("label", "Cluster {}".format(c["cluster_id"])),
        "summary": c.get("summary", ""),
        "questions": c.get("diagnostic_questions", []),
        "size": c.get("size", 0),
    }

try:
    import pandas as pd
    df = pd.read_parquet(REVIEWS)
    total_reviews = len(df)
    for src in source_counts:
        source_counts[src] = int((df["source"] == src).sum())
    keep = df[df["cluster_id"].isin(cluster_meta.keys())].copy().sort_values("created_at", ascending=False)
    for row in keep.itertuples(index=False):
        txt = (row.text or "").strip()
        if not txt:
            continue
        try:
            created = row.created_at.strftime("%Y-%m-%d")
        except Exception:
            created = str(row.created_at)[:10]
        reviews_payload.append({
            "t": txt, "s": row.source,
            "r": int(row.rating) if row.rating else 0,
            "d": created, "c": int(row.cluster_id), "u": row.source_url or "",
        })
except Exception as e:
    print("Warning: parquet not loaded ({}). Falling back to stored quotes.".format(e))
    total_reviews = sum(q["total_volume"] for q in diagnosis.values())
    for qid, qdata in diagnosis.items():
        for t in qdata.get("themes", []):
            for qt in t.get("quotes", []):
                reviews_payload.append({
                    "t": qt.get("text", ""), "s": qt.get("source", ""),
                    "r": int(qt.get("rating") or 0), "d": (qt.get("created_at") or "")[:10],
                    "c": t.get("cluster_id", -1), "u": qt.get("source_url", ""),
                })

Q_LABELS = {"1":"Awareness","2":"Trust","3":"Effort","4":"Relevance","5":"Context","6":"Agency"}
Q_COLORS = {"1":"#10b981","2":"#3b82f6","3":"#ef4444","4":"#8b5cf6","5":"#06b6d4","6":"#f97316"}

theme_map = defaultdict(lambda: {"cells": {}, "total": 0, "summary": "", "confidence": "medium", "quotes": [], "cluster_id": -1})
for qid, qdata in diagnosis.items():
    for t in qdata.get("themes", []):
        e = theme_map[t["theme_label"]]
        e["cells"][qid] = {"volume": t["volume"]}
        e["total"] += t["volume"]
        if e["cluster_id"] == -1:
            e["cluster_id"] = t.get("cluster_id", -1)
        if not e["summary"]:
            e["summary"] = t["summary"]
        if not e["quotes"]:
            e["quotes"] = t.get("quotes", [])[:3]
        if t.get("confidence") == "high":
            e["confidence"] = "high"

heatmap_rows = sorted(
    [{"label": k, "cells": v["cells"], "total": v["total"], "summary": v["summary"],
      "confidence": v["confidence"], "quotes": v["quotes"], "cluster_id": v["cluster_id"]}
     for k, v in theme_map.items()],
    key=lambda x: x["total"], reverse=True)[:18]

top_themes = []
for r in heatmap_rows[:10]:
    dom_q = max(r["cells"], key=lambda q: r["cells"][q]["volume"])
    top_themes.append({"label": r["label"], "volume": r["total"], "summary": r["summary"],
        "confidence": r["confidence"], "quotes": r["quotes"], "question": int(dom_q),
        "cells": r["cells"], "cluster_id": r["cluster_id"]})

payload = {
    "total_reviews": total_reviews, "total_clusters": len(clusters), "source_counts": source_counts,
    "q_totals": {qid: q["total_volume"] for qid, q in diagnosis.items()},
    "q_labels": Q_LABELS, "q_colors": Q_COLORS, "heatmap_rows": heatmap_rows, "top_themes": top_themes,
    "reviews": reviews_payload, "clusters": {str(cid): m for cid, m in cluster_meta.items()},
    "catalogued_count": len(reviews_payload),
    "diagnosis": {qid: {"question": q["question"], "total_volume": q["total_volume"],
        "theme_count": q["theme_count"],
        "themes": [{"theme_label": t["theme_label"], "volume": t["volume"], "summary": t["summary"],
            "confidence": t.get("confidence","medium"), "cluster_id": t.get("cluster_id",-1),
            "quotes": t.get("quotes",[])[:3]} for t in q.get("themes", [])]}
        for qid, q in diagnosis.items()},
}

html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA_JSON*/", json.dumps(payload, ensure_ascii=False))
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print("Written: {}  ({} bytes, {} reviews embedded)".format(OUT, len(html), len(reviews_payload)))
