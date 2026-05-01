"""
EarningsSense - main entry point / home page.

Demo mode:  uses pre-computed sample data from data/samples/
Live mode:  enter any ticker in Live Analysis
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EarningsSense - AI Earnings Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.ui.sidebar import render_sidebar_branding
from src.ui.theme   import C, base_css

render_sidebar_branding()      # injects CSS + theme toggle
st.markdown(base_css(), unsafe_allow_html=True)

# ── Paths ─────────────────────────────────────────────────────────────────────

SAMPLES_DIR = Path("data/samples")
INDEX_FILE  = SAMPLES_DIR / "index.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Sidebar company selector ──────────────────────────────────────────────────

with st.sidebar:
    c = C()
    st.markdown(
        f"<hr style='border:none;border-top:1px solid {c['border']};margin:.5rem 0 .8rem;'>",
        unsafe_allow_html=True,
    )

    index = load_index()
    if index:
        st.markdown(
            f"<div class='es-label'>Sample analyses</div>",
            unsafe_allow_html=True,
        )
        options       = {f"{e['ticker']} - {e['quarter']}": e["file"] for e in index}
        selected_label = st.selectbox("", list(options.keys()), index=0,
                                      label_visibility="collapsed")
        selected_file  = options[selected_label]

        st.markdown(
            f"<div style='color:{c['muted']};font-size:.72rem;margin-top:.3rem;'>"
            f"Pre-computed demos - use Live Analysis for any ticker</div>",
            unsafe_allow_html=True,
        )
    else:
        selected_file = None

    st.markdown(
        f"<hr style='border:none;border-top:1px solid {c['border']};margin:.8rem 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(f"""
    <div style='font-size:.78rem;color:{c['subtext']};line-height:1.7;'>
    <strong style='color:{c['subtext']};'>About EarningsSense</strong><br>
    Institutional-grade earnings intelligence - free and open-source.
    Built by Elias Wächter.<br><br>
    <strong>Models</strong><br>
    <a href='https://arxiv.org/abs/1908.10063' style='color:{c['blue']};'>FinBERT</a>
    (Araci 2019) ·
    <a href='https://sraf.nd.edu/loughranmcdonald-master-dictionary/'
       style='color:{c['blue']};'>Loughran-McDonald</a><br>
    Hedge language (Li 2010)
    </div>
    """, unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────────────────────────────

data: dict | None = None
if selected_file:
    data = load_sample(selected_file)

if data is None:
    # ── Landing page ──────────────────────────────────────────────────────────
    c = C()

    st.markdown("## EarningsSense")
    st.markdown(
        f"<div style='color:{c['subtext']};margin-bottom:1.5rem;font-size:1rem;'>"
        f"FinBERT + Loughran-McDonald NLP on SEC 10-Q filings. "
        f"Built by <strong>Elias Wächter</strong>.</div>",
        unsafe_allow_html=True,
    )

    # ── Historical reference banner ───────────────────────────────────────────
    st.markdown(
        f"<div style='background:{c['surface']};border:1px solid {c['border']};"
        f"border-left:3px solid {c['blue']};border-radius:8px;"
        f"padding:.6rem 1rem;margin-bottom:1.25rem;font-size:.8rem;color:{c['muted']};'>"
        f"<strong style='color:{c['blue']};'>Q3 2025 Historical Reference</strong>"
        f" - Scores below were computed from live EDGAR filings at the time of each report. "
        f"Run <strong>Live Analysis</strong> to score any ticker against its current filing."
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── 3 hero stat cards ─────────────────────────────────────────────────────
    h1, h2, h3 = st.columns(3)
    def _hero(col, label, value, color, note):
        with col:
            st.markdown(
                f"<div class='es-card' style='text-align:center;'>"
                f"<div class='es-label'>{label}</div>"
                f"<div style='color:{color};font-size:2.4rem;font-weight:700;"
                f"letter-spacing:-1px;line-height:1;margin:.25rem 0;'>{value}</div>"
                f"<div style='color:{c['muted']};font-size:.72rem;'>{note}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    _hero(h1, "META DRS  Q3 2025", "34.8", c["red"],
          "2× next-highest · stock fell 11.3% next session")
    _hero(h2, "AMZN MCI  Q3 2025", "41.4", c["green"],
          "hedge density 0.21/100w · stock +9.6% next session")
    _hero(h3, "Q1 2026 filings due", "May 10", c["blue"],
          "most large-cap filers · 40-day window from March 31")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Q3 2025 results table ─────────────────────────────────────────────────
    st.markdown(
        f"<hr class='es-section-rule'>",
        unsafe_allow_html=True,
    )
    st.markdown("#### Q3 2025 - MCI / DRS from live EDGAR filings at report date")
    st.markdown(
        f"<div style='color:{c['muted']};font-size:.78rem;margin-bottom:.75rem;'>"
        f"Next-day return = close-to-close from earnings date to next session. "
        f"These scores will differ from a live run today - management tone changes quarter to quarter."
        f"</div>",
        unsafe_allow_html=True,
    )

    import pandas as pd
    Q3 = [
        {"Company": "GOOGL", "MCI": 43.6, "DRS": 16.5, "Hedge/100w": 1.22, "Next-day": "+2.7%"},
        {"Company": "MSFT",  "MCI": 42.8, "DRS":  2.2, "Hedge/100w": 0.13, "Next-day": "-2.9%"},
        {"Company": "AMZN",  "MCI": 41.4, "DRS": 10.1, "Hedge/100w": 0.21, "Next-day": "+9.6%"},
        {"Company": "AAPL",  "MCI": 38.9, "DRS":  6.6, "Hedge/100w": 0.06, "Next-day": "-0.4%"},
        {"Company": "NVDA",  "MCI": 37.9, "DRS":  9.9, "Hedge/100w": 0.27, "Next-day": "-3.1%"},
        {"Company": "TSLA",  "MCI": 36.5, "DRS":  8.7, "Hedge/100w": 0.49, "Next-day": "+2.3%"},
        {"Company": "META",  "MCI": 23.0, "DRS": 34.8, "Hedge/100w": 2.88, "Next-day": "-11.3%"},
    ]
    st.dataframe(
        pd.DataFrame(Q3).style.format(
            {"MCI": "{:.1f}", "DRS": "{:.1f}", "Hedge/100w": "{:.2f}"}
        ),
        use_container_width=True,
        hide_index=True,
    )

    # ── Filing countdown ──────────────────────────────────────────────────────
    st.markdown(
        f"<hr class='es-section-rule'>",
        unsafe_allow_html=True,
    )
    st.markdown("#### Upcoming 10-Q filing windows")
    st.markdown(
        f"<div style='color:{c['muted']};font-size:.78rem;margin-bottom:.9rem;'>"
        f"Large accelerated filers must file within 40 calendar days of quarter end. "
        f"Progress bar shows % of the 40-day window elapsed."
        f"</div>",
        unsafe_allow_html=True,
    )

    try:
        from src.data.filing_calendar import get_all_upcoming
        from datetime import date as _date
        from pathlib import Path as _Path

        DEFAULT_TICKERS_LAND = [
            "NVDA", "MSFT", "META", "AMZN", "GOOGL",
            "AAPL", "TSLA", "NFLX", "AMD", "ORCL",
        ]
        upcoming = get_all_upcoming(DEFAULT_TICKERS_LAND)
        today    = _date.today()

        fc1, fc2 = st.columns(2)
        cols_cycle = [fc1, fc2]

        STATUS_COLOR = {
            "FILED":      c["green"],
            "IMMINENT":   c["red"],
            "THIS MONTH": c["amber"],
            "UPCOMING":   c["blue"],
            "OVERDUE":    c["muted"],
        }

        for i, r in enumerate(upcoming):
            col = cols_cycle[i % 2]

            # Check if we already have a cached filing for this ticker
            _cache_path = _Path("data/cache") / f"{r['ticker']}_10q.json"
            _already_filed = _cache_path.exists()

            if _already_filed:
                sc          = STATUS_COLOR["FILED"]
                badge_text  = "FILED"
                right_label = "✓ scored"
                progress_bar = ""
            else:
                sc          = STATUS_COLOR.get(r["status"], c["muted"])
                days_gone   = (today - r["quarter_end"]).days if r["in_window"] else 0
                pct_elapsed = max(0, min(100, int(days_gone / 40 * 100))) if r["in_window"] else 0
                bar_color   = c["red"] if pct_elapsed > 75 else (c["amber"] if pct_elapsed > 40 else c["blue"])
                window_text = f"in 40-day window ({pct_elapsed}% elapsed)" if r["in_window"] else ""
                badge_text  = f"due {r['filing_due'].strftime('%b %d')}{' · ' + window_text if window_text else ''}"
                right_label = f"{r['days_to_due']}d"
                progress_bar = (
                    f"<div style='background:{c['border']};border-radius:2px;height:3px;margin-top:.4rem;'>"
                    f"<div style='background:{bar_color};width:{pct_elapsed}%;height:3px;"
                    f"border-radius:2px;'></div></div>"
                    if r["in_window"] else ""
                )

            with col:
                st.markdown(
                    f"<div class='es-card-sm' style='border-left:3px solid {sc};'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                    f"<div>"
                    f"<span style='font-weight:700;color:{c['text']};font-size:.9rem;'>{r['ticker']}</span>"
                    f"<span style='color:{c['muted']};font-size:.72rem;margin-left:.5rem;'>{badge_text}</span>"
                    f"</div>"
                    f"<span style='color:{sc};font-size:.82rem;font-weight:700;'>{right_label}</span>"
                    f"</div>"
                    + progress_bar
                    + "</div>",
                    unsafe_allow_html=True,
                )
    except Exception:
        st.markdown(
            f"<div style='color:{c['muted']};font-size:.8rem;'>"
            f"Filing calendar unavailable - use Live Analysis to check any ticker.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:{c['surface']};border:1px solid {c['border']};"
        f"border-radius:8px;padding:.75rem 1rem;font-size:.85rem;color:{c['subtext']};'>"
        f"Use <strong style='color:{c['blue']};'>Live Analysis</strong> to score any ticker, "
        f"or <strong style='color:{c['blue']};'>Market Scan</strong> to rank your full watchlist."
        f"</div>",
        unsafe_allow_html=True,
    )
    st.stop()


# ── Sample data display ───────────────────────────────────────────────────────

c = C()

ticker  = data["ticker"]
company = data["company"]
quarter = data["quarter"]
earn_dt = data.get("earnings_date", "")
snippet = data.get("transcript_snippet", "")
sent    = data["sentiment"]
ling    = data["linguistics"]
scores  = data["scores"]
pi      = data.get("price_impact", {})

mci = scores["management_confidence_index"]
drs = scores["deception_risk_score"]

from src.visualization.charts import (
    confidence_gauges, sentiment_bar, linguistic_radar, price_impact_chart,
)

# ── Header ────────────────────────────────────────────────────────────────────

hcol1, hcol2 = st.columns([4, 1])
with hcol1:
    st.markdown(f"## {company}")
    st.markdown(
        f"<div style='color:{c['muted']};font-size:.85rem;'>"
        f"{ticker} &nbsp;·&nbsp; {quarter} &nbsp;·&nbsp; {earn_dt}</div>",
        unsafe_allow_html=True,
    )
with hcol2:
    mci_pill = "pill-green" if mci >= 60 else ("pill-blue" if mci >= 40 else "pill-red")
    drs_pill = "pill-red"   if drs >= 50 else ("pill-amber" if drs >= 30 else "pill-green")
    st.markdown(
        f"<div style='text-align:right;margin-top:.75rem;'>"
        f"<span class='pill {mci_pill}'>MCI {mci:.0f}</span>"
        f"&nbsp;"
        f"<span class='pill {drs_pill}'>DRS {drs:.0f}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)

# ── Gauges + sentiment ────────────────────────────────────────────────────────

col_gauge, col_sent = st.columns([1.2, 1])

with col_gauge:
    st.plotly_chart(confidence_gauges(mci, drs), use_container_width=True,
                    config={"displayModeBar": False})
    st.markdown(
        f"<div style='font-size:.78rem;color:{c['muted']};padding:.25rem 0 .5rem;'>"
        f"<strong style='color:{c['subtext']};'>MCI</strong> - FinBERT positive + certainty ratio "
        f"+ inverted hedge density + passive voice avoidance. "
        f"<strong style='color:{c['subtext']};'>DRS</strong> - hedge density + passive voice "
        f"+ negative sentiment combined."
        f"</div>",
        unsafe_allow_html=True,
    )

with col_sent:
    st.plotly_chart(sentiment_bar(sent["positive"], sent["negative"], sent["neutral"], ticker),
                    use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        f"<div style='background:{c['surface']};border-left:3px solid {c['blue']};"
        f"padding:.75rem 1rem;border-radius:4px;font-size:.82rem;"
        f"color:{c['subtext']};font-style:italic;margin-top:.5rem;'>"
        f"{snippet[:380]}...</div>",
        unsafe_allow_html=True,
    )

st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)

# ── Linguistic features ───────────────────────────────────────────────────────

col_radar, col_metrics = st.columns([1, 1])

with col_radar:
    st.plotly_chart(linguistic_radar(
        ling["hedge_density"], ling["certainty_ratio"],
        ling["passive_voice_ratio"], ling["vague_language_score"],
    ), use_container_width=True, config={"displayModeBar": False})

with col_metrics:
    st.markdown(f"<div class='es-label'>Linguistic breakdown</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='color:{c['muted']};font-size:.75rem;margin-bottom:.75rem;'>"
        f"Loughran-McDonald word lists + passive voice detection.</div>",
        unsafe_allow_html=True,
    )

    for label, value, unit, cap, higher_good in [
        ("Hedge Density",        ling["hedge_density"],        "per 100 words", 5.0,  False),
        ("Certainty Ratio",      ling["certainty_ratio"],      "affirmatives/hedges", 5.0, True),
        ("Passive Voice",        ling["passive_voice_ratio"],  "fraction",       0.5,  False),
        ("Vague Language Score", ling["vague_language_score"], "per 100 words",  3.0,  False),
    ]:
        pct  = min(value / cap, 1.0)
        good = (pct > 0.5) == higher_good
        bar  = c["green"] if good else (c["red"] if abs(pct - 0.5) > 0.2 else c["amber"])
        st.markdown(
            f"<div class='es-card'>"
            f"<div style='display:flex;justify-content:space-between;margin-bottom:.3rem;'>"
            f"<span style='font-weight:600;color:{c['text']};font-size:.85rem;'>{label}</span>"
            f"<span style='color:{c['subtext']};font-size:.82rem;'>"
            f"{value:.3f} <span style='color:{c['muted']};font-size:.72rem;'>({unit})</span></span>"
            f"</div>"
            f"<div style='background:{c['surface2']};border-radius:3px;height:5px;'>"
            f"<div style='background:{bar};width:{pct*100:.0f}%;height:5px;border-radius:3px;'></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div style='color:{c['muted']};font-size:.72rem;'>"
        f"{ling['word_count']:,} words · "
        f"{sent['sentence_count']} sentences · "
        f"{sent['chunk_count']} FinBERT chunks</div>",
        unsafe_allow_html=True,
    )

# ── Price impact ──────────────────────────────────────────────────────────────

price_series = pi.get("price_series", [])

if price_series and earn_dt:
    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
    col_price, col_returns = st.columns([2.5, 1])

    with col_price:
        st.plotly_chart(price_impact_chart(price_series, earn_dt, ticker, mci),
                        use_container_width=True, config={"displayModeBar": False})

    with col_returns:
        st.markdown(f"<div class='es-label'>Post-earnings returns</div>",
                    unsafe_allow_html=True)
        st.markdown(
            f"<div style='color:{c['muted']};font-size:.72rem;margin-bottom:.5rem;'>"
            f"From earnings close.</div>",
            unsafe_allow_html=True,
        )
        for label, key in [
            ("Next Day", "next_day_return"),
            ("5-Day",    "five_day_return"),
            ("30-Day",   "thirty_day_return"),
        ]:
            val = pi.get(key)
            if val is not None:
                col = c["green"] if val >= 0 else c["red"]
                sign = "+" if val >= 0 else ""
                st.markdown(
                    f"<div class='es-kpi' style='margin-bottom:.5rem;'>"
                    f"<div style='color:{c['muted']};font-size:.72rem;'>{label}</div>"
                    f"<div style='color:{col};font-size:1.6rem;font-weight:700;'>"
                    f"{sign}{val*100:.1f}%</div></div>",
                    unsafe_allow_html=True,
                )

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown(
    f"<div class='es-footer'>"
    f"EarningsSense &nbsp;·&nbsp; Built by Elias Wächter<br>"
    f"FinBERT · Loughran-McDonald · SEC EDGAR · Yahoo Finance · Streamlit · Plotly<br>"
    f"<span style='color:{c['muted']};font-size:.72rem;'>"
    f"Araci (2019) · Loughran &amp; McDonald (2011) · Li (2010) · Rogers et al. (2011)"
    f"</span></div>",
    unsafe_allow_html=True,
)
