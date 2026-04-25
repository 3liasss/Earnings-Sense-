"""
EarningsSense — Hedge fund-grade backtest + factor validation engine.

Layer 1 — Alpha Engine:
  IC/ICIR per quarter, tone-shift features, volatility target,
  long-short simulation, OLS, Ridge, Random Forest.

Layer 2 — Factor Validation:
  Fama-MacBeth cross-sectional regression (priced factor test),
  IC decay curves (1d->5d->30d signal persistence),
  IC by sector, IC by regime (bull/bear/high-vol/low-vol),
  AlphaScore composite portfolio (L/S 20%, drawdown, turnover, Calmar).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


@dataclass
class BacktestMetrics:
    n_obs: int
    n_quarters: int
    n_tickers: int
    date_range: str

    # Layer 1: IC / ICIR
    ic_mci_1d:    float
    ic_drs_1d:    float
    ic_mci_5d:    float
    ic_drs_5d:    float
    ic_hedge_1d:  float
    icir_mci_1d:  float
    icir_drs_1d:  float
    icir_mci_5d:  float
    icir_drs_5d:  float

    # Tone-shift IC
    ic_dmci_1d:   float
    ic_ddrs_1d:   float
    ic_dmci_5d:   float
    ic_ddrs_5d:   float

    # Volatility target
    ic_drs_vol:   float
    ic_mci_vol:   float

    # Long-short (tercile)
    ls_mean_1d:   float
    ls_hit_1d:    float
    ls_sharpe_1d: float
    ls_mean_5d:   float
    ls_hit_5d:    float
    ls_sharpe_5d: float

    # Lag
    lag_ic_drs:   float
    lag_ic_mci:   float
    lag_p_drs:    float

    # OLS
    ols_mci_coef: float
    ols_mci_pval: float
    ols_drs_coef: float
    ols_drs_pval: float
    ols_r2:       float

    # Ridge
    ridge_r2_1d:  float
    ridge_r2_5d:  float
    ridge_coefs:  dict

    # Random Forest
    rf_r2_1d:       float
    rf_r2_5d:       float
    rf_importances: dict

    # Per-quarter IC series
    ic_series: list[dict] = field(default_factory=list)
    ls_series: list[dict] = field(default_factory=list)

    # Layer 2: Fama-MacBeth
    fm_beta_mci:    float = 0.0
    fm_beta_drs:    float = 0.0
    fm_beta_dmci:   float = 0.0
    fm_beta_ddrs:   float = 0.0
    fm_tstat_mci:   float = 0.0
    fm_tstat_drs:   float = 0.0
    fm_tstat_dmci:  float = 0.0
    fm_tstat_ddrs:  float = 0.0
    fm_pval_mci:    float = 1.0
    fm_pval_drs:    float = 1.0
    fm_pval_dmci:   float = 1.0
    fm_pval_ddrs:   float = 1.0
    fm_avg_r2:      float = 0.0
    fm_beta_series: list[dict] = field(default_factory=list)

    # Layer 2: AlphaScore portfolio
    port_ann_return:   float = 0.0
    port_ann_vol:      float = 0.0
    port_sharpe:       float = 0.0
    port_max_dd:       float = 0.0
    port_hit_rate:     float = 0.0
    port_calmar:       float = 0.0
    port_turnover:     float = 0.0
    port_ic_alpha_1d:  float = 0.0
    port_ic_alpha_5d:  float = 0.0
    port_equity_curve: list[dict] = field(default_factory=list)

    # Layer 2: IC decay / sector / regime
    ic_decay_mci: list[dict] = field(default_factory=list)
    ic_decay_drs: list[dict] = field(default_factory=list)
    ic_by_sector: list[dict] = field(default_factory=list)
    ic_by_regime: list[dict] = field(default_factory=list)


def _spearman_ic(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 5:
        return 0.0, 1.0
    r, p = scipy_stats.spearmanr(x[mask], y[mask])
    return float(r), float(p)


def _mean_icir(df: pd.DataFrame, signal_col: str, target_col: str) -> tuple[float, float]:
    ics = []
    for q in df["quarter"].unique():
        qdf = df[df["quarter"] == q].dropna(subset=[signal_col, target_col])
        if len(qdf) < 5:
            continue
        ic, _ = _spearman_ic(qdf[signal_col].values, qdf[target_col].values)
        ics.append(ic)
    if not ics:
        return 0.0, 0.0
    arr  = np.array(ics)
    mean = float(np.mean(arr))
    icir = mean / (float(np.std(arr)) + 1e-9) if len(arr) > 1 else 0.0
    return round(mean, 4), round(icir, 3)


def _long_short(df: pd.DataFrame, signal_col: str, return_col: str) -> tuple[float, float, float, list[dict]]:
    quarters = sorted(df["quarter"].unique())
    ls_rets, ls_labels = [], []
    for q in quarters:
        qdf = df[df["quarter"] == q].dropna(subset=[signal_col, return_col])
        if len(qdf) < 6:
            continue
        qdf_s  = qdf.sort_values(signal_col)
        t      = max(1, len(qdf_s) // 3)
        long_r = qdf_s.iloc[-t:][return_col].mean()
        shrt_r = qdf_s.iloc[:t][return_col].mean()
        ls_rets.append(long_r - shrt_r)
        ls_labels.append(q)
    if not ls_rets:
        return 0.0, 0.0, 0.0, []
    arr    = np.array(ls_rets)
    mean   = float(np.mean(arr))
    hit    = float(np.mean(arr > 0))
    sharpe = mean / (float(np.std(arr)) + 1e-9) * np.sqrt(4) if len(arr) > 1 else 0.0
    series = [{"quarter": q, "ls_return": round(r, 5)} for q, r in zip(ls_labels, ls_rets)]
    return round(mean, 5), round(hit, 3), round(sharpe, 3), series


def _add_tone_shift(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["ticker", "report_date"]).copy()
    for col in ["mci", "drs", "hedge_density", "certainty_ratio"]:
        if col in df.columns:
            df[f"d_{col}"] = df.groupby("ticker")[col].diff()
    return df


def _add_volatility(df: pd.DataFrame) -> pd.DataFrame:
    if "price_series" not in df.columns:
        df["realised_vol_post"] = np.nan
        df["vol_change"]        = np.nan
        return df
    vol_posts, vol_changes = [], []
    for _, row in df.iterrows():
        try:
            ps = row["price_series"]
            if not ps or len(ps) < 5:
                raise ValueError
            closes = np.array([p["close"] for p in ps])
            rets   = np.diff(closes) / closes[:-1]
            n, mid = len(rets), len(rets) // 2
            pre_v  = float(np.std(rets[:mid])) * np.sqrt(252) if mid > 2 else np.nan
            post_v = float(np.std(rets[mid:])) * np.sqrt(252) if n - mid > 2 else np.nan
            vol_posts.append(post_v)
            vol_changes.append(post_v - pre_v if (post_v and pre_v) else np.nan)
        except Exception:
            vol_posts.append(np.nan)
            vol_changes.append(np.nan)
    df = df.copy()
    df["realised_vol_post"] = vol_posts
    df["vol_change"]        = vol_changes
    return df


FEATURE_COLS = [
    "mci", "drs", "hedge_density", "certainty_ratio",
    "passive_voice_ratio", "vague_language_score",
    "d_mci", "d_drs", "d_hedge_density",
]


def _ml_models(df: pd.DataFrame, target: str) -> tuple[float, float, dict, dict]:
    from sklearn.linear_model  import RidgeCV
    from sklearn.ensemble       import RandomForestRegressor
    from sklearn.preprocessing  import StandardScaler
    from sklearn.pipeline       import Pipeline
    feat_cols = [c for c in FEATURE_COLS if c in df.columns]
    sub = df[feat_cols + [target, "quarter"]].dropna()
    if len(sub) < 30:
        return 0.0, 0.0, {}, {}
    X = sub[feat_cols].values
    y = sub[target].values
    split = int(len(sub) * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]
    if len(X_te) < 5:
        return 0.0, 0.0, {}, {}
    try:
        pipe = Pipeline([("scaler", StandardScaler()), ("ridge", RidgeCV(alphas=[0.01,0.1,1,10,100]))])
        pipe.fit(X_tr, y_tr)
        ridge_r2    = float(pipe.score(X_te, y_te))
        ridge_coefs = {f: round(float(c), 6) for f, c in zip(feat_cols, pipe.named_steps["ridge"].coef_)}
    except Exception:
        ridge_r2, ridge_coefs = 0.0, {}
    try:
        rf = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=5, random_state=42, n_jobs=-1)
        rf.fit(X_tr, y_tr)
        rf_r2 = float(rf.score(X_te, y_te))
        rf_imp = {f: round(float(i), 4) for f, i in zip(feat_cols, rf.feature_importances_)}
    except Exception:
        rf_r2, rf_imp = 0.0, {}
    return round(ridge_r2, 4), round(rf_r2, 4), ridge_coefs, rf_imp


def compute_metrics(df: pd.DataFrame) -> BacktestMetrics:
    df = df.copy()
    df = _add_tone_shift(df)
    df = _add_volatility(df)

    df_1d = df.dropna(subset=["mci", "drs", "next_day_return"])
    df_5d = df.dropna(subset=["mci", "drs", "five_day_return"]) if "five_day_return" in df.columns else pd.DataFrame()

    if len(df_1d) < 10:
        raise ValueError(f"Insufficient data: {len(df_1d)} obs (need >=10)")

    quarters   = sorted(df_1d["quarter"].unique())
    date_range = f"{df_1d['report_date'].min()} to {df_1d['report_date'].max()}"

    ic_mci_1d,  icir_mci_1d  = _mean_icir(df_1d, "mci",           "next_day_return")
    ic_drs_1d,  icir_drs_1d  = _mean_icir(df_1d, "drs",           "next_day_return")
    ic_hedge_1d, _            = _mean_icir(df_1d, "hedge_density", "next_day_return")
    ic_dmci_1d, _             = _mean_icir(df_1d, "d_mci",         "next_day_return")
    ic_ddrs_1d, _             = _mean_icir(df_1d, "d_drs",         "next_day_return")

    ic_mci_5d = ic_drs_5d = icir_mci_5d = icir_drs_5d = ic_dmci_5d = ic_ddrs_5d = 0.0
    if not df_5d.empty:
        ic_mci_5d,  icir_mci_5d  = _mean_icir(df_5d, "mci", "five_day_return")
        ic_drs_5d,  icir_drs_5d  = _mean_icir(df_5d, "drs", "five_day_return")
        ic_dmci_5d, _            = _mean_icir(df_5d, "d_mci", "five_day_return")
        ic_ddrs_5d, _            = _mean_icir(df_5d, "d_drs", "five_day_return")

    ic_drs_vol = ic_mci_vol = 0.0
    df_vol = df_1d.dropna(subset=["vol_change"])
    if len(df_vol) >= 10:
        ic_drs_vol, _ = _mean_icir(df_vol, "drs", "vol_change")
        ic_mci_vol, _ = _mean_icir(df_vol, "mci", "vol_change")

    ls_m1, ls_h1, ls_s1, ls_ser1 = _long_short(df_1d, "mci", "next_day_return")
    ls_m5 = ls_h5 = ls_s5 = 0.0
    if not df_5d.empty:
        ls_m5, ls_h5, ls_s5, _ = _long_short(df_5d, "mci", "five_day_return")

    lag_ic_drs = lag_ic_mci = lag_p_drs = 0.0
    try:
        dl = df_1d.sort_values(["ticker", "report_date"]).copy()
        dl["nrl"] = dl.groupby("ticker")["next_day_return"].shift(-1)
        dlv = dl.dropna(subset=["nrl"])
        if len(dlv) >= 15:
            lag_ic_drs, lag_p_drs = _spearman_ic(dlv["drs"].values, dlv["nrl"].values)
            lag_ic_mci, _         = _spearman_ic(dlv["mci"].values, dlv["nrl"].values)
    except Exception:
        pass

    ols_mci_coef = ols_mci_pval = ols_drs_coef = ols_drs_pval = ols_r2 = 0.0
    try:
        import statsmodels.api as sm
        X   = sm.add_constant(df_1d[["mci", "drs"]].values)
        res = sm.OLS(df_1d["next_day_return"].values, X).fit()
        ols_mci_coef, ols_drs_coef = float(res.params[1]), float(res.params[2])
        ols_mci_pval, ols_drs_pval = float(res.pvalues[1]), float(res.pvalues[2])
        ols_r2 = float(res.rsquared)
    except Exception:
        pass

    ridge_r2_1d, rf_r2_1d, ridge_coefs, rf_imp = _ml_models(df_1d, "next_day_return")
    ridge_r2_5d = rf_r2_5d = 0.0
    if not df_5d.empty:
        ridge_r2_5d, rf_r2_5d, _, _ = _ml_models(df_5d, "five_day_return")

    ic_records = []
    for q in quarters:
        qdf = df_1d[df_1d["quarter"] == q]
        if len(qdf) < 4:
            continue
        im, _ = _spearman_ic(qdf["mci"].values, qdf["next_day_return"].values)
        id_, _ = _spearman_ic(qdf["drs"].values, qdf["next_day_return"].values)
        ih, _ = _spearman_ic(qdf["hedge_density"].values, qdf["next_day_return"].values)
        ic_records.append({"quarter": q, "ic_mci": round(im,3), "ic_drs": round(id_,3), "ic_hedge": round(ih,3), "n": len(qdf)})

    # Layer 2: Fama-MacBeth
    fm_fields = dict(fm_beta_mci=0.0, fm_beta_drs=0.0, fm_beta_dmci=0.0, fm_beta_ddrs=0.0,
                     fm_tstat_mci=0.0, fm_tstat_drs=0.0, fm_tstat_dmci=0.0, fm_tstat_ddrs=0.0,
                     fm_pval_mci=1.0, fm_pval_drs=1.0, fm_pval_dmci=1.0, fm_pval_ddrs=1.0,
                     fm_avg_r2=0.0, fm_beta_series=[])
    try:
        from src.analysis.fama_macbeth import run_fama_macbeth
        fm = run_fama_macbeth(df_1d)
        if fm:
            fm_fields = dict(
                fm_beta_mci=fm.beta_mci, fm_beta_drs=fm.beta_drs,
                fm_beta_dmci=fm.beta_dmci, fm_beta_ddrs=fm.beta_ddrs,
                fm_tstat_mci=fm.tstat_mci, fm_tstat_drs=fm.tstat_drs,
                fm_tstat_dmci=fm.tstat_dmci, fm_tstat_ddrs=fm.tstat_ddrs,
                fm_pval_mci=fm.pval_mci, fm_pval_drs=fm.pval_drs,
                fm_pval_dmci=fm.pval_dmci, fm_pval_ddrs=fm.pval_ddrs,
                fm_avg_r2=fm.avg_r2, fm_beta_series=fm.beta_series)
    except Exception:
        pass

    # Layer 2: AlphaScore portfolio
    port_fields = dict(port_ann_return=0.0, port_ann_vol=0.0, port_sharpe=0.0,
                       port_max_dd=0.0, port_hit_rate=0.0, port_calmar=0.0,
                       port_turnover=0.0, port_ic_alpha_1d=0.0, port_ic_alpha_5d=0.0,
                       port_equity_curve=[])
    try:
        from src.analysis.portfolio import construct_portfolio
        port = construct_portfolio(df_1d)
        if port:
            port_fields = dict(
                port_ann_return=port.ann_return_ls, port_ann_vol=port.ann_vol_ls,
                port_sharpe=port.sharpe_ls, port_max_dd=port.max_drawdown,
                port_hit_rate=port.hit_rate, port_calmar=port.calmar_ratio,
                port_turnover=port.avg_turnover, port_ic_alpha_1d=port.ic_alpha_1d,
                port_ic_alpha_5d=port.ic_alpha_5d, port_equity_curve=port.equity_curve)
    except Exception:
        pass

    # Layer 2: IC decay / sector / regime
    ic_decay_mci = ic_decay_drs = ic_sector = ic_regime = []
    try:
        from src.analysis.portfolio import ic_decay_curve, ic_by_sector, ic_by_regime
        ic_decay_mci = ic_decay_curve(df, "mci")
        ic_decay_drs = ic_decay_curve(df, "drs")
        ic_sector    = ic_by_sector(df_1d)
        ic_regime    = ic_by_regime(df_1d)
    except Exception:
        pass

    return BacktestMetrics(
        n_obs=len(df_1d), n_quarters=len(quarters),
        n_tickers=df_1d["ticker"].nunique(), date_range=date_range,
        ic_mci_1d=ic_mci_1d, ic_drs_1d=ic_drs_1d,
        ic_mci_5d=ic_mci_5d, ic_drs_5d=ic_drs_5d, ic_hedge_1d=ic_hedge_1d,
        icir_mci_1d=icir_mci_1d, icir_drs_1d=icir_drs_1d,
        icir_mci_5d=icir_mci_5d, icir_drs_5d=icir_drs_5d,
        ic_dmci_1d=ic_dmci_1d, ic_ddrs_1d=ic_ddrs_1d,
        ic_dmci_5d=ic_dmci_5d, ic_ddrs_5d=ic_ddrs_5d,
        ic_drs_vol=ic_drs_vol, ic_mci_vol=ic_mci_vol,
        ls_mean_1d=ls_m1, ls_hit_1d=ls_h1, ls_sharpe_1d=ls_s1,
        ls_mean_5d=ls_m5, ls_hit_5d=ls_h5, ls_sharpe_5d=ls_s5,
        lag_ic_drs=round(lag_ic_drs,4), lag_ic_mci=round(lag_ic_mci,4), lag_p_drs=round(lag_p_drs,4),
        ols_mci_coef=round(ols_mci_coef,6), ols_mci_pval=round(ols_mci_pval,4),
        ols_drs_coef=round(ols_drs_coef,6), ols_drs_pval=round(ols_drs_pval,4), ols_r2=round(ols_r2,4),
        ridge_r2_1d=ridge_r2_1d, ridge_r2_5d=ridge_r2_5d, ridge_coefs=ridge_coefs,
        rf_r2_1d=rf_r2_1d, rf_r2_5d=rf_r2_5d, rf_importances=rf_imp,
        ic_series=ic_records, ls_series=ls_ser1,
        **fm_fields, **port_fields,
        ic_decay_mci=ic_decay_mci, ic_decay_drs=ic_decay_drs,
        ic_by_sector=ic_sector, ic_by_regime=ic_regime,
    )


def ic_label(ic: float) -> str:
    a = abs(ic)
    if a >= 0.10: return "Strong"
    if a >= 0.05: return "Meaningful"
    if a >= 0.02: return "Weak"
    return "Negligible"

def icir_label(icir: float) -> str:
    a = abs(icir)
    if a >= 1.0: return "Strong"
    if a >= 0.5: return "Moderate"
    return "Weak"
