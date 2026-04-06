"""
Stock price data fetcher using yfinance.

Computes post-earnings return metrics (next-day, 5-day, 30-day)
relative to the earnings date closing price.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf


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
          - price_series      (list[dict]): [{date, close}, ...] for 61 days
                              (30 before earnings + earnings day + 30 after)
    """
    t0 = datetime.strptime(earnings_date, "%Y-%m-%d")
    start = (t0 - timedelta(days=45)).strftime("%Y-%m-%d")
    end = (t0 + timedelta(days=45)).strftime("%Y-%m-%d")

    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No price data found for {ticker}.")

    df = df[["Close"]].copy()
    df.index = pd.to_datetime(df.index)

    # Find nearest trading day on or after earnings date
    candidate_dates = df.index[df.index >= t0]
    if candidate_dates.empty:
        raise ValueError(f"No trading data on or after {earnings_date} for {ticker}.")
    earnings_ts = candidate_dates[0]

    # Slice window: 30 trading days before and after
    idx = df.index.get_loc(earnings_ts)
    pre_start = max(0, idx - 30)
    post_end = min(len(df), idx + 31)
    window = df.iloc[pre_start:post_end].copy()

    earnings_close = float(df.loc[earnings_ts, "Close"])

    def _return_at(offset_days: int) -> Optional[float]:
        future_dates = df.index[df.index > earnings_ts]
        if len(future_dates) >= offset_days:
            future_close = float(df.loc[future_dates[offset_days - 1], "Close"])
            return round((future_close - earnings_close) / earnings_close, 4)
        return None

    price_series = [
        {"date": str(d.date()), "close": round(float(c), 2)}
        for d, c in zip(window.index, window["Close"])
    ]

    return {
        "earnings_date": earnings_date,
        "earnings_close": round(earnings_close, 2),
        "next_day_return": _return_at(1),
        "five_day_return": _return_at(5),
        "thirty_day_return": _return_at(30),
        "price_series": price_series,
    }
