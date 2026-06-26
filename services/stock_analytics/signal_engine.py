"""
signal_engine.py  -  Brand Stock Tracker: Signal Engine & Backtest.

Loads features.csv, generates rule-based BUY/SELL/HOLD signals from the
brand_health_index and stock price data, runs a vectorised backtest starting
with $10,000, plots an equity curve, and prints performance metrics.
"""

import logging
import pathlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("brand_stock_tracker.signal_engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TICKER          = "AAPL"
DATA_DIR        = pathlib.Path(__file__).resolve().parent.parent.parent / "data"
FEATURES_CSV    = DATA_DIR / "features.csv"
STOCK_CSV       = DATA_DIR / f"stock_{TICKER}.csv"
EQUITY_PLOT     = DATA_DIR / "equity_curve.png"

INITIAL_CASH        = 10_000.0
BHI_CHANGE_THRESH   = 0.10
PRICE_CHANGE_CAP    = 0.02
ROLLING_WINDOW      = 3
TRADING_DAYS_YEAR   = 252
RISK_FREE_RATE      = 0.0


# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------

def load_features(path: pathlib.Path) -> pd.DataFrame:
    """Load the features CSV produced by sentiment.py."""
    if not path.exists():
        logger.error("features.csv not found: %s -- run sentiment.py first.", path)
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, index_col="Date", parse_dates=True)
        df = df.sort_index()
        logger.info("Loaded features: %d rows, columns: %s", len(df), list(df.columns))
        return df
    except Exception as exc:
        logger.error("Failed to load features: %s", exc, exc_info=True)
        return pd.DataFrame()


