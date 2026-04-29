"""
EarningsSense - Live Analysis page.

Supports two analysis sources:
  - 10-Q Filing (MD&A)  : free, no API key, fetched from SEC EDGAR
  - Earnings Call Transcript : requires FMP_API_KEY (free tier at financialmodelingprep.com)

For transcripts, the Q&A section is scored separately so you can compare
management language under scripted remarks vs. analyst pressure.
"""
from __future__ import annotations

import html

import streamlit as st

st.set_page_config(
    page_title="Live Analysis - EarningsSense",
    layout="wide",
)

from src.ui.sidebar import inject_sidebar_style, render_sidebar_branding
inject_sidebar_style()

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

render_sidebar_branding()

st.title("Live Analysis")
st.markdown(
    "<div style='color:#94a3b8;margin-bottom:1rem;'>"
    "Score any publicly traded US company from its latest SEC 10-Q filing "
    "or earnings call transcript.</div>",
    unsafe_allow_html=True,
)

# ── Input row ─────────────────────────────────────────────────────────────────

col_input, col_btn = st.columns([3, 1])
with col_input:
    ticker_input = st.text_input(
        "Ticker symbol",
        placeholder="e.g. NVDA, MSFT, AAPL, META",
        label_visibility="collapsed",
    )
with col_btn:
    run_btn = st.button("Analyze →", type="primary")

source_mode = st.radio(
    "Analysis source",
    ["10-Q Filing (MD&A)", "Earnings Call Transcript (FMP API)"],
    horizontal=True,
    label_visibility="collapsed",
)

if source_mode == "Earnings Call Transcript (FMP API)":
    st.markdown(
        "<div style='color:#475569;font-size:0.77rem;'>"
        "Requires FMP_API_KEY. Free key at "
        "<a href='https://financialmodelingprep.com/developer/docs/' "
        "style='color:#60a5fa;'>financialmodelingprep.com</a> - "
        "add to .streamlit/secrets.toml as "
        "<code>FMP_API_KEY = \"your_key\"</code></div>",
        unsafe_allow_html=True,
    )

st.markdown(
    "<div style='color:#475569;font-size:0.77rem;margin-bottom:1rem;'>"
    "Fetches live from SEC EDGAR or FMP - any publicly traded US company.</div>",
    unsafe_allow_html=True,
)

# ── Analysis pipeline ─────────────────────────────────────────────────────────

