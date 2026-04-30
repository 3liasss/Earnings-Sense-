"""
EarningsSense - Market Scan.
Fetches the latest 10-Q for a watchlist, runs the full pipeline,
ranks by Deception Risk Score. Highest risk at top.
"""
from __future__ import annotations

import html
import time

import streamlit as st

st.set_page_config(page_title="Market Scan - EarningsSense", layout="wide")

from src.ui.sidebar import render_sidebar_branding
from src.ui.theme   import base_css, C

render_sidebar_branding()
st.markdown(base_css(), unsafe_allow_html=True)

c = C()

st.title("Market Scan")
st.markdown(
    f"<div style='color:{c['subtext']};margin-bottom:1.25rem;'>"
    f"Fetches the latest 10-Q for each ticker from SEC EDGAR and scores it. "
    f"Ranked by Deception Risk Score - highest risk at top.</div>",
    unsafe_allow_html=True,
)

# ── Sidebar controls ──────────────────────────────────────────────────────────

DEFAULT_TICKERS = ["NVDA", "MSFT", "META", "AMZN", "GOOGL",
                   "AAPL", "TSLA", "NFLX", "AMD", "ORCL"]

if "scan_ticker_text" not in st.session_state:
    st.session_state["scan_ticker_text"] = "\n".join(DEFAULT_TICKERS)

with st.sidebar:
    st.markdown(
        f"<hr style='border:none;border-top:1px solid {c['border']};margin:.5rem 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='es-label'>Tickers to scan</div>", unsafe_allow_html=True)
    st.text_area(
        "tickers",
        height=200,
        label_visibility="collapsed",
        key="scan_ticker_text",
    )
    tickers  = [t.strip().upper() for t in
                st.session_state["scan_ticker_text"].replace(",", "\n").splitlines()
                if t.strip()]
    run_scan = st.button("Run Scan", type="primary", use_container_width=True)

    st.markdown(
        f"<div style='color:{c['muted']};font-size:.72rem;margin-top:.4rem;'>"
        f"Each ticker fetches the most recent 10-Q, extracts MD&amp;A, "
        f"and runs FinBERT + Loughran-McDonald.</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<hr style='border:none;border-top:1px solid {c['border']};margin:.75rem 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='es-label'>Watchlist</div>", unsafe_allow_html=True)
    from src.db.database import init_db, get_watchlist, set_watchlist
    init_db()

    wl1, wl2 = st.columns(2)
    with wl1:
        if st.button("Save", use_container_width=True, help="Save current tickers"):
            set_watchlist(tickers)
            st.success(f"Saved {len(tickers)}")
    with wl2:
        if st.button("Load", use_container_width=True, help="Load saved watchlist"):
            saved = get_watchlist()
            if saved:
                st.session_state["scan_ticker_text"] = "\n".join(saved)
                st.rerun()
            else:
                st.info("Watchlist is empty")

    saved_wl = get_watchlist()
    if saved_wl:
        st.markdown(
            f"<div style='color:{c['muted']};font-size:.72rem;'>"
            f"{len(saved_wl)} saved: {', '.join(saved_wl[:6])}"
            f"{'...' if len(saved_wl) > 6 else ''}</div>",
            unsafe_allow_html=True,
        )

# ── Scan execution ───────────────────────────────────────────────────────────

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
    st.session_state.scan_errors  = []

