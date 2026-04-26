# EarningsSense

Linguistic factor investing system for earnings-driven equity alpha.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://earnings-sense.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

Hedge funds pay $50,000–$200,000/year for services like RavenPack and AlphaSense that run NLP on earnings filings before the market opens. EarningsSense replicates the core methodology using public SEC filings, open-source models, and zero paid data — then goes further with institutional-grade signal validation.

---

## Hypothesis

> **Management language in SEC 10-Q filings contains systematic information about future stock returns that is not fully priced by the market at the time of filing.**

Specifically: executives who hedge excessively, use passive voice to avoid accountability, and obscure guidance with vague language tend to precede negative post-earnings price reactions. This is the linguistic equivalent of insider tone — detectable from public filings, hours before the market processes it.

The signal is grounded in academic finance. Loughran & McDonald (2011) showed that standard sentiment lexicons misclassify financial language and that financial-specific word lists predict returns. Li (2010) showed that MD&A readability predicts future earnings. We operationalise both into a real-time scoring system with two outputs:

**MCI — Management Confidence Index (0–100)**
Confident, direct, forward-committed language → high MCI. Hedged, passive, evasive language → low MCI.

**DRS — Deception Risk Score (0–100)**
High hedge density + passive voice + vague language + negative FinBERT → high DRS.

---

## Signal Construction

```
SEC EDGAR 10-Q  ──►  MD&A section extraction
(free, public)        (BeautifulSoup + section header regex)
                          │
                          ▼
                 FinBERT chunked inference     ──►  positive / negative / neutral
                 (ProsusAI/finbert)
                          │
                 Loughran-McDonald engine      ──►  hedge_density
                 (financial word lists)              certainty_ratio
                                                     passive_voice_ratio
                                                     vague_language_score
                          │
                          ▼
         MCI = pos×40 + certainty×25 + (1−hedge)×20 + (1−passive)×15
         DRS = hedge×40 + passive×30 + neg×20 + vague×10
                          │
                          ▼
         Yahoo Finance prices  ──►  +1d / +5d / +30d post-earnings returns
```

Earnings call transcripts run the same pipeline, with Q&A section scored separately — management language under analyst questioning tends to be more revealing than prepared remarks.

---

## Signal Validation (Layer 2)

Built April 2025. Validated across 500+ 10-Q filings from 65 S&P 500 companies spanning up to 8 years of data (2015–2026).

### Fama-MacBeth Factor Test

Each quarter, cross-sectional regression: `return_it = β1·z(MCI) + β2·z(DRS) + β3·z(ΔMCI) + β4·z(ΔDRS) + ε`

Average betas over time with Newey-West standard errors. Tests whether MCI/DRS are **priced factors** — not just correlated with returns in one period, but consistently so across time. `|t| > 1.96` = statistically significant.

### AlphaScore Composite Portfolio

`AlphaScore = z(MCI) − 0.5·z(DRS) + z(ΔMCI) − 0.5·z(ΔDRS)`

Signals z-scored cross-sectionally within each quarter. Long top 20% / short bottom 20% by AlphaScore each quarter. Performance tracked with annualised Sharpe, max drawdown, Calmar ratio, and turnover.

### IC Decay Curves

IC computed at 1d, 5d, and 30d horizons. Measures whether the signal's predictive power decays quickly (noise) or persists (structural).

### Regime & Sector Breakdown

IC split by bull/bear/high-vol/low-vol regimes and by GICS sector. Identifies where the signal works best and controls for sector-wide hedging patterns.

---

## Real Results — Q3 2025 (Oct–Nov 2025 filings)

| Company | MCI | DRS | Hedge / 100w | Next-day return |
|---------|:---:|:---:|:------------:|:---------------:|
| GOOGL | 43.6 | 16.5 | 1.22 | +2.7% |
| MSFT | 42.8 | 2.2 | 0.13 | -2.9% |
| AMZN | 41.4 | 10.1 | 0.21 | **+9.6%** |
| AAPL | 38.9 | 6.6 | 0.06 | -0.4% |
| NVDA | 37.9 | 9.9 | 0.27 | -3.1% |
| TSLA | 36.5 | 8.7 | 0.49 | +2.3% |
| **META** | **23.0** | **34.8** | **2.88** | **-11.3%** |

