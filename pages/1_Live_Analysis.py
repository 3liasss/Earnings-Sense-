"""
EarningsSense - Live Analysis.

10-Q MD&A (free, SEC EDGAR) or earnings call transcript (FMP API).
Q&A section scored separately to compare prepared remarks vs analyst pressure.
"""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

st.set_page_config(page_title="Live Analysis - EarningsSense", layout="wide")

from src.ui.sidebar import render_sidebar_branding
from src.ui.theme   import base_css, C

render_sidebar_branding()
st.markdown(base_css(), unsafe_allow_html=True)

c = C()

st.title("Live Analysis")
st.markdown(
    f"<div style='color:{c['subtext']};margin-bottom:1.25rem;'>"
    f"Score any publicly traded US company from its latest SEC 10-Q filing "
    f"or earnings call transcript. Always fetches live from source.</div>",
    unsafe_allow_html=True,
)

# ── URL param pre-fill: ?ticker=NVDA auto-populates and runs ─────────────────

_url_ticker = st.query_params.get("ticker", "").strip().upper()

# ── Input - st.form so Enter key submits without clicking the button ──────────

with st.form("analysis_form"):
    col_input, col_mode, col_btn = st.columns([2, 2, 1])
    with col_input:
        ticker_input = st.text_input(
            "Ticker",
            value=_url_ticker,
            placeholder="NVDA, MSFT, AAPL, META...",
            label_visibility="collapsed",
        )
    with col_mode:
        source_mode = st.radio(
            "Source",
            ["10-Q Filing (MD&A)", "Earnings Call Transcript (FMP)"],
            horizontal=True,
            label_visibility="collapsed",
        )
    with col_btn:
        run_btn = st.form_submit_button(
            "Analyze →", type="primary", use_container_width=True
        )

if source_mode == "Earnings Call Transcript (FMP)":
    st.markdown(
        f"<div style='color:{c['muted']};font-size:.75rem;margin-bottom:.5rem;'>"
        f"Requires FMP_API_KEY. Free key at "
        f"<a href='https://financialmodelingprep.com/developer/docs/' "
        f"style='color:{c['blue']};'>financialmodelingprep.com</a> - "
        f"add to <code>.streamlit/secrets.toml</code> as "
        f"<code>FMP_API_KEY = \"your_key\"</code>.</div>",
        unsafe_allow_html=True,
    )

# ── Pipeline ──────────────────────────────────────────────────────────────────

# Auto-trigger from URL param if user hasn't clicked yet
if _url_ticker and not run_btn:
    run_btn = True
    ticker_input = _url_ticker

COMMON_TYPOS = {
    "APPL": "AAPL", "GOGL": "GOOGL", "GOOG": "GOOGL",
    "AMZON": "AMZN", "AMAZN": "AMZN", "NFLIX": "NFLX",
    "MSFT.": "MSFT", "NVDIA": "NVDA",
}

if run_btn and not ticker_input:
    st.warning("Enter a ticker symbol - e.g. NVDA, MSFT, AAPL.")
    st.stop()

