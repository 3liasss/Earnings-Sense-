# EarningsSense

NLP system for analysing earnings filings and scoring management language.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://earnings-sense.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

Hedge funds pay $50k-200k/year for services like RavenPack and AlphaSense that run NLP on earnings filings before the market opens. EarningsSense replicates the core methodology using public SEC filings and open-source models - no paid data.

---

## What it does

Pulls the MD&A section from any company's latest 10-Q or earnings call transcript, runs two analyses, and produces two scores:

**MCI - Management Confidence Index (0-100)**
How direct and confident management language sounds. Combines FinBERT sentiment with certainty ratio, hedge density, and passive voice.

**DRS - Deception Risk Score (0-100)**
How evasive or hedged the language is. High DRS means management is using a lot of "may", "subject to", "we believe", passive constructions, and vague qualifiers.

```
SEC EDGAR 10-Q  ->  FinBERT transformer  ->  Management Confidence Index
(free, public)      (ProsusAI/finbert)
                    Loughran-McDonald    ->  Deception Risk Score
                    linguistic engine
                    (hedge density,
                     certainty ratio,
                     passive voice,
                     vague language)

Earnings Call   ->  Same pipeline        ->  Prepared Remarks score
Transcript          + Q&A split               Q&A Session score (separate)
(FMP API)
```

---

## Hypothesis

Management language in SEC 10-Q filings contains information about future stock returns that isn't fully priced at the time of filing. Executives who hedge excessively, use passive voice to avoid accountability, and obscure guidance with vague language tend to precede negative post-earnings reactions. The signal comes from public filings available hours before the market processes them.

Based on Loughran & McDonald (2011), who showed finance-specific word lists predict returns better than general sentiment models, and Li (2010), who showed MD&A readability predicts future earnings.

---

## Results - Q3 2025

Filings from late October / November 2025. Next-day return is close-to-close from earnings date.

| Company | MCI | DRS | Hedge / 100w | Next-day return |
|---------|:---:|:---:|:------------:|:---------------:|
| GOOGL | 43.6 | 16.5 | 1.22 | +2.7% |
| MSFT | 42.8 | 2.2 | 0.13 | -2.9% |
| AMZN | 41.4 | 10.1 | 0.21 | +9.6% |
| AAPL | 38.9 | 6.6 | 0.06 | -0.4% |
| NVDA | 37.9 | 9.9 | 0.27 | -3.1% |
| TSLA | 36.5 | 8.7 | 0.49 | +2.3% |
| META | 23.0 | 34.8 | 2.88 | -11.3% |

META's DRS was 34.8 - more than 2x the next-highest. Hedge density of 2.88 per 100 words vs an average of 0.40 for the other six. Stock dropped 11.3% the next session (Oct 29 close $751.67 -> Oct 30 close $666.47).

The same pattern in Q3 2024: META DRS 34.8, stock dropped 4.1%.

The signal is not perfect. MSFT had the second-highest MCI in Q3 2025 and still dropped 2.9% because Azure guidance was mixed. Confident language doesn't override guidance disappointments.

---

## Features

**Live Analysis**
- Score any US-listed company from its latest 10-Q or earnings call transcript
- Transcripts: Q&A section scored separately - management language under analyst questioning tends to be more revealing than prepared remarks
- MCI/DRS gauges, FinBERT sentiment bar, linguistic radar chart
- Multi-quarter MCI/DRS trend chart (up to 8 quarters of history)
- Sector benchmark - how this company compares to others in the same sector
- Guidance Score from forward-looking statement analysis
- Key guidance phrases extracted and highlighted
- YoY delta - automatic trend vs prior quarter (Improving / Deteriorating / Stable / Mixed)
- EPS actual vs estimate chart (transcript mode, requires FMP key)
- Post-earnings price chart - 60-day window around earnings date
- PDF export

**Market Scan**
- Auto-scans a configurable watchlist on load
- Ranked by DRS - highest risk at top
- Sector breakdown showing avg MCI/DRS per GICS sector
- Watchlist save/load to SQLite

**Compare**
- Side-by-side analysis of two tickers
- Full metric table, dual gauges, sentiment bars, radar charts, key phrases
- Summary: which company has more confident language / lower deception risk

**Backtest** *(work in progress)*
- Signal validation across S&P 500 companies - still building this out

---

## Linguistic signals

