"""
AI Recommendation Engine – Streamlit page.

Renders a form for the investor's profile, calls the recommendation engine,
and displays results as allocation charts, fund tables, growth projections,
and AI-generated explanations.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, r"C:\Users\GANESH\.gemini\antigravity\scratch\mf_analytics")

from databricks_connector.data_service import DataService
from services.ai_service import AIService
from services.recommendation_engine import RecommendationEngine
from config.settings import AppConfig
from utils.formatters import (
    format_currency,
    format_large_number,
    format_pct,
    format_risk_level,
    get_color_for_value,
)

# ---------------------------------------------------------------------------
# Theme colours (inline to avoid hard dependency on charts.theme at import)
# ---------------------------------------------------------------------------

_COLORS = {
    "primary": "#6366F1",
    "secondary": "#8B5CF6",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "info": "#3B82F6",
    "bg_card": "rgba(30, 30, 60, 0.55)",
    "bg_dark": "#0F0F23",
    "text": "#E2E8F0",
}

_CATEGORY_COLORS: dict[str, str] = {
    "Large Cap": "#6366F1",
    "Mid Cap": "#8B5CF6",
    "Small Cap": "#EC4899",
    "Flexi Cap": "#14B8A6",
    "Multi Cap": "#F97316",
    "ELSS": "#EAB308",
    "Hybrid": "#06B6D4",
    "Debt": "#10B981",
    "Index": "#64748B",
}


def _get_category_color(cat: str) -> str:
    return _CATEGORY_COLORS.get(cat, "#94A3B8")


# ---------------------------------------------------------------------------
# Glassmorphism card helper
# ---------------------------------------------------------------------------

def _metric_card(label: str, value: str, delta: str = "", color: str = "#6366F1") -> str:
    """Return HTML for a single KPI card."""
    delta_html = ""
    if delta:
        delta_color = "#10B981" if not delta.startswith("-") and not delta.startswith("▼") else "#EF4444"
        delta_html = f'<div style="font-size:0.85rem;color:{delta_color};margin-top:2px">{delta}</div>'

    return f"""
    <div style="
        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08));
        border: 1px solid rgba(99,102,241,0.25);
        border-radius: 16px;
        padding: 20px 18px;
        text-align: center;
        backdrop-filter: blur(10px);
    ">
        <div style="font-size:0.85rem;color:#94A3B8;margin-bottom:6px">{label}</div>
        <div style="font-size:1.65rem;font-weight:700;color:{color}">{value}</div>
        {delta_html}
    </div>
    """


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render() -> None:
    """Render the AI Recommendation Engine page."""

    st.markdown(
        "<h1 style='text-align:center'>🤖 AI Recommendation Engine</h1>"
        "<p style='text-align:center;color:#94A3B8;margin-bottom:24px'>"
        "Get personalised mutual fund recommendations based on your profile</p>",
        unsafe_allow_html=True,
    )

    # ---- Initialise services (cached) ----
    data_service = _get_data_service()
    ai_service = _get_ai_service()
    engine = RecommendationEngine(data_service, ai_service)

    # ---- Input form ----
    with st.form("recommendation_form"):
        st.subheader("📝 Investor Profile")
        col1, col2 = st.columns(2)

        with col1:
            investment_amount = st.number_input(
                "Investment Amount (₹)",
                min_value=10_000,
                max_value=100_000_000,
                value=500_000,
                step=10_000,
                format="%d",
            )
            age = st.slider("Age", min_value=18, max_value=80, value=30)
            risk_appetite = st.select_slider(
                "Risk Appetite",
                options=["Low", "Medium", "High"],
                value="Medium",
            )

        with col2:
            horizon_years = st.slider(
                "Investment Horizon (years)", min_value=1, max_value=30, value=5,
            )
            goal = st.selectbox("Financial Goal", options=AppConfig.GOALS, index=0)

        submitted = st.form_submit_button(
            "🚀 Get Recommendations",
            use_container_width=True,
        )

    if not submitted:
        _render_placeholder()
        return

    # ---- Generate recommendations ----
    with st.spinner("Analysing your profile and building recommendations…"):
        result = engine.get_recommendations(
            investment_amount=investment_amount,
            age=age,
            risk_appetite=risk_appetite,
            horizon_years=horizon_years,
            goal=goal,
        )

    recommended_funds = result["recommended_funds"]
    summary = result["portfolio_summary"]
    alloc_df = result["allocation_chart_data"]

    if not recommended_funds:
        st.warning("No funds matched the criteria.  Try adjusting your profile.")
        return

    # ---- Risk Profile Card ----
    profile_emoji = {"conservative": "🛡️", "moderate": "⚖️", "aggressive": "🚀"}.get(
        summary["profile"], "📊"
    )
    profile_label = summary["profile"].title()
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, rgba(99,102,241,0.18), rgba(236,72,153,0.12));
            border: 1px solid rgba(99,102,241,0.3);
            border-radius: 16px;
            padding: 18px 24px;
            margin-bottom: 24px;
            text-align: center;
        ">
            <span style="font-size:2rem">{profile_emoji}</span>
            <h3 style="margin:4px 0 2px">Your Risk Profile: {profile_label}</h3>
            <p style="color:#94A3B8;margin:0">
                Based on age {age}, {risk_appetite.lower()} risk appetite,
                and {horizon_years}-year horizon
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Portfolio summary KPIs ----
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            _metric_card("Expected CAGR", f"{summary['expected_cagr']:.1f}%", color=_COLORS["success"]),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            _metric_card("Risk Level", summary["risk_level"], color=_COLORS["warning"]),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            _metric_card("Diversification", f"{summary['diversification_score']:.0f}/100", color=_COLORS["info"]),
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            _metric_card("Funds Selected", str(summary["num_funds"]), color=_COLORS["primary"]),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ---- Allocation donut chart + fund table ----
    chart_col, table_col = st.columns([1, 1.3])

    with chart_col:
        st.subheader("📊 Recommended Allocation")
        if not alloc_df.empty:
            colors = [_get_category_color(c) for c in alloc_df["category"]]
            fig = go.Figure(data=[go.Pie(
                labels=alloc_df["category"],
                values=alloc_df["allocation_pct"],
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="#1E1E3C", width=2)),
                textinfo="label+percent",
                textfont=dict(size=12, color="white"),
                hovertemplate="<b>%{label}</b><br>Allocation: %{value:.1f}%<extra></extra>",
            )])
            fig.update_layout(
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                annotations=[dict(
                    text=f"₹{investment_amount / 100_000:.1f}L",
                    x=0.5, y=0.5, font=dict(size=18, color="white"), showarrow=False,
                )],
            )
            st.plotly_chart(fig, use_container_width=True)

    with table_col:
        st.subheader("🏆 Recommended Funds")
        for fund in recommended_funds:
            cat_color = _get_category_color(fund["category"])
            risk_color = (
                _COLORS["success"] if fund["risk_score"] <= 4
                else _COLORS["danger"] if fund["risk_score"] >= 8
                else _COLORS["warning"]
            )
            st.markdown(
                f"""
                <div style="
                    background: rgba(30,30,60,0.4);
                    border-left: 4px solid {cat_color};
                    border-radius: 8px;
                    padding: 12px 16px;
                    margin-bottom: 10px;
                ">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <div>
                            <span style="font-weight:600;font-size:0.95rem;color:white">
                                {fund['fund_name'][:45]}
                            </span>
                            <span style="
                                background:{cat_color}22;
                                color:{cat_color};
                                padding:2px 8px;
                                border-radius:12px;
                                font-size:0.75rem;
                                margin-left:8px;
                            ">{fund['category']}</span>
                        </div>
                        <span style="
                            font-weight:700;
                            font-size:1rem;
                            color:{_COLORS['success']};
                        ">{fund['allocation_pct']:.1f}%</span>
                    </div>
                    <div style="
                        display:flex;gap:16px;margin-top:6px;font-size:0.8rem;color:#94A3B8
                    ">
                        <span>Return: <b style="color:white">{fund['expected_return']:.1f}%</b></span>
                        <span>Risk: <b style="color:{risk_color}">{fund['risk_score']}/10</b></span>
                        <span>Sharpe: <b style="color:white">{fund['sharpe_ratio']:.2f}</b></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---- AI Explanations ----
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    with st.expander("💡 AI-Powered Reasoning", expanded=False):
        for fund in recommended_funds:
            st.markdown(
                f"**{fund['fund_name']}** ({fund['category']}, {fund['allocation_pct']:.1f}%)",
            )
            st.info(fund["reason"])
            st.markdown("---")

    # ---- Expected Growth Chart ----
    st.subheader("📈 Expected Growth Projection")
    _render_growth_chart(investment_amount, recommended_funds, horizon_years)


