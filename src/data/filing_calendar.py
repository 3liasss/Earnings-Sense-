"""
SEC 10-Q filing deadline tracker.

Large accelerated filers (all S&P 500 mega-caps) must file 10-Qs
within 40 calendar days of quarter end. This module computes the
next expected filing window per ticker based on fiscal year end month.

10-K annual reports are excluded - only 10-Q quarters tracked.
"""
from __future__ import annotations

import calendar as cal_module
from datetime import date, timedelta

# Month of fiscal year END (Q4 / annual 10-K)
# This determines all quarterly end dates: Q1=FYend-9m, Q2=FYend-6m, Q3=FYend-3m
FY_END_MONTHS: dict[str, int] = {
    "NVDA":  1,   # January 31
    "MSFT":  6,   # June 30
    "META":  12,  # December 31
    "AMZN":  12,
    "GOOGL": 12,
    "AAPL":  9,   # ~September 28 (fiscal calendar)
    "TSLA":  12,
    "NFLX":  12,
    "AMD":   12,
    "ORCL":  5,   # May 31
}

FILING_DEADLINE_DAYS = 40


def _month_end(year: int, month: int) -> date:
    return date(year, month, cal_module.monthrange(year, month)[1])


def _10q_quarter_ends(fy_end_month: int, reference: date) -> list[date]:
    """
    Generate 10-Q quarter end dates (not the annual Q4) around a reference date.
    For FY ending month M: Q1 ends M-9, Q2 ends M-6, Q3 ends M-3 (all mod 12).
    """
    ends: set[date] = set()
    for year_offset in range(-1, 3):
        y = reference.year + year_offset
        for subtract in (3, 6, 9):
            m = fy_end_month - subtract
            adj_y = y
            while m <= 0:
                m += 12
                adj_y -= 1
            ends.add(_month_end(adj_y, m))
    return sorted(ends)


def next_10q(ticker: str, as_of: date | None = None) -> dict | None:
    """
    Return the next expected 10-Q filing window for a ticker.

    Returns:
        dict with keys:
          ticker       - ticker symbol
          quarter_end  - date: last day of the filing quarter
          filing_due   - date: SEC deadline (quarter_end + 40 days)
          days_to_due  - int: days until filing deadline from as_of
          in_window    - bool: quarter already ended but filing not yet due
          status       - str: "IMMINENT" | "THIS MONTH" | "UPCOMING" | "OVERDUE"
    """
    if as_of is None:
        as_of = date.today()

    fy_end = FY_END_MONTHS.get(ticker.upper())
    if fy_end is None:
        return None

    candidates = [
        (qe, qe + timedelta(days=FILING_DEADLINE_DAYS))
        for qe in _10q_quarter_ends(fy_end, as_of)
    ]
    # Keep only future or active (due date not yet passed)
    future = [(qe, due) for qe, due in candidates if due >= as_of]
    if not future:
        return None

    qe, due = future[0]
    days_to_due = (due - as_of).days

    if days_to_due <= 0:
        status = "OVERDUE"
    elif days_to_due <= 7:
        status = "IMMINENT"
    elif days_to_due <= 30:
        status = "THIS MONTH"
    else:
        status = "UPCOMING"

    return {
        "ticker":      ticker,
        "quarter_end": qe,
        "filing_due":  due,
        "days_to_due": days_to_due,
        "in_window":   qe <= as_of,
        "status":      status,
    }


def get_all_upcoming(tickers: list[str], as_of: date | None = None) -> list[dict]:
    """Return filing countdowns for a list of tickers, sorted soonest first."""
    if as_of is None:
        as_of = date.today()
    results = [next_10q(t, as_of) for t in tickers]
    return sorted((r for r in results if r), key=lambda r: r["days_to_due"])
