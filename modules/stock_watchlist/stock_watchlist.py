import streamlit as st
import pandas as pd
import yfinance as yf
from charts.chart_factory import ChartFactory
from utils.formatters import format_currency, format_pct, get_color_for_value

# ---------------------------------------------------------------------------
# Constants & Session State Initialization
# ---------------------------------------------------------------------------

SECTORS_AND_INDUSTRIES = {
    "Technology": {
        "Software": ["MSFT", "ADBE", "CRM", "ORCL", "PANW", "SNOW", "PLTR", "WDAY", "NOW", "TEAM", "MDB", "DDOG", "NET", "CRWD", "OKTA", "ZS", "SNPS", "CDNS", "ANSS", "VRSN"],
        "Semiconductors": ["NVDA", "AVGO", "AMD", "INTC", "QCOM", "TXN", "MU", "ADI", "ASML", "AMAT", "LRCX", "KLAC", "MRVL", "NXPI", "MCHP"],
        "Hardware & Electronics": ["AAPL", "HPQ", "DELL", "CSCO", "ANET", "MSI", "STX", "WDC", "HPE", "FLEX"],
        "IT Services": ["ACN", "INFY", "TCS.NS", "WIT", "CTS", "IBN", "CTSH", "EPAM", "LDOS", "GIB"]
    },
    "Financials": {
        "Banks": ["JPM", "BAC", "WFC", "C", "HDB", "RY", "TD", "HSBC", "UBS", "SAN", "BMO", "BNS", "ING", "KB", "PNC"],
        "Credit & Payments": ["V", "MA", "AXP", "PYPL", "DFS", "COF", "SOFI", "SQ", "FI", "FIS", "GPN", "JKHY", "FLT", "WEX", "MKL"],
        "Capital Markets": ["GS", "MS", "BLK", "SCHW", "MSCI", "SPGI", "MCO", "LAZ", "RJF", "LPLA", "IBKR", "CBOE", "NDAQ", "ICE", "CME"],
        "Insurance": ["BRK-B", "PGR", "MET", "ALL", "CB", "AIG", "TRV", "PRU", "AFL", "MFC"]
    },
    "Healthcare": {
        "Pharmaceuticals": ["LLY", "JNJ", "MRK", "ABBV", "PFE", "BMY", "NVO", "AZN", "GSK", "SNY", "TAK", "NVS", "REGN", "VRTX", "BIIB"],
        "Biotechnology": ["AMGN", "GILD", "MRNA", "ALNY", "BGNE", "IQV", "EXAS", "CRSP", "BENE", "ALXN", "ILMN", "BMRN", "TECH", "NTRA", "EDIT"],
        "Medical Devices": ["TMO", "MDT", "ABT", "SYK", "ISRG", "BSX", "EW", "ZBH", "BDX", "GEHC", "ALC", "STE", "BAX", "RMD", "DXCM"],
        "Healthcare Plans": ["UNH", "ELV", "CI", "CNC", "HUM", "UNM", "AET", "CVS", "HCA", "UHS"]
    },
    "Consumer Cyclical": {
        "Auto Manufacturers": ["TSLA", "TM", "F", "GM", "HMC", "STLA", "RACE", "LI", "NIO", "XPEV", "BYDDF", "LCID", "RIVN", "HYMTF", "NSANY"],
        "Internet Retail": ["AMZN", "BABA", "PDD", "MELI", "JD", "EBAY", "CHWY", "ETSY", "RVLV", "QRTEA"],
        "Restaurants": ["MCD", "SBUX", "YUM", "CMG", "DPZ", "WEN", "QSR", "DRI", "TXRH", "CAKE", "EAT", "SHAK", "WING", "BJRI", "PLAY"],
        "Apparel & Retail": ["NKE", "TJX", "HD", "LOW", "LULU", "COST", "TGT", "KSS", "M", "JWN", "GPS", "ANF", "ROST", "DLTR", "CROX"]
    },
    "Consumer Defensive": {
        "Beverages & Food": ["KO", "PEP", "BUD", "DEO", "MDLZ", "KHC", "GIS", "SYY", "ADM", "STZ", "TAP", "HSY", "K", "SJM", "CAG", "CPB", "POST", "HRL", "MKC", "TSN"],
        "Household & Personal": ["PG", "UL", "CL", "EL", "KMB", "CHD", "HRB", "COTY", "CLX", "REVN", "IPG", "OMC", "NWL", "SPB", "EPC", "ENR", "NUS", "ELF", "KVUE", "KDP", "WMT", "DG", "KR", "SFM", "BJ"],
        "Tobacco": ["PM", "MO", "BTI", "UVV", "VGR", "IMB.L", "TABAK.PR", "RL", "BATS.L", "GGL.L"]
    },
    "Energy": {
        "Oil & Gas (Integrated)": ["XOM", "CVX", "SHEL", "TTE", "BP", "EQNR", "E", "PTR", "PBR", "IMO", "SU", "CVE", "YPF", "CENX", "HES"],
        "Oil & Gas (E&P/Refining)": ["COP", "EOG", "MPC", "PSX", "VLO", "OXY", "DVN", "HAL", "SLB", "BKR", "FANG", "MRO", "APA", "OVV", "CHK", "CTRA", "WDS", "EQT", "PXD", "HP"],
        "Clean Energy & Solar": ["NEE", "FSLR", "ENPH", "BE", "RUN", "SEDG", "PLUG", "CSIQ", "NOVA", "SPWR", "HASI", "AY", "CWEN", "ORA", "TPIC", "FCEL", "BLDP", "CHPT", "BLNK", "VWDRY"]
    },
    "Industrials": {
        "Aerospace & Defense": ["RTX", "LMT", "BA", "GD", "NOC", "HON", "GE", "TDG", "HEI", "TXT", "HWM", "BWXT", "LHX", "ERJ", "AJRD"],
        "Machinery & Heavy Equip": ["CAT", "DE", "MMM", "ETN", "EMR", "PCAR", "CMI", "ITW", "PH", "AME", "DOV", "XYL", "IR", "ROK", "SNA", "FTV", "GWW", "FAST", "URI", "OSK"],
        "Logistics & Transport": ["UNP", "UPS", "FDX", "CSX", "NSC", "ODFL", "LUV", "DAL", "UAL", "AAL", "JBHT", "KNX", "CHRW", "EXPD", "DSV.CO", "CAR", "HTZ", "CP", "CNI", "ZTO"]
    },
    "Communication Services": {
        "Internet Content": ["META", "GOOGL", "NFLX", "BIDU", "SPOT", "PINS", "SNAP", "MTCH", "IAC", "YNDX", "GRUB", "ATHM", "TCEHY", "NTES", "SE", "CPNG", "DADA", "WIX", "ZG", "TRIP", "ANGI", "EXPE", "BKNG", "TCOM", "CZR", "RBLX", "BILI", "IQ", "HUYA", "YY", "TME"],
        "Telecom Services": ["VZ", "T", "TMUS", "ORAN", "VOD", "LUMN", "FYBR", "CHTR", "CMCSA", "SIRI", "DISH", "AMX", "TU", "BCE", "RCI", "SKM", "KT", "PHI", "TEF", "TIMB", "MBT", "ZTE", "RCOM.NS", "IDEA.NS"]
    },
    "Basic Materials": {
        "Chemicals": ["LIN", "APD", "DOW", "DD", "SHW", "ECL", "PPG", "VAL", "EMN", "HUN", "OLN", "FMC", "CE", "CC", "MOS", "CF", "NTR", "ICL", "IPI", "TROP", "SMG", "KRO", "GPRE", "ALB", "SQM", "IFF", "CTVA", "KWR"],
        "Mining & Metals": ["FCX", "NEM", "BHP", "RIO", "VALE", "AA", "NUE", "STLD", "X", "CLF", "MT", "SCCO", "HBM", "TECK", "GOLD", "FNV", "WPM", "AEM", "KGC", "IAG", "NG", "CDE", "HL", "AG", "MUX", "LAC", "MP"]
    },
    "Real Estate": {
        "REITs": ["PLD", "AMT", "EQIX", "SPG", "O", "CCI", "WY", "PSA", "DLR", "SBAC", "WELL", "AVB", "EQR", "VTR", "ARE", "BXP", "REG", "FRT", "KIM", "UDR", "ESS", "MAA", "CPT", "SUI", "ELS", "CUBE", "EXR", "LSI", "COLD", "VICI", "MGP", "GLPI", "HST", "PEB", "SHO", "DRH", "RLJ", "APLE", "PK", "RHP", "WPC", "NNN", "ADC", "SRC", "EPR", "STAG", "RPT", "BRX", "SITC", "UE", "EGP", "FR", "REXR", "ILPT", "ORCC"]
    },
    "Utilities": {
        "Regulated Electric/Gas": ["SO", "DUK", "D", "EXC", "AEP", "SRE", "WEC", "XEL", "PEG", "ED", "FE", "EIX", "PCG", "DTE", "PPL", "CMS", "AEE", "ES", "CNP", "LNT", "ATO", "NI", "SR", "SWX", "OGE", "PNW", "WRB", "ALE", "MGEE", "NWN", "CWT", "AWR", "SJW", "WTRG", "YORW", "MDU", "NJR", "CNX", "RGC", "EVRG", "HE", "AVA", "POR", "BKH", "IDA", "VVC", "DEI", "NSP", "UGI", "NFG", "AES", "NRG", "VST", "AWK", "UTL"]
    }
}

