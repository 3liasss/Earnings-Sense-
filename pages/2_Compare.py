"""
EarningsSense - Compare Tickers.

Side-by-side NLP analysis of two companies from their latest 10-Q filings.
Runs the full FinBERT + linguistic pipeline on both and presents a
structured comparison of every signal.
"""
from __future__ import annotations

import html

import streamlit as st

st.set_page_config(
    page_title="Compare - EarningsSense",
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

st.title("Compare Tickers")
st.markdown(
    "<div style='color:#94a3b8;margin-bottom:1.5rem;'>"
    "Side-by-side NLP analysis from the latest 10-Q filing of two companies.</div>",
    unsafe_allow_html=True,
)

# ── Ticker inputs ─────────────────────────────────────────────────────────────

c1, c2, c_btn = st.columns([2, 2, 1])
with c1:
    ticker1 = st.text_input("Ticker 1", placeholder="e.g. AAPL")
with c2:
    ticker2 = st.text_input("Ticker 2", placeholder="e.g. MSFT")
with c_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    compare_btn = st.button("Compare →", type="primary")


# ── Analysis helper ───────────────────────────────────────────────────────────

def _run_analysis(ticker: str) -> dict | None:
    """Run the full pipeline for one ticker and return a flat result dict."""
    from src.data.edgar           import fetch_filing_text
    from src.analysis.sentiment   import analyze as analyze_sentiment
    from src.analysis.linguistics import extract as extract_linguistics
    from src.analysis.signals     import compute_scores
    from src.analysis.guidance    import extract_guidance
    from src.data.sectors         import get_sector

    try:
        filing = fetch_filing_text(ticker)
    except Exception as e:
        st.error(f"{ticker}: fetch failed - {e}")
        return None

    sentiment   = analyze_sentiment(filing["text"])
    linguistics = extract_linguistics(filing["text"])
    scores      = compute_scores(sentiment, linguistics)
    guidance    = extract_guidance(filing["text"])

    report_date = filing.get("report_date", "")
    if report_date and len(report_date) >= 7:
        year, month = report_date[:4], report_date[5:7]
        quarter = f"{year}-Q{(int(month) - 1) // 3 + 1}"
    else:
        quarter = "Latest"

    return {
        "ticker":    ticker,
        "company":   filing.get("company", ticker),
        "quarter":   quarter,
        "sector":    get_sector(ticker),
        "mci":       scores.management_confidence_index,
        "drs":       scores.deception_risk_score,
        "guidance":  guidance.guidance_score,
        "hedge":     linguistics.hedge_density,
        "certainty": linguistics.certainty_ratio,
        "passive":   linguistics.passive_voice_ratio,
        "vague":     linguistics.vague_language_score,
        "words":     linguistics.word_count,
        "pos":       sentiment.positive,
        "neg":       sentiment.negative,
        "neu":       sentiment.neutral,
        "key_phrases": guidance.key_phrases,
    }


# ── Run comparison ────────────────────────────────────────────────────────────

if compare_btn and ticker1 and ticker2:
    t1 = ticker1.strip().upper()
    t2 = ticker2.strip().upper()

    if t1 == t2:
        st.warning("Enter two different ticker symbols.")
        st.stop()

    with st.spinner(f"Running full analysis for {t1} and {t2} (may take ~60s)..."):
        r1 = _run_analysis(t1)
        r2 = _run_analysis(t2) if r1 else None

    if not r1 or not r2:
        st.stop()

    from src.visualization.charts import confidence_gauges, sentiment_bar, linguistic_radar

    st.markdown("---")

    # Company headers
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(f"### {r1['ticker']}")
        st.markdown(
            f"<div style='color:#64748b;font-size:.85rem;'>"
            f"{r1['company']} · {r1['quarter']} · {r1['sector']}</div>",
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(f"### {r2['ticker']}")
        st.markdown(
            f"<div style='color:#64748b;font-size:.85rem;'>"
            f"{r2['company']} · {r2['quarter']} · {r2['sector']}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("#### Signal Comparison")

    def _mci_color(v: float) -> str:
        return "#22c55e" if v >= 65 else ("#f97316" if v >= 45 else "#ef4444")

    def _drs_color(v: float) -> str:
        return "#ef4444" if v >= 55 else ("#f97316" if v >= 35 else "#22c55e")

    metrics = [
        ("MCI",             "mci",       _mci_color, _mci_color, "{:.0f}"),
        ("DRS",             "drs",       _drs_color, _drs_color, "{:.0f}"),
        ("Guidance Score",  "guidance",  lambda _: "#a78bfa", lambda _: "#a78bfa", "{:.0f}"),
        ("Hedge density",   "hedge",     lambda _: "#94a3b8", lambda _: "#94a3b8", "{:.3f}"),
        ("Certainty ratio", "certainty", lambda _: "#94a3b8", lambda _: "#94a3b8", "{:.3f}"),
        ("Passive voice",   "passive",   lambda _: "#94a3b8", lambda _: "#94a3b8", "{:.3f}"),
        ("Vague language",  "vague",     lambda _: "#94a3b8", lambda _: "#94a3b8", "{:.3f}"),
        ("FinBERT positive","pos",       lambda _: "#22c55e", lambda _: "#22c55e", "{:.3f}"),
        ("FinBERT negative","neg",       lambda _: "#ef4444", lambda _: "#ef4444", "{:.3f}"),
        ("Words analyzed",  "words",     lambda _: "#475569", lambda _: "#475569", "{:,}"),
    ]

    hdr_m, hdr_1, hdr_2 = st.columns([2.5, 1.5, 1.5])
    hdr_m.markdown("<div style='color:#475569;font-size:.72rem;font-weight:600;text-transform:uppercase;'>Metric</div>", unsafe_allow_html=True)
    hdr_1.markdown(f"<div style='color:#475569;font-size:.72rem;font-weight:600;text-transform:uppercase;'>{t1}</div>", unsafe_allow_html=True)
    hdr_2.markdown(f"<div style='color:#475569;font-size:.72rem;font-weight:600;text-transform:uppercase;'>{t2}</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:.25rem 0 .5rem;border-color:#1e293b;'>", unsafe_allow_html=True)

    for label, key, cfn1, cfn2, fmt in metrics:
        v1 = r1.get(key, 0)
        v2 = r2.get(key, 0)
        mc_m, mc_1, mc_2 = st.columns([2.5, 1.5, 1.5])
        mc_m.markdown(f"<span style='color:#94a3b8;font-size:.85rem;'>{label}</span>", unsafe_allow_html=True)
        mc_1.markdown(f"<span style='color:{cfn1(v1)};font-weight:700;'>{fmt.format(v1)}</span>", unsafe_allow_html=True)
        mc_2.markdown(f"<span style='color:{cfn2(v2)};font-weight:700;'>{fmt.format(v2)}</span>", unsafe_allow_html=True)

    st.markdown("---")

    # Gauges side by side
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(confidence_gauges(r1["mci"], r1["drs"]), width="stretch")
    with col_r:
        st.plotly_chart(confidence_gauges(r2["mci"], r2["drs"]), width="stretch")

    # Sentiment bars
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(sentiment_bar(r1["pos"], r1["neg"], r1["neu"], r1["ticker"]), width="stretch")
    with col_r:
        st.plotly_chart(sentiment_bar(r2["pos"], r2["neg"], r2["neu"], r2["ticker"]), width="stretch")

    # Linguistic radars
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(
            linguistic_radar(r1["hedge"], r1["certainty"], r1["passive"], r1["vague"]),
            width="stretch",
        )
    with col_r:
        st.plotly_chart(
            linguistic_radar(r2["hedge"], r2["certainty"], r2["passive"], r2["vague"]),
            width="stretch",
        )

    # Key guidance phrases
    st.markdown("---")
    st.markdown("#### Key Guidance Phrases")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(f"**{t1}**")
        kp1 = r1.get("key_phrases", [])
        if kp1:
            for phrase in kp1[:3]:
                st.markdown(
                    f"<div style='background:#1e293b;border-left:3px solid #a78bfa;"
                    f"padding:.6rem 1rem;border-radius:4px;color:#cbd5e1;"
                    f"font-size:.82rem;margin-bottom:.4rem;font-style:italic;'>"
                    f"\"{html.escape(phrase)}\"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("<div style='color:#475569;font-size:.82rem;'>None detected</div>", unsafe_allow_html=True)

    with col_r:
        st.markdown(f"**{t2}**")
        kp2 = r2.get("key_phrases", [])
        if kp2:
            for phrase in kp2[:3]:
                st.markdown(
                    f"<div style='background:#1e293b;border-left:3px solid #a78bfa;"
                    f"padding:.6rem 1rem;border-radius:4px;color:#cbd5e1;"
                    f"font-size:.82rem;margin-bottom:.4rem;font-style:italic;'>"
                    f"\"{html.escape(phrase)}\"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("<div style='color:#475569;font-size:.82rem;'>None detected</div>", unsafe_allow_html=True)

    # Summary callout
    st.markdown("---")
    winner_mci = t1 if r1["mci"] >= r2["mci"] else t2
    winner_drs = t1 if r1["drs"] <= r2["drs"] else t2
    st.markdown(
        f"<div style='background:#1e3a5f22;border:1px solid #3b82f655;"
        f"border-radius:12px;padding:1rem 1.25rem;'>"
        f"<div style='color:#60a5fa;font-size:.72rem;font-weight:700;"
        f"text-transform:uppercase;margin-bottom:.4rem;'>Summary</div>"
        f"<div style='color:#cbd5e1;font-size:.88rem;'>"
        f"More confident language (higher MCI): "
        f"<strong style='color:#22c55e;'>{winner_mci}</strong>"
        f" &nbsp;·&nbsp; "
        f"Lower deception risk (lower DRS): "
        f"<strong style='color:#22c55e;'>{winner_drs}</strong>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

elif compare_btn:
    st.warning("Enter both ticker symbols to compare.")
