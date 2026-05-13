"""
Narges Rashidi — Press Intelligence Dashboard
If I Only Knew PR

Run locally:  streamlit run dashboard.py
Cloud:        https://narges-press-monitor-538spugleugn6wtdypc4n2.streamlit.app
"""
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "press_narges.db"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Narges Rashidi · Press Intelligence",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ─────────────────────────────────────────────────────────────
ACCENT   = "#4f46e5"
TEAL     = "#0891b2"
GREEN    = "#059669"
RED      = "#dc2626"
AMBER    = "#d97706"
PINK     = "#db2777"
PURPLE   = "#7c3aed"
SLATE    = "#64748b"
DARK     = "#0f172a"
MUTED    = "#94a3b8"
BORDER   = "#e2e8f0"
BG_SOFT  = "#f8fafc"

CHART_PALETTE = [ACCENT, TEAL, GREEN, AMBER, RED, PURPLE, PINK, "#0ea5e9"]


# ── Minimal CSS — using st.html for reliable injection ───────────────────────
st.html("""
<style>
  /* Typography */
  html, body, [class*="st-"], [data-testid="stAppViewContainer"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
  }

  /* Hide deploy + main menu */
  [data-testid="stDeployButton"] { display: none; }
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }

  /* Sidebar polish */
  [data-testid="stSidebar"] {
    background: #0f172a;
  }
  [data-testid="stSidebar"] * { color: #e2e8f0; }
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] h4 { color: white; }
  [data-testid="stSidebar"] label { color: #94a3b8 !important; font-size: 12px !important; font-weight: 500; }
  [data-testid="stSidebar"] [data-baseweb="select"] > div,
  [data-testid="stSidebar"] input {
    background: #1e293b !important;
    border-color: #334155 !important;
    color: white !important;
  }
  [data-testid="stSidebar"] button {
    background: #4f46e5 !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
  }

  /* Main content padding */
  .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1500px; }

  /* Metric cards — proper styled cards */
  [data-testid="stMetric"] {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 18px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s, transform 0.2s;
  }
  [data-testid="stMetric"]:hover {
    box-shadow: 0 6px 20px rgba(0,0,0,0.08);
    transform: translateY(-1px);
  }
  [data-testid="stMetricLabel"] {
    font-size: 12px !important;
    color: #64748b !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.75rem !important;
    font-weight: 800 !important;
    color: #0f172a !important;
    letter-spacing: -0.02em;
    line-height: 1.1;
  }
  [data-testid="stMetricDelta"] {
    font-size: 12px !important;
    font-weight: 600 !important;
  }

  /* Section dividers */
  hr { border-color: #e2e8f0 !important; margin: 2rem 0 !important; }

  /* Tabs */
  [data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent !important;
    border-bottom: 1px solid #e2e8f0;
  }
  [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 10px 20px !important;
    font-weight: 500 !important;
    color: #64748b !important;
  }
  [aria-selected="true"][data-baseweb="tab"] {
    color: #4f46e5 !important;
    font-weight: 600 !important;
  }

  /* DataFrames */
  [data-testid="stDataFrame"] {
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    overflow: hidden;
  }

  /* Buttons */
  .stButton button {
    border-radius: 10px;
    font-weight: 600;
  }

  /* Selectbox */
  [data-baseweb="select"] > div {
    border-radius: 10px !important;
    border-color: #e2e8f0 !important;
  }

  /* Hero section */
  .hero {
    padding: 8px 0 24px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 32px;
  }
  .hero-eyebrow {
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  .hero-title {
    font-size: 28px;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.03em;
    margin: 0;
  }
  .hero-subtitle {
    color: #64748b;
    font-size: 15px;
    margin-top: 4px;
  }

  /* Story card */
  .story-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #4f46e5;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
    transition: all 0.15s;
  }
  .story-card:hover {
    border-left-color: #4338ca;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  }
  .story-title {
    font-size: 14px;
    font-weight: 600;
    color: #0f172a;
    margin: 0 0 6px;
    line-height: 1.4;
    text-decoration: none;
    display: block;
  }
  .story-title:hover { color: #4f46e5; }
  .story-meta {
    font-size: 12px;
    color: #64748b;
    margin-bottom: 8px;
  }
  .story-snippet {
    font-size: 13px;
    color: #475569;
    line-height: 1.5;
    margin: 0;
  }

  /* Pill badges */
  .pill {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 100px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 4px;
  }
  .pill-t1 { background: #e0e7ff; color: #4338ca; }
  .pill-t2 { background: #d1fae5; color: #047857; }
  .pill-t3 { background: #f1f5f9; color: #64748b; }
  .pill-pos { background: #d1fae5; color: #047857; }
  .pill-neg { background: #fee2e2; color: #b91c1c; }
  .pill-neu { background: #f1f5f9; color: #64748b; }

  /* Topic bar */
  .topic-bar-bg {
    background: #f1f5f9;
    height: 10px;
    border-radius: 100px;
    overflow: hidden;
  }
  .topic-bar-fill {
    background: linear-gradient(90deg, #4f46e5, #6366f1);
    height: 100%;
    border-radius: 100px;
  }
</style>
""")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe_int(v) -> int:
    try:
        return 0 if (v is None or (isinstance(v, float) and pd.isna(v))) else int(v)
    except Exception:
        return 0


