"""
SEC EDGAR data fetcher.

Pulls 10-Q filings (quarterly reports) for a given ticker using the
free, public EDGAR REST API - no API key required.

The Management Discussion & Analysis (MD&A) section is extracted as a
proxy for earnings call language; it contains the same forward-looking
statements and management commentary that professional NLP services analyze.

EDGAR API docs: https://www.sec.gov/developer
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# EDGAR requires a descriptive User-Agent (email or company name)
HEADERS = {
    "User-Agent": "EarningsSense research@earningssense.ai",
    "Accept-Encoding": "gzip, deflate",
}

CACHE_DIR = Path("data/cache")
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"


def _get(url: str, retries: int = 3, delay: float = 0.5) -> requests.Response:
    """GET with retry and polite rate-limiting (EDGAR asks for ≤10 req/sec)."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            time.sleep(delay)
            return r
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}")


# ── CIK lookup ────────────────────────────────────────────────────────────────

_ticker_map: Optional[dict] = None


def get_cik(ticker: str) -> str:
    """
    Return the zero-padded 10-digit CIK for a ticker symbol.

    Uses the EDGAR company_tickers.json endpoint, which maps every
    publicly traded company to its SEC CIK number.
    """
    global _ticker_map

    if _ticker_map is None:
        resp = _get(TICKER_MAP_URL)
        raw = resp.json()
        _ticker_map = {v["ticker"].upper(): str(v["cik_str"]).zfill(10)
                       for v in raw.values()}

    cik = _ticker_map.get(ticker.upper())
    if not cik:
        raise ValueError(f"Ticker '{ticker}' not found in EDGAR. "
                         f"Try the parent company ticker.")
    return cik


# ── Filing discovery ──────────────────────────────────────────────────────────

def get_recent_10q_filings(cik: str, limit: int = 4) -> list[dict]:
    """
    Return the most recent 10-Q filing metadata for a company.

    Each dict contains: accession_number, filing_date, report_date.
    """
    url = SUBMISSIONS_URL.format(cik=cik)
    data = _get(url).json()

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    accessions = filings.get("accessionNumber", [])
    dates = filings.get("filingDate", [])
    report_dates = filings.get("reportDate", [])
    primary_docs = filings.get("primaryDocument", [])

    results = []
    for form, acc, date, rdate, pdoc in zip(forms, accessions, dates, report_dates, primary_docs):
        if form == "10-Q":
            results.append({
                "accession_number": acc.replace("-", ""),
                "accession_raw": acc,
                "filing_date": date,
                "report_date": rdate,
                "primary_document": pdoc,
            })
        if len(results) >= limit:
            break

    return results


def get_all_10q_filings(cik: str, max_quarters: int = 32) -> list[dict]:
    """
    Return up to max_quarters 10-Q filings going back as far as EDGAR's
    recent-submissions batch allows (typically 8+ years).

    The EDGAR submissions API stores the last ~1000 filings in
    data.filings.recent - this covers 30+ 10-Qs for most large caps.
    Results are returned newest-first.
    """
    url  = SUBMISSIONS_URL.format(cik=cik)
    data = _get(url).json()

    filings      = data.get("filings", {}).get("recent", {})
    forms        = filings.get("form", [])
    accessions   = filings.get("accessionNumber", [])
    dates        = filings.get("filingDate", [])
    report_dates = filings.get("reportDate", [])
    primary_docs = filings.get("primaryDocument", [])

    results = []
    for form, acc, date, rdate, pdoc in zip(
        forms, accessions, dates, report_dates, primary_docs
    ):
        if form == "10-Q":
            results.append({
                "accession_number": acc.replace("-", ""),
                "accession_raw":    acc,
                "filing_date":      date,
                "report_date":      rdate,
                "primary_document": pdoc,
            })
        if len(results) >= max_quarters:
            break

    return results


# ── Text extraction ───────────────────────────────────────────────────────────

