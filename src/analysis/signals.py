"""
Composite signal computation: Management Confidence Index (MCI) and
Deception Risk Score (DRS).

MCI (0–100): Combines FinBERT positive sentiment with linguistic certainty
signals. Higher = management sounds more confident and direct.

DRS (0–100): Combines hedging density, passive voice, and negative sentiment.
Higher = elevated risk of misleading or overly cautious language.

Also provides a backtest engine that correlates MCI with post-earnings
price movements — the empirical validity test.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Scores:
    management_confidence_index: float  # 0–100, higher = more confident
    deception_risk_score: float         # 0–100, higher = more risk


@dataclass
class BacktestResult:
    pearson_r: float
    p_value: float
    n_observations: int
    interpretation: str
    samples: list[dict]


# ── Score computation ─────────────────────────────────────────────────────────

def compute_scores(sentiment, linguistics) -> Scores:
    """
    Compute MCI and DRS from FinBERT sentiment + linguistic features.

    MCI formula (100-point scale):
      - FinBERT positive score          → 40 pts max
      - Certainty ratio (norm to 0–1)   → 25 pts max
      - Hedge density (inverted, norm)  → 20 pts max
      - Passive voice ratio (inverted)  → 15 pts max

    DRS formula (100-point scale):
      - Hedge density (norm)            → 40 pts max
      - Passive voice ratio             → 30 pts max
      - FinBERT negative score          → 20 pts max
      - Vague language (norm)           → 10 pts max
    """
    # Normalize certainty ratio: cap at 5 → map to [0, 1]
    certainty_norm = min(linguistics.certainty_ratio / 5.0, 1.0)

    # Normalize hedge density: cap at 5 per 100 words → [0, 1], then invert
    hedge_norm_inv = 1.0 - min(linguistics.hedge_density / 5.0, 1.0)

    # Passive voice already [0, 1]; invert for MCI contribution
    passive_inv = 1.0 - linguistics.passive_voice_ratio

    # Vague language: cap at 3 per 100 words → [0, 1]
    vague_norm = min(linguistics.vague_language_score / 3.0, 1.0)

    mci = (
        sentiment.positive * 40.0
        + certainty_norm * 25.0
        + hedge_norm_inv * 20.0
        + passive_inv * 15.0
    )

    drs = (
        (1.0 - hedge_norm_inv) * 40.0
        + linguistics.passive_voice_ratio * 30.0
        + sentiment.negative * 20.0
        + vague_norm * 10.0
    )

    return Scores(
        management_confidence_index=round(min(max(mci, 0), 100), 1),
        deception_risk_score=round(min(max(drs, 0), 100), 1),
    )


# ── Backtest engine ───────────────────────────────────────────────────────────

def backtest(samples: list[dict]) -> BacktestResult:
    """
    Correlate Management Confidence Index with next-day stock returns.

    Args:
        samples: list of sample dicts, each containing:
                 scores.management_confidence_index  (float)
                 price_impact.next_day_return        (float, e.g. 0.054 = +5.4%)

    Returns:
        BacktestResult with Pearson r, p-value, and enriched sample list.
    """
    if len(samples) < 3:
        return BacktestResult(0.0, 1.0, len(samples), "insufficient data", samples)

    mcis = np.array([s["scores"]["management_confidence_index"] for s in samples])
    returns = np.array([s["price_impact"]["next_day_return"] * 100 for s in samples])

    # Pearson correlation + two-tailed p-value via t-distribution
    r = float(np.corrcoef(mcis, returns)[0, 1])
    n = len(samples)
    if abs(r) >= 1.0:
        p_value = 0.0
    else:
        t_stat = r * np.sqrt((n - 2) / (1 - r ** 2))
        from scipy import stats
        p_value = float(2 * stats.t.sf(abs(t_stat), df=n - 2))

    if abs(r) >= 0.7:
        strength = "strong"
    elif abs(r) >= 0.4:
        strength = "moderate"
    else:
        strength = "weak"

    direction = "positive" if r > 0 else "negative"
    sig = "statistically significant (p < 0.05)" if p_value < 0.05 else f"p = {p_value:.3f}"
    interpretation = (
        f"{strength.capitalize()} {direction} correlation (r = {r:.3f}), {sig}. "
        f"Higher management confidence tends to precede {'better' if r > 0 else 'worse'} "
        f"next-day returns."
    )

    return BacktestResult(
        pearson_r=round(r, 3),
        p_value=round(p_value, 4),
        n_observations=n,
        interpretation=interpretation,
        samples=samples,
    )
