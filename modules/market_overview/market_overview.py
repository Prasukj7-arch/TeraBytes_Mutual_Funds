"""
Market Overview module for the Mutual Fund Analytics dashboard.
"""

import streamlit as st
import pandas as pd
from databricks_connector.data_service import DataService
from charts.chart_factory import ChartFactory
from charts.theme import COLORS
from utils.formatters import format_currency_cr, format_pct, format_number

@st.cache_resource
def get_data_service():
    return DataService()

def render():
    """Render the Market Overview page."""
    ds = get_data_service()
    
    st.markdown('<h1 class="page-title">📊 Market Overview</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Overall Mutual Fund market size, AUM distributions, and category-level performances.</p>', unsafe_allow_html=True)

    try:
        summary = ds.get_market_summary()
        funds_df = ds.get_all_funds()
    except Exception as e:
        st.error(f"Error loading market summary: {e}")
        return

    # KPI cards row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card info">
            <div class="kpi-label">Total Funds</div>
            <div class="kpi-value">{summary.get("total_funds", 0)}</div>
            <div class="kpi-delta positive">▲ Active Schemes</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="kpi-card accent">
            <div class="kpi-label">Total AUM</div>
            <div class="kpi-value">{format_currency_cr(summary.get("total_aum", 0))}</div>
            <div class="kpi-delta positive">▲ Assets Under Mgmt</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="kpi-card success">
            <div class="kpi-label">Avg 1Y Return</div>
            <div class="kpi-value">{format_pct(summary.get("avg_return_1y", 0))}</div>
            <div class="kpi-delta positive">▲ Market Median</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        best_cat = summary.get("best_category", "")
        best_ret = summary.get("best_category_return", 0)
        st.markdown(f"""
        <div class="kpi-card success">
            <div class="kpi-label">Best Category</div>
            <div class="kpi-value" style="font-size: 1.2rem; padding: 4px 0;">{best_cat}</div>
            <div class="kpi-delta positive">▲ {format_pct(best_ret)} Return</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        worst_cat = summary.get("worst_category", "")
        worst_ret = summary.get("worst_category_return", 0)
        st.markdown(f"""
        <div class="kpi-card danger">
            <div class="kpi-label">Worst Category</div>
            <div class="kpi-value" style="font-size: 1.2rem; padding: 4px 0;">{worst_cat}</div>
            <div class="kpi-delta negative">▼ {format_pct(worst_ret)} Return</div>
        </div>
        """, unsafe_allow_html=True)

    with col6:
        st.markdown(f"""
        <div class="kpi-card warning">
            <div class="kpi-label">Avg Risk Score</div>
            <div class="kpi-value">{format_number(summary.get("avg_risk_score", 5.0))} / 10</div>
            <div class="kpi-delta">⚡ Market Risk Index</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Row 1 Charts: AUM distribution and Category Return
    r1_col1, r1_col2 = st.columns(2)
    
    with r1_col1:
        st.markdown('<div class="section-subheader">💼 AUM Allocation by Category</div>', unsafe_allow_html=True)
        # Group by category
        cat_aum = funds_df.groupby("category")["aum"].sum().reset_index()
        fig_aum = ChartFactory.pie_chart(cat_aum, names="category", values="aum", title="AUM Distribution")
        st.plotly_chart(fig_aum, use_container_width=True)

    with r1_col2:
        st.markdown('<div class="section-subheader">📈 Average returns by Category (1Y vs 3Y)</div>', unsafe_allow_html=True)
        cat_perf = funds_df.groupby("category")[["returns_1y", "returns_3y"]].mean().reset_index()
        fig_perf = ChartFactory.grouped_bar_chart(cat_perf, x="category", y_columns=["returns_1y", "returns_3y"], title="Category Returns")
        st.plotly_chart(fig_perf, use_container_width=True)

    # Row 2 Charts: Treemap and Heatmap
    r2_col1, r2_col2 = st.columns(2)

    with r2_col1:
        st.markdown('<div class="section-subheader">🌳 Market Hierarchy (Category > Fund House)</div>', unsafe_allow_html=True)
        # Treemap
        fig_tree = ChartFactory.treemap(funds_df, path=["category", "fund_house"], values="aum", title="AUM Treemap")
        st.plotly_chart(fig_tree, use_container_width=True)

    with r2_col2:
        st.markdown('<div class="section-subheader">🔥 Category Performance Matrix</div>', unsafe_allow_html=True)
        # Average returns for category
        cat_matrix = funds_df.groupby("category")[["returns_1m", "returns_3m", "returns_6m", "returns_1y", "returns_3y", "returns_5y"]].mean()
        fig_heat = ChartFactory.heatmap(cat_matrix, title="Category Returns Heatmap")
        st.plotly_chart(fig_heat, use_container_width=True)

    # Row 3: Fund Count and Risk vs Returns
    r3_col1, r3_col2 = st.columns(2)

    with r3_col1:
        st.markdown('<div class="section-subheader">📊 Scheme Distribution across Asset Classes</div>', unsafe_allow_html=True)
        cat_count = funds_df.groupby("category")["fund_name"].count().reset_index()
        fig_count = ChartFactory.bar_chart(cat_count, x="category", y="fund_name", title="Scheme Count by Category")
        st.plotly_chart(fig_count, use_container_width=True)

    with r3_col2:
        st.markdown('<div class="section-subheader">🔵 Risk (Beta) vs Reward (1Y Return)</div>', unsafe_allow_html=True)
        # Scatterplot
        fig_scatter = ChartFactory.scatter_chart(
            funds_df,
            x="beta",
            y="returns_1y",
            title="Volatility Risk Frontier",
            size_col="aum",
            color_col="category",
            hover_name="fund_name"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