if run_scan:
    from src.data.edgar          import fetch_filing_text
    from src.analysis.sentiment  import analyze as analyze_sentiment
    from src.analysis.linguistics import extract as extract_linguistics
    from src.analysis.signals    import compute_scores

    results = []
    errors  = []

    prog   = st.progress(0, text="Starting scan...")
    status = st.empty()

    for i, ticker in enumerate(tickers):
        prog.progress(i / len(tickers), text=f"Scanning {ticker}... ({i+1}/{len(tickers)})")
        status.markdown(
            f"<div style='color:{c['muted']};font-size:.8rem;'>"
            f"Fetching SEC EDGAR 10-Q for <strong>{html.escape(ticker)}</strong>...</div>",
            unsafe_allow_html=True,
        )
        try:
            filing      = fetch_filing_text(ticker, use_cache=True)
            sentiment   = analyze_sentiment(filing["text"])
            linguistics = extract_linguistics(filing["text"])
            scores      = compute_scores(sentiment, linguistics)
            results.append({
                "ticker":      ticker,
                "company":     filing.get("company", ticker),
                "filing_date": filing.get("filing_date", ""),
                "report_date": filing.get("report_date", ""),
                "mci":         scores.management_confidence_index,
                "drs":         scores.deception_risk_score,
                "pos":         sentiment.positive,
                "neg":         sentiment.negative,
                "hedge":       linguistics.hedge_density,
                "certainty":   linguistics.certainty_ratio,
                "passive":     linguistics.passive_voice_ratio,
                "words":       linguistics.word_count,
            })
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})
        time.sleep(0.3)

    prog.progress(1.0, text="Scan complete.")
    status.empty()

    results.sort(key=lambda x: -x["drs"])
    st.session_state.scan_results = results
    st.session_state.scan_errors  = errors

# ── Results ───────────────────────────────────────────────────────────────────

results = st.session_state.get("scan_results", [])
errors  = st.session_state.get("scan_errors",  [])

