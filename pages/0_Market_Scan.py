"""
EarningsSense - Market Scan

Automatically fetches the latest 10-Q for a default watchlist of mega-cap
tickers, runs FinBERT + linguistic analysis on each, and ranks them by
Deception Risk Score. No manual input required - opens ready to read.
"""

from __future__ import annotations
import html
import time
import streamlit as st

st.set_page_config(
    page_title="Market Scan - EarningsSense",
    layout="wide",
)

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
h1,h2,h3 { color: #f1f5f9 !important; }
.ticker-card {
    background: #1e293b; border: 1px solid #334155;
    border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 0.5rem;
}
.ticker-card:hover { border-color: #3b82f6; }
.flag-red   { color: #ef4444; font-weight: 700; }
.flag-green { color: #22c55e; font-weight: 700; }
.flag-amber { color: #f97316; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.title("Market Scan")
st.markdown("<div style='color:#94a3b8;margin-bottom:1.5rem;'>Latest 10-Q filings fetched live from SEC EDGAR and scored automatically. Ranked by Deception Risk Score - highest risk at top.</div>", unsafe_allow_html=True)

# ── Default ticker universe ───────────────────────────────────────────────────

DEFAULT_TICKERS = ["NVDA", "MSFT", "META", "AMZN", "GOOGL", "AAPL", "TSLA", "NFLX", "AMD", "ORCL"]

# Session state for ticker text (enables Load Watchlist to update the text area)
if "scan_ticker_text" not in st.session_state:
    st.session_state["scan_ticker_text"] = "\n".join(DEFAULT_TICKERS)

with st.sidebar:
    st.markdown("### Tickers to scan")
    st.text_area(
        "One per line or comma-separated",
        height=220,
        label_visibility="collapsed",
        key="scan_ticker_text",
    )
    tickers  = [t.strip().upper() for t in
                st.session_state["scan_ticker_text"].replace(",", "\n").splitlines()
                if t.strip()]
    run_scan = st.button("Run Scan", type="primary")

    st.markdown("---")
    st.markdown("<div style='color:#475569;font-size:0.75rem;'>Each ticker fetches the most recent 10-Q from SEC EDGAR, extracts the MD&A section, and runs FinBERT + Loughran-McDonald analysis.</div>", unsafe_allow_html=True)

    # Watchlist
    st.markdown("---")
    st.markdown("**Watchlist**")
    from src.db.database import init_db, get_watchlist, set_watchlist
    init_db()

    wl_col1, wl_col2 = st.columns(2)
    with wl_col1:
        if st.button("Save", help="Save current tickers as watchlist"):
            set_watchlist(tickers)
            st.success(f"Saved {len(tickers)}")
    with wl_col2:
        if st.button("Load", help="Load saved watchlist into scan list"):
            saved = get_watchlist()
            if saved:
                st.session_state["scan_ticker_text"] = "\n".join(saved)
                st.rerun()
            else:
                st.info("Watchlist is empty")

    saved_wl = get_watchlist()
    if saved_wl:
        st.markdown(
            f"<div style='color:#475569;font-size:.75rem;'>"
            f"{len(saved_wl)} saved: {', '.join(saved_wl[:6])}"
            f"{'...' if len(saved_wl) > 6 else ''}</div>",
            unsafe_allow_html=True,
        )

# ── Auto-run on first load ────────────────────────────────────────────────────

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
    st.session_state.scan_done = False

if run_scan or not st.session_state.scan_done:
    from src.data.edgar import fetch_filing_text
    from src.analysis.sentiment import analyze as analyze_sentiment
    from src.analysis.linguistics import extract as extract_linguistics
    from src.analysis.signals import compute_scores

    results = []
    errors  = []

    progress_bar = st.progress(0, text="Starting scan…")
    status_box   = st.empty()

    for i, ticker in enumerate(tickers):
        progress_bar.progress((i) / len(tickers), text=f"Scanning {ticker}… ({i+1}/{len(tickers)})")
        status_box.markdown(f"<div style='color:#64748b;font-size:.82rem;'>Fetching SEC EDGAR 10-Q for <b>{html.escape(ticker)}</b>...</div>", unsafe_allow_html=True)

        try:
            filing     = fetch_filing_text(ticker, use_cache=True)
            sentiment  = analyze_sentiment(filing["text"])
            linguistics = extract_linguistics(filing["text"])
            scores     = compute_scores(sentiment, linguistics)

            results.append({
                "ticker":       ticker,
                "company":      filing.get("company", ticker),
                "filing_date":  filing.get("filing_date", ""),
                "report_date":  filing.get("report_date", ""),
                "mci":          scores.management_confidence_index,
                "drs":          scores.deception_risk_score,
                "pos":          sentiment.positive,
                "neg":          sentiment.negative,
                "hedge":        linguistics.hedge_density,
                "certainty":    linguistics.certainty_ratio,
                "passive":      linguistics.passive_voice_ratio,
                "words":        linguistics.word_count,
            })
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})

        time.sleep(0.3)

    progress_bar.progress(1.0, text="Scan complete.")
    status_box.empty()

    # Sort by DRS descending (highest risk first)
    results.sort(key=lambda x: -x["drs"])
    st.session_state.scan_results = results
    st.session_state.scan_errors  = errors
    st.session_state.scan_done    = True

# ── Results table ─────────────────────────────────────────────────────────────

results = st.session_state.get("scan_results", [])
errors  = st.session_state.get("scan_errors", [])

if not results:
    st.info("Click **Run Scan** to start, or wait for the auto-scan to complete.")
    st.stop()

# Summary row
avg_mci = sum(r["mci"] for r in results) / len(results)
avg_drs = sum(r["drs"] for r in results) / len(results)
high_risk = [r for r in results if r["drs"] >= 25]
low_risk  = [r for r in results if r["mci"] >= 50]

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"<div style='text-align:center;'><div style='font-size:1.6rem;font-weight:700;color:#60a5fa;'>{len(results)}</div><div style='color:#64748b;font-size:.78rem;'>Tickers scanned</div></div>", unsafe_allow_html=True)
with c2:
    col = "#ef4444" if avg_drs >= 20 else "#f97316" if avg_drs >= 12 else "#22c55e"
    st.markdown(f"<div style='text-align:center;'><div style='font-size:1.6rem;font-weight:700;color:{col};'>{avg_drs:.1f}</div><div style='color:#64748b;font-size:.78rem;'>Avg Deception Risk</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div style='text-align:center;'><div style='font-size:1.6rem;font-weight:700;color:#f97316;'>{len(high_risk)}</div><div style='color:#64748b;font-size:.78rem;'>High-risk filings (DRS ≥ 25)</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown(f"<div style='text-align:center;'><div style='font-size:1.6rem;font-weight:700;color:#22c55e;'>{len(low_risk)}</div><div style='color:#64748b;font-size:.78rem;'>Confident filings (MCI ≥ 50)</div></div>", unsafe_allow_html=True)

st.markdown("---")
st.markdown("### Results - sorted by Deception Risk Score")

# Header row
cols = st.columns([1.2, 2.5, 1, 1, 1, 1, 1, 1.5])
for col, label in zip(cols, ["Ticker", "Company", "MCI", "DRS", "FB+", "Hedge", "Certainty", "Filed"]):
    col.markdown(f"<div style='color:#475569;font-size:.72rem;font-weight:600;text-transform:uppercase;'>{label}</div>", unsafe_allow_html=True)

st.markdown("<hr style='margin:.25rem 0 .5rem;border-color:#1e293b;'>", unsafe_allow_html=True)

for r in results:
    mci_color = "#22c55e" if r["mci"] >= 50 else ("#f97316" if r["mci"] >= 38 else "#ef4444")
    drs_color = "#ef4444" if r["drs"] >= 25 else ("#f97316" if r["drs"] >= 15 else "#22c55e")
    risk_badge = ""
    if r["drs"] >= 25:
        risk_badge = " [HIGH RISK]"
    elif r["mci"] >= 50:
        risk_badge = " [CONFIDENT]"

    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.2, 2.5, 1, 1, 1, 1, 1, 1.5])
    c1.markdown(f"**{r['ticker']}**{risk_badge}")
    c2.markdown(f"<div style='color:#94a3b8;font-size:.82rem;'>{r['company'][:28]}</div>", unsafe_allow_html=True)
    c3.markdown(f"<span style='color:{mci_color};font-weight:700;'>{r['mci']:.0f}</span>", unsafe_allow_html=True)
    c4.markdown(f"<span style='color:{drs_color};font-weight:700;'>{r['drs']:.0f}</span>", unsafe_allow_html=True)
    c5.markdown(f"<span style='color:#94a3b8;'>{r['pos']:.3f}</span>", unsafe_allow_html=True)
    c6.markdown(f"<span style='color:#94a3b8;'>{r['hedge']:.2f}</span>", unsafe_allow_html=True)
    c7.markdown(f"<span style='color:#94a3b8;'>{r['certainty']:.2f}</span>", unsafe_allow_html=True)
    c8.markdown(f"<span style='color:#475569;font-size:.78rem;'>{r['filing_date']}</span>", unsafe_allow_html=True)

# Errors
if errors:
    with st.expander(f"{len(errors)} ticker(s) failed"):
        for e in errors:
            st.markdown(f"<div style='color:#ef4444;font-size:.82rem;'>{html.escape(e['ticker'])}: {html.escape(str(e['error']))}</div>", unsafe_allow_html=True)

# ── Highlight box ─────────────────────────────────────────────────────────────

st.markdown("---")
if results:
    worst = results[0]   # highest DRS (already sorted)
    best  = max(results, key=lambda x: x["mci"])

    col_w, col_b = st.columns(2)
    with col_w:
        st.markdown(f"""
        <div style='background:#450a0a22;border:1px solid #ef444455;border-radius:12px;padding:1rem 1.25rem;'>
            <div style='color:#ef4444;font-size:.72rem;font-weight:700;text-transform:uppercase;margin-bottom:.4rem;'>Highest Risk</div>
            <div style='font-size:1.4rem;font-weight:700;'>{worst['ticker']}</div>
            <div style='color:#94a3b8;font-size:.82rem;margin-bottom:.5rem;'>{worst['company']}</div>
            <div style='color:#f87171;font-size:.85rem;'>DRS {worst['drs']:.0f} · Hedge density {worst['hedge']:.2f}/100w · Certainty {worst['certainty']:.2f}</div>
            <div style='color:#64748b;font-size:.75rem;margin-top:.3rem;'>Filed {worst['filing_date']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_b:
        st.markdown(f"""
        <div style='background:#14532d22;border:1px solid #22c55e55;border-radius:12px;padding:1rem 1.25rem;'>
            <div style='color:#22c55e;font-size:.72rem;font-weight:700;text-transform:uppercase;margin-bottom:.4rem;'>Most Confident</div>
            <div style='font-size:1.4rem;font-weight:700;'>{best['ticker']}</div>
            <div style='color:#94a3b8;font-size:.82rem;margin-bottom:.5rem;'>{best['company']}</div>
            <div style='color:#4ade80;font-size:.85rem;'>MCI {best['mci']:.0f} · Hedge density {best['hedge']:.2f}/100w · Certainty {best['certainty']:.2f}</div>
            <div style='color:#64748b;font-size:.75rem;margin-top:.3rem;'>Filed {best['filing_date']}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Sector overlay ────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### Sector breakdown")
st.markdown("<div style='color:#94a3b8;font-size:.82rem;margin-bottom:.75rem;'>Average MCI and DRS by GICS sector across scanned tickers. Highlights whether risk is company-specific or sector-wide.</div>", unsafe_allow_html=True)

from src.data.sectors import get_sector
from collections import defaultdict

sector_groups: dict[str, list] = defaultdict(list)
for r in results:
    sector = get_sector(r["ticker"])
    sector_groups[sector].append(r)

sector_summary = []
for sector, members in sector_groups.items():
    sector_summary.append({
        "sector":    sector,
        "tickers":   ", ".join(m["ticker"] for m in members),
        "count":     len(members),
        "avg_mci":   sum(m["mci"] for m in members) / len(members),
        "avg_drs":   sum(m["drs"] for m in members) / len(members),
        "avg_hedge": sum(m["hedge"] for m in members) / len(members),
        "max_drs":   max(m["drs"] for m in members),
        "members":   members,
    })

sector_summary.sort(key=lambda x: -x["avg_drs"])

# Header row
sh1, sh2, sh3, sh4, sh5, sh6 = st.columns([2.5, 3, 0.8, 0.8, 0.8, 0.8])
for col, label in zip([sh1, sh2, sh3, sh4, sh5, sh6], ["Sector", "Tickers", "Count", "Avg MCI", "Avg DRS", "Max DRS"]):
    col.markdown(f"<div style='color:#475569;font-size:.72rem;font-weight:600;text-transform:uppercase;'>{label}</div>", unsafe_allow_html=True)
st.markdown("<hr style='margin:.25rem 0 .5rem;border-color:#1e293b;'>", unsafe_allow_html=True)

for s in sector_summary:
    mci_color = "#22c55e" if s["avg_mci"] >= 50 else ("#f97316" if s["avg_mci"] >= 38 else "#ef4444")
    drs_color = "#ef4444" if s["avg_drs"] >= 25 else ("#f97316" if s["avg_drs"] >= 15 else "#22c55e")
    max_color = "#ef4444" if s["max_drs"] >= 25 else ("#f97316" if s["max_drs"] >= 15 else "#22c55e")

    sc1, sc2, sc3, sc4, sc5, sc6 = st.columns([2.5, 3, 0.8, 0.8, 0.8, 0.8])
    sc1.markdown(f"<span style='color:#e2e8f0;font-weight:600;font-size:.88rem;'>{s['sector']}</span>", unsafe_allow_html=True)
    sc2.markdown(f"<span style='color:#64748b;font-size:.82rem;'>{s['tickers']}</span>", unsafe_allow_html=True)
    sc3.markdown(f"<span style='color:#475569;font-size:.82rem;'>{s['count']}</span>", unsafe_allow_html=True)
    sc4.markdown(f"<span style='color:{mci_color};font-weight:700;'>{s['avg_mci']:.1f}</span>", unsafe_allow_html=True)
    sc5.markdown(f"<span style='color:{drs_color};font-weight:700;'>{s['avg_drs']:.1f}</span>", unsafe_allow_html=True)
    sc6.markdown(f"<span style='color:{max_color};font-weight:700;'>{s['max_drs']:.1f}</span>", unsafe_allow_html=True)

if sector_summary:
    top_sector = sector_summary[0]
    if top_sector["avg_drs"] >= 15:
        st.markdown(
            f"<div style='background:#450a0a22;border-left:3px solid #ef4444;padding:.6rem 1rem;border-radius:4px;color:#cbd5e1;font-size:.82rem;margin-top:.75rem;'>"
            f"<strong style='color:#ef4444;'>{top_sector['sector']}</strong> has the highest avg DRS at "
            f"<strong>{top_sector['avg_drs']:.1f}</strong> across {top_sector['count']} ticker(s) - "
            f"{top_sector['tickers']}. May indicate sector-wide hedging rather than company-specific risk."
            f"</div>",
            unsafe_allow_html=True,
        )
