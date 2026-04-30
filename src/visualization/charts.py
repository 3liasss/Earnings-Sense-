"""
Plotly chart builders for EarningsSense.
All functions are theme-aware via src.ui.theme.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from src.ui.theme import C, plotly_layout, is_dark
except Exception:
    # Fallback when running outside Streamlit (tests etc.)
    def is_dark() -> bool: return True
    def C() -> dict:
        return {
            "bg": "#0b1221", "surface": "#1a2236", "surface2": "#101827",
            "border": "#2d3f5a", "text": "#f1f5f9", "subtext": "#94a3b8",
            "muted": "#4b6280", "green": "#22c55e", "red": "#ef4444",
            "amber": "#f97316", "blue": "#3b82f6", "violet": "#8b5cf6",
        }
    def plotly_layout(height: int = 300, **kw) -> dict:
        c = C()
        base = dict(paper_bgcolor=c["bg"], plot_bgcolor=c["surface"],
                    font=dict(color=c["text"], family="Inter, sans-serif"),
                    margin=dict(l=16, r=16, t=40, b=16), height=height)
        base.update(kw)
        return base


# ── Gauge charts ──────────────────────────────────────────────────────────────

def confidence_gauges(mci: float, drs: float) -> go.Figure:
    """
    Side-by-side MCI / DRS gauges.
    Subplot titles are inside the chart; no redundant outer title.
    """
    c = C()
    dark = is_dark()

    steps_mci = [
        {"range": [0,  33], "color": c["surface2"]},
        {"range": [33, 66], "color": "#1e3a5f" if dark else "#dbeafe"},
        {"range": [66, 100], "color": "#14532d" if dark else "#dcfce7"},
    ]
    steps_drs = [
        {"range": [0,  33], "color": "#14532d" if dark else "#dcfce7"},
        {"range": [33, 66], "color": "#431407" if dark else "#ffedd5"},
        {"range": [66, 100], "color": "#450a0a" if dark else "#fee2e2"},
    ]

    mci_color = (c["green"] if mci >= 60 else c["blue"] if mci >= 40 else c["red"])
    drs_color = (c["red"] if drs >= 55 else c["amber"] if drs >= 30 else c["green"])

    def _gauge(value, bar_color, steps, label):
        return go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": label, "font": {"size": 13, "color": c["subtext"]}},
            number={"suffix": "/100", "font": {"size": 30, "color": bar_color},
                    "valueformat": ".0f"},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": c["muted"],
                    "tickfont": {"color": c["muted"], "size": 9},
                    "nticks": 6,
                },
                "bar":         {"color": bar_color, "thickness": 0.28},
                "bgcolor":     c["surface"],
                "borderwidth": 1,
                "bordercolor": c["border"],
                "steps":       steps,
                "threshold": {
                    "line":      {"color": bar_color, "width": 3},
                    "thickness": 0.8,
                    "value":     value,
                },
            },
        )

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "indicator"}, {"type": "indicator"}]],
    )
    fig.add_trace(_gauge(mci, mci_color, steps_mci, "Management Confidence"), row=1, col=1)
    fig.add_trace(_gauge(drs, drs_color, steps_drs, "Deception Risk"), row=1, col=2)

    fig.update_layout(**plotly_layout(height=300))
    return fig


# ── Sentiment bar ─────────────────────────────────────────────────────────────

def sentiment_bar(positive: float, negative: float, neutral: float,
                  company: str = "") -> go.Figure:
    c = C()
    fig = go.Figure()

    for label, value, color in [
        ("Positive", positive * 100, c["green"]),
        ("Neutral",  neutral  * 100, c["subtext"]),
        ("Negative", negative * 100, c["red"]),
    ]:
        fig.add_trace(go.Bar(
            name=label,
            x=[value],
            y=["Sentiment"],
            orientation="h",
            marker_color=color,
            text=f"{value:.1f}%",
            textposition="inside",
            textfont={"color": "#ffffff", "size": 12, "family": "Inter, sans-serif"},
            hovertemplate=f"<b>{label}</b>: {{x:.1f}}%<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.05,
            xanchor="right",  x=1,
            font={"color": c["subtext"], "size": 11},
        ),
        xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False,
                   zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False),
        title={"text": f"FinBERT Sentiment  {company}",
               "font": {"size": 12, "color": c["muted"]}},
        **plotly_layout(height=150),
    )
    return fig


# ── Linguistic radar ──────────────────────────────────────────────────────────

def linguistic_radar(hedge_density: float, certainty_ratio: float,
                     passive_voice_ratio: float, vague_language_score: float) -> go.Figure:
    c = C()
    dark = is_dark()

    def norm(v, cap): return min(v / cap, 1.0) * 100

    raw = {
        "Hedge Density":    (hedge_density,       5.0,  False),
        "Certainty Ratio":  (certainty_ratio,      5.0,  True),
        "Passive Voice":    (passive_voice_ratio,  0.5,  False),
        "Vague Language":   (vague_language_score, 3.0,  False),
    }
    labels   = list(raw.keys()) + [list(raw.keys())[0]]
    normed   = [norm(v, cap) for v, cap, _ in raw.values()]
    normed  += [normed[0]]

    # Value annotation text per spoke
    raw_vals = [v for v, _, _ in raw.values()]
    fmt_vals = [f"{v:.2f}" for v in raw_vals]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=normed,
        theta=labels,
        fill="toself",
        fillcolor=f"rgba(139,92,246,{'0.20' if dark else '0.12'})",
        line=dict(color=c["violet"], width=2),
        name="Profile",
        hovertemplate=(
            "<b>%{theta}</b><br>"
            "Normalized: %{r:.1f}/100<extra></extra>"
        ),
    ))

    # Invisible trace for the raw value annotations at each spoke tip
    annotation_r = [min(norm(v, cap) + 12, 108) for v, cap, _ in raw.values()]
    annotation_r.append(annotation_r[0])
    fig.add_trace(go.Scatterpolar(
        r=annotation_r,
        theta=labels,
        mode="text",
        text=fmt_vals + [fmt_vals[0]],
        textfont={"color": c["subtext"], "size": 10},
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.update_layout(
        polar=dict(
            bgcolor=c["surface"],
            radialaxis=dict(
                visible=True,
                range=[0, 110],
                tickfont={"color": c["muted"], "size": 8},
                gridcolor=c["border"],
                linecolor=c["border"],
                showticklabels=True,
                tickvals=[25, 50, 75, 100],
                ticktext=["25", "50", "75", "100"],
            ),
            angularaxis=dict(
                tickfont={"color": c["subtext"], "size": 11},
                gridcolor=c["border"],
                linecolor=c["border"],
            ),
        ),
        title={"text": "Linguistic Feature Profile",
               "font": {"size": 12, "color": c["muted"]}},
        showlegend=False,
        **plotly_layout(height=340),
    )
    return fig


# ── Price impact chart ────────────────────────────────────────────────────────

def price_impact_chart(price_series: list[dict], earnings_date: str,
                       ticker: str, mci: float) -> go.Figure:
    c = C()

    dates  = [p["date"]  for p in price_series]
    closes = [p["close"] for p in price_series]

    try:
        earn_idx = dates.index(earnings_date)
    except ValueError:
        earn_idx = min(
            range(len(dates)),
            key=lambda i: abs(
                int(dates[i].replace("-", "")) - int(earnings_date.replace("-", ""))
            ),
        )

    pre_dates  = dates[:earn_idx + 1]
    post_dates = dates[earn_idx:]
    pre_close  = closes[:earn_idx + 1]
    post_close = closes[earn_idx:]

    post_color = c["green"] if post_close[-1] >= post_close[0] else c["red"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pre_dates, y=pre_close,
        mode="lines",
        line=dict(color=c["muted"], width=1.5),
        name="Pre-earnings",
        hovertemplate="<b>%{x}</b><br>$%{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=post_dates, y=post_close,
        mode="lines",
        line=dict(color=post_color, width=2.5),
        name="Post-earnings",
        hovertemplate="<b>%{x}</b><br>$%{y:.2f}<extra></extra>",
    ))

    fig.add_shape(
        type="line", x0=earnings_date, x1=earnings_date,
        y0=0, y1=1, yref="paper",
        line=dict(color=c["blue"], width=1.5, dash="dot"),
    )
    fig.add_annotation(
        x=earnings_date, y=0.96, yref="paper",
        text=f" Earnings  MCI {mci:.0f}",
        showarrow=False,
        font=dict(color=c["blue"], size=11),
        xanchor="left",
        bgcolor=c["surface2"],
        borderpad=4,
    )

    fig.update_layout(
        xaxis=dict(showgrid=True, gridcolor=c["border"],
                   tickfont={"color": c["muted"], "size": 10},
                   title=dict(text="Date", font={"color": c["muted"], "size": 11})),
        yaxis=dict(showgrid=True, gridcolor=c["border"],
                   tickfont={"color": c["muted"], "size": 10},
                   tickprefix="$",
                   title=dict(text="Close", font={"color": c["muted"], "size": 11})),
        legend=dict(font={"color": c["subtext"], "size": 11}),
        title={"text": f"{ticker} - 30-day price window around earnings",
               "font": {"size": 12, "color": c["muted"]}},
        **plotly_layout(height=300),
    )
    return fig


# ── Multi-quarter trend ───────────────────────────────────────────────────────

def mci_trend_chart(history: list[dict]) -> go.Figure:
    c = C()
    sorted_h = sorted(history, key=lambda x: x.get("report_date") or x.get("quarter", ""))
    labels   = [h.get("quarter") or h.get("report_date", "?") for h in sorted_h]
    mcis     = [h.get("mci", 0) for h in sorted_h]
    drss     = [h.get("drs", 0) for h in sorted_h]

    all_vals = mcis + drss
    y_min    = max(0, min(all_vals) - 8)
    y_max    = min(100, max(all_vals) + 8)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=mcis,
        mode="lines+markers",
        line=dict(color=c["blue"], width=2.5),
        marker=dict(size=7, color=c["blue"],
                    line=dict(color=c["surface"], width=1.5)),
        name="MCI",
        hovertemplate="<b>%{x}</b><br>MCI: %{y:.1f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=drss,
        mode="lines+markers",
        line=dict(color=c["amber"], width=2.5, dash="dot"),
        marker=dict(size=7, color=c["amber"],
                    line=dict(color=c["surface"], width=1.5)),
        name="DRS",
        hovertemplate="<b>%{x}</b><br>DRS: %{y:.1f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(showgrid=True, gridcolor=c["border"],
                   tickfont={"color": c["muted"], "size": 10}),
        yaxis=dict(range=[y_min, y_max], showgrid=True, gridcolor=c["border"],
                   tickfont={"color": c["muted"], "size": 10}),
        legend=dict(font={"color": c["subtext"]},
                    orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        title={"text": "MCI / DRS - multi-quarter trend",
               "font": {"size": 12, "color": c["muted"]}},
        **plotly_layout(height=260),
    )
    return fig


# ── EPS actual vs estimate ────────────────────────────────────────────────────

def earnings_surprise_chart(surprises: list[dict], ticker: str) -> go.Figure:
    c = C()
    rev       = list(reversed(surprises))
    dates     = [s["date"][:7]        for s in rev]
    actuals   = [s["actual_eps"]      for s in rev]
    estimates = [s["estimated_eps"]   for s in rev]
    dot_colors = [c["green"] if a >= e else c["red"] for a, e in zip(actuals, estimates)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=estimates,
        name="Estimate",
        marker_color=c["border"],
        opacity=0.8,
        hovertemplate="<b>%{x}</b><br>Estimate: $%{y:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=actuals,
        mode="markers",
        marker=dict(size=12, color=dot_colors,
                    line=dict(color=c["surface"], width=2)),
        name="Actual",
        hovertemplate="<b>%{x}</b><br>Actual: $%{y:.3f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(showgrid=False, tickfont={"color": c["muted"], "size": 10}),
        yaxis=dict(showgrid=True, gridcolor=c["border"],
                   tickfont={"color": c["muted"], "size": 10}, tickprefix="$"),
        legend=dict(font={"color": c["subtext"]},
                    orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        title={"text": f"{ticker} - EPS actual vs estimate",
               "font": {"size": 12, "color": c["muted"]}},
        **plotly_layout(height=240),
    )
    return fig


# ── Backtest scatter ──────────────────────────────────────────────────────────

def backtest_scatter(samples: list[dict], pearson_r: float, p_value: float) -> go.Figure:
    c = C()
    mcis    = [s["scores"]["management_confidence_index"] for s in samples]
    returns = [s["price_impact"]["next_day_return"] * 100   for s in samples]
    labels  = [f"{s['ticker']} {s['quarter']}"              for s in samples]

    m, b   = np.polyfit(mcis, returns, 1)
    x_line = [min(mcis) - 2, max(mcis) + 2]
    y_line = [m * x + b for x in x_line]

    point_colors = [c["green"] if r >= 0 else c["red"] for r in returns]
    sig_text = "p < 0.05" if p_value < 0.05 else f"p = {p_value:.3f}"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_line, y=y_line,
        mode="lines",
        line=dict(color=c["violet"], dash="dash", width=1.5),
        name=f"OLS trend (r={pearson_r:+.3f})",
        hoverinfo="skip",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=c["border"], line_width=1)
    fig.add_trace(go.Scatter(
        x=mcis, y=returns,
        mode="markers+text",
        marker=dict(color=point_colors, size=11,
                    line=dict(color=c["surface"], width=1.5)),
        text=labels,
        textposition="top center",
        textfont={"size": 9, "color": c["muted"]},
        name="Events",
        customdata=labels,
        hovertemplate=(
            "<b>%{customdata}</b><br>"
            "MCI: %{x:.1f}<br>"
            "Return: %{y:+.2f}%<extra></extra>"
        ),
    ))

    fig.update_layout(
        xaxis=dict(title="Management Confidence Index",
                   showgrid=True, gridcolor=c["border"],
                   tickfont={"color": c["muted"], "size": 10}),
        yaxis=dict(title="Next-Day Return (%)",
                   showgrid=True, gridcolor=c["border"],
                   tickfont={"color": c["muted"], "size": 10},
                   ticksuffix="%"),
        legend=dict(font={"color": c["subtext"]}),
        title={"text": f"MCI vs next-day return  r={pearson_r:+.3f}  {sig_text}",
               "font": {"size": 12, "color": c["muted"]}},
        **plotly_layout(height=400),
    )
    return fig