def _find_document_url(cik: str, accession: str, primary_document: Optional[str] = None) -> Optional[str]:
    """
    Return the direct URL to the primary 10-Q HTML document.

    Uses the primaryDocument field from the EDGAR submissions API first
    (most reliable), then falls back to index.json scanning.
    """
    cik_raw = cik.lstrip("0")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_raw}/{accession}/"

    # Fast path: primaryDocument field is already the filename
    if primary_document and primary_document.endswith(".htm"):
        return base + primary_document

    # Fallback: scan filing index JSON
    try:
        index_json_url = base + f"{accession[:10]}-{accession[10:12]}-{accession[12:]}-index.json"
        data = _get(index_json_url).json()
        for doc in data.get("documents", []):
            if doc.get("type") == "10-Q" and doc.get("name", "").endswith(".htm"):
                return base + doc["name"]
    except Exception:
        pass

    return None


_MDA_PATTERNS = [
    re.compile(r"management.{0,20}discussion.{0,20}analysis", re.IGNORECASE),
    re.compile(r"results of operations", re.IGNORECASE),
]


def _extract_mda(html: str) -> str:
    """
    Extract the MD&A section from a 10-Q HTML document.

    Uses section header detection to isolate the relevant text block.
    Falls back to the full body text if MD&A boundaries can't be found.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove only scripts and styles - keep tables (they contain MD&A text)
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s{2,}", " ", text)

    # Find all MD&A section starts - take the LAST one (avoids table-of-contents hit)
    start_idx = None
    for pattern in _MDA_PATTERNS:
        for m in pattern.finditer(text):
            start_idx = m.start()  # keep last match
        if start_idx:
            break

    if start_idx is None:
        words = text.split()
        return " ".join(words[:5000])

    # Find next major section header after MD&A to bound the extraction window
    window = text[start_idx + 200:]
    section_after = re.search(
        r"ITEM\s+3[\.\s]|quantitative and qualitative|item\s+4[\.\s]|controls and procedures",
        window,
        re.IGNORECASE,
    )
    end_idx = (start_idx + 200 + section_after.start()
               if section_after else start_idx + 50000)

    mda_text = text[start_idx:end_idx]
    words = mda_text.split()
    return " ".join(words[:5000])   # cap at 5,000 words for inference speed


# ── Main public function ──────────────────────────────────────────────────────

def fetch_filing_text(ticker: str, use_cache: bool = True) -> dict:
    """
    Fetch the most recent 10-Q MD&A text for a ticker.

    Returns a dict with keys: ticker, company, filing_date, report_date, text.
    Results are cached to data/cache/ to avoid redundant API calls.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{ticker.upper()}_10q.json"

    if use_cache and cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    cik = get_cik(ticker)
    filings = get_recent_10q_filings(cik, limit=1)

    if not filings:
        raise ValueError(f"No 10-Q filings found for {ticker}.")

    filing = filings[0]
    doc_url = _find_document_url(cik, filing["accession_number"], filing.get("primary_document"))

    if doc_url is None:
        raise ValueError(f"Could not locate 10-Q document for {ticker}.")

    html = _get(doc_url).text
    mda_text = _extract_mda(html)

    # Fetch company name from submissions metadata
    sub_data = _get(SUBMISSIONS_URL.format(cik=cik)).json()
    company_name = sub_data.get("name", ticker.upper())

    result = {
        "ticker": ticker.upper(),
        "company": company_name,
        "filing_date": filing["filing_date"],
        "report_date": filing["report_date"],
        "text": mda_text,
        "source": doc_url,
    }

    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


