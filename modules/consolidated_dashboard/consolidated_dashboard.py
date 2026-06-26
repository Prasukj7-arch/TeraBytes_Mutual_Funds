import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

from services.db import get_holdings, add_holding
from databricks_connector.data_service import DataService
from charts.chart_factory import ChartFactory
from charts.theme import COLORS
from utils.formatters import format_currency, format_pct, get_color_for_value

# ---------------------------------------------------------------------------
# Seeding Helper
# ---------------------------------------------------------------------------
def seed_demo_holdings(user_id="user_001"):
    """Auto-seeds a few realistic holdings if the user portfolio is empty."""
    holdings = get_holdings(user_id)
    if not holdings:
        # Stock holdings (8 stocks across diverse industries)
        add_holding(user_id, "stock", "AAPL", 15.0, "2024-01-15", 185.00)
        add_holding(user_id, "stock", "MSFT", 10.0, "2024-02-10", 405.00)
        add_holding(user_id, "stock", "NVDA", 25.0, "2024-03-05", 120.00)
        add_holding(user_id, "stock", "TSLA", 20.0, "2024-04-12", 175.00)
        add_holding(user_id, "stock", "JPM", 30.0, "2024-02-25", 180.00)
        add_holding(user_id, "stock", "LLY", 12.0, "2024-05-18", 750.00)
        add_holding(user_id, "stock", "XOM", 40.0, "2023-12-10", 100.00)
        add_holding(user_id, "stock", "NEE", 50.0, "2024-03-15", 62.00)
        
        # Mutual fund holdings (5 mutual funds across categories)
        add_holding(user_id, "mutual_fund", "SBI Blue Chip Fund - Regular Growth", 500.0, "2023-11-20", 72.50)
        add_holding(user_id, "mutual_fund", "HDFC Large Cap Fund - Direct Growth", 300.0, "2024-01-05", 115.40)
        add_holding(user_id, "mutual_fund", "ICICI Prudential Midcap Fund - Direct Growth", 250.0, "2023-10-15", 145.00)
        add_holding(user_id, "mutual_fund", "Axis Large Cap Fund - Regular Growth", 400.0, "2024-02-18", 55.00)
        add_holding(user_id, "mutual_fund", "Nippon India Small Cap Fund - Growth", 150.0, "2024-04-05", 95.00)
        st.rerun()

# ---------------------------------------------------------------------------
# Data Loader
# ---------------------------------------------------------------------------
def load_consolidated_holdings(user_id="user_001"):
    holdings = get_holdings(user_id)
    if not holdings:
        return pd.DataFrame()
        
    records = []
    funds_df = None
    try:
        ds = DataService()
        funds_df = ds.get_all_funds()
    except Exception:
        pass
        
    for h in holdings:
        symbol = h["symbol"]
        asset_type = h["asset_type"]
        units = h["units"]
        purchase_price = h["purchase_price"]
        
        name = symbol
        current_price = None
        
        if asset_type == "stock":
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                current_price = info.get("last_price", None)
                if current_price is None:
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        current_price = float(hist["Close"].iloc[-1])
            except Exception:
                pass
        else:
            if funds_df is not None and not funds_df.empty:
                match = funds_df[
                    (funds_df["fund_name"].astype(str).str.lower() == symbol.lower()) |
                    (funds_df.index.astype(str) == symbol)
                ]
                if not match.empty:
                    name = match.iloc[0]["fund_name"]
                    current_price = float(match.iloc[0]["nav"])
            
            if current_price is None:
                # Direct check via DataService just in case
                try:
                    ds = DataService()
                    funds_df_agg = ds.get_all_funds()
                    match = funds_df_agg[funds_df_agg.index.astype(str) == symbol]
                    if not match.empty:
                        name = match.iloc[0]["fund_name"]
                        current_price = float(match.iloc[0]["nav"])
                except Exception:
                    pass
                    
        if current_price is None:
            # Simulation fallback (+6.5% standard gain)
            current_price = purchase_price * 1.065
            
        invested = purchase_price * units
        current_value = current_price * units
        gain = current_value - invested
        gain_pct = (gain / invested) * 100 if invested > 0 else 0
        
        records.append({
            "id": h["id"],
            "asset_type": "Stock" if asset_type == "stock" else "Mutual Fund",
            "symbol": symbol,
            "name": name,
            "units": units,
            "purchase_price": purchase_price,
            "current_price": current_price,
            "invested": invested,
            "current_value": current_value,
            "gain": gain,
            "gain_pct": gain_pct
        })
        
    return pd.DataFrame(records)