if run_btn and ticker_input:
    raw = ticker_input.strip().upper().replace(".", "").replace(" ", "")

    # Catch obvious typos before hitting EDGAR
    if raw in COMMON_TYPOS:
        suggestion = COMMON_TYPOS[raw]
        st.warning(f"Did you mean **{suggestion}**? Analyzing that instead.")
        raw = suggestion

    if not raw.isalpha() or len(raw) > 5:
        st.error(
            f"**{html.escape(raw)}** doesn't look like a valid US ticker. "
            f"Tickers are 1-5 letters (e.g. NVDA, MSFT, GOOGL)."
        )
        st.stop()

    ticker = raw
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

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

    with st.spinner("Running FinBERT + linguistic analysis..."):
        sentiment   = analyze_sentiment(analysis_text)
        linguistics = extract_linguistics(analysis_text)
        scores      = compute_scores(sentiment, linguistics)
        guidance    = extract_guidance(analysis_text)

    if source_mode != "10-Q Filing (MD&A)" and qa_text and len(qa_text.split()) > 100:
        with st.spinner("Scoring Q&A section..."):
            qa_sentiment_result   = analyze_sentiment(qa_text)
            qa_linguistics_result = extract_linguistics(qa_text)
            qa_scores             = compute_scores(qa_sentiment_result, qa_linguistics_result)

    if report_date and len(report_date) >= 7:
        year, month = report_date[:4], report_date[5:7]
        quarter = f"{year}-Q{(int(month) - 1) // 3 + 1}"
    else:
        quarter = "Latest"

    history = get_mci_history(ticker, limit=12)
    yoy = compute_yoy_delta(
        scores.management_confidence_index,
        scores.deception_risk_score,
        guidance.guidance_score,
        history,
        quarter,
    )

    price_impact = {}
    if report_date:
        with st.spinner("Fetching price impact..."):
            try:
                from src.data.prices import fetch_price_impact
                price_impact = fetch_price_impact(ticker, report_date)
            except Exception:
                pass

    earnings_surprises = []
    if source_mode != "10-Q Filing (MD&A)":
        try:
            from src.data.transcripts import fetch_earnings_surprise
            earnings_surprises = fetch_earnings_surprise(ticker)
        except Exception:
            pass

    sector        = get_sector(ticker)
    sector_tickers = [t for t in get_tickers_in_sector(sector) if t != ticker]
    sector_bench  = get_sector_benchmarks(sector_tickers[:30])

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

    # ── Display ────────────────────────────────────────────────────────────────

    from src.visualization.charts import (
        confidence_gauges, sentiment_bar, linguistic_radar,
        price_impact_chart, mci_trend_chart, earnings_surprise_chart,
    )

    mci       = scores.management_confidence_index
    drs       = scores.deception_risk_score
    gs        = guidance.guidance_score
    delta_mci = yoy.delta_mci
    ret       = price_impact.get("next_day_return")

    mci_color = c["green"] if mci >= 65 else (c["amber"] if mci >= 45 else c["red"])
    drs_color = c["red"]   if drs >= 55 else (c["amber"] if drs >= 35 else c["green"])

    # Header + PDF export inline
    hdr1, hdr2 = st.columns([5, 1])
    with hdr1:
        st.markdown(f"## {ticker} - {company_name}")
        st.markdown(
            f"<div style='color:{c['muted']};font-size:.82rem;'>"
            f"{quarter} &nbsp;·&nbsp; {report_date} &nbsp;·&nbsp; "
            f"Sector: {sector} &nbsp;·&nbsp; Source: {html.escape(source_label)}"
            f"&nbsp;·&nbsp; <span style='color:{c['muted']};'>Fetched {fetched_at}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with hdr2:
        st.markdown("<br>", unsafe_allow_html=True)
        try:
            from src.visualization.report_pdf import generate_pdf
            pdf_result = {"ticker": ticker, "company": company_name, "quarter": quarter,
                          "earnings_date": report_date, "source_label": source_label,
                          "snippet_label": snippet_label, "snippet": analysis_text[:600]+"...",
                          "sentiment": {"positive": sentiment.positive, "negative": sentiment.negative,
                                        "neutral": sentiment.neutral, "sentence_count": sentiment.sentence_count,
                                        "chunk_count": sentiment.chunk_count},
                          "linguistics": {"certainty_ratio": linguistics.certainty_ratio,
                                          "hedge_density": linguistics.hedge_density,
                                          "passive_voice_ratio": linguistics.passive_voice_ratio,
                                          "vague_language_score": linguistics.vague_language_score,
                                          "word_count": linguistics.word_count,
                                          "avg_sentence_length": linguistics.avg_sentence_length},
                          "scores": {"management_confidence_index": mci, "deception_risk_score": drs},
                          "guidance": {"guidance_score": gs, "fls_sentence_count": guidance.fls_sentence_count,
                                       "fls_ratio": guidance.fls_ratio, "key_phrases": guidance.key_phrases},
                          "yoy": {"delta_mci": yoy.delta_mci, "delta_drs": yoy.delta_drs,
                                  "trend": yoy.trend, "interpretation": yoy.interpretation},
                          "qa_scores": {"management_confidence_index": qa_scores.management_confidence_index,
                                        "deception_risk_score": qa_scores.deception_risk_score}
                           if qa_scores else None,
                          "price_impact": price_impact, "earnings_surprises": earnings_surprises,
                          "sector": sector, "sector_bench": sector_bench, "history": history}
            pdf_bytes = generate_pdf(pdf_result)
            st.download_button(
                "Export PDF",
                data=pdf_bytes,
                file_name=f"{ticker}_{quarter}_earningssense.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception:
            pass

    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)

    # ── 4 KPI cards - 2+2 layout for readability ──────────────────────────────
    delta_str = f"QoQ: {delta_mci:+.1f} pts" if delta_mci is not None else "QoQ: -"
    ret_str   = f"{ret*100:+.2f}%" if ret is not None else "-"
    ret_color = c["green"] if (ret or 0) >= 0 else c["red"]

    row1a, row1b = st.columns(2)
    row2a, row2b = st.columns(2)

    def _kpi(col, label, value_html, sub, border_color):
        with col:
            st.markdown(
                f"<div class='es-kpi' style='border-left:3px solid {border_color};"
                f"text-align:left;margin-bottom:.5rem;'>"
                f"<div class='es-label'>{label}</div>"
                f"<div style='font-size:2.2rem;font-weight:700;letter-spacing:-1px;"
                f"line-height:1.1;'>{value_html}</div>"
                f"<div style='color:{c['muted']};font-size:.72rem;margin-top:.2rem;'>{sub}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    _kpi(row1a, "Management Confidence Index",
         f"<span style='color:{mci_color};'>{mci:.0f}</span><span style='font-size:1.1rem;color:{c['muted']};'>/100</span>",
         delta_str, mci_color)
    _kpi(row1b, "Deception Risk Score",
         f"<span style='color:{drs_color};'>{drs:.0f}</span><span style='font-size:1.1rem;color:{c['muted']};'>/100</span>",
         "Higher = more evasive language", drs_color)
    _kpi(row2a, "Guidance Score",
         f"<span style='color:{c['violet']};'>{gs:.0f}</span><span style='font-size:1.1rem;color:{c['muted']};'>/100</span>",
         "Forward-looking statement confidence", c["violet"])
    _kpi(row2b, "Next-Day Return",
         f"<span style='color:{ret_color};'>{ret_str}</span>",
         "Post-filing close-to-close", ret_color)

    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)

    # ── Sector benchmark + YoY banner ─────────────────────────────────────────
    sb = sector_bench
    if sb.get("count", 0) > 0:
        mci_diff = mci - sb["avg_mci"]
        drs_diff = drs - sb["avg_drs"]
        st.markdown(
            f"<div style='background:{c['surface']};border:1px solid {c['border']};"
            f"border-radius:6px;padding:.55rem 1rem;font-size:.8rem;color:{c['subtext']};"
            f"margin-bottom:.6rem;'>"
            f"<strong>Sector benchmark</strong> ({sector}, n={sb['count']}): "
            f"MCI <span style='color:{mci_color};'>{mci_diff:+.1f}</span> vs avg {sb['avg_mci']:.1f}"
            f"&nbsp;·&nbsp;"
            f"DRS <span style='color:{drs_color};'>{drs_diff:+.1f}</span> vs avg {sb['avg_drs']:.1f}"
            f"</div>",
            unsafe_allow_html=True,
        )

    yoy_data = yoy
    if yoy_data.trend and yoy_data.trend != "no_prior":
        tc = {"improving": c["green"], "deteriorating": c["red"],
              "stable": c["blue"], "mixed": c["amber"]}.get(yoy_data.trend, c["muted"])
        st.markdown(
            f"<div class='es-banner' style='background:{tc}14;border-color:{tc};'>"
            f"<strong style='color:{tc};'>QoQ: {html.escape(yoy_data.trend.upper())}</strong>"
            f" &nbsp;&mdash;&nbsp; {html.escape(yoy_data.interpretation)}</div>",
            unsafe_allow_html=True,
        )

    # ── Gauges + sentiment ────────────────────────────────────────────────────
    col_g, col_s = st.columns(2)
    with col_g:
        st.plotly_chart(confidence_gauges(mci, drs), use_container_width=True,
                        config={"displayModeBar": False})
    with col_s:
        st.plotly_chart(
            sentiment_bar(sentiment.positive, sentiment.negative, sentiment.neutral, ticker),
            use_container_width=True, config={"displayModeBar": False},
        )

    # ── Q&A split ─────────────────────────────────────────────────────────────
    if qa_scores:
        st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
        st.markdown(f"<div class='es-label'>Prepared remarks vs Q&A session</div>",
                    unsafe_allow_html=True)
        st.markdown(
            f"<div style='color:{c['muted']};font-size:.75rem;margin-bottom:.75rem;'>"
            f"Management language often becomes more hedged under analyst questioning. "
            f"Lower MCI or higher DRS in Q&amp;A = deflection signal.</div>",
            unsafe_allow_html=True,
        )
        mci_delta = qa_scores.management_confidence_index - mci
        drs_delta = qa_scores.deception_risk_score - drs
        qa_c1, qa_c2, qa_c3 = st.columns(3)
        with qa_c1:
            st.markdown(
                f"<div class='es-kpi'>"
                f"<div class='es-label'>Prepared MCI</div>"
                f"<div style='color:{c['blue']};font-size:1.8rem;font-weight:700;'>{mci:.0f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with qa_c2:
            qa_mci_c = c["green"] if qa_scores.management_confidence_index >= mci else c["red"]
            st.markdown(
                f"<div class='es-kpi'>"
                f"<div class='es-label'>Q&A MCI</div>"
                f"<div style='color:{qa_mci_c};font-size:1.8rem;font-weight:700;'>"
                f"{qa_scores.management_confidence_index:.0f}</div>"
                f"<div style='color:{c['muted']};font-size:.72rem;'>vs prepared: {mci_delta:+.1f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with qa_c3:
            qa_drs_c = c["red"] if qa_scores.deception_risk_score > drs else c["green"]
            st.markdown(
                f"<div class='es-kpi'>"
                f"<div class='es-label'>Q&A DRS</div>"
                f"<div style='color:{qa_drs_c};font-size:1.8rem;font-weight:700;'>"
                f"{qa_scores.deception_risk_score:.0f}</div>"
                f"<div style='color:{c['muted']};font-size:.72rem;'>vs prepared: {drs_delta:+.1f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Guidance phrases ──────────────────────────────────────────────────────
    kp = guidance.key_phrases
    if kp:
        st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
        st.markdown(f"<div class='es-label'>Key guidance phrases</div>",
                    unsafe_allow_html=True)
        for phrase in kp:
            st.markdown(
                f"<div style='background:{c['surface']};border-left:3px solid {c['violet']};"
                f"padding:.55rem 1rem;border-radius:4px;color:{c['subtext']};font-size:.84rem;"
                f"margin-bottom:.35rem;font-style:italic;'>"
                f"&ldquo;{html.escape(phrase)}&rdquo;</div>",
                unsafe_allow_html=True,
            )

    # ── Linguistic radar + price chart ────────────────────────────────────────
    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)

    col_r, col_p = st.columns(2)
    with col_r:
        ling_data = {
            "hedge_density":        linguistics.hedge_density,
            "certainty_ratio":      linguistics.certainty_ratio,
            "passive_voice_ratio":  linguistics.passive_voice_ratio,
            "vague_language_score": linguistics.vague_language_score,
        }
        st.plotly_chart(
            linguistic_radar(
                ling_data["hedge_density"], ling_data["certainty_ratio"],
                ling_data["passive_voice_ratio"], ling_data["vague_language_score"],
            ),
            use_container_width=True, config={"displayModeBar": False},
        )
        st.markdown(
            f"<div style='color:{c['muted']};font-size:.72rem;text-align:center;'>"
            f"{linguistics.word_count:,} words analyzed · "
            f"{sentiment.sentence_count} sentences · "
            f"{sentiment.chunk_count} FinBERT chunks</div>",
            unsafe_allow_html=True,
        )

    with col_p:
        pi_data      = price_impact
        price_series = pi_data.get("price_series", [])
        if price_series and report_date:
            st.plotly_chart(
                price_impact_chart(price_series, report_date, ticker, mci),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.markdown(f"<div class='es-label'>Post-earnings returns</div>",
                        unsafe_allow_html=True)
            for label, key in [
                ("Next Day", "next_day_return"),
                ("5-Day",    "five_day_return"),
                ("30-Day",   "thirty_day_return"),
            ]:
                val = pi_data.get(key)
                if val is not None:
                    col_r2 = c["green"] if val >= 0 else c["red"]
                    st.markdown(
                        f"<div class='es-kpi' style='margin-bottom:.5rem;'>"
                        f"<div class='es-label'>{label}</div>"
                        f"<div style='color:{col_r2};font-size:1.6rem;font-weight:700;'>"
                        f"{val*100:+.1f}%</div></div>",
                        unsafe_allow_html=True,
                    )

    # ── Multi-quarter trend ───────────────────────────────────────────────────
    if len(history) > 1:
        st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
        st.markdown(f"<div class='es-label'>Multi-quarter MCI / DRS trend</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(mci_trend_chart(history), use_container_width=True,
                        config={"displayModeBar": False})

    # ── EPS surprise chart (FMP only) ─────────────────────────────────────────
    if earnings_surprises:
        st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
        st.markdown(f"<div class='es-label'>EPS actual vs estimate</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(
            earnings_surprise_chart(earnings_surprises, ticker),
            use_container_width=True, config={"displayModeBar": False},
        )

    # ── Transcript snippet ────────────────────────────────────────────────────
    st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
    with st.expander(snippet_label):
        st.markdown(
            f"<div style='color:{c['subtext']};font-size:.82rem;line-height:1.7;'>"
            f"{html.escape(analysis_text[:800])}...</div>",
            unsafe_allow_html=True,
        )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown(
        f"<div class='es-footer'>"
        f"EarningsSense &nbsp;·&nbsp; Built by Elias Wächter<br>"
        f"FinBERT · Loughran-McDonald · SEC EDGAR · Streamlit"
        f"</div>",
        unsafe_allow_html=True,
    )

elif run_btn and not ticker_input:
    st.warning("Enter a ticker symbol to analyze.")
