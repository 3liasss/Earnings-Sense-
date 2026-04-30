"""
Single source of truth for colors and CSS.
All pages import from here - never hardcode hex values elsewhere.
"""
from __future__ import annotations
import streamlit as st

# ── Palettes ──────────────────────────────────────────────────────────────────

DARK: dict[str, str] = {
    "bg":       "#0b1221",
    "surface":  "#1a2236",
    "surface2": "#101827",
    "border":   "#2d3f5a",
    "border2":  "#1a2236",
    "text":     "#f1f5f9",
    "subtext":  "#94a3b8",
    "muted":    "#4b6280",
    "sidebar":  "#0b1221",
    # signals - slightly vivid on dark
    "green":    "#22c55e",
    "red":      "#ef4444",
    "amber":    "#f97316",
    "blue":     "#3b82f6",
    "violet":   "#8b5cf6",
    "cyan":     "#06b6d4",
    # pill backgrounds
    "pill_green":  "#14532d",
    "pill_red":    "#450a0a",
    "pill_blue":   "#1e3a5f",
    "pill_amber":  "#431407",
    "pill_violet": "#2e1065",
}

LIGHT: dict[str, str] = {
    "bg":       "#f8fafc",
    "surface":  "#ffffff",
    "surface2": "#f1f5f9",
    "border":   "#e2e8f0",
    "border2":  "#f1f5f9",
    "text":     "#0f172a",
    "subtext":  "#475569",
    "muted":    "#94a3b8",
    "sidebar":  "#f1f5f9",
    "green":    "#16a34a",
    "red":      "#dc2626",
    "amber":    "#ea580c",
    "blue":     "#2563eb",
    "violet":   "#7c3aed",
    "cyan":     "#0891b2",
    "pill_green":  "#dcfce7",
    "pill_red":    "#fee2e2",
    "pill_blue":   "#dbeafe",
    "pill_amber":  "#ffedd5",
    "pill_violet": "#ede9fe",
}


# ── Accessors ─────────────────────────────────────────────────────────────────

def get_theme() -> str:
    return st.session_state.get("_es_theme", "dark")


def set_theme(t: str) -> None:
    st.session_state["_es_theme"] = t


def C() -> dict[str, str]:
    """Active theme color dict."""
    return DARK if get_theme() == "dark" else LIGHT


def is_dark() -> bool:
    return get_theme() == "dark"


# ── Plotly layout helper ──────────────────────────────────────────────────────

def plotly_layout(height: int = 300, **overrides) -> dict:
    c = C()
    base = dict(
        paper_bgcolor=c["bg"],
        plot_bgcolor=c["surface"],
        font=dict(color=c["text"], family="Inter, system-ui, -apple-system, sans-serif", size=12),
        margin=dict(l=16, r=16, t=40, b=16),
        height=height,
        hoverlabel=dict(
            bgcolor=c["surface2"],
            bordercolor=c["border"],
            font=dict(color=c["text"], size=12),
        ),
    )
    base.update(overrides)
    return base


# ── Full page CSS ─────────────────────────────────────────────────────────────

