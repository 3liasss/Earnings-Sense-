"""
EarningsSense - Full research-grade backtest runner.

Fetches up to 32 quarters (~8 years) of 10-Q filings for S&P 500
companies, scores each using the linguistic engine, fetches post-earnings
price returns from Yahoo Finance, and saves:

    data/backtest/results.csv    - raw per-filing results
    data/backtest/metrics.json   - computed signal quality metrics

Run from project root:
    python scripts/run_backtest.py [--tickers ...] [--quarters N]

Default: 65 tickers, 32 quarters each (~8 years back).
Respects EDGAR rate limits (0.4s between requests).
Cached per filing - safe to interrupt and resume.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.edgar import (
    get_cik, get_all_10q_filings, _find_document_url, _extract_mda, _get,
)
from src.analysis.linguistics import extract as extract_linguistics
from src.analysis.signals     import compute_scores
from src.data.prices          import fetch_price_impact


# ── Ticker universe ────────────────────────────────────────────────────────────

SP500_UNIVERSE = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA",
    # Large-cap tech
    "NFLX", "AMD", "ORCL", "CRM", "ADBE", "INTC", "QCOM", "TXN",
    "AVGO", "IBM", "AMAT", "NOW", "PANW",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "AXP", "USB", "PNC",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "BMY", "CVS",
    # Consumer staples
    "PG", "KO", "PEP", "WMT", "COST",
    # Consumer discretionary
    "HD", "MCD", "NKE", "SBUX", "TGT", "F", "GM",
    # Industrials
    "CAT", "BA", "HON", "GE", "RTX", "UPS", "LMT", "DE",
    # Energy
    "XOM", "CVX", "COP", "EOG",
    # Communication
    "T", "VZ", "DIS", "CMCSA",
    # Materials / Utilities / RE
    "LIN", "NEE", "AMT",
]

# ── Neutral sentiment stub (no FinBERT dependency) ────────────────────────────

@dataclass
class NeutralSentiment:
    positive: float = 0.33
    negative: float = 0.33
    neutral:  float = 0.34
    sentence_count: int = 0
    chunk_count:    int = 0


# ── Caching ───────────────────────────────────────────────────────────────────

CACHE_DIR = Path("data/backtest/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _score_filing(cik: str, ticker: str, filing: dict) -> dict | None:
    report_date = filing["report_date"]
    cache_path  = CACHE_DIR / f"{ticker}_{report_date}.json"

    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except Exception:
            pass

    try:
        doc_url = _find_document_url(
            cik, filing["accession_number"], filing.get("primary_document")
        )
        if not doc_url:
            return None

        html     = _get(doc_url).text
        mda_text = _extract_mda(html)
        if len(mda_text.split()) < 150:
            return None

        ling   = extract_linguistics(mda_text)
        scores = compute_scores(NeutralSentiment(), ling)

        y, m    = report_date[:4], report_date[5:7]
        quarter = f"{y}-Q{(int(m)-1)//3 + 1}"

        price_data = {}
        price_series = []
        try:
            price_data   = fetch_price_impact(ticker, report_date)
            price_series = price_data.get("price_series", [])
        except Exception:
            pass

        record = {
            "ticker":               ticker,
            "quarter":              quarter,
            "report_date":          report_date,
            "filing_date":          filing.get("filing_date", ""),
            "mci":                  scores.management_confidence_index,
            "drs":                  scores.deception_risk_score,
            "hedge_density":        round(ling.hedge_density, 4),
            "certainty_ratio":      round(ling.certainty_ratio, 4),
            "passive_voice_ratio":  round(ling.passive_voice_ratio, 4),
            "vague_language_score": round(ling.vague_language_score, 4),
            "word_count":           ling.word_count,
            "next_day_return":      price_data.get("next_day_return"),
            "five_day_return":      price_data.get("five_day_return"),
            "thirty_day_return":    price_data.get("thirty_day_return"),
            "price_series":         price_series,
        }
        cache_path.write_text(json.dumps(record, indent=2))
        return record

    except Exception as e:
        print(f"  [skip] {ticker} {report_date}: {e}", flush=True)
        return None


def _process_ticker(ticker: str, n_quarters: int) -> list[dict]:
    results = []
    try:
        cik     = get_cik(ticker)
        filings = get_all_10q_filings(cik, max_quarters=n_quarters)
        if not filings:
            return []
        for filing in filings:
            record = _score_filing(cik, ticker, filing)
            if record:
                results.append(record)
            time.sleep(0.4)
    except Exception as e:
        print(f"[error] {ticker}: {e}", flush=True)
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def run(tickers: list[str], n_quarters: int = 32) -> pd.DataFrame:
    print(f"\n{'='*60}")
    print(f"EarningsSense Research Backtest")
    print(f"Tickers: {len(tickers)}  |  Max quarters: {n_quarters} (~{n_quarters//4} years)")
    print(f"{'='*60}\n")

    all_records: list[dict] = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i:>3}/{len(tickers)}] {ticker}", flush=True)
        records = _process_ticker(ticker, n_quarters)
        all_records.extend(records)
        scored = sum(1 for r in records if r.get("next_day_return") is not None)
        print(f"         -> {len(records)} quarters, {scored} with returns", flush=True)

    return pd.DataFrame(all_records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers",  nargs="+", default=None)
    parser.add_argument("--quarters", type=int,  default=32)
    args    = parser.parse_args()
    tickers = args.tickers or SP500_UNIVERSE

    df = run(tickers, n_quarters=args.quarters)
    if df.empty:
        print("\nNo data collected.")
        return

    out_dir = Path("data/backtest")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save without price_series (keeps CSV clean)
    csv_cols = [c for c in df.columns if c != "price_series"]
    df[csv_cols].to_csv(out_dir / "results.csv", index=False)
    print(f"\nSaved {len(df)} records -> data/backtest/results.csv")

    df_v = df.dropna(subset=["mci", "drs", "next_day_return"])
    print(f"Valid observations (with 1d return): {len(df_v)}")

    if len(df_v) >= 10:
        from src.analysis.backtest_engine import compute_metrics
        m = compute_metrics(df_v)

        m_dict = {k: v for k, v in vars(m).items()}
        (out_dir / "metrics.json").write_text(json.dumps(m_dict, indent=2, default=str))

        print(f"\n{'='*60}")
        print("BACKTEST RESULTS")
        print(f"{'='*60}")
        print(f"Observations : {m.n_obs}  |  Tickers: {m.n_tickers}  |  Quarters: {m.n_quarters}")
        print(f"Date range   : {m.date_range}")
        print()
        print(f"IC  (MCI, 1d) : {m.ic_mci_1d:+.4f}   ICIR: {m.icir_mci_1d:+.3f}")
        print(f"IC  (DRS, 1d) : {m.ic_drs_1d:+.4f}   ICIR: {m.icir_drs_1d:+.3f}")
        print(f"IC  (MCI, 5d) : {m.ic_mci_5d:+.4f}   ICIR: {m.icir_mci_5d:+.3f}")
        print(f"IC  (DRS, 5d) : {m.ic_drs_5d:+.4f}   ICIR: {m.icir_drs_5d:+.3f}")
        print()
        print(f"Tone-shift IC (ΔMCI, 1d) : {m.ic_dmci_1d:+.4f}")
        print(f"Tone-shift IC (ΔDRS, 1d) : {m.ic_ddrs_1d:+.4f}")
        print()
        print(f"Volatility IC (DRS) : {m.ic_drs_vol:+.4f}")
        print()
        print(f"L/S (1d)  mean: {m.ls_mean_1d*100:+.3f}%  hit: {m.ls_hit_1d:.1%}  Sharpe: {m.ls_sharpe_1d:.3f}")
        print(f"L/S (5d)  mean: {m.ls_mean_5d*100:+.3f}%  hit: {m.ls_hit_5d:.1%}  Sharpe: {m.ls_sharpe_5d:.3f}")
        print()
        print(f"Lag IC  DRS->t+1: {m.lag_ic_drs:+.4f}  p={m.lag_p_drs:.3f}")
        print()
        print(f"OLS  MCI: coef={m.ols_mci_coef:+.5f} p={m.ols_mci_pval:.3f}")
        print(f"OLS  DRS: coef={m.ols_drs_coef:+.5f} p={m.ols_drs_pval:.3f}")
        print(f"OLS  R²={m.ols_r2:.4f}")
        print()
        print(f"Ridge R² (1d): {m.ridge_r2_1d:.4f}  (5d): {m.ridge_r2_5d:.4f}")
        print(f"RF    R² (1d): {m.rf_r2_1d:.4f}  (5d): {m.rf_r2_5d:.4f}")
        if m.rf_importances:
            top = sorted(m.rf_importances.items(), key=lambda x: -x[1])[:4]
            print(f"Top RF features: {top}")
        print(f"{'='*60}")
        print(f"\nMetrics saved -> data/backtest/metrics.json")


if __name__ == "__main__":
    main()
