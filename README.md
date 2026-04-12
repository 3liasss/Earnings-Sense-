# EarningsSense

Institutional-grade earnings filing analysis for retail investors.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://earnings-sense.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

Hedge funds pay $50,000–$200,000/year for services like RavenPack and AlphaSense that run NLP on earnings filings before the market opens. EarningsSense replicates the core methodology using public SEC filings, open-source models, and zero paid data.

---

## What it does

Pulls the MD&A section from any company's latest 10-Q on SEC EDGAR (free, no API key), runs two analyses, and produces two scores:

**Management Confidence Index (MCI, 0–100)** — how direct and confident management language sounds. Combines FinBERT sentiment with certainty ratio, hedge density, and passive voice.

**Deception Risk Score (DRS, 0–100)** — risk signal for evasive or overly hedged language. High DRS means management is hedging heavily, using vague terms, and avoiding accountability.

```
SEC EDGAR 10-Q  -->  FinBERT transformer  -->  Management Confidence Index
(free, public)       (ProsusAI/finbert)
                     Loughran-McDonald   -->  Deception Risk Score
                     linguistic engine
                     (hedge density,
                      certainty ratio,
                      passive voice,
                      vague language)
```

The app also fetches the actual post-earnings stock return so you can see how the scores tracked price movement.

---

## Real results

Scores computed by running the pipeline on actual SEC EDGAR 10-Q filings. **All next-day returns independently verified** against historical close prices (stockanalysis.com, StatMuse).

### Q3 2025 filings

Earnings reported late October – November 2025. Next-day return = close on earnings date → close on following trading session.

| Company | MCI | DRS | Hedge / 100w | Next-day return | Verified |
|---------|:---:|:---:|:------------:|:---------------:|:--------:|
| GOOGL | 43.6 | 16.5 | 1.22 | +2.7% | ✓ +2.65% actual |
| MSFT | 42.8 | 2.2 | 0.13 | -2.9% | ✓ -2.92% actual |
| AMZN | 41.4 | 10.1 | 0.21 | **+9.6%** | ✓ +9.58% actual |
| AAPL | 38.9 | 6.6 | 0.06 | -0.4% | ✓ -0.38% actual |
| NVDA | 37.9 | 9.9 | 0.27 | -3.1% | ✓ -3.15% actual |
| TSLA | 36.5 | 8.7 | 0.49 | +2.3% | ✓ +2.28% actual |
| **META** | **23.0** | **34.8** | **2.88** | **-11.3%** | ✓ -11.33% actual |

**META's DRS was 34.8 — more than 2× the next-highest company.** Hedge density of 2.88 per 100 words vs. an average of 0.26 for the other six. The filing was loaded with "subject to", "we believe", "may", "uncertain" throughout sections where other filings were direct. The stock dropped 11.3% the following session (Oct 29 close $751.67 → Oct 30 close $666.47).

**The same pattern appeared in Q3 2024:** META's DRS was 34.8 again, and the stock dropped 4.1% (Oct 30 close $588.96 → Oct 31 close $564.86, verified via StatMuse).

**The signal is not perfect.** MSFT had the second-highest MCI in Q3 2025 and still dropped 2.9% — Q1 FY2026 Azure guidance came in mixed. In Q3 2024, MSFT dropped 6.05% (Oct 30 close $427.53 → Oct 31 close $401.65) despite strong underlying results. Confident language doesn't override guidance disappointments.

---

## Linguistic signals

| Signal | What it measures |
|--------|-----------------|
| Hedge density | Hedging phrases per 100 words — "we believe", "may", "subject to", "approximately" |
| Certainty ratio | Strong affirmatives / (hedges + 1) — "will deliver", "committed", "record" |
| Passive voice ratio | Fraction of sentences in passive voice — accountability-avoidance signal |
| Vague language score | Vague terms per 100 words — "various", "significant", "certain ongoing challenges" |
| FinBERT sentiment | Positive / negative / neutral from BERT fine-tuned on 10,000+ financial documents |

Academic basis: Loughran & McDonald (2011) *Journal of Finance*, Li (2010) *Journal of Accounting Research*, Araci (2019) *arXiv:1908.10063*

---

## Tech stack

| Layer | Technology |
|---|---|
| Language model | ProsusAI/finbert (HuggingFace Transformers + PyTorch) |
| Filing data | SEC EDGAR REST API — free, no key required |
| Price data | Yahoo Finance HTTP API |
| Dashboard | Streamlit |
| Charts | Plotly (dark theme, interactive) |
| Database | SQLite (MCI history, watchlist) |
| Statistics | NumPy + SciPy |
| Testing | pytest |

---

## Getting started

```bash
git clone https://github.com/3liasss/Earnings-Sense-.git
cd Earnings-Sense-
pip install -r requirements.txt
streamlit run app.py
```

First run downloads FinBERT (~440 MB) from HuggingFace Hub. Cached after that.

**Run a live analysis:**
1. Open `http://localhost:8501`
2. Go to Live Analysis
3. Enter any US ticker and hit Analyze

**Market Scan:**
- Loads the latest 10-Q for 10 default tickers on open
- Ranks by Deception Risk Score
- Flags high-risk filings automatically

---

## Limitations

Read this before drawing any conclusions:

- **n is small.** The table above covers 7 companies for one quarter. Any correlation observed is directionally interesting, not statistically conclusive. More data needed before making any trading claims.

- **FinBERT reads 10-Q filings, not earnings call transcripts.** 10-Qs are more legalistic. The model tends toward neutral — the linguistic signals (hedge density, passive voice) carry more weight than raw sentiment scores here.

- **Language is not fundamentals.** MSFT had the second-highest MCI in Q3 2025 and still dropped 2.9% because Azure guidance was mixed. In Q3 2024 MSFT dropped 6.05% for the same reason. Confident language does not save a stock when guidance disappoints.

- **TSLA is an outlier.** Moves are driven by delivery numbers and Musk commentary, not MD&A language. It consistently breaks the signal.

- **No real-time data.** SEC filings are published after market close. This is a same-evening signal for next-day positioning, not a pre-earnings tool.

- **Not forward-tested.** These results were computed on historical data. The signal may not hold out-of-sample.

---

## Project structure

```
earningssense/
├── app.py                      Streamlit entry point + landing page
├── requirements.txt
├── assets/
├── pages/
│   ├── 0_Market_Scan.py        Auto-scans default tickers on load
│   └── 1_Live_Analysis.py      Analyze any ticker in real time
└── src/
    ├── data/
    │   ├── edgar.py             SEC EDGAR 10-Q fetcher + MD&A extractor
    │   ├── prices.py            Post-earnings return calculator
    │   ├── filing_calendar.py   10-Q deadline tracker
    │   └── sectors.py           Sector classification
    ├── analysis/
    │   ├── sentiment.py         FinBERT chunked inference engine
    │   ├── linguistics.py       Hedge / certainty / passive / vague extractor
    │   ├── signals.py           MCI + DRS scoring
    │   └── guidance.py          Forward-looking statement detector
    ├── visualization/
    │   └── charts.py            Plotly chart builders
    └── db/
        └── database.py          SQLite MCI history store
```

---

## License

MIT
