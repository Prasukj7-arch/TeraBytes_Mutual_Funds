"""
Fund Ups & Downs Analysis module for the Mutual Fund Analytics dashboard.
"""

import streamlit as st
import pandas as pd
from databricks_connector.data_service import DataService
from charts.chart_factory import ChartFactory
from charts.theme import COLORS
from utils.formatters import format_pct, format_currency_cr

@st.cache_resource
def get_data_service():
    return DataService()

def render():
    """Render the Fund Ups & Downs page."""
    ds = get_data_service()

    st.markdown('<h1 class="page-title">📈 Fund Ups & Downs Analysis</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Identify top performing gainers and underperforming losers across different return horizons.</p>', unsafe_allow_html=True)

    # Horizon period selection
    period_map = {
        "1 Month": "returns_1m",
        "3 Months": "returns_3m",
        "6 Months": "returns_6m",
        "1 Year": "returns_1y",
        "3 Years": "returns_3y",
        "5 Years": "returns_5y",
    }
    
    selected_period = st.radio("Select Return Horizon", list(period_map.keys()), index=3, horizontal=True)
    period_col = period_map[selected_period]

    try:
        gainers = ds.get_top_performers(n=10, period=period_col)
        losers = ds.get_bottom_performers(n=10, period=period_col)
        all_funds = ds.get_all_funds()
    except Exception as e:
        st.error(f"Error loading gainers/losers: {e}")
        return

    # Render top 10 gainers & losers tables in two columns
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-subheader">🟢 Top 10 Gainers</div>', unsafe_allow_html=True)
        # Select columns to display
        g_disp = gainers[["fund_name", "category", period_col, "aum"]].copy()
        g_disp.columns = ["Fund Name", "Category", "Return %", "AUM (Cr)"]
        g_disp["Return %"] = g_disp["Return %"].map(lambda x: f"+{x:.2f}%")
        g_disp["AUM (Cr)"] = g_disp["AUM (Cr)"].map(lambda x: f"₹{x:,.0f} Cr")
        
        # Display as streamlit dataframe with nice styling configuration
        st.dataframe(
            g_disp,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Return %": st.column_config.TextColumn(help="Fund appreciation return", validate="^\\+.*"),
            }
        )

    with col2:
        st.markdown('<div class="section-subheader">🔴 Top 10 Losers</div>', unsafe_allow_html=True)
        l_disp = losers[["fund_name", "category", period_col, "aum"]].copy()
        l_disp.columns = ["Fund Name", "Category", "Return %", "AUM (Cr)"]
        l_disp["Return %"] = l_disp["Return %"].map(lambda x: f"{x:.2f}%")
        l_disp["AUM (Cr)"] = l_disp["AUM (Cr)"].map(lambda x: f"₹{x:,.0f} Cr")
        
        st.dataframe(
            l_disp,
            hide_index=True,
            use_container_width=True
        )

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Combined performance ranking bar chart
    st.markdown('<div class="section-subheader">📊 Return Frontier (Top vs Bottom Performers)</div>', unsafe_allow_html=True)
    
    # Combine gainers and losers
    gainers_clean = gainers.copy().head(5)
    losers_clean = losers.copy().head(5)
    combined = pd.concat([gainers_clean, losers_clean])
    combined["Performance Profile"] = combined[period_col].apply(lambda x: "Gainer" if x >= 0 else "Loser")

    fig_rank = ChartFactory.horizontal_bar_chart(
        combined,
        x=period_col,
        y="fund_name",
        title=f"Top 5 Gainers & Bottom 5 Losers ({selected_period})",
        color_col="Performance Profile"
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    # Category average bar chart
    st.markdown('<div class="section-subheader">🏷️ Asset Category Average Performance</div>', unsafe_allow_html=True)
    cat_avg = all_funds.groupby("category")[period_col].mean().reset_index().sort_values(by=period_col, ascending=False)
    
    fig_cat_avg = ChartFactory.bar_chart(
        cat_avg,
        x="category",
        y=period_col,
        title=f"Category Average Returns ({selected_period})",
        color_col="category"
    )
    st.plotly_chart(fig_cat_avg, use_container_width=True)
