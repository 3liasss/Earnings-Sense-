"""
EarningsSense - Compare Tickers.
Side-by-side NLP analysis of two companies from their latest 10-Q filings.
"""
from __future__ import annotations

import html

import streamlit as st

st.set_page_config(page_title="Compare - EarningsSense", layout="wide")

from src.ui.sidebar import render_sidebar_branding
from src.ui.theme   import base_css, C

render_sidebar_branding()
st.markdown(base_css(), unsafe_allow_html=True)

c = C()

st.title("Compare Tickers")
st.markdown(
    f"<div style='color:{c['subtext']};margin-bottom:1.25rem;'>"
    f"Side-by-side NLP analysis from the latest 10-Q of two companies. "
    f"Fetches live from SEC EDGAR.</div>",
    unsafe_allow_html=True,
)

# ── Inputs ────────────────────────────────────────────────────────────────────

col1, col2, col_btn = st.columns([2, 2, 1])
with col1:
    ticker1 = st.text_input("Ticker 1", placeholder="e.g. AAPL")
with col2:
    ticker2 = st.text_input("Ticker 2", placeholder="e.g. MSFT")
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    compare_btn = st.button("Compare →", type="primary", use_container_width=True)


# ── Analysis helper ───────────────────────────────────────────────────────────

def _run_analysis(ticker: str) -> dict | None:
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
        "ticker":      ticker,
        "company":     filing.get("company", ticker),
        "quarter":     quarter,
        "sector":      get_sector(ticker),
        "mci":         scores.management_confidence_index,
        "drs":         scores.deception_risk_score,
        "guidance":    guidance.guidance_score,
        "hedge":       linguistics.hedge_density,
        "certainty":   linguistics.certainty_ratio,
        "passive":     linguistics.passive_voice_ratio,
        "vague":       linguistics.vague_language_score,
        "words":       linguistics.word_count,
        "pos":         sentiment.positive,
        "neg":         sentiment.negative,
        "neu":         sentiment.neutral,
        "key_phrases": guidance.key_phrases,
    }


# ── Run ───────────────────────────────────────────────────────────────────────

