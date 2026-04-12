"""
EarningsSense - AI Earnings Intelligence Platform
==================================================
Institutional-grade earnings call intelligence - open-source.

Run:
    streamlit run app.py

Demo mode (no internet/model required):
    Uses pre-computed sample data from data/samples/

Live mode (requires internet + first-run model download ~440MB):
    Enter any ticker → fetches SEC EDGAR filing → runs FinBERT + linguistic
    analysis in real time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EarningsSense - AI Earnings Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Dark theme tweaks */
    .block-container { padding-top: 1.5rem; }
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    .pill {
        display: inline-block;
        padding: 0.2em 0.7em;
        border-radius: 999px;
        font-size: 0.78em;
        font-weight: 600;
    }
    .pill-green { background: #14532d; color: #4ade80; }
    .pill-red   { background: #450a0a; color: #f87171; }
    .pill-blue  { background: #1e3a5f; color: #60a5fa; }
    h1, h2, h3 { color: #f1f5f9 !important; }
    .stSidebar { background: #0f172a; }
</style>
""", unsafe_allow_html=True)

# ── Paths ─────────────────────────────────────────────────────────────────────

SAMPLES_DIR = Path("data/samples")
INDEX_FILE  = SAMPLES_DIR / "index.json"


# ── Data loading helpers ──────────────────────────────────────────────────────

@st.cache_data
def load_index() -> list[dict]:
    if not INDEX_FILE.exists():
        return []
    with open(INDEX_FILE) as f:
        return json.load(f)

@st.cache_data
def load_sample(filename: str) -> dict | None:
    path = SAMPLES_DIR / filename
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)

@st.cache_data
def load_all_samples() -> list[dict]:
    index = load_index()
    samples = [load_sample(entry["file"]) for entry in index]
    return [s for s in samples if s is not None]


# ── Live analysis helper ──────────────────────────────────────────────────────