META's DRS was 34.8 — more than 2× the next-highest company. Hedge density of 2.88 per 100 words vs an average of 0.40 for the other six. The filing was saturated with "subject to", "we believe", "may", "uncertain" in sections where other filings were direct. Stock dropped 11.3% the following session.

The same pattern held in Q3 2024: META DRS 34.8 again, stock dropped 4.1%.

**The signal is not perfect.** MSFT had the second-highest MCI in Q3 2025 and still dropped 2.9% — Azure guidance was mixed. Confident language does not override guidance disappointments.

---

## Features

### Live Analysis
- Score any US-listed company from its latest **10-Q filing** or **earnings call transcript**
- Transcripts: **Q&A section scored separately** — reveals evasion under analyst pressure
- **MCI/DRS gauges**, FinBERT sentiment bar, linguistic radar chart
- **Multi-quarter trend chart** — see how tone has shifted over up to 8 quarters
- **Sector benchmark** — vs average of all previously scanned companies in same sector
- **Guidance Score** (0–100) from forward-looking statement analysis
- **Key guidance phrases** — notable forward-looking sentences extracted and highlighted
- **YoY delta** — automatic trend classification (Improving / Deteriorating / Stable / Mixed)
- **EPS actual vs. estimate chart** (transcript mode with FMP key)
- **Post-earnings price chart** — 60-day window centred on earnings date
- **PDF export** — full report download

### Market Scan
- Auto-scans configurable watchlist on load, no manual trigger needed
- Ranked by DRS — highest risk at top
- Summary: avg DRS, high-risk count, confident-filing count
- **Sector breakdown** — avg MCI/DRS per GICS sector across the scan
- Watchlist save/load to SQLite

### Compare
- Side-by-side full analysis of two tickers
- Full metric table, dual gauges, sentiment bars, radar charts, guidance phrases
- Summary callout: which company has more confident language / lower deception risk

### Backtest & Signal Validation
- **IC / ICIR** (1d + 5d) per quarter — Spearman rank correlation between signal and return
- **Tone-shift IC** — ΔMCI / ΔDRS vs prior quarter, tests if changes beat levels
- **Volatility target** — does evasive language predict post-earnings vol spikes?
- **Long-short simulation** — quarterly L/S tercile equity curve and Sharpe
- **Fama-MacBeth regression** — cross-sectional betas + t-stats (priced factor test)
- **AlphaScore portfolio** — composite L/S 20% with drawdown, Calmar, turnover
- **IC decay curves** — signal persistence from 1d → 5d → 30d
- **IC by sector** — where does the signal work?
- **IC by regime** — bull / bear / high-vol / low-vol breakdown
- **OLS regression** — MCI/DRS coefficient significance with R²
- **Ridge + Random Forest** — out-of-sample R², feature importance ranking
- Raw data table (all scored filings)

---

## Linguistic Signals

| Signal | What it measures | High value means |
|--------|-----------------|-----------------|
| Hedge density | Hedging phrases per 100 words | Management uncertain, covering downside |
| Certainty ratio | Certainty words / (hedges + 1) | Management committed and direct |
| Passive voice ratio | Passive sentences / total sentences | Avoiding accountability |
| Vague language score | Vague terms per 100 words | Obscuring specifics |
| FinBERT sentiment | Positive / negative / neutral probability | Overall tone from finance-trained model |
| Guidance Score | Positive vs negative forward-looking language | Optimistic / pessimistic about future |

**Academic basis:**
- Loughran & McDonald (2011) — *Journal of Finance* — financial-specific word lists predict returns
- Li (2010) — *Journal of Accounting Research* — MD&A readability predicts earnings
- Araci (2019) — *arXiv:1908.10063* — FinBERT: financial sentiment analysis with BERT
- Fama & MacBeth (1973) — *Journal of Political Economy* — cross-sectional factor pricing

---

## Architecture

