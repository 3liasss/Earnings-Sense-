# EarningsSense

**Institutional-grade earnings intelligence. Free. Open-source. No Bloomberg terminal required.**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://earnings-sense.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

Hedge funds pay $50k–200k/year for services like RavenPack and AlphaSense that run NLP on earnings filings before the market opens. EarningsSense replicates the core methodology using public SEC filings and open-source models — no paid data, no subscription, no gatekeeping.

---

## The idea

When a CFO says "we believe results may be subject to certain factors" instead of "we will hit $X", that's a signal. When management uses passive voice to avoid accountability, hedges every forward statement, and buries guidance in vague qualifiers — that pattern shows up in the language before it shows up in the stock price.

Wall Street has been quantifying this for years. Now you can too.

---

## Two scores. One filing. Minutes after it drops.

**MCI — Management Confidence Index (0–100)**
How direct and confident the language sounds. Combines FinBERT sentiment with certainty ratio, hedge density, and passive voice avoidance. Higher = management is speaking with conviction.

**DRS — Deception Risk Score (0–100)**
How evasive or hedged the language is. High DRS = lots of "may", "subject to", "we believe", passive constructions, vague qualifiers. The language of a company that knows something you don't.

```
SEC EDGAR 10-Q  ──▶  FinBERT transformer  ──▶  Management Confidence Index
(free, public)        (ProsusAI/finbert)
                      Loughran-McDonald    ──▶  Deception Risk Score
                      linguistic engine
                      (hedge density · certainty ratio · passive voice · vague language)

Earnings Call   ──▶  Same pipeline        ──▶  Prepared Remarks score
Transcript            + Q&A split         ──▶  Q&A Session score (deflection detection)
(FMP API)
```

---

## Q3 2025 — what the scores said

Filings from late October / November 2025. Next-day return is close-to-close from the earnings date.

| Company | MCI | DRS | Hedge / 100w | Next-day |
|---------|:---:|:---:|:------------:|:--------:|
| GOOGL | 43.6 | 16.5 | 1.22 | +2.7% |
| MSFT  | 42.8 |  2.2 | 0.13 | -2.9% |
| AMZN  | 41.4 | 10.1 | 0.21 | +9.6% |
| AAPL  | 38.9 |  6.6 | 0.06 | -0.4% |
| NVDA  | 37.9 |  9.9 | 0.27 | -3.1% |
| TSLA  | 36.5 |  8.7 | 0.49 | +2.3% |
| META  | 23.0 | **34.8** | **2.88** | **-11.3%** |

META's DRS was 34.8 — more than 2× the next-highest. Hedge density of 2.88 per 100 words vs an average of 0.40 for the rest. Stock dropped 11.3% the next session.

The signal is not a crystal ball. MSFT had strong MCI and still dropped 2.9% — confident language doesn't override guidance misses. But evasive language before a miss? That pattern keeps showing up.

---

## What's in the app

**Live Analysis**
Score any US-listed company from its latest 10-Q the moment it hits EDGAR. Or use an earnings call transcript (Q&A scored separately — analyst questioning tends to reveal more than scripted remarks). Includes sector benchmark, QoQ trend, proactive signal flags, guidance phrase extraction, and PDF export.

**Market Scan**
Score and rank a full watchlist by Deception Risk Score. MCI sparklines show trend direction at a glance. Sector breakdown reveals whether risk is company-specific or sector-wide hedging.

**Compare**
Side-by-side NLP analysis of two tickers. Overlaid linguistic radar chart shows exactly where the language profiles diverge.

---

## Linguistic signals

| Signal | What it measures |
|--------|-----------------|
| Hedge density | Hedging phrases per 100 words — "we believe", "may", "subject to", "approximately" |
| Certainty ratio | Strong affirmatives / (hedges + 1) — "will deliver", "committed", "record" |
| Passive voice ratio | Fraction of sentences in passive voice — accountability-avoidance signal |
| Vague language score | Vague terms per 100 words — "various", "significant", "certain ongoing challenges" |
| FinBERT sentiment | Positive / negative / neutral from BERT fine-tuned on financial text |
| Guidance Score | Forward-looking statement confidence based on positive vs negative guidance language |

Academic basis: Loughran & McDonald (2011) *Journal of Finance*, Li (2010) *Journal of Accounting Research*, Araci (2019) *arXiv:1908.10063*

---

## Updates

This project gets regular updates. Active development.

**May 2026**
- Dark / light theme with smooth transitions across all pages
- Proactive signal flags: HIGH DECEPTION RISK, TOP DRS IN SECTOR, MCI drop QoQ, high hedge density
- MCI sparkline column in Market Scan (DB-backed trend history)
- Dual-trace overlaid radar chart in Compare
- Filing calendar detects when companies file before the deadline
- Enter key support, URL param pre-fill (`?ticker=NVDA`), common typo correction
- Cache freshness indicator + force refresh in Live Analysis
- PDF export

**March 2025**
- Earnings call transcript analysis with Q&A vs prepared remarks split
- Multi-quarter MCI/DRS trend and YoY delta classification
- Sector benchmarking against historical scans
- EPS actual vs estimate chart (FMP API)

**February 2025**
- Initial release: MCI and DRS scoring from SEC EDGAR 10-Q filings
- Market Scan, Live Analysis, Compare pages
- SQLite history and watchlist persistence

---

## Tech stack

| Layer | Technology |
|---|---|
| Language model | ProsusAI/finbert (HuggingFace Transformers + PyTorch) |
| Filing data | SEC EDGAR REST API — free, no key required |
| Transcript data | FinancialModelingPrep API — free tier (250 req/day) |
| Price data | Yahoo Finance HTTP API |
| Dashboard | Streamlit |
| Charts | Plotly (interactive, dark/light theme) |
| Database | SQLite |
| Statistics | NumPy · SciPy · statsmodels |

---

## Getting started

```bash
git clone https://github.com/3liasss/Earnings-Sense-.git
cd Earnings-Sense-
pip install -r requirements.txt
streamlit run app.py
```

First run downloads FinBERT (~440 MB) from HuggingFace. Cached after that.

**Optional — earnings call transcripts and EPS data:**

Create `.streamlit/secrets.toml`:
```toml
FMP_API_KEY = "your_free_key_here"
```

Free key at [financialmodelingprep.com](https://financialmodelingprep.com/developer/docs/). 250 requests/day on the free tier.

---

## Limitations

- **Language is not fundamentals.** Confident language doesn't save a stock when the numbers disappoint. This is one signal, not a trading system.
- **10-Qs are lawyered.** The MD&A section is reviewed multiple times. Transcripts tend to show rawer patterns, especially in Q&A.
- **No real-time data.** Filings drop after market close. Same-evening signal for next-day positioning — not a pre-earnings tool.
- **Sample is small.** The Q3 table covers 7 companies. Directionally interesting, not statistically conclusive on its own.

---

## Project structure

```
├── app.py
├── pages/
│   ├── 0_Market_Scan.py
│   ├── 1_Live_Analysis.py
│   └── 2_Compare.py
└── src/
    ├── data/
    │   ├── edgar.py
    │   ├── transcripts.py
    │   ├── prices.py
    │   ├── sectors.py
    │   └── filing_calendar.py
    ├── analysis/
    │   ├── sentiment.py
    │   ├── linguistics.py
    │   ├── signals.py
    │   └── guidance.py
    ├── visualization/
    │   ├── charts.py
    │   └── report_pdf.py
    └── db/
        └── database.py
```

---

## License

MIT — use it, fork it, build on it.
