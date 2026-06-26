import logging
import math
import os
import queue
import random
import threading
import time
import warnings
import pathlib
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

warnings.filterwarnings("ignore", category=FutureWarning)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("bst")

# ──────────────────────────────────────────────────────────────────────────────
# Global state via Streamlit cache (survives reruns)
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_vader():
    return SentimentIntensityAnalyzer()

@st.cache_resource
def get_queue():
    return queue.Queue(maxsize=2000)

@st.cache_resource
def get_stream_state():
    return {
        "thread": None,
        "stop_evt": None,
        "keyword": None,
        "mode": None,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

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

# Compile a flat list of all unique tickers for the dropdown lookup
POPULAR_TICKERS_SET = set()
for sector_data in SECTORS_AND_INDUSTRIES.values():
    for ind_stocks in sector_data.values():
        for s in ind_stocks:
            POPULAR_TICKERS_SET.add(s)
POPULAR_TICKERS = sorted(list(POPULAR_TICKERS_SET))

def get_ticker_sector(tk):
    for s_sec, s_inds in SECTORS_AND_INDUSTRIES.items():
        for s_ind, s_tks in s_inds.items():
            if tk in s_tks:
                return s_sec
    return "Other"

ETFS = {"Index":["SPY","QQQ","VTI","IWM"],"Sector":["XLK","XLF","XLE","XLV"],
        "Thematic":["ARKK","ARKG","ICLN","SOXX"]}

DEMO_POOL = [
    ("Apple just crushed quarterly earnings — absolutely incredible results!", 0.88),
    ("iPhone demand in Asia is surging. Very bullish on AAPL long-term.", 0.74),
    ("Apple Vision Pro disappointing. Very few units sold this quarter.", -0.61),
    ("Bought more Apple stock today. Conviction is extremely high here.", 0.79),
    ("Supply chain concerns for Apple are overblown. Market overreacted.", 0.42),
    ("Apple antitrust case in EU could seriously hurt App Store revenue.", -0.65),
    ("New MacBook Pro is a masterpiece. Apple design is unmatched.", 0.82),
    ("Apple stock is fairly valued here. Neutral, waiting for next catalyst.", 0.05),
    ("Tim Cook's AI strategy is vague and unconvincing. I'm worried.", -0.55),
    ("Apple cutting prices in China — strategic and very smart move!", 0.58),
    ("AAPL bouncing back strongly after last week's sell-off. Let's go!", 0.67),
    ("Regulatory headwinds for Apple are real. Proceed with caution.", -0.45),
    ("Apple's services revenue is a massive growth driver. Underappreciated.", 0.70),
    ("Weak iPhone upgrade cycle this year. Disappointed with demand.", -0.50),
    ("Apple Watch market share growing steadily. Solid ecosystem play.", 0.52),
    ("AAPL down 4% today on macro fears. Not company-specific. Buy the dip.", 0.35),
    ("Apple retail store traffic data suggests strong holiday season.", 0.63),
    ("Concerns about Apple's dependence on China manufacturing. High risk.", -0.48),
    ("Apple's R&D spending is huge — laying groundwork for next decade.", 0.60),
    ("Just picked up AAPL puts. This rally looks overdone to me.", -0.42),
]

DARK = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(12,12,24,0.7)",
            font=dict(family="Inter,sans-serif", color="#d0d0e0"),
            margin=dict(l=8,r=8,t=44,b=8))

# ──────────────────────────────────────────────────────────────────────────────
# Stream management
# ──────────────────────────────────────────────────────────────────────────────

def _demo_worker(keyword, stop_evt, Q):
    logger.info("Demo stream ON  keyword=%r", keyword)
    while not stop_evt.is_set():
        txt, base = random.choice(DEMO_POOL)
        # Adapt text for user selected stock keyword
        txt = txt.replace("Apple", keyword).replace("AAPL", keyword)
        noise = random.gauss(0, 0.2)
        score = float(np.clip(base + noise, -1, 1))
        try:
            Q.put_nowait({"text": txt, "score": score,
                          "ts": datetime.now(timezone.utc).isoformat()})
        except queue.Full:
            pass
        stop_evt.wait(random.uniform(1.0, 2.5))
    logger.info("Demo stream OFF")


def _live_worker(bearer, keyword, stop_evt, Q, vader):
    logger.info("Live stream ON  keyword=%r", keyword)
    try:
        import tweepy
        class _C(tweepy.StreamingClient):
            def on_tweet(self, t):
                if stop_evt.is_set(): self.disconnect()
                s = vader.polarity_scores(t.text)["compound"]
                try:
                    Q.put_nowait({"text":t.text,"score":s,
                                  "ts":datetime.now(timezone.utc).isoformat()})
                except queue.Full:
                    pass
            def on_errors(self, e): logger.error("Stream err: %s", e)
            def on_exception(self, e): logger.error("Stream exc: %s", e)
        c = _C(bearer, wait_on_rate_limit=True)
        ex = c.get_rules()
        if ex and ex.data:
            c.delete_rules([r.id for r in ex.data])
        c.add_rules(tweepy.StreamRule(f"{keyword} lang:en -is:retweet"))
        c.filter(tweet_fields=["id","text","created_at"])
    except Exception as e:
        logger.error("Live stream crashed: %s", e)


def manage_stream(stream_on, keyword, bearer=None):
    _S = get_stream_state()
    _Q = get_queue()
    vader = get_vader()
    
    mode = "live" if bearer else "demo"
    
    # Check if thread is currently running
    alive = _S["thread"] is not None and _S["thread"].is_alive()
    
    if not stream_on:
        if alive and _S["stop_evt"]:
            logger.info("Stopping stream...")
            _S["stop_evt"].set()
        return

    # If stream_on is True, ensure it's running with correct config
    if alive and _S["keyword"] == keyword and _S["mode"] == mode:
        return  # Already running perfectly

    # Stop old config if exists
    if alive and _S["stop_evt"]:
        _S["stop_evt"].set()
        _S["thread"].join(timeout=1.0)
    
    # Flush queue
    while not _Q.empty():
        try: _Q.get_nowait()
        except: break

    evt = threading.Event()
    if mode == "live":
        t = threading.Thread(target=_live_worker, args=(bearer, keyword, evt, _Q, vader), daemon=True)
    else:
        t = threading.Thread(target=_demo_worker, args=(keyword, evt, _Q), daemon=True)
    
    t.start()
    _S.update({"thread": t, "stop_evt": evt, "keyword": keyword, "mode": mode})

