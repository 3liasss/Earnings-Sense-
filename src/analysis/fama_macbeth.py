"""
Fama-MacBeth cross-sectional regression engine.

Procedure:
  1. Each quarter t: regress returns on z-scored signals cross-sectionally
        AR(i,t) = β0 + β1*z(MCI) + β2*z(DRS) + β3*z(ΔMCI) + β4*z(ΔDRS) + ε
  2. Collect time series of betas: {β1_t, β2_t, ...}
  3. Factor premium = mean(βk) over T quarters
  4. FM t-stat = mean(βk) / (std(βk) / sqrt(T))   ← Newey-West if T >= 8
  5. p-value from t-distribution with T-1 degrees of freedom

Result tells you: "Is this a priced factor, or lucky noise?"
  |t| > 1.96 → significant at 5%
  |t| > 2.58 → significant at 1%
  Stable β time-series → factor is consistent, not regime-dependent
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


@dataclass
class FamaMacBethResult:
    # ── Factor premiums (mean cross-sectional beta over T quarters) ────────────
    beta_mci:  float   # >0 = confident language earns positive return premium
    beta_drs:  float   # <0 = evasive language earns negative premium (good sign)
    beta_dmci: float   # >0 = tone improving → premium
    beta_ddrs: float   # <0 = risk rising → premium negative

    # ── Fama-MacBeth t-statistics ──────────────────────────────────────────────
    tstat_mci:  float
    tstat_drs:  float
    tstat_dmci: float
    tstat_ddrs: float

    # ── p-values (two-tailed) ─────────────────────────────────────────────────
    pval_mci:  float
    pval_drs:  float
    pval_dmci: float
    pval_ddrs: float

    # ── Average cross-sectional R² ────────────────────────────────────────────
    avg_r2: float

    # ── Dataset stats ─────────────────────────────────────────────────────────
    n_quarters: int
    n_obs: int

    # ── Beta time-series (for stability chart) ────────────────────────────────
    beta_series: list[dict] = field(default_factory=list)


def _newey_west_se(betas: np.ndarray, max_lag: int = 2) -> float:
    """Newey-West HAC standard error for a time series of estimates."""
    T  = len(betas)
    mu = np.mean(betas)
    e  = betas - mu
    # Bartlett kernel
    nw_var = np.sum(e ** 2) / T
    for lag in range(1, min(max_lag + 1, T)):
        weight  = 1.0 - lag / (max_lag + 1)
        nw_var += 2 * weight * np.sum(e[lag:] * e[:-lag]) / T
    return float(np.sqrt(max(nw_var / T, 1e-16)))


def run_fama_macbeth(
    df: pd.DataFrame,
    target: str = "next_day_return",
    use_newey_west: bool = True,
) -> Optional[FamaMacBethResult]:
    """
    Run Fama-MacBeth on the given DataFrame.

    Required columns: ticker, quarter, report_date, mci, drs, <target>
    Optional:         d_mci, d_drs (computed here if missing)
    """
    try:
        import statsmodels.api as sm
    except ImportError:
        sm = None

    df = df.copy().sort_values(["ticker", "report_date"])

    # Add tone-shift if missing
    for col in ["mci", "drs"]:
        dc = f"d_{col}"
        if dc not in df.columns:
            df[dc] = df.groupby("ticker")[col].diff()

    FEATURES = ["mci", "drs", "d_mci", "d_drs"]
    needed   = FEATURES + [target, "quarter"]
    sub      = df[needed].dropna()

    if len(sub) < 20:
        return None

    quarters = sorted(sub["quarter"].unique())

    betas: dict[str, list[float]] = {f: [] for f in FEATURES}
    r2s: list[float] = []
    beta_series: list[dict] = []

    for q in quarters:
        qdf = sub[sub["quarter"] == q].copy()
        if len(qdf) < 5:
            continue

        # Cross-sectional z-score within this quarter
        X_raw = qdf[FEATURES].values.astype(float)
        mu    = X_raw.mean(axis=0)
        sd    = X_raw.std(axis=0)
        sd[sd < 1e-9] = 1.0
        X_z   = (X_raw - mu) / sd

        y = qdf[target].values.astype(float)

        try:
            if sm is not None:
                res  = sm.OLS(y, sm.add_constant(X_z)).fit()
                coef = res.params[1:]
                r2   = float(res.rsquared)
            else:
                from sklearn.linear_model import LinearRegression
                reg  = LinearRegression().fit(X_z, y)
                coef = reg.coef_
                r2   = float(reg.score(X_z, y))
        except Exception:
            continue

        if len(coef) < 4:
            continue

        for i, f in enumerate(FEATURES):
            betas[f].append(float(coef[i]))
        r2s.append(r2)
        beta_series.append({
            "quarter":    q,
            "beta_mci":  round(float(coef[0]), 6),
            "beta_drs":  round(float(coef[1]), 6),
            "beta_dmci": round(float(coef[2]), 6),
            "beta_ddrs": round(float(coef[3]), 6),
            "r2":        round(r2, 4),
            "n":         int(len(qdf)),
        })

    T = len(betas["mci"])
    if T < 3:
        return None

    def _fm_stat(key: str) -> tuple[float, float, float]:
        arr  = np.array(betas[key])
        mean = float(np.mean(arr))
        if use_newey_west and T >= 8:
            se = _newey_west_se(arr)
        else:
            se = float(np.std(arr, ddof=1)) / np.sqrt(T)
        se   = max(se, 1e-12)
        tval = mean / se
        pval = float(2 * scipy_stats.t.sf(abs(tval), df=T - 1))
        return round(mean, 6), round(tval, 3), round(pval, 4)

    m_mci,  t_mci,  p_mci  = _fm_stat("mci")
    m_drs,  t_drs,  p_drs  = _fm_stat("drs")
    m_dmci, t_dmci, p_dmci = _fm_stat("d_mci")
    m_ddrs, t_ddrs, p_ddrs = _fm_stat("d_drs")

    return FamaMacBethResult(
        beta_mci=m_mci,    beta_drs=m_drs,
        beta_dmci=m_dmci,  beta_ddrs=m_ddrs,
        tstat_mci=t_mci,   tstat_drs=t_drs,
        tstat_dmci=t_dmci, tstat_ddrs=t_ddrs,
        pval_mci=p_mci,    pval_drs=p_drs,
        pval_dmci=p_dmci,  pval_ddrs=p_ddrs,
        avg_r2=round(float(np.mean(r2s)), 4) if r2s else 0.0,
        n_quarters=T,
        n_obs=int(len(sub)),
        beta_series=beta_series,
    )
