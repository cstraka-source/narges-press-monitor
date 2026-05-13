"""
Narges Rashidi — Press Intelligence Dashboard
If I Only Knew PR

Live:   https://narges-press-monitor.streamlit.app
Local:  streamlit run dashboard.py
"""
import io
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

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

# ── Block search engine indexing ──────────────────────────────────────────────
st.html("""
<meta name="robots" content="noindex, nofollow, noarchive, nosnippet, noimageindex">
<meta name="googlebot" content="noindex, nofollow">
<meta name="bingbot" content="noindex, nofollow">
""")


# ── Password gate ─────────────────────────────────────────────────────────────
def check_password() -> bool:
    """Returns True if user has entered the correct password (or no password is set)."""
    try:
        required_pw = st.secrets.get("DASHBOARD_PASSWORD", "")
    except Exception:
        required_pw = ""

    # No password configured (e.g. local dev) → allow through
    if not required_pw:
        return True

    if st.session_state.get("auth_ok"):
        return True

    # Hide sidebar on the login screen
    st.html("""
    <style>
      [data-testid="stSidebar"] { display: none !important; }
      [data-testid="collapsedControl"] { display: none !important; }
      .block-container { max-width: 480px !important; padding-top: 6rem !important; }
      #MainMenu, footer, header { visibility: hidden; }
    </style>
    """)

    st.markdown("""
    <div style="text-align:center;margin-bottom:32px;">
      <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;font-weight:700;margin-bottom:8px;">
        If I Only Knew PR
      </div>
      <div style="font-size:32px;font-weight:800;color:#0f172a;letter-spacing:-0.03em;line-height:1.1;">
        Narges Rashidi
      </div>
      <div style="font-size:14px;color:#64748b;margin-top:6px;">
        Press Intelligence Dashboard
      </div>
    </div>
    <div style="background:white;border:1px solid #e2e8f0;border-radius:14px;padding:32px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
      <div style="font-size:14px;font-weight:600;color:#0f172a;margin-bottom:4px;">Sign in</div>
      <div style="font-size:13px;color:#64748b;margin-bottom:20px;">Enter the access password to continue.</div>
    </div>
    """, unsafe_allow_html=True)

    pw = st.text_input("Password", type="password", label_visibility="collapsed",
                       placeholder="Password", key="pw_input")
    if st.button("Sign in", type="primary", use_container_width=True):
        if pw == required_pw:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    return False


if not check_password():
    st.stop()

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

CHART_PALETTE = [ACCENT, TEAL, GREEN, AMBER, RED, PURPLE, PINK, "#0ea5e9", "#84cc16"]

# Emotion lexicon — keyword-based emotional analysis
EMOTION_KEYWORDS = {
    "Joy":          ["win","won","brilliant","amazing","wonderful","beautiful","celebrate","congratulations","incredible","fantastic","love","perfect","best","triumph","happy","delighted","thrilled","proud"],
    "Trust":        ["authentic","honest","powerful","important","genuine","reliable","deserved","trust","integrity","dignity","truth"],
    "Surprise":     ["surprise","shocking","unexpected","stunning","incredible","wow","extraordinary","remarkable"],
    "Sadness":      ["sad","tragic","heartbreaking","devastating","loss","grief","sorrow","mourning","pain"],
    "Fear":         ["fear","scared","afraid","worried","anxious","frightening","danger","threat"],
    "Anger":        ["anger","outraged","furious","angry","disgusting","appalling","unacceptable"],
    "Anticipation": ["upcoming","excited","looking forward","next","soon","anticipation","preview","new"],
    "Disgust":      ["disgusted","disgust","disturbing","offensive","awful","terrible","horrible"],
}
EMOTION_COLORS = {
    "Joy": "#facc15", "Trust": "#22c55e", "Surprise": "#a855f7",
    "Sadness": "#3b82f6", "Fear": "#64748b", "Anger": "#ef4444",
    "Anticipation": "#fb923c", "Disgust": "#a16207",
}