# ──────────────────────────────────────────────────────────────────────────────
# Data fetching (cached)
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def fetch_stock(ticker, period="1mo"):
    logger.info("yfinance: %s %s", ticker, period)
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=False)
        if df.empty:
            raise ValueError("yfinance returned empty dataframe")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index.name = "Date"
        return df.sort_index()
    except Exception as e:
        logger.error("fetch_stock error: %s. Falling back to mock data.", e)
        # Mock stock history for offline/fallback support
        days_map = {"5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 252}
        n_days = days_map.get(period, 30)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n_days, freq="B")
        prices = [150.0 * (1 + 0.005 * i + 0.015 * (i % 5 - 2)) for i in range(n_days)]
        df_mock = pd.DataFrame({
            "Open": [p*0.99 for p in prices],
            "High": [p*1.01 for p in prices],
            "Low": [p*0.98 for p in prices],
            "Close": prices,
            "Volume": [1000000 + i*50000 for i in range(n_days)]
        }, index=dates)
        df_mock.index.name = "Date"
        return df_mock


@st.cache_data(ttl=60, show_spinner=False)
def fetch_info(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.info
    except:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_multi(tickers, period="1mo"):
    out = {}
    for tk in tickers:
        df = fetch_stock(tk, "5d")
        if not df.empty and "Close" in df.columns and len(df) >= 2:
            now_pr = float(df["Close"].iloc[-1])
            prev_pr = float(df["Close"].iloc[-2])
            out[tk] = (now_pr, prev_pr)
    return out

# ──────────────────────────────────────────────────────────────────────────────
# Dynamic Backtest Engine
# ──────────────────────────────────────────────────────────────────────────────

def run_dynamic_backtest(df):
    """
    Since we don't have historical VADER sentiment for arbitrary tickers,
    we simulate the 'Brand Health Index' using price momentum (EMA crossover + RSI)
    to generate dynamic backtests for any chosen stock on the fly.
    """
    if df.empty or len(df) < 15:
        return pd.DataFrame(), pd.DataFrame()
    
    df = df.copy()
    c = df["Close"]
    
    # Simulate Brand Health Features
    fast_ma = c.ewm(span=5).mean()
    slow_ma = c.ewm(span=15).mean()
    rsi_diff = c.diff()
    gain = rsi_diff.clip(lower=0).rolling(7).mean()
    loss = (-rsi_diff.clip(upper=0)).rolling(7).mean()
    rsi = 100 - (100 / (1 + gain / loss.replace(0, 1)))
    
    # Synthetic Brand Health Index based on momentum
    bhi = ((fast_ma / slow_ma - 1) * 10) + ((rsi - 50) / 100)
    
    # Generate Signals
    signals = ["HOLD"] * len(df)
    for i in range(1, len(df)):
        # Buy if BHI crosses > 0.1, Sell if crosses < -0.1
        if bhi.iloc[i] > 0.1 and bhi.iloc[i-1] <= 0.1:
            signals[i] = "BUY"
        elif bhi.iloc[i] < -0.1 and bhi.iloc[i-1] >= -0.1:
            signals[i] = "SELL"
            
    df["signal"] = signals
    df["brand_health_index"] = bhi
    df["avg_sentiment"] = (bhi / 2).clip(-1, 1)  # Proxy
    df["tweet_count"] = np.random.randint(50, 500, size=len(df))
    df["daily_return"] = c.pct_change()
    
    # Backtest Execution
    cash = 10000.0
    shares = 0.0
    portfolio = []
    
    for i in range(len(df)):
        price = float(df["Open"].iloc[i]) if pd.notna(df["Open"].iloc[i]) else float(c.iloc[i])
        sig = df["signal"].iloc[i]
        
        if sig == "BUY" and cash > 0:
            shares = cash / price
            cash = 0
        elif sig == "SELL" and shares > 0:
            cash = shares * price
            shares = 0
            
        pv = cash + (shares * float(c.iloc[i]))
        portfolio.append(pv)
        
    df["portfolio_value"] = portfolio
    
    features_df = df[["daily_return", "brand_health_index", "avg_sentiment", "tweet_count", "Close"]].dropna()
    return df, features_df


# ──────────────────────────────────────────────────────────────────────────────
# Risk metrics
# ──────────────────────────────────────────────────────────────────────────────

def calc_risk(df):
    if df.empty or "Close" not in df.columns: return {}
    c = df["Close"].squeeze().dropna()
    if len(c) < 5: return {}
    r = c.pct_change().dropna()
    ann_r  = (1 + r.mean())**252 - 1
    ann_v  = r.std() * math.sqrt(252)
    sharpe = r.mean()/r.std()*math.sqrt(252) if r.std() > 0 else 0
    neg    = r[r < 0]
    sortino= r.mean()/neg.std()*math.sqrt(252) if len(neg)>1 and neg.std()>0 else 0
    dd     = c/c.cummax()-1
    max_dd = float(dd.min())
    var95  = float(np.percentile(r,5))
    var99  = float(np.percentile(r,1))
    cvar95 = float(r[r <= var95].mean()) if (r<=var95).any() else var95
    beta   = r.cov(r) / r.var() if r.var() > 0 else 1
    return dict(ann_r=ann_r, ann_v=ann_v, sharpe=sharpe, sortino=sortino,
                max_dd=max_dd, var95=var95, var99=var99, cvar95=cvar95,
                beta=beta, dd=dd, rets=r, close=c)

# ──────────────────────────────────────────────────────────────────────────────
# Chart helpers
# ──────────────────────────────────────────────────────────────────────────────

def dk(fig, h=380):
    fig.update_layout(**DARK, height=h)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False)
    return fig


def candle_chart(df, ticker):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.72, 0.28], vertical_spacing=0.04)
    if df.empty: return dk(fig)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=ticker,
        increasing=dict(line=dict(color="#00e676"), fillcolor="rgba(0,230,118,0.55)"),
        decreasing=dict(line=dict(color="#ff5252"), fillcolor="rgba(255,82,82,0.55)")),
        row=1, col=1)
    if len(df) >= 10:
        ma10 = df["Close"].rolling(10).mean()
        ma20 = df["Close"].rolling(20).mean()
        fig.add_trace(go.Scatter(x=df.index, y=ma10, mode="lines", name="MA10",
            line=dict(color="#64b5f6", width=1.5, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=ma20, mode="lines", name="MA20",
            line=dict(color="#ffd740", width=1.5, dash="dash")), row=1, col=1)
    colors = ["#00e676" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#ff5252"
              for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume",
        marker_color=colors, opacity=0.55), row=2, col=1)
    fig.update_layout(**DARK, height=480, xaxis_rangeslider_visible=False,
        title=f"<b>{ticker}</b> — Candlestick · MA10 · MA20 · Volume",
        legend=dict(orientation="h", y=1.06, x=0))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False)
    return fig