def base_css() -> str:
    c = C()
    dark = is_dark()
    return f"""
<style>
/* ── Reset & base ──────────────────────────────────────────── */
.stApp {{
    background-color: {c['bg']} !important;
    transition: background-color 0.18s ease, color 0.18s ease;
}}
[data-testid="stSidebar"],
.stSidebar {{
    background-color: {c['sidebar']} !important;
}}
[data-testid="stSidebarContent"] {{
    background-color: {c['sidebar']} !important;
}}
.block-container {{
    padding-top: 1.5rem;
    max-width: 1400px;
}}

/* ── Typography hierarchy ───────────────────────────────────── */
h1 {{
    color:          {c['text']} !important;
    font-size:      1.85rem !important;
    font-weight:    800 !important;
    letter-spacing: -0.5px !important;
    line-height:    1.15 !important;
}}
h2 {{
    color:          {c['text']} !important;
    font-size:      1.25rem !important;
    font-weight:    700 !important;
    letter-spacing: -0.3px !important;
}}
h3 {{
    color:          {c['subtext']} !important;
    font-size:      1rem !important;
    font-weight:    600 !important;
    letter-spacing: -0.2px !important;
}}
h4 {{
    color:          {c['subtext']} !important;
    font-size:      0.9rem !important;
    font-weight:    600 !important;
}}
[data-testid="stMarkdownContainer"] p {{
    color: {c['subtext']};
    line-height: 1.6;
}}

/* ── Ticker pill ────────────────────────────────────────────── */
.es-ticker {{
    display:         inline-block;
    font-family:     'SF Mono', 'Fira Mono', 'Roboto Mono', monospace;
    font-size:       0.78rem;
    font-weight:     700;
    letter-spacing:  0.5px;
    background:      {c['pill_blue']};
    color:           {c['blue']};
    border:          1px solid {c['border']};
    border-radius:   5px;
    padding:         0.1em 0.55em;
    vertical-align:  middle;
}}

/* ── Cards ─────────────────────────────────────────────────── */
.es-card {{
    background:    {c['surface']};
    border:        1px solid {c['border']};
    border-radius: 10px;
    padding:       1rem 1.25rem;
    margin-bottom: 0.75rem;
    transition:    background 0.18s ease, border-color 0.18s ease;
}}
.es-card-sm {{
    background:    {c['surface']};
    border:        1px solid {c['border']};
    border-radius: 8px;
    padding:       0.55rem 1rem;
    margin-bottom: 0.35rem;
    transition:    border-color 0.15s;
}}
.es-card-sm:hover {{
    border-color: {c['blue']};
}}
.es-kpi {{
    background:    {c['surface']};
    border:        1px solid {c['border']};
    border-radius: 10px;
    padding:       0.9rem 1rem;
    margin-bottom: 0;
    text-align:    center;
}}

/* ── Risk left borders ──────────────────────────────────────── */
.risk-high   {{ border-left: 3px solid {c['red']}   !important; }}
.risk-medium {{ border-left: 3px solid {c['amber']}  !important; }}
.risk-low    {{ border-left: 3px solid {c['green']}  !important; }}

/* ── Pills ──────────────────────────────────────────────────── */
.pill {{
    display:        inline-block;
    padding:        0.18em 0.65em;
    border-radius:  999px;
    font-size:      0.73em;
    font-weight:    600;
    letter-spacing: 0.3px;
}}
.pill-green  {{ background:{c['pill_green']};  color:{c['green']};  }}
.pill-red    {{ background:{c['pill_red']};    color:{c['red']};    }}
.pill-blue   {{ background:{c['pill_blue']};   color:{c['blue']};   }}
.pill-amber  {{ background:{c['pill_amber']};  color:{c['amber']};  }}
.pill-violet {{ background:{c['pill_violet']}; color:{c['violet']}; }}

/* ── Section headers ────────────────────────────────────────── */
.es-label {{
    font-size:      0.7rem;
    font-weight:    700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color:          {c['muted']};
    margin-bottom:  0.4rem;
}}
.es-section-rule {{
    border: none;
    border-top: 1px solid {c['border']};
    margin: 1.5rem 0 1rem 0;
}}

/* ── YoY banner ─────────────────────────────────────────────── */
.es-banner {{
    padding:       0.6rem 1rem;
    border-radius: 6px;
    border-left:   3px solid;
    font-size:     0.85rem;
    color:         {c['text']};
    margin-bottom: 1rem;
}}

/* ── Footer ─────────────────────────────────────────────────── */
.es-footer {{
    text-align:  center;
    color:       {c['subtext']};
    font-size:   0.78rem;
    padding:     1.5rem 0 0.5rem 0;
    border-top:  1px solid {c['border']};
    margin-top:  2rem;
    line-height: 1.8;
}}

/* ── Streamlit widget overrides ─────────────────────────────── */
.stTextInput input {{
    background-color: {c['surface']} !important;
    color:            {c['text']} !important;
    border-color:     {c['border']} !important;
}}
.stSelectbox [data-testid="stSelectbox"] > div {{
    background-color: {c['surface']} !important;
    color:            {c['text']} !important;
}}
.stRadio label, .stCheckbox label {{
    color: {c['subtext']} !important;
}}
[data-testid="stDataFrame"] {{
    background: {c['surface']} !important;
}}

/* ── Scrollbar ──────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {c['surface2']}; }}
::-webkit-scrollbar-thumb {{
    background:    {c['border']};
    border-radius: 3px;
}}
::-webkit-scrollbar-thumb:hover {{ background: {c['muted']}; }}
</style>
"""
