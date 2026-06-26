"""
ingest.py  -  Brand Stock Tracker data ingestion pipeline.

Downloads 30 days of AAPL stock data (yfinance), fetches up to 100
recent tweets mentioning Apple (Tweepy v2), saves both as CSVs, and
generates a closing-price line chart PNG.
"""

import os
import logging
import pathlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
import tweepy
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
logger = logging.getLogger("brand_stock_tracker.ingest")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TICKER = "AAPL"
TWEET_QUERY = "Apple lang:en -is:retweet"
MAX_TWEETS = 100
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ensure_data_dir() -> None:
    """Create the data/ output directory if it does not already exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory ready: %s", DATA_DIR.resolve())


# ---------------------------------------------------------------------------
# 1. Stock data
# ---------------------------------------------------------------------------
def fetch_stock_data(ticker: str, days: int = 30) -> pd.DataFrame:
    """Download the last *days* calendar days of OHLCV data for *ticker*.

    Returns an empty DataFrame on failure.
    """
    end_date = datetime.now(tz=timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    logger.info(
        "Fetching %d days of stock data for %s  (%s to %s)...",
        days, ticker, start_date, end_date,
    )
    try:
        df = yf.download(
            ticker,
            start=str(start_date),
            end=str(end_date),
            progress=False,
            auto_adjust=False,
        )
        if df.empty:
            logger.warning("yfinance returned an empty DataFrame for %s.", ticker)
            return df

        # Flatten multi-level columns produced by newer yfinance versions.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index.name = "Date"
        logger.info("Downloaded %d rows of stock data.", len(df))
        return df

    except Exception as exc:
        logger.error("Failed to fetch stock data: %s", exc, exc_info=True)
        return pd.DataFrame()


def save_stock_data(df: pd.DataFrame, ticker: str) -> pathlib.Path:
    """Persist the stock DataFrame as CSV. Returns the output path."""
    path = DATA_DIR / f"stock_{ticker}.csv"
    df.to_csv(path)
    logger.info("Stock data saved -> %s", path)
    return path


# ---------------------------------------------------------------------------
# 2. Tweet ingestion
# ---------------------------------------------------------------------------
def fetch_tweets(query: str, max_results: int = 100) -> pd.DataFrame:
    """Search recent tweets via the Twitter v2 API.

    Reads the bearer token from the TWITTER_BEARER_TOKEN environment variable.
    Returns an empty DataFrame on failure or missing credentials.
    """
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        logger.error(
            "TWITTER_BEARER_TOKEN environment variable is not set. "
            "Tweet fetching skipped."
        )
        return pd.DataFrame(columns=["id", "text", "created_at", "author_id"])

    logger.info("Connecting to Twitter API v2 (max_results=%d)...", max_results)
    try:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

        # Recent-search endpoint accepts 10-100 results per page.
        clamped = max(10, min(max_results, 100))

        response = client.search_recent_tweets(
            query=query,
            max_results=clamped,
            tweet_fields=["id", "text", "created_at", "author_id"],
        )

        if not response.data:
            logger.warning("Twitter API returned no tweets for the given query.")
            return pd.DataFrame(columns=["id", "text", "created_at", "author_id"])

        records = [
            {
                "id":         tweet.id,
                "text":       tweet.text,
                "created_at": tweet.created_at,
                "author_id":  tweet.author_id,
            }
            for tweet in response.data
        ]

        df = pd.DataFrame(records)
        logger.info("Fetched %d tweets.", len(df))
        return df

    except tweepy.TweepyException as exc:
        logger.error("Tweepy error: %s", exc, exc_info=True)
        return pd.DataFrame(columns=["id", "text", "created_at", "author_id"])
    except Exception as exc:
        logger.error("Unexpected error during tweet fetch: %s", exc, exc_info=True)
        return pd.DataFrame(columns=["id", "text", "created_at", "author_id"])


def save_tweets(df: pd.DataFrame, ticker: str) -> pathlib.Path:
    """Persist the tweets DataFrame as CSV. Returns the output path."""
    path = DATA_DIR / f"tweets_{ticker}.csv"
    df.to_csv(path, index=False)
    logger.info("Tweet data saved -> %s", path)
    return path


# ---------------------------------------------------------------------------
# 3. Closing-price chart
# ---------------------------------------------------------------------------
def plot_closing_price(df: pd.DataFrame, ticker: str):
    """Plot a closing-price line chart and save it as data/price_plot.png.

    Returns the output path, or None if the chart could not be generated.
    """
    if df.empty or "Close" not in df.columns:
        logger.warning("No closing price data; chart not generated.")
        return None

    logger.info("Generating closing price chart for %s...", ticker)
    try:
        fig, ax = plt.subplots(figsize=(12, 5))

        dates  = pd.to_datetime(df.index)
        closes = df["Close"].squeeze()

        ax.plot(dates, closes, linewidth=2, color="#0071e3", label="Close Price")
        ax.fill_between(dates, closes, closes.min(), alpha=0.08, color="#0071e3")

        ax.set_title(
            f"{ticker} - Closing Price (Last 30 Days)",
            fontsize=15, fontweight="bold", pad=14,
        )
        ax.set_xlabel("Date", fontsize=11)
        ax.set_ylabel("Price (USD)", fontsize=11)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        fig.autofmt_xdate(rotation=30, ha="right")
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.legend(fontsize=10)
        plt.tight_layout()

        path = DATA_DIR / "price_plot.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        logger.info("Chart saved -> %s", path)
        return path

    except Exception as exc:
        logger.error("Failed to generate chart: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("=== Brand Stock Tracker - Ingestion Pipeline START ===")

    ensure_data_dir()

    # Stock ---
    stock_df = fetch_stock_data(TICKER, days=30)
    if not stock_df.empty:
        save_stock_data(stock_df, TICKER)
        plot_closing_price(stock_df, TICKER)
    else:
        logger.warning("Stock data unavailable; skipping save and chart.")

    # Tweets ---
    tweets_df = fetch_tweets(TWEET_QUERY, max_results=MAX_TWEETS)
    save_tweets(tweets_df, TICKER)

    logger.info("=== Ingestion Pipeline COMPLETE ===")
    logger.info(
        "Outputs:\n  Stock CSV : %s\n  Tweets CSV: %s\n  Chart PNG : %s",
        DATA_DIR / f"stock_{TICKER}.csv",
        DATA_DIR / f"tweets_{TICKER}.csv",
        DATA_DIR / "price_plot.png",
    )


if __name__ == "__main__":
    main()
