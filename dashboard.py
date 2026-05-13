"""
Narges Rashidi — Press Intelligence Dashboard
If I Only Knew PR

Run locally:  streamlit run dashboard.py
Cloud:        https://narges-press-monitor-538spugleugn6wtdypc4n2.streamlit.app
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "press_narges.db"

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Narges Rashidi · Press Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ─────────────────────────────────────────────────────────────
ACCENT   = "#4f46e5"   # indigo-600
ACCENT_L = "#e0e7ff"   # indigo-100
GREEN    = "#059669"
RED      = "#dc2626"
SLATE    = "#64748b"
DARK     = "#0f172a"
BG       = "#f8fafc"
CARD_BG  = "#ffffff"
BORDER   = "#e2e8f0"

CHART_COLORS = ["#4f46e5","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"]

PLOTLY_LAYOUT = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(family="Inter, sans-serif", color=DARK, size=12),
    margin=dict(l=0, r=0, t=16, b=0),
    legend=dict(orientation="h", y=1.15, x=0, font=dict(size=11)),
    xaxis=dict(showgrid=False, tickfont=dict(color=SLATE)),
    yaxis=dict(gridcolor="#f1f5f9", tickfont=dict(color=SLATE), zeroline=False),
    hoverlabel=dict(bgcolor="white", bordercolor=BORDER, font=dict(family="Inter, sans-serif")),
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  /* ── Base ── */
  html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif !important;
    background: {BG};
    color: {DARK};
  }}

  /* Hide Streamlit chrome (but keep toolbar so error messages can be dismissed) */
  #MainMenu, footer {{ visibility: hidden; }}
  .stDeployButton {{ display: none; }}
  [data-testid="collapsedControl"] {{ color: {DARK}; }}

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {{
    background: {DARK} !important;
    border-right: none;
  }}
  [data-testid="stSidebar"] * {{ color: #cbd5e1 !important; }}
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3 {{
    color: white !important;
  }}
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stTextInput label {{
    color: #94a3b8 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: .06em;
    font-weight: 600;
  }}
  [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
  [data-testid="stSidebar"] [data-testid="stTextInput"] input {{
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    color: white !important;
    border-radius: 8px;
  }}
  [data-testid="stSidebar"] hr {{ border-color: #1e293b !important; }}
  [data-testid="stSidebar"] button {{
    background: {ACCENT} !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
  }}

  /* ── Main area ── */
  .main .block-container {{
    padding: 2rem 2.5rem 4rem;
    max-width: 1600px;
  }}

  /* ── Tabs ── */
  [data-testid="stTabs"] [data-baseweb="tab-list"] {{
    background: transparent;
    border-bottom: 2px solid {BORDER};
    gap: 0;
  }}
  [data-testid="stTabs"] [data-baseweb="tab"] {{
    background: transparent;
    color: {SLATE};
    font-weight: 500;
    font-size: 14px;
    padding: 12px 24px;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
  }}
  [data-testid="stTabs"] [aria-selected="true"] {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
  }}

  /* ── Metric cards ── */
  .kpi-grid {{ display: grid; grid-template-columns: repeat(6,1fr); gap: 16px; margin: 24px 0; }}
  .kpi-card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 20px 20px 16px;
    position: relative;
    overflow: hidden;
    transition: box-shadow .2s;
    box-shadow: 0 1px 3px rgba(0,0,0,.05);
  }}
  .kpi-card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,.09); }}
  .kpi-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: {ACCENT};
  }}
  .kpi-icon {{ font-size: 22px; margin-bottom: 8px; }}
  .kpi-value {{
    font-size: 2rem;
    font-weight: 800;
    color: {DARK};
    line-height: 1;
    letter-spacing: -.02em;
  }}
  .kpi-label {{
    font-size: 12px;
    font-weight: 500;
    color: {SLATE};
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: .06em;
  }}
  .kpi-card.green::before {{ background: {GREEN}; }}
  .kpi-card.red::before   {{ background: {RED}; }}
  .kpi-card.teal::before  {{ background: #06b6d4; }}
  .kpi-card.amber::before {{ background: #f59e0b; }}
  .kpi-card.purple::before{{ background: #8b5cf6; }}

  /* ── Section titles ── */
  .section-title {{
    font-size: 16px;
    font-weight: 700;
    color: {DARK};
    margin: 0 0 16px;
    letter-spacing: -.01em;
  }}

  /* ── Chart card ── */
  .chart-card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,.05);
    margin-bottom: 20px;
  }}

  /* ── Mention card ── */
  .mention-card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
    transition: all .2s;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
  }}
  .mention-card:hover {{
    border-color: {ACCENT};
    box-shadow: 0 4px 20px rgba(79,70,229,.12);
    transform: translateY(-1px);
  }}
  .mention-title {{
    font-size: 14px;
    font-weight: 600;
    color: {DARK};
    text-decoration: none;
    line-height: 1.4;
  }}
  .mention-title:hover {{ color: {ACCENT}; }}
  .mention-meta {{
    font-size: 12px;
    color: {SLATE};
    margin: 6px 0 10px;
  }}
  .mention-snippet {{
    font-size: 13px;
    color: #475569;
    line-height: 1.5;
    margin: 0;
  }}

  /* ── Badges ── */
  .badge {{
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: 100px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 4px;
    letter-spacing: .02em;
  }}
  .badge-t1  {{ background: {ACCENT_L}; color: {ACCENT}; }}
  .badge-t2  {{ background: #dcfce7;    color: #166534; }}
  .badge-t3  {{ background: #f1f5f9;    color: {SLATE}; }}
  .badge-pos {{ background: #d1fae5;    color: #065f46; }}
  .badge-neg {{ background: #fee2e2;    color: #991b1b; }}
  .badge-neu {{ background: #f1f5f9;    color: {SLATE}; }}
  .badge-plat{{ background: #fef3c7;    color: #92400e; }}

  /* ── Comparison table ── */
  .comp-table {{ width: 100%; border-collapse: collapse; }}
  .comp-table th {{
    font-size: 12px;
    font-weight: 600;
    color: {SLATE};
    text-transform: uppercase;
    letter-spacing: .06em;
    padding: 12px 16px;
    border-bottom: 2px solid {BORDER};
    text-align: left;
  }}
  .comp-table td {{
    padding: 14px 16px;
    border-bottom: 1px solid {BORDER};
    font-size: 14px;
    font-weight: 500;
  }}
  .comp-table tr:hover td {{ background: {BG}; }}
  .comp-table .metric-label {{ color: {DARK}; font-weight: 500; }}
  .comp-val  {{ font-weight: 700; font-size: 16px; color: {DARK}; }}
  .comp-prev {{ color: {SLATE}; font-size: 14px; }}
  .delta-up  {{ color: {GREEN}; font-weight: 700; font-size: 13px; }}
  .delta-dn  {{ color: {RED};   font-weight: 700; font-size: 13px; }}
  .delta-flat{{ color: {SLATE}; font-weight: 600; font-size: 13px; }}

  /* ── Topic row ── */
  .topic-row {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 24px;
    transition: box-shadow .2s;
  }}
  .topic-row:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,.08); }}
  .topic-name {{ font-weight: 700; font-size: 15px; color: {DARK}; min-width: 220px; }}
  .topic-stat {{ text-align: center; min-width: 80px; }}
  .topic-stat-val {{ font-size: 18px; font-weight: 800; color: {DARK}; }}
  .topic-stat-lbl {{ font-size: 11px; color: {SLATE}; font-weight: 500; text-transform: uppercase; letter-spacing:.04em; }}

  /* ── SOV bar ── */
  .sov-bar-wrap {{ flex: 1; }}
  .sov-bar-bg {{
    background: #f1f5f9; border-radius: 100px;
    height: 8px; overflow: hidden; margin-bottom: 4px;
  }}
  .sov-bar-fill {{ height: 100%; border-radius: 100px; background: {ACCENT}; }}
  .sov-pct {{ font-size: 13px; font-weight: 700; color: {ACCENT}; }}

  /* ── Instagram card ── */
  .ig-card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
    transition: box-shadow .2s;
  }}
  .ig-card:hover {{ box-shadow: 0 6px 20px rgba(0,0,0,.10); }}
  .ig-date {{ font-size: 12px; color: {SLATE}; font-weight: 500; margin-bottom: 8px; }}
  .ig-caption {{ font-size: 13px; color: #334155; line-height: 1.55; margin-bottom: 14px; }}
  .ig-stats {{ display: flex; gap: 16px; font-size: 13px; font-weight: 600; color: {SLATE}; }}
  .ig-link {{
    display: inline-block; margin-top: 12px;
    font-size: 12px; font-weight: 600; color: {ACCENT};
    text-decoration: none;
  }}
  .ig-link:hover {{ text-decoration: underline; }}

  /* ── Streamlit widget overrides ── */
  [data-testid="stSelectbox"] > div > div,
  [data-testid="stTextInput"] input {{
    border-radius: 10px !important;
    border-color: {BORDER} !important;
    font-family: 'Inter', sans-serif !important;
  }}
  [data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
  .stButton > button {{
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
  }}
  div[data-testid="stMetric"] {{ display: none; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe_int(v) -> int:
    try:
        return 0 if (v is None or (isinstance(v, float) and pd.isna(v))) else int(v)
    except Exception:
        return 0

def reach_est(row) -> int:
    tier, plat = str(row.get("tier") or "Tier 3"), str(row.get("platform") or "")
    v = _safe_int(row.get("views"))
    if plat == "YouTube":       return v
    if plat in ("TikTok","Facebook"): return v * 3
    if tier == "Tier 1":        return 850_000
    if tier == "Tier 2":        return 120_000
    return 15_000

def ave_est(row) -> float:
    tier, plat = str(row.get("tier") or "Tier 3"), str(row.get("platform") or "")
    v = _safe_int(row.get("views"))
    if plat == "YouTube":       return v * 0.003
    if plat in ("TikTok","Facebook"): return v * 0.002
    if tier == "Tier 1":        return 2500.0
    if tier == "Tier 2":        return 350.0
    return 75.0

def fmt_reach(r: int) -> str:
    if r >= 1_000_000: return f"{r/1_000_000:.1f}M"
    if r >= 1_000:     return f"{r/1_000:.0f}K"
    return str(r)

def delta_html(cur, prev, invert=False) -> str:
    if prev == 0:
        return '<span class="delta-up">NEW</span>' if cur > 0 else '<span class="delta-flat">—</span>'
    pct = (cur - prev) / prev * 100
    up = pct >= 0
    if invert: up = not up
    cls   = "delta-up" if up else "delta-dn"
    arrow = "↑" if up else "↓"
    return f'<span class="{cls}">{arrow} {abs(pct):.0f}%</span>'

def tier_badge(t) -> str:
    n = str(t or "Tier 3")[-1]
    return f'<span class="badge badge-t{n}">{t}</span>'

def sent_badge(s) -> str:
    s = (s or "neutral").lower()
    return f'<span class="badge badge-{s[:3]}">{s.capitalize()}</span>'

def plat_badge(p) -> str:
    return f'<span class="badge badge-plat">{p}</span>'

def chart_theme(fig, height=280) -> go.Figure:
    fig.update_layout(height=height, **PLOTLY_LAYOUT)
    return fig


# ── Data ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    data_dir    = Path(__file__).parent / "data"
    parquet     = data_dir / "press.parquet"
    ig_parquet  = data_dir / "instagram.parquet"
    if parquet.exists():
        df = pd.read_parquet(parquet)
        ig = pd.read_parquet(ig_parquet) if ig_parquet.exists() else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM press ORDER BY date DESC, created_at DESC", conn)
        try:    ig = pd.read_sql_query("SELECT * FROM instagram_posts ORDER BY date DESC", conn)
        except: ig = pd.DataFrame()
        conn.close()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if not ig.empty:
        ig["date"] = pd.to_datetime(ig["date"], errors="coerce")
    return df, ig

df_all, ig_all = load_data()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:8px 0 20px">
      <div style="font-size:11px;font-weight:700;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px">If I Only Knew PR</div>
      <div style="font-size:22px;font-weight:800;color:white;letter-spacing:-.02em">Narges Rashidi</div>
      <div style="font-size:12px;color:#64748b;margin-top:2px">Press Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    PERIOD_OPTS = {"Last 7 days":7,"Last 14 days":14,"Last 30 days":30,
                   "Last 60 days":60,"Last 90 days":90,"All time":9999}
    period_label = st.selectbox("Time period", list(PERIOD_OPTS.keys()))
    DAYS = PERIOD_OPTS[period_label]

    platforms = ["All"] + sorted(df_all["platform"].dropna().unique().tolist())
    sel_plat = st.selectbox("Platform", platforms)

    sel_tier = st.selectbox("Tier", ["All","Tier 1","Tier 2","Tier 3"])
    sel_type = st.selectbox("Type", ["All"] + sorted(df_all["type"].dropna().unique().tolist()))
    search   = st.text_input("Search", placeholder="keyword…")

    st.divider()
    if st.button("↺  Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    last_entry = df_all["created_at"].max() if not df_all.empty else "—"
    st.markdown(f"""
    <div style="margin-top:16px;font-size:11px;color:#475569;line-height:1.6">
      <div>{len(df_all):,} total items</div>
      <div>Last updated {str(last_entry)[:10]}</div>
      <div style="margin-top:8px">Updates every Monday 8am</div>
    </div>
    """, unsafe_allow_html=True)


# ── Apply filters ─────────────────────────────────────────────────────────────
cutoff = pd.Timestamp.now() - pd.Timedelta(days=DAYS) if DAYS < 9999 else pd.Timestamp("2000-01-01")
df = df_all[df_all["date"] >= cutoff].copy() if DAYS < 9999 else df_all.copy()
if sel_plat != "All": df = df[df["platform"] == sel_plat]
if sel_tier != "All": df = df[df["tier"] == sel_tier]
if sel_type != "All": df = df[df["type"] == sel_type]
if search:
    m = (df["title"].str.contains(search,case=False,na=False) |
         df["snippet"].str.contains(search,case=False,na=False) |
         df["source"].str.contains(search,case=False,na=False))
    df = df[m]

df["reach"] = df.apply(reach_est, axis=1)
df["ave"]   = df.apply(ave_est,   axis=1)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
  <div>
    <h1 style="font-size:28px;font-weight:800;color:{DARK};letter-spacing:-.03em;margin:0">
      Press Intelligence
    </h1>
    <p style="color:{SLATE};font-size:14px;margin:4px 0 0">
      Narges Rashidi &nbsp;·&nbsp; {period_label}
      {"&nbsp;·&nbsp; " + sel_plat if sel_plat != "All" else ""}
      {"&nbsp;·&nbsp; " + sel_tier if sel_tier != "All" else ""}
      {"&nbsp;·&nbsp; &quot;" + search + "&quot;" if search else ""}
    </p>
  </div>
  <div style="font-size:13px;color:{SLATE}">
    <span style="background:{ACCENT_L};color:{ACCENT};padding:6px 14px;border-radius:100px;font-weight:600">
      {len(df):,} mentions
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_ov, tab_cmp, tab_topics, tab_ig = st.tabs([
    "  Overview  ", "  Period Comparison  ", "  Topic Analysis  ", "  Instagram  "
])


# ════════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ════════════════════════════════════════════════════════════════════════════════
with tab_ov:

    # ── KPI cards ──
    pos_n  = int((df["sentiment"]=="positive").sum())
    neg_n  = int((df["sentiment"]=="negative").sum())
    t1_n   = int((df["tier"]=="Tier 1").sum())
    reach  = int(df["reach"].sum())
    ave    = df["ave"].sum()
    pos_pct= round(pos_n/max(len(df),1)*100)

    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon">📰</div>
        <div class="kpi-value">{len(df):,}</div>
        <div class="kpi-label">Total mentions</div>
      </div>
      <div class="kpi-card green">
        <div class="kpi-icon">✅</div>
        <div class="kpi-value" style="color:{GREEN}">{pos_n}</div>
        <div class="kpi-label">Positive &nbsp;<span style="color:#9ca3af;font-weight:400">{pos_pct}%</span></div>
      </div>
      <div class="kpi-card red">
        <div class="kpi-icon">⚠️</div>
        <div class="kpi-value" style="color:{RED}">{neg_n}</div>
        <div class="kpi-label">Negative</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon">⭐</div>
        <div class="kpi-value">{t1_n:,}</div>
        <div class="kpi-label">Tier 1 hits</div>
      </div>
      <div class="kpi-card teal">
        <div class="kpi-icon">👁</div>
        <div class="kpi-value" style="color:#0891b2">{fmt_reach(reach)}</div>
        <div class="kpi-label">Est. reach</div>
      </div>
      <div class="kpi-card purple">
        <div class="kpi-icon">💷</div>
        <div class="kpi-value" style="color:#7c3aed">£{ave/1000:.0f}K</div>
        <div class="kpi-label">Est. AVE</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Charts row 1 ──
    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Mentions over time</p>', unsafe_allow_html=True)
        if df["date"].notna().any():
            daily = df.groupby(df["date"].dt.date).size().reset_index(name="n")
            pos_d = df[df["sentiment"]=="positive"].groupby(df["date"].dt.date).size().reset_index(name="n")
            neg_d = df[df["sentiment"]=="negative"].groupby(df["date"].dt.date).size().reset_index(name="n")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=daily["date"], y=daily["n"], name="All mentions",
                line=dict(color=ACCENT, width=2.5), fill="tozeroy",
                fillcolor="rgba(79,70,229,.07)"))
            if not pos_d.empty:
                fig.add_trace(go.Scatter(x=pos_d["date"], y=pos_d["n"], name="Positive",
                    line=dict(color=GREEN, width=1.5, dash="dot")))
            if not neg_d.empty:
                fig.add_trace(go.Scatter(x=neg_d["date"], y=neg_d["n"], name="Negative",
                    line=dict(color=RED, width=1.5, dash="dot")))
            st.plotly_chart(chart_theme(fig, 260), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Estimated reach over time</p>', unsafe_allow_html=True)
        if df["date"].notna().any():
            reach_d = df.groupby(df["date"].dt.date)["reach"].sum().reset_index()
            fig_r = go.Figure(go.Scatter(x=reach_d["date"], y=reach_d["reach"],
                fill="tozeroy", line=dict(color="#06b6d4", width=2.5),
                fillcolor="rgba(6,182,212,.07)", name="Reach"))
            fig_r.update_yaxes(tickformat=".2s")
            st.plotly_chart(chart_theme(fig_r, 220), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Platform split</p>', unsafe_allow_html=True)
        if not df.empty:
            plat_d = df.groupby("platform").size().reset_index(name="n").sort_values("n", ascending=False)
            fig2 = px.pie(plat_d, values="n", names="platform", hole=0.52,
                color_discrete_sequence=CHART_COLORS)
            fig2.update_traces(textposition="inside", textinfo="percent+label",
                textfont=dict(size=12, family="Inter, sans-serif"))
            fig2.update_layout(height=240, showlegend=False, **{k:v for k,v in PLOTLY_LAYOUT.items()
                                                                  if k not in ("xaxis","yaxis")})
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Sentiment breakdown</p>', unsafe_allow_html=True)
        if df["sentiment"].notna().any():
            sd = df[df["sentiment"].notna()].groupby("sentiment").size().reset_index(name="n")
            cmap = {"positive": GREEN, "neutral": "#94a3b8", "negative": RED}
            fig3 = px.pie(sd, values="n", names="sentiment", hole=0.52,
                color="sentiment", color_discrete_map=cmap)
            fig3.update_traces(textposition="inside", textinfo="percent+label",
                textfont=dict(size=12, family="Inter, sans-serif"))
            fig3.update_layout(height=240, showlegend=True,
                legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
                **{k:v for k,v in PLOTLY_LAYOUT.items() if k not in ("xaxis","yaxis","legend")})
            st.plotly_chart(fig3, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Charts row 2 ──
    d1, d2 = st.columns(2)
    with d1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Most active sources</p>', unsafe_allow_html=True)
        if not df.empty:
            src = df.groupby("source").size().reset_index(name="n").sort_values("n").tail(12)
            fig4 = go.Figure(go.Bar(y=src["source"], x=src["n"], orientation="h",
                marker=dict(color=ACCENT, opacity=0.85),
                text=src["n"], textposition="outside",
                textfont=dict(size=11, color=SLATE)))
            fig4.update_xaxes(gridcolor="#f1f5f9")
            fig4.update_yaxes(showgrid=False, tickfont=dict(size=11))
            st.plotly_chart(chart_theme(fig4, 360), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with d2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Tier & type breakdown</p>', unsafe_allow_html=True)
        e1, e2 = st.columns(2)
        with e1:
            if not df.empty:
                td = df.groupby("tier").size().reset_index(name="n")
                tcolors = {"Tier 1": ACCENT, "Tier 2": GREEN, "Tier 3": "#94a3b8"}
                fig5 = go.Figure(go.Bar(x=td["tier"], y=td["n"],
                    marker_color=[tcolors.get(t, SLATE) for t in td["tier"]],
                    text=td["n"], textposition="outside"))
                fig5.update_yaxes(gridcolor="#f1f5f9")
                st.plotly_chart(chart_theme(fig5, 180), use_container_width=True)
        with e2:
            if not df.empty:
                typ = df.groupby("type").size().reset_index(name="n").sort_values("n", ascending=True)
                fig6 = go.Figure(go.Bar(y=typ["type"], x=typ["n"], orientation="h",
                    marker=dict(color="#06b6d4", opacity=0.85),
                    text=typ["n"], textposition="outside"))
                fig6.update_xaxes(gridcolor="#f1f5f9")
                st.plotly_chart(chart_theme(fig6, 180), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Most impactful ──
    st.markdown('<p class="section-title" style="margin-top:8px">Most impactful coverage</p>', unsafe_allow_html=True)
    impact = df.sort_values("reach", ascending=False).head(10)
    for _, row in impact.iterrows():
        url   = row.get("url","") or ""
        title = (row.get("title") or "Untitled")[:120]
        src   = row.get("source","")
        date_s = row["date"].strftime("%d %b %Y") if pd.notna(row.get("date")) else ""
        plat   = row.get("platform","")
        snip   = (row.get("snippet") or "")[:180]
        link = f'<a href="{url}" target="_blank" class="mention-title">{title}</a>' if url else f'<span class="mention-title">{title}</span>'
        st.markdown(f"""
        <div class="mention-card">
          {link}
          <div class="mention-meta">
            {src} &nbsp;·&nbsp; {date_s} &nbsp;·&nbsp;
            {tier_badge(row.get("tier"))} {sent_badge(row.get("sentiment"))} {plat_badge(plat)}
            &nbsp; <span style="color:{SLATE}">Reach ~{fmt_reach(int(row['reach']))}</span>
          </div>
          <p class="mention-snippet">{snip}</p>
        </div>
        """, unsafe_allow_html=True)

    # ── Full table ──
    st.markdown(f'<p class="section-title" style="margin-top:24px">All mentions ({len(df):,})</p>', unsafe_allow_html=True)
    disp = df[["date","title","source","platform","tier","type","sentiment","views","url"]].copy()
    disp["date"] = disp["date"].dt.strftime("%Y-%m-%d").fillna("—")
    # Keep numeric columns numeric; fill text columns only
    for c in ("title","source","platform","tier","type","sentiment","url"):
        disp[c] = disp[c].fillna("—")
    st.dataframe(disp, use_container_width=True, height=480, hide_index=True,
        column_config={
            "url":   st.column_config.LinkColumn("Link", display_text="Open ↗"),
            "title": st.column_config.TextColumn("Title", width="large"),
            "date":  st.column_config.TextColumn("Date", width="small"),
            "tier":  st.column_config.TextColumn("Tier", width="small"),
            "views": st.column_config.NumberColumn("Views", format="%d"),
        })


# ════════════════════════════════════════════════════════════════════════════════
# PERIOD COMPARISON
# ════════════════════════════════════════════════════════════════════════════════
with tab_cmp:
    st.markdown(f'<h2 style="font-size:20px;font-weight:700;color:{DARK};margin-bottom:20px">Compare periods</h2>', unsafe_allow_html=True)
    pc1, pc2, _ = st.columns([2,2,3])
    cur_days_label  = pc1.selectbox("Current period",  ["Last 7 days","Last 14 days","Last 30 days","Last 60 days"], key="cmp_cur")
    prev_mode_label = pc2.selectbox("Compare against", ["Previous period","Same period last month"], key="cmp_prev")

    cur_n    = {"Last 7 days":7,"Last 14 days":14,"Last 30 days":30,"Last 60 days":60}[cur_days_label]
    now      = pd.Timestamp.now()
    cur_start= now - pd.Timedelta(days=cur_n)
    prev_start= cur_start - pd.Timedelta(days=cur_n)
    prev_end = cur_start

    df_c = df_all[df_all["date"] >= cur_start].copy()
    df_p = df_all[(df_all["date"] >= prev_start) & (df_all["date"] < prev_end)].copy()
    for d in (df_c, df_p):
        d["reach"] = d.apply(reach_est, axis=1)
        d["ave"]   = d.apply(ave_est,   axis=1)

    SOCIAL = {"TikTok","Facebook","Bluesky","Instagram"}
    def _m(d):
        sm = d["platform"].isin(SOCIAL)
        return dict(
            total=len(d), social=int(sm.sum()), nonsocial=int((~sm).sum()),
            pos=int((d["sentiment"]=="positive").sum()),
            neg=int((d["sentiment"]=="negative").sum()),
            pos_pct=round((d["sentiment"]=="positive").mean()*100,1) if len(d) else 0,
            neg_pct=round((d["sentiment"]=="negative").mean()*100,1) if len(d) else 0,
            sreach=int(d[sm]["reach"].sum()), nreach=int(d[~sm]["reach"].sum()),
            reach=int(d["reach"].sum()), ave=int(d["ave"].sum()),
            t1=int((d["tier"]=="Tier 1").sum()),
        )
    mc, mp = _m(df_c), _m(df_p)
    cur_lbl  = f"{cur_start.strftime('%d %b')} – {now.strftime('%d %b %Y')}"
    prev_lbl = f"{prev_start.strftime('%d %b')} – {prev_end.strftime('%d %b %Y')}"

    rows = [
        ("Total mentions",        mc["total"],   mp["total"],   False),
        ("Social media mentions", mc["social"],  mp["social"],  False),
        ("Non-social mentions",   mc["nonsocial"],mp["nonsocial"],False),
        ("Positive mentions",     mc["pos"],     mp["pos"],     False),
        ("Negative mentions",     mc["neg"],     mp["neg"],     True),
        ("Social reach",          mc["sreach"],  mp["sreach"],  False),
        ("Non-social reach",      mc["nreach"],  mp["nreach"],  False),
        ("Est. AVE",              mc["ave"],     mp["ave"],     False),
        ("Tier 1 hits",           mc["t1"],      mp["t1"],      False),
    ]

    reach_rows = {"Social reach", "Non-social reach"}
    ave_rows   = {"Est. AVE"}

    st.markdown(f"""
    <table class="comp-table">
      <thead>
        <tr>
          <th style="width:35%">Metric</th>
          <th>{cur_lbl}</th>
          <th>vs</th>
          <th>{prev_lbl}</th>
        </tr>
      </thead>
      <tbody>
    """ + "".join(f"""
        <tr>
          <td class="metric-label">{lbl}</td>
          <td><span class="comp-val">{("£"+fmt_reach(cv)) if lbl in ave_rows else (fmt_reach(cv) if lbl in reach_rows else f"{cv:,}")}</span>
              &nbsp; {delta_html(cv, pv, inv)}</td>
          <td></td>
          <td class="comp-prev">{("£"+fmt_reach(pv)) if lbl in ave_rows else (fmt_reach(pv) if lbl in reach_rows else f"{pv:,}")}</td>
        </tr>
    """ for lbl,cv,pv,inv in rows) + """
      </tbody>
    </table>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Mentions — current vs previous</p>', unsafe_allow_html=True)
        fig_cc = go.Figure()
        if df_c["date"].notna().any():
            cd = df_c.groupby(df_c["date"].dt.date).size().reset_index(name="n")
            fig_cc.add_trace(go.Scatter(x=cd["date"],y=cd["n"],name="Current",
                line=dict(color=ACCENT,width=2.5),fill="tozeroy",fillcolor="rgba(79,70,229,.07)"))
        if df_p["date"].notna().any():
            pd_ = df_p.groupby(df_p["date"].dt.date).size().reset_index(name="n")
            fig_cc.add_trace(go.Scatter(x=pd_["date"],y=pd_["n"],name="Previous",
                line=dict(color="#a5b4fc",width=1.5,dash="dash")))
        st.plotly_chart(chart_theme(fig_cc,260), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with cc2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Reach — current vs previous</p>', unsafe_allow_html=True)
        fig_cr = go.Figure()
        if df_c["date"].notna().any():
            cr_ = df_c.groupby(df_c["date"].dt.date)["reach"].sum().reset_index()
            fig_cr.add_trace(go.Scatter(x=cr_["date"],y=cr_["reach"],name="Current",
                line=dict(color="#06b6d4",width=2.5),fill="tozeroy",fillcolor="rgba(6,182,212,.07)"))
        if df_p["date"].notna().any():
            pr_ = df_p.groupby(df_p["date"].dt.date)["reach"].sum().reset_index()
            fig_cr.add_trace(go.Scatter(x=pr_["date"],y=pr_["reach"],name="Previous",
                line=dict(color="#a5f3fc",width=1.5,dash="dash")))
        fig_cr.update_yaxes(tickformat=".2s")
        st.plotly_chart(chart_theme(fig_cr,260), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    cc3, cc4 = st.columns(2)
    with cc3:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Sentiment breakdown</p>', unsafe_allow_html=True)
        sdf_rows = []
        for lbl, d in [(cur_lbl,df_c),(prev_lbl,df_p)]:
            tot = max(len(d),1)
            sdf_rows.append({"Period":lbl,
                "Positive":round((d["sentiment"]=="positive").sum()/tot*100,1),
                "Neutral" :round((d["sentiment"]=="neutral").sum()/tot*100,1),
                "Negative":round((d["sentiment"]=="negative").sum()/tot*100,1)})
        sdf = pd.DataFrame(sdf_rows)
        fig_s = go.Figure()
        for col,color in [("Positive",GREEN),("Neutral","#94a3b8"),("Negative",RED)]:
            fig_s.add_trace(go.Bar(name=col,x=sdf["Period"],y=sdf[col],marker_color=color))
        fig_s.update_layout(barmode="stack")
        fig_s.update_yaxes(ticksuffix="%")
        st.plotly_chart(chart_theme(fig_s,260), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with cc4:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">Platform share</p>', unsafe_allow_html=True)
        cat_rows = []
        for lbl, d in [(cur_lbl,df_c),(prev_lbl,df_p)]:
            tot = max(len(d),1)
            for plat, grp in d.groupby("platform"):
                cat_rows.append({"Period":lbl,"Platform":plat,"Pct":round(len(grp)/tot*100,1)})
        if cat_rows:
            cdf = pd.DataFrame(cat_rows)
            fig_cat = px.bar(cdf,x="Period",y="Pct",color="Platform",barmode="stack",
                color_discrete_sequence=CHART_COLORS)
            fig_cat.update_yaxes(ticksuffix="%")
            st.plotly_chart(chart_theme(fig_cat,260), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# TOPIC ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════
_TOPICS = [
    ("🏆 BAFTA Win",                 ["bafta","leading actress","award","winner","wins"]),
    ("🎬 Prisoner 951",              ["prisoner 951","prisoner951"]),
    ("🕊️ Nazanin Zaghari-Ratcliffe", ["nazanin","zaghari","ratcliffe"]),
    ("🇮🇷 Iranian Actress",          ["iranian actress","iran","persian"]),
    ("💛 Save the Children",         ["save the children","savechildren","charity"]),
    ("📺 BAFTA TV Awards 2026",      ["bafta tv","bafta television","bafta 2026"]),
    ("🎭 Film & TV Reviews",         ["review","drama","series","episode"]),
    ("🎙️ Interviews",               ["interview","speaks","talks to","q&a","in conversation"]),
]

with tab_topics:
    st.markdown(f'<h2 style="font-size:20px;font-weight:700;color:{DARK};margin-bottom:6px">Topic Analysis</h2>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:{SLATE};font-size:14px;margin-bottom:24px">Coverage automatically clustered into key themes. Mentions may appear in multiple topics.</p>', unsafe_allow_html=True)

    tp_col, _ = st.columns([2,4])
    tp_days = PERIOD_OPTS[tp_col.selectbox("Period", list(PERIOD_OPTS.keys()), key="tp_period")]
    tp_cutoff = pd.Timestamp.now() - pd.Timedelta(days=tp_days) if tp_days < 9999 else pd.Timestamp("2000-01-01")
    df_tp = df_all[df_all["date"] >= tp_cutoff].copy() if tp_days < 9999 else df_all.copy()
    df_tp["reach"] = df_tp.apply(reach_est, axis=1)
    df_tp["ave"]   = df_tp.apply(ave_est, axis=1)

    text_col = (df_tp["title"].fillna("") + " " + df_tp["snippet"].fillna("")).str.lower()
    topic_rows = []
    for name, kws in _TOPICS:
        mask = text_col.apply(lambda t: any(k in t for k in kws))
        sub = df_tp[mask]
        if sub.empty: continue
        topic_rows.append(dict(
            name=name, mentions=len(sub), reach=int(sub["reach"].sum()),
            ave=sub["ave"].sum(),
            pos=int((sub["sentiment"]=="positive").sum()),
            neg=int((sub["sentiment"]=="negative").sum()),
            kws=kws,
        ))
    if topic_rows:
        total_m = sum(r["mentions"] for r in topic_rows)
        for r in topic_rows:
            r["sov"] = r["mentions"]/total_m*100

        # SOV chart
        tc1, tc2 = st.columns([3,2])
        with tc1:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.markdown('<p class="section-title">Mentions by topic</p>', unsafe_allow_html=True)
            names_sorted = sorted(topic_rows, key=lambda x: x["mentions"])
            fig_t = go.Figure(go.Bar(
                y=[r["name"] for r in names_sorted],
                x=[r["mentions"] for r in names_sorted],
                orientation="h",
                marker=dict(color=ACCENT, opacity=0.85),
                text=[r["mentions"] for r in names_sorted],
                textposition="outside",
            ))
            fig_t.update_xaxes(gridcolor="#f1f5f9")
            st.plotly_chart(chart_theme(fig_t, 320), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with tc2:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.markdown('<p class="section-title">Share of voice</p>', unsafe_allow_html=True)
            fig_sov = px.pie(
                pd.DataFrame(topic_rows), values="sov", names="name",
                hole=0.5, color_discrete_sequence=CHART_COLORS)
            fig_sov.update_traces(textposition="inside", textinfo="percent",
                textfont=dict(size=11))
            fig_sov.update_layout(height=320, showlegend=True,
                legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=10)),
                **{k:v for k,v in PLOTLY_LAYOUT.items() if k not in ("xaxis","yaxis","legend")})
            st.plotly_chart(fig_sov, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        for r in sorted(topic_rows, key=lambda x: x["mentions"], reverse=True):
            sov_pct = r["sov"]
            st.markdown(f"""
            <div class="topic-row">
              <div class="topic-name">{r['name']}</div>
              <div class="topic-stat">
                <div class="topic-stat-val">{r['mentions']}</div>
                <div class="topic-stat-lbl">Mentions</div>
              </div>
              <div class="topic-stat">
                <div class="topic-stat-val">{fmt_reach(r['reach'])}</div>
                <div class="topic-stat-lbl">Reach</div>
              </div>
              <div class="sov-bar-wrap">
                <div class="sov-bar-bg"><div class="sov-bar-fill" style="width:{min(sov_pct,100):.0f}%"></div></div>
                <span class="sov-pct">{sov_pct:.1f}% share of voice</span>
              </div>
              <div class="topic-stat">
                <div class="topic-stat-val" style="color:{GREEN}">{r['pos']}</div>
                <div class="topic-stat-lbl">Positive</div>
              </div>
              <div class="topic-stat">
                <div class="topic-stat-val" style="color:{RED}">{r['neg']}</div>
                <div class="topic-stat-lbl">Negative</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        drill = st.selectbox("Drill into topic", [r["name"] for r in topic_rows], key="drill")
        drill_kws = next(r["kws"] for r in topic_rows if r["name"]==drill)
        drill_mask = text_col.apply(lambda t: any(k in t for k in drill_kws))
        drill_df = df_tp[drill_mask][["date","title","source","platform","tier","sentiment","url"]].copy()
        drill_df["date"] = drill_df["date"].dt.strftime("%Y-%m-%d").fillna("—")
        for c in ("title","source","platform","tier","sentiment","url"):
            drill_df[c] = drill_df[c].fillna("—")
        st.markdown(f'<p style="color:{SLATE};font-size:13px;margin-bottom:8px">{len(drill_df)} mentions for <b>{drill}</b></p>', unsafe_allow_html=True)
        st.dataframe(drill_df, use_container_width=True, height=380, hide_index=True,
            column_config={
                "url":   st.column_config.LinkColumn("Link", display_text="Open ↗"),
                "title": st.column_config.TextColumn("Title", width="large"),
                "date":  st.column_config.TextColumn("Date", width="small"),
            })
    else:
        st.info("Not enough data for topic analysis. Run the monitor to fetch more coverage.")


# ════════════════════════════════════════════════════════════════════════════════
# INSTAGRAM
# ════════════════════════════════════════════════════════════════════════════════
with tab_ig:
    st.markdown(f'<h2 style="font-size:20px;font-weight:700;color:{DARK};margin-bottom:6px">Instagram <span style="color:{SLATE};font-weight:400">@nargesrashidi</span></h2>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:{SLATE};font-size:14px;margin-bottom:20px">Her own posts · Posts that tag her · Hashtag mentions (#nargesrashidi, #prisoner951)</p>', unsafe_allow_html=True)

    if ig_all.empty:
        st.info("No Instagram data yet. Run `python3 run.py` to fetch.")
    else:
        ig_days = PERIOD_OPTS[st.selectbox("Period", list(PERIOD_OPTS.keys()), index=2, key="ig_period")]
        ig_cut  = pd.Timestamp.now() - pd.Timedelta(days=ig_days) if ig_days < 9999 else pd.Timestamp("2000-01-01")
        ig_df   = ig_all[ig_all["date"] >= ig_cut].copy() if ig_days < 9999 else ig_all.copy()

        # Source type filter
        src_types = ["All", "own_post", "tagged", "hashtag"]
        src_labels = {"own_post": "Her posts", "tagged": "Tags her", "hashtag": "Hashtag"}
        ig_src = st.selectbox("Source", src_types,
            format_func=lambda x: "All sources" if x=="All" else src_labels.get(x,x), key="ig_src")
        if ig_src != "All" and "source_type" in ig_df.columns:
            ig_df = ig_df[ig_df["source_type"] == ig_src]

        if ig_df.empty:
            st.info("No posts in this period.")
        else:
            # Coerce numeric columns
            ig_df["likes"]    = pd.to_numeric(ig_df.get("likes",    0), errors="coerce").fillna(0).astype(int)
            ig_df["comments"] = pd.to_numeric(ig_df.get("comments", 0), errors="coerce").fillna(0).astype(int)

            # KPI row
            has_src = "source_type" in ig_df.columns
            own_n    = int((ig_df["source_type"]=="own_post").sum()) if has_src else len(ig_df)
            tagged_n = int((ig_df["source_type"]=="tagged").sum())   if has_src else 0
            htag_n   = int((ig_df["source_type"]=="hashtag").sum())  if has_src else 0
            total_likes = int(ig_df["likes"].sum())
            st.markdown(f"""
            <div class="kpi-grid" style="grid-template-columns:repeat(5,1fr)">
              <div class="kpi-card">
                <div class="kpi-icon">📸</div>
                <div class="kpi-value">{len(ig_df):,}</div>
                <div class="kpi-label">Total posts</div>
              </div>
              <div class="kpi-card green">
                <div class="kpi-icon">❤️</div>
                <div class="kpi-value" style="color:{GREEN}">{total_likes:,}</div>
                <div class="kpi-label">Total likes</div>
              </div>
              <div class="kpi-card">
                <div class="kpi-icon">🏷️</div>
                <div class="kpi-value">{tagged_n}</div>
                <div class="kpi-label">Tags her</div>
              </div>
              <div class="kpi-card teal">
                <div class="kpi-icon">#️⃣</div>
                <div class="kpi-value" style="color:#0891b2">{htag_n}</div>
                <div class="kpi-label">Hashtag posts</div>
              </div>
              <div class="kpi-card purple">
                <div class="kpi-icon">👤</div>
                <div class="kpi-value" style="color:#7c3aed">{own_n}</div>
                <div class="kpi-label">Her own posts</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            ig_chart1, ig_chart2 = st.columns([3,2])
            with ig_chart1:
                if ig_df["date"].notna().any():
                    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
                    st.markdown('<p class="section-title">Likes over time</p>', unsafe_allow_html=True)
                    ig_daily = ig_df.groupby(ig_df["date"].dt.date)["likes"].sum().reset_index()
                    fig_ig = go.Figure(go.Bar(x=ig_daily["date"], y=ig_daily["likes"],
                        marker_color="#ec4899", name="Likes"))
                    fig_ig.update_yaxes(gridcolor="#f1f5f9")
                    st.plotly_chart(chart_theme(fig_ig, 240), use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

            with ig_chart2:
                if has_src and ig_df["source_type"].notna().any():
                    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
                    st.markdown('<p class="section-title">Source breakdown</p>', unsafe_allow_html=True)
                    src_counts = ig_df["source_type"].map(src_labels).value_counts().reset_index()
                    src_counts.columns = ["type", "count"]
                    fig_src = px.pie(src_counts, values="count", names="type", hole=0.5,
                        color_discrete_sequence=["#ec4899","#4f46e5","#06b6d4"])
                    fig_src.update_traces(textposition="inside", textinfo="percent+label",
                        textfont=dict(size=12))
                    fig_src.update_layout(height=240, showlegend=False,
                        **{k:v for k,v in PLOTLY_LAYOUT.items() if k not in ("xaxis","yaxis","legend")})
                    st.plotly_chart(fig_src, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

            # Sort by likes desc — most impactful first
            ig_sorted = ig_df.sort_values("likes", ascending=False)
            st.markdown(f'<p class="section-title" style="margin-top:8px">All posts ({len(ig_sorted):,}) — sorted by likes</p>', unsafe_allow_html=True)
            cols = st.columns(3)
            for i, (_, post) in enumerate(ig_sorted.head(30).iterrows()):
                with cols[i % 3]:
                    cap = (post.get("caption") or "")[:200]
                    src_type = post.get("source_type","own_post")
                    src_label = src_labels.get(src_type, src_type)
                    src_color = {"own_post":"#ec4899","tagged":"#4f46e5","hashtag":"#06b6d4"}.get(src_type,"#94a3b8")
                    username = post.get("username","")
                    htag = post.get("hashtag","")
                    src_display = f"#{htag}" if src_type=="hashtag" and htag else (f"@{username}" if username else "")
                    st.markdown(f"""
                    <div class="ig-card">
                      <div class="ig-date">
                        {post['date']} ·
                        <span style="background:{src_color}20;color:{src_color};padding:1px 8px;border-radius:100px;font-size:11px;font-weight:600">{src_label}</span>
                        {f'<span style="color:{SLATE};font-size:12px">&nbsp;{src_display}</span>' if src_display else ''}
                      </div>
                      <p class="ig-caption">{cap}</p>
                      <div class="ig-stats">
                        <span>❤️ {post.get('likes',0):,}</span>
                        <span>💬 {post.get('comments',0):,}</span>
                      </div>
                      <a href="{post.get('url','')}" target="_blank" class="ig-link">View on Instagram ↗</a>
                    </div>
                    """, unsafe_allow_html=True)

st.markdown(f"""
<div style="text-align:center;padding:40px 0 20px;color:{SLATE};font-size:12px">
  If I Only Knew PR &nbsp;·&nbsp; Narges Rashidi Press Monitor &nbsp;·&nbsp; Updates every Monday
</div>
""", unsafe_allow_html=True)
