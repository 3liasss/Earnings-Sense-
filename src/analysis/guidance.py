"""
Forward-looking statement (FLS) extraction and guidance scoring.

Identifies guidance phrases in MD&A text and scores how confident
management sounds about the future — separate from historical results.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

GUIDANCE_POSITIVE = [
    "expect revenue", "expect growth", "expect to achieve", "expect to deliver",
    "will grow", "will increase", "will exceed", "will deliver", "will achieve",
    "confident in", "on track to", "well positioned", "strong pipeline",
    "accelerating", "expanding", "record", "outperform", "exceed guidance",
    "raise guidance", "above guidance",
]

GUIDANCE_NEGATIVE = [
    "below expectations", "miss", "shortfall", "headwinds", "challenging",
    "lower than expected", "reduced guidance", "cut guidance", "lowering outlook",
    "uncertain outlook", "difficult environment", "pressure on margins",
    "slower than", "decline in", "weakness in",
]

FLS_MARKERS = re.compile(
    r"\b(expect|anticipate|believe|forecast|guidance|outlook|project|estimate"
    r"|will|plan to|intend to|going forward|next quarter|full year|fiscal year)\b",
    re.IGNORECASE,
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class GuidanceResult:
    guidance_score: float           # 0–100, higher = more positive guidance
    fls_sentence_count: int         # number of forward-looking sentences
    fls_ratio: float                # fls sentences / total sentences
    key_phrases: list[str] = field(default_factory=list)  # up to 5 notable phrases


def extract_guidance(text: str) -> GuidanceResult:
    if not text or not text.strip():
        return GuidanceResult(50.0, 0, 0.0, [])

    sentences = _SENTENCE_RE.split(text.strip())
    fls_sentences = [s for s in sentences if FLS_MARKERS.search(s)]

    text_lower = text.lower()
    pos_count = sum(text_lower.count(p) for p in GUIDANCE_POSITIVE)
    neg_count = sum(text_lower.count(p) for p in GUIDANCE_NEGATIVE)

    # Score: 50 baseline, shift by pos/neg balance
    total = pos_count + neg_count + 1
    guidance_score = 50.0 + ((pos_count - neg_count) / total) * 40.0
    guidance_score = max(0.0, min(100.0, guidance_score))

    # Extract up to 5 key forward-looking phrases
    key_phrases: list[str] = []
    for s in fls_sentences[:20]:
        s = s.strip()
        if 15 < len(s.split()) < 35:
            key_phrases.append(s)
        if len(key_phrases) >= 5:
            break

    fls_ratio = len(fls_sentences) / max(len(sentences), 1)

    return GuidanceResult(
        guidance_score=round(guidance_score, 1),
        fls_sentence_count=len(fls_sentences),
        fls_ratio=round(fls_ratio, 3),
        key_phrases=key_phrases,
    )


@dataclass
class YoYDelta:
    delta_mci: Optional[float]
    delta_drs: Optional[float]
    trend: str                  # "improving" | "deteriorating" | "stable" | "mixed" | "no_prior"
    interpretation: str


def compute_yoy_delta(
    current_mci: float,
    current_drs: float,
    current_guidance: float,
    history: list[dict],
    current_quarter: str,
) -> YoYDelta:
    if not history:
        return YoYDelta(None, None, "no_prior", "No prior quarters available for comparison.")

    prior = next(
        (h for h in history if h.get("quarter") != current_quarter),
        None
    )
    if not prior:
        return YoYDelta(None, None, "no_prior", "No prior quarter data available.")

    delta_mci = round(current_mci - (prior.get("mci") or current_mci), 1)
    delta_drs = round(current_drs - (prior.get("drs") or current_drs), 1)

    if delta_mci >= 5 and delta_drs <= -3:
        trend = "improving"
        interp = f"Confidence up {delta_mci:+.1f} pts, risk down {delta_drs:+.1f} pts vs prior quarter."
    elif delta_mci <= -5 and delta_drs >= 3:
        trend = "deteriorating"
        interp = f"Confidence down {delta_mci:+.1f} pts, risk up {delta_drs:+.1f} pts vs prior quarter."
    elif abs(delta_mci) < 5 and abs(delta_drs) < 3:
        trend = "stable"
        interp = f"Language largely unchanged vs prior quarter (ΔMCI {delta_mci:+.1f}, ΔDRS {delta_drs:+.1f})."
    else:
        trend = "mixed"
        interp = f"Mixed signals: ΔMCI {delta_mci:+.1f}, ΔDRS {delta_drs:+.1f} vs prior quarter."

    return YoYDelta(delta_mci=delta_mci, delta_drs=delta_drs, trend=trend, interpretation=interp)