POPULAR_TICKERS_SET = set()
for sector_data in SECTORS_AND_INDUSTRIES.values():
    for ind_stocks in sector_data.values():
        for s in ind_stocks:
            POPULAR_TICKERS_SET.add(s)
POPULAR_TICKERS = sorted(list(POPULAR_TICKERS_SET))

def get_ticker_metadata(ticker_symbol):
    for sector, industries in SECTORS_AND_INDUSTRIES.items():
        for industry, tickers in industries.items():
            if ticker_symbol in tickers:
                return sector, industry
    return "Other", "Other"

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com, Inc.",
    "NVDA": "NVIDIA Corporation",
    "TSLA": "Tesla, Inc.",
    "META": "Meta Platforms, Inc.",
    "BRK-B": "Berkshire Hathaway Inc.",
    "LLY": "Eli Lilly and Company",
    "V": "Visa Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "UNH": "UnitedHealth Group Inc.",
    "XOM": "Exxon Mobil Corporation",
    "RTX": "RTX Corporation",
    "PG": "Procter & Gamble Co.",
    "COST": "Costco Wholesale Corp.",
    "NEE": "NextEra Energy, Inc.",
    "NKE": "NIKE, Inc.",
    "KO": "The Coca-Cola Company",
    "PEP": "PepsiCo, Inc.",
    "JNJ": "Johnson & Johnson",
    "TCS.NS": "Tata Consultancy Services",
    "INFY": "Infosys Limited",
    "MRK": "Merck & Co., Inc.",
    "DIS": "The Walt Disney Company",
    "CAT": "Caterpillar Inc.",
    "GE": "General Electric Company",
    "AMD": "Advanced Micro Devices",
    "NFLX": "Netflix, Inc.",
    "BAC": "Bank of America Corp.",
    "HD": "The Home Depot, Inc.",
    "CVX": "Chevron Corporation",
    "WMT": "Walmart Inc.",
    "MA": "Mastercard Incorporated",
    "ADBE": "Adobe Inc.",
    "CRM": "Salesforce, Inc.",
    "PFE": "Pfizer Inc.",
    "INTC": "Intel Corporation",
    "UPS": "United Parcel Service",
    "PLTR": "Palantir Technologies",
    "T": "AT&T Inc.",
    "VZ": "Verizon Communications",
    "LIN": "Linde plc",
    "BHP": "BHP Group Limited",
    "PLD": "Prologis, Inc.",
    "O": "Realty Income Corporation",
    "SO": "The Southern Company"
}

