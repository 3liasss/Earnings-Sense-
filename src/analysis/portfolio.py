"""
Portfolio construction engine.

AlphaScore = z(MCI) - λ·z(DRS) + z(ΔMCI) - λ·z(ΔDRS)

where z() = cross-sectional z-score within quarter (zero mean, unit variance).
λ controls how much we penalise deception risk vs reward confidence.

Portfolio rules:
  Long  top    top_pct of AlphaScore (default 20%)
  Short bottom top_pct of AlphaScore
  Equal-weight within each leg

Risk management:
  Sector-neutral variant: rank within sector, then combine
  Volatility scaling: scale position size by 1/realised_vol
  Max drawdown tracking

Output metrics:
  Annualised return, Sharpe, max drawdown, hit rate, turnover,
  long/short leg breakdown, NAV series.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class PortfolioResult:
    lambda_val: float
    top_pct: float

    # ── Performance (annualised at 4 events/year) ──────────────────────────────
    ann_return_ls: float
    ann_vol_ls:    float
    sharpe_ls:     float
    max_drawdown:  float
    hit_rate:      float
    calmar_ratio:  float

    # ── Leg breakdown ──────────────────────────────────────────────────────────
    mean_long_ret:  float
    mean_short_ret: float
    mean_ls_spread: float

    # ── Operational ───────────────────────────────────────────────────────────
    avg_turnover:  float   # fraction of names replaced each quarter
    avg_n_long:    float
    avg_n_short:   float

    # ── AlphaScore stats ──────────────────────────────────────────────────────
    ic_alpha_1d: float     # IC of AlphaScore vs 1d return
    ic_alpha_5d: float     # IC of AlphaScore vs 5d return (if available)

    # ── NAV / equity curve ────────────────────────────────────────────────────
    equity_curve: list[dict] = field(default_factory=list)
    # [{quarter, long_ret, short_ret, ls_ret, nav_ls, drawdown}]


def _zscore_cross(series: pd.Series) -> pd.Series:
    """Cross-sectional z-score: zero mean, unit variance."""
    mu = series.mean()
    sd = series.std()
    if sd < 1e-9:
        return series - mu
    return (series - mu) / sd


def _max_drawdown(returns: np.ndarray) -> float:
    """Max peak-to-trough drawdown from a return series."""
    nav   = np.cumprod(1 + returns)
    peak  = np.maximum.accumulate(nav)
    dd    = (nav - peak) / peak
    return float(dd.min())


def compute_alpha_scores(df: pd.DataFrame, lambda_val: float = 0.5) -> pd.DataFrame:
    """
    Add cross-sectionally z-scored signals and AlphaScore to df.
    Returns copy with new columns: z_mci, z_drs, z_dmci, z_ddrs, alpha_score.
    """
    df = df.copy().sort_values(["ticker", "report_date"])

    for col in ["mci", "drs"]:
        dc = f"d_{col}"
        if dc not in df.columns:
            df[dc] = df.groupby("ticker")[col].diff()

    def _quarter_zscore(grp: pd.DataFrame) -> pd.DataFrame:
        grp = grp.copy()
        for col, zcol in [("mci", "z_mci"), ("drs", "z_drs"),
                          ("d_mci", "z_dmci"), ("d_drs", "z_ddrs")]:
            if col in grp.columns:
                grp[zcol] = _zscore_cross(grp[col])
            else:
                grp[zcol] = 0.0
        grp["alpha_score"] = (
            grp["z_mci"]
            - lambda_val * grp["z_drs"]
            + grp["z_dmci"]
            - lambda_val * grp["z_ddrs"]
        )
        return grp

    parts = []
    for q, grp in df.groupby("quarter"):
        parts.append(_quarter_zscore(grp.copy()))
    df = pd.concat(parts).reset_index(drop=True)
    return df


def construct_portfolio(
    df: pd.DataFrame,
    return_col: str = "next_day_return",
    top_pct: float  = 0.20,
    lambda_val: float = 0.5,
) -> Optional[PortfolioResult]:
    """
    Build long-short portfolio based on AlphaScore.
    Returns PortfolioResult or None if insufficient data.
    """
    from scipy import stats as scipy_stats

    df = compute_alpha_scores(df, lambda_val=lambda_val)
    sub = df.dropna(subset=["alpha_score", return_col]).copy()

    quarters = sorted(sub["quarter"].unique())
    if len(quarters) < 3:
        return None

    ls_rets:    list[float] = []
    long_rets:  list[float] = []
    short_rets: list[float] = []
    n_longs:    list[int]   = []
    n_shorts:   list[int]   = []
    equity_curve: list[dict] = []

    prev_long_names:  set = set()
    prev_short_names: set = set()
    turnovers: list[float] = []

    nav = 1.0

    for q in quarters:
        qdf = sub[sub["quarter"] == q].sort_values("alpha_score")
        n   = len(qdf)
        if n < 5:
            continue

        k = max(1, int(np.ceil(n * top_pct)))

        long_df  = qdf.iloc[-k:]   # top k by AlphaScore
        short_df = qdf.iloc[:k]    # bottom k by AlphaScore

        long_names  = set(long_df["ticker"])
        short_names = set(short_df["ticker"])

        # Turnover
        if prev_long_names or prev_short_names:
            all_prev = prev_long_names | prev_short_names
            all_curr = long_names | short_names
            unchanged = len(all_prev & all_curr)
            turnover  = 1.0 - unchanged / max(len(all_prev), 1)
            turnovers.append(turnover)

        prev_long_names  = long_names
        prev_short_names = short_names

        long_ret  = float(long_df[return_col].mean())
        short_ret = float(short_df[return_col].mean())
        ls_ret    = long_ret - short_ret

        ls_rets.append(ls_ret)
        long_rets.append(long_ret)
        short_rets.append(short_ret)
        n_longs.append(k)
        n_shorts.append(k)

        nav *= (1 + ls_ret)
        peak_nav = max(1.0, nav)  # simplified running peak
        equity_curve.append({
            "quarter":   q,
            "long_ret":  round(long_ret, 5),
            "short_ret": round(short_ret, 5),
            "ls_ret":    round(ls_ret, 5),
            "nav_ls":    round(nav, 5),
        })

    if len(ls_rets) < 3:
        return None

    arr = np.array(ls_rets)
    ann_ret = float(np.mean(arr)) * 4          # 4 quarters/year
    ann_vol = float(np.std(arr, ddof=1)) * np.sqrt(4)
    sharpe  = ann_ret / max(ann_vol, 1e-9)
    mdd     = _max_drawdown(arr)
    hit     = float(np.mean(arr > 0))
    calmar  = ann_ret / max(abs(mdd), 1e-9)

    # IC of AlphaScore vs return
    alpha_vals = sub["alpha_score"].values
    ret_vals   = sub[return_col].values
    mask = ~(np.isnan(alpha_vals) | np.isnan(ret_vals))
    ic_1d = float(scipy_stats.spearmanr(alpha_vals[mask], ret_vals[mask]).correlation) if mask.sum() >= 5 else 0.0

    ic_5d = 0.0
    if "five_day_return" in sub.columns:
        r5 = sub["five_day_return"].values
        m5 = ~(np.isnan(alpha_vals) | np.isnan(r5))
        if m5.sum() >= 5:
            ic_5d = float(scipy_stats.spearmanr(alpha_vals[m5], r5[m5]).correlation)

    return PortfolioResult(
        lambda_val=lambda_val,
        top_pct=top_pct,
        ann_return_ls=round(ann_ret, 4),
        ann_vol_ls=round(ann_vol, 4),
        sharpe_ls=round(sharpe, 3),
        max_drawdown=round(mdd, 4),
        hit_rate=round(hit, 3),
        calmar_ratio=round(calmar, 3),
        mean_long_ret=round(float(np.mean(long_rets)), 5),
        mean_short_ret=round(float(np.mean(short_rets)), 5),
        mean_ls_spread=round(float(np.mean(arr)), 5),
        avg_turnover=round(float(np.mean(turnovers)) if turnovers else 0.0, 3),
        avg_n_long=round(float(np.mean(n_longs)), 1),
        avg_n_short=round(float(np.mean(n_shorts)), 1),
        ic_alpha_1d=round(ic_1d, 4),
        ic_alpha_5d=round(ic_5d, 4),
        equity_curve=equity_curve,
    )


def ic_decay_curve(
    df: pd.DataFrame,
    signal_col: str = "mci",
) -> list[dict]:
    """
    Compute IC at each available return horizon (1d, 5d, 30d).
    Returns list of {horizon, ic, n} for plotting IC decay.
    """
    from scipy import stats as scipy_stats

    horizons = [
        (1,  "next_day_return",   "1d"),
        (5,  "five_day_return",   "5d"),
        (30, "thirty_day_return", "30d"),
    ]

    results = []
    for days, col, label in horizons:
        if col not in df.columns:
            continue
        sub  = df[[signal_col, col]].dropna()
        if len(sub) < 10:
            continue
        ic, _ = scipy_stats.spearmanr(sub[signal_col].values, sub[col].values)
        results.append({
            "label":  label,
            "days":   days,
            "ic":     round(float(ic), 4),
            "n":      int(len(sub)),
        })
    return results


def ic_by_sector(
    df: pd.DataFrame,
    signal_col: str = "mci",
    return_col: str = "next_day_return",
) -> list[dict]:
    """
    Compute IC per sector. Requires 'sector' column or looks up from ticker.
    """
    from scipy import stats as scipy_stats
    from src.data.sectors import get_sector

    df = df.copy()
    if "sector" not in df.columns:
        df["sector"] = df["ticker"].map(get_sector)

    results = []
    for sector, grp in df.groupby("sector"):
        sub = grp[[signal_col, return_col]].dropna()
        if len(sub) < 8:
            continue
        ic, _ = scipy_stats.spearmanr(sub[signal_col].values, sub[return_col].values)
        results.append({
            "sector": sector,
            "ic":     round(float(ic), 4),
            "n":      int(len(sub)),
        })

    return sorted(results, key=lambda x: -abs(x["ic"]))


def ic_by_regime(
    df: pd.DataFrame,
    signal_col: str = "mci",
    return_col: str = "next_day_return",
) -> list[dict]:
    """
    Regime detection using cross-sectional return dispersion per quarter.
    High-vol regime = quarters where abs(return) std is in top tercile.
    Returns IC broken down by: bull, bear, high_vol, low_vol regimes.
    """
    from scipy import stats as scipy_stats

    df = df.copy()

    # Compute per-quarter stats
    q_stats = (
        df.groupby("quarter")[return_col]
        .agg(median_ret="median", vol=lambda x: x.std())
        .reset_index()
    )
    vol_33  = q_stats["vol"].quantile(0.33)
    vol_67  = q_stats["vol"].quantile(0.67)

    def _regime(row):
        if row["vol"] >= vol_67:
            return "high_vol"
        if row["vol"] <= vol_33:
            return "low_vol"
        if row["median_ret"] > 0:
            return "bull"
        return "bear"

    q_stats["regime"] = q_stats.apply(_regime, axis=1)
    df = df.merge(q_stats[["quarter", "regime"]], on="quarter", how="left")

    results = []
    for regime, grp in df.groupby("regime"):
        sub = grp[[signal_col, return_col]].dropna()
        if len(sub) < 8:
            continue
        ic, _ = scipy_stats.spearmanr(sub[signal_col].values, sub[return_col].values)
        results.append({
            "regime": regime,
            "ic":     round(float(ic), 4),
            "n":      int(len(sub)),
        })

    return results