def load_open_prices(path: pathlib.Path) -> pd.Series:
    """Load the Open column from the stock CSV for execution prices."""
    if not path.exists():
        logger.error("Stock CSV not found: %s", path)
        return pd.Series(dtype=float)
    try:
        df = pd.read_csv(path, index_col="Date", parse_dates=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.sort_index()
        logger.info("Loaded %d Open prices.", len(df))
        return df["Open"].rename("Open")
    except Exception as exc:
        logger.error("Failed to load open prices: %s", exc, exc_info=True)
        return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# 2. Signal generation (vectorised)
# ---------------------------------------------------------------------------

def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 3-day rolling percentage changes for brand_health_index and Close,
    then assign BUY / SELL / HOLD signals using vectorised operations.
    """
    required = {"brand_health_index", "Close"}
    missing  = required - set(df.columns)
    if missing:
        logger.error("Missing columns for signal generation: %s", missing)
        return df

    df = df.copy()

    bhi_pct   = df["brand_health_index"].pct_change(periods=ROLLING_WINDOW)
    price_pct = df["Close"].pct_change(periods=ROLLING_WINDOW)

    df["bhi_pct_change"]   = bhi_pct
    df["price_pct_change"] = price_pct

    buy_cond  = (bhi_pct >  BHI_CHANGE_THRESH) & (price_pct <  PRICE_CHANGE_CAP)
    sell_cond = (bhi_pct < -BHI_CHANGE_THRESH) & (price_pct > -PRICE_CHANGE_CAP)

    df["signal"] = np.select(
        [buy_cond, sell_cond],
        ["BUY",    "SELL"],
        default="HOLD",
    )

    counts = df["signal"].value_counts().to_dict()
    logger.info(
        "Signals generated -> BUY: %d  SELL: %d  HOLD: %d",
        counts.get("BUY",  0),
        counts.get("SELL", 0),
        counts.get("HOLD", 0),
    )
    return df


# ---------------------------------------------------------------------------
# 3. Vectorised backtest
# ---------------------------------------------------------------------------

def run_backtest(df: pd.DataFrame, open_prices: pd.Series) -> pd.DataFrame:
    """Simulate a long-only backtest on the signal column."""
    if df.empty or "signal" not in df.columns:
        logger.error("No signal column available; backtest skipped.")
        return df

    df = df.copy()
    df["Open"] = open_prices.reindex(df.index)
    df["exec_open"] = df["Open"].shift(-1)

    raw_pos = np.where(df["signal"] == "BUY",  1,
              np.where(df["signal"] == "SELL", 0,
                       np.nan))

    df["raw_pos"] = raw_pos
    df["position"] = (
        pd.Series(raw_pos, index=df.index)
        .ffill()
        .fillna(0)
        .astype(int)
    )

    df["pos_change"] = df["position"].diff().fillna(df["position"])

    cash       = INITIAL_CASH
    shares     = 0.0
    cash_arr   = np.empty(len(df))
    shares_arr = np.empty(len(df))

    positions = df["position"].values
    exec_open = df["exec_open"].values

    for i in range(len(df)):
        prev_pos = positions[i - 1] if i > 0 else 0
        cur_pos  = positions[i]
        price    = exec_open[i] if not np.isnan(exec_open[i]) else df["Close"].values[i]

        if cur_pos == 1 and prev_pos == 0:
            shares = cash / price
            cash   = 0.0
        elif cur_pos == 0 and prev_pos == 1:
            cash   = shares * price
            shares = 0.0

        cash_arr[i]   = cash
        shares_arr[i] = shares

    df["cash"]   = cash_arr
    df["shares"] = shares_arr
    df["portfolio_value"] = df["cash"] + df["shares"] * df["Close"]
    df["daily_pnl"] = df["portfolio_value"].diff().fillna(0.0)

    logger.info(
        "Backtest complete. Initial: $%.2f  Final: $%.2f",
        INITIAL_CASH,
        df["portfolio_value"].iloc[-1],
    )
    return df


# ---------------------------------------------------------------------------
# 4. Performance metrics
# ---------------------------------------------------------------------------

def compute_metrics(df: pd.DataFrame) -> dict:
    """Compute total return and annualised Sharpe ratio."""
    if df.empty or "portfolio_value" not in df.columns:
        return {}

    pv       = df["portfolio_value"]
    total_r  = (pv.iloc[-1] / pv.iloc[0] - 1) * 100

    daily_r  = pv.pct_change().dropna()
    excess_r = daily_r - RISK_FREE_RATE / TRADING_DAYS_YEAR
    sharpe   = (
        excess_r.mean() / excess_r.std() * np.sqrt(TRADING_DAYS_YEAR)
        if excess_r.std() > 0 else np.nan
    )

    max_dd_val = (pv / pv.cummax() - 1).min() * 100

    metrics = {
        "initial_value":    INITIAL_CASH,
        "final_value":      pv.iloc[-1],
        "total_return_pct": total_r,
        "sharpe_ratio":     sharpe,
        "max_drawdown_pct": max_dd_val,
        "num_trades":       int((df["pos_change"].abs() > 0).sum()),
    }
    return metrics


def print_metrics(metrics: dict) -> None:
    """Pretty-print the performance metrics."""
    if not metrics:
        logger.warning("No metrics to display.")
        return
    print()
    print("=" * 50)
    print("           Backtest Performance Summary")
    print("=" * 50)
    print(f"  Initial Portfolio Value : ${metrics['initial_value']:>10,.2f}")
    print(f"  Final Portfolio Value   : ${metrics['final_value']:>10,.2f}")
    print(f"  Total Return            : {metrics['total_return_pct']:>+10.2f} %")
    print(f"  Annualised Sharpe Ratio : {metrics['sharpe_ratio']:>10.4f}")
    print(f"  Max Drawdown            : {metrics['max_drawdown_pct']:>+10.2f} %")
    print(f"  Number of Trades        : {metrics['num_trades']:>10d}")
    print("=" * 50)
    print()


# ---------------------------------------------------------------------------
# 5. Plot equity curve
# ---------------------------------------------------------------------------

def plot_equity_curve(df: pd.DataFrame, metrics: dict) -> pathlib.Path | None:
    """Plot equity curve vs. buy-and-hold benchmark and mark trade signals."""
    if df.empty or "portfolio_value" not in df.columns:
        logger.warning("No portfolio data available; equity curve skipped.")
        return None

    try:
        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(13, 8),
            gridspec_kw={"height_ratios": [3, 1]},
            sharex=True,
        )

        dates = pd.to_datetime(df.index)
        pv    = df["portfolio_value"]

        bah_shares = INITIAL_CASH / df["Close"].iloc[0]
        bah_value  = bah_shares * df["Close"]

        ax1.plot(dates, pv,        color="#0071e3", linewidth=2,   label="Strategy")
        ax1.plot(dates, bah_value, color="#ff9500", linewidth=1.5, linestyle="--", label="Buy & Hold")
        ax1.fill_between(dates, pv, bah_value,
                         where=(pv >= bah_value), alpha=0.12, color="#34c759", label="Outperform")
        ax1.fill_between(dates, pv, bah_value,
                         where=(pv <  bah_value), alpha=0.12, color="#ff3b30", label="Underperform")

        buy_dates  = dates[df["signal"] == "BUY"]
        sell_dates = dates[df["signal"] == "SELL"]
        buy_vals   = pv[df["signal"] == "BUY"]
        sell_vals  = pv[df["signal"] == "SELL"]

        ax1.scatter(buy_dates,  buy_vals,  marker="^", color="#34c759", s=90, zorder=5, label="BUY signal")
        ax1.scatter(sell_dates, sell_vals, marker="v", color="#ff3b30", s=90, zorder=5, label="SELL signal")

        tr   = metrics.get("total_return_pct", float("nan"))
        shrp = metrics.get("sharpe_ratio",     float("nan"))
        ax1.set_title(
            f"{TICKER} Signal Strategy  |  Return: {tr:+.2f}%  |  Sharpe: {shrp:.4f}",
            fontsize=14, fontweight="bold", pad=12,
        )
        ax1.set_ylabel("Portfolio Value (USD)", fontsize=11)
        ax1.legend(fontsize=9, loc="upper left")
        ax1.grid(axis="y", linestyle="--", alpha=0.45)
        ax1.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
        )

        bhi = df["brand_health_index"]
        ax2.bar(dates, bhi,
                color=np.where(bhi >= 0, "#34c759", "#ff3b30"),
                alpha=0.75, width=0.8)
        ax2.axhline(0, color="white", linewidth=0.6, linestyle="--")
        ax2.set_ylabel("Brand Health Index", fontsize=9)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        fig.autofmt_xdate(rotation=30, ha="right")
        ax2.grid(axis="y", linestyle="--", alpha=0.35)

        plt.tight_layout()
        fig.savefig(EQUITY_PLOT, dpi=150)
        plt.close(fig)
        logger.info("Equity curve saved -> %s", EQUITY_PLOT)
        return EQUITY_PLOT

    except Exception as exc:
        logger.error("Failed to plot equity curve: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=== Brand Stock Tracker - Signal Engine START ===")

    df         = load_features(FEATURES_CSV)
    open_prices = load_open_prices(STOCK_CSV)

    if df.empty:
        logger.error("No features data; aborting.")
        return

    df = generate_signals(df)
    df = run_backtest(df, open_prices)
    metrics = compute_metrics(df)
    print_metrics(metrics)
    plot_equity_curve(df, metrics)

    out = DATA_DIR / "signal_results.csv"
    df.to_csv(out)
    logger.info("Signal results saved -> %s", out)
    logger.info("=== Signal Engine COMPLETE ===")


if __name__ == "__main__":
    main()
