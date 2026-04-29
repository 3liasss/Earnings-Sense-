"""Shared sidebar branding injected on every page."""
from __future__ import annotations
import streamlit as st

# Applied on every page to keep sidebar dark regardless of Streamlit theme
SIDEBAR_CSS = """
<style>
.stSidebar, [data-testid="stSidebar"] {
    background-color: #0f172a !important;
}
[data-testid="stSidebarContent"] {
    background-color: #0f172a !important;
}
</style>
"""


def inject_sidebar_style() -> None:
    st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)


def render_sidebar_branding() -> None:
    """Call inside (or after) your page's `with st.sidebar:` block."""
    inject_sidebar_style()
    with st.sidebar:
        st.markdown("---")
        st.markdown(
            """
            <div style='font-size:.8rem;line-height:1.7;'>
            <span style='color:#64748b;font-weight:600;'>EarningsSense</span><br>
            <span style='color:#475569;'>Built by Elias Wächter</span><br>
            <span style='color:#334155;font-size:.73rem;'>
            FinBERT · Loughran-McDonald · SEC EDGAR
            </span><br><br>
            <a href='https://github.com/3liasss/Earnings-Sense-'
               style='color:#3b82f6;text-decoration:none;'>GitHub</a>
            &nbsp;·&nbsp;
            <a href='https://earnings-sense.streamlit.app'
               style='color:#3b82f6;text-decoration:none;'>Live app</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