def reach_est(row) -> int:
    tier, plat = str(row.get("tier") or "Tier 3"), str(row.get("platform") or "")
    v = _safe_int(row.get("views"))
    if plat == "YouTube":        return v
    if plat in ("TikTok","Facebook"): return v * 3
    if tier == "Tier 1":         return 850_000
    if tier == "Tier 2":         return 120_000
    return 15_000


def ave_est(row) -> float:
    tier, plat = str(row.get("tier") or "Tier 3"), str(row.get("platform") or "")
    v = _safe_int(row.get("views"))
    if plat == "YouTube":        return v * 0.003
    if plat in ("TikTok","Facebook"): return v * 0.002
    if tier == "Tier 1":         return 2500.0
    if tier == "Tier 2":         return 350.0
    return 75.0


def fmt_compact(n) -> str:
    n = int(n)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 10_000:    return f"{n/1_000:.0f}K"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return f"{n:,}"


def fmt_pct_delta(cur, prev, invert=False) -> str:
    if prev == 0:
        return "NEW" if cur > 0 else "—"
    pct = (cur - prev) / prev * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.0f}%"


def style_chart(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=20, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="-apple-system, sans-serif", color=DARK, size=12),
        legend=dict(
            orientation="h", y=1.12, x=0,
            font=dict(size=11, color=SLATE),
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor=BORDER,
            font=dict(family="-apple-system, sans-serif"),
        ),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(color=SLATE, size=11))
    fig.update_yaxes(gridcolor="#f1f5f9", zeroline=False, tickfont=dict(color=SLATE, size=11))
    return fig


def pill(text: str, kind: str) -> str:
    return f'<span class="pill pill-{kind}">{text}</span>'


def tier_pill(t) -> str:
    n = str(t or "Tier 3")[-1]
    return pill(str(t or ""), f"t{n}")


def sent_pill(s) -> str:
    s = (str(s) if s else "neutral").lower()
    return pill(s.capitalize(), s[:3])


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    data_dir = Path(__file__).parent / "data"
    parquet = data_dir / "press.parquet"
    ig_parquet = data_dir / "instagram.parquet"
    if parquet.exists():
        df = pd.read_parquet(parquet)
        ig = pd.read_parquet(ig_parquet) if ig_parquet.exists() else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM press ORDER BY date DESC", conn)
        try:
            ig = pd.read_sql_query("SELECT * FROM instagram_posts ORDER BY date DESC", conn)
        except Exception:
            ig = pd.DataFrame()
        conn.close()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if not ig.empty:
        ig["date"] = pd.to_datetime(ig["date"], errors="coerce")
        for c in ("likes", "comments"):
            if c in ig.columns:
                ig[c] = pd.to_numeric(ig[c], errors="coerce").fillna(0).astype(int)
    return df, ig