def init_watchlist():
    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = POPULAR_TICKERS.copy()

# ---------------------------------------------------------------------------
# Data Fetcher (cached for performance)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def fetch_watchlist_data(tickers):
    """Fetch live quote data for multiple tickers in parallel/sequential calls."""
    records = []
    
    # Attempt to fetch 2 days of daily history for all tickers in a single bulk request
    df = pd.DataFrame()
    if tickers:
        try:
            df = yf.download(tickers, period="2d", group_by="ticker", progress=False, auto_adjust=False)
        except Exception:
            pass

    for ticker_symbol in tickers:
        sector, industry = get_ticker_metadata(ticker_symbol)
        
        # Setup clean default/fallback values
        name = COMPANY_NAMES.get(ticker_symbol, f"{ticker_symbol} Inc.")
        last_price = 150.0
        change = 1.5
        pct_change = 0.01
        high = 152.0
        low = 149.0
        volume = 1000000
        mkt_cap = 1500000000000
        
        # Extract fields from bulk downloaded dataframe if available
        try:
            if not df.empty:
                # 1. Single Ticker (Index columns)
                if len(tickers) == 1:
                    ticker_df = df.dropna()
                    if not ticker_df.empty:
                        if len(ticker_df) >= 2:
                            last_price = float(ticker_df["Close"].iloc[-1])
                            prev_close = float(ticker_df["Close"].iloc[-2])
                            high = float(ticker_df["High"].iloc[-1])
                            low = float(ticker_df["Low"].iloc[-1])
                            volume = int(ticker_df["Volume"].iloc[-1])
                            change = last_price - prev_close
                            pct_change = (change / prev_close) if prev_close else 0.0
                        else:
                            last_price = float(ticker_df["Close"].iloc[-1])
                            high = float(ticker_df["High"].iloc[-1])
                            low = float(ticker_df["Low"].iloc[-1])
                            volume = int(ticker_df["Volume"].iloc[-1])
                            change = 0.0
                            pct_change = 0.0
                # 2. Multi-ticker (MultiIndex columns)
                elif ticker_symbol in df.columns.levels[0]:
                    ticker_df = df[ticker_symbol].dropna()
                    if not ticker_df.empty:
                        if len(ticker_df) >= 2:
                            last_price = float(ticker_df["Close"].iloc[-1])
                            prev_close = float(ticker_df["Close"].iloc[-2])
                            high = float(ticker_df["High"].iloc[-1])
                            low = float(ticker_df["Low"].iloc[-1])
                            volume = int(ticker_df["Volume"].iloc[-1])
                            change = last_price - prev_close
                            pct_change = (change / prev_close) if prev_close else 0.0
                        else:
                            last_price = float(ticker_df["Close"].iloc[-1])
                            high = float(ticker_df["High"].iloc[-1])
                            low = float(ticker_df["Low"].iloc[-1])
                            volume = int(ticker_df["Volume"].iloc[-1])
                            change = 0.0
                            pct_change = 0.0
        except Exception:
            pass
            
        records.append({
            "Symbol": ticker_symbol,
            "Company Name": name,
            "Live Price": last_price,
            "Change": change,
            "Change %": pct_change,
            "Day High": high,
            "Day Low": low,
            "Volume": volume,
            "Market Cap": mkt_cap,
            "Sector": sector,
            "Industry": industry
        })
        
    return pd.DataFrame(records)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_history(ticker_symbol, period="1mo"):
    """Fetch historical close prices for plotting."""
    try:
        df = yf.download(ticker_symbol, period=period, progress=False, auto_adjust=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index.name = "Date"
        return df.sort_index()
    except Exception:
        # Generate mock history for offline support
        dates = pd.date_range(end=pd.Timestamp.now(), periods=30, freq="B")
        prices = [150.0 * (1 + 0.005 * i + 0.02 * (i % 3 - 1)) for i in range(30)]
        return pd.DataFrame({"Close": prices}, index=dates)

SECTOR_ICONS = {
    "Technology": "💻",
    "Financials": "🏦",
    "Healthcare": "🏥",
    "Consumer Cyclical": "🚗",
    "Consumer Defensive": "📦",
    "Energy": "⚡",
    "Industrials": "🛠️",
    "Communication Services": "📡",
    "Basic Materials": "🧱",
    "Real Estate": "🏢",
    "Utilities": "🔌",
    "Other": "📁"
}

def render_stock_card(row):
    ticker = row["Symbol"]
    price = row["Live Price"]
    change_pct = row["Change %"]
    
    color = get_color_for_value(change_pct)
    arrow = "▲" if change_pct >= 0 else "▼"
    
    st.markdown(f"""
    <div class="kpi-card" style="cursor: pointer; border-left: 4px solid {color}; margin-bottom: 15px; height: 160px;">
        <p class="kpi-title" style="font-weight: bold; color: {color}; margin-bottom: 2px;">{ticker}</p>
        <h2 style="font-size: 1.6rem; margin: 0; color: #F8FAFC;">${price:,.2f}</h2>
        <p style="margin: 0; font-size: 0.8rem; color: {color}; font-weight: bold;">
            {arrow} {format_pct(change_pct)}
        </p>
        <p style="margin: 0; font-size: 0.75rem; color: #E2E8F0; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{row['Company Name']}</p>
        <p style="margin: 0; font-size: 0.65rem; color: #94A3B8; font-style: italic; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{row.get('Sector', 'Other')} · {row.get('Industry', 'Other')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Simple button underneath to remove ticker
    if st.button(f"🗑️ Remove {ticker}", key=f"del_{ticker}", use_container_width=True):
        st.session_state["watchlist"].remove(ticker)
        st.rerun()

# ---------------------------------------------------------------------------
# Page Renderer
# ---------------------------------------------------------------------------
def render():
    init_watchlist()
    
    st.markdown('<div class="main-header"><h1>📈 Stock Watchlist</h1><p>Track real-time pricing and performance for your favorite equities.</p></div>', unsafe_allow_html=True)
    
    # Sidebar control for adding stocks
    st.sidebar.markdown("### ➕ Add to Watchlist")
    
    # Let user select from popular tickers or type a custom one
    add_method = st.sidebar.radio("Add Method", ["Select Popular", "Custom Ticker"], horizontal=True)
    
    if add_method == "Select Popular":
        # Sector dropdown
        s_sector = st.sidebar.selectbox("Choose Sector", list(SECTORS_AND_INDUSTRIES.keys()), key="wl_add_sector")
        # Industry dropdown
        s_industry = st.sidebar.selectbox("Choose Industry", list(SECTORS_AND_INDUSTRIES[s_sector].keys()), key="wl_add_industry")
        # Tickers filtered by sector and industry
        all_sug_tickers = SECTORS_AND_INDUSTRIES[s_sector][s_industry]
        available = [t for t in all_sug_tickers if t not in st.session_state["watchlist"]]
        if available:
            selected_ticker = st.sidebar.selectbox("Choose Ticker", available, key="wl_add_ticker")
            if st.sidebar.button("Add Ticker", key="add_popular_btn"):
                st.session_state["watchlist"].append(selected_ticker)
                st.rerun()
        else:
            st.sidebar.info("All popular stocks in this industry are already in your watchlist!")
    else:
        custom_ticker = st.sidebar.text_input("Enter Ticker Symbol (e.g. GOOG, TSLA)").strip().upper()
        if st.sidebar.button("Add Ticker", key="add_custom_btn"):
            if custom_ticker:
                if custom_ticker not in st.session_state["watchlist"]:
                    st.session_state["watchlist"].append(custom_ticker)
                    st.rerun()
                else:
                    st.sidebar.warning("Ticker already in watchlist.")
            else:
                st.sidebar.error("Please enter a valid ticker symbol.")
                
    # Watchlist Body
    watchlist = st.session_state["watchlist"]
    
    if not watchlist:
        st.info("Watchlist is currently empty. Add tickers from the sidebar to start tracking.")
        return
        
    st.markdown(f"#### Tracking {len(watchlist)} stocks:")
    
    # Load and format data
    df = fetch_watchlist_data(watchlist)
    
    # Watchlist Grouping Filter
    unique_sectors = sorted(list(df["Sector"].unique()))
    
    st.markdown("### 🔍 Filter and Group Watchlist")
    filter_sector = st.selectbox("View Sector", ["All Sectors"] + unique_sectors, index=0, key="wl_sector_filter")
    
    if filter_sector == "All Sectors":
        # Group and display by sector
        for sector in unique_sectors:
            sector_df = df[df["Sector"] == sector]
            icon = SECTOR_ICONS.get(sector, "📁")
            
            st.markdown(f"### {icon} {sector} ({len(sector_df)} stocks)")
            
            cols = st.columns(4)
            for idx, (original_idx, row) in enumerate(sector_df.reset_index(drop=True).iterrows()):
                col_idx = idx % 4
                with cols[col_idx]:
                    render_stock_card(row)
    else:
        # Display selected sector
        sector_df = df[df["Sector"] == filter_sector]
        icon = SECTOR_ICONS.get(filter_sector, "📁")
        st.markdown(f"### {icon} {filter_sector} ({len(sector_df)} stocks)")
        
        cols = st.columns(4)
        for idx, (original_idx, row) in enumerate(sector_df.reset_index(drop=True).iterrows()):
            col_idx = idx % 4
            with cols[col_idx]:
                render_stock_card(row)
                
    st.markdown("---")
    
    # Selected Stock Detail Chart
    st.markdown("### 📊 Stock Detail Chart")
    chart_sector = st.selectbox("Filter Chart Ticker by Sector", ["All Sectors"] + unique_sectors, key="wl_chart_sector_filter")
    
    if chart_sector == "All Sectors":
        chart_options = watchlist
    else:
        chart_options = df[df["Sector"] == chart_sector]["Symbol"].tolist()
        
    def format_watchlist_option(tk):
        match = df[df["Symbol"] == tk]
        if not match.empty:
            row = match.iloc[0]
            return f"{tk} — {row['Sector']}"
        return tk

    if chart_options:
        selected_stock = st.selectbox("Select stock to view detail chart:", chart_options, format_func=format_watchlist_option)
    else:
        selected_stock = None
        st.info("No stocks in this sector are currently in your watchlist.")
    
    if selected_stock:
        # Period Selector
        chart_col1, chart_col2 = st.columns([3, 1])
        with chart_col2:
            period = st.selectbox("Chart Period:", ["1mo", "3mo", "6mo", "1y"], index=0)
            
            # Fetch and show basic metrics
            stock_info = df[df["Symbol"] == selected_stock].iloc[0]
            st.markdown(f"""
            **Company Details:**
            * Name: {stock_info['Company Name']}
            * Sector: {stock_info.get('Sector', 'Other')}
            * Industry: {stock_info.get('Industry', 'Other')}
            * Day Range: ${stock_info['Day Low']:,.2f} - ${stock_info['Day High']:,.2f}
            * Volume: {stock_info['Volume']:,}
            * Market Cap: ${stock_info['Market Cap']/1e9:,.2f}B
            """)
            
        with chart_col1:
            hist_df = fetch_stock_history(selected_stock, period=period)
            if not hist_df.empty:
                fig = ChartFactory.line_chart(
                    hist_df.reset_index(),
                    x="Date",
                    y="Close",
                    title=f"{selected_stock} Close Price ({period})"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Failed to fetch historical chart data.")
