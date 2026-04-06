"""
Plotly chart builders for the EarningsSense dashboard.

All functions return go.Figure objects ready to be passed to
st.plotly_chart(..., use_container_width=True).
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ── Color palette ─────────────────────────────────────────────────────────────

COLORS = {
    "positive":   "#22c55e",   # green-500
    "negative":   "#ef4444",   # red-500
    "neutral":    "#94a3b8",   # slate-400
    "mci":        "#3b82f6",   # blue-500
    "drs":        "#f97316",   # orange-500
    "accent":     "#8b5cf6",   # violet-500
    "bg":         "#0f172a",   # slate-900
    "surface":    "#1e293b",   # slate-800
    "text":       "#f1f5f9",   # slate-100
    "subtext":    "#94a3b8",   # slate-400
    "grid":       "#334155",   # slate-700
}

_LAYOUT_DEFAULTS = dict(
    paper_bgcolor=COLORS["bg"],
    plot_bgcolor=COLORS["surface"],
    font=dict(color=COLORS["text"], family="Inter, sans-serif"),
    margin=dict(l=20, r=20, t=40, b=20),
)


def _base_layout(**overrides) -> dict:
    layout = dict(_LAYOUT_DEFAULTS)
    layout.update(overrides)
    return layout


# ── Gauge charts ──────────────────────────────────────────────────────────────

def confidence_gauges(mci: float, drs: float) -> go.Figure:
    """
    Two side-by-side gauge indicators:
      Left  — Management Confidence Index (0–100, blue, higher is better)
      Right — Deception Risk Score        (0–100, orange, lower is better)
    """
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "indicator"}, {"type": "indicator"}]],
        subplot_titles=["Management Confidence Index", "Deception Risk Score"],
    )

    def _gauge(value, color, threshold_color, title):
        return go.Indicator(
            mode="gauge+number+delta",
            value=value,
            number={"suffix": "/100", "font": {"size": 32, "color": COLORS["text"]}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickcolor": COLORS["subtext"],
                    "tickfont": {"color": COLORS["subtext"]},
                },
                "bar": {"color": color, "thickness": 0.3},
                "bgcolor": COLORS["surface"],
                "bordercolor": COLORS["grid"],
                "steps": [
                    {"range": [0, 33],  "color": "#1e293b"},
                    {"range": [33, 66], "color": "#1e3a5f"},
                    {"range": [66, 100],"color": "#1e3a4a"},
                ],
                "threshold": {
                    "line": {"color": threshold_color, "width": 3},
                    "thickness": 0.75,
                    "value": value,
                },
            },
        )

    fig.add_trace(_gauge(mci, COLORS["mci"], COLORS["positive"], "MCI"), row=1, col=1)
    fig.add_trace(_gauge(drs, COLORS["drs"], COLORS["negative"], "DRS"), row=1, col=2)

    fig.update_layout(
        height=280,
        **_base_layout(
            title={
                "text": "Signal Overview",
                "font": {"size": 16, "color": COLORS["subtext"]},
            }
        ),
    )
    return fig


# ── Sentiment breakdown ───────────────────────────────────────────────────────

def sentiment_bar(positive: float, negative: float, neutral: float,
                  company: str = "") -> go.Figure:
    """Horizontal stacked bar showing positive / neutral / negative breakdown."""
    fig = go.Figure()

    for label, value, color in [
        ("Positive", positive * 100, COLORS["positive"]),
        ("Neutral",  neutral  * 100, COLORS["neutral"]),
        ("Negative", negative * 100, COLORS["negative"]),
    ]:
        fig.add_trace(go.Bar(
            name=label,
            x=[value],
            y=["FinBERT Sentiment"],
            orientation="h",
            marker_color=color,
            text=f"{value:.1f}%",
            textposition="inside",
            textfont={"color": "white", "size": 13},
            hovertemplate=f"<b>{label}</b>: {{x:.1f}}%<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        height=120,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font={"color": COLORS["text"]},
        ),
        xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, tickfont={"color": COLORS["subtext"]}),
        title={
            "text": f"FinBERT Sentiment Analysis — {company}",
            "font": {"size": 14, "color": COLORS["subtext"]},
        },
        **_base_layout(),
    )
    return fig


# ── Linguistic radar chart ────────────────────────────────────────────────────

def linguistic_radar(hedge_density: float, certainty_ratio: float,
                     passive_voice_ratio: float, vague_language_score: float) -> go.Figure:
    """
    Radar chart of the four linguistic metrics.
    Values are normalized to [0, 100] for display.
    """
    # Normalize to 0–100 for display
    def norm(v, cap): return min(v / cap, 1.0) * 100

    categories = [
        "Hedge Density",
        "Certainty Ratio",
        "Passive Voice",
        "Vague Language",
        "Hedge Density",   # close the polygon
    ]
    values = [
        norm(hedge_density, 5.0),
        norm(certainty_ratio, 5.0),
        norm(passive_voice_ratio, 0.5),
        norm(vague_language_score, 3.0),
        norm(hedge_density, 5.0),   # repeat first to close shape
    ]

    fig = go.Figure(go.Scatterpolar(
        r=values,
        theta=categories,
        fill="toself",
        fillcolor=f"rgba(139, 92, 246, 0.25)",
        line=dict(color=COLORS["accent"], width=2),
        name="Linguistic Profile",
    ))

    fig.update_layout(
        polar=dict(
            bgcolor=COLORS["surface"],
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont={"color": COLORS["subtext"], "size": 9},
                gridcolor=COLORS["grid"],
                linecolor=COLORS["grid"],
            ),
            angularaxis=dict(
                tickfont={"color": COLORS["text"], "size": 11},
                gridcolor=COLORS["grid"],
                linecolor=COLORS["grid"],
            ),
        ),
        height=340,
        title={
            "text": "Linguistic Feature Profile",
            "font": {"size": 14, "color": COLORS["subtext"]},
        },
        showlegend=False,
        **_base_layout(),
    )
    return fig


# ── Price impact chart ────────────────────────────────────────────────────────

def price_impact_chart(price_series: list[dict], earnings_date: str,
                       ticker: str, mci: float) -> go.Figure:
    """
    Line chart of closing prices around the earnings date.
    Annotates the earnings event with MCI score.
    """
    dates = [p["date"] for p in price_series]
    closes = [p["close"] for p in price_series]

    # Find the earnings date index
    try:
        earn_idx = dates.index(earnings_date)
    except ValueError:
        # Find nearest date
        earn_idx = min(range(len(dates)), key=lambda i: abs(dates[i] - earnings_date))

    pre_dates  = dates[:earn_idx + 1]
    post_dates = dates[earn_idx:]
    pre_close  = closes[:earn_idx + 1]
    post_close = closes[earn_idx:]

    fig = go.Figure()

    # Pre-earnings line
    fig.add_trace(go.Scatter(
        x=pre_dates, y=pre_close,
        mode="lines",
        line=dict(color=COLORS["subtext"], width=2),
        name="Pre-Earnings",
        hovertemplate="<b>%{x}</b><br>Close: $%{y:.2f}<extra></extra>",
    ))

    # Post-earnings line
    fig.add_trace(go.Scatter(
        x=post_dates, y=post_close,
        mode="lines",
        line=dict(
            color=COLORS["positive"] if post_close[-1] >= post_close[0] else COLORS["negative"],
            width=2.5,
        ),
        name="Post-Earnings",
        hovertemplate="<b>%{x}</b><br>Close: $%{y:.2f}<extra></extra>",
    ))

    # Earnings date vertical annotation
    fig.add_vline(
        x=earnings_date,
        line_dash="dot",
        line_color=COLORS["mci"],
        line_width=2,
        annotation_text=f"Earnings  MCI {mci:.0f}",
        annotation_position="top right",
        annotation_font_color=COLORS["mci"],
    )

    fig.update_layout(
        height=320,
        xaxis=dict(
            title="Date",
            showgrid=True,
            gridcolor=COLORS["grid"],
            tickfont={"color": COLORS["subtext"]},
        ),
        yaxis=dict(
            title="Close Price (USD)",
            showgrid=True,
            gridcolor=COLORS["grid"],
            tickfont={"color": COLORS["subtext"]},
            tickprefix="$",
        ),
        legend=dict(font={"color": COLORS["text"]}),
        title={
            "text": f"{ticker} — 30-Day Price Impact Around Earnings",
            "font": {"size": 14, "color": COLORS["subtext"]},
        },
        **_base_layout(),
    )
    return fig


# ── Backtest scatter ──────────────────────────────────────────────────────────

def backtest_scatter(samples: list[dict], pearson_r: float, p_value: float) -> go.Figure:
    """
    Scatter plot: Management Confidence Index vs. next-day return.
    Includes OLS regression trend line.
    """
    mcis    = [s["scores"]["management_confidence_index"] for s in samples]
    returns = [s["price_impact"]["next_day_return"] * 100 for s in samples]
    labels  = [f"{s['ticker']} {s['quarter']}" for s in samples]

    # OLS trend line
    m, b = np.polyfit(mcis, returns, 1)
    x_line = [min(mcis) - 2, max(mcis) + 2]
    y_line = [m * x + b for x in x_line]

    # Color points by return direction
    point_colors = [COLORS["positive"] if r >= 0 else COLORS["negative"] for r in returns]

    fig = go.Figure()

    # Trend line
    fig.add_trace(go.Scatter(
        x=x_line, y=y_line,
        mode="lines",
        line=dict(color=COLORS["accent"], dash="dash", width=1.5),
        name=f"OLS Trend (r={pearson_r:+.3f})",
        hoverinfo="skip",
    ))

    # Zero return line
    fig.add_hline(y=0, line_dash="dot", line_color=COLORS["grid"], line_width=1)

    # Data points
    fig.add_trace(go.Scatter(
        x=mcis,
        y=returns,
        mode="markers+text",
        marker=dict(
            color=point_colors,
            size=12,
            line=dict(color="white", width=1),
        ),
        text=labels,
        textposition="top center",
        textfont={"size": 9, "color": COLORS["subtext"]},
        name="Earnings Events",
        customdata=labels,
        hovertemplate=(
            "<b>%{customdata}</b><br>"
            "MCI: %{x:.1f}<br>"
            "Next-Day Return: %{y:+.2f}%<extra></extra>"
        ),
    ))

    sig_text = "p < 0.05 ✓" if p_value < 0.05 else f"p = {p_value:.3f}"
    fig.update_layout(
        height=400,
        xaxis=dict(
            title="Management Confidence Index",
            showgrid=True, gridcolor=COLORS["grid"],
            tickfont={"color": COLORS["subtext"]},
        ),
        yaxis=dict(
            title="Next-Day Return (%)",
            showgrid=True, gridcolor=COLORS["grid"],
            tickfont={"color": COLORS["subtext"]},
            ticksuffix="%",
        ),
        legend=dict(font={"color": COLORS["text"]}),
        title={
            "text": (
                f"Backtest: MCI vs. Next-Day Return — "
                f"Pearson r = {pearson_r:+.3f}, {sig_text}"
            ),
            "font": {"size": 14, "color": COLORS["subtext"]},
        },
        **_base_layout(),
    )
    return fig
