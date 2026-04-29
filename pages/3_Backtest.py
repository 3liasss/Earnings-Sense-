"""
EarningsSense - Research-Grade Signal Validation page.

Displays institutional-grade backtest metrics computed across 500-2000+
10-Q filings from S&P 500 companies spanning up to 8 years.

Run scripts/run_backtest.py first to generate data/backtest/results.csv.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Backtest - EarningsSense", layout="wide")

from src.ui.sidebar import inject_sidebar_style, render_sidebar_branding
inject_sidebar_style()
render_sidebar_branding()

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
.metric-card {
    background: #1e293b; border: 1px solid #334155;
    border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 0.75rem;
    text-align: center;
}
.section-header {
    color: #f1f5f9; font-size: 1.1rem; font-weight: 600;
    margin: 1.25rem 0 0.4rem 0;
}
h1,h2,h3 { color: #f1f5f9 !important; }
</style>
""", unsafe_allow_html=True)

COLORS = {
    "mci":     "#3b82f6",
    "drs":     "#ef4444",
    "hedge":   "#f97316",
    "ridge":   "#a855f7",
    "rf":      "#10b981",
    "surface": "#1e293b",
    "border":  "#334155",
    "green":   "#22c55e",
    "muted":   "#94a3b8",
    "bg":      "#0f172a",
}

RESULTS_CSV  = Path("data/backtest/results.csv")
METRICS_JSON = Path("data/backtest/metrics.json")

st.title("Signal Validation - Backtest")
st.markdown(
    "<div style='color:#94a3b8;margin-bottom:1rem;'>"
    "Research-grade signal quality metrics computed across S&amp;P 500 10-Q filings "
    "(8 years · 65 tickers · 32 quarters max). "
    "IC, ICIR, tone-shift, volatility target, Ridge + Random Forest.</div>",
    unsafe_allow_html=True,
)

# ── Load data ─────────────────────────────────────────────────────────────────

if not RESULTS_CSV.exists():
    st.warning(
        "No backtest data found. Run the data collection script first:\n\n"
        "```bash\npython scripts/run_backtest.py\n```\n\n"
        "This fetches up to 32 quarters of 10-Q data for 65 S&P 500 companies "
        "and takes 20-40 minutes (EDGAR rate-limited). Safe to interrupt and resume."
    )
    st.stop()

@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(RESULTS_CSV)
    m  = json.loads(METRICS_JSON.read_text()) if METRICS_JSON.exists() else None
    return df, m

df_raw, metrics = load_data()

df = df_raw.dropna(subset=["mci", "drs", "next_day_return"]).copy()

if len(df) < 10:
    st.error(f"Only {len(df)} observations with price data. Need ≥10 to compute metrics.")
    st.stop()

if metrics is None:
    from src.analysis.backtest_engine import compute_metrics
    metrics = vars(compute_metrics(df))

# ── Helper display functions ──────────────────────────────────────────────────

def _ic_color(ic: float) -> str:
    a = abs(ic)
    if a >= 0.10: return COLORS["green"]
    if a >= 0.05: return COLORS["mci"]
    if a >= 0.02: return COLORS["hedge"]
    return COLORS["muted"]

def _ic_label(ic: float) -> str:
    a = abs(ic)
    if a >= 0.10: return "Strong"
    if a >= 0.05: return "Meaningful"
    if a >= 0.02: return "Weak"
    return "Negligible"

def _icir_color(v: float) -> str:
    a = abs(v)
    if a >= 1.0: return COLORS["green"]
    if a >= 0.5: return COLORS["mci"]
    return COLORS["muted"]

