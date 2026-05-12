"""
Generate a Brand24-style HTML analysis report from the local database.

Usage:
    python report.py              # last 14 days
    python report.py --days 30
    python report.py --open       # auto-open in browser
"""
import argparse
import json
import os
import sqlite3
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "press_narges.db"

# Estimated reach per platform tier (avg unique audience per item)
_REACH_ESTIMATES = {
    ("Tier 1", "Online"): 250_000,
    ("Tier 1", "Print"): 180_000,
    ("Tier 2", "Online"): 45_000,
    ("Tier 2", "Print"): 30_000,
    ("Tier 3", "Online"): 8_000,
    ("YouTube", "YouTube"): None,   # use actual view count
    ("Bluesky", "Bluesky"): None,   # use likes as proxy
    ("X", "X"): None,
    ("TikTok", "TikTok"): None,
}

# AVE rate per platform/tier (cost per 1000 impressions in £)
_AVE_CPM = {
    "Tier 1": 25,
    "Tier 2": 12,
    "Tier 3": 4,
    "YouTube": 8,
    "Bluesky": 3,
    "X": 5,
    "TikTok": 6,
}

_TOPIC_RULES = [
    ("BAFTA Win", ["bafta", "leading actress", "best actress", "award win"]),
    ("Nazanin / Prisoner 951", ["nazanin", "prisoner 951", "zaghari", "jailed", "briton in iran"]),
    ("Iranian Identity / Diaspora", ["iranian", "persian", "diaspora", "iran", "evin"]),
    ("Performance & Craft", ["performance", "acting", "portrayal", "role", "actress"]),
    ("Red Carpet / Fashion", ["fashion", "dress", "style", "red carpet", "outfit", "look"]),
    ("Career & Projects", ["new project", "film", "series", "cast", "upcoming"]),
]

_PLATFORM_COLOURS = {
    "Online": "#3b82f6",
    "YouTube": "#ef4444",
    "Print": "#6b7280",
    "Bluesky": "#0085ff",
    "X": "#000000",
    "TikTok": "#010101",
    "TikTok": "#fe2c55",
}