def run_live_analysis(ticker: str) -> dict | None:
    """
    Fetch SEC EDGAR filing, run FinBERT + linguistic analysis, compute scores.
    Returns a result dict compatible with the sample data schema, or None on error.
    """
    from src.data.edgar  import fetch_filing_text
    from src.data.prices import fetch_price_impact
    from src.analysis.sentiment  import analyze as analyze_sentiment
    from src.analysis.linguistics import extract as extract_linguistics
    from src.analysis.signals    import compute_scores

    with st.spinner(f"Fetching SEC EDGAR 10-Q for {ticker.upper()}..."):
        try:
            filing = fetch_filing_text(ticker)
        except Exception as e:
            st.error(f"EDGAR fetch failed: {e}")
            return None

    with st.spinner("Running FinBERT sentiment analysis (this may take ~30s on CPU)..."):
        sentiment = analyze_sentiment(filing["text"])

    with st.spinner("Extracting linguistic features..."):
        from src.analysis.linguistics import extract as extract_ling
        linguistics = extract_ling(filing["text"])

    scores = compute_scores(sentiment, linguistics)

    price_impact: dict = {}
    if filing.get("report_date"):
        with st.spinner("Fetching price impact data..."):
            try:
                price_impact = fetch_price_impact(ticker, filing["report_date"])
            except Exception:
                price_impact = {}

    return {
        "ticker": filing["ticker"],
        "company": filing["company"],
        "quarter": filing.get("report_date", "Latest 10-Q"),
        "earnings_date": filing.get("report_date", ""),
        "transcript_snippet": filing["text"][:600] + "...",
        "sentiment": {
            "positive":       sentiment.positive,
            "negative":       sentiment.negative,
            "neutral":        sentiment.neutral,
            "sentence_count": sentiment.sentence_count,
            "chunk_count":    sentiment.chunk_count,
        },
        "linguistics": {
            "hedge_density":        linguistics.hedge_density,
            "certainty_ratio":      linguistics.certainty_ratio,
            "passive_voice_ratio":  linguistics.passive_voice_ratio,
            "vague_language_score": linguistics.vague_language_score,
            "word_count":           linguistics.word_count,
        },
        "scores": {
            "management_confidence_index": scores.management_confidence_index,
            "deception_risk_score":        scores.deception_risk_score,
        },
        "price_impact": price_impact,
        "source": filing.get("source", ""),
    }


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.shields.io/badge/EarningsSense-AI%20Earnings%20Intelligence-3b82f6?style=for-the-badge", use_container_width=True)
    st.markdown("---")

    index = load_index()
    has_samples = len(index) > 0

    if has_samples:
        st.markdown("### Select a Company")
        options = {f"{e['ticker']} - {e['quarter']}": e["file"] for e in index}
        selected_label = st.selectbox("Pre-analyzed samples:", list(options.keys()), index=0)
        selected_file  = options[selected_label]
    else:
        selected_file = None

    st.markdown("---")
    st.markdown("### Live Analysis")
    st.caption("Fetches SEC EDGAR filing + runs FinBERT. Requires internet. First run downloads ~440MB model.")
    live_ticker = st.text_input("Ticker symbol:", placeholder="e.g. AAPL, MSFT, NVDA").strip().upper()
    run_live    = st.button("Analyze Live", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("""
    **About EarningsSense**

    Institutional-grade earnings intelligence - free and open-source.
    Made by Elias Wächter.

    Models & methods:
    - [FinBERT](https://arxiv.org/abs/1908.10063) (Araci, 2019)
    - [Loughran-McDonald word lists](https://sraf.nd.edu/loughranmcdonald-master-dictionary/)
    - Hedge language detection (Li, 2010)

    Built with Python · Streamlit · Plotly · HuggingFace Transformers
    """)


# ── Load data ─────────────────────────────────────────────────────────────────

data: dict | None = None

if run_live and live_ticker:
    data = run_live_analysis(live_ticker)
    if data is None and selected_file:
        st.warning("Live analysis failed. Falling back to sample data.")
        data = load_sample(selected_file)
elif selected_file:
    data = load_sample(selected_file)

if data is None:
    # ── Landing page ──────────────────────────────────────────────────────────
    st.markdown("## EarningsSense")
    st.markdown("<div style='color:#94a3b8;margin-bottom:1.5rem;'>FinBERT + Loughran-McDonald NLP on SEC 10-Q filings. Made by Elias Wächter.</div>", unsafe_allow_html=True)

    # Hero stats
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div style='background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem 1.25rem;text-align:center;'><div style='color:#64748b;font-size:.75rem;margin-bottom:.3rem;'>Pearson r — MCI vs return</div><div style='color:#60a5fa;font-size:2.2rem;font-weight:700;'>+0.783</div><div style='color:#475569;font-size:.72rem;'>n=14 (7 companies × 2 quarters)</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem 1.25rem;text-align:center;'><div style='color:#64748b;font-size:.75rem;margin-bottom:.3rem;'>META DRS — Q3 2025</div><div style='color:#ef4444;font-size:2.2rem;font-weight:700;'>34.8</div><div style='color:#475569;font-size:.72rem;'>2x next-highest — stock fell 11.3%</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div style='background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1rem 1.25rem;text-align:center;'><div style='color:#64748b;font-size:.75rem;margin-bottom:.3rem;'>Next batch of filings due</div><div style='color:#22c55e;font-size:2.2rem;font-weight:700;'>May 10</div><div style='color:#475569;font-size:.72rem;'>8 of 10 default tickers — Q1 2026</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Correlation chart
    if Path("assets/mci_vs_returns.png").exists():
        col_chart, col_info2 = st.columns([2, 1])
        with col_chart:
            st.image("assets/mci_vs_returns.png", use_container_width=True)
        with col_info2:
            st.markdown("#### What this shows")
            st.markdown("""
Each dot is one company's MCI score vs next-day stock return after the 10-Q filing.

Higher MCI = more direct, confident management language. The trend line (TSLA excluded as structural outlier) shows the correlation holds across sectors and quarters.

The same META signal appeared twice: DRS 34.8 in Q3 2024 (fell 4.1%) and DRS 34.8 in Q3 2025 (fell 11.3%).
            """)

    st.markdown("---")

    # Q3 2025 results table
    st.markdown("#### Q3 2025 results — computed on live EDGAR filings")
    Q3_DATA = [
        {"Company": "GOOGL", "MCI": 43.6, "DRS": 16.5, "Hedge / 100w": 1.22, "Next-day return": "+2.5%"},
        {"Company": "MSFT",  "MCI": 42.8, "DRS":  2.2, "Hedge / 100w": 0.13, "Next-day return": "-0.7%"},
        {"Company": "AMZN",  "MCI": 41.4, "DRS": 10.1, "Hedge / 100w": 0.21, "Next-day return": "+9.6%"},
        {"Company": "AAPL",  "MCI": 38.9, "DRS":  6.6, "Hedge / 100w": 0.06, "Next-day return": "-0.7%"},
        {"Company": "NVDA",  "MCI": 37.9, "DRS":  9.9, "Hedge / 100w": 0.27, "Next-day return": "-3.1%"},
        {"Company": "TSLA",  "MCI": 36.5, "DRS":  8.7, "Hedge / 100w": 0.49, "Next-day return": "+2.3%"},
        {"Company": "META",  "MCI": 23.0, "DRS": 34.8, "Hedge / 100w": 2.88, "Next-day return": "-11.3%"},
    ]
    import pandas as pd
    df = pd.DataFrame(Q3_DATA)
    st.dataframe(
        df.style.background_gradient(subset=["MCI"], cmap="RdYlGn", vmin=0, vmax=100)
               .background_gradient(subset=["DRS"], cmap="RdYlGn_r", vmin=0, vmax=40)
               .format({"MCI": "{:.1f}", "DRS": "{:.1f}", "Hedge / 100w": "{:.2f}"}),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")

    # Filing countdown
    st.markdown("#### Upcoming 10-Q filings")
    st.markdown("<div style='color:#64748b;font-size:.82rem;margin-bottom:.75rem;'>Large accelerated filers must file within 40 days of quarter end. Quarter ended March 31 for most — filings due by May 10.</div>", unsafe_allow_html=True)

    from src.data.filing_calendar import get_all_upcoming
    DEFAULT_TICKERS_LAND = ["NVDA", "MSFT", "META", "AMZN", "GOOGL", "AAPL", "TSLA", "NFLX", "AMD", "ORCL"]
    upcoming = get_all_upcoming(DEFAULT_TICKERS_LAND)

    fc1, fc2 = st.columns(2)
    cols_cycle = [fc1, fc2]
    for i, r in enumerate(upcoming):
        col = cols_cycle[i % 2]
        status_color = {"IMMINENT": "#ef4444", "THIS MONTH": "#f97316", "UPCOMING": "#60a5fa", "OVERDUE": "#6b7280"}.get(r["status"], "#94a3b8")
        window_note = " - quarter ended, in filing window" if r["in_window"] else ""
        with col:
            st.markdown(
                f"<div style='background:#1e293b;border:1px solid #334155;border-radius:8px;padding:.6rem 1rem;margin-bottom:.4rem;display:flex;justify-content:space-between;align-items:center;'>"
                f"<div><span style='font-weight:700;color:#e2e8f0;'>{r['ticker']}</span>"
                f"<span style='color:#475569;font-size:.75rem;margin-left:.5rem;'>due {r['filing_due'].strftime('%b %d')}{window_note}</span></div>"
                f"<span style='color:{status_color};font-size:.78rem;font-weight:600;'>{r['days_to_due']}d</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Use **Live Analysis** in the sidebar to score any ticker, or **Market Scan** to rank the full default watchlist.")
    st.stop()

# Unpack
ticker   = data["ticker"]
company  = data["company"]
quarter  = data["quarter"]
earn_dt  = data.get("earnings_date", "")
snippet  = data.get("transcript_snippet", "")
sent     = data["sentiment"]
ling     = data["linguistics"]
scores   = data["scores"]
pi       = data.get("price_impact", {})

mci = scores["management_confidence_index"]
drs = scores["deception_risk_score"]

from src.visualization.charts import (
    confidence_gauges,
    sentiment_bar,
    linguistic_radar,
    price_impact_chart,
    backtest_scatter,
)
from src.analysis.signals import backtest as run_backtest

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(
    f"## EarningsSense &nbsp;&nbsp;"
    f"<span style='font-size:1rem; color:#94a3b8; font-weight:400;'>"
    f"AI Earnings Intelligence</span>",
    unsafe_allow_html=True,
)
st.caption("Institutional NLP analysis of earnings calls - free and open-source.")

st.markdown("---")

# Company header row
col_info, col_mci_pill, col_drs_pill = st.columns([3, 1, 1])
with col_info:
    st.markdown(f"### {company}")
    st.markdown(f"**{ticker}** &nbsp;·&nbsp; {quarter} &nbsp;·&nbsp; Earnings: {earn_dt}")
with col_mci_pill:
    mci_color = "green" if mci >= 60 else ("blue" if mci >= 40 else "red")
    st.markdown(
        f"<div style='text-align:center; margin-top:1rem;'>"
        f"<div class='pill pill-blue'>MCI {mci:.0f}/100</div></div>",
        unsafe_allow_html=True,
    )
with col_drs_pill:
    drs_color = "red" if drs >= 50 else ("blue" if drs >= 30 else "green")
    st.markdown(
        f"<div style='text-align:center; margin-top:1rem;'>"
        f"<div class='pill {'pill-red' if drs >= 50 else 'pill-blue'}'>DRS {drs:.0f}/100</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Section 1: Gauges + Sentiment ─────────────────────────────────────────────

col_gauge, col_sent = st.columns([1.2, 1])

with col_gauge:
    st.plotly_chart(
        confidence_gauges(mci, drs),
        use_container_width=True,
        config={"displayModeBar": False},
    )
    st.markdown("""
    <div style='font-size:0.8rem; color:#64748b; padding: 0.5rem 0;'>
    <b>MCI</b> - Management Confidence Index: combines FinBERT positive sentiment,
    certainty language density, inverted hedge frequency, and passive voice avoidance.<br><br>
    <b>DRS</b> - Deception Risk Score: high hedge density + passive voice + negative
    sentiment → elevated institutional scrutiny signal.
    </div>
    """, unsafe_allow_html=True)

with col_sent:
    st.plotly_chart(
        sentiment_bar(sent["positive"], sent["negative"], sent["neutral"], ticker),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    st.markdown("#### Transcript Excerpt")
    st.markdown(
        f"<div style='background:#1e293b; border-left: 3px solid #3b82f6; "
        f"padding:0.8rem 1rem; border-radius:4px; font-size:0.85rem; "
        f"color:#cbd5e1; font-style:italic;'>{snippet[:420]}...</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Section 2: Linguistic features ───────────────────────────────────────────

col_radar, col_metrics = st.columns([1, 1])

with col_radar:
    st.plotly_chart(
        linguistic_radar(
            ling["hedge_density"],
            ling["certainty_ratio"],
            ling["passive_voice_ratio"],
            ling["vague_language_score"],
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )

with col_metrics:
    st.markdown("#### Linguistic Feature Breakdown")
    st.markdown(
        "<div style='font-size:0.8rem; color:#64748b; margin-bottom:0.75rem;'>"
        "Based on Loughran-McDonald financial word lists + passive voice detection.</div>",
        unsafe_allow_html=True,
    )

    metrics = [
        ("Hedge Density",         ling["hedge_density"],        "hedging phrases per 100 words",     5.0,  False),
        ("Certainty Ratio",       ling["certainty_ratio"],       "affirmatives ÷ hedges",             5.0,  True),
        ("Passive Voice Ratio",   ling["passive_voice_ratio"],   "fraction of passive sentences",     0.5,  False),
        ("Vague Language Score",  ling["vague_language_score"],  "vague terms per 100 words",         3.0,  False),
    ]

    for label, value, unit, cap, higher_is_better in metrics:
        pct = min(value / cap, 1.0)
        bar_color = "#22c55e" if (pct > 0.5) == higher_is_better else "#ef4444"
        bar_color = "#94a3b8" if 0.3 < pct < 0.7 else bar_color
        st.markdown(f"""
        <div class='metric-card'>
            <div style='display:flex; justify-content:space-between; margin-bottom:0.3rem;'>
                <span style='font-weight:600; color:#e2e8f0;'>{label}</span>
                <span style='color:#94a3b8; font-size:0.9rem;'>{value:.3f} <span style='font-size:0.75rem;'>({unit})</span></span>
            </div>
            <div style='background:#0f172a; border-radius:4px; height:6px;'>
                <div style='background:{bar_color}; width:{pct*100:.0f}%; height:6px; border-radius:4px;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(
        f"<div style='font-size:0.8rem; color:#64748b; margin-top:0.5rem;'>"
        f"Analyzed {ling['word_count']:,} words · "
        f"{sent['sentence_count']} sentences · "
        f"{sent['chunk_count']} FinBERT inference chunks</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Section 3: Price impact ───────────────────────────────────────────────────

price_series = pi.get("price_series", [])

if price_series and earn_dt:
    col_price, col_returns = st.columns([2.5, 1])

    with col_price:
        st.plotly_chart(
            price_impact_chart(price_series, earn_dt, ticker, mci),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with col_returns:
        st.markdown("#### Post-Earnings Returns")
        st.markdown(
            "<div style='font-size:0.8rem; color:#64748b; margin-bottom:0.75rem;'>"
            "From earnings close.</div>",
            unsafe_allow_html=True,
        )

        for label, key in [
            ("Next Day",  "next_day_return"),
            ("5-Day",     "five_day_return"),
            ("30-Day",    "thirty_day_return"),
        ]:
            val = pi.get(key)
            if val is not None:
                sign  = "+" if val >= 0 else ""
                color = "#22c55e" if val >= 0 else "#ef4444"
                st.markdown(
                    f"<div class='metric-card'>"
                    f"<div style='color:#94a3b8; font-size:0.8rem;'>{label}</div>"
                    f"<div style='font-size:1.6rem; font-weight:700; color:{color};'>"
                    f"{sign}{val*100:.1f}%</div></div>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

# ── Section 4: Backtest ───────────────────────────────────────────────────────

st.markdown("## Signal Backtest")
st.markdown(
    "<div style='font-size:0.85rem; color:#64748b; margin-bottom:1rem;'>"
    "Does the Management Confidence Index predict next-day stock returns? "
    "Below is the empirical validation across all 8 pre-analyzed earnings events.</div>",
    unsafe_allow_html=True,
)

all_samples = load_all_samples()
bt = run_backtest(all_samples)

col_bt_chart, col_bt_stats = st.columns([2.5, 1])

with col_bt_chart:
    st.plotly_chart(
        backtest_scatter(all_samples, bt.pearson_r, bt.p_value),
        use_container_width=True,
        config={"displayModeBar": False},
    )

with col_bt_stats:
    st.markdown("#### Backtest Statistics")

    r_color = "#22c55e" if bt.pearson_r > 0.4 else ("#f97316" if bt.pearson_r > 0.2 else "#ef4444")
    p_color = "#22c55e" if bt.p_value < 0.05 else "#f97316"

    st.markdown(f"""
    <div class='metric-card'>
        <div style='color:#94a3b8; font-size:0.8rem;'>Pearson r</div>
        <div style='font-size:2rem; font-weight:700; color:{r_color};'>{bt.pearson_r:+.3f}</div>
    </div>
    <div class='metric-card'>
        <div style='color:#94a3b8; font-size:0.8rem;'>p-value</div>
        <div style='font-size:2rem; font-weight:700; color:{p_color};'>{bt.p_value:.4f}</div>
    </div>
    <div class='metric-card'>
        <div style='color:#94a3b8; font-size:0.8rem;'>Observations</div>
        <div style='font-size:2rem; font-weight:700; color:#e2e8f0;'>{bt.n_observations}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f"<div style='font-size:0.78rem; color:#64748b; margin-top:0.5rem;'>"
        f"{bt.interpretation}</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Footer ─────────────────────────────────────────────────────────────────────

st.markdown("""
<div style='text-align:center; color:#334155; font-size:0.8rem; padding:1rem 0;'>
EarningsSense · Made by Elias Wächter ·
Built with FinBERT, SEC EDGAR, Yahoo Finance, Streamlit, Plotly
<br>
Academic references: Araci (2019) · Loughran & McDonald (2011) · Li (2010) · Rogers et al. (2011)
</div>
""", unsafe_allow_html=True)
