import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date

from services.db import get_holdings, add_holding, delete_holding
from databricks_connector.data_service import DataService
from charts.chart_factory import ChartFactory
from utils.formatters import format_currency, format_pct, get_color_for_value, format_risk_level

# ---------------------------------------------------------------------------
# Card Helpers
# ---------------------------------------------------------------------------
def _metric_card(label: str, value: str, delta: str = "", color: str = "#6366F1") -> str:
    delta_html = ""
    if delta:
        d_color = "#10B981" if not delta.startswith("-") and not delta.startswith("▼") else "#EF4444"
        delta_html = f'<div style="font-size:0.85rem;color:{d_color};margin-top:2px">{delta}</div>'

    return f"""
    <div style="
        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08));
        border: 1px solid rgba(99,102,241,0.25);
        border-radius: 16px;
        padding: 16px 12px;
        text-align: center;
        backdrop-filter: blur(10px);
        margin-bottom: 10px;
    ">
        <div style="font-size:0.8rem;color:#94A3B8;margin-bottom:4px">{label}</div>
        <div style="font-size:1.4rem;font-weight:700;color:{color}">{value}</div>
        {delta_html}
    </div>
    """

# ---------------------------------------------------------------------------
# Data Fetcher (cached for speed)
# ---------------------------------------------------------------------------
def load_and_calculate_holdings(user_id="user_001"):
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
        risk_score = 5.0  # default medium
        category = "Other"
        
        if asset_type == "stock":
            category = "Equities"
            # Get Stock price
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                current_price = info.get("last_price", None)
                if current_price is None:
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        current_price = float(hist["Close"].iloc[-1])
                        
                beta = info.get("beta", 1.0)
                risk_score = min(max(beta * 6.0, 1.0), 10.0) # custom stock risk heuristic
            except Exception:
                pass
        else:
            # Get Mutual Fund NAV
            if funds_df is not None and not funds_df.empty:
                match = funds_df[
                    (funds_df["fund_name"].astype(str).str.lower() == symbol.lower()) |
                    (funds_df.index.astype(str) == symbol)
                ]
                if not match.empty:
                    name = match.iloc[0]["fund_name"]
                    current_price = float(match.iloc[0]["nav"])
                    risk_score = float(match.iloc[0].get("risk_score", 5.0))
                    category = match.iloc[0].get("category", "Mutual Funds")
            
            if current_price is None:
                try:
                    ds = DataService()
                    funds_df_agg = ds.get_all_funds()
                    match = funds_df_agg[funds_df_agg.index.astype(str) == symbol]
                    if not match.empty:
                        name = match.iloc[0]["fund_name"]
                        current_price = float(match.iloc[0]["nav"])
                        risk_score = float(match.iloc[0].get("risk_score", 5.0))
                        category = match.iloc[0].get("category", "Mutual Funds")
                except Exception:
                    pass
                    
        if current_price is None:
            current_price = purchase_price * 1.065  # simulation fallback
            
        invested = purchase_price * units
        current_value = current_price * units
        gain = current_value - invested
        gain_pct = (gain / invested) * 100 if invested > 0 else 0
        
        records.append({
            "id": h["id"],
            "asset_type": "Stock" if asset_type == "stock" else "Mutual Fund",
            "symbol": symbol,
            "name": name,
            "category": category,
            "units": units,
            "purchase_price": purchase_price,
            "current_price": current_price,
            "invested": invested,
            "current_value": current_value,
            "gain": gain,
            "gain_pct": gain_pct,
            "risk_score": risk_score,
            "purchase_date": h["purchase_date"]
        })
        
    df = pd.DataFrame(records)
    # Calculate allocations
    if not df.empty:
        total_val = df["current_value"].sum()
        df["allocation_pct"] = (df["current_value"] / total_val) * 100 if total_val > 0 else 0
    return df

