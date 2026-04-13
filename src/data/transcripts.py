"""
Earnings call transcript fetcher.

Source priority:
  1. FinancialModelingPrep API  - structured JSON, Q&A preserved (paid plan required)
  2. Motley Fool scraping       - free, full transcript with Q&A, no key needed
  3. SEC EDGAR 8-K fallback     - always works, earnings press release (no Q&A section)

FMP key is optional - add FMP_API_KEY to .streamlit/secrets.toml for priority-1 source.
Also provides EPS actual vs. estimate data via FMP earnings-surprises endpoint.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FMP_BASE  = "https://financialmodelingprep.com/api/v3"
CACHE_DIR = Path("data/cache")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get_api_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("FMP_API_KEY", os.environ.get("FMP_API_KEY", ""))
    except Exception:
        return os.environ.get("FMP_API_KEY", "")


def _get_json(url: str) -> object:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_transcript(ticker: str, use_cache: bool = True) -> dict:
    """
    Fetch the most recent earnings call transcript for a ticker.

    Tries FMP → Motley Fool → EDGAR 8-K in that order.

    Returns dict with keys:
        ticker, company, report_date, quarter_label, text,
        prepared_remarks, qa_text, source
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{ticker.upper()}_transcript.json"

    if use_cache and cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    # 1. Try FMP (if key present and plan supports transcripts)
    api_key = _get_api_key()
    if api_key:
        result = _try_fmp(ticker, api_key)
        if result:
            result.update({"ticker": ticker.upper()})
            _save(result, cache_path)
            return result

    # 2. Try Motley Fool (free, no key required)
    result = _try_motley_fool(ticker)
    if result:
        result.update({"ticker": ticker.upper(), "company": ticker.upper()})
        _save(result, cache_path)
        return result

    # 3. Fall back to EDGAR 8-K
    return _fetch_8k_fallback(ticker, use_cache, cache_path)


def _save(result: dict, path: Path) -> None:
    with open(path, "w") as f:
        json.dump(result, f, indent=2)


# ── Source 1: FMP ─────────────────────────────────────────────────────────────

def _try_fmp(ticker: str, api_key: str) -> dict | None:
    try:
        url  = f"{FMP_BASE}/earning_call_transcript/{ticker.upper()}?apikey={api_key}"
        data = _get_json(url)

        if isinstance(data, dict) and "Error Message" in data:
            return None
        if not data or not isinstance(data, list):
            return None

        transcript = data[0]
        content    = (transcript.get("content") or "").strip()
        if len(content.split()) < 200:
            return None

        prepared, qa = _split_transcript(content)
        q = transcript.get("quarter", "")
        y = transcript.get("year",    "")

        return {
            "company":          ticker.upper(),
            "report_date":      (transcript.get("date") or "")[:10],
            "quarter_label":    f"Q{q} {y}" if q and y else "Latest",
            "text":             content,
            "prepared_remarks": prepared,
            "qa_text":          qa,
            "source":           "FMP Earnings Call Transcript",
        }
    except requests.HTTPError as e:
        if e.response.status_code in (401, 403):
            return None  # paid plan required - try next source
        return None
    except Exception:
        return None


# ── Source 2: Motley Fool ─────────────────────────────────────────────────────

def _try_motley_fool(ticker: str) -> dict | None:
    """
    Search Motley Fool for the latest earnings call transcript and scrape it.
    Returns None on any failure so the caller can try the next source.
    """
    try:
        # Search for transcript
        search_url = (
            f"https://www.fool.com/search/?q={ticker}+earnings+call+transcript"
            f"&source=eefsiteheader"
        )
        resp = requests.get(search_url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        soup          = BeautifulSoup(resp.text, "html.parser")
        transcript_url = None

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "earnings/call-transcripts" in href and "earnings-call-transcript" in href:
                if not href.startswith("http"):
                    href = "https://www.fool.com" + href
                transcript_url = href
                break

        if not transcript_url:
            return None

        time.sleep(1.0)  # polite delay between requests

        resp = requests.get(transcript_url, headers=_HEADERS, timeout=20)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "aside", "figure", "header", "footer", "nav"]):
            tag.decompose()

        # Try multiple selectors for the article body
        article = None
        for tag, attrs in [
            ("div",     {"class": "article-body"}),
            ("div",     {"id":    "article-body"}),
            ("section", {"class": re.compile("article")}),
            ("article", {}),
        ]:
            candidate = soup.find(tag, attrs) if attrs else soup.find(tag)
            if candidate and len(candidate.get_text().split()) > 200:
                article = candidate
                break

        if not article:
            return None

        raw  = article.get_text(separator=" ", strip=True)
        raw  = re.sub(r"\s{2,}", " ", raw)
        words = raw.split()

        if len(words) < 300:
            return None

        text = " ".join(words[:8000])

        # Extract date from URL e.g. /2025/10/29/
        date_m = re.search(r"/call-transcripts/(\d{4})/(\d{2})/(\d{2})/", transcript_url)
        report_date = (
            f"{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}"
            if date_m else ""
        )

        # Extract quarter from slug e.g. meta-platforms-q3-2025-earnings-call
        slug    = transcript_url.rstrip("/").split("/")[-1]
        q_match = re.search(r"-q(\d)-(\d{4})-", slug)
        quarter_label = (
            f"Q{q_match.group(1)} {q_match.group(2)}" if q_match else "Latest"
        )

        prepared, qa = _split_transcript(text)

        return {
            "company":          ticker.upper(),
            "report_date":      report_date,
            "quarter_label":    quarter_label,
            "text":             text,
            "prepared_remarks": prepared,
            "qa_text":          qa,
            "source":           f"Motley Fool Transcript ({transcript_url})",
        }

    except Exception:
        return None


# ── Source 3: EDGAR 8-K fallback ─────────────────────────────────────────────

def _fetch_8k_fallback(ticker: str, use_cache: bool, cache_path: Path) -> dict:
    """Fetch latest 8-K earnings press release from EDGAR as last resort."""
    from src.data.edgar import fetch_8k_text

    filing = fetch_8k_text(ticker, use_cache=use_cache)

    result = {
        "ticker":           ticker.upper(),
        "company":          filing.get("company", ticker.upper()),
        "report_date":      filing.get("report_date", ""),
        "quarter_label":    (filing.get("filing_date") or "")[:7] or "Latest",
        "text":             filing["text"],
        "prepared_remarks": filing["text"],
        "qa_text":          "",
        "source":           "SEC EDGAR 8-K Earnings Release",
    }

    _save(result, cache_path)
    return result


# ── Shared helpers ────────────────────────────────────────────────────────────

def _split_transcript(text: str) -> tuple[str, str]:
    """Split transcript into prepared remarks and Q&A sections."""
    marker = re.compile(
        r"(question[\s-]and[\s-]answer|Q&A session"
        r"|we will now (?:begin|take).{0,25}question"
        r"|operator.{0,30}question"
        r"|open.{0,20}(?:line|floor).{0,20}question"
        r"|please go ahead.{0,20}question)",
        re.IGNORECASE,
    )
    m = marker.search(text)
    if m:
        return text[:m.start()].strip(), text[m.start():].strip()
    return text.strip(), ""


# ── FMP earnings surprise ─────────────────────────────────────────────────────

def fetch_earnings_surprise(ticker: str) -> list[dict]:
    """
    Fetch recent EPS actual vs. estimate data from FMP (free tier endpoint).
    Returns [] if no key or request fails.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    try:
        url  = f"{FMP_BASE}/earnings-surprises/{ticker.upper()}?apikey={api_key}"
        data = _get_json(url)

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
