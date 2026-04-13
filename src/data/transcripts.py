"""
Earnings call transcript fetcher using FinancialModelingPrep (FMP) API.

Free tier: 250 requests/day.
Get a free API key at: https://financialmodelingprep.com/developer/docs/
Set key as FMP_API_KEY in .streamlit/secrets.toml or as an environment variable.

Also provides EPS actual vs. estimate data via the earnings-surprises endpoint.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

FMP_BASE  = "https://financialmodelingprep.com/api/v3"
CACHE_DIR = Path("data/cache")


def _get_api_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("FMP_API_KEY", os.environ.get("FMP_API_KEY", ""))
    except Exception:
        return os.environ.get("FMP_API_KEY", "")


def _get(url: str) -> object:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_transcript(ticker: str, use_cache: bool = True) -> dict:
    """
    Fetch the most recent earnings call transcript for a ticker via FMP API.

    Returns dict with keys:
        ticker, company, report_date, quarter_label, text,
        prepared_remarks, qa_text, source

    Raises ValueError if API key is not set, quota exceeded, or no data found.
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "FMP_API_KEY not configured. "
            "Add FMP_API_KEY = \"your_key\" to .streamlit/secrets.toml. "
            "Free keys available at financialmodelingprep.com"
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{ticker.upper()}_transcript.json"

    if use_cache and cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    url  = f"{FMP_BASE}/earning_call_transcript/{ticker.upper()}?apikey={api_key}"
    data = _get(url)

    if isinstance(data, dict) and "Error Message" in data:
        raise ValueError(f"FMP API error: {data['Error Message']}")
    if not data or not isinstance(data, list):
        raise ValueError(f"No transcripts found for {ticker} on FMP.")

    transcript = data[0]
    content    = transcript.get("content", "").strip()
    if not content:
        raise ValueError(f"Transcript content is empty for {ticker}.")

    prepared_remarks, qa_text = _split_transcript(content)
    q = transcript.get("quarter", "")
    y = transcript.get("year",    "")

    result = {
        "ticker":           ticker.upper(),
        "company":          ticker.upper(),
        "report_date":      (transcript.get("date", "") or "")[:10],
        "quarter_label":    f"Q{q} {y}" if q and y else "Latest",
        "text":             content,
        "prepared_remarks": prepared_remarks,
        "qa_text":          qa_text,
        "source":           "FMP Earnings Call Transcript",
    }

    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


def _split_transcript(text: str) -> tuple[str, str]:
    """
    Split a transcript into prepared remarks and analyst Q&A sections.
    Returns (prepared_remarks, qa_text). qa_text is empty if no Q&A found.
    """
    marker = re.compile(
        r"(question[\s-]and[\s-]answer|Q&A session"
        r"|we will now (begin|take).{0,25}question"
        r"|operator.{0,30}question"
        r"|open.{0,20}(line|floor).{0,20}question"
        r"|please go ahead.{0,20}question)",
        re.IGNORECASE,
    )
    m = marker.search(text)
    if m:
        return text[:m.start()].strip(), text[m.start():].strip()
    return text.strip(), ""


def fetch_earnings_surprise(ticker: str) -> list[dict]:
    """
    Fetch recent EPS actual vs. estimate data from FMP earnings-surprises endpoint.

    Returns list of dicts (up to 6 quarters):
        {date, actual_eps, estimated_eps, surprise_pct}

    Returns [] if API key is not set or the request fails.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    try:
        url  = f"{FMP_BASE}/earnings-surprises/{ticker.upper()}?apikey={api_key}"
        data = _get(url)

        if not isinstance(data, list):
            return []

        results = []
        for item in data[:6]:
            actual   = item.get("actualEarningResult")
            estimate = item.get("estimatedEarning")
            if actual is None or estimate is None:
                continue
            surprise = (
                round((float(actual) - float(estimate)) / abs(float(estimate)) * 100, 2)
                if estimate != 0 else 0.0
            )
            results.append({
                "date":          item.get("date", ""),
                "actual_eps":    round(float(actual),   3),
                "estimated_eps": round(float(estimate), 3),
                "surprise_pct":  surprise,
            })
        return results
    except Exception:
        return []