if run_btn and ticker_input:
    ticker = ticker_input.strip().upper()

    from src.analysis.sentiment   import analyze as analyze_sentiment
    from src.analysis.linguistics import extract as extract_linguistics
    from src.analysis.signals     import compute_scores
    from src.analysis.guidance    import extract_guidance, compute_yoy_delta
    from src.db.database          import (init_db, get_mci_history,
                                          upsert_mci_score, get_sector_benchmarks)
    from src.data.sectors         import get_sector, get_tickers_in_sector

    init_db()

    qa_scores             = None
    qa_sentiment_result   = None
    qa_linguistics_result = None

    # --- Fetch source text ---
    if source_mode == "10-Q Filing (MD&A)":
        from src.data.edgar import fetch_filing_text
        with st.spinner(f"Fetching SEC EDGAR 10-Q for {ticker}..."):
            try:
                filing = fetch_filing_text(ticker)
            except Exception as e:
                st.error(f"EDGAR fetch failed: {e}")
                st.stop()
        analysis_text = filing["text"]
        report_date   = filing.get("report_date", "")
        company_name  = filing.get("company", ticker)
        source_label  = "10-Q MD&A"
        snippet_label = "MD&A Text Snippet"

    else:
        from src.data.transcripts import fetch_transcript
        with st.spinner(f"Fetching earnings call transcript for {ticker}..."):
            try:
                transcript = fetch_transcript(ticker)
            except ValueError as e:
                st.error(str(e))
                st.stop()
            except Exception as e:
                st.error(f"Transcript fetch failed: {e}")
                st.stop()
        analysis_text = transcript["text"]
        qa_text       = transcript.get("qa_text", "")
        report_date   = transcript.get("report_date", "")
        company_name  = transcript.get("company", ticker)
        source_label  = f"Earnings Call {transcript.get('quarter_label', '')}"
        snippet_label = "Transcript Snippet"

    # --- Main NLP pipeline ---
    with st.spinner("Running FinBERT + linguistic analysis..."):
        sentiment   = analyze_sentiment(analysis_text)
        linguistics = extract_linguistics(analysis_text)
        scores      = compute_scores(sentiment, linguistics)
        guidance    = extract_guidance(analysis_text)

    # --- Separate Q&A analysis for transcripts ---
    if source_mode != "10-Q Filing (MD&A)" and qa_text and len(qa_text.split()) > 100:
        with st.spinner("Scoring Q&A section separately..."):
            qa_sentiment_result   = analyze_sentiment(qa_text)
            qa_linguistics_result = extract_linguistics(qa_text)
            qa_scores             = compute_scores(qa_sentiment_result, qa_linguistics_result)

    # --- Quarter label ---
    if report_date and len(report_date) >= 7:
        year, month = report_date[:4], report_date[5:7]
        quarter = f"{year}-Q{(int(month) - 1) // 3 + 1}"
    else:
        quarter = "Latest"

    # --- DB: history + YoY delta ---
    history = get_mci_history(ticker, limit=12)
    yoy = compute_yoy_delta(
        scores.management_confidence_index,
        scores.deception_risk_score,
        guidance.guidance_score,
        history,
        quarter,
    )

    # --- Price impact ---
    price_impact = {}
    if report_date:
        with st.spinner("Fetching price impact..."):
            try:
                from src.data.prices import fetch_price_impact
                price_impact = fetch_price_impact(ticker, report_date)
            except Exception:
                pass

    # --- Earnings surprise (FMP only) ---
    earnings_surprises = []
    if source_mode != "10-Q Filing (MD&A)":
        try:
            from src.data.transcripts import fetch_earnings_surprise
            earnings_surprises = fetch_earnings_surprise(ticker)
        except Exception:
            pass

    # --- Sector benchmark ---
    sector         = get_sector(ticker)
    sector_tickers = [t for t in get_tickers_in_sector(sector) if t != ticker]
    sector_bench   = get_sector_benchmarks(sector_tickers[:30])

    # --- Persist to DB ---
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
        "ticker":       ticker,
        "company":      company_name,
        "quarter":      quarter,
        "earnings_date": report_date,
        "source_label": source_label,
        "snippet_label": snippet_label,
        "snippet":      analysis_text[:600] + "...",
        "sentiment": {
            "positive":       sentiment.positive,
            "negative":       sentiment.negative,
            "neutral":        sentiment.neutral,
            "sentence_count": sentiment.sentence_count,
            "chunk_count":    sentiment.chunk_count,
        },
        "linguistics": {
            "certainty_ratio":      linguistics.certainty_ratio,
            "hedge_density":        linguistics.hedge_density,
            "passive_voice_ratio":  linguistics.passive_voice_ratio,
            "vague_language_score": linguistics.vague_language_score,
            "word_count":           linguistics.word_count,
            "avg_sentence_length":  linguistics.avg_sentence_length,
        },
        "scores": {
            "management_confidence_index": scores.management_confidence_index,
            "deception_risk_score":        scores.deception_risk_score,
        },
        "qa_scores": {
            "management_confidence_index": qa_scores.management_confidence_index,
            "deception_risk_score":        qa_scores.deception_risk_score,
        } if qa_scores else None,
        "guidance": {
            "guidance_score":     guidance.guidance_score,
            "fls_sentence_count": guidance.fls_sentence_count,
            "fls_ratio":          guidance.fls_ratio,
            "key_phrases":        guidance.key_phrases,
        },
        "yoy": {
            "delta_mci":      yoy.delta_mci,
            "delta_drs":      yoy.delta_drs,
            "trend":          yoy.trend,
            "interpretation": yoy.interpretation,
        },
        "price_impact":       price_impact,
        "earnings_surprises": earnings_surprises,
        "sector":             sector,
        "sector_bench":       sector_bench,
        "history":            history,
    }

    # ── Display ────────────────────────────────────────────────────────────────
    from src.visualization.charts import (
        confidence_gauges, sentiment_bar, linguistic_radar,
        price_impact_chart, mci_trend_chart, earnings_surprise_chart,
    )

    mci = result["scores"]["management_confidence_index"]
    drs = result["scores"]["deception_risk_score"]
    gs  = result["guidance"]["guidance_score"]
    delta_mci = result["yoy"]["delta_mci"]

    st.markdown(f"## {result['ticker']} - {result['company']}")
    st.markdown(
        f"<div style='color:#64748b;font-size:0.85rem;'>"
        f"{result['quarter']} · {result['earnings_date']} · "
        f"Sector: {result['sector']} · Source: {result['source_label']}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # KPI row
    mci_color = "#22c55e" if mci >= 65 else ("#f97316" if mci >= 45 else "#ef4444")
    drs_color = "#ef4444" if drs >= 55 else ("#f97316" if drs >= 35 else "#22c55e")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        delta_str = f"YoY: {delta_mci:+.1f} pts" if delta_mci is not None else "YoY: -"
        st.markdown(
            f"<div class='metric-card'>"
            f"<div style='color:#64748b;font-size:.75rem;'>MCI</div>"
            f"<div style='color:{mci_color};font-size:2.2rem;font-weight:700;'>{mci:.0f}</div>"
            f"<div style='color:#64748b;font-size:.75rem;'>{delta_str}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='metric-card'>"
            f"<div style='color:#64748b;font-size:.75rem;'>DRS</div>"
            f"<div style='color:{drs_color};font-size:2.2rem;font-weight:700;'>{drs:.0f}</div>"
            f"<div style='color:#64748b;font-size:.75rem;'>Deception Risk</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='metric-card'>"
            f"<div style='color:#64748b;font-size:.75rem;'>Guidance Score</div>"
            f"<div style='color:#a78bfa;font-size:2.2rem;font-weight:700;'>{gs:.0f}</div>"
            f"<div style='color:#64748b;font-size:.75rem;'>Forward confidence</div></div>",
            unsafe_allow_html=True,
        )
    with c4:
        ret       = result["price_impact"].get("next_day_return")
        ret_str   = f"{ret * 100:+.2f}%" if ret is not None else "-"
        ret_color = "#22c55e" if (ret or 0) >= 0 else "#ef4444"
        st.markdown(
            f"<div class='metric-card'>"
            f"<div style='color:#64748b;font-size:.75rem;'>Next-Day Return</div>"
            f"<div style='color:{ret_color};font-size:2.2rem;font-weight:700;'>{ret_str}</div>"
            f"<div style='color:#64748b;font-size:.75rem;'>Post-filing</div></div>",
            unsafe_allow_html=True,
        )

    # Sector benchmark
    sb = result["sector_bench"]
    if sb.get("count", 0) > 0:
        mci_diff = mci - sb["avg_mci"]
        drs_diff = drs - sb["avg_drs"]
        mci_vs = f"{'above' if mci_diff >= 0 else 'below'} sector avg ({sb['avg_mci']:.1f})"
        drs_vs = f"{'above' if drs_diff >= 0 else 'below'} sector avg ({sb['avg_drs']:.1f})"
        st.markdown(
            f"<div style='color:#475569;font-size:.8rem;margin-bottom:.4rem;'>"
            f"Sector ({result['sector']}, n={sb['count']}): "
            f"MCI {mci_diff:+.1f} {mci_vs} · DRS {drs_diff:+.1f} {drs_vs}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # YoY trend banner
    yoy_data = result["yoy"]
    if yoy_data["trend"] and yoy_data["trend"] != "no_prior":
        tc = {"improving": "#22c55e", "deteriorating": "#ef4444",
              "stable": "#60a5fa", "mixed": "#f97316"}.get(yoy_data["trend"], "#94a3b8")
        st.markdown(
            f"<div style='background:{tc}18;border-left:3px solid {tc};padding:.6rem 1rem;"
            f"border-radius:4px;color:#cbd5e1;font-size:.85rem;margin-bottom:1rem;'>"
            f"<strong style='color:{tc};'>YoY: {html.escape(yoy_data['trend'].upper())}</strong>"
            f" - {html.escape(yoy_data['interpretation'])}</div>",
            unsafe_allow_html=True,
        )

    # Gauges + sentiment bar
    col_g, col_s = st.columns(2)
    with col_g:
        st.plotly_chart(confidence_gauges(mci, drs), width="stretch")
    with col_s:
        sent = result["sentiment"]
        st.plotly_chart(
            sentiment_bar(sent["positive"], sent["negative"], sent["neutral"], ticker),
            width="stretch",
        )

    # Transcript Q&A comparison
    if result["qa_scores"]:
        qas = result["qa_scores"]
        st.markdown("#### Prepared Remarks vs. Q&A Session")
        st.markdown(
            "<div style='color:#64748b;font-size:.8rem;margin-bottom:.5rem;'>"
            "Management language often becomes more hedged under analyst questioning. "
            "A lower MCI or higher DRS in Q&A may indicate deflection under pressure.</div>",
            unsafe_allow_html=True,
        )
        qa_c1, qa_c2, qa_c3 = st.columns(3)
        mci_delta = qas["management_confidence_index"] - mci
        drs_delta = qas["deception_risk_score"] - drs
        with qa_c1:
            st.markdown(
                f"<div class='metric-card'>"
                f"<div style='color:#64748b;font-size:.75rem;'>Prepared Remarks MCI</div>"
                f"<div style='color:#3b82f6;font-size:1.8rem;font-weight:700;'>{mci:.0f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with qa_c2:
            qa_mci_c = "#22c55e" if qas["management_confidence_index"] >= mci else "#ef4444"
            st.markdown(
                f"<div class='metric-card'>"
                f"<div style='color:#64748b;font-size:.75rem;'>Q&A Session MCI</div>"
                f"<div style='color:{qa_mci_c};font-size:1.8rem;font-weight:700;'>"
                f"{qas['management_confidence_index']:.0f}</div>"
                f"<div style='color:#64748b;font-size:.72rem;'>vs prepared: {mci_delta:+.1f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with qa_c3:
            qa_drs_c = "#ef4444" if qas["deception_risk_score"] > drs else "#22c55e"
            st.markdown(
                f"<div class='metric-card'>"
                f"<div style='color:#64748b;font-size:.75rem;'>Q&A Session DRS</div>"
                f"<div style='color:{qa_drs_c};font-size:1.8rem;font-weight:700;'>"
                f"{qas['deception_risk_score']:.0f}</div>"
                f"<div style='color:#64748b;font-size:.72rem;'>vs prepared: {drs_delta:+.1f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Guidance key phrases
    kp = result["guidance"]["key_phrases"]
    if kp:
        st.markdown("#### Key Guidance Phrases")
        for phrase in kp:
            st.markdown(
                f"<div style='background:#1e293b;border-left:3px solid #a78bfa;"
                f"padding:.6rem 1rem;border-radius:4px;color:#cbd5e1;font-size:.85rem;"
                f"margin-bottom:.4rem;font-style:italic;'>\"{html.escape(phrase)}\"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Linguistic radar + price impact
    ling = result["linguistics"]
    col_r, col_p = st.columns(2)
    with col_r:
        st.plotly_chart(
            linguistic_radar(
                ling["hedge_density"], ling["certainty_ratio"],
                ling["passive_voice_ratio"], ling["vague_language_score"],
            ),
            width="stretch",
        )
    with col_p:
        pi           = result["price_impact"]
        price_series = pi.get("price_series", [])
        earn_date    = result["earnings_date"]
        if price_series and earn_date:
            st.plotly_chart(
                price_impact_chart(price_series, earn_date, ticker, mci),
                width="stretch",
            )
        else:
            st.markdown("#### Post-Earnings Returns")
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
                        f"<div style='color:#94a3b8;font-size:.8rem;'>{label}</div>"
                        f"<div style='font-size:1.6rem;font-weight:700;color:{color};'>"
                        f"{sign}{val * 100:.1f}%</div></div>",
                        unsafe_allow_html=True,
                    )

    # Multi-quarter trend
    if len(history) > 1:
        st.markdown("---")
        st.markdown("#### Multi-Quarter MCI / DRS Trend")
        st.plotly_chart(mci_trend_chart(history), width="stretch")

    # Earnings surprise (transcript mode with FMP key)
    if result["earnings_surprises"]:
        st.markdown("---")
        st.markdown("#### EPS Actual vs. Estimate")
        st.plotly_chart(
            earnings_surprise_chart(result["earnings_surprises"], ticker),
            width="stretch",
        )

    st.markdown("---")

    # Export + snippet
    from src.visualization.report_pdf import generate_pdf
    try:
        pdf_bytes = generate_pdf(result)
        st.download_button(
            "Download report (PDF)",
            data=pdf_bytes,
            file_name=f"{ticker}_{quarter}_earningssense.pdf",
            mime="application/pdf",
        )
    except Exception as _pdf_err:
        st.warning(f"PDF generation failed: {_pdf_err}")

    with st.expander(result["snippet_label"]):
        st.markdown(
            f"<div style='color:#94a3b8;font-size:.82rem;line-height:1.6;'>"
            f"{html.escape(result['snippet'])}</div>",
            unsafe_allow_html=True,
        )

elif run_btn and not ticker_input:
    st.warning("Enter a ticker symbol to analyze.")
