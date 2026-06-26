"""
MF Analytics Pro — Main Application Entry Point

Mutual Fund Analytics & Portfolio Recommendation Platform
Enterprise-grade dashboard with dynamic Databricks integration,
AI-powered recommendations, and advanced Plotly visualizations.
"""

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st

from config.settings import AppConfig, DatabricksConfig, OpenAIConfig


# ─────────────────────────────────────────────
# Page Configuration (MUST be first st call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title=AppConfig.APP_TITLE,
    page_icon=AppConfig.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": f"## {AppConfig.APP_TITLE}\n{AppConfig.APP_DESCRIPTION}",
    },
)


# ─────────────────────────────────────────────
# Load Custom CSS
# ─────────────────────────────────────────────
def load_css():
    """Inject custom stylesheet."""
    css_path = Path(__file__).parent / "assets" / "styles.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css()


# ─────────────────────────────────────────────
# Navigation / Page Definitions
# ─────────────────────────────────────────────
PAGES = {
    "📊 Market Overview": "market_overview",
    "🔍 Fund Analytics": "fund_analysis",
    "📈 Ups & Downs": "ups_downs",
    "📂 Category Analytics": "category_analysis",
    "🤖 AI Recommendations": "ai_recommendation",
    "💼 Portfolio Analysis": "portfolio_analysis",
}


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
def render_sidebar():
    """Build the sidebar navigation and status panel."""
    with st.sidebar:
        # Logo / branding
        st.markdown(
            """
            <div class="sidebar-logo">
                <h1>📊 MF Analytics Pro</h1>
                <p>Mutual Fund Platform</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Mode indicator
        if AppConfig.is_demo_mode():
            st.markdown(
                '<span class="mode-badge mode-demo">⚡ Demo Mode</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="mode-badge mode-live">🟢 Live — Databricks</span>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Navigation
        selected = st.radio(
            "Navigation",
            list(PAGES.keys()),
            index=0,
            label_visibility="collapsed",
        )

        st.markdown("---")

        # Status panel
        with st.expander("⚙️ System Status", expanded=False):
            # Databricks status
            if DatabricksConfig.is_configured():
                st.markdown("✅ **Databricks** — Connected")
            else:
                st.markdown("🟡 **Databricks** — Not configured")

            # AI status
            if OpenAIConfig.is_configured():
                model_label = "Azure OpenAI" if OpenAIConfig.use_azure() else "OpenAI"
                st.markdown(f"✅ **AI** — {model_label} ({OpenAIConfig.MODEL})")
            else:
                st.markdown("🟡 **AI** — Offline (rule-based)")

            # Mode
            st.markdown(f"📦 **Mode** — `{AppConfig.MODE}`")

        st.markdown("---")
        st.markdown(
            """
            <div style="text-align:center; color: #475569; font-size: 0.7rem;">
                MF Analytics Pro v1.0<br>
                © 2025 — Enterprise Analytics
            </div>
            """,
            unsafe_allow_html=True,
        )

    return selected


# ─────────────────────────────────────────────
# Page Router
# ─────────────────────────────────────────────
def load_page(page_key: str):
    """Dynamically import and render the selected module."""

    if page_key == "market_overview":
        from modules.market_overview.market_overview import render
    elif page_key == "fund_analysis":
        from modules.fund_analysis.fund_analysis import render
    elif page_key == "ups_downs":
        from modules.ups_downs.ups_downs import render
    elif page_key == "category_analysis":
        from modules.category_analysis.category_analysis import render
    elif page_key == "ai_recommendation":
        from modules.ai_recommendation.recommendation import render
    elif page_key == "portfolio_analysis":
        from modules.portfolio_analysis.portfolio_analysis import render
    else:
        st.error(f"Unknown page: {page_key}")
        return

    render()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    """Application entry point."""
    selected_label = render_sidebar()
    page_key = PAGES[selected_label]
    load_page(page_key)


if __name__ == "__main__":
    main()