# ---------------------------------------------------------------------------
# Render Page
# ---------------------------------------------------------------------------
def render():
    st.markdown('<div class="main-header"><h1>💼 Consolidated Portfolio Manager</h1><p>Analyze your net asset performance, add new investments, and track risk metrics.</p></div>', unsafe_allow_html=True)
    
    user_id = "user_001"
    
    # -----------------------------------------------------------------------
    # Column splits for Management vs Analysis
    # -----------------------------------------------------------------------
    col_input, col_view = st.columns([1, 2])
    
    with col_input:
        st.markdown("### ➕ Add New Holding")
        asset_type = st.selectbox("Asset Class", ["Stock", "Mutual Fund"])
        
        # Load mutual funds list for suggestions if selected
        mf_options = []
        try:
            ds = DataService()
            funds_df = ds.get_all_funds()
            if not funds_df.empty:
                mf_options = list(funds_df["fund_name"].values)
        except Exception:
            pass
            
        # Dynamically render inputs
        if asset_type == "Stock":
            symbol = st.text_input("Ticker Symbol (e.g. AAPL, MSFT, TSLA)").strip().upper()
        else:
            if mf_options:
                symbol = st.selectbox("Select Mutual Fund", mf_options)
            else:
                symbol = st.text_input("Enter Mutual Fund Name/Code").strip()
                
        units = st.number_input("Units Purchased", min_value=0.0, step=1.0, value=10.0)
        p_price = st.number_input("Purchase Price / NAV", min_value=0.0, step=1.0, value=100.0)
        p_date = st.date_input("Purchase Date", max_value=date.today())
        
        if st.button("💾 Save Holding", use_container_width=True):
            if symbol:
                db_asset_type = "stock" if asset_type == "Stock" else "mutual_fund"
                add_holding(user_id, db_asset_type, symbol, units, str(p_date), p_price)
                st.success(f"Holding for {symbol} saved successfully!")
                time_sleep = 0.5
                st.rerun()
            else:
                st.error("Please enter a valid symbol or select a fund.")
                
    with col_view:
        st.markdown("### 📋 Current Portfolio Holdings")
        df = load_and_calculate_holdings(user_id)
        
        if df.empty:
            st.info("Your portfolio is currently empty. Add assets in the sidebar/input panel to see analytics.")
            return
            
        # Display holdings with delete buttons
        for idx, row in df.iterrows():
            with st.container():
                col_name, col_perf, col_action = st.columns([3, 2, 1])
                with col_name:
                    badge_color = "#3B82F6" if row["asset_type"] == "Stock" else "#8B5CF6"
                    st.markdown(f"""
                    **{row['name']}**  
                    <span style="background-color: {badge_color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">{row['asset_type']}</span>
                    <span style="font-size: 0.8rem; color: #94A3B8;"> | {row['units']:.2f} units @ ${row['purchase_price']:,.2f}</span>
                    """, unsafe_allow_html=True)
                with col_perf:
                    color = get_color_for_value(row["gain"])
                    arrow = "▲" if row["gain"] >= 0 else "▼"
                    st.markdown(f"""
                    <div style="text-align: right;">
                        <span style="font-weight: bold; color: #F8FAFC;">{format_currency(row['current_value'])}</span><br/>
                        <span style="font-size: 0.8rem; color: {color}; font-weight: bold;">{arrow} {format_pct(row['gain_pct']/100)}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with col_action:
                    if st.button("🗑️", key=f"del_h_{row['id']}"):
                        delete_holding(row["id"])
                        st.success("Holding deleted!")
                        st.rerun()
                st.markdown('<hr style="margin: 0.5rem 0; border-color: rgba(148,163,184,0.1);"/>', unsafe_allow_html=True)
                
    st.markdown("---")
    
    # -----------------------------------------------------------------------
    # Portfolio Analysis Metrics & Projections
    # -----------------------------------------------------------------------
    st.markdown("### 📊 Consolidated Wealth Analytics")
    
    total_invested = df["invested"].sum()
    total_value = df["current_value"].sum()
    net_profit = total_value - total_invested
    net_return_pct = (net_profit / total_invested) * 100 if total_invested > 0 else 0
    
    # Weighted risk score
    weighted_risk = (df["risk_score"] * df["allocation_pct"]).sum() / 100
    
    # Diversification (HHI-based)
    hhi = (df["allocation_pct"] ** 2).sum() / 10000
    diversification = 100 * (1.0 - hhi)
    
    # KPI metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(_metric_card("Net Worth Value", format_currency(total_value)), unsafe_allow_html=True)
    with col2:
        st.markdown(_metric_card("Unrealized Profit", format_currency(net_profit), delta=format_pct(net_return_pct/100)), unsafe_allow_html=True)
    with col3:
        risk_color = "#10B981" if weighted_risk <= 4 else ("#EF4444" if weighted_risk >= 7 else "#F59E0B")
        st.markdown(_metric_card("Weighted Risk", f"{weighted_risk:.1f}/10", delta=format_risk_level(int(round(weighted_risk))), color=risk_color), unsafe_allow_html=True)
    with col4:
        st.markdown(_metric_card("Diversification Score", f"{diversification:.1f}%"), unsafe_allow_html=True)
        
    st.markdown("<br/>", unsafe_allow_html=True)
    
    # Allocation & Risk Layout
    col_chart, col_radar = st.columns(2)
    
    with col_chart:
        st.markdown("#### 📂 Allocation by Asset Class & Sector")
        fig_pie = ChartFactory.pie_chart(
            df,
            names="category",
            values="current_value",
            title="Portfolio Category Allocation",
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_radar:
        st.markdown("#### ⚡ Portfolio Risk Radar")
        
        # Build dimensions
        vol_score = min(df["risk_score"].mean() * 0.9, 10.0)
        drawdown_score = min((net_return_pct / -10) if net_return_pct < 0 else 2.0, 10.0)
        market_sens = min(weighted_risk * 0.8, 10.0)
        concentration_score = min(hhi * 10.0, 10.0)
        expense_drag = 3.5  # standard estimate
        
        dimensions = ["Volatility", "Drawdown", "Market Sensitivity", "Concentration", "Expense Drag"]
        scores = [vol_score, drawdown_score, market_sens, concentration_score, expense_drag]
        # Close radar loop
        dimensions_c = dimensions + [dimensions[0]]
        scores_c = scores + [scores[0]]
        
        fig_radar = go.Figure(go.Scatterpolar(
            r=scores_c,
            theta=dimensions_c,
            fill="toself",
            fillcolor="rgba(139,92,246,0.15)",
            line=dict(color="#8B5CF6", width=2),
            marker=dict(color="#6366F1", size=6)
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(visible=True, range=[0, 10], gridcolor="rgba(255,255,255,0.08)"),
                angularaxis=dict(gridcolor="rgba(255,255,255,0.08)")
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=300,
            margin=dict(l=40, r=40, t=20, b=20)
        )
        st.plotly_chart(fig_radar, use_container_width=True)
        
    st.markdown("---")
    
    # Future projections
    st.markdown("### 🔮 Future Value Projections")
    
    years = [1, 3, 5, 10]
    
    # CAGR assumptions
    cagr_cons = 0.06
    cagr_mod = 0.10
    cagr_aggr = 0.14
    
    x_vals = [0] + years
    cons_vals = [total_value] + [total_value * (1 + cagr_cons) ** y for y in years]
    mod_vals = [total_value] + [total_value * (1 + cagr_mod) ** y for y in years]
    aggr_vals = [total_value] + [total_value * (1 + cagr_aggr) ** y for y in years]
    
    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(x=x_vals, y=cons_vals, name="Conservative (6% CAGR)", line=dict(color="#3B82F6", width=2, dash="dot")))
    fig_proj.add_trace(go.Scatter(x=x_vals, y=mod_vals, name="Moderate (10% CAGR)", line=dict(color="#8B5CF6", width=3)))
    fig_proj.add_trace(go.Scatter(x=x_vals, y=aggr_vals, name="Aggressive (14% CAGR)", line=dict(color="#10B981", width=2, dash="dash")))
    
    fig_proj.update_layout(
        xaxis_title="Years from Now",
        yaxis_title="Projected Value",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0"),
        height=320,
        legend=dict(orientation="h", y=1.08, x=0),
        margin=dict(l=40, r=40, t=10, b=40)
    )
    st.plotly_chart(fig_proj, use_container_width=True)