if compare_btn and ticker1 and ticker2:
    t1 = ticker1.strip().upper()
    t2 = ticker2.strip().upper()

    if t1 == t2:
        st.warning("Enter two different ticker symbols.")
        st.stop()

    with st.spinner(f"Analyzing {t1} and {t2}..."):
        r1 = _run_analysis(t1)
        r2 = _run_analysis(t2) if r1 else None

    if not r1 or not r2:
        st.stop()

    from src.visualization.charts import (confidence_gauges, sentiment_bar,
                                          linguistic_radar, linguistic_radar_compare)

    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)

    # ── VERDICT at the top ────────────────────────────────────────────────────
    winner_mci = t1 if r1["mci"] >= r2["mci"] else t2
    winner_drs = t1 if r1["drs"] <= r2["drs"] else t2
    same_winner = winner_mci == winner_drs

    verdict_color = c["green"] if same_winner else c["amber"]
    if same_winner:
        verdict = (f"<strong style='color:{c['green']};'>{winner_mci}</strong> "
                   f"has more confident language AND lower deception risk.")
    else:
        verdict = (f"More confident language: <strong style='color:{c['green']};'>{winner_mci}</strong>"
                   f" &nbsp;·&nbsp; "
                   f"Lower deception risk: <strong style='color:{c['green']};'>{winner_drs}</strong>")

    st.markdown(
        f"<div style='background:{verdict_color}12;border:1px solid {verdict_color}44;"
        f"border-left:4px solid {verdict_color};border-radius:10px;"
        f"padding:1rem 1.25rem;margin-bottom:1.25rem;'>"
        f"<div class='es-label' style='color:{verdict_color};margin-bottom:.3rem;'>Verdict</div>"
        f"<div style='color:{c['text']};font-size:.95rem;'>{verdict}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Company headers ───────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(
            f"<h3><span class='es-ticker'>{r1['ticker']}</span> {r1['company']}</h3>"
            f"<div style='color:{c['muted']};font-size:.82rem;margin-top:-.5rem;'>"
            f"{r1['quarter']} · {r1['sector']}</div>",
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(
            f"<h3><span class='es-ticker'>{r2['ticker']}</span> {r2['company']}</h3>"
            f"<div style='color:{c['muted']};font-size:.82rem;margin-top:-.5rem;'>"
            f"{r2['quarter']} · {r2['sector']}</div>",
            unsafe_allow_html=True,
        )

    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
    st.markdown(f"<div class='es-label'>Signal comparison</div>", unsafe_allow_html=True)

    def _mci_color(v):
        return c["green"] if v >= 65 else (c["amber"] if v >= 45 else c["red"])

    def _drs_color(v):
        return c["red"] if v >= 55 else (c["amber"] if v >= 35 else c["green"])

    METRICS = [
        ("MCI",             "mci",      _mci_color, _mci_color, "{:.0f}"),
        ("DRS",             "drs",      _drs_color, _drs_color, "{:.0f}"),
        ("Guidance Score",  "guidance", lambda _: c["violet"], lambda _: c["violet"], "{:.0f}"),
        ("Hedge density",   "hedge",    lambda _: c["subtext"], lambda _: c["subtext"], "{:.3f}"),
        ("Certainty ratio", "certainty",lambda _: c["subtext"], lambda _: c["subtext"], "{:.3f}"),
        ("Passive voice",   "passive",  lambda _: c["subtext"], lambda _: c["subtext"], "{:.3f}"),
        ("Vague language",  "vague",    lambda _: c["subtext"], lambda _: c["subtext"], "{:.3f}"),
        ("FinBERT positive","pos",      lambda _: c["green"],   lambda _: c["green"],   "{:.3f}"),
        ("FinBERT negative","neg",      lambda _: c["red"],     lambda _: c["red"],     "{:.3f}"),
        ("Words analyzed",  "words",    lambda _: c["muted"],   lambda _: c["muted"],   "{:,}"),
    ]

    hm, h1, h2 = st.columns([2.5, 1.5, 1.5])
    hm.markdown(f"<div class='es-label'>Metric</div>", unsafe_allow_html=True)
    h1.markdown(f"<div class='es-label'>{t1}</div>", unsafe_allow_html=True)
    h2.markdown(f"<div class='es-label'>{t2}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<hr style='border:none;border-top:1px solid {c['border']};margin:.2rem 0 .4rem;'>",
        unsafe_allow_html=True,
    )

    for label, key, cfn1, cfn2, fmt in METRICS:
        v1, v2 = r1.get(key, 0), r2.get(key, 0)
        cm, c1, c2 = st.columns([2.5, 1.5, 1.5])
        cm.markdown(f"<span style='color:{c['subtext']};font-size:.85rem;'>{label}</span>",
                    unsafe_allow_html=True)
        c1.markdown(f"<span style='color:{cfn1(v1)};font-weight:700;'>{fmt.format(v1)}</span>",
                    unsafe_allow_html=True)
        c2.markdown(f"<span style='color:{cfn2(v2)};font-weight:700;'>{fmt.format(v2)}</span>",
                    unsafe_allow_html=True)

    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)

    # ── Gauges side by side ───────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(confidence_gauges(r1["mci"], r1["drs"]),
                        use_container_width=True, config={"displayModeBar": False})
    with col_r:
        st.plotly_chart(confidence_gauges(r2["mci"], r2["drs"]),
                        use_container_width=True, config={"displayModeBar": False})

    # ── Sentiment bars ────────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(sentiment_bar(r1["pos"], r1["neg"], r1["neu"], r1["ticker"]),
                        use_container_width=True, config={"displayModeBar": False})
    with col_r:
        st.plotly_chart(sentiment_bar(r2["pos"], r2["neg"], r2["neu"], r2["ticker"]),
                        use_container_width=True, config={"displayModeBar": False})

    # ── Linguistic radar - dual-trace overlay ─────────────────────────────────
    st.markdown(f"<div class='es-label'>Linguistic profile overlay</div>",
                unsafe_allow_html=True)
    st.plotly_chart(
        linguistic_radar_compare(
            r1["hedge"], r1["certainty"], r1["passive"], r1["vague"], t1,
            r2["hedge"], r2["certainty"], r2["passive"], r2["vague"], t2,
        ),
        use_container_width=True, config={"displayModeBar": False},
    )

    # ── Key guidance phrases ──────────────────────────────────────────────────
    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
    st.markdown(f"<div class='es-label'>Key guidance phrases</div>",
                unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    for col, ticker_sym, result in [(col_l, t1, r1), (col_r, t2, r2)]:
        with col:
            st.markdown(f"<strong style='color:{c['subtext']};'>{ticker_sym}</strong>",
                        unsafe_allow_html=True)
            kp = result.get("key_phrases", [])
            if kp:
                for phrase in kp[:3]:
                    st.markdown(
                        f"<div style='background:{c['surface']};border-left:3px solid {c['violet']};"
                        f"padding:.5rem .9rem;border-radius:4px;color:{c['subtext']};"
                        f"font-size:.82rem;margin-bottom:.35rem;font-style:italic;'>"
                        f"&ldquo;{html.escape(phrase)}&rdquo;</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    f"<div style='color:{c['muted']};font-size:.82rem;'>None detected</div>",
                    unsafe_allow_html=True,
                )

    st.markdown(
        f"<div class='es-footer'>"
        f"EarningsSense &nbsp;·&nbsp; Built by Elias Wächter<br>"
        f"FinBERT · Loughran-McDonald · SEC EDGAR · Streamlit"
        f"</div>",
        unsafe_allow_html=True,
    )

elif compare_btn:
    st.warning("Enter both ticker symbols to compare.")