df_all, ig_all = load_data()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 16px;">
      <div style="font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#94a3b8;font-weight:600;margin-bottom:4px;">
        If I Only Knew PR
      </div>
      <div style="font-size:22px;font-weight:800;color:white;letter-spacing:-0.02em;line-height:1.1;">
        Narges Rashidi
      </div>
      <div style="font-size:13px;color:#94a3b8;margin-top:2px;">
        Press Intelligence
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    PERIODS = {
        "Last 7 days": 7,
        "Last 14 days": 14,
        "Last 30 days": 30,
        "Last 60 days": 60,
        "Last 90 days": 90,
        "All time": 9999,
    }
    period_lbl = st.selectbox("Time period", list(PERIODS.keys()), index=2)
    DAYS = PERIODS[period_lbl]

    platforms = ["All"] + sorted(df_all["platform"].dropna().unique().tolist())
    f_plat = st.selectbox("Platform", platforms)
    f_tier = st.selectbox("Tier", ["All", "Tier 1", "Tier 2", "Tier 3"])
    types = ["All"] + sorted(df_all["type"].dropna().unique().tolist())
    f_type = st.selectbox("Type", types)
    f_search = st.text_input("Search", placeholder="keyword…")

    st.divider()
    if st.button("↺  Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    last_update = df_all["created_at"].max() if not df_all.empty else "—"
    st.markdown(f"""
    <div style="margin-top:16px;font-size:11px;color:#94a3b8;line-height:1.7;">
      <div><b style="color:#cbd5e1">{len(df_all):,}</b> total items</div>
      <div>Updated {str(last_update)[:10]}</div>
      <div style="margin-top:6px;color:#64748b;">Auto-updates Monday 8am</div>
    </div>
    """, unsafe_allow_html=True)


# ── Apply filters ─────────────────────────────────────────────────────────────
cutoff = pd.Timestamp.now() - pd.Timedelta(days=DAYS) if DAYS < 9999 else pd.Timestamp("2000-01-01")
df = df_all[df_all["date"] >= cutoff].copy() if DAYS < 9999 else df_all.copy()
if f_plat != "All":
    df = df[df["platform"] == f_plat]
if f_tier != "All":
    df = df[df["tier"] == f_tier]
if f_type != "All":
    df = df[df["type"] == f_type]
if f_search:
    mask = (df["title"].str.contains(f_search, case=False, na=False) |
            df["snippet"].str.contains(f_search, case=False, na=False) |
            df["source"].str.contains(f_search, case=False, na=False))
    df = df[mask]

if not df.empty:
    df["reach_calc"] = df.apply(reach_est, axis=1)
    df["ave_calc"]   = df.apply(ave_est, axis=1)
else:
    df["reach_calc"] = []
    df["ave_calc"] = []


# ── HERO ──────────────────────────────────────────────────────────────────────
filter_chips = []
if f_plat != "All": filter_chips.append(f_plat)
if f_tier != "All": filter_chips.append(f_tier)
if f_type != "All": filter_chips.append(f_type)
if f_search:        filter_chips.append(f'"{f_search}"')
chip_str = " · ".join(filter_chips) if filter_chips else ""

st.markdown(f"""
<div class="hero">
  <div class="hero-eyebrow">Press Intelligence</div>
  <h1 class="hero-title">Narges Rashidi</h1>
  <p class="hero-subtitle">
    {period_lbl}{" &nbsp;·&nbsp; " + chip_str if chip_str else ""} &nbsp;·&nbsp;
    <b style="color:#0f172a">{len(df):,}</b> mentions in view
  </p>
</div>
""", unsafe_allow_html=True)


# ── KEY METRICS ───────────────────────────────────────────────────────────────
pos_n = int((df["sentiment"] == "positive").sum())
neg_n = int((df["sentiment"] == "negative").sum())
neu_n = int((df["sentiment"] == "neutral").sum())
t1_n  = int((df["tier"] == "Tier 1").sum())
reach_total = int(df["reach_calc"].sum()) if not df.empty else 0
ave_total   = float(df["ave_calc"].sum())  if not df.empty else 0
pos_pct = round(pos_n / max(len(df), 1) * 100)

# Comparison vs previous period (for deltas)
if DAYS < 9999:
    prev_cutoff = cutoff - pd.Timedelta(days=DAYS)
    df_prev = df_all[(df_all["date"] >= prev_cutoff) & (df_all["date"] < cutoff)].copy()
    if not df_prev.empty:
        df_prev["reach_calc"] = df_prev.apply(reach_est, axis=1)
        df_prev["ave_calc"]   = df_prev.apply(ave_est,   axis=1)
    prev_mentions = len(df_prev)
    prev_pos      = int((df_prev["sentiment"] == "positive").sum()) if not df_prev.empty else 0
    prev_t1       = int((df_prev["tier"] == "Tier 1").sum()) if not df_prev.empty else 0
    prev_reach    = int(df_prev["reach_calc"].sum()) if not df_prev.empty else 0
    prev_ave      = float(df_prev["ave_calc"].sum())  if not df_prev.empty else 0
else:
    prev_mentions = prev_pos = prev_t1 = prev_reach = 0
    prev_ave = 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total mentions", f"{len(df):,}",  fmt_pct_delta(len(df), prev_mentions))
c2.metric("Positive coverage", f"{pos_n}",    f"{pos_pct}% of total")
c3.metric("Tier 1 hits",    f"{t1_n}",       fmt_pct_delta(t1_n, prev_t1))
c4.metric("Estimated reach", fmt_compact(reach_total), fmt_pct_delta(reach_total, prev_reach))
c5.metric("Estimated AVE",   f"£{fmt_compact(ave_total)}", fmt_pct_delta(ave_total, prev_ave))


# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview", "Top Stories", "Compare Periods", "Topic Analysis", "Instagram"
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ════════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Mentions over time")
    if not df.empty and df["date"].notna().any():
        daily = df.groupby(df["date"].dt.date).size().reset_index(name="mentions")
        daily.columns = ["date", "mentions"]
        pos_d = df[df["sentiment"]=="positive"].groupby(df["date"].dt.date).size().reset_index(name="n")
        neg_d = df[df["sentiment"]=="negative"].groupby(df["date"].dt.date).size().reset_index(name="n")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["mentions"], name="All mentions",
            line=dict(color=ACCENT, width=3),
            fill="tozeroy", fillcolor="rgba(79,70,229,0.08)",
            hovertemplate="<b>%{x}</b><br>%{y} mentions<extra></extra>",
        ))
        if not pos_d.empty:
            fig.add_trace(go.Scatter(
                x=pos_d["date"], y=pos_d["n"], name="Positive",
                line=dict(color=GREEN, width=2, dash="dot"),
                hovertemplate="%{x}<br>%{y} positive<extra></extra>",
            ))
        if not neg_d.empty:
            fig.add_trace(go.Scatter(
                x=neg_d["date"], y=neg_d["n"], name="Negative",
                line=dict(color=RED, width=2, dash="dot"),
                hovertemplate="%{x}<br>%{y} negative<extra></extra>",
            ))
        st.plotly_chart(style_chart(fig, 300), use_container_width=True)
    else:
        st.info("No data in this period.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Three side-by-side charts
    a1, a2, a3 = st.columns(3)

    with a1:
        st.markdown("##### Platform")
        if not df.empty:
            plat = df.groupby("platform").size().reset_index(name="n").sort_values("n", ascending=False)
            fig = go.Figure(go.Pie(
                labels=plat["platform"], values=plat["n"], hole=0.55,
                marker=dict(colors=CHART_PALETTE),
                textfont=dict(size=11),
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>",
            ))
            fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=0,b=0), height=240,
                              paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

    with a2:
        st.markdown("##### Sentiment")
        if df["sentiment"].notna().any():
            sd = df[df["sentiment"].notna()].groupby("sentiment").size().reset_index(name="n")
            cmap = {"positive": GREEN, "neutral": MUTED, "negative": RED}
            fig = go.Figure(go.Pie(
                labels=sd["sentiment"].str.capitalize(), values=sd["n"], hole=0.55,
                marker=dict(colors=[cmap.get(s, MUTED) for s in sd["sentiment"]]),
                textfont=dict(size=11),
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>",
            ))
            fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=0,b=0), height=240,
                              paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sentiment data yet.")

    with a3:
        st.markdown("##### Tier mix")
        if not df.empty:
            td = df.groupby("tier").size().reset_index(name="n")
            colors_map = {"Tier 1": ACCENT, "Tier 2": GREEN, "Tier 3": MUTED}
            fig = go.Figure(go.Bar(
                x=td["tier"], y=td["n"],
                marker_color=[colors_map.get(t, MUTED) for t in td["tier"]],
                text=td["n"], textposition="outside",
                textfont=dict(size=12, color=DARK),
                hovertemplate="<b>%{x}</b><br>%{y} mentions<extra></extra>",
            ))
            st.plotly_chart(style_chart(fig, 240), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Sources + Coverage type
    b1, b2 = st.columns([3, 2])

    with b1:
        st.subheader("Most active sources")
        if not df.empty:
            src = (df.groupby("source").size()
                   .reset_index(name="n")
                   .sort_values("n").tail(12))
            fig = go.Figure(go.Bar(
                y=src["source"], x=src["n"], orientation="h",
                marker_color=ACCENT, opacity=0.9,
                text=src["n"], textposition="outside",
                textfont=dict(size=11, color=DARK),
                hovertemplate="<b>%{y}</b><br>%{x} mentions<extra></extra>",
            ))
            fig.update_yaxes(tickfont=dict(size=11))
            st.plotly_chart(style_chart(fig, 360), use_container_width=True)

    with b2:
        st.subheader("Coverage type")
        if not df.empty:
            typ = (df.groupby("type").size()
                   .reset_index(name="n")
                   .sort_values("n"))
            fig = go.Figure(go.Bar(
                y=typ["type"], x=typ["n"], orientation="h",
                marker_color=TEAL, opacity=0.9,
                text=typ["n"], textposition="outside",
                textfont=dict(size=11, color=DARK),
                hovertemplate="<b>%{y}</b><br>%{x}<extra></extra>",
            ))
            fig.update_yaxes(tickfont=dict(size=11))
            st.plotly_chart(style_chart(fig, 360), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — TOP STORIES
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Most impactful coverage")
    st.caption("Sorted by estimated reach — highest visibility first")

    if df.empty:
        st.info("No coverage in this period.")
    else:
        top = df.sort_values("reach_calc", ascending=False).head(15)
        for _, row in top.iterrows():
            url = row.get("url") or ""
            title = (row.get("title") or "Untitled")[:140]
            src = row.get("source") or "—"
            date_s = row["date"].strftime("%d %b %Y") if pd.notna(row.get("date")) else ""
            plat = row.get("platform") or ""
            snip = (row.get("snippet") or "")[:200]
            link_html = (f'<a href="{url}" target="_blank" class="story-title">{title}</a>'
                         if url else f'<span class="story-title">{title}</span>')
            tags = f"{tier_pill(row.get('tier'))} {sent_pill(row.get('sentiment'))}"
            st.markdown(f"""
            <div class="story-card">
              {link_html}
              <div class="story-meta">
                <b>{src}</b> &nbsp;·&nbsp; {date_s} &nbsp;·&nbsp; {plat}
                &nbsp; {tags}
                &nbsp; <span style="color:{SLATE};">Reach ~{fmt_compact(row['reach_calc'])}</span>
              </div>
              <p class="story-snippet">{snip}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader(f"All mentions ({len(df):,})")

    # Build proper sortable table
    if not df.empty:
        tbl = df[["date", "title", "source", "platform", "tier", "type", "sentiment", "reach_calc", "url"]].copy()
        tbl["date"] = tbl["date"].dt.strftime("%Y-%m-%d")
        tbl = tbl.rename(columns={
            "date":"Date", "title":"Title", "source":"Source", "platform":"Platform",
            "tier":"Tier", "type":"Type", "sentiment":"Sentiment", "reach_calc":"Reach",
            "url":"Link",
        })
        st.dataframe(
            tbl, use_container_width=True, height=500, hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn(width="small", display_text="Open ↗"),
                "Title": st.column_config.TextColumn(width="large"),
                "Date": st.column_config.TextColumn(width="small"),
                "Tier": st.column_config.TextColumn(width="small"),
                "Reach": st.column_config.NumberColumn(format="%d"),
            }
        )


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — PERIOD COMPARISON
# ════════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Compare periods")
    st.caption("Current vs previous period — see what's trending up")

    pc1, pc2 = st.columns(2)
    cur_lbl = pc1.selectbox("Current period",
        ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"],
        index=2, key="cmp_cur_lbl")
    pc2.markdown(f"<div style='padding-top:30px;color:#64748b'>vs preceding {cur_lbl.split()[-2]} {cur_lbl.split()[-1]}</div>", unsafe_allow_html=True)

    cur_n = PERIODS[cur_lbl]
    now = pd.Timestamp.now()
    cur_start  = now - pd.Timedelta(days=cur_n)
    prev_start = cur_start - pd.Timedelta(days=cur_n)

    dC = df_all[df_all["date"] >= cur_start].copy()
    dP = df_all[(df_all["date"] >= prev_start) & (df_all["date"] < cur_start)].copy()
    for d in (dC, dP):
        d["reach_calc"] = d.apply(reach_est, axis=1) if not d.empty else []
        d["ave_calc"]   = d.apply(ave_est,   axis=1) if not d.empty else []

    SOCIAL = {"TikTok", "Facebook", "Bluesky", "Instagram"}
    def _m(d):
        sm = d["platform"].isin(SOCIAL) if not d.empty else pd.Series([], dtype=bool)
        return dict(
            total=len(d),
            social=int(sm.sum()) if not d.empty else 0,
            nonsocial=int((~sm).sum()) if not d.empty else 0,
            pos=int((d["sentiment"]=="positive").sum()) if not d.empty else 0,
            neg=int((d["sentiment"]=="negative").sum()) if not d.empty else 0,
            t1=int((d["tier"]=="Tier 1").sum()) if not d.empty else 0,
            reach=int(d["reach_calc"].sum()) if not d.empty else 0,
            sreach=int(d[sm]["reach_calc"].sum()) if not d.empty else 0,
            nreach=int(d[~sm]["reach_calc"].sum()) if not d.empty else 0,
            ave=float(d["ave_calc"].sum()) if not d.empty else 0,
        )
    mc, mp = _m(dC), _m(dP)

    cur_range  = f"{cur_start.strftime('%d %b')} – {now.strftime('%d %b')}"
    prev_range = f"{prev_start.strftime('%d %b')} – {cur_start.strftime('%d %b')}"

    st.markdown("<br>", unsafe_allow_html=True)

    # Build native dataframe for comparison
    rows = [
        ("Total mentions",          mc["total"],     mp["total"],     False, ""),
        ("Social media mentions",   mc["social"],    mp["social"],    False, ""),
        ("Non-social mentions",     mc["nonsocial"], mp["nonsocial"], False, ""),
        ("Positive mentions",       mc["pos"],       mp["pos"],       False, ""),
        ("Negative mentions",       mc["neg"],       mp["neg"],       True,  ""),
        ("Tier 1 hits",             mc["t1"],        mp["t1"],        False, ""),
        ("Social reach",            mc["sreach"],    mp["sreach"],    False, "reach"),
        ("Non-social reach",        mc["nreach"],    mp["nreach"],    False, "reach"),
        ("Total reach",             mc["reach"],     mp["reach"],     False, "reach"),
        ("Estimated AVE",           int(mc["ave"]),  int(mp["ave"]),  False, "money"),
    ]
    cmp_df = pd.DataFrame([
        {
            "Metric": lbl,
            f"{cur_range}": (
                f"£{fmt_compact(cv)}" if kind == "money" else
                fmt_compact(cv)       if kind == "reach" else
                f"{cv:,}"
            ),
            "Change": fmt_pct_delta(cv, pv, inv),
            f"{prev_range}": (
                f"£{fmt_compact(pv)}" if kind == "money" else
                fmt_compact(pv)       if kind == "reach" else
                f"{pv:,}"
            ),
        }
        for lbl, cv, pv, inv, kind in rows
    ])

    st.dataframe(cmp_df, use_container_width=True, hide_index=True,
        column_config={
            "Metric": st.column_config.TextColumn(width="medium"),
            "Change": st.column_config.TextColumn(width="small"),
        })

    st.markdown("<br>", unsafe_allow_html=True)
    cc1, cc2 = st.columns(2)

    with cc1:
        st.subheader("Mentions trend")
        fig = go.Figure()
        if dC["date"].notna().any():
            cd = dC.groupby(dC["date"].dt.date).size().reset_index(name="n")
            fig.add_trace(go.Scatter(x=cd["date"], y=cd["n"], name="Current",
                line=dict(color=ACCENT, width=3),
                fill="tozeroy", fillcolor="rgba(79,70,229,0.08)"))
        if dP["date"].notna().any():
            pd_ = dP.groupby(dP["date"].dt.date).size().reset_index(name="n")
            fig.add_trace(go.Scatter(x=pd_["date"], y=pd_["n"], name="Previous",
                line=dict(color=MUTED, width=2, dash="dash")))
        st.plotly_chart(style_chart(fig, 280), use_container_width=True)

    with cc2:
        st.subheader("Reach trend")
        fig = go.Figure()
        if dC["date"].notna().any():
            cd = dC.groupby(dC["date"].dt.date)["reach_calc"].sum().reset_index()
            fig.add_trace(go.Scatter(x=cd["date"], y=cd["reach_calc"], name="Current",
                line=dict(color=TEAL, width=3),
                fill="tozeroy", fillcolor="rgba(8,145,178,0.08)"))
        if dP["date"].notna().any():
            pd_ = dP.groupby(dP["date"].dt.date)["reach_calc"].sum().reset_index()
            fig.add_trace(go.Scatter(x=pd_["date"], y=pd_["reach_calc"], name="Previous",
                line=dict(color=MUTED, width=2, dash="dash")))
        fig.update_yaxes(tickformat=".2s")
        st.plotly_chart(style_chart(fig, 280), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — TOPIC ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════
_TOPICS = [
    ("BAFTA Win",                    ["bafta", "leading actress", "award", "winner", "wins"]),
    ("Prisoner 951",                 ["prisoner 951", "prisoner951"]),
    ("Nazanin Zaghari-Ratcliffe",    ["nazanin", "zaghari", "ratcliffe"]),
    ("Iranian Actress",              ["iranian actress", "iran", "persian"]),
    ("Save the Children",            ["save the children", "savechildren", "charity"]),
    ("BAFTA TV Awards 2026",         ["bafta tv", "bafta television", "bafta 2026"]),
    ("Film & TV Reviews",            ["review", "drama", "series", "episode"]),
    ("Interviews & Profiles",        ["interview", "speaks", "talks to", "q&a", "in conversation", "profile"]),
]

with tab4:
    st.subheader("Topic clustering")
    st.caption("Coverage automatically grouped into key themes")

    text_col = (df["title"].fillna("") + " " + df["snippet"].fillna("")).str.lower() if not df.empty else pd.Series([])
    topics = []
    for name, kws in _TOPICS:
        if df.empty:
            continue
        mask = text_col.apply(lambda t: any(k in t for k in kws))
        sub = df[mask]
        if sub.empty:
            continue
        topics.append({
            "name": name,
            "mentions": len(sub),
            "reach": int(sub["reach_calc"].sum()),
            "pos": int((sub["sentiment"]=="positive").sum()),
            "neg": int((sub["sentiment"]=="negative").sum()),
            "kws": kws,
        })

    if not topics:
        st.info("Not enough data for topic analysis. Try a longer time period.")
    else:
        total_m = sum(t["mentions"] for t in topics)
        for t in topics:
            t["sov"] = t["mentions"] / total_m * 100

        topics_df = pd.DataFrame(topics).sort_values("mentions", ascending=False)

        ta1, ta2 = st.columns([3, 2])
        with ta1:
            st.markdown("##### Mentions by topic")
            sd_chart = topics_df.sort_values("mentions")
            fig = go.Figure(go.Bar(
                y=sd_chart["name"], x=sd_chart["mentions"], orientation="h",
                marker_color=ACCENT, opacity=0.9,
                text=sd_chart["mentions"], textposition="outside",
                hovertemplate="<b>%{y}</b><br>%{x} mentions<extra></extra>",
            ))
            st.plotly_chart(style_chart(fig, 360), use_container_width=True)

        with ta2:
            st.markdown("##### Share of voice")
            fig = go.Figure(go.Pie(
                labels=topics_df["name"], values=topics_df["sov"], hole=0.5,
                marker=dict(colors=CHART_PALETTE),
                textfont=dict(size=10),
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
            ))
            fig.update_layout(
                margin=dict(l=0,r=0,t=0,b=0), height=360, paper_bgcolor="white",
                showlegend=True, legend=dict(orientation="v", x=1.0, y=0.5,
                    font=dict(size=10, color=SLATE)),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Topic details")

        # Native streamlit table for topics
        td_disp = topics_df.copy()
        td_disp["Reach"] = td_disp["reach"].apply(fmt_compact)
        td_disp["SOV"] = td_disp["sov"].apply(lambda x: f"{x:.1f}%")
        td_disp["Positive"] = td_disp["pos"]
        td_disp["Negative"] = td_disp["neg"]
        td_disp = td_disp[["name", "mentions", "Reach", "SOV", "Positive", "Negative"]]
        td_disp = td_disp.rename(columns={"name": "Topic", "mentions": "Mentions"})
        st.dataframe(td_disp, use_container_width=True, hide_index=True,
            column_config={
                "Topic": st.column_config.TextColumn(width="large"),
                "SOV": st.column_config.ProgressColumn(
                    "Share of voice", min_value=0, max_value=100,
                    format="%.1f%%",
                ) if hasattr(st.column_config, "ProgressColumn") else st.column_config.TextColumn(),
            })

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Drill into a topic")
        drill = st.selectbox("Topic", topics_df["name"].tolist(), key="topic_drill", label_visibility="collapsed")
        drill_kws = next(t["kws"] for t in topics if t["name"] == drill)
        drill_mask = text_col.apply(lambda t: any(k in t for k in drill_kws))
        drill_df = df[drill_mask][["date","title","source","platform","tier","sentiment","url"]].copy()
        drill_df["date"] = drill_df["date"].dt.strftime("%Y-%m-%d")
        drill_df = drill_df.rename(columns={
            "date":"Date","title":"Title","source":"Source",
            "platform":"Platform","tier":"Tier","sentiment":"Sentiment","url":"Link",
        })
        st.caption(f"**{len(drill_df)}** mentions for *{drill}*")
        st.dataframe(drill_df, use_container_width=True, height=400, hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn(display_text="Open ↗"),
                "Title": st.column_config.TextColumn(width="large"),
            })


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — INSTAGRAM
# ════════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("Instagram coverage")
    st.caption("Her posts · Posts that tag her · Hashtag mentions (#nargesrashidi, #prisoner951)")

    if ig_all.empty:
        st.info("No Instagram data yet. Run `python3 run.py` to fetch.")
    else:
        # Filters
        ig_p1, ig_p2 = st.columns([1, 1])
        ig_period_n = PERIODS[ig_p1.selectbox("Period", list(PERIODS.keys()), index=2, key="ig_per")]
        SRC_LABELS = {"all": "All sources", "own_post": "Her own posts", "tagged": "Tags her", "hashtag": "Hashtag posts"}
        ig_src = ig_p2.selectbox("Source", ["all", "own_post", "tagged", "hashtag"],
            format_func=SRC_LABELS.get, key="ig_src")

        ig_cut = pd.Timestamp.now() - pd.Timedelta(days=ig_period_n) if ig_period_n < 9999 else pd.Timestamp("2000-01-01")
        ig_df = ig_all[ig_all["date"] >= ig_cut].copy() if ig_period_n < 9999 else ig_all.copy()
        if ig_src != "all" and "source_type" in ig_df.columns:
            ig_df = ig_df[ig_df["source_type"] == ig_src]

        if ig_df.empty:
            st.info("No posts in this period.")
        else:
            # Metrics
            has_src = "source_type" in ig_df.columns
            tagged_n = int((ig_df["source_type"]=="tagged").sum())   if has_src else 0
            htag_n   = int((ig_df["source_type"]=="hashtag").sum())  if has_src else 0
            own_n    = int((ig_df["source_type"]=="own_post").sum()) if has_src else len(ig_df)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total posts",   len(ig_df))
            m2.metric("Her own posts", own_n)
            m3.metric("Tags her",      tagged_n)
            m4.metric("Hashtag posts", htag_n)
            m5.metric("Total likes",   fmt_compact(int(ig_df["likes"].sum())))

            st.markdown("<br>", unsafe_allow_html=True)

            ig_c1, ig_c2 = st.columns([3, 2])
            with ig_c1:
                st.markdown("##### Engagement over time")
                if ig_df["date"].notna().any():
                    by_day = ig_df.groupby(ig_df["date"].dt.date).agg(
                        likes=("likes", "sum"),
                        comments=("comments", "sum"),
                    ).reset_index()
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=by_day["date"], y=by_day["likes"],
                        name="Likes", marker_color=PINK, opacity=0.85))
                    fig.add_trace(go.Bar(x=by_day["date"], y=by_day["comments"],
                        name="Comments", marker_color=AMBER, opacity=0.85))
                    fig.update_layout(barmode="group")
                    st.plotly_chart(style_chart(fig, 300), use_container_width=True)

            with ig_c2:
                if has_src:
                    st.markdown("##### Source breakdown")
                    src_map = {"own_post": "Her posts", "tagged": "Tags her", "hashtag": "Hashtag"}
                    src_counts = (ig_df["source_type"].map(src_map)
                                  .value_counts().reset_index())
                    src_counts.columns = ["source", "count"]
                    fig = go.Figure(go.Pie(
                        labels=src_counts["source"], values=src_counts["count"], hole=0.5,
                        marker=dict(colors=[PINK, ACCENT, TEAL]),
                        textfont=dict(size=12),
                        textinfo="label+percent",
                    ))
                    fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=0,b=0),
                                      height=300, paper_bgcolor="white")
                    st.plotly_chart(fig, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"##### Top {min(len(ig_df), 24)} posts — by engagement")

            top_posts = ig_df.sort_values("likes", ascending=False).head(24)
            cols = st.columns(3)
            for i, (_, post) in enumerate(top_posts.iterrows()):
                with cols[i % 3]:
                    cap = (post.get("caption") or "")[:200]
                    src_type = post.get("source_type", "own_post") if has_src else "own_post"
                    src_lbl = src_map.get(src_type, src_type) if has_src else "Her posts"
                    src_color = {"own_post": PINK, "tagged": ACCENT, "hashtag": TEAL}.get(src_type, MUTED)
                    username = post.get("username", "")
                    htag = post.get("hashtag", "")
                    handle = (f"#{htag}" if (src_type == "hashtag" and htag) else
                              (f"@{username}" if username else ""))
                    url = post.get("url", "") or ""
                    date_s = post["date"].strftime("%d %b %Y") if pd.notna(post.get("date")) else ""

                    with st.container(border=True):
                        st.markdown(f"""
                        <div style="font-size:11px;color:#64748b;margin-bottom:6px;">
                          <span style="background:{src_color}1a;color:{src_color};padding:2px 8px;border-radius:100px;font-weight:600;">{src_lbl}</span>
                          &nbsp;{handle}&nbsp;·&nbsp;{date_s}
                        </div>
                        <div style="font-size:13px;color:#0f172a;line-height:1.5;margin-bottom:10px;min-height:60px;">{cap}</div>
                        <div style="font-size:13px;color:#64748b;font-weight:600;">
                          ❤️ {int(post.get('likes',0)):,} &nbsp; 💬 {int(post.get('comments',0)):,}
                        </div>
                        <a href="{url}" target="_blank" style="font-size:11px;color:#4f46e5;text-decoration:none;font-weight:600;">View on Instagram ↗</a>
                        """, unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:48px 0 16px;color:#94a3b8;font-size:12px;">
  If I Only Knew PR &nbsp;·&nbsp; Narges Rashidi Press Monitor &nbsp;·&nbsp; Updates every Monday 8am
</div>
""", unsafe_allow_html=True)
