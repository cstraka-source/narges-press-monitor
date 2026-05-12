"""
Interactive press monitoring dashboard — Brand24-style.
Reads live from press_narges.db (SQLite).

Run: streamlit run dashboard.py
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "press_narges.db"

st.set_page_config(
    page_title="Narges Rashidi · Press Monitor",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="metric-container"] {
        background:#f8f9fa;border-radius:12px;padding:16px;border:1px solid #e9ecef;
    }
    .mention-card {
        background:white;border:1px solid #dee2e6;border-radius:10px;
        padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.06);
    }
    .badge {display:inline-block;padding:2px 8px;border-radius:20px;font-size:.75rem;font-weight:600;}
    .badge-t1{background:#dbeafe;color:#1d4ed8;}
    .badge-t2{background:#dcfce7;color:#166534;}
    .badge-t3{background:#f3f4f6;color:#374151;}
    .badge-pos{background:#d1fae5;color:#065f46;}
    .badge-neg{background:#fee2e2;color:#991b1b;}
    .badge-neu{background:#f3f4f6;color:#374151;}
    .comp-row {padding:10px 0;border-bottom:1px solid #f0f0f0;}
    .up   {color:#16a34a;font-weight:600;}
    .down {color:#dc2626;font-weight:600;}
    .flat {color:#6b7280;}
    .topic-card {
        background:white;border:1px solid #e5e7eb;border-radius:12px;
        padding:20px;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,.05);
    }
</style>
""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    data_dir = Path(__file__).parent / "data"
    parquet_path = data_dir / "press.parquet"
    ig_parquet = data_dir / "instagram.parquet"

    # Prefer Parquet (cloud-friendly); fall back to live SQLite when running locally
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        ig = pd.read_parquet(ig_parquet) if ig_parquet.exists() else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM press ORDER BY date DESC, created_at DESC", conn)
        try:
            ig = pd.read_sql_query("SELECT * FROM instagram_posts ORDER BY date DESC", conn)
        except Exception:
            ig = pd.DataFrame()
        conn.close()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if not ig.empty:
        ig["date"] = pd.to_datetime(ig["date"], errors="coerce")
    return df, ig


def _safe_int(v) -> int:
    try:
        return 0 if (v is None or (isinstance(v, float) and pd.isna(v))) else int(v)
    except Exception:
        return 0


def reach_est(row) -> int:
    tier, platform = str(row.get("tier") or "Tier 3"), str(row.get("platform") or "")
    v = _safe_int(row.get("views"))
    if platform == "YouTube":
        return v
    if platform in ("TikTok", "Facebook"):
        return v * 3
    if tier == "Tier 1":
        return 850_000
    if tier == "Tier 2":
        return 120_000
    return 15_000


def ave_est(row) -> float:
    tier, platform = str(row.get("tier") or "Tier 3"), str(row.get("platform") or "")
    v = _safe_int(row.get("views"))
    if platform == "YouTube":
        return v * 0.003
    if platform in ("TikTok", "Facebook"):
        return v * 0.002
    if tier == "Tier 1":
        return 2500.0
    if tier == "Tier 2":
        return 350.0
    return 75.0


def _pct_change(new, old) -> str:
    if old == 0:
        return '<span class="up">▲ NEW</span>' if new > 0 else '<span class="flat">—</span>'
    pct = (new - old) / old * 100
    cls = "up" if pct >= 0 else "down"
    arrow = "▲" if pct >= 0 else "▼"
    return f'<span class="{cls}">{arrow} {abs(pct):.0f}%</span>'


def _fmt_reach(r: int) -> str:
    if r >= 1_000_000:
        return f"{r/1_000_000:.1f}M"
    if r >= 1_000:
        return f"{r/1_000:.0f}K"
    return str(r)


# Topic clusters — keyword → topic name mapping
_TOPIC_CLUSTERS = [
    ("BAFTA Win",               ["bafta", "leading actress", "award", "winner", "wins"]),
    ("Prisoner 951",            ["prisoner 951", "prisoner951"]),
    ("Nazanin Zaghari-Ratcliffe",["nazanin", "zaghari", "ratcliffe"]),
    ("Iranian Actress",         ["iranian actress", "iran", "persian"]),
    ("Save the Children",       ["save the children", "savechildren", "charity"]),
    ("BAFTA TV Awards 2026",    ["bafta tv", "bafta television", "bafta 2026"]),
    ("Film & TV Reviews",       ["review", "drama", "series", "episode"]),
    ("Interviews",              ["interview", "speaks", "talks to", "q&a", "in conversation"]),
]


def classify_topics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    text_col = (df["title"].fillna("") + " " + df["snippet"].fillna("")).str.lower()
    for topic_name, keywords in _TOPIC_CLUSTERS:
        mask = text_col.apply(lambda t: any(k in t for k in keywords))
        sub = df[mask].copy()
        if sub.empty:
            continue
        sub["reach"] = sub.apply(reach_est, axis=1)
        sub["ave"]   = sub.apply(ave_est, axis=1)
        pos = (sub["sentiment"] == "positive").sum()
        neg = (sub["sentiment"] == "negative").sum()
        rows.append({
            "topic": topic_name,
            "mentions": len(sub),
            "reach": sub["reach"].sum(),
            "ave": sub["ave"].sum(),
            "positive": int(pos),
            "negative": int(neg),
            "sov": 0.0,
        })
    result = pd.DataFrame(rows)
    if not result.empty:
        total = result["mentions"].sum()
        result["sov"] = (result["mentions"] / total * 100).round(2) if total else 0.0
    return result


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 📰 Narges Rashidi")
st.sidebar.markdown("*If I Only Knew PR*")
st.sidebar.divider()

df_all, ig_all = load_data()

if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.caption(f"Database: {len(df_all):,} items total")
st.sidebar.caption(f"Last entry: {df_all['created_at'].max() if not df_all.empty else '—'}")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_compare, tab_topics, tab_instagram = st.tabs([
    "📊 Overview", "📈 Period Comparison", "🏷️ Topic Analysis", "📸 Instagram"
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ════════════════════════════════════════════════════════════════════════════════
with tab_overview:
    st.markdown("### Filters")
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    period_opts = {"Last 7 days":7,"Last 14 days":14,"Last 30 days":30,"Last 60 days":60,"Last 90 days":90,"All time":9999}
    days = period_opts[fc1.selectbox("Period", list(period_opts.keys()), key="ov_period")]
    cutoff_naive = (pd.Timestamp.now() - pd.Timedelta(days=days)) if days < 9999 else pd.Timestamp("2000-01-01")
    df = df_all[df_all["date"] >= cutoff_naive].copy() if days < 9999 else df_all.copy()

    platforms = ["All"] + sorted(df["platform"].dropna().unique().tolist())
    sel_p = fc2.selectbox("Platform", platforms, key="ov_plat")
    if sel_p != "All":
        df = df[df["platform"] == sel_p]

    sel_tier = fc3.selectbox("Tier", ["All","Tier 1","Tier 2","Tier 3"], key="ov_tier")
    if sel_tier != "All":
        df = df[df["tier"] == sel_tier]

    sel_type = fc4.selectbox("Type", ["All"] + sorted(df["type"].dropna().unique().tolist()), key="ov_type")
    if sel_type != "All":
        df = df[df["type"] == sel_type]

    search = fc5.text_input("Search", placeholder="keyword…", key="ov_search")
    if search:
        mask = (df["title"].str.contains(search, case=False, na=False) |
                df["snippet"].str.contains(search, case=False, na=False) |
                df["source"].str.contains(search, case=False, na=False))
        df = df[mask]

    df["reach"] = df.apply(reach_est, axis=1)
    df["ave"]   = df.apply(ave_est, axis=1)
    pos_n = int((df["sentiment"] == "positive").sum())
    neg_n = int((df["sentiment"] == "negative").sum())
    t1_n  = int((df["tier"] == "Tier 1").sum())

    st.divider()
    m1,m2,m3,m4,m5,m6 = st.columns(6)
    m1.metric("Total mentions", f"{len(df):,}")
    m2.metric("Positive ✅", f"{pos_n}")
    m3.metric("Negative ❌", f"{neg_n}")
    m4.metric("Tier 1 hits", f"{t1_n:,}")
    m5.metric("Est. reach", _fmt_reach(int(df["reach"].sum())))
    m6.metric("Est. AVE", f"£{df['ave'].sum():,.0f}")

    st.divider()
    cl, cm, cr = st.columns([3,2,2])

    with cl:
        st.subheader("Mentions over time")
        if df["date"].notna().any():
            daily = df.groupby(df["date"].dt.date).size().reset_index(name="Mentions")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=daily["date"], y=daily["Mentions"], name="Mentions",
                line=dict(color="#2563eb",width=2.5), fill="tozeroy",
                fillcolor="rgba(37,99,235,.08)"))
            pos_d = df[df["sentiment"]=="positive"].groupby(df["date"].dt.date).size().reset_index(name="n")
            neg_d = df[df["sentiment"]=="negative"].groupby(df["date"].dt.date).size().reset_index(name="n")
            if not pos_d.empty:
                fig.add_trace(go.Scatter(x=pos_d["date"],y=pos_d["n"],name="Positive",
                    line=dict(color="#16a34a",width=1.5,dash="dot")))
            if not neg_d.empty:
                fig.add_trace(go.Scatter(x=neg_d["date"],y=neg_d["n"],name="Negative",
                    line=dict(color="#dc2626",width=1.5,dash="dot")))
            fig.update_layout(height=260,margin=dict(l=0,r=0,t=10,b=0),
                legend=dict(orientation="h",y=1.12),
                plot_bgcolor="white",paper_bgcolor="white")
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor="#f5f5f5")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Reach over time")
        if df["date"].notna().any():
            reach_d = df.groupby(df["date"].dt.date)["reach"].sum().reset_index()
            fig_r = go.Figure(go.Scatter(x=reach_d["date"],y=reach_d["reach"],
                fill="tozeroy", line=dict(color="#7c3aed",width=2.5),
                fillcolor="rgba(124,58,237,.08)"))
            fig_r.update_layout(height=220,margin=dict(l=0,r=0,t=10,b=0),
                plot_bgcolor="white",paper_bgcolor="white")
            fig_r.update_xaxes(showgrid=False)
            fig_r.update_yaxes(gridcolor="#f5f5f5", tickformat=".2s")
            st.plotly_chart(fig_r, use_container_width=True)

    with cm:
        st.subheader("Platform split")
        if not df.empty:
            plat = df.groupby("platform").size().reset_index(name="count").sort_values("count",ascending=False)
            fig2 = px.pie(plat,values="count",names="platform",hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_traces(textposition="inside",textinfo="percent+label")
            fig2.update_layout(height=260,margin=dict(l=0,r=0,t=10,b=0),
                showlegend=False,paper_bgcolor="white")
            st.plotly_chart(fig2,use_container_width=True)

        st.subheader("Sentiment")
        if df["sentiment"].notna().any():
            sd = df[df["sentiment"].notna()].groupby("sentiment").size().reset_index(name="n")
            cmap = {"positive":"#16a34a","neutral":"#9ca3af","negative":"#dc2626"}
            fig3 = px.pie(sd,values="n",names="sentiment",hole=0.45,
                color="sentiment",color_discrete_map=cmap)
            fig3.update_traces(textposition="inside",textinfo="percent+label")
            fig3.update_layout(height=220,margin=dict(l=0,r=0,t=10,b=0),
                showlegend=True,paper_bgcolor="white")
            st.plotly_chart(fig3,use_container_width=True)

    with cr:
        st.subheader("Tier breakdown")
        if not df.empty:
            td = df.groupby("tier").size().reset_index(name="n")
            tcolors = {"Tier 1":"#2563eb","Tier 2":"#16a34a","Tier 3":"#9ca3af"}
            td["color"] = td["tier"].map(tcolors)
            fig4 = go.Figure(go.Bar(x=td["tier"],y=td["n"],
                marker_color=td["color"].tolist(),
                text=td["n"],textposition="outside"))
            fig4.update_layout(height=260,margin=dict(l=0,r=0,t=10,b=0),
                plot_bgcolor="white",paper_bgcolor="white")
            fig4.update_yaxes(gridcolor="#f5f5f5")
            st.plotly_chart(fig4,use_container_width=True)

        st.subheader("Type breakdown")
        if not df.empty:
            typ = df.groupby("type").size().reset_index(name="n").sort_values("n",ascending=True)
            fig5 = go.Figure(go.Bar(y=typ["type"],x=typ["n"],orientation="h",
                marker_color="#2563eb",text=typ["n"],textposition="outside"))
            fig5.update_layout(height=220,margin=dict(l=0,r=0,t=10,b=0),
                plot_bgcolor="white",paper_bgcolor="white")
            fig5.update_xaxes(gridcolor="#f5f5f5")
            st.plotly_chart(fig5,use_container_width=True)

    st.divider()
    sa, sb = st.columns(2)

    with sa:
        st.subheader("Most active sources")
        if not df.empty:
            src = df.groupby("source").size().reset_index(name="n").sort_values("n",ascending=False).head(12)
            fig6 = go.Figure(go.Bar(y=src["source"],x=src["n"],orientation="h",
                marker_color="#2563eb",text=src["n"],textposition="outside"))
            fig6.update_layout(height=380,margin=dict(l=0,r=0,t=10,b=0),
                plot_bgcolor="white",paper_bgcolor="white")
            fig6.update_xaxes(gridcolor="#f5f5f5")
            st.plotly_chart(fig6,use_container_width=True)

    with sb:
        st.subheader("Most impactful coverage")
        impact = df.sort_values("reach",ascending=False).head(8)
        for _, row in impact.iterrows():
            tb = f"<span class='badge badge-t{str(row.get('tier','Tier 3'))[-1]}'>{row.get('tier','')}</span>"
            sent = row.get("sentiment") or "neutral"
            sb2 = f"<span class='badge badge-{sent}'>{sent}</span>"
            url = row.get("url","")
            title = row.get("title","") or ""
            source = row.get("source","")
            date_s = row["date"].strftime("%d %b %Y") if pd.notna(row.get("date")) else ""
            snip = (row.get("snippet") or "")[:150]
            link = f'<a href="{url}" target="_blank" style="font-weight:600;color:#1d4ed8;text-decoration:none">{title[:90]}</a>' if url else f"<b>{title[:90]}</b>"
            st.markdown(f"""<div class="mention-card">
              {link}<br>
              <small style="color:#6b7280">{source} · {date_s}</small> {tb} {sb2}<br>
              <small>Reach ~{_fmt_reach(int(row['reach']))}</small>
              <p style="margin:6px 0 0;font-size:.85rem;color:#4b5563">{snip}</p>
            </div>""", unsafe_allow_html=True)

    st.divider()
    st.subheader(f"All mentions ({len(df):,})")
    disp = df[["date","title","source","platform","tier","type","sentiment","views","likes","url"]].copy()
    disp["date"] = disp["date"].dt.strftime("%Y-%m-%d")
    disp = disp.fillna("—")
    st.dataframe(disp, use_container_width=True, height=500, hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("Link", display_text="Open →"),
            "title": st.column_config.TextColumn("Title", width="large"),
            "date": st.column_config.TextColumn("Date", width="small"),
            "tier": st.column_config.TextColumn("Tier", width="small"),
        })


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2: PERIOD COMPARISON
# ════════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.markdown("### Compare two time periods")
    cc1, cc2, cc3 = st.columns([2,2,1])
    with cc1:
        st.markdown("**Current period**")
        cur_days = st.selectbox("", ["Last 7 days","Last 14 days","Last 30 days","Last 60 days"],
            key="cmp_cur", label_visibility="collapsed")
    with cc2:
        st.markdown("**vs.**")
        prev_mode = st.selectbox("", ["Previous period","Previous 30 days","Previous 60 days","Previous 90 days"],
            key="cmp_prev", label_visibility="collapsed")

    cur_n = {"Last 7 days":7,"Last 14 days":14,"Last 30 days":30,"Last 60 days":60}[cur_days]
    now = pd.Timestamp.now()
    cur_start  = now - pd.Timedelta(days=cur_n)
    prev_start = cur_start - pd.Timedelta(days=cur_n)
    prev_end   = cur_start

    df_cur  = df_all[(df_all["date"] >= cur_start)].copy()
    df_prev = df_all[(df_all["date"] >= prev_start) & (df_all["date"] < prev_end)].copy()

    df_cur["reach"]  = df_cur.apply(reach_est, axis=1)
    df_cur["ave"]    = df_cur.apply(ave_est, axis=1)
    df_prev["reach"] = df_prev.apply(reach_est, axis=1)
    df_prev["ave"]   = df_prev.apply(ave_est, axis=1)

    social_platforms = {"TikTok","Facebook","Bluesky","Instagram"}

    def _metrics(d):
        social_mask = d["platform"].isin(social_platforms)
        return {
            "total":       len(d),
            "social":      int(social_mask.sum()),
            "nonsocial":   int((~social_mask).sum()),
            "pos_n":       int((d["sentiment"]=="positive").sum()),
            "neg_n":       int((d["sentiment"]=="negative").sum()),
            "pos_pct":     round((d["sentiment"]=="positive").mean()*100,1) if len(d) else 0,
            "neg_pct":     round((d["sentiment"]=="negative").mean()*100,1) if len(d) else 0,
            "social_reach":    int(d[social_mask]["reach"].sum()),
            "nonsocial_reach": int(d[~social_mask]["reach"].sum()),
            "reach":           int(d["reach"].sum()),
            "ave":             d["ave"].sum(),
            "t1":              int((d["tier"]=="Tier 1").sum()),
        }

    mc = _metrics(df_cur)
    mp = _metrics(df_prev)

    cur_label  = f"{cur_start.strftime('%d %b')} – {now.strftime('%d %b %Y')}"
    prev_label = f"{prev_start.strftime('%d %b')} – {prev_end.strftime('%d %b %Y')}"

    st.divider()
    h1,h2,h3 = st.columns([3,2,2])
    h1.markdown("**Metric**")
    h2.markdown(f"**{cur_label}**")
    h3.markdown(f"**{prev_label}**")
    st.divider()

    rows = [
        ("Total mentions",          mc["total"],         mp["total"],         False),
        ("Social media mentions",   mc["social"],        mp["social"],        False),
        ("Non-social media",        mc["nonsocial"],     mp["nonsocial"],     False),
        ("Positive mentions",       mc["pos_n"],         mp["pos_n"],         False),
        ("Negative mentions",       mc["neg_n"],         mp["neg_n"],         True),
        ("Social media reach",      mc["social_reach"],  mp["social_reach"],  False),
        ("Non-social reach",        mc["nonsocial_reach"],mp["nonsocial_reach"],False),
        ("Est. AVE",                int(mc["ave"]),      int(mp["ave"]),      False),
        ("Tier 1 hits",             mc["t1"],            mp["t1"],            False),
    ]

    for label, cur_v, prev_v, invert in rows:
        r1,r2,r3 = st.columns([3,2,2])
        r1.markdown(f"**{label}**")
        pct_html = _pct_change(cur_v, prev_v)
        if invert and "up" in pct_html:
            pct_html = pct_html.replace("up","down").replace("▲","▼")
        elif invert and "down" in pct_html:
            pct_html = pct_html.replace("down","up").replace("▼","▲")
        display_v = _fmt_reach(cur_v) if "reach" in label.lower() else (f"£{cur_v:,}" if "AVE" in label else f"{cur_v:,}")
        r2.markdown(f"{display_v} &nbsp; {pct_html}", unsafe_allow_html=True)
        display_p = _fmt_reach(prev_v) if "reach" in label.lower() else (f"£{prev_v:,}" if "AVE" in label else f"{prev_v:,}")
        r3.markdown(display_p)

    st.divider()

    # Overlay charts
    ch1, ch2 = st.columns(2)
    with ch1:
        st.subheader("Mentions")
        fig_c1 = go.Figure()
        if df_cur["date"].notna().any():
            cd = df_cur.groupby(df_cur["date"].dt.date).size().reset_index(name="n")
            fig_c1.add_trace(go.Scatter(x=cd["date"],y=cd["n"],name="Current period",
                line=dict(color="#2563eb",width=2.5),fill="tozeroy",fillcolor="rgba(37,99,235,.08)"))
        if df_prev["date"].notna().any():
            pd_ = df_prev.groupby(df_prev["date"].dt.date).size().reset_index(name="n")
            fig_c1.add_trace(go.Scatter(x=pd_["date"],y=pd_["n"],name="Previous period",
                line=dict(color="#93c5fd",width=1.5,dash="dash")))
        fig_c1.update_layout(height=280,margin=dict(l=0,r=0,t=10,b=0),
            plot_bgcolor="white",paper_bgcolor="white",
            legend=dict(orientation="h",y=1.12))
        fig_c1.update_xaxes(showgrid=False)
        fig_c1.update_yaxes(gridcolor="#f5f5f5")
        st.plotly_chart(fig_c1,use_container_width=True)

    with ch2:
        st.subheader("Reach")
        fig_c2 = go.Figure()
        if df_cur["date"].notna().any():
            cr_ = df_cur.groupby(df_cur["date"].dt.date)["reach"].sum().reset_index()
            fig_c2.add_trace(go.Scatter(x=cr_["date"],y=cr_["reach"],name="Current period",
                line=dict(color="#7c3aed",width=2.5),fill="tozeroy",fillcolor="rgba(124,58,237,.08)"))
        if df_prev["date"].notna().any():
            pr_ = df_prev.groupby(df_prev["date"].dt.date)["reach"].sum().reset_index()
            fig_c2.add_trace(go.Scatter(x=pr_["date"],y=pr_["reach"],name="Previous period",
                line=dict(color="#c4b5fd",width=1.5,dash="dash")))
        fig_c2.update_layout(height=280,margin=dict(l=0,r=0,t=10,b=0),
            plot_bgcolor="white",paper_bgcolor="white",
            legend=dict(orientation="h",y=1.12))
        fig_c2.update_xaxes(showgrid=False)
        fig_c2.update_yaxes(gridcolor="#f5f5f5",tickformat=".2s")
        st.plotly_chart(fig_c2,use_container_width=True)

    ch3, ch4 = st.columns(2)
    with ch3:
        st.subheader("Sentiment breakdown")
        sent_data = []
        for period_lbl, d in [(cur_label, df_cur), (prev_label, df_prev)]:
            tot = max(len(d),1)
            sent_data.append({"Period":period_lbl,"Positive":round((d["sentiment"]=="positive").sum()/tot*100,1),
                "Neutral":round((d["sentiment"]=="neutral").sum()/tot*100,1),
                "Negative":round((d["sentiment"]=="negative").sum()/tot*100,1)})
        sdf = pd.DataFrame(sent_data)
        fig_s = go.Figure()
        for col,color in [("Positive","#16a34a"),("Neutral","#9ca3af"),("Negative","#dc2626")]:
            fig_s.add_trace(go.Bar(name=col,x=sdf["Period"],y=sdf[col],marker_color=color))
        fig_s.update_layout(barmode="stack",height=280,margin=dict(l=0,r=0,t=10,b=0),
            plot_bgcolor="white",paper_bgcolor="white",
            yaxis_title="%",legend=dict(orientation="h",y=1.12))
        fig_s.update_yaxes(gridcolor="#f5f5f5")
        st.plotly_chart(fig_s,use_container_width=True)

    with ch4:
        st.subheader("Categories share")
        cat_data = []
        for period_lbl, d in [(cur_label, df_cur), (prev_label, df_prev)]:
            tot = max(len(d),1)
            for plat, grp in d.groupby("platform"):
                cat_data.append({"Period":period_lbl,"Platform":plat,"Pct":round(len(grp)/tot*100,1)})
        if cat_data:
            cdf = pd.DataFrame(cat_data)
            fig_cat = px.bar(cdf,x="Period",y="Pct",color="Platform",barmode="stack",
                color_discrete_sequence=px.colors.qualitative.Set2)
            fig_cat.update_layout(height=280,margin=dict(l=0,r=0,t=10,b=0),
                plot_bgcolor="white",paper_bgcolor="white",
                yaxis_title="%",legend=dict(orientation="h",y=1.12))
            fig_cat.update_yaxes(gridcolor="#f5f5f5")
            st.plotly_chart(fig_cat,use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3: TOPIC ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════
with tab_topics:
    st.markdown("### AI Topic Analysis")
    st.caption("Automatically clusters coverage into key themes. Mentions may appear in multiple topics.")

    tp_col, _ = st.columns([2,3])
    tp_period = tp_col.selectbox("Period", list(period_opts.keys()), key="tp_period")
    tp_days = period_opts[tp_period]
    tp_cutoff = pd.Timestamp.now() - pd.Timedelta(days=tp_days) if tp_days < 9999 else pd.Timestamp("2000-01-01")
    df_tp = df_all[df_all["date"] >= tp_cutoff].copy() if tp_days < 9999 else df_all.copy()

    topics_df = classify_topics(df_tp)

    if topics_df.empty:
        st.info("Not enough data for topic analysis. Run the monitor first.")
    else:
        total_reach_tp = topics_df["reach"].sum()

        # Summary chart
        fig_t = go.Figure()
        fig_t.add_trace(go.Bar(
            name="Mentions", x=topics_df["topic"], y=topics_df["mentions"],
            marker_color="#2563eb", text=topics_df["mentions"], textposition="outside",
        ))
        fig_t.update_layout(height=300, margin=dict(l=0,r=0,t=20,b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            title="Mentions per topic")
        fig_t.update_yaxes(gridcolor="#f5f5f5")
        st.plotly_chart(fig_t, use_container_width=True)

        # SOV chart
        fig_sov = px.pie(topics_df, values="sov", names="topic", hole=0.4,
            title="Share of Voice",
            color_discrete_sequence=px.colors.qualitative.Set3)
        fig_sov.update_traces(textposition="inside", textinfo="percent+label")
        fig_sov.update_layout(height=320, margin=dict(l=0,r=0,t=40,b=0), paper_bgcolor="white")
        st.plotly_chart(fig_sov, use_container_width=True)

        st.divider()
        st.subheader("Topic details")

        # Table header
        h1,h2,h3,h4,h5,h6 = st.columns([3,1,2,2,1,1])
        h1.markdown("**Topic**")
        h2.markdown("**Mentions**")
        h3.markdown("**Reach**")
        h4.markdown("**Share of Voice**")
        h5.markdown("**Positive**")
        h6.markdown("**Negative**")
        st.divider()

        for _, row in topics_df.sort_values("mentions", ascending=False).iterrows():
            c1,c2,c3,c4,c5,c6 = st.columns([3,1,2,2,1,1])
            c1.markdown(f"**{row['topic']}**")
            c2.markdown(str(int(row["mentions"])))
            c3.markdown(_fmt_reach(int(row["reach"])))
            # SOV bar
            sov_pct = float(row["sov"])
            c4.markdown(f"""
                <div style="display:flex;align-items:center;gap:8px">
                  <div style="background:#e5e7eb;border-radius:4px;width:100%;height:8px">
                    <div style="background:#2563eb;width:{min(sov_pct,100):.0f}%;height:100%;border-radius:4px"></div>
                  </div>
                  <span style="white-space:nowrap;font-size:.85rem">{sov_pct:.1f}%</span>
                </div>
            """, unsafe_allow_html=True)
            c5.markdown(f'<span style="color:#16a34a;font-weight:600">{int(row["positive"])}</span>', unsafe_allow_html=True)
            c6.markdown(f'<span style="color:#dc2626;font-weight:600">{int(row["negative"])}</span>', unsafe_allow_html=True)

        st.divider()

        # Drill into a topic
        sel_topic = st.selectbox("Drill into topic →", topics_df["topic"].tolist(), key="drill_topic")
        if sel_topic:
            kws = next((kws for name,kws in _TOPIC_CLUSTERS if name==sel_topic), [])
            text_col = (df_tp["title"].fillna("") + " " + df_tp["snippet"].fillna("")).str.lower()
            topic_items = df_tp[text_col.apply(lambda t: any(k in t for k in kws))].copy()
            topic_items["reach"] = topic_items.apply(reach_est, axis=1)
            st.markdown(f"**{len(topic_items)} mentions** for *{sel_topic}*")
            disp2 = topic_items[["date","title","source","platform","tier","sentiment","url"]].copy()
            disp2["date"] = disp2["date"].dt.strftime("%Y-%m-%d")
            disp2 = disp2.fillna("—")
            st.dataframe(disp2, use_container_width=True, height=400, hide_index=True,
                column_config={
                    "url": st.column_config.LinkColumn("Link", display_text="Open →"),
                    "title": st.column_config.TextColumn("Title", width="large"),
                    "date": st.column_config.TextColumn("Date", width="small"),
                })


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4: INSTAGRAM
# ════════════════════════════════════════════════════════════════════════════════
with tab_instagram:
    st.markdown("### 📸 Instagram @nargesrashidi")
    if ig_all.empty:
        st.info("No Instagram data yet. Run `python3 run.py` to fetch.")
    else:
        ig_period_opts = {"Last 14 days":14,"Last 30 days":30,"Last 90 days":90,"All time":9999}
        ig_days = ig_period_opts[st.selectbox("Period", list(ig_period_opts.keys()), key="ig_period")]
        ig_cutoff = pd.Timestamp.now() - pd.Timedelta(days=ig_days) if ig_days < 9999 else pd.Timestamp("2000-01-01")
        ig_df = ig_all[ig_all["date"] >= ig_cutoff] if ig_days < 9999 else ig_all

        if ig_df.empty:
            st.info("No posts in this period.")
        else:
            # Stats
            im1,im2,im3 = st.columns(3)
            im1.metric("Posts", len(ig_df))
            im2.metric("Total likes", f"{ig_df['likes'].sum():,}")
            im3.metric("Total comments", f"{ig_df['comments'].sum():,}")

            st.divider()

            # Engagement chart
            if ig_df["date"].notna().any():
                fig_ig = go.Figure()
                fig_ig.add_trace(go.Bar(x=ig_df["date"].dt.strftime("%d %b"),
                    y=ig_df["likes"], name="Likes", marker_color="#ec4899"))
                fig_ig.add_trace(go.Bar(x=ig_df["date"].dt.strftime("%d %b"),
                    y=ig_df["comments"], name="Comments", marker_color="#f97316"))
                fig_ig.update_layout(height=250,barmode="group",
                    margin=dict(l=0,r=0,t=10,b=0),
                    plot_bgcolor="white",paper_bgcolor="white",
                    legend=dict(orientation="h",y=1.12))
                fig_ig.update_yaxes(gridcolor="#f5f5f5")
                st.plotly_chart(fig_ig,use_container_width=True)

            st.divider()
            cols = st.columns(3)
            for i, (_, post) in enumerate(ig_df.iterrows()):
                with cols[i % 3]:
                    cap = (post.get("caption") or "")[:220]
                    st.markdown(f"""<div class="mention-card">
                      <b>{post['date']}</b> · <span style="color:#6b7280">{post.get('media_type','')}</span><br>
                      <p style="font-size:.9rem;margin:8px 0;color:#374151">{cap}</p>
                      ❤️ <b>{post.get('likes',0):,}</b> &nbsp;
                      💬 <b>{post.get('comments',0):,}</b><br>
                      <a href="{post.get('url','')}" target="_blank" style="font-size:.85rem">View post →</a>
                    </div>""", unsafe_allow_html=True)

st.divider()
st.caption("If I Only Knew PR · Narges Rashidi Press Monitor · Updates every Monday 8am")
