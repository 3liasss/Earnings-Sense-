# EarningsSense

Institutional-grade earnings call analysis for retail investors.

Hedge funds run NLP on earnings transcripts before the market opens. Services like RavenPack and AlphaSense charge $50,000-$200,000/year for this. EarningsSense replicates the core methodology using public SEC filings, open-source models, and zero paid data.

---

## What it does

Pulls the MD&A section from any company's latest 10-Q on SEC EDGAR (free, no API key), runs two analyses, and produces two scores:

**Management Confidence Index (MCI, 0-100)** - how direct and confident management language sounds. Combines FinBERT sentiment with certainty ratio and hedge density.

**Deception Risk Score (DRS, 0-100)** - risk signal for evasive or overly hedged language. High DRS means management is hedging heavily.

```
SEC EDGAR 10-Q  -->  FinBERT transformer  -->  Management Confidence Index
(free, public)       (ProsusAI/finbert)
                     Loughran-McDonald   -->  Deception Risk Score
                     linguistic engine
                     (hedge density,
                      certainty ratio,
                      passive voice)
```

The app also fetches the actual post-earnings stock return so you can see how the scores tracked price movement.

---

## Real results

Scores computed by running the pipeline on actual SEC EDGAR 10-Q filings. Returns from Yahoo Finance. Each row shows the most recent 10-Q available per company - calendar-year companies are Q3 2025 (Sep 30), MSFT and AAPL have Q2/Q1 FY2026 filings (Dec 2025).

| Company | Report date | MCI | DRS | Hedge density | Next-day return |
|---------|-------------|:---:|:---:|:-------------:|:---------------:|
| MSFT | Dec 2025 | 52.0 | 12.4 | 0.22 / 100w | -2.2% |
| GOOGL | Sep 2025 | 43.6 | 16.5 | 1.22 / 100w | +2.5% |
| AMZN | Sep 2025 | 41.4 | 10.1 | 0.21 / 100w | +9.6% |
| AAPL | Dec 2025 | 39.2 | 21.4 | 0.51 / 100w | -0.3% |
| NVDA | Sep 2025 | 37.9 | 9.9 | 0.27 / 100w | -3.1% |
| TSLA | Sep 2025 | 36.5 | 8.7 | 0.49 / 100w | +2.3% |
| **META** | **Sep 2025** | **23.0** | **34.8** | **2.88 / 100w** | **-11.3%** |

META's DRS was 34.8 - more than 2x the next-highest company. Hedge density of 2.88 per 100 words vs an average of 0.48 for the rest. The filing was loaded with "subject to", "we believe", "may", "uncertain" throughout sections where other filings were direct. The stock dropped 11.3% the following day.

The same pattern appeared in Q3 2024: META's DRS was 34.8 again, and it dropped 4.1%.

### MCI vs next-day return

![MCI vs Returns](assets/mci_vs_returns.png)

Pearson r = **+0.783** across 7 companies x 2 quarters (n=14 observations, historical backtest).

---

## Linguistic signals

| Signal | What it measures |
|--------|-----------------|
| Hedge density | Hedging phrases per 100 words - "we believe", "may", "subject to", "approximately" |
| Certainty ratio | Strong affirmatives / (hedges + 1) - "will deliver", "committed", "record" |
| Passive voice ratio | Fraction of sentences in passive voice - accountability-avoidance signal |
| Vague language score | Vague terms per 100 words - "various", "significant", "certain ongoing challenges" |
| FinBERT sentiment | Positive / negative / neutral from BERT fine-tuned on 10,000+ financial documents |

Academic basis: Loughran & McDonald (2011) *Journal of Finance*, Li (2010) *Journal of Accounting Research*, Araci (2019) *arXiv:1908.10063*

---

## Tech stack

| Layer | Technology |
|---|---|
| Language model | ProsusAI/finbert (HuggingFace Transformers + PyTorch) |
| Filing data | SEC EDGAR REST API - free, no key required |
| Price data | Yahoo Finance HTTP API |
| Dashboard | Streamlit |
| Charts | Plotly (dark theme, interactive) |
| Database | SQLite (mci_history, watchlist) |
| Statistics | NumPy + SciPy (Pearson r, t-distribution p-value) |
| Testing | pytest |

---

## Getting started

```bash
git clone https://github.com/3liasss/Earnings-Sense-.git
cd Earnings-Sense-
pip install -r requirements.txt
streamlit run app.py
```

First run downloads FinBERT (~440MB) from HuggingFace Hub. Cached after that.

**Run a live analysis:**
1. Open `http://localhost:8501`
2. Go to Live Analysis
3. Enter any ticker and hit Analyze

**Market Scan:**
- Loads the latest 10-Q for 10 default tickers on open
- Ranks by Deception Risk Score
- Flags high-risk filings automatically

---

## Limitations

Read this before drawing any conclusions:

- n is small. The backtest covers 7 companies across 2 quarters. Pearson r of 0.78 on n=14 is not statistically significant. More data needed before making any trading claims.

- FinBERT reads 10-Q filings, not earnings call transcripts. 10-Qs are more legalistic than calls. The model tends toward neutral - the linguistic signals carry more weight than raw sentiment scores here.

- Language is not fundamentals. MSFT had the highest MCI in Q3 2024 and still dropped 6% because Azure guidance missed. Confident language does not save a stock when the numbers disappoint.

- TSLA is an outlier. Moves are driven by delivery numbers and Musk commentary, not MD&A language. It consistently breaks the signal.

- No real-time data. SEC filings are published after market close. This is a same-evening signal for next-day positioning, not a pre-earnings tool.

- Not forward-tested. These results were computed on historical data. The signal may not hold out-of-sample.

---

## Project structure

```
earningssense/
- app.py                      Streamlit entry point
- requirements.txt
- assets/
  - mci_vs_returns.png        Correlation chart
- pages/
  - 0_Market_Scan.py          Auto-scans default tickers on load
  - 1_Live_Analysis.py        Analyze any ticker in real time
- src/
  - data/
    - edgar.py                SEC EDGAR 10-Q fetcher + MD&A extractor
    - prices.py               Post-earnings return calculator
  - analysis/
    - sentiment.py            FinBERT chunked inference engine
    - linguistics.py          Hedge/certainty/passive/vague extractor
    - signals.py              MCI + DRS scoring + backtest engine
  - visualization/
    - charts.py               Plotly chart builders
- tests/
  - test_analysis.py
```

---

## License

MIT