def _fetch(conn, days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    cur = conn.execute("SELECT * FROM press WHERE date >= ? ORDER BY date DESC", (cutoff,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetch_ig(conn, days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        cur = conn.execute("SELECT * FROM instagram_posts WHERE date >= ? ORDER BY date DESC", (cutoff,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []


def _estimate_reach(item):
    if item.get("views") and item["views"] > 0:
        return item["views"]
    key = (item.get("tier", "Tier 3"), item.get("platform", "Online"))
    return _REACH_ESTIMATES.get(key, 5000)


def _ave(item):
    reach = _estimate_reach(item)
    cpm_key = item.get("platform") if item.get("platform") in _AVE_CPM else item.get("tier", "Tier 3")
    cpm = _AVE_CPM.get(cpm_key, 4)
    return int((reach / 1000) * cpm)


def _classify_topic(item):
    text = ((item.get("title") or "") + " " + (item.get("snippet") or "")).lower()
    for topic, keywords in _TOPIC_RULES:
        if any(kw in text for kw in keywords):
            return topic
    return "Other"


def _timeline(items, days):
    counts = defaultdict(int)
    for item in items:
        if item.get("date"):
            counts[item["date"]] += 1
    start = datetime.now(timezone.utc) - timedelta(days=days)
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days + 1)]
    return dates, [counts.get(d, 0) for d in dates]


def build_report(items, ig_items, days):
    total = len(items)
    sentiment_counts = Counter(i.get("sentiment", "neutral") for i in items)
    platform_counts = Counter(i.get("platform", "Online") for i in items)
    tier_counts = Counter(i.get("tier", "Tier 3") for i in items)

    total_reach = sum(_estimate_reach(i) for i in items)
    total_ave = sum(_ave(i) for i in items)
    positive_pct = round(sentiment_counts.get("positive", 0) / max(total, 1) * 100)
    negative_pct = round(sentiment_counts.get("negative", 0) / max(total, 1) * 100)

    # Topics
    topic_data = defaultdict(lambda: {"count": 0, "reach": 0})
    for item in items:
        t = _classify_topic(item)
        topic_data[t]["count"] += 1
        topic_data[t]["reach"] += _estimate_reach(item)
    topics = sorted(topic_data.items(), key=lambda x: -x[1]["reach"])

    # Top influencers/sources
    source_data = defaultdict(lambda: {"count": 0, "reach": 0, "platform": ""})
    for item in items:
        s = item.get("source", "")
        source_data[s]["count"] += 1
        source_data[s]["reach"] += _estimate_reach(item)
        source_data[s]["platform"] = item.get("platform", "Online")
    top_sources = sorted(source_data.items(), key=lambda x: -x[1]["reach"])[:15]

    # Timeline
    dates, counts = _timeline(items, days)

    # Platform chart data
    plat_labels = list(platform_counts.keys())
    plat_values = [platform_counts[p] for p in plat_labels]
    plat_colours = [_PLATFORM_COLOURS.get(p, "#94a3b8") for p in plat_labels]

    # Top items
    top_items = sorted(items, key=lambda x: _estimate_reach(x), reverse=True)[:10]

    date_str = datetime.now().strftime("%d %B %Y")
    period_str = f"Last {days} days"

    platform_icon = {
        "Online": "🌐", "YouTube": "▶️", "Print": "📰",
        "Bluesky": "🦋", "X": "✖️", "TikTok": "🎵",
    }

    sentiment_colour = {"positive": "#22c55e", "neutral": "#94a3b8", "negative": "#ef4444"}

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Narges Rashidi — Press Report {date_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8fafc; color: #1e293b; }}
  .header {{ background: #fff; border-bottom: 1px solid #e2e8f0; padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; }}
  .header h1 {{ font-size: 20px; font-weight: 700; }}
  .header .period {{ color: #64748b; font-size: 14px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px 32px; }}
  .overview {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #e2e8f0; }}
  .card .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
  .card .value {{ font-size: 28px; font-weight: 700; }}
  .card .sub {{ font-size: 13px; color: #64748b; margin-top: 4px; }}
  .card.positive .value {{ color: #22c55e; }}
  .card.negative .value {{ color: #ef4444; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
  .grid3 {{ display: grid; grid-template-columns: 2fr 1fr; gap: 24px; margin-bottom: 24px; }}
  .panel {{ background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 24px; }}
  .panel h2 {{ font-size: 15px; font-weight: 600; margin-bottom: 20px; color: #0f172a; }}
  .topic-row {{ display: flex; align-items: center; margin-bottom: 14px; gap: 12px; }}
  .topic-name {{ width: 220px; font-size: 14px; font-weight: 500; flex-shrink: 0; }}
  .topic-bar-wrap {{ flex: 1; background: #f1f5f9; border-radius: 4px; height: 8px; }}
  .topic-bar {{ background: #3b82f6; border-radius: 4px; height: 8px; }}
  .topic-meta {{ font-size: 13px; color: #64748b; width: 140px; text-align: right; flex-shrink: 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 8px 12px; color: #64748b; font-weight: 500; border-bottom: 2px solid #f1f5f9; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #f8fafc; vertical-align: middle; }}
  tr:hover td {{ background: #f8fafc; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }}
  .badge-positive {{ background: #dcfce7; color: #16a34a; }}
  .badge-neutral {{ background: #f1f5f9; color: #475569; }}
  .badge-negative {{ background: #fee2e2; color: #dc2626; }}
  .badge-t1 {{ background: #fee2e2; color: #dc2626; }}
  .badge-t2 {{ background: #ffedd5; color: #c2410c; }}
  .badge-t3 {{ background: #f1f5f9; color: #475569; }}
  .plat-badge {{ display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; background: #f1f5f9; color: #334155; }}
  a {{ color: #3b82f6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .chart-wrap {{ position: relative; height: 240px; }}
  .chart-wrap-sm {{ position: relative; height: 200px; }}
  .footer {{ text-align: center; color: #94a3b8; font-size: 12px; padding: 32px; }}
  @media (max-width: 900px) {{
    .overview {{ grid-template-columns: repeat(3, 1fr); }}
    .grid2, .grid3 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>📊 Narges Rashidi — Press & Social Monitor</h1>
    <div class="period">{period_str} &nbsp;·&nbsp; Generated {date_str}</div>
  </div>
</div>

<div class="container">

<!-- Overview cards -->
<div class="overview">
  <div class="card">
    <div class="label">Total mentions</div>
    <div class="value">{total:,}</div>
    <div class="sub">across all sources</div>
  </div>
  <div class="card">
    <div class="label">Total reach</div>
    <div class="value">{_fmt_reach(total_reach)}</div>
    <div class="sub">estimated impressions</div>
  </div>
  <div class="card">
    <div class="label">AVE</div>
    <div class="value">${total_ave:,}</div>
    <div class="sub">ad value equivalent</div>
  </div>
  <div class="card positive">
    <div class="label">Positive</div>
    <div class="value">{positive_pct}%</div>
    <div class="sub">{sentiment_counts.get('positive', 0)} mentions</div>
  </div>
  <div class="card negative">
    <div class="label">Negative</div>
    <div class="value">{negative_pct}%</div>
    <div class="sub">{sentiment_counts.get('negative', 0)} mentions</div>
  </div>
  <div class="card">
    <div class="label">Tier 1 hits</div>
    <div class="value">{tier_counts.get('Tier 1', 0)}</div>
    <div class="sub">national / major trade</div>
  </div>
</div>

<!-- Timeline + Platform split -->
<div class="grid3">
  <div class="panel">
    <h2>Mentions over time</h2>
    <div class="chart-wrap">
      <canvas id="timelineChart"></canvas>
    </div>
  </div>
  <div class="panel">
    <h2>By platform</h2>
    <div class="chart-wrap">
      <canvas id="platformChart"></canvas>
    </div>
  </div>
</div>

<!-- Topic analysis -->
<div class="panel" style="margin-bottom:24px">
  <h2>Topic analysis</h2>
  {"".join(_topic_row(t, d, max(v["reach"] for _, v in topics) if topics else 1) for t, d in topics)}
</div>

<!-- Influencers table -->
<div class="panel" style="margin-bottom:24px">
  <h2>Top influencers & sources</h2>
  <table>
    <thead><tr>
      <th>Source</th><th>Platform</th><th>Mentions</th><th>Est. reach</th>
    </tr></thead>
    <tbody>
      {"".join(_source_row(s, d) for s, d in top_sources)}
    </tbody>
  </table>
</div>

<!-- Most impactful items -->
<div class="panel" style="margin-bottom:24px">
  <h2>Most impactful coverage</h2>
  <table>
    <thead><tr>
      <th>Title</th><th>Source</th><th>Date</th><th>Tier</th><th>Sentiment</th><th>Reach</th>
    </tr></thead>
    <tbody>
      {"".join(_item_row(i) for i in top_items)}
    </tbody>
  </table>
</div>

</div>

<div class="footer">Narges Rashidi Press Monitor · If I Only Knew · {date_str}</div>

<script>
const tl = document.getElementById('timelineChart');
new Chart(tl, {{
  type: 'line',
  data: {{
    labels: {json.dumps(dates[-30:])},
    datasets: [{{
      label: 'Mentions',
      data: {json.dumps(counts[-30:])},
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.08)',
      borderWidth: 2,
      pointRadius: 2,
      fill: true,
      tension: 0.3,
    }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 11 }} }} }}, y: {{ beginAtZero: true, ticks: {{ stepSize: 1, font: {{ size: 11 }} }} }} }} }}
}});

const pl = document.getElementById('platformChart');
new Chart(pl, {{
  type: 'doughnut',
  data: {{
    labels: {json.dumps(plat_labels)},
    datasets: [{{ data: {json.dumps(plat_values)}, backgroundColor: {json.dumps(plat_colours)}, borderWidth: 2, borderColor: '#fff' }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ font: {{ size: 12 }}, padding: 12 }} }} }} }}
}});
</script>
</body>
</html>"""
    return html


def _fmt_reach(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def _topic_row(topic, data, max_reach):
    pct = int(data["reach"] / max(max_reach, 1) * 100)
    share = round(data["reach"] / max(max_reach, 1) * 100, 1)
    return f"""
  <div class="topic-row">
    <div class="topic-name">{topic}</div>
    <div class="topic-bar-wrap"><div class="topic-bar" style="width:{pct}%"></div></div>
    <div class="topic-meta">{data['count']} mentions &nbsp;·&nbsp; {_fmt_reach(data['reach'])} reach</div>
  </div>"""


def _source_row(source, data):
    plat = data["platform"]
    icon = {"Online": "🌐", "YouTube": "▶️", "Print": "📰", "Bluesky": "🦋", "X": "✖️", "TikTok": "🎵"}.get(plat, "🌐")
    return f"""<tr>
      <td><strong>{source}</strong></td>
      <td><span class="plat-badge">{icon} {plat}</span></td>
      <td>{data['count']}</td>
      <td>{_fmt_reach(data['reach'])}</td>
    </tr>"""


def _item_row(item):
    tier = item.get("tier", "Tier 3")
    tier_cls = {"Tier 1": "t1", "Tier 2": "t2", "Tier 3": "t3"}.get(tier, "t3")
    sent = item.get("sentiment", "neutral")
    title = (item.get("title") or "")[:80]
    url = item.get("url", "")
    source = (item.get("source") or "")[:30]
    date = item.get("date", "")
    return f"""<tr>
      <td><a href="{url}" target="_blank">{title}</a></td>
      <td>{source}</td>
      <td>{date}</td>
      <td><span class="badge badge-{tier_cls}">{tier}</span></td>
      <td><span class="badge badge-{sent}">{sent}</span></td>
      <td>{_fmt_reach(_estimate_reach(item))}</td>
    </tr>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    items = _fetch(conn, args.days)
    ig_items = _fetch_ig(conn, args.days)

    if not items:
        print("No items found. Run run.py first.")
        return

    html = build_report(items, ig_items, args.days)
    date_str = datetime.now().strftime("%Y-%m-%d")
    out = Path(__file__).parent / f"press_report_{date_str}.html"
    out.write_text(html)
    print(f"Report generated → {out.name}")

    if args.open:
        webbrowser.open(f"file://{out}")


if __name__ == "__main__":
    main()
