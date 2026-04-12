"""
EarningsSense — Live Analysis page.

Enter any ticker to fetch the latest SEC EDGAR 10-Q filing and run
MCI/DRS/Guidance scoring in real time.
"""

from __future__ import annotations
import json
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Live Analysis — EarningsSense",
    layout="wide",
)

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
.metric-card {
    background: #1e293b; border: 1px solid #334155;
    border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 0.75rem;
}
h1,h2,h3 { color: #f1f5f9 !important; }
</style>
""", unsafe_allow_html=True)

st.title("Live Analysis")
st.markdown("<div style='color:#94a3b8;margin-bottom:1.5rem;'>Enter any S&P 500 ticker to fetch the latest SEC 10-Q and score management language in real time.</div>", unsafe_allow_html=True)

# ── Sample mode fallback ───────────────────────────────────────────────────────

SAMPLES_DIR = Path("data/samples")
INDEX_FILE  = SAMPLES_DIR / "index.json"

@st.cache_data
def load_index():
    if not INDEX_FILE.exists():
        return []
    with open(INDEX_FILE) as f:
        return json.load(f)

@st.cache_data
def load_sample(filename: str) -> dict:
    with open(SAMPLES_DIR / filename) as f:
        return json.load(f)

# ── UI ─────────────────────────────────────────────────────────────────────────

col_input, col_btn = st.columns([3, 1])
with col_input:
    ticker_input = st.text_input(
        "Ticker symbol",
        placeholder="e.g. NVDA, MSFT, AAPL, META, TSLA",
        label_visibility="collapsed",
    )
with col_btn:
    run_btn = st.button("Analyze →", type="primary", use_container_width=True)

st.markdown("<div style='color:#475569;font-size:0.78rem;margin-top:-0.5rem;margin-bottom:1rem;'>Fetches the latest SEC EDGAR 10-Q filing automatically — any publicly traded US company.</div>", unsafe_allow_html=True)

if run_btn and ticker_input:
    ticker = ticker_input.strip().upper()

    if True:  # always live
        from src.data.edgar import fetch_filing_text
        from src.data.prices import fetch_price_impact
        from src.analysis.sentiment import analyze as analyze_sentiment
        from src.analysis.linguistics import extract as extract_linguistics
        from src.analysis.signals import compute_scores
        from src.analysis.guidance import extract_guidance, compute_yoy_delta
        from src.db.database import init_db, get_mci_history, upsert_mci_score
        from src.data.sectors import get_sector

        init_db()

        with st.spinner(f"Fetching SEC EDGAR 10-Q for {ticker}…"):
            try:
                filing = fetch_filing_text(ticker)
            except Exception as e:
                st.error(f"EDGAR fetch failed: {e}")
                st.stop()

        with st.spinner("Running FinBERT + linguistic analysis…"):
            sentiment   = analyze_sentiment(filing["text"])
            linguistics = extract_linguistics(filing["text"])
            scores      = compute_scores(sentiment, linguistics)
            guidance    = extract_guidance(filing["text"])

        report_date = filing.get("report_date", "")
        year, month = report_date[:4], report_date[5:7]
        quarter     = f"{year}-Q{(int(month)-1)//3+1}"

        history = get_mci_history(ticker, limit=12)
        yoy     = compute_yoy_delta(
            scores.management_confidence_index,
            scores.deception_risk_score,
            guidance.guidance_score,
            history,
            quarter,
        )

        price_impact = {}
        if report_date:
            with st.spinner("Fetching price impact…"):
                try:
                    price_impact = fetch_price_impact(ticker, report_date)
                except Exception:
                    pass

        upsert_mci_score(
            ticker=ticker, quarter=quarter, report_date=report_date,
            mci=scores.management_confidence_index,
            drs=scores.deception_risk_score,
            sentiment_pos=sentiment.positive,
            sentiment_neg=sentiment.negative,
            certainty_ratio=linguistics.certainty_ratio,
            hedge_density=linguistics.hedge_density,
            guidance_score=guidance.guidance_score,
            delta_mci=yoy.delta_mci,
            next_day_return=price_impact.get("next_day_return"),
        )

        result = {
            "ticker": ticker,
            "company": filing.get("company", ticker),
            "quarter": quarter,
            "earnings_date": report_date,
            "transcript_snippet": filing["text"][:600] + "…",
            "sentiment": {
                "positive": sentiment.positive,
                "negative": sentiment.negative,
                "neutral":  sentiment.neutral,
            },
            "linguistics": {
                "certainty_ratio":       linguistics.certainty_ratio,
                "hedge_density":         linguistics.hedge_density,
                "passive_voice_ratio":   linguistics.passive_voice_ratio,
                "vague_language_score":  linguistics.vague_language_score,
                "word_count":            linguistics.word_count,
                "avg_sentence_length":   linguistics.avg_sentence_length,
            },
            "scores": {
                "management_confidence_index": scores.management_confidence_index,
                "deception_risk_score":        scores.deception_risk_score,
            },
            "guidance": {
                "guidance_score":      guidance.guidance_score,
                "fls_sentence_count":  guidance.fls_sentence_count,
                "fls_ratio":           guidance.fls_ratio,
                "key_phrases":         guidance.key_phrases,
            },
            "yoy": {
                "delta_mci":   yoy.delta_mci,
                "delta_drs":   yoy.delta_drs,
                "trend":       yoy.trend,
                "interpretation": yoy.interpretation,
            },
            "price_impact": price_impact,
            "sector": get_sector(ticker),
        }

    # ── Display results ────────────────────────────────────────────────────────
    from src.visualization.charts import confidence_gauges, sentiment_bar, linguistic_radar, price_impact_chart

    st.markdown(f"## {result['ticker']} — {result.get('company','')}")
    st.markdown(f"<div style='color:#64748b;font-size:0.85rem;'>{result.get('quarter','')} · {result.get('earnings_date','')} · Sector: {result.get('sector','Unknown')}</div>", unsafe_allow_html=True)
    st.markdown("---")

    mci = result["scores"]["management_confidence_index"]
    drs = result["scores"]["deception_risk_score"]
    guidance_score = result.get("guidance", {}).get("guidance_score")
    delta_mci      = result.get("yoy", {}).get("delta_mci")

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    mci_color = "#22c55e" if mci >= 65 else ("#f97316" if mci >= 45 else "#ef4444")
    drs_color = "#ef4444" if drs >= 55 else ("#f97316" if drs >= 35 else "#22c55e")
    with c1:
        delta_str = f"YoY: {delta_mci:+.1f} pts" if delta_mci is not None else "YoY: —"
        st.markdown(f"<div class='metric-card'><div style='color:#64748b;font-size:.75rem;'>MCI</div><div style='color:{mci_color};font-size:2.2rem;font-weight:700;'>{mci:.0f}</div><div style='color:#64748b;font-size:.75rem;'>{delta_str}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-card'><div style='color:#64748b;font-size:.75rem;'>DRS</div><div style='color:{drs_color};font-size:2.2rem;font-weight:700;'>{drs:.0f}</div><div style='color:#64748b;font-size:.75rem;'>Deception Risk</div></div>", unsafe_allow_html=True)
    with c3:
        gs = f"{guidance_score:.0f}" if guidance_score is not None else "—"
        st.markdown(f"<div class='metric-card'><div style='color:#64748b;font-size:.75rem;'>Guidance Score</div><div style='color:#a78bfa;font-size:2.2rem;font-weight:700;'>{gs}</div><div style='color:#64748b;font-size:.75rem;'>Forward confidence</div></div>", unsafe_allow_html=True)
    with c4:
        ret = result.get("price_impact", {}).get("next_day_return")
        ret_str = f"{ret*100:+.2f}%" if ret is not None else "—"
        ret_color = "#22c55e" if (ret or 0) >= 0 else "#ef4444"
        st.markdown(f"<div class='metric-card'><div style='color:#64748b;font-size:.75rem;'>Next-Day Return</div><div style='color:{ret_color};font-size:2.2rem;font-weight:700;'>{ret_str}</div><div style='color:#64748b;font-size:.75rem;'>Post-filing</div></div>", unsafe_allow_html=True)

    # YoY delta banner
    yoy_data = result.get("yoy", {})
    if yoy_data.get("trend") and yoy_data["trend"] != "no_prior":
        trend_colors = {"improving": "#22c55e", "deteriorating": "#ef4444", "stable": "#60a5fa", "mixed": "#f97316"}
        tc = trend_colors.get(yoy_data["trend"], "#94a3b8")
        st.markdown(f"<div style='background:{tc}18;border-left:3px solid {tc};padding:.6rem 1rem;border-radius:4px;color:#cbd5e1;font-size:.85rem;margin-bottom:1rem;'><strong style='color:{tc};'>YoY Trend: {yoy_data['trend'].upper()}</strong> — {yoy_data['interpretation']}</div>", unsafe_allow_html=True)

    # Gauges + sentiment
    col_g, col_s = st.columns([1, 1])
    with col_g:
        st.plotly_chart(confidence_gauges(result), use_container_width=True)
    with col_s:
        st.plotly_chart(sentiment_bar(result), use_container_width=True)

    # Guidance key phrases
    kp = result.get("guidance", {}).get("key_phrases", [])
    if kp:
        st.markdown("#### Key Guidance Phrases")
        for phrase in kp:
            st.markdown(f"<div style='background:#1e293b;border-left:3px solid #a78bfa;padding:.6rem 1rem;border-radius:4px;color:#cbd5e1;font-size:.85rem;margin-bottom:.4rem;font-style:italic;'>\"{phrase}\"</div>", unsafe_allow_html=True)

    # Linguistic radar + price impact
    col_r, col_p = st.columns([1, 1])
    with col_r:
        st.plotly_chart(linguistic_radar(result), use_container_width=True)
    with col_p:
        if result.get("price_impact"):
            st.plotly_chart(price_impact_chart(result), use_container_width=True)

    # Raw snippet
    with st.expander("MD&A Text Snippet"):
        st.markdown(f"<div style='color:#94a3b8;font-size:.82rem;line-height:1.6;'>{result.get('transcript_snippet','')}</div>", unsafe_allow_html=True)

elif run_btn and not ticker_input:
    st.warning("Enter a ticker symbol to analyze.")