# ---------------------------------------------------------------------------
# Growth projection chart
# ---------------------------------------------------------------------------

def _render_growth_chart(
    investment: float,
    funds: list[dict],
    horizon: int,
) -> None:
    """Render a multi-scenario line chart of projected portfolio growth."""
    years = list(range(0, min(horizon, 30) + 1))
    weighted_return = sum(
        f["expected_return"] * f["allocation_pct"] for f in funds
    ) / max(sum(f["allocation_pct"] for f in funds), 1)

    conservative_rate = max(weighted_return * 0.6, 4.0) / 100
    moderate_rate = max(weighted_return * 0.85, 6.0) / 100
    aggressive_rate = max(weighted_return * 1.15, 10.0) / 100

    conservative_vals = [investment * (1 + conservative_rate) ** y for y in years]
    moderate_vals = [investment * (1 + moderate_rate) ** y for y in years]
    aggressive_vals = [investment * (1 + aggressive_rate) ** y for y in years]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=conservative_vals, name=f"Conservative ({conservative_rate*100:.1f}%)",
        line=dict(color="#3B82F6", width=2, dash="dot"),
        fill="tonexty" if False else None,
        hovertemplate="Year %{x}: ₹%{y:,.0f}<extra>Conservative</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=moderate_vals, name=f"Moderate ({moderate_rate*100:.1f}%)",
        line=dict(color="#8B5CF6", width=3),
        hovertemplate="Year %{x}: ₹%{y:,.0f}<extra>Moderate</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=aggressive_vals, name=f"Aggressive ({aggressive_rate*100:.1f}%)",
        line=dict(color="#10B981", width=2, dash="dash"),
        hovertemplate="Year %{x}: ₹%{y:,.0f}<extra>Aggressive</extra>",
    ))

    fig.update_layout(
        xaxis_title="Years",
        yaxis_title="Portfolio Value (₹)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0"),
        height=400,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
            font=dict(size=12),
        ),
        margin=dict(l=60, r=30, t=40, b=50),
        xaxis=dict(gridcolor="rgba(148,163,184,0.1)", dtick=max(1, horizon // 10)),
        yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
    )

    # Add annotation for final moderate value
    final_val = moderate_vals[-1]
    fig.add_annotation(
        x=years[-1], y=final_val,
        text=f"₹{final_val/100_000:.1f}L",
        showarrow=True, arrowhead=2, ax=-40, ay=-30,
        font=dict(color="white", size=12),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary row below chart
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            _metric_card(
                f"Conservative ({horizon}Y)",
                format_large_number(conservative_vals[-1]),
                color="#3B82F6",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _metric_card(
                f"Moderate ({horizon}Y)",
                format_large_number(moderate_vals[-1]),
                color="#8B5CF6",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _metric_card(
                f"Aggressive ({horizon}Y)",
                format_large_number(aggressive_vals[-1]),
                color="#10B981",
            ),
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Placeholder when form has not been submitted
# ---------------------------------------------------------------------------

def _render_placeholder() -> None:
    """Show guidance content before the user submits the form."""
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align:center;padding:40px 20px;color:#94A3B8">
            <div style="font-size:4rem">🎯</div>
            <h3>Fill in your investor profile above and click
                <span style="color:#6366F1">Get Recommendations</span></h3>
            <p style="max-width:500px;margin:auto">
                Our recommendation engine analyses 150+ mutual funds across 9
                categories to build a personalised portfolio aligned with your
                goals and risk tolerance.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Service caching
# ---------------------------------------------------------------------------

@st.cache_resource
def _get_data_service() -> DataService:
    return DataService()


@st.cache_resource
def _get_ai_service() -> AIService:
    return AIService()