def _metric_card(col, label: str, value: str, sub: str, color: str):
    with col:
        st.markdown(
            f"<div class='metric-card'>"
            f"<div style='color:#64748b;font-size:.72rem;'>{label}</div>"
            f"<div style='color:{color};font-size:1.75rem;font-weight:700;'>{value}</div>"
            f"<div style='color:#475569;font-size:.7rem;'>{sub}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

# Convenience aliases
m = metrics

# ── Dataset summary ───────────────────────────────────────────────────────────

st.markdown(
    f"<div style='color:#64748b;font-size:.82rem;margin-bottom:1rem;'>"
    f"Dataset: <b style='color:#f1f5f9;'>{m['n_obs']}</b> observations · "
    f"<b style='color:#f1f5f9;'>{m['n_tickers']}</b> tickers · "
    f"<b style='color:#f1f5f9;'>{m['n_quarters']}</b> quarters · "
    f"<span style='color:#475569;'>{m.get('date_range', '')}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Section 1: Core IC / ICIR ─────────────────────────────────────────────────

st.markdown("<div class='section-header'>Core Signal Quality — IC &amp; ICIR</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='color:#64748b;font-size:.78rem;margin-bottom:.6rem;'>"
    "Spearman rank IC computed within each quarterly cohort. "
    "IC > 0.05 = meaningful alpha, > 0.10 = strong. "
    "ICIR measures consistency over time (> 0.5 acceptable, > 1.0 strong).</div>",
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
_metric_card(c1, "IC (MCI · 1d)",   f"{m['ic_mci_1d']:+.4f}",  _ic_label(m['ic_mci_1d']),    _ic_color(m['ic_mci_1d']))
_metric_card(c2, "IC (DRS · 1d)",   f"{m['ic_drs_1d']:+.4f}",  _ic_label(m['ic_drs_1d']),    _ic_color(m['ic_drs_1d']))
_metric_card(c3, "ICIR (MCI · 1d)", f"{m['icir_mci_1d']:+.3f}", "IC consistency",             _icir_color(m['icir_mci_1d']))
_metric_card(c4, "ICIR (DRS · 1d)", f"{m['icir_drs_1d']:+.3f}", "IC consistency",             _icir_color(m['icir_drs_1d']))

if m.get("ic_mci_5d", 0) or m.get("ic_drs_5d", 0):
    c5, c6, c7, c8 = st.columns(4)
    _metric_card(c5, "IC (MCI · 5d)",   f"{m['ic_mci_5d']:+.4f}",  _ic_label(m['ic_mci_5d']),   _ic_color(m['ic_mci_5d']))
    _metric_card(c6, "IC (DRS · 5d)",   f"{m['ic_drs_5d']:+.4f}",  _ic_label(m['ic_drs_5d']),   _ic_color(m['ic_drs_5d']))
    _metric_card(c7, "ICIR (MCI · 5d)", f"{m['icir_mci_5d']:+.3f}", "IC consistency",            _icir_color(m['icir_mci_5d']))
    _metric_card(c8, "ICIR (DRS · 5d)", f"{m['icir_drs_5d']:+.3f}", "IC consistency",            _icir_color(m['icir_drs_5d']))

# ── IC per quarter chart ──────────────────────────────────────────────────────

ic_series = m.get("ic_series", [])
if ic_series:
    st.markdown("<div class='section-header'>IC per Quarter</div>", unsafe_allow_html=True)
    ic_df    = pd.DataFrame(ic_series).sort_values("quarter")
    quarters = ic_df["quarter"].tolist()

    fig = go.Figure()
    fig.add_hline(y=0.05,  line=dict(color="#22c55e", width=1, dash="dot"))
    fig.add_hline(y=-0.05, line=dict(color="#ef4444", width=1, dash="dot"))
    fig.add_hline(y=0,     line=dict(color="#475569", width=1))
    fig.add_trace(go.Bar(
        x=quarters, y=ic_df["ic_mci"].tolist(), name="IC (MCI)",
        marker_color=[COLORS["mci"] if v >= 0 else "#64748b" for v in ic_df["ic_mci"]],
    ))
    fig.add_trace(go.Bar(
        x=quarters, y=ic_df["ic_drs"].tolist(), name="IC (DRS)",
        marker_color=[COLORS["drs"] if v < 0 else "#64748b" for v in ic_df["ic_drs"]],
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
        font=dict(color="#94a3b8", size=11), barmode="group",
        legend=dict(bgcolor="#1e293b", bordercolor="#334155"),
        xaxis=dict(gridcolor="#1e293b"),
        yaxis=dict(gridcolor="#1e293b", tickformat="+.3f", title="IC"),
        margin=dict(l=40, r=20, t=20, b=40), height=300,
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Section 2: Long-Short Simulation ─────────────────────────────────────────

st.markdown("<div class='section-header'>Long-Short Simulation</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='color:#64748b;font-size:.78rem;margin-bottom:.6rem;'>"
    "Each quarter: long top-tercile by MCI, short bottom-tercile. "
    "Annualised Sharpe assumes 4 earnings events per year.</div>",
    unsafe_allow_html=True,
)

ls1, ls2, ls3 = st.columns(3)
_metric_card(ls1, "L/S Return (1d)", f"{m['ls_mean_1d']*100:+.3f}%",
             f"Hit rate {m['ls_hit_1d']:.0%}", COLORS["green"] if m['ls_mean_1d'] > 0 else COLORS["drs"])
_metric_card(ls2, "L/S Sharpe (1d)", f"{m['ls_sharpe_1d']:.3f}",
             "Annualised", _icir_color(m['ls_sharpe_1d']))

if m.get("ls_mean_5d", 0) or m.get("ls_sharpe_5d", 0):
    _metric_card(ls3, "L/S Sharpe (5d)", f"{m['ls_sharpe_5d']:.3f}",
                 "5d horizon", _icir_color(m['ls_sharpe_5d']))

# L/S equity curve using ls_series
ls_series = m.get("ls_series", [])
if ls_series:
    ls_q   = [x["quarter"]   for x in ls_series]
    ls_r   = [x["ls_return"] for x in ls_series]
    cumret = list((pd.Series([1 + r for r in ls_r]).cumprod() - 1))

    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color="#475569", width=1))
    fig.add_trace(go.Bar(
        x=ls_q, y=[r * 100 for r in ls_r], name="Quarterly L/S",
        marker_color=[COLORS["green"] if r >= 0 else COLORS["drs"] for r in ls_r],
        yaxis="y2",
    ))
    fig.add_trace(go.Scatter(
        x=ls_q, y=[c * 100 for c in cumret],
        mode="lines+markers", line=dict(color=COLORS["mci"], width=2),
        marker=dict(size=5), name="Cumulative",
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
        font=dict(color="#94a3b8", size=11),
        yaxis=dict(title="Cumulative (%)", gridcolor="#1e293b", tickformat="+.1f"),
        yaxis2=dict(title="Quarterly (%)", overlaying="y", side="right",
                    showgrid=False, tickformat="+.1f"),
        xaxis=dict(gridcolor="#1e293b"),
        legend=dict(bgcolor="#1e293b", bordercolor="#334155"),
        margin=dict(l=40, r=60, t=20, b=40), height=300,
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Section 3: Tone-Shift IC ──────────────────────────────────────────────────

st.markdown("<div class='section-header'>Tone-Shift Features — &Delta;MCI &amp; &Delta;DRS</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='color:#64748b;font-size:.78rem;margin-bottom:.6rem;'>"
    "Change in MCI / DRS vs prior quarter for the same company. "
    "A deteriorating tone (negative ΔMCI) may predict worse returns independent of absolute level.</div>",
    unsafe_allow_html=True,
)

ts1, ts2, ts3, ts4 = st.columns(4)
_metric_card(ts1, "IC (ΔMCI · 1d)", f"{m['ic_dmci_1d']:+.4f}", _ic_label(m['ic_dmci_1d']), _ic_color(m['ic_dmci_1d']))
_metric_card(ts2, "IC (ΔDRS · 1d)", f"{m['ic_ddrs_1d']:+.4f}", _ic_label(m['ic_ddrs_1d']), _ic_color(m['ic_ddrs_1d']))
_metric_card(ts3, "IC (ΔMCI · 5d)", f"{m['ic_dmci_5d']:+.4f}", _ic_label(m['ic_dmci_5d']), _ic_color(m['ic_dmci_5d']))
_metric_card(ts4, "IC (ΔDRS · 5d)", f"{m['ic_ddrs_5d']:+.4f}", _ic_label(m['ic_ddrs_5d']), _ic_color(m['ic_ddrs_5d']))

st.markdown("---")

# ── Section 4: Volatility Target ─────────────────────────────────────────────

st.markdown("<div class='section-header'>Volatility Target — Does Language Predict Volatility?</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='color:#64748b;font-size:.78rem;margin-bottom:.6rem;'>"
    "Realised annualised vol post-earnings vs pre-earnings. "
    "IC (DRS vs vol_change): positive = evasive language predicts vol spikes.</div>",
    unsafe_allow_html=True,
)

v1, v2 = st.columns(2)
_metric_card(v1, "IC (DRS vs vol change)", f"{m['ic_drs_vol']:+.4f}",
             _ic_label(m['ic_drs_vol']), _ic_color(m['ic_drs_vol']))
_metric_card(v2, "IC (MCI vs vol change)", f"{m['ic_mci_vol']:+.4f}",
             _ic_label(m['ic_mci_vol']), _ic_color(m['ic_mci_vol']))

st.markdown("---")

# ── Section 5: Lag Analysis ───────────────────────────────────────────────────

st.markdown("<div class='section-header'>Leading Indicator — DRS(t) Predicting Return(t+1)?</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='color:#64748b;font-size:.78rem;margin-bottom:.6rem;'>"
    "Lag IC: correlation between DRS at earnings(t) and next-day return at earnings(t+1). "
    "Negative = today's high DRS signals worse reaction next quarter.</div>",
    unsafe_allow_html=True,
)

lag1, lag2 = st.columns(2)
sig_str = "statistically significant" if m["lag_p_drs"] < 0.05 else f"p = {m['lag_p_drs']:.3f}"
_metric_card(lag1, "Lag IC (DRS → t+1)", f"{m['lag_ic_drs']:+.4f}", sig_str, _ic_color(m['lag_ic_drs']))
_metric_card(lag2, "Lag IC (MCI → t+1)", f"{m['lag_ic_mci']:+.4f}", "leading indicator test", _ic_color(m['lag_ic_mci']))

# Lag scatter
try:
    df_lag = df.sort_values(["ticker", "report_date"]).copy()
    df_lag["lag_return"] = df_lag.groupby("ticker")["next_day_return"].shift(-1)
    df_lag_v = df_lag.dropna(subset=["drs", "lag_return"])
    if len(df_lag_v) >= 10:
        x_v = df_lag_v["drs"].values
        y_v = df_lag_v["lag_return"].values * 100
        fig = go.Figure()
        fig.add_hline(y=0, line=dict(color="#475569", width=1))
        try:
            mm, bb = np.polyfit(x_v, y_v, 1)
            xl = np.linspace(x_v.min(), x_v.max(), 50)
            fig.add_trace(go.Scatter(x=xl, y=mm*xl+bb, mode="lines",
                                     line=dict(color=COLORS["drs"], width=2, dash="dash"),
                                     showlegend=False))
        except Exception:
            pass
        fig.add_trace(go.Scatter(
            x=x_v, y=y_v, mode="markers",
            marker=dict(color=COLORS["drs"], size=5, opacity=0.6),
            text=df_lag_v["ticker"] + " " + df_lag_v["quarter"],
            hovertemplate="DRS(t): %{x:.1f}<br>Return(t+1): %{y:+.2f}%<br>%{text}<extra></extra>",
        ))
        fig.update_layout(
            paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
            font=dict(color="#94a3b8", size=11),
            xaxis=dict(title="DRS this quarter", gridcolor="#1e293b"),
            yaxis=dict(title="Next quarter return (%)", gridcolor="#1e293b", tickformat="+.1f"),
            margin=dict(l=40, r=20, t=20, b=40), height=280, showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.warning(f"Lag scatter: {e}")

st.markdown("---")

# ── Section 6: OLS Regression ─────────────────────────────────────────────────

st.markdown("<div class='section-header'>OLS Regression</div>", unsafe_allow_html=True)

ols_data = {
    "Signal":      ["MCI", "DRS"],
    "Coefficient": [m["ols_mci_coef"], m["ols_drs_coef"]],
    "p-value":     [m["ols_mci_pval"], m["ols_drs_pval"]],
    "Significant": ["Yes" if m["ols_mci_pval"] < 0.05 else "No",
                    "Yes" if m["ols_drs_pval"] < 0.05 else "No"],
}
ols_df = pd.DataFrame(ols_data)
ols_df["Coefficient"] = ols_df["Coefficient"].map("{:+.6f}".format)
ols_df["p-value"]     = ols_df["p-value"].map("{:.4f}".format)
st.dataframe(ols_df, use_container_width=False, hide_index=True)
st.markdown(
    f"<div style='color:#64748b;font-size:.77rem;'>R² = {m['ols_r2']:.4f} "
    f"(fraction of return variance explained by MCI + DRS)</div>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Section 7: ML Models ──────────────────────────────────────────────────────

st.markdown("<div class='section-header'>ML Models — Ridge &amp; Random Forest</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='color:#64748b;font-size:.78rem;margin-bottom:.6rem;'>"
    "Time-based 80/20 train/test split. Features: MCI, DRS, hedge density, "
    "certainty ratio, passive voice, vague language, tone-shift deltas. "
    "Out-of-sample R² on newest 20% of data.</div>",
    unsafe_allow_html=True,
)

ml1, ml2, ml3, ml4 = st.columns(4)
_metric_card(ml1, "Ridge R² (1d)", f"{m['ridge_r2_1d']:.4f}", "out-of-sample", COLORS["ridge"])
_metric_card(ml2, "Ridge R² (5d)", f"{m['ridge_r2_5d']:.4f}", "out-of-sample", COLORS["ridge"])
_metric_card(ml3, "RF R² (1d)",    f"{m['rf_r2_1d']:.4f}",   "out-of-sample", COLORS["rf"])
_metric_card(ml4, "RF R² (5d)",    f"{m['rf_r2_5d']:.4f}",   "out-of-sample", COLORS["rf"])

# Feature importance bar chart
rf_imp = m.get("rf_importances", {})
ridge_coefs = m.get("ridge_coefs", {})

if rf_imp:
    imp_sorted = sorted(rf_imp.items(), key=lambda x: -x[1])
    feat_names = [x[0] for x in imp_sorted]
    feat_vals  = [x[1] for x in imp_sorted]

    fig = go.Figure(go.Bar(
        x=feat_vals, y=feat_names,
        orientation="h",
        marker_color=COLORS["rf"],
        text=[f"{v:.3f}" for v in feat_vals],
        textposition="outside",
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
        font=dict(color="#94a3b8", size=11),
        title=dict(text="Random Forest Feature Importance", font=dict(color="#f1f5f9", size=13)),
        xaxis=dict(gridcolor="#1e293b", title="Importance"),
        yaxis=dict(gridcolor="#1e293b", autorange="reversed"),
        margin=dict(l=160, r=60, t=40, b=30), height=320,
    )
    st.plotly_chart(fig, use_container_width=True)

if ridge_coefs:
    rc_sorted = sorted(ridge_coefs.items(), key=lambda x: -abs(x[1]))
    feat_names = [x[0] for x in rc_sorted]
    coef_vals  = [x[1] for x in rc_sorted]

    fig = go.Figure(go.Bar(
        x=coef_vals, y=feat_names,
        orientation="h",
        marker_color=[COLORS["mci"] if v >= 0 else COLORS["drs"] for v in coef_vals],
        text=[f"{v:+.4f}" for v in coef_vals],
        textposition="outside",
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
        font=dict(color="#94a3b8", size=11),
        title=dict(text="Ridge Coefficients (standardised features)", font=dict(color="#f1f5f9", size=13)),
        xaxis=dict(gridcolor="#1e293b", title="Coefficient"),
        yaxis=dict(gridcolor="#1e293b", autorange="reversed"),
        margin=dict(l=160, r=60, t=40, b=30), height=320,
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Section 8: Signal vs Return Scatter ───────────────────────────────────────

st.markdown("<div class='section-header'>Signal vs Next-Day Return</div>", unsafe_allow_html=True)
col_s1, col_s2 = st.columns(2)

for col, x_col, label, color in [
    (col_s1, "mci", "MCI", COLORS["mci"]),
    (col_s2, "drs", "DRS", COLORS["drs"]),
]:
    with col:
        x_v = df[x_col].values
        y_v = df["next_day_return"].values * 100
        fig = go.Figure()
        fig.add_hline(y=0, line=dict(color="#475569", width=1))
        try:
            mm, bb = np.polyfit(x_v, y_v, 1)
            xl = np.linspace(x_v.min(), x_v.max(), 50)
            fig.add_trace(go.Scatter(x=xl, y=mm*xl+bb, mode="lines",
                                     line=dict(color=color, width=2, dash="dash"),
                                     showlegend=False))
        except Exception:
            pass
        fig.add_trace(go.Scatter(
            x=x_v, y=y_v, mode="markers",
            marker=dict(color=color, size=5, opacity=0.6,
                        line=dict(color=COLORS["bg"], width=0.5)),
            text=df["ticker"] + " " + df["quarter"],
            hovertemplate=f"{label}: %{{x:.1f}}<br>Return: %{{y:+.2f}}%<br>%{{text}}<extra></extra>",
        ))
        fig.update_layout(
            paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
            font=dict(color="#94a3b8", size=11),
            xaxis=dict(title=label, gridcolor="#1e293b"),
            yaxis=dict(title="Next-Day Return (%)", gridcolor="#1e293b", tickformat="+.1f"),
            margin=dict(l=40, r=20, t=20, b=40), height=300, showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Methodology ───────────────────────────────────────────────────────────────

with st.expander("Methodology"):
    st.markdown("""
**Scoring:** Linguistic engine only (no FinBERT). MCI and DRS are driven by certainty
ratio, hedge density, passive voice ratio, and vague language score using the
Loughran-McDonald financial word lists. Sentiment is fixed at neutral (0.33/0.33/0.34)
so rankings are 100% linguistic — this isolates the novel contribution.

**Data:** SEC EDGAR 10-Q MD&A sections (up to 32 quarters per ticker ≈ 8 years).
Price data from Yahoo Finance. ~65 S&P 500 companies across all sectors.

**IC (Information Coefficient):** Spearman rank correlation within each quarterly cohort
(all companies reporting that quarter). Mean IC across cohorts is the signal quality
measure. IC > 0.05 = meaningful, > 0.10 = strong.

**ICIR:** mean(IC) / std(IC). Measures consistency. > 0.5 acceptable, > 1.0 strong.

**Tone-shift (ΔMCI/ΔDRS):** First difference per ticker. Captures whether management
tone is improving or deteriorating vs prior quarter — orthogonal to absolute level.

**Volatility target:** Annualised realised vol pre vs post earnings (std × √252).
vol_change = post − pre. Tests whether evasive language predicts vol spikes.

**Long-Short:** Each quarter, top-tercile MCI long / bottom-tercile short. Annualised
Sharpe assumes 4 earnings events per year.

**Lag analysis:** DRS(t) vs next-day return at earnings(t+1). Tests whether today's
evasiveness predicts next quarter's market reaction.

**OLS:** next_day_return ~ MCI + DRS. Statistical significance of coefficients matters
more than R² (returns are noisy by construction).

**Ridge / Random Forest:** RidgeCV + sklearn RF on 9 features with time-based 80/20
train/test split (oldest 80% train). Out-of-sample R² reported.
""")

# ── Raw data ──────────────────────────────────────────────────────────────────

with st.expander(f"Raw data ({len(df)} observations)"):
    display_cols = ["ticker", "quarter", "report_date", "mci", "drs",
                    "hedge_density", "certainty_ratio", "passive_voice_ratio",
                    "next_day_return", "five_day_return", "thirty_day_return"]
    show_df = df[[c for c in display_cols if c in df.columns]].copy()
    for rc in ["next_day_return", "five_day_return", "thirty_day_return"]:
        if rc in show_df.columns:
            show_df[rc] = show_df[rc].map(lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "-")
    st.dataframe(show_df, use_container_width=True, hide_index=True)
