"""
Portfolio Analysis – Streamlit page.

Renders a comprehensive analysis dashboard for a selected client portfolio
including KPI cards, allocation charts, diversification gauge, risk radar,
AI advisor insights, and future value projections.
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
from services.portfolio_engine import PortfolioEngine
from utils.formatters import (
    format_currency,
    format_currency_lakhs,
    format_large_number,
    format_pct,
    format_risk_level,
    get_color_for_value,
)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

_COLORS = {
    "primary": "#6366F1",
    "secondary": "#8B5CF6",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "info": "#3B82F6",
    "bg_card": "rgba(30, 30, 60, 0.55)",
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


def _cat_color(cat: str) -> str:
    return _CATEGORY_COLORS.get(cat, "#94A3B8")


# ---------------------------------------------------------------------------
# Glassmorphism card helper
# ---------------------------------------------------------------------------

def _metric_card(
    label: str,
    value: str,
    delta: str = "",
    color: str = "#6366F1",
) -> str:
    delta_html = ""
    if delta:
        d_color = "#10B981" if not delta.startswith("-") and not delta.startswith("▼") else "#EF4444"
        delta_html = f'<div style="font-size:0.85rem;color:{d_color};margin-top:2px">{delta}</div>'

    return f"""
    <div style="
        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08));
        border: 1px solid rgba(99,102,241,0.25);
        border-radius: 16px;
        padding: 20px 16px;
        text-align: center;
        backdrop-filter: blur(10px);
    ">
        <div style="font-size:0.82rem;color:#94A3B8;margin-bottom:6px">{label}</div>
        <div style="font-size:1.5rem;font-weight:700;color:{color}">{value}</div>
        {delta_html}
    </div>
    """


# ---------------------------------------------------------------------------
# Gauge helper
# ---------------------------------------------------------------------------

def _gauge_chart(
    value: float,
    title: str,
    max_val: float = 100,
    height: int = 250,
) -> go.Figure:
    """Create a gauge chart."""
    if value <= max_val * 0.33:
        bar_color = _COLORS["danger"]
    elif value <= max_val * 0.66:
        bar_color = _COLORS["warning"]
    else:
        bar_color = _COLORS["success"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title=dict(text=title, font=dict(size=14, color="#E2E8F0")),
        number=dict(font=dict(size=28, color="white"), suffix="" if max_val == 100 else ""),
        gauge=dict(
            axis=dict(range=[0, max_val], tickfont=dict(color="#94A3B8", size=10)),
            bar=dict(color=bar_color),
            bgcolor="rgba(30,30,60,0.3)",
            borderwidth=0,
            steps=[
                dict(range=[0, max_val * 0.33], color="rgba(239,68,68,0.15)"),
                dict(range=[max_val * 0.33, max_val * 0.66], color="rgba(245,158,11,0.15)"),
                dict(range=[max_val * 0.66, max_val], color="rgba(16,185,129,0.15)"),
            ],
        ),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=30, r=30, t=50, b=10),
    )
    return fig


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

_CLIENT_OPTIONS = {
    "Client A – Conservative": "Client A - Conservative",
    "Client B – Moderate": "Client B - Moderate",
    "Client C – Aggressive": "Client C - Aggressive",
}


def render() -> None:
    """Render the Portfolio Analysis page."""

    st.markdown(
        "<h1 style='text-align:center'>💼 Portfolio Analysis</h1>"
        "<p style='text-align:center;color:#94A3B8;margin-bottom:20px'>"
        "Deep-dive into client portfolio performance, risk, and AI recommendations</p>",
        unsafe_allow_html=True,
    )

    # ---- Client selector ----
    selected_label = st.selectbox(
        "Select Client Portfolio",
        list(_CLIENT_OPTIONS.keys()),
        index=0,
    )
    client_name = _CLIENT_OPTIONS[selected_label]

    # ---- Services ----
    data_service = _get_data_service()
    ai_service = _get_ai_service()
    engine = PortfolioEngine(data_service, ai_service)

    with st.spinner("Analysing portfolio…"):
        result = engine.analyze_portfolio(client_name)

    summary = result["summary"]
    allocation = result["allocation"]
    diversification = result["diversification_score"]
    risk_analysis = result["risk_analysis"]
    ai_analysis = result["ai_analysis"]
    future = result["future_projection"]

    # ==================================================================
    # 1. KPI Cards
    # ==================================================================
    st.markdown("### 📊 Portfolio Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            _metric_card(
                "Total Investment",
                format_large_number(summary["total_investment"]),
                color=_COLORS["info"],
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _metric_card(
                "Current Value",
                format_large_number(summary["current_value"]),
                color=_COLORS["primary"],
            ),
            unsafe_allow_html=True,
        )
    with c3:
        ret_color = _COLORS["success"] if summary["total_return"] >= 0 else _COLORS["danger"]
        st.markdown(
            _metric_card(
                "Total Return",
                format_large_number(summary["total_return"]),
                delta=format_pct(summary["total_return_pct"]),
                color=ret_color,
            ),
            unsafe_allow_html=True,
        )

    c4, c5, c6 = st.columns(3)
    with c4:
        st.markdown(
            _metric_card("Return %", format_pct(summary["total_return_pct"]),
                         color=get_color_for_value(summary["total_return_pct"])),
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            _metric_card("CAGR", format_pct(summary["cagr"]),
                         color=get_color_for_value(summary["cagr"])),
            unsafe_allow_html=True,
        )
    with c6:
        risk_color = (
            _COLORS["success"] if summary["risk_score"] <= 4
            else _COLORS["danger"] if summary["risk_score"] >= 7
            else _COLORS["warning"]
        )
        st.markdown(
            _metric_card(
                "Risk Score",
                f"{summary['risk_score']:.1f}/10",
                delta=format_risk_level(int(round(summary["risk_score"]))),
                color=risk_color,
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ==================================================================
    # 2. Allocation Analysis
    # ==================================================================
    st.markdown("### 📂 Allocation Analysis")
    tab_cat, tab_fund, tab_detail = st.tabs(["Category Allocation", "Fund Allocation", "Detailed Holdings"])

    cat_alloc: pd.DataFrame = allocation["category_allocation"]
    fund_alloc: pd.DataFrame = allocation["fund_allocation"]

    # --- Category donut ---
    with tab_cat:
        if not cat_alloc.empty:
            colors = [_cat_color(c) for c in cat_alloc["category"]]
            fig = go.Figure(data=[go.Pie(
                labels=cat_alloc["category"],
                values=cat_alloc["allocation_pct"],
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="#1E1E3C", width=2)),
                textinfo="label+percent",
                textfont=dict(size=12, color="white"),
                hovertemplate="<b>%{label}</b><br>Allocation: %{value:.1f}%<br>"
                              "Value: ₹%{customdata:,.0f}<extra></extra>",
                customdata=cat_alloc["current_value"],
            )])
            fig.update_layout(
                showlegend=True,
                legend=dict(font=dict(color="#E2E8F0", size=11)),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=380,
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No category allocation data.")

    # --- Fund horizontal bar ---
    with tab_fund:
        if not fund_alloc.empty:
            sorted_funds = fund_alloc.sort_values("allocation_pct", ascending=True)
            colors = [_cat_color(c) for c in sorted_funds["category"]]
            fig = go.Figure(go.Bar(
                x=sorted_funds["allocation_pct"],
                y=sorted_funds["fund_name"].str[:40],
                orientation="h",
                marker=dict(color=colors, line=dict(color="rgba(0,0,0,0.2)", width=1)),
                text=[f"{v:.1f}%" for v in sorted_funds["allocation_pct"]],
                textposition="auto",
                textfont=dict(color="white", size=11),
                hovertemplate="<b>%{y}</b><br>Allocation: %{x:.1f}%<extra></extra>",
            ))
            fig.update_layout(
                xaxis_title="Allocation %",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E2E8F0"),
                height=max(350, len(sorted_funds) * 38),
                margin=dict(l=220, r=30, t=20, b=40),
                xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
                yaxis=dict(tickfont=dict(size=11)),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No fund allocation data.")

    # --- Detailed holdings table ---
    with tab_detail:
        if not fund_alloc.empty:
            display_df = fund_alloc.copy()
            display_df["Investment"] = display_df["investment_amount"].apply(format_large_number)
            display_df["Current Value"] = display_df["current_value"].apply(format_large_number)
            display_df["Allocation %"] = display_df["allocation_pct"].apply(lambda v: f"{v:.1f}%")
            display_df["Return"] = (
                (display_df["current_value"] - display_df["investment_amount"])
                / display_df["investment_amount"].replace(0, np.nan) * 100
            ).apply(lambda v: f"{v:+.1f}%" if pd.notna(v) else "N/A")
            st.dataframe(
                display_df[["fund_name", "category", "Investment", "Current Value", "Allocation %", "Return"]].rename(
                    columns={"fund_name": "Fund Name", "category": "Category"}
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No holdings data.")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ==================================================================
    # 3. Diversification Score
    # ==================================================================
    div_col, risk_col = st.columns(2)

    with div_col:
        st.markdown("### 🎯 Diversification Score")
        st.plotly_chart(
            _gauge_chart(diversification, "Diversification (0–100)"),
            use_container_width=True,
        )
        if diversification >= 70:
            st.success("Excellent diversification – well spread across categories.")
        elif diversification >= 40:
            st.warning("Moderate diversification – consider broadening category exposure.")
        else:
            st.error("Low diversification – portfolio is concentrated in few holdings.")

    # ==================================================================
    # 4. Risk Analysis
    # ==================================================================
    with risk_col:
        st.markdown("### ⚡ Risk Analysis")
        st.plotly_chart(
            _gauge_chart(
                risk_analysis["overall_risk_score"],
                f"Overall Risk: {risk_analysis['overall_risk']}",
                max_val=10,
            ),
            use_container_width=True,
        )

    # Risk breakdown radar
    breakdown = risk_analysis.get("risk_breakdown", {})
    if breakdown:
        st.markdown("#### Risk Breakdown")
        categories_r = list(breakdown.keys())
        values_r = list(breakdown.values())
        # Close the radar polygon
        categories_r_closed = categories_r + [categories_r[0]]
        values_r_closed = values_r + [values_r[0]]

        fig = go.Figure(go.Scatterpolar(
            r=values_r_closed,
            theta=categories_r_closed,
            fill="toself",
            fillcolor="rgba(99,102,241,0.2)",
            line=dict(color="#6366F1", width=2),
            marker=dict(color="#8B5CF6", size=6),
            hovertemplate="<b>%{theta}</b>: %{r:.1f}/10<extra></extra>",
        ))
        fig.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(
                    visible=True, range=[0, 10],
                    gridcolor="rgba(148,163,184,0.15)",
                    tickfont=dict(color="#94A3B8", size=10),
                ),
                angularaxis=dict(
                    gridcolor="rgba(148,163,184,0.15)",
                    tickfont=dict(color="#E2E8F0", size=11),
                ),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=350,
            margin=dict(l=60, r=60, t=30, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ==================================================================
    # 5. AI Portfolio Advisor
    # ==================================================================
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(236,72,153,0.10));
            border: 1px solid rgba(99,102,241,0.3);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 16px;
        ">
            <h3 style="margin:0 0 4px">🧠 AI Portfolio Advisor</h3>
            <p style="color:#94A3B8;margin:0;font-size:0.9rem">
                Intelligent analysis powered by
                """ + ("OpenAI GPT" if ai_service.ai_available else "rule-based engine") + """
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Strengths
    with st.expander("✅ Strengths", expanded=True):
        for s in ai_analysis.get("strengths", []):
            st.markdown(f"<div style='color:#10B981;padding:4px 0'>✔ {s}</div>", unsafe_allow_html=True)

    # Weaknesses
    with st.expander("⚠️ Weaknesses", expanded=True):
        for w in ai_analysis.get("weaknesses", []):
            st.markdown(f"<div style='color:#F59E0B;padding:4px 0'>⚠ {w}</div>", unsafe_allow_html=True)

    # Recommendations
    with st.expander("💡 Recommendations", expanded=True):
        for r in ai_analysis.get("recommendations", []):
            st.markdown(f"<div style='color:#3B82F6;padding:4px 0'>💡 {r}</div>", unsafe_allow_html=True)

    # Health score gauge
    health = ai_analysis.get("health_score", 50)
    st.markdown("#### 📊 Portfolio Health Score")
    st.plotly_chart(
        _gauge_chart(health, "Health Score"),
        use_container_width=True,
    )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ==================================================================
    # 6. Future Value Projection
    # ==================================================================
    st.markdown("### 🔮 Future Value Projection")

    years = future["years"]
    current_val = summary["current_value"]

    # Build traces including the starting point
    x_vals = [0] + years
    conservative_vals = [current_val] + future["conservative"]
    moderate_vals = [current_val] + future["moderate"]
    aggressive_vals = [current_val] + future["aggressive"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_vals, y=conservative_vals,
        name=f"Conservative ({future['cagr_conservative']:.1f}%)",
        line=dict(color="#3B82F6", width=2, dash="dot"),
        hovertemplate="Year %{x}: ₹%{y:,.0f}<extra>Conservative</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x_vals, y=moderate_vals,
        name=f"Moderate ({future['cagr_moderate']:.1f}%)",
        line=dict(color="#8B5CF6", width=3),
        hovertemplate="Year %{x}: ₹%{y:,.0f}<extra>Moderate</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x_vals, y=aggressive_vals,
        name=f"Aggressive ({future['cagr_aggressive']:.1f}%)",
        line=dict(color="#10B981", width=2, dash="dash"),
        hovertemplate="Year %{x}: ₹%{y:,.0f}<extra>Aggressive</extra>",
    ))

    fig.update_layout(
        xaxis_title="Years from Now",
        yaxis_title="Portfolio Value (₹)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0"),
        height=400,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
        ),
        margin=dict(l=60, r=30, t=40, b=50),
        xaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
        yaxis=dict(gridcolor="rgba(148,163,184,0.1)"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Projection summary cards
    p1, p2, p3, p4 = st.columns(4)
    for col_st, yr_idx, label in [
        (p1, 0, "1 Year"),
        (p2, 1, "3 Years"),
        (p3, 2, "5 Years"),
        (p4, 3, "10 Years"),
    ]:
        if yr_idx < len(future["moderate"]):
            val = future["moderate"][yr_idx]
            with col_st:
                st.markdown(
                    _metric_card(label, format_large_number(val), color=_COLORS["primary"]),
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
