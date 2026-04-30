"""Sidebar branding + theme toggle - imported by every page."""
from __future__ import annotations
import streamlit as st
from src.ui.theme import base_css, C, get_theme, set_theme


def inject_theme_css() -> None:
    st.markdown(base_css(), unsafe_allow_html=True)


def render_sidebar_branding() -> None:
    """
    Call once per page right after set_page_config.
    Puts the dark/light toggle at the very top of the sidebar,
    then injects CSS, then renders the bottom branding block.
    """
    # Toggle is rendered first so it appears above all page-specific content
    with st.sidebar:
        c = C()
        dark = get_theme() == "dark"

        tog_col, label_col = st.columns([1, 4])
        with tog_col:
            toggled = st.toggle(
                "",
                value=dark,
                key="_theme_toggle",
                label_visibility="collapsed",
                help="Dark / light mode",
            )
        with label_col:
            st.markdown(
                f"<div style='padding-top:.42rem;font-size:.78rem;"
                f"color:{c['muted']};'>{'Dark' if dark else 'Light'} mode</div>",
                unsafe_allow_html=True,
            )

        if toggled != dark:
            set_theme("dark" if toggled else "light")
            st.rerun()

        st.markdown(
            f"<hr style='border:none;border-top:1px solid {c['border']};margin:.5rem 0;'>",
            unsafe_allow_html=True,
        )

    # Inject CSS after the toggle widget is registered but before page content
    inject_theme_css()

    # Branding at the bottom of sidebar (will appear below page-specific controls)
    with st.sidebar:
        c = C()  # re-fetch after potential theme change
        st.markdown(
            f"<div style='position:sticky;bottom:0;font-size:.78rem;line-height:1.75;"
            f"padding-top:.5rem;'>"
            f"<hr style='border:none;border-top:1px solid {c['border']};margin:0 0 .5rem;'>"
            f"<span style='color:{c['subtext']};font-weight:600;'>EarningsSense</span><br>"
            f"<span style='color:{c['muted']};'>Built by Elias Wächter</span><br>"
            f"<span style='color:{c['muted']};font-size:.72rem;'>"
            f"FinBERT · Loughran-McDonald · SEC EDGAR</span><br><br>"
            f"<a href='https://github.com/3liasss/Earnings-Sense-' "
            f"style='color:{c['blue']};text-decoration:none;'>GitHub</a>"
            f"&nbsp;·&nbsp;"
            f"<a href='https://earnings-sense.streamlit.app' "
            f"style='color:{c['blue']};text-decoration:none;'>Live app</a>"
            f"</div>",
            unsafe_allow_html=True,
        )
