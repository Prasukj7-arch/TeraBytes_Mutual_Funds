"""
Category Analytics module for the Mutual Fund Analytics dashboard.
"""

import streamlit as st
import pandas as pd
import numpy as np
from databricks_connector.data_service import DataService
from charts.chart_factory import ChartFactory
from charts.theme import COLORS
from utils.formatters import format_currency_cr, format_pct, format_number, format_risk_level

@st.cache_resource
def get_data_service():
    return DataService()

def render():
    """Render the Category Analytics page."""
    ds = get_data_service()

    st.markdown('<h1 class="page-title">📂 Category Analytics</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Deep dive benchmarking of specific mutual fund categories against the broader market index.</p>', unsafe_allow_html=True)

    try:
        categories = ds.get_categories()
        all_funds = ds.get_all_funds()
    except Exception as e:
        st.error(f"Error loading category data: {e}")
        return

    # Category Selector
    selected_cat = st.selectbox("Select Asset Category", categories)

    if not selected_cat:
        st.warning("Please select a category.")
        return

    # Filter data
    cat_df = all_funds[all_funds["category"] == selected_cat].copy()
    
    # Calculate statistics
    num_funds = len(cat_df)
    avg_aum = cat_df["aum"].mean()
    avg_ret_1y = cat_df["returns_1y"].mean()
    avg_sharpe = cat_df["sharpe_ratio"].mean()
    avg_risk = cat_df["risk_score"].mean()

    # KPI Summary Row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""
        <div class="kpi-card info">
            <div class="kpi-label">Number of Funds</div>
            <div class="kpi-value">{num_funds}</div>
            <div class="kpi-delta">Active Schemes</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="kpi-card accent">
            <div class="kpi-label">Average AUM</div>
            <div class="kpi-value">{format_currency_cr(avg_aum)}</div>
            <div class="kpi-delta">Crores per Fund</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="kpi-card success">
            <div class="kpi-label">Average 1Y Return</div>
            <div class="kpi-value">{format_pct(avg_ret_1y)}</div>
            <div class="kpi-delta">Annualized</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="kpi-card success">
            <div class="kpi-label">Average Sharpe</div>
            <div class="kpi-value">{format_number(avg_sharpe)}</div>
            <div class="kpi-delta">Risk-Adjusted Ratio</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="kpi-card warning">
            <div class="kpi-label">Average Risk</div>
            <div class="kpi-value">{format_number(avg_risk)} / 10</div>
            <div class="kpi-delta">{format_risk_level(avg_risk)} Category Profile</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Performance Charts
    r1_col1, r1_col2 = st.columns(2)

    with r1_col1:
        st.markdown(f'<div class="section-subheader">🟢 Top 10 Schemes in {selected_cat} by 1Y Returns</div>', unsafe_allow_html=True)
        top_funds = cat_df.sort_values(by="returns_1y", ascending=False).head(10)
        fig_top = ChartFactory.bar_chart(top_funds, x="fund_name", y="returns_1y", title="Top 10 Funds", color_col="fund_name")
        st.plotly_chart(fig_top, use_container_width=True)

    with r1_col2:
        st.markdown('<div class="section-subheader">🕸️ Risk Factor Radar Benchmarking</div>', unsafe_allow_html=True)
        
        # Category avg vs market avg
        metrics = ["sharpe_ratio", "alpha", "beta", "volatility", "risk_score"]
        cat_vals = [cat_df[m].mean() for m in metrics]
        mkt_vals = [all_funds[m].mean() for m in metrics]

        # Normalise metrics to 0-1 scale for visual stability on radar
        cat_vals_norm = []
        mkt_vals_norm = []
        for i, m in enumerate(metrics):
            min_val = all_funds[m].min()
            max_val = all_funds[m].max()
            rng = (max_val - min_val) if max_val != min_val else 1.0
            cat_vals_norm.append((cat_vals[i] - min_val) / rng)
            mkt_vals_norm.append((mkt_vals[i] - min_val) / rng)

        # Plot radar
        fig_radar = ChartFactory.radar_chart(
            categories=["Sharpe", "Alpha", "Beta", "Volatility", "Risk Score"],
            values=cat_vals_norm,
            title="Category Risk Profile vs Market Average"
        )
        
        # Add market avg line to radar
        import plotly.graph_objects as go
        fig_radar.add_trace(go.Scatterpolar(
            r=mkt_vals_norm,
            theta=["Sharpe", "Alpha", "Beta", "Volatility", "Risk Score"],
            fill='toself',
            name='Market Average',
            line=dict(color=COLORS['secondary'])
        ))
        
        st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Volatility and AUM distributions
    r2_col1, r2_col2 = st.columns(2)

    with r2_col1:
        st.markdown('<div class="section-subheader">📊 Volatility Distribution (Daily Std Dev)</div>', unsafe_allow_html=True)
        fig_hist = ChartFactory.histogram(cat_df, x="volatility", title="Scheme Volatility Histogram")
        st.plotly_chart(fig_hist, use_container_width=True)

    with r2_col2:
        st.markdown('<div class="section-subheader">💼 AUM Concentration (Largest to Smallest Schemes)</div>', unsafe_allow_html=True)
        aum_sorted = cat_df.sort_values(by="aum", ascending=False)
        fig_area = ChartFactory.area_chart(aum_sorted, x="fund_name", y="aum", title="AUM Size Distribution")
        st.plotly_chart(fig_area, use_container_width=True)
