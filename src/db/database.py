"""
Lightweight SQLite store for MCI history and watchlist.
Keeps a local record of every ticker that has been scored so the
dashboard can show YoY trends without re-running FinBERT.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

DB_PATH = Path("data/earningssense.db")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS mci_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker        TEXT    NOT NULL,
                quarter       TEXT    NOT NULL,
                report_date   TEXT,
                mci           REAL,
                drs           REAL,
                sentiment_pos REAL,
                sentiment_neg REAL,
                certainty_ratio REAL,
                hedge_density   REAL,
                guidance_score  REAL,
                delta_mci       REAL,
                next_day_return REAL,
                created_at    TEXT DEFAULT (datetime('now')),
                UNIQUE(ticker, quarter)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker     TEXT UNIQUE NOT NULL,
                added_at   TEXT DEFAULT (datetime('now'))
            )
        """)


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_mci_score(
    ticker: str,
    quarter: str,
    report_date: str = "",
    mci: float = 0.0,
    drs: float = 0.0,
    sentiment_pos: float = 0.0,
    sentiment_neg: float = 0.0,
    certainty_ratio: float = 0.0,
    hedge_density: float = 0.0,
    guidance_score: Optional[float] = None,
    delta_mci: Optional[float] = None,
    next_day_return: Optional[float] = None,
) -> None:
    with get_db() as db:
        db.execute("""
            INSERT INTO mci_history
              (ticker, quarter, report_date, mci, drs, sentiment_pos, sentiment_neg,
               certainty_ratio, hedge_density, guidance_score, delta_mci, next_day_return)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker, quarter) DO UPDATE SET
              mci=excluded.mci, drs=excluded.drs,
              sentiment_pos=excluded.sentiment_pos,
              sentiment_neg=excluded.sentiment_neg,
              certainty_ratio=excluded.certainty_ratio,
              hedge_density=excluded.hedge_density,
              guidance_score=excluded.guidance_score,
              delta_mci=excluded.delta_mci,
              next_day_return=excluded.next_day_return
        """, (ticker, quarter, report_date, mci, drs, sentiment_pos, sentiment_neg,
              certainty_ratio, hedge_density, guidance_score, delta_mci, next_day_return))


def get_mci_history(ticker: str, limit: int = 12) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM mci_history WHERE ticker=? ORDER BY report_date DESC LIMIT ?",
            (ticker, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def get_watchlist() -> list[str]:
    """Return tickers in the watchlist, sorted alphabetically."""
    with get_db() as db:
        rows = db.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
    return [r["ticker"] for r in rows]


def set_watchlist(tickers: list[str]) -> None:
    """Replace the entire watchlist with the given tickers."""
    with get_db() as db:
        db.execute("DELETE FROM watchlist")
        for t in tickers:
            t = t.strip().upper()
            if t:
                db.execute("INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)", (t,))


def get_sector_benchmarks(tickers: list[str]) -> dict:
    """
    Return avg MCI and DRS for a list of tickers using their most recent DB records.
    Returns {} if no records found.
    """
    if not tickers:
        return {}
    placeholders = ",".join("?" * len(tickers))
    with get_db() as db:
        rows = db.execute(f"""
            SELECT h.ticker, h.mci, h.drs
            FROM mci_history h
            INNER JOIN (
                SELECT ticker, MAX(id) AS max_id
                FROM mci_history
                WHERE ticker IN ({placeholders})
                GROUP BY ticker
            ) latest ON h.ticker = latest.ticker AND h.id = latest.max_id
        """, tickers).fetchall()
    data = [dict(r) for r in rows]
    if not data:
        return {}
    return {
        "count":   len(data),
        "avg_mci": round(sum(d["mci"] for d in data) / len(data), 1),
        "avg_drs": round(sum(d["drs"] for d in data) / len(data), 1),
    }
