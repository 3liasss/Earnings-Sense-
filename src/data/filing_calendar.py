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
    Return the most relevant 10-Q filing window for a ticker.
    Priority: in-window > recently overdue (within 60 days) > next upcoming.
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

    # 1. Prefer an active in-window filing (quarter ended, deadline not yet passed)
    in_window = [(qe, due) for qe, due in candidates if qe <= as_of and due >= as_of]
    if in_window:
        qe, due = in_window[0]
    else:
        # 2. Show recently overdue (within 60 days) rather than jumping to next quarter
        recently_overdue = sorted(
            [(qe, due) for qe, due in candidates if due < as_of and (as_of - due).days <= 60],
            key=lambda x: x[1], reverse=True,
        )
        if recently_overdue:
            qe, due = recently_overdue[0]
        else:
            # 3. Fall back to next upcoming
            upcoming = [(qe, due) for qe, due in candidates if due > as_of]
            if not upcoming:
                return None
            qe, due = upcoming[0]

    days_to_due = (due - as_of).days

    if days_to_due < 0:
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
        "in_window":   qe <= as_of <= due,
        "status":      status,
    }


def get_all_upcoming(tickers: list[str], as_of: date | None = None) -> list[dict]:
    """Return filing countdowns for a list of tickers, sorted soonest first."""
    if as_of is None:
        as_of = date.today()
    results = [next_10q(t, as_of) for t in tickers]
    return sorted((r for r in results if r), key=lambda r: r["days_to_due"])