def sent_stream_chart(hist):
    fig = go.Figure()
    if not hist:
        fig.add_annotation(text="⏳  Live stream buffering — tweets appear here…",
            showarrow=False, font=dict(size=14, color="#666"),
            xref="paper", yref="paper", x=0.5, y=0.5)
        return dk(fig, 300)
    df = pd.DataFrame(hist).tail(60).copy()
    df["ts"] = pd.to_datetime(df["ts"])
    df["roll"] = df["score"].rolling(5, min_periods=1).mean()
    cols = ["#00e676" if s >= 0 else "#ff5252" for s in df["score"]]
    fig.add_trace(go.Bar(x=df["ts"], y=df["score"], marker_color=cols,
        name="Per-tweet score", opacity=0.65))
    fig.add_trace(go.Scatter(x=df["ts"], y=df["roll"], mode="lines",
        line=dict(color="#ffd740", width=2.5), name="Rolling avg (5)"))
    fig.add_hrect(y0=0.15, y1=1.05, fillcolor="rgba(0,230,118,0.06)",
        line_width=0, annotation_text="BUY zone",
        annotation_font_color="#00e676", annotation_position="top right")
    fig.add_hrect(y0=-1.05, y1=-0.15, fillcolor="rgba(255,82,82,0.06)",
        line_width=0, annotation_text="SELL zone",
        annotation_font_color="#ff5252", annotation_position="bottom right")
    fig.add_hline(y=0, line_color="#555", line_width=1)
    fig.update_layout(**DARK, height=300,
        title="<b>Live Tweet Sentiment Stream</b>",
        yaxis=dict(range=[-1.1, 1.1]),
        legend=dict(orientation="h", y=1.08, x=0))
    return dk(fig, 300)


def gauge_chart(value, prev):
    delta = value - prev
    color = "#00e676" if value > 0.15 else ("#ff5252" if value < -0.15 else "#ffd740")
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(value, 3),
        delta=dict(reference=round(prev, 3),
                   increasing=dict(color="#00e676"),
                   decreasing=dict(color="#ff5252"),
                   font=dict(size=16)),
        gauge=dict(
            axis=dict(range=[-8,8], tickcolor="#555",
                      tickfont=dict(size=10), nticks=9),
            bar=dict(color=color, thickness=0.28),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[
                dict(range=[-8,-0.15], color="rgba(255,82,82,0.10)"),
                dict(range=[-0.15,0.15], color="rgba(255,215,64,0.08)"),
                dict(range=[0.15,8],  color="rgba(0,230,118,0.10)"),
            ],
            threshold=dict(line=dict(color=color, width=4),
                           thickness=0.85, value=value),
        ),
        title=dict(text="Cumulative Sentiment Score",
                   font=dict(size=13, color="#aaa")),
        number=dict(font=dict(size=48, color="#fff"),
                    suffix=""),
    ))
    fig.update_layout(**DARK, height=230)
    return fig


def drawdown_chart(dd, close):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.55, 0.45], vertical_spacing=0.06)
    fig.add_trace(go.Scatter(x=close.index, y=close, mode="lines",
        line=dict(color="#64b5f6", width=2), name="Close"), row=1, col=1)
    roll_max = close.cummax()
    fig.add_trace(go.Scatter(x=close.index, y=roll_max, mode="lines",
        line=dict(color="#00e676", width=1, dash="dot"), name="Peak"), row=1, col=1)
    fig.add_trace(go.Scatter(x=dd.index, y=dd*100, mode="lines", fill="tozeroy",
        line=dict(color="#ff5252", width=1.5),
        fillcolor="rgba(255,82,82,0.18)", name="Drawdown %"), row=2, col=1)
    fig.update_layout(**DARK, height=400,
        title="<b>Price vs Drawdown</b>",
        legend=dict(orientation="h", y=1.06, x=0))
    fig.update_yaxes(row=2, ticksuffix="%", gridcolor="rgba(255,255,255,0.05)")
    return dk(fig, 400)


def return_dist_chart(rets):
    mu, sd = rets.mean()*100, rets.std()*100
    var95  = np.percentile(rets,5)*100
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=rets*100, nbinsx=35,
        marker_color="rgba(100,181,246,0.70)", name="Daily Returns"))
    fig.add_vline(x=mu, line_dash="dash", line_color="#00e676",
        annotation_text=f"Mean {mu:+.2f}%",
        annotation_font_color="#00e676", annotation_position="top right")
    fig.add_vline(x=var95, line_dash="dot", line_color="#ff5252",
        annotation_text=f"VaR95 {var95:.2f}%",
        annotation_font_color="#ff5252", annotation_position="top left")
    fig.add_vrect(x0=var95, x1=rets.min()*100,
        fillcolor="rgba(255,82,82,0.09)", line_width=0)
    return dk(fig.update_layout(title="<b>Daily Return Distribution</b>",
        xaxis_title="Return (%)", bargap=0.08,
        legend=dict(orientation="h",y=1.06,x=0)), 300)


def rolling_vol_chart(rets, windows=[10,20]):
    fig = go.Figure()
    colors = ["#ce93d8","#80cbc4"]
    for w,c in zip(windows,colors):
        rv = rets.rolling(w).std()*math.sqrt(252)*100
        fig.add_trace(go.Scatter(x=rv.index, y=rv, mode="lines",
            line=dict(color=c, width=2), name=f"Vol {w}d (ann.)"))
    return dk(fig.update_layout(title="<b>Rolling Annualised Volatility</b>",
        yaxis=dict(ticksuffix="%",gridcolor="rgba(255,255,255,0.05)"),
        legend=dict(orientation="h",y=1.06,x=0)), 280)


