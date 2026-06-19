"""
Generate the heatmap dashboard by injecting real pipeline data into heatmap_template.html.
Run: python generate_heatmap.py
"""
import json
import sys
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
try:
    import pandas as pd
    df = pd.read_parquet(REVIEWS)
    total_reviews = len(df)
    for src in source_counts:
        source_counts[src] = int((df["source"] == src).sum())
except Exception as e:
    print("Warning: parquet not loaded ({}). Using diagnosis counts.".format(e))
    total_reviews = sum(q["total_volume"] for q in diagnosis.values())

Q_LABELS = {"1":"Awareness","2":"Trust","3":"Effort","4":"Relevance","5":"Context","6":"Agency"}
Q_COLORS = {"1":"#10b981","2":"#3b82f6","3":"#ef4444","4":"#8b5cf6","5":"#06b6d4","6":"#f97316"}

theme_map = defaultdict(lambda: {"cells": {}, "total": 0, "summary": "", "confidence": "medium", "quotes": []})
for qid, qdata in diagnosis.items():
    for t in qdata.get("themes", []):
        label = t["theme_label"]
        e = theme_map[label]
        e["cells"][qid] = {"volume": t["volume"]}
        e["total"] += t["volume"]
        if not e["summary"]:
            e["summary"] = t["summary"]
        if not e["quotes"]:
            e["quotes"] = t.get("quotes", [])[:3]
        if t.get("confidence") == "high":
            e["confidence"] = "high"

heatmap_rows = sorted(
    [{"label": k, "cells": v["cells"], "total": v["total"],
      "summary": v["summary"], "confidence": v["confidence"], "quotes": v["quotes"]}
     for k, v in theme_map.items()],
    key=lambda x: x["total"], reverse=True
)[:18]

top_themes = []
for r in heatmap_rows[:10]:
    dom_q = max(r["cells"], key=lambda q: r["cells"][q]["volume"])
    top_themes.append({
        "label": r["label"], "volume": r["total"],
        "summary": r["summary"], "confidence": r["confidence"],
        "quotes": r["quotes"], "question": int(dom_q), "cells": r["cells"],
    })

payload = {
    "total_reviews": total_reviews,
    "total_clusters": len(clusters),
    "source_counts": source_counts,
    "q_totals": {qid: q["total_volume"] for qid, q in diagnosis.items()},
    "q_labels": Q_LABELS,
    "q_colors": Q_COLORS,
    "heatmap_rows": heatmap_rows,
    "top_themes": top_themes,
    "diagnosis": {
        qid: {
            "question": q["question"],
            "total_volume": q["total_volume"],
            "theme_count": q["theme_count"],
            "themes": [
                {"theme_label": t["theme_label"], "volume": t["volume"],
                 "summary": t["summary"], "confidence": t.get("confidence","medium"),
                 "quotes": t.get("quotes",[])[:3]}
                for t in q.get("themes", [])
            ],
        }
        for qid, q in diagnosis.items()
    },
}

data_json = json.dumps(payload, ensure_ascii=False)
template  = TEMPLATE.read_text(encoding="utf-8")
html      = template.replace("/*DATA_JSON*/", data_json)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print("Written: {}  ({} bytes)".format(OUT, len(html)))