| Signal | What it measures |
|--------|-----------------|
| Hedge density | Hedging phrases per 100 words - "we believe", "may", "subject to", "approximately" |
| Certainty ratio | Strong affirmatives / (hedges + 1) - "will deliver", "committed", "record" |
| Passive voice ratio | Fraction of sentences in passive voice - accountability-avoidance signal |
| Vague language score | Vague terms per 100 words - "various", "significant", "certain ongoing challenges" |
| FinBERT sentiment | Positive / negative / neutral from BERT fine-tuned on financial text |
| Guidance Score | Forward-looking statement confidence based on positive vs negative guidance language |

Academic basis: Loughran & McDonald (2011) *Journal of Finance*, Li (2010) *Journal of Accounting Research*, Araci (2019) *arXiv:1908.10063*

---

## Updates

**April 2025**
- Built full signal validation layer: Fama-MacBeth cross-sectional regression, AlphaScore composite portfolio (L/S 20%), IC decay curves, IC by sector and regime
- Added tone-shift features (delta MCI/DRS vs prior quarter) to the backtest engine
- Ridge regression and Random Forest with time-based train/test split
- 8-year historical data collection via EDGAR (65 S&P 500 tickers, up to 32 quarters each)
- Volatility target analysis (does evasive language predict post-earnings vol spikes?)

**March 2025**
- Added earnings call transcript analysis with Q&A vs prepared remarks split
- PDF export for full analysis reports
- Multi-quarter MCI/DRS trend chart and YoY delta classification
- Sector benchmarking against historical scans
- EPS actual vs estimate chart (FMP API)

**February 2025**
- Initial release: MCI and DRS scoring from SEC EDGAR 10-Q filings
- Market Scan page (auto-scan watchlist, sector breakdown)
- Live Analysis page (single ticker deep dive)
- Compare page (side-by-side two tickers)
- SQLite history and watchlist persistence

---

## Tech stack

| Layer | Technology |
|---|---|
| Language model | ProsusAI/finbert (HuggingFace Transformers + PyTorch) |
| Filing data | SEC EDGAR REST API - free, no key required |
| Transcript data | FinancialModelingPrep API - free tier (250 req/day) |
| Price data | Yahoo Finance HTTP API |
| Dashboard | Streamlit |
| Charts | Plotly (dark theme, interactive) |
| Database | SQLite |
| Statistics | NumPy, SciPy, statsmodels |
| ML | scikit-learn (Ridge, Random Forest) |

---

## Getting started

```bash
git clone https://github.com/3liasss/Earnings-Sense-.git
cd Earnings-Sense-
pip install -r requirements.txt
streamlit run app.py
```

First run downloads FinBERT (~440 MB) from HuggingFace. Cached after that.

**Optional - earnings call transcripts and EPS data:**

Create `.streamlit/secrets.toml`:
```toml
FMP_API_KEY = "your_free_key_here"
```

Free key at [financialmodelingprep.com](https://financialmodelingprep.com/developer/docs/). 250 requests/day on the free tier.

---

## Limitations

- **n is small.** The table above covers 7 companies for one quarter. Any correlation is directionally interesting but not statistically conclusive at this sample size.
- **10-Qs are lawyered.** The MD&A section is drafted and reviewed multiple times before filing. Transcripts tend to show more natural patterns, especially in Q&A.
- **Language is not fundamentals.** MSFT had the second-highest MCI in Q3 2025 and still dropped 2.9% because guidance was mixed. Confident language doesn't save a stock when the numbers disappoint.
- **No real-time data.** Filings are published after market close. This is a same-evening signal for next-day positioning, not a pre-earnings tool.
- **Not forward-tested.** Results were computed on historical data. The signal may not hold out-of-sample.

---

## Project structure

```
├── app.py
├── pages/
│   ├── 0_Market_Scan.py
│   ├── 1_Live_Analysis.py
│   ├── 2_Compare.py
│   └── 3_Backtest.py
├── scripts/
│   └── run_backtest.py
└── src/
    ├── data/
    │   ├── edgar.py
    │   ├── transcripts.py
    │   ├── prices.py
    │   └── sectors.py
    ├── analysis/
    │   ├── sentiment.py
    │   ├── linguistics.py
    │   ├── signals.py
    │   ├── guidance.py
    │   ├── backtest_engine.py
    │   ├── fama_macbeth.py
    │   └── portfolio.py
    ├── visualization/
    │   ├── charts.py
    │   └── report_pdf.py
    └── db/
        └── database.py
```

---

## License

MIT
