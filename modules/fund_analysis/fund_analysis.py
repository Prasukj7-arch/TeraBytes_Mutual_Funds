"""
Fund Performance Analytics module for the Mutual Fund Analytics dashboard.
"""

import streamlit as st
import pandas as pd
from databricks_connector.data_service import DataService
from charts.chart_factory import ChartFactory
from charts.theme import COLORS
from utils.formatters import format_currency, format_currency_cr, format_pct, format_number, format_risk_level

@st.cache_resource
def get_data_service():
    return DataService()

def render():
    """Render the Fund Analytics page."""
    ds = get_data_service()

    st.markdown('<h1 class="page-title">🔍 Fund Performance Analytics</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Deep dive statistics, NAV historical lines, and risk-adjusted metrics for individual schemes.</p>', unsafe_allow_html=True)

    try:
        funds_df = ds.get_all_funds()
    except Exception as e:
        st.error(f"Error loading fund list: {e}")
        return

    # 1. Fund Selection
    fund_names = sorted(funds_df["fund_name"].tolist())
    selected_fund_name = st.selectbox("Search & Select Mutual Fund", fund_names)

    if not selected_fund_name:
        st.warning("Please select a fund.")
        return

    fund = ds.get_fund_by_name(selected_fund_name)
    category = fund["category"]

    # 2. Render KPIs (NAV, AUM, Expense, Sharpe, Alpha, Beta, Volatility, CAGR, Max Drawdown, Risk Score)
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card info">
            <div class="kpi-label">Current NAV</div>
            <div class="kpi-value">{format_currency(fund.get("nav", 0))}</div>
            <div class="kpi-delta">Net Asset Value</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="kpi-card accent">
            <div class="kpi-label">AUM (Size)</div>
            <div class="kpi-value">{format_currency_cr(fund.get("aum", 0))}</div>
            <div class="kpi-delta">Crores</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="kpi-card danger">
            <div class="kpi-label">Expense Ratio</div>
            <div class="kpi-value">{format_number(fund.get("expense_ratio", 1.0))}%</div>
            <div class="kpi-delta">TER</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="kpi-card success">
            <div class="kpi-label">Sharpe Ratio</div>
            <div class="kpi-value">{format_number(fund.get("sharpe_ratio", 1.0))}</div>
            <div class="kpi-delta">Risk-Adjusted</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="kpi-card success">
            <div class="kpi-label">Alpha</div>
            <div class="kpi-value">{format_pct(fund.get("alpha", 0))}</div>
            <div class="kpi-delta">Excess Return</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)

    col6, col7, col8, col9, col10 = st.columns(5)

    with col6:
        st.markdown(f"""
        <div class="kpi-card info">
            <div class="kpi-label">Beta</div>
            <div class="kpi-value">{format_number(fund.get("beta", 1.0))}</div>
            <div class="kpi-delta">Market Correlation</div>
        </div>
        """, unsafe_allow_html=True)

    with col7:
        st.markdown(f"""
        <div class="kpi-card warning">
            <div class="kpi-label">Volatility</div>
            <div class="kpi-value">{format_number(fund.get("volatility", 10.0))}%</div>
            <div class="kpi-delta">Standard Deviation</div>
        </div>
        """, unsafe_allow_html=True)

    with col8:
        st.markdown(f"""
        <div class="kpi-card success">
            <div class="kpi-label">Expected CAGR</div>
            <div class="kpi-value">{format_pct(fund.get("cagr", fund.get("returns_5y", 12.0)))}</div>
            <div class="kpi-delta">5Y Return (CAGR)</div>
        </div>
        """, unsafe_allow_html=True)

    with col9:
        st.markdown(f"""
        <div class="kpi-card danger">
            <div class="kpi-label">Max Drawdown</div>
            <div class="kpi-value">{format_number(fund.get("max_drawdown", -10.0))}%</div>
            <div class="kpi-delta">Peak-to-Trough Decline</div>
        </div>
        """, unsafe_allow_html=True)

    with col10:
        score = int(fund.get("risk_score", 5))
        st.markdown(f"""
        <div class="kpi-card warning">
            <div class="kpi-label">Riskometer</div>
            <div class="kpi-value">{score} / 10</div>
            <div class="kpi-delta">{format_risk_level(score)} Risk Profile</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Historical NAV chart
    st.markdown('<div class="section-subheader">📈 Historical Net Asset Value (NAV) Line</div>', unsafe_allow_html=True)
    
    # Range select
    period_options = {
        "1 Month": 30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year": 365,
        "3 Years": 1095,
        "Max": 9999
    }
    selected_period = st.radio("Time Frame", list(period_options.keys()), index=3, horizontal=True)
    
    try:
        nav_history = ds.get_nav_history(selected_fund_name)
        if not nav_history.empty:
            date_col = "nav_date" if "nav_date" in nav_history.columns else ("date" if "date" in nav_history.columns else nav_history.columns[0])
            nav_history["date"] = pd.to_datetime(nav_history[date_col])
            nav_history = nav_history.sort_values(by="date")
            
            days = period_options[selected_period]
            if days != 9999:
                cutoff_date = nav_history["date"].max() - pd.Timedelta(days=days)
                nav_history = nav_history[nav_history["date"] >= cutoff_date]
                
            fig_nav = ChartFactory.line_chart(nav_history, x="date", y="nav", title=f"{selected_fund_name} NAV Trend")
            st.plotly_chart(fig_nav, use_container_width=True)
        else:
            st.info("No daily NAV history data available.")
    except Exception as e:
        st.error(f"Error loading NAV history: {e}")

    # Return comparison block
    st.markdown("<br>", unsafe_allow_html=True)
    r3_col1, r3_col2 = st.columns(2)

    with r3_col1:
        st.markdown('<div class="section-subheader">⏱️ Returns Timeline comparison (vs Category Average)</div>', unsafe_allow_html=True)
        # Compute category averages
        cat_avg = funds_df[funds_df["category"] == category][["returns_1m", "returns_3m", "returns_6m", "returns_1y", "returns_3y", "returns_5y"]].mean().reset_index()
        cat_avg.columns = ["Period", "Category Average"]
        
        fund_ret = pd.DataFrame({
            "Period": ["returns_1m", "returns_3m", "returns_6m", "returns_1y", "returns_3y", "returns_5y"],
            "Fund Return": [fund.get(p, 0) for p in ["returns_1m", "returns_3m", "returns_6m", "returns_1y", "returns_3y", "returns_5y"]]
        })
        
        comp_df = pd.merge(fund_ret, cat_avg, on="Period")
        # Format Period labels
        comp_df["Period"] = comp_df["Period"].str.replace("returns_", "").str.upper()
        
        fig_comp = ChartFactory.grouped_bar_chart(comp_df, x="Period", y_columns=["Fund Return", "Category Average"], title="Fund vs Category Return Analysis")
        st.plotly_chart(fig_comp, use_container_width=True)

    with r3_col2:
        st.markdown('<div class="section-subheader">🔮 Peer Risk-Return Position (Bubble Chart)</div>', unsafe_allow_html=True)
        # All funds in category, highlight selected
        peers = funds_df[funds_df["category"] == category].copy()
        peers["is_selected"] = peers["fund_name"] == selected_fund_name
        peers["Selected Highlight"] = peers["is_selected"].map({True: "Selected Scheme", False: "Peer Scheme"})

        fig_bubble = ChartFactory.bubble_chart(
            peers,
            x="volatility",
            y="returns_1y",
            size="aum",
            title=f"Category: {category} — Risk vs Return Positioning",
            color_col="Selected Highlight",
            hover_name="fund_name"
        )
        st.plotly_chart(fig_bubble, use_container_width=True)