# ── CSS (reliable via st.html) ────────────────────────────────────────────────
st.html("""
<style>
  html, body, [class*="st-"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
  }
  [data-testid="stDeployButton"] { display: none; }
  #MainMenu, footer { visibility: hidden; }

  [data-testid="stSidebar"] { background: #0f172a; }
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
  [data-testid="stSidebar"] [data-baseweb="tag"] {
    background: #4f46e5 !important;
    color: white !important;
  }
  [data-testid="stSidebar"] button {
    background: #4f46e5 !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
  }

  .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1600px; }

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
    font-size: 12px !important; color: #64748b !important;
    text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.75rem !important; font-weight: 800 !important;
    color: #0f172a !important; letter-spacing: -0.02em; line-height: 1.1;
  }
  [data-testid="stMetricDelta"] { font-size: 12px !important; font-weight: 600 !important; }

  hr { border-color: #e2e8f0 !important; margin: 2rem 0 !important; }

  [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent !important;
    border-bottom: 1px solid #e2e8f0;
    overflow-x: auto;
  }
  [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 10px 18px !important;
    font-weight: 500 !important;
    color: #64748b !important;
    white-space: nowrap;
  }
  [aria-selected="true"][data-baseweb="tab"] {
    color: #4f46e5 !important;
    font-weight: 600 !important;
  }

  [data-testid="stDataFrame"] {
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    overflow: hidden;
  }

  .stButton button {
    border-radius: 10px;
    font-weight: 600;
  }

  [data-baseweb="select"] > div {
    border-radius: 10px !important;
    border-color: #e2e8f0 !important;
  }

  .hero {
    padding: 8px 0 24px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 32px;
  }
  .hero-eyebrow { color: #64748b; font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 4px; }
  .hero-title { font-size: 28px; font-weight: 800; color: #0f172a; letter-spacing: -0.03em; margin: 0; }
  .hero-subtitle { color: #64748b; font-size: 15px; margin-top: 4px; }

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
    font-size: 14px; font-weight: 600; color: #0f172a;
    margin: 0 0 6px; line-height: 1.4; text-decoration: none; display: block;
  }
  .story-title:hover { color: #4f46e5; }
  .story-meta { font-size: 12px; color: #64748b; margin-bottom: 8px; }
  .story-snippet { font-size: 13px; color: #475569; line-height: 1.5; margin: 0; }

  .pill {
    display: inline-block; padding: 2px 9px; border-radius: 100px;
    font-size: 11px; font-weight: 600; margin-right: 4px;
  }
  .pill-t1 { background: #e0e7ff; color: #4338ca; }
  .pill-t2 { background: #d1fae5; color: #047857; }
  .pill-t3 { background: #f1f5f9; color: #64748b; }
  .pill-pos { background: #d1fae5; color: #047857; }
  .pill-neg { background: #fee2e2; color: #b91c1c; }
  .pill-neu { background: #f1f5f9; color: #64748b; }

  .hashtag-pill {
    display: inline-flex; align-items: baseline; gap: 6px;
    background: #f1f5f9; padding: 6px 12px; border-radius: 100px;
    margin: 4px 6px 4px 0; font-size: 13px; color: #0f172a;
    transition: all 0.15s; cursor: default;
  }
  .hashtag-pill:hover { background: #e0e7ff; }
  .hashtag-pill b { color: #4f46e5; font-weight: 700; }
  .hashtag-count { font-size: 11px; color: #64748b; font-weight: 700; }

  .domain-row {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; background: white; border: 1px solid #e2e8f0;
    border-radius: 10px; margin-bottom: 8px;
  }
  .domain-row b { font-weight: 600; color: #0f172a; flex: 1; font-size: 13px; }
  .domain-row .count { font-weight: 700; color: #4f46e5; font-size: 14px; }

  .source-card {
    background: white; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 16px; transition: all 0.15s;
  }
  .source-card:hover { box-shadow: 0 6px 20px rgba(0,0,0,0.08); }
  .source-name { font-weight: 700; font-size: 14px; color: #0f172a; margin-bottom: 4px; }
  .source-meta { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
  .source-stat { font-size: 18px; font-weight: 800; color: #4f46e5; margin: 8px 0 0; }

  .filter-chip {
    display: inline-flex; align-items: center; gap: 6px;
    background: #e0e7ff; color: #4338ca; padding: 4px 12px;
    border-radius: 100px; font-size: 12px; font-weight: 600;
    margin: 0 6px 6px 0;
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
    if plat == "YouTube":         return v
    if plat in ("TikTok","Facebook"): return v * 3
    if tier == "Tier 1":          return 850_000
    if tier == "Tier 2":          return 120_000
    return 15_000


def ave_est(row) -> float:
    tier, plat = str(row.get("tier") or "Tier 3"), str(row.get("platform") or "")
    v = _safe_int(row.get("views"))
    if plat == "YouTube":          return v * 0.003
    if plat in ("TikTok","Facebook"): return v * 0.002
    if tier == "Tier 1":           return 2500.0
    if tier == "Tier 2":           return 350.0
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
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="-apple-system, sans-serif", color=DARK, size=12),
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11, color=SLATE), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="white", bordercolor=BORDER, font=dict(family="-apple-system, sans-serif")),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(color=SLATE, size=11))
    fig.update_yaxes(gridcolor="#f1f5f9", zeroline=False, tickfont=dict(color=SLATE, size=11))
    return fig


def tier_pill(t):
    n = str(t or "Tier 3")[-1]
    return f'<span class="pill pill-t{n}">{t or ""}</span>'


def sent_pill(s):
    s = (str(s) if s else "neutral").lower()
    return f'<span class="pill pill-{s[:3]}">{s.capitalize()}</span>'


# ── Hashtag, domain, emoji extractors ─────────────────────────────────────────
HASHTAG_RE = re.compile(r"#(\w{2,30})", re.UNICODE)
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA70-\U0001FAFF"  # extended symbols
    "]", flags=re.UNICODE
)


def extract_hashtags(text: str) -> list[str]:
    return [h.lower() for h in HASHTAG_RE.findall(text or "")]


def extract_emojis(text: str) -> list[str]:
    return EMOJI_RE.findall(text or "")


def extract_domain(url: str) -> str:
    try:
        d = urlparse(url).netloc.replace("www.", "")
        return d.split("/")[0] if d else ""
    except Exception:
        return ""


def compute_emotions(texts: list[str]) -> dict[str, int]:
    counts = {e: 0 for e in EMOTION_KEYWORDS}
    for t in texts:
        if not t:
            continue
        lt = t.lower()
        for emotion, kws in EMOTION_KEYWORDS.items():
            for kw in kws:
                if kw in lt:
                    counts[emotion] += 1
                    break  # one hit per text per emotion
    return counts


def compute_presence_score(df: pd.DataFrame) -> int:
    """0-100 score based on mentions, reach, tier mix, sentiment balance."""
    if df.empty:
        return 0
    n          = len(df)
    reach      = df.apply(reach_est, axis=1).sum() if not df.empty else 0
    t1_share   = (df["tier"]=="Tier 1").mean() if not df.empty else 0
    pos_share  = (df["sentiment"]=="positive").mean() if not df.empty else 0
    neg_share  = (df["sentiment"]=="negative").mean() if not df.empty else 0

    score_mentions = min(n / 50, 1.0) * 30
    score_reach    = min(reach / 5_000_000, 1.0) * 30
    score_tier1    = t1_share * 25
    score_sent     = max(0, (pos_share - neg_share)) * 15
    return int(score_mentions + score_reach + score_tier1 + score_sent)


# ── Data ──────────────────────────────────────────────────────────────────────
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
        for c in ("likes","comments"):
            if c in ig.columns:
                ig[c] = pd.to_numeric(ig[c], errors="coerce").fillna(0).astype(int)
    return df, ig


df_all, ig_all = load_data()

# Initialize session-state filters (for cross-tab quick filters)
for k, default in [("qf_source", []), ("qf_hashtag", []), ("qf_topic", None)]:
    if k not in st.session_state:
        st.session_state[k] = default


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

    # Period
    PERIODS = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30,
               "Last 60 days": 60, "Last 90 days": 90, "All time": 9999,
               "Custom range": -1}
    period_lbl = st.selectbox("Time period", list(PERIODS.keys()), index=2)
    if PERIODS[period_lbl] == -1:
        today = pd.Timestamp.now().date()
        dr = st.date_input("Pick range", (today - timedelta(days=30), today), key="custom_dr")
        if isinstance(dr, tuple) and len(dr) == 2:
            cutoff_start, cutoff_end = pd.Timestamp(dr[0]), pd.Timestamp(dr[1]) + pd.Timedelta(days=1)
        else:
            cutoff_start = pd.Timestamp(today - timedelta(days=30))
            cutoff_end   = pd.Timestamp(today) + pd.Timedelta(days=1)
    else:
        DAYS = PERIODS[period_lbl]
        cutoff_end   = pd.Timestamp.now() + pd.Timedelta(days=1)
        cutoff_start = (pd.Timestamp.now() - pd.Timedelta(days=DAYS)) if DAYS < 9999 else pd.Timestamp("2000-01-01")

    # Platforms (multi-select)
    platforms_avail = sorted(df_all["platform"].dropna().unique().tolist())
    f_platforms = st.multiselect("Platforms", platforms_avail, default=[],
        help="Empty = all platforms")

    # Tiers (multi-select)
    f_tiers = st.multiselect("Tiers", ["Tier 1", "Tier 2", "Tier 3"], default=[])

    # Sentiment (multi-select)
    f_sents = st.multiselect("Sentiment", ["positive", "neutral", "negative"], default=[],
        format_func=str.capitalize)

    # Types
    types_avail = sorted(df_all["type"].dropna().unique().tolist())
    f_types = st.multiselect("Coverage type", types_avail, default=[])

    # Sources (multi-select with autocomplete)
    sources_avail = sorted(df_all["source"].dropna().unique().tolist())
    f_sources = st.multiselect("Sources", sources_avail,
        default=st.session_state["qf_source"], key="qf_source",
        help="Pick specific outlets (or use chart/sidebar quick filters)")

    # Min reach slider
    f_min_reach = st.slider("Min estimated reach", 0, 1_000_000, 0, step=50_000,
        format="%dK" if False else "%d")

    # Search
    f_search = st.text_input("Keyword search", placeholder="e.g. BAFTA, Prisoner 951")

    st.divider()

    def _clear_filters():
        # Callback runs before the next script run, so we can mutate
        # widget-bound session_state without hitting the API error.
        for k in ("qf_source",):
            if k in st.session_state:
                del st.session_state[k]

    refresh_col, clear_col = st.columns(2)
    if refresh_col.button("↺  Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    clear_col.button("✕  Clear filters", use_container_width=True, on_click=_clear_filters)

    last_update = df_all["created_at"].max() if not df_all.empty else "—"
    st.markdown(f"""
    <div style="margin-top:16px;font-size:11px;color:#94a3b8;line-height:1.7;">
      <div><b style="color:#cbd5e1">{len(df_all):,}</b> total items</div>
      <div>Updated {str(last_update)[:10]}</div>
      <div style="margin-top:6px;color:#64748b;">Auto-updates Monday 8am</div>
    </div>
    """, unsafe_allow_html=True)


# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_all[(df_all["date"] >= cutoff_start) & (df_all["date"] < cutoff_end)].copy()
if f_platforms: df = df[df["platform"].isin(f_platforms)]
if f_tiers:     df = df[df["tier"].isin(f_tiers)]
if f_sents:     df = df[df["sentiment"].isin(f_sents)]
if f_types:     df = df[df["type"].isin(f_types)]
if f_sources:   df = df[df["source"].isin(f_sources)]
if f_search:
    m = (df["title"].str.contains(f_search, case=False, na=False) |
         df["snippet"].str.contains(f_search, case=False, na=False) |
         df["source"].str.contains(f_search, case=False, na=False))
    if "full_text" in df.columns:
        m = m | df["full_text"].str.contains(f_search, case=False, na=False)
    df = df[m]

if not df.empty:
    df["reach_calc"] = df.apply(reach_est, axis=1)
    df["ave_calc"]   = df.apply(ave_est, axis=1)
    if f_min_reach > 0:
        df = df[df["reach_calc"] >= f_min_reach]
else:
    df["reach_calc"] = []
    df["ave_calc"]   = []


# ── HERO ──────────────────────────────────────────────────────────────────────
chips = []
if f_platforms: chips.append(f"📱 {', '.join(f_platforms)}")
if f_tiers:     chips.append(f"⭐ {', '.join(f_tiers)}")
if f_sents:     chips.append(f"😊 {', '.join(s.capitalize() for s in f_sents)}")
if f_types:     chips.append(f"📂 {', '.join(f_types)}")
if f_sources:   chips.append(f"📰 {len(f_sources)} source" + ("s" if len(f_sources)!=1 else ""))
if f_search:    chips.append(f'🔍 "{f_search}"')
if f_min_reach: chips.append(f"📊 ≥ {fmt_compact(f_min_reach)} reach")

chip_html = " ".join(f'<span class="filter-chip">{c}</span>' for c in chips)

st.markdown(f"""
<div class="hero">
  <div class="hero-eyebrow">Press Intelligence</div>
  <h1 class="hero-title">Narges Rashidi</h1>
  <p class="hero-subtitle">
    {period_lbl} &nbsp;·&nbsp; <b style="color:#0f172a">{len(df):,}</b> mentions in view
  </p>
  <div style="margin-top:12px">{chip_html}</div>
</div>
""", unsafe_allow_html=True)


# ── KEY METRICS (with deltas) ─────────────────────────────────────────────────
pos_n = int((df["sentiment"]=="positive").sum())
neg_n = int((df["sentiment"]=="negative").sum())
t1_n  = int((df["tier"]=="Tier 1").sum())
reach_total = int(df["reach_calc"].sum()) if not df.empty else 0
ave_total   = float(df["ave_calc"].sum())  if not df.empty else 0
pos_pct = round(pos_n / max(len(df), 1) * 100)
presence_score = compute_presence_score(df)

# Comparison vs previous equivalent period
period_n_days = (cutoff_end - cutoff_start).days
prev_start = cutoff_start - pd.Timedelta(days=period_n_days)
df_prev = df_all[(df_all["date"] >= prev_start) & (df_all["date"] < cutoff_start)].copy()
if f_platforms: df_prev = df_prev[df_prev["platform"].isin(f_platforms)]
if f_tiers:     df_prev = df_prev[df_prev["tier"].isin(f_tiers)]
if f_sources:   df_prev = df_prev[df_prev["source"].isin(f_sources)]
if not df_prev.empty:
    df_prev["reach_calc"] = df_prev.apply(reach_est, axis=1)
prev_mentions = len(df_prev)
prev_pos      = int((df_prev["sentiment"]=="positive").sum()) if not df_prev.empty else 0
prev_t1       = int((df_prev["tier"]=="Tier 1").sum())       if not df_prev.empty else 0
prev_reach    = int(df_prev["reach_calc"].sum())              if not df_prev.empty else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total mentions",  f"{len(df):,}",            fmt_pct_delta(len(df), prev_mentions))
c2.metric("Positive",        f"{pos_n}",                f"{pos_pct}% positive")
c3.metric("Negative",        f"{neg_n}")
c4.metric("Tier 1 hits",     f"{t1_n}",                 fmt_pct_delta(t1_n, prev_t1))
c5.metric("Reach",           fmt_compact(reach_total),  fmt_pct_delta(reach_total, prev_reach))
c6.metric("Presence Score",  f"{presence_score}/100",   "out of 100")


# ── TABS ──────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "Overview", "Top Stories", "Sources & Influence", "Trends & Topics",
    "Compare Periods", "Topic Analysis", "Instagram", "✨ Ask AI",
])
(tab_overview, tab_stories, tab_sources, tab_trends,
 tab_compare, tab_topics, tab_ig, tab_ai) = tabs


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ════════════════════════════════════════════════════════════════════════════════
with tab_overview:
    if df.empty:
        st.info("No data matches the current filters. Try widening them.")
    else:
        # ── Mentions & reach combined chart ──
        st.subheader("Mentions & reach over time")
        daily = df.groupby(df["date"].dt.date).agg(
            mentions=("id", "count"),
            reach=("reach_calc", "sum"),
        ).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily["date"], y=daily["mentions"], name="Mentions",
            line=dict(color=ACCENT, width=3), fill="tozeroy", fillcolor="rgba(79,70,229,0.08)",
            yaxis="y", hovertemplate="<b>%{x}</b><br>%{y} mentions<extra></extra>"))
        fig.add_trace(go.Scatter(x=daily["date"], y=daily["reach"], name="Reach",
            line=dict(color=TEAL, width=3, dash="dot"), yaxis="y2",
            hovertemplate="<b>%{x}</b><br>%{y:,.0f} reach<extra></extra>"))
        fig.update_layout(
            yaxis=dict(title=dict(text="Mentions", font=dict(color=ACCENT)), gridcolor="#f1f5f9"),
            yaxis2=dict(title=dict(text="Reach", font=dict(color=TEAL)),
                        overlaying="y", side="right", showgrid=False, tickformat=".2s"),
        )
        st.plotly_chart(style_chart(fig, 320), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Sentiment & platform & tier ──
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown("##### Platform mix")
            plat = df.groupby("platform").size().reset_index(name="n").sort_values("n", ascending=False)
            fig = go.Figure(go.Pie(labels=plat["platform"], values=plat["n"], hole=0.55,
                marker=dict(colors=CHART_PALETTE),
                textinfo="label+percent", textfont=dict(size=11)))
            fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=0,b=0), height=260, paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        with a2:
            st.markdown("##### Sentiment")
            if df["sentiment"].notna().any():
                sd = df[df["sentiment"].notna()].groupby("sentiment").size().reset_index(name="n")
                cmap = {"positive": GREEN, "neutral": MUTED, "negative": RED}
                fig = go.Figure(go.Pie(labels=sd["sentiment"].str.capitalize(), values=sd["n"], hole=0.55,
                    marker=dict(colors=[cmap.get(s, MUTED) for s in sd["sentiment"]]),
                    textinfo="label+percent", textfont=dict(size=11)))
                fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=0,b=0), height=260, paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
        with a3:
            st.markdown("##### Tier mix")
            td = df.groupby("tier").size().reset_index(name="n")
            colors_map = {"Tier 1": ACCENT, "Tier 2": GREEN, "Tier 3": MUTED}
            fig = go.Figure(go.Bar(
                x=td["tier"], y=td["n"],
                marker_color=[colors_map.get(t, MUTED) for t in td["tier"]],
                text=td["n"], textposition="outside",
                textfont=dict(size=12, color=DARK)))
            st.plotly_chart(style_chart(fig, 260), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Sentiment over time ──
        st.subheader("Sentiment over time")
        if df["sentiment"].notna().any():
            sent_daily = df.groupby([df["date"].dt.date, "sentiment"]).size().reset_index(name="n")
            fig = go.Figure()
            for sent, color in [("positive", GREEN), ("negative", RED), ("neutral", MUTED)]:
                sub = sent_daily[sent_daily["sentiment"]==sent]
                if not sub.empty:
                    fig.add_trace(go.Scatter(x=sub["date"], y=sub["n"], name=sent.capitalize(),
                        line=dict(color=color, width=2),
                        hovertemplate=f"<b>%{{x}}</b><br>%{{y}} {sent}<extra></extra>"))
            st.plotly_chart(style_chart(fig, 260), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — TOP STORIES
# ════════════════════════════════════════════════════════════════════════════════
with tab_stories:
    if df.empty:
        st.info("No coverage in this period.")
    else:
        sort_by = st.selectbox("Sort by", ["Reach (highest first)", "Date (newest first)", "Date (oldest first)"],
            label_visibility="collapsed", key="story_sort")
        if "Date (newest" in sort_by:    top = df.sort_values("date", ascending=False)
        elif "Date (oldest" in sort_by:  top = df.sort_values("date", ascending=True)
        else:                            top = df.sort_values("reach_calc", ascending=False)

        st.subheader(f"All {len(df):,} mentions")
        for _, row in top.head(40).iterrows():
            url = row.get("url") or ""
            title = (row.get("title") or "Untitled")[:140]
            src = row.get("source") or "—"
            date_s = row["date"].strftime("%d %b %Y") if pd.notna(row.get("date")) else ""
            plat = row.get("platform") or ""
            snip = (row.get("snippet") or "")[:200]
            link_html = (f'<a href="{url}" target="_blank" class="story-title">{title}</a>'
                         if url else f'<span class="story-title">{title}</span>')
            st.markdown(f"""
            <div class="story-card">
              {link_html}
              <div class="story-meta">
                <b>{src}</b> &nbsp;·&nbsp; {date_s} &nbsp;·&nbsp; {plat}
                &nbsp; {tier_pill(row.get('tier'))} {sent_pill(row.get('sentiment'))}
                &nbsp; <span style="color:{SLATE};">Reach ~{fmt_compact(row['reach_calc'])}</span>
              </div>
              <p class="story-snippet">{snip}</p>
            </div>
            """, unsafe_allow_html=True)

        if len(df) > 40:
            st.caption(f"Showing first 40 of {len(df):,}. Use filters or table below to see more.")

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📊 Browse all as table"):
            tbl = df[["date","title","source","platform","tier","type","sentiment","reach_calc","url"]].copy()
            tbl["date"] = tbl["date"].dt.strftime("%Y-%m-%d")
            tbl = tbl.rename(columns={
                "date":"Date","title":"Title","source":"Source","platform":"Platform",
                "tier":"Tier","type":"Type","sentiment":"Sentiment","reach_calc":"Reach","url":"Link",
            })
            st.dataframe(tbl, use_container_width=True, height=500, hide_index=True,
                column_config={
                    "Link": st.column_config.LinkColumn(width="small", display_text="Open ↗"),
                    "Title": st.column_config.TextColumn(width="large"),
                    "Reach": st.column_config.NumberColumn(format="%d"),
                })


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — SOURCES & INFLUENCE
# ════════════════════════════════════════════════════════════════════════════════
with tab_sources:
    if df.empty:
        st.info("No data.")
    else:
        st.subheader("Most active sources")
        st.caption("Outlets and accounts driving coverage. Click any source to filter the whole dashboard.")

        src_grp = (df.groupby("source").agg(
            mentions=("id", "count"),
            reach=("reach_calc", "sum"),
            tier=("tier", "first"),
            platform=("platform", "first"),
            positive=("sentiment", lambda s: (s=="positive").sum()),
            negative=("sentiment", lambda s: (s=="negative").sum()),
        ).reset_index())
        src_grp["share_of_voice"] = src_grp["mentions"] / src_grp["mentions"].sum() * 100
        src_grp = src_grp.sort_values("mentions", ascending=False)

        # Top sources display + quick filter
        top_n = min(12, len(src_grp))
        for i in range(0, top_n, 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i+j >= top_n: break
                r = src_grp.iloc[i+j]
                with col:
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"""
                        <div class="source-name">{r['source']}</div>
                        <div class="source-meta">{r['platform']} · {r['tier']}</div>
                        <div style="margin-top:10px;display:flex;gap:18px;">
                          <div><div style="font-size:18px;font-weight:800;color:{ACCENT};">{r['mentions']}</div><div style="font-size:10px;color:{SLATE};text-transform:uppercase;font-weight:600;">Mentions</div></div>
                          <div><div style="font-size:18px;font-weight:800;color:{TEAL};">{fmt_compact(r['reach'])}</div><div style="font-size:10px;color:{SLATE};text-transform:uppercase;font-weight:600;">Reach</div></div>
                          <div><div style="font-size:18px;font-weight:800;color:{PURPLE};">{r['share_of_voice']:.1f}%</div><div style="font-size:10px;color:{SLATE};text-transform:uppercase;font-weight:600;">SoV</div></div>
                        </div>
                        """, unsafe_allow_html=True)
                        if c2.button("Filter", key=f"flt_src_{r['source']}_{i}_{j}", use_container_width=True):
                            st.session_state["qf_source"] = [r["source"]]
                            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("Share of voice ranking")
        ranking_df = src_grp.head(20).copy()
        ranking_df["Sentiment"] = ranking_df.apply(
            lambda r: f"+{r['positive']} / -{r['negative']}", axis=1)
        ranking_df["Reach"] = ranking_df["reach"].apply(fmt_compact)
        ranking_df["SoV"]   = ranking_df["share_of_voice"]
        ranking_df = ranking_df[["source","mentions","Reach","SoV","Sentiment","platform","tier"]]
        ranking_df.columns = ["Source", "Mentions", "Reach", "Share of voice", "Sentiment +/-", "Platform", "Tier"]
        st.dataframe(ranking_df, use_container_width=True, hide_index=True,
            column_config={
                "Source": st.column_config.TextColumn(width="medium"),
                "Share of voice": st.column_config.ProgressColumn(
                    "Share of voice", min_value=0, max_value=float(src_grp["share_of_voice"].max()),
                    format="%.1f%%"
                ),
            })

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("Sentiment by source (top 10)")
        sent_src = src_grp.head(10).copy()
        sent_src["neutral"] = sent_src["mentions"] - sent_src["positive"] - sent_src["negative"]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Positive", x=sent_src["source"], y=sent_src["positive"], marker_color=GREEN))
        fig.add_trace(go.Bar(name="Neutral",  x=sent_src["source"], y=sent_src["neutral"],  marker_color=MUTED))
        fig.add_trace(go.Bar(name="Negative", x=sent_src["source"], y=sent_src["negative"], marker_color=RED))
        fig.update_layout(barmode="stack")
        st.plotly_chart(style_chart(fig, 320), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — TRENDS & TOPICS (hashtags, links, emojis, hot hours, word cloud, emotions)
# ════════════════════════════════════════════════════════════════════════════════
with tab_trends:
    if df.empty:
        st.info("No data in this period.")
    else:
        # ── Trending hashtags ──
        all_text = " ".join(((df["title"].fillna("") + " " + df["snippet"].fillna("") + " " + df["full_text"].fillna(""))).tolist())
        hashtags = extract_hashtags(all_text)
        hashtag_counts = Counter(hashtags).most_common(20)

        h1, h2 = st.columns(2)
        with h1:
            st.subheader("Trending hashtags")
            if hashtag_counts:
                html = "".join(
                    f'<span class="hashtag-pill"><b>#{tag}</b><span class="hashtag-count">{n}</span></span>'
                    for tag, n in hashtag_counts[:18]
                )
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.info("No hashtags found in this period.")

        with h2:
            st.subheader("Trending links")
            urls = df["url"].dropna().tolist()
            domains = [extract_domain(u) for u in urls if extract_domain(u)]
            domain_counts = Counter(domains).most_common(12)
            if domain_counts:
                for dom, n in domain_counts:
                    pct = n / max(len(urls), 1) * 100
                    st.markdown(f"""
                    <div class="domain-row">
                      <b>{dom}</b>
                      <span class="count">{n}</span>
                      <span style="color:{SLATE};font-size:11px;">{pct:.1f}%</span>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Hot hours heatmap ──
        st.subheader("Hot hours — when coverage breaks")
        st.caption("Day-of-week × hour heatmap. Darker = more mentions.")
        if df["date"].notna().any():
            hh = df.copy()
            hh["dow"]  = hh["date"].dt.dayofweek
            hh["hour"] = hh["date"].dt.hour
            DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            grid = hh.groupby(["dow","hour"]).size().unstack(fill_value=0)
            grid = grid.reindex(index=range(7), columns=range(24), fill_value=0)
            grid.index = [DOW[i] for i in grid.index]
            fig = go.Figure(go.Heatmap(
                z=grid.values, x=[f"{h:02d}" for h in range(24)], y=grid.index,
                colorscale=[[0,"#f1f5f9"], [0.3,"#c7d2fe"], [0.7,"#6366f1"], [1,"#312e81"]],
                hovertemplate="<b>%{y} %{x}:00</b><br>%{z} mentions<extra></extra>",
                showscale=True, colorbar=dict(title=dict(text="mentions"), thickness=14),
            ))
            fig.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0),
                              plot_bgcolor="white", paper_bgcolor="white",
                              font=dict(family="-apple-system, sans-serif", color=DARK))
            fig.update_xaxes(side="top", tickfont=dict(size=10, color=SLATE), showgrid=False)
            fig.update_yaxes(tickfont=dict(size=11, color=SLATE), showgrid=False)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Word cloud + emotions ──
        wc_col, em_col = st.columns([3, 2])

        with wc_col:
            st.subheader("Context of discussion")
            st.caption("Most frequent terms across all coverage")
            from wordcloud import WordCloud, STOPWORDS
            text_blob = (df["title"].fillna("") + " " + df["snippet"].fillna("")).str.cat(sep=" ")
            # Custom stopwords
            sw = set(STOPWORDS)
            sw.update(["narges", "rashidi", "the", "says", "say", "said", "will", "one",
                       "new", "now", "amp", "https", "http", "com", "via", "won"])
            if text_blob.strip():
                wc = WordCloud(
                    width=900, height=400,
                    background_color="white",
                    colormap="viridis",
                    stopwords=sw,
                    max_words=80,
                    relative_scaling=0.5,
                    min_font_size=10,
                    font_path=None,
                ).generate(text_blob)
                import matplotlib.pyplot as plt
                fig_wc, ax = plt.subplots(figsize=(10, 4.5))
                ax.imshow(wc, interpolation="bilinear")
                ax.axis("off")
                fig_wc.patch.set_facecolor("white")
                buf = io.BytesIO()
                fig_wc.savefig(buf, format="png", bbox_inches="tight", dpi=120, facecolor="white")
                plt.close(fig_wc)
                buf.seek(0)
                st.image(buf, use_container_width=True)

        with em_col:
            st.subheader("Emotion analysis")
            st.caption("Detected emotional tone in coverage")
            texts = (df["title"].fillna("") + " " + df["snippet"].fillna("")).tolist()
            emotions = compute_emotions(texts)
            em_df = pd.DataFrame([
                {"emotion": e, "n": v} for e, v in emotions.items() if v > 0
            ]).sort_values("n", ascending=False) if any(emotions.values()) else pd.DataFrame()

            if not em_df.empty:
                total = em_df["n"].sum()
                em_df["pct"] = em_df["n"] / total * 100
                fig_em = go.Figure(go.Pie(
                    labels=em_df["emotion"], values=em_df["n"], hole=0.5,
                    marker=dict(colors=[EMOTION_COLORS.get(e, MUTED) for e in em_df["emotion"]]),
                    textinfo="label+percent", textfont=dict(size=11),
                    hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>",
                ))
                fig_em.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=320, paper_bgcolor="white", showlegend=False)
                st.plotly_chart(fig_em, use_container_width=True)
            else:
                st.info("Not enough data for emotion analysis.")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Most popular emojis ──
        st.subheader("Most popular emojis")
        all_emojis = []
        for txt in (df["snippet"].fillna("") + " " + df["title"].fillna("") + " " + df["full_text"].fillna("")).tolist():
            all_emojis.extend(extract_emojis(txt))
        emoji_counts = Counter(all_emojis).most_common(20)
        # Also include Instagram emojis
        if not ig_all.empty and "caption" in ig_all.columns:
            for cap in ig_all["caption"].fillna("").tolist():
                all_emojis.extend(extract_emojis(cap))
            emoji_counts = Counter(all_emojis).most_common(20)

        if emoji_counts:
            cols = st.columns(10)
            for i, (em, n) in enumerate(emoji_counts[:10]):
                with cols[i]:
                    st.markdown(f"""
                    <div style="text-align:center;padding:14px 0;background:white;border:1px solid {BORDER};border-radius:12px;">
                      <div style="font-size:36px;line-height:1;">{em}</div>
                      <div style="margin-top:6px;font-size:13px;font-weight:700;color:{ACCENT};">{n}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No emojis found in coverage.")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — COMPARE PERIODS
# ════════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.subheader("Compare periods")
    st.caption("Current vs preceding equivalent period")

    cur_lbl = st.selectbox("Current period",
        ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"],
        index=2, key="cmp_cur_lbl")
    cur_n = PERIODS[cur_lbl]
    now = pd.Timestamp.now()
    cur_start  = now - pd.Timedelta(days=cur_n)
    prev_start_c = cur_start - pd.Timedelta(days=cur_n)

    dC = df_all[df_all["date"] >= cur_start].copy()
    dP = df_all[(df_all["date"] >= prev_start_c) & (df_all["date"] < cur_start)].copy()
    for d in (dC, dP):
        if not d.empty:
            d["reach_calc"] = d.apply(reach_est, axis=1)
            d["ave_calc"]   = d.apply(ave_est, axis=1)

    SOCIAL = {"TikTok","Facebook","Bluesky","Instagram"}
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
    prev_range = f"{prev_start_c.strftime('%d %b')} – {cur_start.strftime('%d %b')}"

    rows = [
        ("Total mentions",        mc["total"],     mp["total"],     ""),
        ("Social media",          mc["social"],    mp["social"],    ""),
        ("Non-social media",      mc["nonsocial"], mp["nonsocial"], ""),
        ("Positive",              mc["pos"],       mp["pos"],       ""),
        ("Negative",              mc["neg"],       mp["neg"],       ""),
        ("Tier 1 hits",           mc["t1"],        mp["t1"],        ""),
        ("Social reach",          mc["sreach"],    mp["sreach"],    "reach"),
        ("Non-social reach",      mc["nreach"],    mp["nreach"],    "reach"),
        ("Total reach",           mc["reach"],     mp["reach"],     "reach"),
        ("Estimated AVE",         int(mc["ave"]),  int(mp["ave"]),  "money"),
    ]
    cmp_df = pd.DataFrame([
        {
            "Metric": lbl,
            f"{cur_range}": (f"£{fmt_compact(cv)}" if k=="money" else fmt_compact(cv) if k=="reach" else f"{cv:,}"),
            "Change":  fmt_pct_delta(cv, pv),
            f"{prev_range}": (f"£{fmt_compact(pv)}" if k=="money" else fmt_compact(pv) if k=="reach" else f"{pv:,}"),
        }
        for lbl,cv,pv,k in rows
    ])
    st.dataframe(cmp_df, use_container_width=True, hide_index=True,
        column_config={"Metric": st.column_config.TextColumn(width="medium")})

    st.markdown("<br>", unsafe_allow_html=True)
    cc1, cc2 = st.columns(2)
    with cc1:
        st.subheader("Mentions trend")
        fig = go.Figure()
        if dC["date"].notna().any():
            cd = dC.groupby(dC["date"].dt.date).size().reset_index(name="n")
            fig.add_trace(go.Scatter(x=cd["date"], y=cd["n"], name="Current",
                line=dict(color=ACCENT, width=3), fill="tozeroy", fillcolor="rgba(79,70,229,0.08)"))
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
                line=dict(color=TEAL, width=3), fill="tozeroy", fillcolor="rgba(8,145,178,0.08)"))
        if dP["date"].notna().any():
            pd_ = dP.groupby(dP["date"].dt.date)["reach_calc"].sum().reset_index()
            fig.add_trace(go.Scatter(x=pd_["date"], y=pd_["reach_calc"], name="Previous",
                line=dict(color=MUTED, width=2, dash="dash")))
        fig.update_yaxes(tickformat=".2s")
        st.plotly_chart(style_chart(fig, 280), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 6 — TOPIC ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════
_TOPICS = [
    ("BAFTA Win",                    ["bafta","leading actress","award","winner","wins"]),
    ("Prisoner 951",                 ["prisoner 951","prisoner951"]),
    ("Nazanin Zaghari-Ratcliffe",    ["nazanin","zaghari","ratcliffe"]),
    ("Iranian Actress",              ["iranian actress","iran","persian"]),
    ("Save the Children",            ["save the children","savechildren","charity"]),
    ("BAFTA TV Awards 2026",         ["bafta tv","bafta television","bafta 2026"]),
    ("Film & TV Reviews",            ["review","drama","series","episode"]),
    ("Interviews & Profiles",        ["interview","speaks","talks to","q&a","in conversation","profile"]),
]

with tab_topics:
    st.subheader("Topic clustering")

    text_col = (df["title"].fillna("") + " " + df["snippet"].fillna("")).str.lower() if not df.empty else pd.Series([])
    topics = []
    for name, kws in _TOPICS:
        if df.empty: continue
        mask = text_col.apply(lambda t: any(k in t for k in kws))
        sub = df[mask]
        if sub.empty: continue
        topics.append({
            "name": name, "mentions": len(sub),
            "reach": int(sub["reach_calc"].sum()),
            "pos": int((sub["sentiment"]=="positive").sum()),
            "neg": int((sub["sentiment"]=="negative").sum()),
            "kws": kws,
        })
    if not topics:
        st.info("Not enough data for topic analysis.")
    else:
        total_m = sum(t["mentions"] for t in topics)
        for t in topics: t["sov"] = t["mentions"]/total_m*100
        topics_df = pd.DataFrame(topics).sort_values("mentions", ascending=False)

        ta1, ta2 = st.columns([3, 2])
        with ta1:
            st.markdown("##### Mentions by topic")
            sd = topics_df.sort_values("mentions")
            fig = go.Figure(go.Bar(y=sd["name"], x=sd["mentions"], orientation="h",
                marker_color=ACCENT, opacity=0.9, text=sd["mentions"], textposition="outside"))
            st.plotly_chart(style_chart(fig, 360), use_container_width=True)
        with ta2:
            st.markdown("##### Share of voice")
            fig = go.Figure(go.Pie(labels=topics_df["name"], values=topics_df["sov"], hole=0.5,
                marker=dict(colors=CHART_PALETTE), textinfo="percent", textfont=dict(size=10)))
            fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=360, paper_bgcolor="white",
                showlegend=True, legend=dict(orientation="v", x=1.0, y=0.5, font=dict(size=10, color=SLATE)))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Topic details")
        td_disp = topics_df.copy()
        td_disp["Reach"]    = td_disp["reach"].apply(fmt_compact)
        td_disp["Positive"] = td_disp["pos"]
        td_disp["Negative"] = td_disp["neg"]
        td_disp = td_disp[["name","mentions","Reach","sov","Positive","Negative"]]
        td_disp.columns = ["Topic","Mentions","Reach","Share of voice","Positive","Negative"]
        st.dataframe(td_disp, use_container_width=True, hide_index=True,
            column_config={
                "Topic": st.column_config.TextColumn(width="large"),
                "Share of voice": st.column_config.ProgressColumn(
                    "Share of voice", min_value=0, max_value=100, format="%.1f%%"),
            })

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Drill into a topic")
        drill = st.selectbox("Topic", topics_df["name"].tolist(), key="topic_drill", label_visibility="collapsed")
        drill_kws = next(t["kws"] for t in topics if t["name"]==drill)
        drill_mask = text_col.apply(lambda t: any(k in t for k in drill_kws))
        drill_df = df[drill_mask][["date","title","source","platform","tier","sentiment","url"]].copy()
        drill_df["date"] = drill_df["date"].dt.strftime("%Y-%m-%d")
        drill_df = drill_df.rename(columns={
            "date":"Date","title":"Title","source":"Source","platform":"Platform",
            "tier":"Tier","sentiment":"Sentiment","url":"Link",
        })
        st.caption(f"**{len(drill_df)}** mentions for *{drill}*")
        st.dataframe(drill_df, use_container_width=True, height=400, hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn(display_text="Open ↗"),
                "Title": st.column_config.TextColumn(width="large"),
            })


# ════════════════════════════════════════════════════════════════════════════════
# TAB 7 — INSTAGRAM
# ════════════════════════════════════════════════════════════════════════════════
with tab_ig:
    st.subheader("Instagram coverage")
    st.caption("Her posts · Posts that tag her · Hashtag mentions")

    if ig_all.empty:
        st.info("No Instagram data yet. Run `python3 run.py` to fetch.")
    else:
        ig_p1, ig_p2 = st.columns(2)
        ig_days = PERIODS[ig_p1.selectbox("Period", [k for k in PERIODS if PERIODS[k]>0], index=2, key="ig_per")]
        SRC_LABELS = {"all":"All sources","own_post":"Her posts","tagged":"Tags her","hashtag":"Hashtag posts"}
        ig_src = ig_p2.selectbox("Source", ["all","own_post","tagged","hashtag"],
            format_func=SRC_LABELS.get, key="ig_src")

        ig_cut = pd.Timestamp.now() - pd.Timedelta(days=ig_days) if ig_days < 9999 else pd.Timestamp("2000-01-01")
        ig_df = ig_all[ig_all["date"] >= ig_cut].copy() if ig_days < 9999 else ig_all.copy()
        if ig_src != "all" and "source_type" in ig_df.columns:
            ig_df = ig_df[ig_df["source_type"]==ig_src]

        if ig_df.empty:
            st.info("No posts in this period.")
        else:
            has_src = "source_type" in ig_df.columns
            tagged_n = int((ig_df["source_type"]=="tagged").sum())   if has_src else 0
            htag_n   = int((ig_df["source_type"]=="hashtag").sum())  if has_src else 0
            own_n    = int((ig_df["source_type"]=="own_post").sum()) if has_src else len(ig_df)

            m1,m2,m3,m4,m5 = st.columns(5)
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
                        likes=("likes","sum"), comments=("comments","sum")).reset_index()
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=by_day["date"], y=by_day["likes"], name="Likes",
                        marker_color=PINK, opacity=0.85))
                    fig.add_trace(go.Bar(x=by_day["date"], y=by_day["comments"], name="Comments",
                        marker_color=AMBER, opacity=0.85))
                    fig.update_layout(barmode="group")
                    st.plotly_chart(style_chart(fig, 300), use_container_width=True)
            with ig_c2:
                if has_src:
                    st.markdown("##### Source breakdown")
                    src_map = {"own_post":"Her posts","tagged":"Tags her","hashtag":"Hashtag"}
                    src_counts = ig_df["source_type"].map(src_map).value_counts().reset_index()
                    src_counts.columns = ["source","count"]
                    fig = go.Figure(go.Pie(labels=src_counts["source"], values=src_counts["count"],
                        hole=0.5, marker=dict(colors=[PINK, ACCENT, TEAL]),
                        textinfo="label+percent", textfont=dict(size=12)))
                    fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=0,b=0),
                        height=300, paper_bgcolor="white")
                    st.plotly_chart(fig, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"##### Top {min(len(ig_df),24)} posts — by engagement")
            top_posts = ig_df.sort_values("likes", ascending=False).head(24)
            cols = st.columns(3)
            src_map = {"own_post":"Her posts","tagged":"Tags her","hashtag":"Hashtag"}
            for i, (_, post) in enumerate(top_posts.iterrows()):
                with cols[i % 3]:
                    cap = (post.get("caption") or "")[:200]
                    src_type = post.get("source_type","own_post") if has_src else "own_post"
                    src_lbl = src_map.get(src_type, src_type)
                    src_color = {"own_post":PINK,"tagged":ACCENT,"hashtag":TEAL}.get(src_type, MUTED)
                    username = post.get("username","")
                    htag = post.get("hashtag","")
                    handle = (f"#{htag}" if (src_type=="hashtag" and htag) else
                              (f"@{username}" if username else ""))
                    url = post.get("url","") or ""
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


# ════════════════════════════════════════════════════════════════════════════════
# TAB 8 — ASK AI (chatbot with full data context)
# ════════════════════════════════════════════════════════════════════════════════
with tab_ai:
    st.subheader("Ask AI about the data")
    st.caption("Get insights, summaries, action items, and answers from Claude — using only the items currently visible on the dashboard (after filters).")

    # Build the data context once per filter combination
    def _build_ai_context(df_in: pd.DataFrame, ig_in: pd.DataFrame) -> str:
        if df_in.empty:
            return "No press items match the current filters."
        # Compact each item to a few key fields, cap at 80 most-impactful
        sample = df_in.sort_values("reach_calc", ascending=False).head(80)
        lines = []
        for _, r in sample.iterrows():
            date_s = r["date"].strftime("%Y-%m-%d") if pd.notna(r.get("date")) else "?"
            lines.append(
                f"- [{date_s}] [{r.get('platform','')}/{r.get('tier','')}/{r.get('sentiment','neutral')}] "
                f"{(r.get('source') or '?')}: {(r.get('title') or '')[:140]}"
            )
        press_block = "\n".join(lines)

        # Top sources summary
        src_top = (df_in.groupby("source")
                   .size().reset_index(name="n")
                   .sort_values("n", ascending=False).head(10))
        srcs_block = "\n".join(f"- {r['source']}: {r['n']} mentions" for _, r in src_top.iterrows())

        # Aggregates
        total = len(df_in)
        pos = (df_in["sentiment"]=="positive").sum()
        neg = (df_in["sentiment"]=="negative").sum()
        t1 = (df_in["tier"]=="Tier 1").sum()
        reach = int(df_in["reach_calc"].sum())

        ig_block = ""
        if not ig_in.empty:
            top_ig = ig_in.sort_values("likes", ascending=False).head(15)
            ig_lines = []
            for _, p in top_ig.iterrows():
                date_s = p["date"].strftime("%Y-%m-%d") if pd.notna(p.get("date")) else "?"
                src_t = p.get("source_type","own_post")
                user = p.get("username","")
                cap = (p.get("caption") or "")[:100].replace("\n", " ")
                ig_lines.append(f"- [{date_s}] [{src_t}] @{user} ({p.get('likes',0)} likes): {cap}")
            ig_block = "\n\nINSTAGRAM (top posts by likes):\n" + "\n".join(ig_lines)

        return f"""SUMMARY:
- {total} press mentions in view
- {pos} positive, {neg} negative
- {t1} Tier 1 hits
- Estimated total reach: {reach:,}

TOP SOURCES:
{srcs_block}

PRESS ITEMS (sorted by reach, most-impactful first):
{press_block}{ig_block}
"""

    ctx_text = _build_ai_context(df, ig_all)

    # Suggested prompts
    st.markdown("**Quick prompts:**")
    qp_cols = st.columns(4)
    suggested = [
        ("📈 Weekly summary",     "Give me a concise 5-bullet summary of what happened with Narges Rashidi's press this week. Highlight the biggest wins, any concerning items, and tone shifts."),
        ("🎯 What's working",     "Which angles, outlets, and messages are getting the most traction? What story patterns are landing well? Be specific with sources."),
        ("⚠️ Risks & gaps",       "Are there any concerning patterns, missing coverage, or gaps in tier/platform mix? Anything that needs attention? Anything negative worth noting?"),
        ("💡 Next actions",       "Based on this data, what 3 concrete PR actions should we take next week? Be tactical. Suggest specific outlets, angles, and timing."),
    ]
    if "ai_chat" not in st.session_state:
        st.session_state["ai_chat"] = []  # list of (role, content)
    if "ai_prefill" not in st.session_state:
        st.session_state["ai_prefill"] = ""

    for (label, prompt), col in zip(suggested, qp_cols):
        if col.button(label, use_container_width=True, key=f"qp_{label}"):
            st.session_state["ai_prefill"] = prompt

    # Render conversation so far
    for role, content in st.session_state["ai_chat"]:
        with st.chat_message(role):
            st.markdown(content)

    # Chat input
    user_q = st.chat_input("Ask anything about the press data…")
    if not user_q and st.session_state["ai_prefill"]:
        user_q = st.session_state["ai_prefill"]
        st.session_state["ai_prefill"] = ""

    if user_q:
        st.session_state["ai_chat"].append(("user", user_q))
        with st.chat_message("user"):
            st.markdown(user_q)

        # Build messages for Claude (carrying short conversational memory)
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        try:
            api_key = api_key or st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass

        if not api_key:
            with st.chat_message("assistant"):
                st.warning("AI not configured. The dashboard owner needs to add `ANTHROPIC_API_KEY` to Streamlit Cloud Secrets.")
            st.session_state["ai_chat"].append(("assistant", "AI not configured."))
        else:
            system_prompt = (
                "You are a senior PR strategist analysing press coverage for Iranian-British "
                "actress Narges Rashidi (2026 BAFTA Leading Actress winner for *Prisoner 951*). "
                "Below is a structured snapshot of the current press monitoring view. "
                "Always ground answers in the data — cite specific sources, dates, and counts. "
                "Be concise and actionable. Use bullet points when listing. "
                "If asked something the data can't answer, say so briefly.\n\n"
                f"=== CURRENT PRESS DATA SNAPSHOT ===\n{ctx_text}"
            )

            # Include short conversation history for follow-up questions
            messages = []
            for role, content in st.session_state["ai_chat"][-8:]:
                messages.append({"role": role, "content": content})

            try:
                from anthropic import Anthropic
                client = Anthropic(api_key=api_key)
                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    full = ""
                    with client.messages.stream(
                        model="claude-sonnet-4-5",
                        max_tokens=1500,
                        system=system_prompt,
                        messages=messages,
                    ) as stream:
                        for chunk in stream.text_stream:
                            full += chunk
                            placeholder.markdown(full + "▌")
                    placeholder.markdown(full)
                st.session_state["ai_chat"].append(("assistant", full))
            except Exception as e:
                with st.chat_message("assistant"):
                    st.error(f"AI error: {type(e).__name__}: {str(e)[:200]}")
                st.session_state["ai_chat"].append(("assistant", f"Error: {e}"))

    if st.session_state["ai_chat"]:
        if st.button("🗑 Clear conversation", key="clear_ai_chat"):
            st.session_state["ai_chat"] = []
            st.rerun()

    with st.expander("ℹ️ How this works"):
        st.markdown(f"""
        - Claude receives a snapshot of the **{len(df):,} press items currently in view** (after sidebar filters),
          plus the top Instagram posts.
        - Asking a question = one API call. Cost is roughly **less than a cent per question** with Claude Sonnet.
        - The AI can't see anything outside this dashboard. To get answers about specific periods or platforms,
          adjust the sidebar filters first, then ask.
        - Conversation history is kept for follow-up questions ("expand on that", "give me sources" etc.)
          but cleared when you reload the page.
        """)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:48px 0 16px;color:#94a3b8;font-size:12px;">
  If I Only Knew PR &nbsp;·&nbsp; Narges Rashidi Press Monitor &nbsp;·&nbsp; Auto-updates Monday 8am
</div>
""", unsafe_allow_html=True)