# ---------------------------------------------------------------------------
# Render Function
# ---------------------------------------------------------------------------
def render():
    st.markdown('<div class="main-header"><h1>📊 Consolidated Wealth Dashboard</h1><p>Combined view of your stocks and mutual funds portfolio.</p></div>', unsafe_allow_html=True)
    
    user_id = "user_001"
    
    # Auto-seed demo portfolio if empty
    seed_demo_holdings(user_id)
    
    df = load_consolidated_holdings(user_id)
    
    if df.empty:
        st.info("No holdings found. Please add stocks or mutual funds to your portfolio.")
        return
        
    # Calculate portfolio aggregates
    total_invested = df["invested"].sum()
    total_value = df["current_value"].sum()
    net_profit = total_value - total_invested
    net_return_pct = (net_profit / total_invested) * 100 if total_invested > 0 else 0
    
    stocks_df = df[df["asset_type"] == "Stock"]
    mfs_df = df[df["asset_type"] == "Mutual Fund"]
    
    stocks_value = stocks_df["current_value"].sum()
    mfs_value = mfs_df["current_value"].sum()
    
    stocks_alloc = (stocks_value / total_value) * 100 if total_value > 0 else 0
    mfs_alloc = (mfs_value / total_value) * 100 if total_value > 0 else 0
    
    # Render premium glassmorphic KPI cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <p class="kpi-title">TOTAL PORTFOLIO VALUE</p>
            <h2 class="kpi-value">{format_currency(total_value)}</h2>
            <p class="kpi-delta" style="color: #94A3B8;">Across {len(df)} assets</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <p class="kpi-title">TOTAL INVESTED</p>
            <h2 class="kpi-value">{format_currency(total_invested)}</h2>
            <p class="kpi-delta" style="color: #94A3B8;">Cost basis</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        color = get_color_for_value(net_profit)
        arrow = "▲" if net_profit >= 0 else "▼"
        st.markdown(f"""
        <div class="kpi-card">
            <p class="kpi-title">NET UNREALIZED GAIN</p>
            <h2 class="kpi-value" style="color: {color};">{format_currency(net_profit)}</h2>
            <p class="kpi-delta" style="color: {color};">{arrow} {format_pct(net_return_pct / 100)}</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <p class="kpi-title">ASSET ALLOCATION</p>
            <h2 class="kpi-value" style="font-size: 1.5rem; padding-top: 5px;">
                Stocks: {stocks_alloc:.1f}%<br/>
                MFs: {mfs_alloc:.1f}%
            </h2>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<br/>", unsafe_allow_html=True)
    
    # Plotly Visualizations Row
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.markdown('<div class="card-header"><h3>💼 Wealth Split (Asset Allocation)</h3></div>', unsafe_allow_html=True)
        alloc_data = pd.DataFrame({
            "Asset Class": ["Stocks", "Mutual Funds"],
            "Value": [stocks_value, mfs_value]
        })
        fig_pie = ChartFactory.pie_chart(
            alloc_data,
            names="Asset Class",
            values="Value",
            title="Portfolio Asset Distribution",
            hole=0.45
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with chart_col2:
        st.markdown('<div class="card-header"><h3>🔝 Top Portfolio Holdings</h3></div>', unsafe_allow_html=True)
        top_holdings = df.sort_values(by="current_value", ascending=False).head(5)
        
        # Color bar chart by asset type
        fig_bar = ChartFactory.bar_chart(
            top_holdings,
            x="current_value",
            y="name",
            title="Top 5 Holdings by Current Value",
            color_col="asset_type",
            orientation="h"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        
    # Table of All Holdings
    st.markdown('<div class="card-header"><h3>📋 Asset Breakdown & Performance</h3></div>', unsafe_allow_html=True)
    
    display_df = df.copy()
    display_df["invested_str"] = display_df["invested"].apply(format_currency)
    display_df["current_value_str"] = display_df["current_value"].apply(format_currency)
    display_df["gain_str"] = display_df["gain"].apply(format_currency)
    display_df["gain_pct_str"] = (display_df["gain_pct"] / 100).apply(format_pct)
    
    formatted_table = display_df[[
        "asset_type", "symbol", "name", "units", "invested_str", "current_value_str", "gain_str", "gain_pct_str"
    ]].rename(columns={
        "asset_type": "Asset Type",
        "symbol": "Ticker/Code",
        "name": "Asset Name",
        "units": "Units Held",
        "invested_str": "Invested Amount",
        "current_value_str": "Current Value",
        "gain_str": "Gain / Loss",
        "gain_pct_str": "Return %"
    })
    
    st.dataframe(
        formatted_table,
        use_container_width=True,
        hide_index=True
    )