if not results:
    st.markdown(
        f"<div style='background:{c['surface']};border:1px solid {c['border']};"
        f"border-radius:10px;padding:2rem;text-align:center;'>"
        f"<div style='font-size:2rem;margin-bottom:.5rem;'>📊</div>"
        f"<div style='color:{c['text']};font-weight:600;margin-bottom:.25rem;'>Ready to scan</div>"
        f"<div style='color:{c['muted']};font-size:.82rem;'>"
        f"Edit the ticker list in the sidebar, then click <strong>Run Scan</strong>.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.stop()

# Summary row
avg_mci   = sum(r["mci"] for r in results) / len(results)
avg_drs   = sum(r["drs"] for r in results) / len(results)
high_risk = [r for r in results if r["drs"] >= 25]
confident = [r for r in results if r["mci"] >= 50]

s1, s2, s3, s4 = st.columns(4)
for col, val, label, color in [
    (s1, len(results),    "Tickers scanned",          c["blue"]),
    (s2, f"{avg_drs:.1f}", "Avg deception risk",      c["red"]   if avg_drs >= 20 else (c["amber"] if avg_drs >= 12 else c["green"])),
    (s3, len(high_risk),  "High-risk filings (DRS≥25)", c["amber"]),
    (s4, len(confident),  "Confident (MCI≥50)",         c["green"]),
]:
    with col:
        st.markdown(
            f"<div class='es-kpi'>"
            f"<div class='es-label'>{label}</div>"
            f"<div style='color:{color};font-size:1.75rem;font-weight:700;'>{val}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
st.markdown(f"<div class='es-label'>Results - ranked by deception risk score</div>",
            unsafe_allow_html=True)

# Fetch MCI history once for all tickers (for sparklines)
from src.db.database import get_mci_history as _get_hist
from src.visualization.charts import sparkline as _sparkline
_history_map = {r["ticker"]: _get_hist(r["ticker"], limit=6) for r in results}

# Column header
cols = st.columns([1.2, 2.5, 1, 1, 1, 1, 1, 1.2, 1.3])
for col, label in zip(cols, ["Ticker", "Company", "MCI", "DRS",
                               "FB+", "Hedge", "Certainty", "MCI Trend", "Filed"]):
    col.markdown(
        f"<div style='color:{c['muted']};font-size:.68rem;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:.5px;'>{label}</div>",
        unsafe_allow_html=True,
    )
st.markdown(
    f"<hr style='border:none;border-top:1px solid {c['border']};margin:.2rem 0 .4rem;'>",
    unsafe_allow_html=True,
)

for r in results:
    mci_color = c["green"] if r["mci"] >= 50 else (c["amber"] if r["mci"] >= 38 else c["red"])
    drs_color = c["red"]   if r["drs"] >= 25 else (c["amber"] if r["drs"] >= 15 else c["green"])
    risk_cls  = "risk-high" if r["drs"] >= 25 else ("risk-medium" if r["drs"] >= 15 else "risk-low")

    # Wrap entire row in a styled div with left border
    border_color = (c["red"] if r["drs"] >= 25 else
                    c["amber"] if r["drs"] >= 15 else c["green"])

    st.markdown(
        f"<div style='border-left:3px solid {border_color};padding-left:.5rem;"
        f"margin-bottom:.1rem;'>",
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([1.2, 2.5, 1, 1, 1, 1, 1, 1.2, 1.3])
    c1.markdown(f"**{r['ticker']}**")
    c2.markdown(
        f"<span style='color:{c['subtext']};font-size:.82rem;'>{r['company'][:28]}</span>",
        unsafe_allow_html=True,
    )
    c3.markdown(f"<span style='color:{mci_color};font-weight:700;'>{r['mci']:.0f}</span>",
                unsafe_allow_html=True)
    c4.markdown(f"<span style='color:{drs_color};font-weight:700;'>{r['drs']:.0f}</span>",
                unsafe_allow_html=True)
    c5.markdown(f"<span style='color:{c['subtext']};'>{r['pos']:.3f}</span>",
                unsafe_allow_html=True)
    c6.markdown(f"<span style='color:{c['subtext']};'>{r['hedge']:.2f}</span>",
                unsafe_allow_html=True)
    c7.markdown(f"<span style='color:{c['subtext']};'>{r['certainty']:.2f}</span>",
                unsafe_allow_html=True)
    # Sparkline from DB history (oldest→newest MCI)
    _hist = _history_map.get(r["ticker"], [])
    _mci_vals = [h["mci"] for h in reversed(_hist)] if _hist else []
    _spark = _sparkline(_mci_vals) if len(_mci_vals) >= 2 else "─"
    c8.markdown(
        f"<span style='color:{mci_color};font-family:monospace;letter-spacing:1px;"
        f"font-size:.88rem;'>{_spark}</span>",
        unsafe_allow_html=True,
    )
    c9.markdown(
        f"<span style='color:{c['muted']};font-size:.78rem;'>{r['filing_date']}</span>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

if errors:
    with st.expander(f"{len(errors)} ticker(s) failed"):
        for e in errors:
            st.markdown(
                f"<div style='color:{c['red']};font-size:.82rem;'>"
                f"{html.escape(e['ticker'])}: {html.escape(str(e['error']))}</div>",
                unsafe_allow_html=True,
            )

# ── Highlight cards ───────────────────────────────────────────────────────────

st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)

worst = results[0]
best  = max(results, key=lambda x: x["mci"])

col_w, col_b = st.columns(2)
with col_w:
    st.markdown(
        f"<div class='es-card' style='border-left:3px solid {c['red']};'>"
        f"<div class='es-label' style='color:{c['red']};'>Highest risk</div>"
        f"<div style='font-size:1.4rem;font-weight:700;color:{c['text']};'>{worst['ticker']}</div>"
        f"<div style='color:{c['subtext']};font-size:.82rem;margin-bottom:.4rem;'>{worst['company']}</div>"
        f"<div style='color:{c['red']};font-size:.85rem;'>"
        f"DRS {worst['drs']:.0f} · Hedge {worst['hedge']:.2f}/100w · Certainty {worst['certainty']:.2f}"
        f"</div>"
        f"<div style='color:{c['muted']};font-size:.72rem;margin-top:.25rem;'>Filed {worst['filing_date']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
with col_b:
    st.markdown(
        f"<div class='es-card' style='border-left:3px solid {c['green']};'>"
        f"<div class='es-label' style='color:{c['green']};'>Most confident</div>"
        f"<div style='font-size:1.4rem;font-weight:700;color:{c['text']};'>{best['ticker']}</div>"
        f"<div style='color:{c['subtext']};font-size:.82rem;margin-bottom:.4rem;'>{best['company']}</div>"
        f"<div style='color:{c['green']};font-size:.85rem;'>"
        f"MCI {best['mci']:.0f} · Hedge {best['hedge']:.2f}/100w · Certainty {best['certainty']:.2f}"
        f"</div>"
        f"<div style='color:{c['muted']};font-size:.72rem;margin-top:.25rem;'>Filed {best['filing_date']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

# ── Sector breakdown ──────────────────────────────────────────────────────────

st.markdown(f"<hr class='es-section-rule'>", unsafe_allow_html=True)
st.markdown(f"<div class='es-label'>Sector breakdown</div>", unsafe_allow_html=True)
st.markdown(
    f"<div style='color:{c['muted']};font-size:.75rem;margin-bottom:.75rem;'>"
    f"Average MCI and DRS by GICS sector. High sector-wide DRS suggests "
    f"macro hedging rather than company-specific risk.</div>",
    unsafe_allow_html=True,
)

from src.data.sectors import get_sector
from collections import defaultdict

sector_groups: dict[str, list] = defaultdict(list)
for r in results:
    sector_groups[get_sector(r["ticker"])].append(r)

sector_summary = [
    {
        "sector":    s,
        "tickers":   ", ".join(m["ticker"] for m in members),
        "count":     len(members),
        "avg_mci":   sum(m["mci"]  for m in members) / len(members),
        "avg_drs":   sum(m["drs"]  for m in members) / len(members),
        "max_drs":   max(m["drs"]  for m in members),
    }
    for s, members in sector_groups.items()
]
sector_summary.sort(key=lambda x: -x["avg_drs"])

sh1, sh2, sh3, sh4, sh5, sh6 = st.columns([2.5, 3, 0.8, 0.8, 0.8, 0.8])
for col, label in zip([sh1, sh2, sh3, sh4, sh5, sh6],
                      ["Sector", "Tickers", "N", "Avg MCI", "Avg DRS", "Max DRS"]):
    col.markdown(
        f"<div style='color:{c['muted']};font-size:.68rem;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:.5px;'>{label}</div>",
        unsafe_allow_html=True,
    )
st.markdown(
    f"<hr style='border:none;border-top:1px solid {c['border']};margin:.2rem 0 .4rem;'>",
    unsafe_allow_html=True,
)

for s in sector_summary:
    mci_col = c["green"] if s["avg_mci"] >= 50 else (c["amber"] if s["avg_mci"] >= 38 else c["red"])
    drs_col = c["red"]   if s["avg_drs"] >= 25 else (c["amber"] if s["avg_drs"] >= 15 else c["green"])
    max_col = c["red"]   if s["max_drs"] >= 25 else (c["amber"] if s["max_drs"] >= 15 else c["green"])

    sc1, sc2, sc3, sc4, sc5, sc6 = st.columns([2.5, 3, 0.8, 0.8, 0.8, 0.8])
    sc1.markdown(f"<span style='color:{c['text']};font-weight:600;font-size:.88rem;'>{s['sector']}</span>",
                 unsafe_allow_html=True)
    sc2.markdown(f"<span style='color:{c['muted']};font-size:.8rem;'>{s['tickers']}</span>",
                 unsafe_allow_html=True)
    sc3.markdown(f"<span style='color:{c['muted']};font-size:.82rem;'>{s['count']}</span>",
                 unsafe_allow_html=True)
    sc4.markdown(f"<span style='color:{mci_col};font-weight:700;'>{s['avg_mci']:.1f}</span>",
                 unsafe_allow_html=True)
    sc5.markdown(f"<span style='color:{drs_col};font-weight:700;'>{s['avg_drs']:.1f}</span>",
                 unsafe_allow_html=True)
    sc6.markdown(f"<span style='color:{max_col};font-weight:700;'>{s['max_drs']:.1f}</span>",
                 unsafe_allow_html=True)

if sector_summary and sector_summary[0]["avg_drs"] >= 15:
    top = sector_summary[0]
    st.markdown(
        f"<div style='background:{c['red']}12;border-left:3px solid {c['red']};"
        f"padding:.6rem 1rem;border-radius:4px;color:{c['subtext']};font-size:.82rem;"
        f"margin-top:.75rem;'>"
        f"<strong style='color:{c['red']};'>{top['sector']}</strong> has the highest avg DRS "
        f"at <strong>{top['avg_drs']:.1f}</strong> across {top['count']} ticker(s) - "
        f"{top['tickers']}. May indicate sector-wide hedging.</div>",
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div class='es-footer'>"
    f"EarningsSense &nbsp;·&nbsp; Built by Elias Wächter<br>"
    f"FinBERT · Loughran-McDonald · SEC EDGAR · Streamlit"
    f"</div>",
    unsafe_allow_html=True,
)