def fetch_8k_text(ticker: str, use_cache: bool = True) -> dict:
    """
    Fetch the most recent 8-K earnings press release for a ticker from EDGAR.

    Looks for EX-99.1 exhibit (the earnings release document) in the most
    recent 8-K filing. Falls back to the 8-K primary document if no exhibit
    is found.

    Returns same dict shape as fetch_filing_text():
        ticker, company, filing_date, report_date, text, source
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{ticker.upper()}_8k.json"

    if use_cache and cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    cik  = get_cik(ticker)
    url  = SUBMISSIONS_URL.format(cik=cik)
    data = _get(url).json()

    filings      = data.get("filings", {}).get("recent", {})
    forms        = filings.get("form", [])
    accessions   = filings.get("accessionNumber", [])
    dates        = filings.get("filingDate", [])
    primary_docs = filings.get("primaryDocument", [])

    filing_8k = None
    for form, acc, date, pdoc in zip(forms, accessions, dates, primary_docs):
        if form == "8-K":
            filing_8k = {
                "accession_number": acc.replace("-", ""),
                "accession_raw":    acc,
                "filing_date":      date,
                "primary_document": pdoc,
            }
            break

    if not filing_8k:
        raise ValueError(f"No 8-K filings found for {ticker}.")

    doc_url = _find_8k_exhibit_url(cik, filing_8k["accession_number"],
                                    filing_8k.get("primary_document"))
    if not doc_url:
        raise ValueError(f"Could not locate 8-K document for {ticker}.")

    html_text = _get(doc_url).text
    text      = _extract_8k_text(html_text)
    company_name = data.get("name", ticker.upper())

    result = {
        "ticker":      ticker.upper(),
        "company":     company_name,
        "filing_date": filing_8k["filing_date"],
        "report_date": filing_8k["filing_date"],
        "text":        text,
        "source":      doc_url,
    }

    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


def _find_8k_exhibit_url(cik: str, accession: str,
                          primary_document: Optional[str] = None) -> Optional[str]:
    """
    Return the URL for the EX-99.1 press release in an 8-K filing,
    falling back to the primary 8-K document if no exhibit is found.
    """
    cik_raw = cik.lstrip("0")
    base    = f"https://www.sec.gov/Archives/edgar/data/{cik_raw}/{accession}/"

    try:
        fmt_acc       = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
        index_url     = base + f"{fmt_acc}-index.json"
        index_data    = _get(index_url).json()
        docs          = index_data.get("documents", [])

        # Prefer EX-99.1 (earnings press release)
        for doc in docs:
            if doc.get("type") in ("EX-99.1", "EX-99") and doc.get("name", "").endswith(".htm"):
                return base + doc["name"]

        # Fall back to primary 8-K document
        for doc in docs:
            if doc.get("type") == "8-K" and doc.get("name", "").endswith(".htm"):
                return base + doc["name"]
    except Exception:
        pass

    # Last resort: primaryDocument field
    if primary_document and primary_document.endswith(".htm"):
        return base + primary_document

    return None


def _extract_8k_text(html: str) -> str:
    """Extract narrative text from an 8-K / EX-99.1 press release HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s{2,}", " ", text)
    words = text.split()
    return " ".join(words[:5000])


def fetch_multiple_filings(ticker: str, n_quarters: int = 8) -> list[dict]:
    """
    Fetch text + metadata for the last n_quarters 10-Q filings.

    Returns a list of dicts with keys: ticker, company, filing_date,
    report_date, text, source. Results are cached per quarter to avoid
    redundant EDGAR API calls.

    This is the batch entry point for building a real backtest dataset.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cik      = get_cik(ticker)
    filings  = get_recent_10q_filings(cik, limit=n_quarters)

    # Fetch company name once
    try:
        sub_data     = _get(SUBMISSIONS_URL.format(cik=cik)).json()
        company_name = sub_data.get("name", ticker.upper())
    except Exception:
        company_name = ticker.upper()

    results = []
    for filing in filings:
        cache_path = CACHE_DIR / f"{ticker.upper()}_{filing['report_date']}_10q.json"

        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    results.append(json.load(f))
                continue
            except Exception:
                pass

        doc_url = _find_document_url(cik, filing["accession_number"], filing.get("primary_document"))
        if not doc_url:
            print(f"[edgar] No document URL for {ticker} {filing['report_date']}")
            continue

        try:
            html     = _get(doc_url).text
            mda_text = _extract_mda(html)
        except Exception as e:
            print(f"[edgar] Fetch failed for {ticker} {filing['report_date']}: {e}")
            continue

        record = {
            "ticker":       ticker.upper(),
            "company":      company_name,
            "filing_date":  filing["filing_date"],
            "report_date":  filing["report_date"],
            "text":         mda_text,
            "source":       doc_url,
        }

        with open(cache_path, "w") as f:
            json.dump(record, f, indent=2)

        results.append(record)
        time.sleep(0.6)   # polite EDGAR rate-limiting

    return results