def bollinger_chart(close):
    ma   = close.rolling(20).mean()
    std  = close.rolling(20).std()
    ub   = ma + 2*std
    lb   = ma - 2*std
    fig  = go.Figure()
    fig.add_trace(go.Scatter(x=ub.index, y=ub, mode="lines", name="Upper",
        line=dict(color="rgba(100,181,246,0.35)", width=1)))
    fig.add_trace(go.Scatter(x=lb.index, y=lb, mode="lines", name="Lower",
        line=dict(color="rgba(100,181,246,0.35)", width=1),
        fill="tonexty", fillcolor="rgba(100,181,246,0.06)"))
    fig.add_trace(go.Scatter(x=ma.index, y=ma, mode="lines", name="MA20",
        line=dict(color="#ffd740", width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=close.index, y=close, mode="lines", name="Close",
        line=dict(color="#64b5f6", width=2.5)))
    return dk(fig.update_layout(title="<b>Bollinger Bands (20, ±2σ)</b>",
        legend=dict(orientation="h",y=1.06,x=0)), 300)


def var_bar_chart(rm):
    labels = ["VaR 95%","VaR 99%","CVaR 95%","Max DD"]
    vals   = [rm["var95"]*100, rm["var99"]*100, rm["cvar95"]*100, rm["max_dd"]*100]
    colors = ["#ff9500","#ff5252","#ff3b30","#bf2600"]
    fig    = go.Figure(go.Bar(x=labels, y=vals, marker_color=colors,
        text=[f"{v:.2f}%" for v in vals], textposition="outside",
        textfont=dict(color="#ddd", size=13)))
    fig.update_layout(**DARK, height=280,
        title="<b>Downside Risk Metrics (%)</b>",
        yaxis=dict(ticksuffix="%", gridcolor="rgba(255,255,255,0.05)"),
        showlegend=False)
    return dk(fig, 280)


def performance_bar_chart(tickers_prices):
    if not tickers_prices: return go.Figure()
    tks  = list(tickers_prices.keys())
    
    # Calculate real 1D returns using the tuple (current, previous)
    rets = [((tickers_prices[tk][0] / tickers_prices[tk][1]) - 1)*100 for tk in tks]
    cols = ["#00e676" if r>=0 else "#ff5252" for r in rets]
    
    fig  = go.Figure(go.Bar(x=tks, y=rets, marker_color=cols,
        text=[f"{r:+.2f}%" for r in rets], textposition="outside",
        textfont=dict(color="#ddd",size=11)))
    return dk(fig.update_layout(title="<b>Watchlist — True 1-Day Return</b>",
        yaxis=dict(ticksuffix="%",gridcolor="rgba(255,255,255,0.05)"),
        showlegend=False), 260)


def equity_curve_chart(sig_df):
    if sig_df.empty: return dk(go.Figure(), 300)
    pv_cols = [c for c in sig_df.columns if "portfolio" in c.lower()]
    if not pv_cols: return dk(go.Figure(), 300)
    pv  = sig_df[pv_cols[0]]
    fig = go.Figure()
    if "Close" in sig_df.columns:
        init_price = float(sig_df["Close"].iloc[0])
        bah_shares = 10000 / init_price if init_price else 0
        bah = bah_shares * sig_df["Close"]
        fig.add_trace(go.Scatter(x=sig_df.index, y=bah, mode="lines",
            name="Buy & Hold", line=dict(color="#ff9500",width=1.5,dash="dash")))
    fig.add_trace(go.Scatter(x=sig_df.index, y=pv, mode="lines",
        name="Dynamic Strategy", line=dict(color="#64b5f6",width=2.5),
        fill="tonexty", fillcolor="rgba(100,181,246,0.06)"))
    if "signal" in sig_df.columns:
        for sig, col, sym in [("BUY","#00e676","triangle-up"),
                               ("SELL","#ff5252","triangle-down")]:
            mask = sig_df["signal"]==sig
            fig.add_trace(go.Scatter(x=sig_df.index[mask], y=pv[mask],
                mode="markers", marker=dict(color=col,size=12,symbol=sym),
                name=sig, showlegend=True))
    return dk(fig.update_layout(title="<b>Dynamic Strategy vs Buy & Hold</b>",
        yaxis=dict(tickprefix="$",gridcolor="rgba(255,255,255,0.05)"),
        legend=dict(orientation="h",y=1.06,x=0)), 360)


def corr_heatmap(df):
    cols = [c for c in ["daily_return","brand_health_index","avg_sentiment",
                         "tweet_count","Close"] if c in df.columns]
    if len(cols)<2: return dk(go.Figure(),280)
    corr = df[cols].corr()
    fig  = go.Figure(go.Heatmap(z=corr.values, x=corr.columns, y=corr.index,
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        text=np.round(corr.values,2), texttemplate="%{text}",
        hovertemplate="%{x} vs %{y}: %{z:.3f}<extra></extra>"))
    return dk(fig.update_layout(title="<b>Feature Correlation Heatmap</b>"),300)

# ──────────────────────────────────────────────────────────────────────────────
# Session state init
# ──────────────────────────────────────────────────────────────────────────────

def init():
    defaults = dict(
        hist=[], cum=0.0, prev_cum=0.0, signal="HOLD",
        sig_hist=[], tweet_count=0,
        watchlist=[
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "LLY", "V",
            "JPM", "UNH", "XOM", "RTX", "PG", "COST", "NEE", "NKE", "KO", "PEP",
            "JNJ", "TCS.NS", "INFY", "MRK", "DIS", "CAT", "GE", "AMD", "NFLX", "BAC",
            "HD", "CVX", "WMT", "MA", "ADBE", "CRM", "PFE", "INTC", "UPS", "PLTR",
            "T", "VZ", "LIN", "BHP", "PLD", "O", "SO"
        ],
    )
    for k,v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ──────────────────────────────────────────────────────────────────────────────
# Signal helper
# ──────────────────────────────────────────────────────────────────────────────

def compute_signal(cum, prev):
    d = cum - prev
    if d >  0.15: return "BUY"
    if d < -0.15: return "SELL"
    return "HOLD"

SIG_COLOR = {"BUY":"#00e676","SELL":"#ff5252","HOLD":"#ffd740"}
SIG_EMOJI = {"BUY":"📈 BUY","SELL":"📉 SELL","HOLD":"⏸ HOLD"}
SIG_BG    = {"BUY":"rgba(0,230,118,0.12)","SELL":"rgba(255,82,82,0.12)",
             "HOLD":"rgba(255,215,64,0.10)"}

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def render():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * { font-family:'Inter',sans-serif !important; }

    /* Page background */
    .stApp { background: linear-gradient(160deg,#080816 0%,#0e0e28 55%,#080f20 100%) !important; }

    /* Sidebar overrides */
    [data-testid="stSidebar"] * { color: #c0c8e0 !important; }

    /* Metric overrides */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px; padding: 14px 16px;
    }
    [data-testid="stMetricLabel"] { font-size:0.72rem !important; opacity:0.6; }
    [data-testid="stMetricValue"] { font-size:1.35rem !important; font-weight:700; color:#eef !important; }

    /* Cards */
    .kcard {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px; padding: 16px 18px; margin-bottom: 12px;
    }

    /* Signal badge */
    .sig {
        border-radius: 50px; padding: 14px 0;
        font-size: 1.65rem; font-weight: 800;
        letter-spacing: 0.08em; text-align: center;
        border: 2px solid; width:100%; display:block;
    }

    /* Tweet card */
    .tc {
        border-left: 3px solid;
        border-radius: 6px 12px 12px 6px;
        padding: 9px 12px; margin-bottom: 8px;
        background: rgba(255,255,255,0.025);
        font-size: 0.8rem; line-height:1.5;
    }

    /* Live dot */
    .dot { display:inline-block; width:9px; height:9px; border-radius:50%;
           background:#00e676; box-shadow:0 0 7px #00e676;
           animation: blink 1.4s ease-in-out infinite; }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }

    /* Alert */
    .warn-card {
        background: rgba(255,149,0,0.08);
        border: 1px solid rgba(255,149,0,0.35);
        border-radius:10px; padding:10px 14px; margin-bottom:8px;
        font-size:0.82rem; color:#ffd080;
    }
    .info-card {
        background: rgba(100,181,246,0.07);
        border: 1px solid rgba(100,181,246,0.25);
        border-radius:10px; padding:10px 14px; margin-bottom:8px;
        font-size:0.82rem; color:#a0c8f0;
    }

    /* Divider */
    hr { border-color: rgba(255,255,255,0.07) !important; }

    /* Scrollbar */
    ::-webkit-scrollbar { width:5px; height:5px; }
    ::-webkit-scrollbar-track { background:transparent; }
    ::-webkit-scrollbar-thumb { background:rgba(100,181,246,0.3); border-radius:10px; }
    </style>
    """, unsafe_allow_html=True)

    init()
    _Q = get_queue()

    # ──────────────────────────────────────────────────────────────────────
    # DRAIN QUEUE  (every render, unconditionally)
    # ──────────────────────────────────────────────────────────────────────
    batch = []
    while not _Q.empty():
        try: batch.append(_Q.get_nowait())
        except: break

    if batch:
        st.session_state.hist.extend(batch)
        st.session_state.hist = st.session_state.hist[-500:]
        st.session_state.tweet_count += len(batch)
        st.session_state.prev_cum = st.session_state.cum
        avg = float(np.mean([x["score"] for x in batch]))
        st.session_state.cum += avg
        new_sig = compute_signal(st.session_state.cum, st.session_state.prev_cum)
        if new_sig != st.session_state.signal:
            st.session_state.signal = new_sig
            st.session_state.sig_hist.append({
                "Time": datetime.now().strftime("%H:%M:%S"),
                "Signal": new_sig,
                "Cum Score": round(st.session_state.cum,4),
            })
            st.session_state.sig_hist = st.session_state.sig_hist[-40:]

    # ──────────────────────────────────────────────────────────────────────
    # SIDEBAR
    # ──────────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⚙️ Brand Stock Tracker")
        st.caption("Sentiment-augmented Equity Analytics")

        # Core settings
        st.markdown("#### 🔍 Select or Search Ticker")
        search_method = st.radio("Search Mode", ["Select from List", "Enter Custom Ticker"], horizontal=True, key="bst_search_mode")

        if search_method == "Select from List":
            selected_filter_sector = st.selectbox("Filter Ticker by Sector", ["All Sectors"] + list(SECTORS_AND_INDUSTRIES.keys()), key="bst_ticker_sector_filter")
            
            if selected_filter_sector == "All Sectors":
                filtered_tickers = POPULAR_TICKERS
            else:
                filtered_tickers_set = set()
                for ind_stocks in SECTORS_AND_INDUSTRIES[selected_filter_sector].values():
                    for s in ind_stocks:
                        filtered_tickers_set.add(s)
                filtered_tickers = sorted(list(filtered_tickers_set))
                
            def format_ticker_option(tk):
                sector = get_ticker_sector(tk)
                return f"{tk} — {sector}"
                
            if "_override_ticker" in st.session_state:
                overridden = st.session_state["_override_ticker"]
                if overridden not in filtered_tickers:
                    filtered_tickers = POPULAR_TICKERS
                    st.session_state["bst_ticker_sector_filter"] = "All Sectors"
                
                idx = filtered_tickers.index(overridden) if overridden in filtered_tickers else 0
                ticker = st.selectbox("Choose Ticker", options=filtered_tickers, index=idx, format_func=format_ticker_option, key="bst_ticker_select_box")
                st.session_state.pop("_override_ticker")
            else:
                default_idx = filtered_tickers.index("AAPL") if "AAPL" in filtered_tickers else 0
                ticker = st.selectbox("Choose Ticker", options=filtered_tickers, index=default_idx, format_func=format_ticker_option, key="bst_ticker_select_box")
        else:
            ticker_input = st.text_input("Enter Ticker Symbol", value="AAPL", key="bst_ticker_text_input").strip().upper()
            ticker = ticker_input if ticker_input else "AAPL"
            
        keyword = st.text_input("🐦 Brand Keyword", value=ticker, key="bst_brand_keyword")
        period  = st.select_slider("📅 History",
            options=["5d","1mo","3mo","6mo","1y"], value="1mo", key="bst_period_slider")

        bearer = os.environ.get("TWITTER_BEARER_TOKEN","")
        stream_on = st.toggle("▶ Enable Live Stream", value=True)
        if bearer:
            st.markdown('<span class="dot"></span> &nbsp;**Twitter Live**', unsafe_allow_html=True)
        else:
            st.markdown('<span class="dot"></span> &nbsp;**Demo Mode** (simulated tweets)', unsafe_allow_html=True)

        st.markdown("---")

        # Watchlist manager
        st.markdown("#### 📌 Watchlist")
        wl_input = st.selectbox("Add to watchlist", options=[""] + POPULAR_TICKERS, key="bst_wl_select")
        c1,c2 = st.columns(2)
        if c1.button("➕ Add", key="bst_add_btn") and wl_input:
            tk_add = wl_input.strip().upper()
            if tk_add not in st.session_state.watchlist:
                st.session_state.watchlist.append(tk_add)
        if c2.button("🗑 Clear", key="bst_clear_btn"):
            st.session_state.watchlist = [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "LLY", "V",
                "JPM", "UNH", "XOM", "RTX", "PG", "COST", "NEE", "NKE", "KO", "PEP",
                "JNJ", "TCS.NS", "INFY", "MRK", "DIS", "CAT", "GE", "AMD", "NFLX", "BAC",
                "HD", "CVX", "WMT", "MA", "ADBE", "CRM", "PFE", "INTC", "UPS", "PLTR",
                "T", "VZ", "LIN", "BHP", "PLD", "O", "SO"
            ]

        wl = st.session_state.watchlist
        for tk in wl:
            st.markdown(f"`{tk}`", help=f"Monitoring {tk}")

        st.markdown("---")

        # Suggested stocks by sector
        st.markdown("#### 💡 Suggested Stocks")
        selected_sector = st.selectbox("Sector", list(SECTORS_AND_INDUSTRIES.keys()), key="bst_sector_select")
        selected_industry = st.selectbox("Industry", list(SECTORS_AND_INDUSTRIES[selected_sector].keys()), key="bst_industry_select")
        
        for s in SECTORS_AND_INDUSTRIES[selected_sector][selected_industry]:
            if st.button(s, key=f"sug_{s}", use_container_width=True):
                st.session_state["_override_ticker"] = s
                st.rerun()

        st.markdown("---")

        # ETF / Mutual funds
        st.markdown("#### 🏦 ETFs & Funds")
        etf_cat = st.selectbox("Category", list(ETFS.keys()), key="bst_etf_select")
        for e in ETFS[etf_cat]:
            st.markdown(f"`{e}`")

        st.markdown("---")

        # Reset
        if st.button("🔄 Reset Session", use_container_width=True, key="bst_reset_btn"):
            for k in ["hist","cum","prev_cum","signal","sig_hist","tweet_count"]:
                if k in st.session_state: del st.session_state[k]
            # Clear queue
            while not _Q.empty():
                try: _Q.get_nowait()
                except: break
            st.rerun()

    # ── Start / maintain stream ─────────────────────────────────────────
    manage_stream(stream_on, keyword, bearer or None)

    # ── Fetch data ──────────────────────────────────────────────────────
    df   = fetch_stock(ticker, period)
    rm   = calc_risk(df)
    info = fetch_info(ticker)
    hist = st.session_state.hist
    sig  = st.session_state.signal
    sig_c = SIG_COLOR[sig]
    sig_bg= SIG_BG[sig]

    # Quick stats
    close_now  = float(df["Close"].iloc[-1])  if not df.empty else 0
    close_prev = float(df["Close"].iloc[-2])  if len(df)>1   else close_now
    dp         = close_now - close_prev
    dp_pct     = dp/close_prev*100 if close_prev else 0

    avg_sent   = float(np.mean([x["score"] for x in hist])) if hist else 0.0
    n_tweets   = len(hist)
    bhi        = avg_sent * math.log1p(n_tweets)

    # ── Header ──────────────────────────────────────────────────────────
    h1,h2,h3,h4,h5,h6 = st.columns([2.2,1,1,1,1,1])
    with h1:
        dot = '<span class="dot"></span>' if stream_on else "🔴"
        st.markdown(f"## {dot}&nbsp; {ticker} &nbsp;<span style='font-size:1rem;color:#666;font-weight:400'>{info.get('longName','')[:38]}</span>",
            unsafe_allow_html=True)
        sector_disp = info.get("sector", "Unknown Sector")
        industry_disp = info.get("industry", "Unknown Industry")
        st.caption(f"**{sector_disp}** · **{industry_disp}** · Keyword: **{keyword}** · Period: **{period}**")
    with h2:
        st.metric("💰 Price", f"${close_now:,.2f}", f"{dp:+.2f} ({dp_pct:+.2f}%)")
    with h3:
        st.metric("😊 Sentiment", f"{avg_sent:+.3f}",
            f"{avg_sent - st.session_state.prev_cum:+.3f} vs prev")
    with h4:
        st.metric("🏷 Brand Health", f"{bhi:+.3f}")
    with h5:
        mktcap = info.get("marketCap",0)
        st.metric("📦 Mkt Cap", f"${mktcap/1e9:.1f}B" if mktcap else "—")
    with h6:
        st.markdown(
            f"<div class='sig' style='background:{sig_bg};color:{sig_c};"
            f"border-color:{sig_c}'>{SIG_EMOJI[sig]}</div>",
            unsafe_allow_html=True)

    st.markdown("---")

    # ────────────────────────────────────────────────────────────────────
    # TABS
    # ────────────────────────────────────────────────────────────────────
    tab1,tab2,tab3,tab4,tab5 = st.tabs([
        "📈  Overview",
        "💬  Live Sentiment",
        "🎯  Signals & Backtest",
        "⚠️  Risk Analysis",
        "🏦  Portfolio Explorer",
    ])

    # ════════════════════════ TAB 1  Overview ════════════════════════════
    with tab1:
        st.plotly_chart(candle_chart(df, ticker), use_container_width=True, key="c1")

        if not df.empty:
            col = df["Close"].squeeze()
            ret_1d = dp_pct
            ret_5d = (close_now/float(df["Close"].iloc[max(-5,-len(df))])-1)*100
            ret_mo = (close_now/float(df["Close"].iloc[0])-1)*100
            hi52   = float(col.max())
            lo52   = float(col.min())
            rsi_data = col.diff()
            gain   = rsi_data.clip(lower=0).rolling(14).mean()
            loss   = (-rsi_data.clip(upper=0)).rolling(14).mean()
            rsi    = 100-(100/(1+gain/loss.replace(0,1)))
            rsi_now= float(rsi.iloc[-1]) if not rsi.empty else 50

            k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
            k1.metric("1D Return",   f"{ret_1d:+.2f}%", delta_color="normal")
            k2.metric("5D Return",   f"{ret_5d:+.2f}%", delta_color="normal")
            k3.metric("Period Ret",  f"{ret_mo:+.2f}%", delta_color="normal")
            k4.metric("Period High", f"${hi52:,.2f}")
            k5.metric("Period Low",  f"${lo52:,.2f}")
            k6.metric("RSI (14)",    f"{rsi_now:.1f}",
                help="<30 oversold · >70 overbought")
            k7.metric("Volatility",  f"{rm.get('ann_v',0)*100:.1f}%" if rm else "—")

            # Alerts
            st.markdown("#### 🔔 Market Alerts")
            c_a, c_b = st.columns(2)
            with c_a:
                if rsi_now > 70:
                    st.markdown('<div class="warn-card">⚠️ <b>RSI Overbought</b> — RSI above 70 may indicate near-term correction risk.</div>', unsafe_allow_html=True)
                elif rsi_now < 30:
                    st.markdown('<div class="info-card">ℹ️ <b>RSI Oversold</b> — RSI below 30, potential mean-reversion opportunity.</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="info-card">✅ RSI in neutral zone (30–70). No extreme conditions detected.</div>', unsafe_allow_html=True)
                if rm and abs(rm.get("max_dd",0)) > 0.10:
                    st.markdown(f'<div class="warn-card">⚠️ <b>Significant Drawdown</b> — Max drawdown of {rm["max_dd"]*100:.1f}% detected in selected period.</div>', unsafe_allow_html=True)
            with c_b:
                if rm and rm.get("ann_v",0) > 0.35:
                    st.markdown(f'<div class="warn-card">⚠️ <b>High Volatility</b> — Annualised vol of {rm["ann_v"]*100:.1f}% exceeds 35%. Elevated risk.</div>', unsafe_allow_html=True)
                if avg_sent < -0.3 and n_tweets > 5:
                    st.markdown('<div class="warn-card">⚠️ <b>Negative Sentiment Spike</b> — Public sentiment is strongly negative. Monitor closely.</div>', unsafe_allow_html=True)
                elif avg_sent > 0.5 and n_tweets > 5:
                    st.markdown('<div class="info-card">💡 <b>Strong Positive Sentiment</b> — High positive sentiment, potential momentum signal.</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="info-card">✅ Sentiment within normal range. No spike detected.</div>', unsafe_allow_html=True)

            # Price + Sentiment overlay
            st.markdown("#### 📊 Price × Sentiment Overlay")
            if hist:
                df_h = pd.DataFrame(hist).tail(100)
                df_h["ts"] = pd.to_datetime(df_h["ts"])
                df_h["roll"] = df_h["score"].rolling(5,min_periods=1).mean()
                fig_ov = make_subplots(specs=[[{"secondary_y":True}]])
                fig_ov.add_trace(go.Scatter(x=df.index, y=df["Close"].squeeze(),
                    mode="lines", line=dict(color="#64b5f6",width=2.5), name="Close"),
                    secondary_y=False)
                fig_ov.add_trace(go.Scatter(x=df_h["ts"], y=df_h["roll"],
                    mode="lines", line=dict(color="#ffd740",width=2,dash="dot"),
                    name="Sentiment (rolling 5)"), secondary_y=True)
                fig_ov.update_layout(**DARK, height=280,
                    title="<b>Stock Price vs Rolling Sentiment</b>",
                    legend=dict(orientation="h",y=1.08,x=0))
                fig_ov.update_yaxes(title_text="Price (USD)", secondary_y=False,
                    gridcolor="rgba(255,255,255,0.05)")
                fig_ov.update_yaxes(title_text="Sentiment", secondary_y=True,
                    range=[-1.2,1.2], showgrid=False)
                fig_ov.update_xaxes(showgrid=False)
                st.plotly_chart(fig_ov, use_container_width=True, key="ov1")
            else:
                st.info("Sentiment overlay appears here once tweets start flowing in. (Demo stream auto-starts.)")

    # ════════════════════════ TAB 2  Live Sentiment ══════════════════════
    with tab2:
        left, right = st.columns([3,2], gap="large")

        with left:
            # Gauge — always visible
            st.plotly_chart(gauge_chart(st.session_state.cum,
                                        st.session_state.prev_cum),
                use_container_width=True, key="gauge2")

            # Sentiment stream chart
            st.plotly_chart(sent_stream_chart(hist), use_container_width=True, key="sc2")

            # Trend bar chart: hourly buckets
            if hist:
                df_h = pd.DataFrame(hist)
                df_h["ts"]  = pd.to_datetime(df_h["ts"])
                df_h["min"] = df_h["ts"].dt.floor("1min")
                grp  = df_h.groupby("min")["score"].mean().reset_index()
                grp.columns = ["Minute","Avg Score"]
                grp["Color"] = grp["Avg Score"].apply(
                    lambda s: "#00e676" if s>=0 else "#ff5252")
                fig_min = go.Figure(go.Bar(
                    x=grp["Minute"], y=grp["Avg Score"],
                    marker_color=grp["Color"], name="Avg/min"))
                fig_min.update_layout(**DARK, height=220,
                    title="<b>Per-Minute Average Sentiment</b>",
                    yaxis=dict(range=[-1.1,1.1],
                               gridcolor="rgba(255,255,255,0.05)"))
                fig_min.update_xaxes(showgrid=False)
                st.plotly_chart(fig_min, use_container_width=True, key="pm2")

        with right:
            st.markdown("#### 📊 Sentiment Stats")
            pos = sum(1 for x in hist if x["score"]>0.05)
            neg = sum(1 for x in hist if x["score"]<-0.05)
            neu = max(0, len(hist)-pos-neg)
            total = max(len(hist),1)

            s1,s2,s3 = st.columns(3)
            s1.metric("🟢 Positive", pos, f"{pos/total*100:.0f}%")
            s2.metric("🔴 Negative", neg, f"{neg/total*100:.0f}%")
            s3.metric("⚪ Neutral",  neu, f"{neu/total*100:.0f}%")

            # Pie chart
            if total > 1:
                fig_pie = go.Figure(go.Pie(
                    labels=["Positive","Negative","Neutral"],
                    values=[pos,neg,neu],
                    hole=0.55,
                    marker_colors=["#00e676","#ff5252","#555"],
                    textfont=dict(size=12)))
                fig_pie.update_layout(**DARK, height=220,
                    showlegend=True,
                    legend=dict(orientation="h",y=-0.1,x=0.1))
                st.plotly_chart(fig_pie, use_container_width=True, key="pie2")

            st.markdown("---")
            st.markdown("#### 🗞️ Live Feed")

            if not hist:
                st.info("⏳ Tweets will appear here every ~2 seconds in demo mode.")
            else:
                for item in reversed(hist[-20:]):
                    s   = item["score"]
                    cls = "pos" if s>0.05 else ("neg" if s<-0.05 else "neu")
                    bor = "#00e676" if s>0.05 else ("#ff5252" if s<-0.05 else "#555")
                    ico = "🟢" if s>0.05 else ("🔴" if s<-0.05 else "⚪")
                    ts  = str(item["ts"])[11:19]
                    st.markdown(
                        f"<div class='tc' style='border-color:{bor}'>"
                        f"<span style='opacity:0.45;font-size:0.7rem'>{ico} {ts} &nbsp;·&nbsp; <b>{s:+.3f}</b></span><br>"
                        f"{item['text'][:160]}"
                        f"</div>",
                        unsafe_allow_html=True)

    # ════════════════════════ TAB 3  Signals ════════════════════════════
    with tab3:
        # Generate DYNAMIC backtest instead of reading static CSV
        sig_df, feat_df = run_dynamic_backtest(df)

        if not sig_df.empty:
            # Equity curve
            st.plotly_chart(equity_curve_chart(sig_df), use_container_width=True, key="ec3")

            pv_cols = [c for c in sig_df.columns if "portfolio" in c.lower()]
            if pv_cols:
                pv    = sig_df[pv_cols[0]]
                init_ = float(pv.iloc[0])
                fin_  = float(pv.iloc[-1])
                ret_  = (fin_/init_-1)*100
                rets_ = pv.pct_change().dropna()
                shr_  = rets_.mean()/rets_.std()*math.sqrt(252) if rets_.std()>0 else 0

                m1,m2,m3,m4,m5 = st.columns(5)
                m1.metric("Initial",       f"${init_:,.2f}")
                m2.metric("Final",         f"${fin_:,.2f}")
                m3.metric("Total Return",  f"{ret_:+.2f}%", delta_color="normal")
                m4.metric("Sharpe",        f"{shr_:.3f}")
                m5.metric("Trades",
                    len(sig_df[sig_df.get("signal","").isin(["BUY","SELL"])]) if "signal" in sig_df.columns else "—")
        else:
            st.info("Loading backtest data...", icon="ℹ️")

        st.markdown("---")
        st.markdown("#### 📋 Live Signal Log")
        sig_hist = st.session_state.sig_hist
        if sig_hist:
            sh = pd.DataFrame(reversed(sig_hist))
            def color_row(row):
                c = {"BUY":"#00251a","SELL":"#2a0c0c","HOLD":"#1a1600"}.get(row["Signal"],"")
                fc= {"BUY":"#00e676","SELL":"#ff5252","HOLD":"#ffd740"}.get(row["Signal"],"#fff")
                return [f"background:{c};color:{fc}" for _ in row]
            st.dataframe(sh.style.apply(color_row,axis=1),
                use_container_width=True, hide_index=True)
        else:
            st.caption("Signal log updates when cumulative sentiment spikes ±0.15 from its last snapshot.")

        if not feat_df.empty:
            st.markdown("---")
            st.markdown("#### 🔗 Feature Correlation (Dynamic Proxy)")
            st.plotly_chart(corr_heatmap(feat_df), use_container_width=True, key="ch3")

    # ════════════════════════ TAB 4  Risk Analysis ═══════════════════════
    with tab4:
        if not rm:
            st.warning(f"⚠️  Not enough history for {ticker} with period '{period}'. Try selecting **3mo** or **6mo** above.", icon="⚠️")
        else:
            # Row 1: KPI cards
            st.markdown(f"#### 📊 Risk Snapshot — `{ticker}` · `{period}`")
            r1,r2,r3,r4 = st.columns(4)
            r1.metric("📈 Ann. Return",    f"{rm['ann_r']*100:+.1f}%",
                help="Compounded annual return from daily returns")
            r2.metric("📉 Ann. Volatility",f"{rm['ann_v']*100:.1f}%",
                help="Annualised standard deviation of daily returns")
            r3.metric("⚡ Sharpe Ratio",   f"{rm['sharpe']:.3f}",
                help="Risk-adjusted return (higher = better). >1 is good, >2 excellent.")
            r4.metric("🌊 Sortino Ratio",  f"{rm['sortino']:.3f}",
                help="Like Sharpe but only penalises downside volatility.")

            r5,r6,r7,r8 = st.columns(4)
            r5.metric("🕳 Max Drawdown",   f"{rm['max_dd']*100:.1f}%",
                delta_color="inverse",
                help="Largest peak-to-trough drop in the selected period.")
            r6.metric("📊 VaR 95%",        f"{rm['var95']*100:.2f}%",
                delta_color="inverse",
                help="Daily loss exceeded only 5% of trading days (historical).")
            r7.metric("📊 VaR 99%",        f"{rm['var99']*100:.2f}%",
                delta_color="inverse",
                help="Daily loss exceeded only 1% of trading days.")
            r8.metric("💀 CVaR 95%",       f"{rm['cvar95']*100:.2f}%",
                delta_color="inverse",
                help="Expected loss on the worst 5% of days (tail risk).")

            st.markdown("---")

            # Row 2: Drawdown + VaR bar
            rc1,rc2 = st.columns(2, gap="medium")
            with rc1:
                st.plotly_chart(drawdown_chart(rm["dd"],rm["close"]),
                    use_container_width=True, key="dd4")
            with rc2:
                st.plotly_chart(var_bar_chart(rm), use_container_width=True, key="vb4")

            st.markdown("---")

            # Row 3: Return dist + Rolling vol
            rc3,rc4 = st.columns(2, gap="medium")
            with rc3:
                st.plotly_chart(return_dist_chart(rm["rets"]),
                    use_container_width=True, key="rd4")
            with rc4:
                st.plotly_chart(rolling_vol_chart(rm["rets"]),
                    use_container_width=True, key="rv4")

            st.markdown("---")

            # Row 4: Bollinger full width
            st.plotly_chart(bollinger_chart(rm["close"]),
                use_container_width=True, key="bb4")

            # Risk summary box
            st.markdown("---")
            st.markdown("#### 📝 Risk Summary")
            sharpe_ = rm['sharpe']
            dd_     = rm['max_dd']
            vol_    = rm['ann_v']
            rating  = "🟢 Low" if sharpe_>1 and vol_<0.20 else \
                      ("🟡 Medium" if sharpe_>0 and vol_<0.40 else "🔴 High")
            st.markdown(f"""
            <div class="kcard">
            <b>Overall Risk Rating: {rating}</b><br><br>
            • <b>Sharpe Ratio {sharpe_:.2f}</b> — {'Above 1: solid risk-adjusted returns.' if sharpe_>1 else ('Between 0–1: modest returns relative to risk.' if sharpe_>0 else 'Negative: returns below risk-free rate.')} <br>
            • <b>Annualised Volatility {vol_*100:.1f}%</b> — {'Low volatility, relatively stable.' if vol_<0.20 else ('Moderate volatility.' if vol_<0.35 else 'High volatility — significant price swings.')} <br>
            • <b>Max Drawdown {dd_*100:.1f}%</b> — {'Shallow drawdown, good capital preservation.' if abs(dd_)<0.10 else ('Moderate drawdown.' if abs(dd_)<0.25 else 'Deep drawdown — significant loss from peak.')} <br>
            • <b>VaR 95%: {rm["var95"]*100:.2f}%</b> — On a typical bad day, expect losses no worse than this 95% of the time.
            </div>
            """, unsafe_allow_html=True)

    # ════════════════════════ TAB 5  Portfolio Explorer ══════════════════
    with tab5:
        st.markdown("#### 📌 Watchlist Performance")
        wl = st.session_state.watchlist
        if wl:
            wl_prices = fetch_multi(tuple(wl), period)
            if wl_prices:
                st.plotly_chart(performance_bar_chart(wl_prices),
                    use_container_width=True, key="wlb5")
                cols_ = st.columns(min(len(wl_prices), 5))
                for i,(tk,pr) in enumerate(wl_prices.items()):
                    cols_[i % len(cols_)].metric(tk, f"${pr[0]:,.2f}")
            else:
                st.info("Loading watchlist data…")

        st.markdown("---")
        st.markdown("#### 💡 Suggested Stocks — " + selected_sector + " (" + selected_industry + ")")
        sug_tickers = SECTORS_AND_INDUSTRIES[selected_sector][selected_industry]
        sug_prices  = fetch_multi(tuple(sug_tickers), "1mo")
        if sug_prices:
            fig_sug = go.Figure()
            for i, (tk, pr) in enumerate(sug_prices.items()):
                df_s = fetch_stock(tk,"1mo")
                if not df_s.empty:
                    norm = df_s["Close"].squeeze() / float(df_s["Close"].iloc[0]) * 100
                    fig_sug.add_trace(go.Scatter(x=df_s.index, y=norm,
                        mode="lines", name=tk, line=dict(width=2)))
            fig_sug.update_layout(**DARK, height=340,
                title=f"<b>{selected_sector} ({selected_industry}) Stocks — Normalised Performance (base=100)</b>",
                yaxis=dict(ticksuffix="",gridcolor="rgba(255,255,255,0.05)"),
                legend=dict(orientation="h",y=1.06,x=0))
            fig_sug.update_xaxes(showgrid=False)
            st.plotly_chart(fig_sug, use_container_width=True, key="sug5")

        st.markdown("---")
        st.markdown("#### 🏦 ETF Overview — " + etf_cat)
        etf_tickers = ETFS[etf_cat]
        etf_prices  = fetch_multi(tuple(etf_tickers),"1mo")
        if etf_prices:
            fig_etf = go.Figure()
            for tk,pr in etf_prices.items():
                df_e = fetch_stock(tk,"1mo")
                if not df_e.empty:
                    norm = df_e["Close"].squeeze() / float(df_e["Close"].iloc[0]) * 100
                    fig_etf.add_trace(go.Scatter(x=df_e.index, y=norm,
                        mode="lines", name=tk, line=dict(width=2)))
            fig_etf.update_layout(**DARK, height=300,
                title=f"<b>{etf_cat} ETFs — Normalised (base=100)</b>",
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                legend=dict(orientation="h",y=1.06,x=0))
            fig_etf.update_xaxes(showgrid=False)
            st.plotly_chart(fig_etf, use_container_width=True, key="etf5")

    # ── Footer ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        f"🕐 {datetime.now().strftime('%H:%M:%S')}  ·  "
        f"Tweets buffered: **{st.session_state.tweet_count}**  ·  "
        f"Stream: **{'🟢 Live' if stream_on and bearer else '🟢 Demo' if stream_on else '🔴 Off'}**  ·  "
        f"Brand Stock Tracker v3.1"
    )

    if stream_on:
        time.sleep(2)
        st.rerun()
