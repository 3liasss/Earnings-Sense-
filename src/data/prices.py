"""
Stock price data fetcher using Yahoo Finance HTTP API (no yfinance dependency).

Computes post-earnings return metrics (next-day, 5-day, 30-day)
relative to the earnings date closing price.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import requests


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EarningsSense/1.0)",
    "Accept": "application/json",
}


def _fetch_yahoo(ticker: str, start: datetime, end: datetime) -> list[dict]:
    """Fetch daily close prices from Yahoo Finance chart API."""
    p1 = int(start.timestamp())
    p2 = int(end.timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?interval=1d&period1={p1}&period2={p2}&includeAdjustedClose=true"
    )
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    result_data = data.get("chart", {}).get("result")
    if not result_data:
        raise ValueError(f"No price data returned for {ticker}.")

    r = result_data[0]
    timestamps = r.get("timestamp", [])
    closes = r.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])

    if not timestamps or not closes:
        raise ValueError(f"Empty price series for {ticker}.")

    rows = []
    for ts, c in zip(timestamps, closes):
        if c is None:
            continue
        rows.append({
            "date": datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
            "close": round(float(c), 2),
        })
    return rows


def fetch_price_impact(ticker: str, earnings_date: str) -> dict:
    """
    Fetch daily OHLCV data and compute post-earnings price returns.

    Args:
        ticker:        Stock ticker symbol (e.g. "AAPL").
        earnings_date: Earnings date in "YYYY-MM-DD" format.

    Returns:
        dict with keys:
          - next_day_return   (float): (close[+1] - close[0]) / close[0]
          - five_day_return   (float): (close[+5] - close[0]) / close[0]
          - thirty_day_return (float): (close[+30] - close[0]) / close[0]
          - price_series      (list[dict]): [{date, close}, ...] for ~61 days
    """
    t0 = datetime.strptime(earnings_date, "%Y-%m-%d")
    start = t0 - timedelta(days=50)
    end   = t0 + timedelta(days=50)

    rows = _fetch_yahoo(ticker, start, end)
    if not rows:
        raise ValueError(f"No price data found for {ticker}.")

    # Find nearest trading day on or after earnings date
    earnings_idx: Optional[int] = None
    for i, row in enumerate(rows):
        if row["date"] >= earnings_date:
            earnings_idx = i
            break

    if earnings_idx is None:
        raise ValueError(f"No trading data on or after {earnings_date} for {ticker}.")

    earnings_close = rows[earnings_idx]["close"]

    def _return_at(offset: int) -> Optional[float]:
        target_idx = earnings_idx + offset
        if target_idx < len(rows):
            future_close = rows[target_idx]["close"]
            return round((future_close - earnings_close) / earnings_close, 4)
        return None

    # Window: 30 before through 30 after
    pre_start = max(0, earnings_idx - 30)
    post_end  = min(len(rows), earnings_idx + 31)
    price_series = rows[pre_start:post_end]

    return {
        "earnings_date":    earnings_date,
        "earnings_close":   round(earnings_close, 2),
        "next_day_return":  _return_at(1),
        "five_day_return":  _return_at(5),
        "thirty_day_return": _return_at(30),
        "price_series":     price_series,
    }
