"""Sidebar branding + theme toggle - imported by every page."""
from __future__ import annotations
import streamlit as st
from src.ui.theme import base_css, C, get_theme, set_theme


def inject_theme_css() -> None:
    st.markdown(base_css(), unsafe_allow_html=True)


def render_sidebar_branding() -> None:
    """
    Call once per page, after set_page_config.
    Injects theme CSS and renders the bottom sidebar branding + theme toggle.
    """
    inject_theme_css()

    c = C()
    dark = get_theme() == "dark"

    with st.sidebar:
        # Theme toggle at top of sidebar
        tcol1, tcol2 = st.columns([1, 3])
        with tcol1:
            toggled = st.toggle("", value=dark, key="_theme_toggle",
                                label_visibility="collapsed",
                                help="Toggle dark / light mode")
        with tcol2:
            st.markdown(
                f"<div style='padding-top:.45rem;font-size:.78rem;"
                f"color:{c['muted']};'>{'Dark' if dark else 'Light'} mode</div>",
                unsafe_allow_html=True,
            )

        if toggled != dark:
            set_theme("dark" if toggled else "light")
            st.rerun()

        st.markdown(
            f"<hr style='border:none;border-top:1px solid {c['border']};margin:.6rem 0;'>",
            unsafe_allow_html=True,
        )

        # Branding block
        st.markdown(
            f"<div style='font-size:.78rem;line-height:1.75;'>"
            f"<span style='color:{c['subtext']};font-weight:600;font-size:.82rem;'>"
            f"EarningsSense</span><br>"
            f"<span style='color:{c['muted']};'>Built by Elias Wächter</span><br>"
            f"<span style='color:{c['muted']};font-size:.72rem;'>"
            f"FinBERT · Loughran-McDonald · SEC EDGAR</span><br><br>"
            f"<a href='https://github.com/3liasss/Earnings-Sense-' "
            f"   style='color:{c['blue']};text-decoration:none;'>GitHub</a>"
            f"&nbsp;·&nbsp;"
            f"<a href='https://earnings-sense.streamlit.app' "
            f"   style='color:{c['blue']};text-decoration:none;'>Live app</a>"
            f"</div>",
            unsafe_allow_html=True,
        )
