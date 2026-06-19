"""
Generate an interactive heatmap dashboard from the scrapper pipeline output.
Reads:  reports/diagnosis.json  +  data/interim/clusters.json  +  reviews_embedded.parquet
Writes: reports/heatmap_dashboard.html

Run: python generate_heatmap.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
DIAGNOSIS   = ROOT / "reports" / "diagnosis.json"
CLUSTERS    = ROOT / "data" / "interim" / "clusters.json"
REVIEWS     = ROOT / "data" / "processed" / "reviews_embedded.parquet"
OUT         = ROOT / "reports" / "heatmap_dashboard.html"

# ── Load data ─────────────────────────────────────────────────────────────────
if not DIAGNOSIS.exists():
    sys.exit(f"ERROR: {DIAGNOSIS} not found. Run `python -m scrapper.cli run diagnose` first.")

diagnosis  = json.loads(DIAGNOSIS.read_text(encoding="utf-8"))
clusters   = json.loads(CLUSTERS.read_text(encoding="utf-8")) if CLUSTERS.exists() else []

# Load source breakdown from parquet
source_counts = {"app_store": 0, "play_store": 0, "reddit": 0}
q_source = {str(i): {"app_store": 0, "play_store": 0, "reddit": 0} for i in range(1, 7)}
total_reviews = 0

try:
    import pandas as pd
    df = pd.read_parquet(REVIEWS)
    total_reviews = len(df)
    for src in source_counts:
        source_counts[src] = int((df["source"] == src).sum())

    # Map cluster_id -> diagnostic_questions
    cid_to_qs = {c["cluster_id"]: c["diagnostic_questions"] for c in clusters}
    for _, row in df.iterrows():
        cid = row.get("cluster_id")
        src = row.get("source", "")
        if cid is not None and cid != -1 and src in source_counts:
            for q in cid_to_qs.get(int(cid), []):
                q_source[str(q)][src] += 1
except Exception as e:
    print(f"Warning: could not load parquet ({e}). Using diagnosis.json counts only.")
    total_reviews = sum(q["total_volume"] for q in diagnosis.values())

# ── Build heatmap data ────────────────────────────────────────────────────────
Q_LABELS = {
    "1": "Awareness",
    "2": "Trust",
    "3": "Effort",
    "4": "Relevance",
    "5": "Context",
    "6": "Agency",
}
Q_COLORS = {
    "1": "#10b981",
    "2": "#3b82f6",
    "3": "#ef4444",
    "4": "#8b5cf6",
    "5": "#06b6d4",
    "6": "#f97316",
}

# Heatmap: themes × questions  (value = volume of reviews in that cell)
all_themes = []
for qid, qdata in diagnosis.items():
    for theme in qdata.get("themes", []):
        all_themes.append({
            "label": theme["theme_label"],
            "volume": theme["volume"],
            "question": int(qid),
            "q_label": Q_LABELS[qid],
            "summary": theme["summary"],
            "confidence": theme.get("confidence", "medium"),
            "quotes": theme.get("quotes", [])[:2],
        })

# Sort themes by volume descending, take top 25
all_themes.sort(key=lambda t: t["volume"], reverse=True)
top_themes = all_themes[:25]

# Per-question totals
q_totals = {qid: q["total_volume"] for qid, q in diagnosis.items()}
max_vol = max(q_totals.values()) if q_totals else 1

# ── Embed everything into the HTML ────────────────────────────────────────────
data_json = json.dumps({
    "total_reviews": total_reviews,
    "total_clusters": len(clusters),
    "source_counts": source_counts,
    "q_totals": q_totals,
    "q_labels": Q_LABELS,
    "q_colors": Q_COLORS,
    "q_source": q_source,
    "themes": top_themes,
    "diagnosis": {
        qid: {
            "question": q["question"],
            "total_volume": q["total_volume"],
            "theme_count": q["theme_count"],
            "themes": [
                {
                    "theme_label": t["theme_label"],
                    "volume": t["volume"],
                    "summary": t["summary"],
                    "confidence": t.get("confidence","medium"),
                    "quotes": t.get("quotes", [])[:3],
                }
                for t in q.get("themes", [])
            ]
        }
        for qid, q in diagnosis.items()
    },
}, ensure_ascii=False)

# ── HTML template ─────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spotify Discovery · Review Analysis Heatmap</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f0f0f;color:#fff;min-height:100vh}}
.header{{background:#181818;border-bottom:1px solid #2a2a2a;padding:18px 32px;display:flex;align-items:center;justify-content:space-between}}
.logo{{font-size:18px;font-weight:800;color:#fff}}.logo span{{color:#1DB954}}
.stats{{display:flex;gap:32px}}
.stat{{text-align:center}}.stat-v{{font-size:22px;font-weight:800;color:#1DB954}}.stat-l{{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}}
.content{{padding:28px 32px;max-width:1400px;margin:0 auto}}
h2{{font-size:15px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px}}
.section{{margin-bottom:36px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
.card{{background:#1a1a1a;border-radius:12px;padding:20px}}

/* Heatmap */
.heatmap-wrap{{overflow-x:auto}}
.heatmap{{border-collapse:collapse;width:100%;min-width:600px}}
.heatmap th{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;padding:8px 10px;text-align:center;white-space:nowrap}}
.heatmap td.theme-name{{font-size:12px;color:#ddd;padding:5px 12px 5px 0;white-space:nowrap;max-width:220px;overflow:hidden;text-overflow:ellipsis;text-align:left}}
.heatmap td.cell{{width:80px;height:32px;text-align:center;font-size:11px;font-weight:600;border-radius:4px;cursor:pointer;transition:transform .1s}}
.heatmap td.cell:hover{{transform:scale(1.08);z-index:10;position:relative}}
.vol-badge{{display:inline-block;background:#282828;border-radius:8px;padding:3px 9px;font-size:11px;color:#888}}

/* Question cards */
.q-card{{background:#1a1a1a;border-radius:12px;padding:18px;cursor:pointer;transition:border .15s;border:2px solid transparent}}
.q-card:hover{{border-color:#333}}
.q-num{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px}}
.q-title{{font-size:13px;font-weight:600;margin-bottom:8px;line-height:1.4}}
.q-bar-track{{height:6px;background:#333;border-radius:3px;overflow:hidden;margin-bottom:6px}}
.q-bar-fill{{height:100%;border-radius:3px;transition:width .6s ease}}
.q-meta{{font-size:11px;color:#666}}

/* Source bars */
.src-row{{display:flex;align-items:center;gap:10px;margin-bottom:10px}}
.src-label{{font-size:12px;color:#aaa;width:90px;flex-shrink:0}}
.src-track{{flex:1;height:10px;background:#282828;border-radius:5px;overflow:hidden}}
.src-fill{{height:100%;border-radius:5px}}
.src-count{{font-size:11px;color:#666;width:40px;text-align:right;flex-shrink:0}}

/* Theme list */
.theme-row{{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #222;cursor:pointer}}
.theme-row:last-child{{border-bottom:none}}
.theme-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.theme-info{{flex:1;min-width:0}}
.theme-label{{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.theme-summary{{font-size:11px;color:#666;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.theme-vol{{font-size:12px;color:#888;white-space:nowrap;flex-shrink:0}}
.conf-badge{{font-size:10px;padding:2px 7px;border-radius:8px;font-weight:600;flex-shrink:0}}
.conf-high{{background:rgba(29,185,84,.15);color:#1DB954}}
.conf-medium{{background:rgba(245,158,11,.15);color:#f59e0b}}
.conf-low{{background:rgba(107,114,128,.15);color:#9ca3af}}

/* Detail panel */
#detail{{display:none;position:fixed;top:0;right:0;width:420px;height:100vh;background:#1a1a1a;border-left:1px solid #2a2a2a;z-index:100;overflow-y:auto;padding:24px}}
#detail h3{{font-size:15px;font-weight:700;margin-bottom:4px}}
#detail .close{{position:absolute;top:16px;right:16px;background:#333;border:none;color:#fff;width:28px;height:28px;border-radius:50%;cursor:pointer;font-size:14px}}
.quote-card{{background:#111;border-radius:8px;padding:12px;margin-bottom:10px;border-left:3px solid #333}}
.quote-text{{font-size:13px;font-style:italic;color:#ccc;line-height:1.6;margin-bottom:6px}}
.quote-src{{font-size:11px;color:#555}}
</style>
</head>
<body>

<div class="header">
  <div class="logo">Spotify <span>Discovery</span> · Review Analysis</div>
  <div class="stats" id="header-stats"></div>
  <div style="font-size:12px;color:#555">Scrapper Pipeline v0.1.0</div>
</div>

<div class="content">

  <!-- Q overview cards -->
  <div class="section">
    <h2>Signal by Diagnostic Question</h2>
    <div class="grid3" id="q-cards"></div>
  </div>

  <!-- Heatmap -->
  <div class="section">
    <h2>Theme × Question Heatmap &nbsp;<span style="font-size:11px;color:#555;font-weight:400;text-transform:none;letter-spacing:0">(click any cell for quotes)</span></h2>
    <div class="card heatmap-wrap">
      <table class="heatmap" id="heatmap-table"></table>
    </div>
  </div>

  <!-- Bottom row -->
  <div class="grid2">

    <!-- Source breakdown -->
    <div class="section">
      <h2>Reviews by Source</h2>
      <div class="card">
        <canvas id="sourceChart" height="160"></canvas>
        <div style="margin-top:20px" id="src-bars"></div>
      </div>
    </div>

    <!-- Top themes -->
    <div class="section">
      <h2>Top 10 Themes by Volume</h2>
      <div class="card" id="top-themes"></div>
    </div>

  </div>

  <!-- Volume by question chart -->
  <div class="section">
    <h2>Review Volume per Question</h2>
    <div class="card"><canvas id="volChart" height="80"></canvas></div>
  </div>

</div>

<!-- Detail panel -->
<div id="detail">
  <button class="close" onclick="closeDetail()">✕</button>
  <div id="detail-content"></div>
</div>

<script>
const D = {data_json};
const QC = D.q_colors;
const QL = D.q_labels;

// ── Header stats ─────────────────────────────────────────────────────────────
document.getElementById('header-stats').innerHTML = `
  <div class="stat"><div class="stat-v">${{D.total_reviews.toLocaleString()}}</div><div class="stat-l">Reviews</div></div>
  <div class="stat"><div class="stat-v">${{D.total_clusters}}</div><div class="stat-l">Clusters</div></div>
  <div class="stat"><div class="stat-v">6</div><div class="stat-l">Questions</div></div>
  <div class="stat"><div class="stat-v">3</div><div class="stat-l">Sources</div></div>
`;

// ── Question cards ────────────────────────────────────────────────────────────
const maxVol = Math.max(...Object.values(D.q_totals));
const qCards = document.getElementById('q-cards');
Object.keys(D.q_labels).forEach(qid => {{
  const q = D.diagnosis[qid];
  if (!q) return;
  const pct = Math.round((q.total_volume / maxVol) * 100);
  const signal = pct >= 75 ? '⬆ Dominant' : pct >= 45 ? '● Strong' : '● Moderate';
  qCards.innerHTML += `
    <div class="q-card" onclick="showQuestion('${{qid}}')" style="border-color:${{QC[qid]}}22">
      <div class="q-num" style="color:${{QC[qid]}}">Q${{qid}} · ${{QL[qid]}}</div>
      <div class="q-title">${{q.question}}</div>
      <div class="q-bar-track"><div class="q-bar-fill" style="width:${{pct}}%;background:${{QC[qid]}}"></div></div>
      <div class="q-meta">${{q.theme_count}} themes · ${{q.total_volume.toLocaleString()}} reviews &nbsp; <span style="color:${{QC[qid]}};font-weight:600">${{signal}}</span></div>
    </div>`;
}});

// ── Heatmap ───────────────────────────────────────────────────────────────────
(function buildHeatmap() {{
  const table  = document.getElementById('heatmap-table');
  const qids   = ['1','2','3','4','5','6'];
  const themes = D.themes.slice(0, 20);

  // Header
  let thead = '<thead><tr><th style="text-align:left;padding-right:12px">Theme</th>';
  qids.forEach(q => {{
    thead += `<th style="color:${{QC[q]}}">${{QL[q]}}</th>`;
  }});
  thead += '<th>Vol</th></tr></thead>';

  // Find max for colour scaling
  const maxT = Math.max(...themes.map(t => t.volume));

  let tbody = '<tbody>';
  themes.forEach(theme => {{
    tbody += `<tr>`;
    tbody += `<td class="theme-name" title="${{theme.label}}">${{theme.label}}</td>`;
    qids.forEach(q => {{
      const isMatch = theme.question === parseInt(q);
      if (isMatch) {{
        const alpha = 0.2 + 0.8 * (theme.volume / maxT);
        const hex   = Math.round(alpha * 255).toString(16).padStart(2,'0');
        tbody += `<td class="cell" style="background:${{QC[q]}}${{hex}};color:#fff"
          onclick='showTheme(${{JSON.stringify(theme)}})'>${{theme.volume}}</td>`;
      }} else {{
        tbody += `<td class="cell" style="background:#1a1a1a;color:#333">—</td>`;
      }}
    }});
    tbody += `<td style="padding-left:8px"><span class="vol-badge">${{theme.volume}}</span></td>`;
    tbody += `</tr>`;
  }});
  tbody += '</tbody>';
  table.innerHTML = thead + tbody;
}})();

// ── Source bars ───────────────────────────────────────────────────────────────
const srcNames  = {{'app_store':'App Store','play_store':'Play Store','reddit':'Reddit'}};
const srcColors = {{'app_store':'#3b82f6','play_store':'#10b981','reddit':'#f97316'}};
const maxSrc    = Math.max(...Object.values(D.source_counts));
const srcBars   = document.getElementById('src-bars');
Object.keys(srcNames).forEach(src => {{
  const n   = D.source_counts[src] || 0;
  const pct = maxSrc > 0 ? Math.round(n/maxSrc*100) : 0;
  srcBars.innerHTML += `
    <div class="src-row">
      <div class="src-label">${{srcNames[src]}}</div>
      <div class="src-track"><div class="src-fill" style="width:${{pct}}%;background:${{srcColors[src]}}"></div></div>
      <div class="src-count">${{n.toLocaleString()}}</div>
    </div>`;
}});

// Donut chart
new Chart(document.getElementById('sourceChart'), {{
  type: 'doughnut',
  data: {{
    labels: Object.keys(srcNames).map(k => srcNames[k]),
    datasets: [{{
      data: Object.keys(srcNames).map(k => D.source_counts[k] || 0),
      backgroundColor: Object.keys(srcNames).map(k => srcColors[k]),
      borderWidth: 0,
    }}],
  }},
  options: {{
    responsive: true, cutout: '65%',
    plugins: {{ legend: {{ labels: {{ color:'#888', font: {{size:12}} }} }} }},
  }},
}});

// ── Volume bar chart ─────────────────────────────────────────────────────────
new Chart(document.getElementById('volChart'), {{
  type: 'bar',
  data: {{
    labels: Object.keys(QL).map(q => `Q${{q}} ${{QL[q]}}`),
    datasets: [{{
      label: 'Review volume',
      data: Object.keys(D.q_totals).map(q => D.q_totals[q]),
      backgroundColor: Object.keys(QL).map(q => QC[q]),
      borderRadius: 6,
    }}],
  }},
  options: {{
    responsive: true, indexAxis: 'y',
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color:'#222' }}, ticks: {{ color:'#666' }} }},
      y: {{ grid: {{ display:false }}, ticks: {{ color:'#aaa' }} }},
    }},
  }},
}});

// ── Top themes list ───────────────────────────────────────────────────────────
const topEl = document.getElementById('top-themes');
D.themes.slice(0,10).forEach(t => {{
  const color = QC[String(t.question)];
  topEl.innerHTML += `
    <div class="theme-row" onclick='showTheme(${{JSON.stringify(t)}})'>
      <div class="theme-dot" style="background:${{color}}"></div>
      <div class="theme-info">
        <div class="theme-label">${{t.label}}</div>
        <div class="theme-summary">${{t.summary}}</div>
      </div>
      <span class="conf-badge conf-${{t.confidence}}">${{t.confidence}}</span>
      <div class="theme-vol">${{t.volume}} reviews</div>
    </div>`;
}});

// ── Detail panel ─────────────────────────────────────────────────────────────
function showTheme(t) {{
  const color = QC[String(t.question)];
  let html = `
    <div style="border-left:4px solid ${{color}};padding-left:12px;margin-bottom:16px">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:${{color}}">Q${{t.question}} · ${{QL[String(t.question)]}}</div>
      <h3>${{t.label}}</h3>
      <p style="font-size:13px;color:#888;margin-top:4px">${{t.summary}}</p>
    </div>
    <div style="display:flex;gap:10px;margin-bottom:16px">
      <div style="background:#222;border-radius:8px;padding:10px 16px;flex:1;text-align:center">
        <div style="font-size:20px;font-weight:800;color:${{color}}">${{t.volume}}</div>
        <div style="font-size:10px;color:#555;text-transform:uppercase">Reviews</div>
      </div>
      <div style="background:#222;border-radius:8px;padding:10px 16px;flex:1;text-align:center">
        <div style="font-size:20px;font-weight:800;color:${{color}}">${{t.confidence}}</div>
        <div style="font-size:10px;color:#555;text-transform:uppercase">Confidence</div>
      </div>
    </div>
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#555;margin-bottom:10px">Representative Quotes</div>
  `;
  (t.quotes || []).forEach(q => {{
    const src = (q.source||'').replace('_',' ');
    const rating = q.rating ? ` · ${{q.rating}}★` : '';
    html += `
      <div class="quote-card" style="border-color:${{color}}44">
        <div class="quote-text">"${{q.text ? q.text.substring(0,300) : ''}}${{q.text && q.text.length>300?'…':''}}"</div>
        <div class="quote-src">${{src}}${{rating}}</div>
      </div>`;
  }});
  if (!t.quotes || t.quotes.length === 0) {{
    html += '<p style="font-size:12px;color:#555">No quotes stored for this theme.</p>';
  }}
  document.getElementById('detail-content').innerHTML = html;
  document.getElementById('detail').style.display = 'block';
}}

function showQuestion(qid) {{
  const q = D.diagnosis[qid];
  if (!q) return;
  const color = QC[qid];
  let html = `
    <div style="border-left:4px solid ${{color}};padding-left:12px;margin-bottom:16px">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:${{color}}">Q${{qid}} · ${{QL[qid]}}</div>
      <h3>${{q.question}}</h3>
    </div>
    <div style="display:flex;gap:10px;margin-bottom:20px">
      <div style="background:#222;border-radius:8px;padding:10px 16px;flex:1;text-align:center">
        <div style="font-size:20px;font-weight:800;color:${{color}}">${{q.total_volume}}</div>
        <div style="font-size:10px;color:#555;text-transform:uppercase">Reviews</div>
      </div>
      <div style="background:#222;border-radius:8px;padding:10px 16px;flex:1;text-align:center">
        <div style="font-size:20px;font-weight:800;color:${{color}}">${{q.theme_count}}</div>
        <div style="font-size:10px;color:#555;text-transform:uppercase">Themes</div>
      </div>
    </div>
  `;
  q.themes.forEach(t => {{
    html += `
      <div style="background:#111;border-radius:8px;padding:12px;margin-bottom:10px;border-left:3px solid ${{color}}">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <strong style="font-size:13px">${{t.theme_label}}</strong>
          <span class="vol-badge">${{t.volume}}</span>
        </div>
        <p style="font-size:12px;color:#888;margin:0 0 8px">${{t.summary}}</p>
    `;
    (t.quotes||[]).slice(0,2).forEach(q => {{
      html += `<div style="font-size:11px;font-style:italic;color:#555;margin-top:4px;padding-left:8px;border-left:2px solid #333">"${{(q.text||'').substring(0,150)}}…"</div>`;
    }});
    html += `</div>`;
  }});
  document.getElementById('detail-content').innerHTML = html;
  document.getElementById('detail').style.display = 'block';
}}

function closeDetail() {{
  document.getElementById('detail').style.display = 'none';
}}
</script>
</body>
</html>"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print(f"Dashboard written to: {OUT}")
print("Open it in any browser.")