```
┌─────────────────────────────────┐
│   DATA INGESTION                │
│   EDGAR / FMP / Yahoo / SQLite  │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│   NLP FEATURE ENGINE            │
│   FinBERT + Loughran-McDonald   │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐  Layer 1
│   SIGNAL LAYER                  │  Alpha Engine
│   MCI / DRS / ΔMCI / ΔDRS      │
│   Guidance Score / Tone-shift   │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐  Layer 1
│   BACKTEST ENGINE               │
│   IC, ICIR, L/S, Ridge, RF      │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐  Layer 2
│   FACTOR VALIDATION             │  Institutional Proof
│   Fama-MacBeth / AlphaScore     │
│   IC decay / Sector / Regime    │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│   REPORTING                     │
│   Streamlit / PDF / Rankings    │
└─────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language model | ProsusAI/finbert (HuggingFace Transformers + PyTorch) |
| Word lists | Loughran-McDonald Financial Sentiment Dictionary |
| Filing data | SEC EDGAR REST API — free, no key required |
| Transcript data | FinancialModelingPrep API — free tier (250 req/day) |
| Price data | Yahoo Finance HTTP API — no library, direct requests |
| Dashboard | Streamlit multi-page app |
| Charts | Plotly (dark theme, interactive) |
| Database | SQLite — MCI/DRS history, watchlist, sector benchmarks |
| Statistics | NumPy, SciPy, statsmodels (OLS, Fama-MacBeth) |
| ML | scikit-learn (RidgeCV, RandomForest, StandardScaler) |
| PDF export | reportlab |

---

## Project Structure

```
├── app.py                          Landing page + navigation
├── requirements.txt
├── pages/
│   ├── 0_Market_Scan.py            Auto-scan + sector breakdown + watchlist
│   ├── 1_Live_Analysis.py          Single-ticker deep analysis + PDF export
│   ├── 2_Compare.py                Side-by-side two-ticker comparison
│   └── 3_Backtest.py               Full signal validation dashboard (Layer 1 + 2)
├── scripts/
│   └── run_backtest.py             65-ticker 8-year batch data collection script
└── src/
    ├── data/
    │   ├── edgar.py                SEC EDGAR fetcher + MD&A extractor
    │   ├── transcripts.py          FMP transcript fetcher + EPS surprise data
    │   ├── prices.py               Post-earnings return calculator (Yahoo Finance)
    │   └── sectors.py              GICS sector classification (200+ tickers)
    ├── analysis/
    │   ├── sentiment.py            FinBERT chunked inference
    │   ├── linguistics.py          Hedge / certainty / passive / vague extractor
    │   ├── signals.py              MCI + DRS formula
    │   ├── guidance.py             Forward-looking statement detector + YoY delta
    │   ├── backtest_engine.py      Full Layer 1+2 metrics engine
    │   ├── fama_macbeth.py         Fama-MacBeth cross-sectional regression
    │   └── portfolio.py            AlphaScore portfolio + IC decay/sector/regime
    ├── visualization/
    │   ├── charts.py               Plotly chart builders
    │   └── report_pdf.py           PDF report generator (reportlab)
    └── db/
        └── database.py             SQLite store
```

---

## Getting Started

```bash
git clone https://github.com/3liasss/Earnings-Sense-.git
cd Earnings-Sense-
pip install -r requirements.txt
streamlit run app.py
```

First run downloads FinBERT (~440 MB) from HuggingFace. Cached after that.

**Optional — earnings call transcripts + EPS data:**

```toml
# .streamlit/secrets.toml
FMP_API_KEY = "your_free_key_here"
```

Free key at [financialmodelingprep.com](https://financialmodelingprep.com/developer/docs/). 250 requests/day on the free tier.

**Run the full backtest (65 tickers × 8 years):**

```bash
python scripts/run_backtest.py
# Takes 30-60 min. Safe to interrupt — cached per filing.
# Results saved to data/backtest/results.csv + metrics.json
```

---

## Limitations

- **Sample size.** Statistical significance requires 500+ observations. At fewer observations, IC and FM t-stats are directionally interesting but not conclusive. The full 8-year backtest provides the necessary depth.
- **10-Qs are lawyered.** MD&A is reviewed multiple times before filing. Earnings call transcripts (especially Q&A) reveal more natural hedging patterns.
- **Language ≠ fundamentals.** A confident filing does not override guidance disappointments or macro headwinds. The signal is one input, not a trading system.
- **No real-time data.** Filings are published after market close. This is a post-close signal for next-session positioning.
- **No transaction costs modelled.** The backtest does not include bid-ask spread, market impact, or borrowing costs for short positions.

---

## License

MIT
