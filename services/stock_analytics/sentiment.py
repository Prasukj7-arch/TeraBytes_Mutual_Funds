"""
sentiment.py  -  Brand Stock Tracker: Sentiment Analysis & Brand Health Metric.

Loads tweets CSV, applies VADER sentiment, aggregates by date, merges with
stock price data, computes the brand_health_index, and prints the correlation
between daily stock return and brand_health_index.
"""

import logging
import math
import pathlib

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("brand_stock_tracker.sentiment")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TICKER = "AAPL"
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"
TWEETS_CSV = DATA_DIR / f"tweets_{TICKER}.csv"
STOCK_CSV  = DATA_DIR / f"stock_{TICKER}.csv"
FEATURES_CSV = DATA_DIR / "features.csv"

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------

def load_tweets(path: pathlib.Path) -> pd.DataFrame:
    """Load the tweets CSV produced by ingest.py.

    Returns an empty DataFrame (with expected columns) on failure.
    """
    if not path.exists():
        logger.error("Tweets CSV not found: %s  -- run ingest.py first.", path)
        return pd.DataFrame(columns=["id", "text", "created_at", "author_id"])
    try:
        df = pd.read_csv(path, parse_dates=["created_at"])
        logger.info("Loaded %d tweets from %s.", len(df), path)
        return df
    except Exception as exc:
        logger.error("Failed to load tweets: %s", exc, exc_info=True)
        return pd.DataFrame(columns=["id", "text", "created_at", "author_id"])


def load_stock(path: pathlib.Path) -> pd.DataFrame:
    """Load the stock CSV produced by ingest.py.

    Returns an empty DataFrame on failure.
    """
    if not path.exists():
        logger.error("Stock CSV not found: %s  -- run ingest.py first.", path)
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, index_col="Date", parse_dates=True)
        df.columns = [
            c[0] if isinstance(c, tuple) else c for c in df.columns
        ]
        logger.info("Loaded %d rows of stock data from %s.", len(df), path)
        return df
    except Exception as exc:
        logger.error("Failed to load stock data: %s", exc, exc_info=True)
        return pd.DataFrame()

# ---------------------------------------------------------------------------
# 2. VADER sentiment scoring
# ---------------------------------------------------------------------------

def score_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'compound' VADER score column to the tweets DataFrame.

    Rows with missing or non-string text receive a score of 0.0.
    """
    if df.empty:
        logger.warning("Tweet DataFrame is empty; skipping sentiment scoring.")
        return df

    analyzer = SentimentIntensityAnalyzer()
    logger.info("Scoring sentiment for %d tweets...", len(df))

    def safe_score(text) -> float:
        try:
            if not isinstance(text, str) or not text.strip():
                return 0.0
            return analyzer.polarity_scores(text)["compound"]
        except Exception:
            return 0.0

    df = df.copy()
    df["compound"] = df["text"].apply(safe_score)
    logger.info(
        "Sentiment scoring complete. Mean compound: %.4f  (min=%.4f, max=%.4f)",
        df["compound"].mean(),
        df["compound"].min(),
        df["compound"].max(),
    )
    return df

# ---------------------------------------------------------------------------
# 3. Aggregate by date
# ---------------------------------------------------------------------------

def aggregate_by_date(df: pd.DataFrame) -> pd.DataFrame:
    """Group tweets by UTC date and compute avg_sentiment and tweet_count.

    Returns a DataFrame indexed by date.
    """
    if df.empty or "compound" not in df.columns:
        logger.warning("Cannot aggregate; DataFrame is empty or missing 'compound'.")
        return pd.DataFrame(columns=["avg_sentiment", "tweet_count"])

    df = df.copy()

    if pd.api.types.is_datetime64_any_dtype(df["created_at"]):
        df["date"] = df["created_at"].dt.tz_convert("UTC").dt.normalize() if df["created_at"].dt.tz is not None else df["created_at"].dt.normalize()
    else:
        df["date"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce").dt.normalize()

    agg = (
        df.groupby("date")
        .agg(
            avg_sentiment=("compound", "mean"),
            tweet_count=("compound", "count"),
        )
        .reset_index()
        .rename(columns={"date": "Date"})
        .set_index("Date")
    )
    agg.index = pd.DatetimeIndex(agg.index).normalize()
    logger.info("Aggregated tweet sentiment into %d date buckets.", len(agg))
    return agg

# ---------------------------------------------------------------------------
# 4. Compute brand_health_index
# ---------------------------------------------------------------------------

def compute_brand_health(agg: pd.DataFrame) -> pd.DataFrame:
    """Add brand_health_index = avg_sentiment * log(1 + tweet_count).

    A positive / high-volume day yields a high positive index.
    A negative / high-volume day yields a strongly negative index.
    """
    if agg.empty:
        return agg
    agg = agg.copy()
    agg["brand_health_index"] = agg["avg_sentiment"] * np.log1p(agg["tweet_count"])
    logger.info(
        "Brand health index computed. Mean=%.4f  Std=%.4f",
        agg["brand_health_index"].mean(),
        agg["brand_health_index"].std(),
    )
    return agg

# ---------------------------------------------------------------------------
# 5. Merge with stock data & compute daily return
# ---------------------------------------------------------------------------

def merge_with_stock(sentiment_agg: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    """Join sentiment aggregation with stock price data on date.

    Adds a 'daily_return' column = percentage change of Close price.
    """
    if stock.empty:
        logger.warning("Stock DataFrame is empty; returning sentiment-only data.")
        return sentiment_agg

    stock = stock.copy()
    stock.index = pd.DatetimeIndex(stock.index).normalize()

    if "Close" not in stock.columns:
        logger.error("Stock data has no 'Close' column.")
        return sentiment_agg

    stock["daily_return"] = stock["Close"].pct_change() * 100

    merged = sentiment_agg.join(
        stock[["Close", "Volume", "daily_return"]],
        how="outer",
    ).sort_index()

    before = len(merged)
    merged = merged.dropna(subset=["brand_health_index", "daily_return"])
    logger.info(
        "Merged dataset: %d rows (dropped %d rows with NaN in key columns).",
        len(merged),
        before - len(merged),
    )
    return merged

# ---------------------------------------------------------------------------
# 6. Correlation analysis
# ---------------------------------------------------------------------------

def print_correlation(df: pd.DataFrame) -> None:
    """Print the Pearson correlation between daily_return and brand_health_index."""
    if df.empty or not {"daily_return", "brand_health_index"}.issubset(df.columns):
        logger.warning("Not enough data to compute correlation.")
        return

    if len(df) < 2:
        logger.warning(
            "Only %d overlapping data point(s); correlation requires >= 2.",
            len(df),
        )
        return

    corr = df["daily_return"].corr(df["brand_health_index"])
    n    = len(df)
    print()
    print("=" * 55)
    print("  Brand Health vs. Daily Stock Return Correlation")
    print("=" * 55)
    print(f"  Observations (overlapping dates) : {n}")
    print(f"  Pearson r (return ~ brand_health): {corr:+.4f}")
    if abs(corr) >= 0.7:
        strength = "strong"
    elif abs(corr) >= 0.4:
        strength = "moderate"
    else:
        strength = "weak"
    direction = "positive" if corr > 0 else "negative"
    print(f"  Interpretation                   : {strength} {direction} correlation")
    print("=" * 55)
    print()
    logger.info("Correlation (daily_return ~ brand_health_index) = %.4f  (n=%d)", corr, n)

    corr_matrix = df[["daily_return", "brand_health_index", "avg_sentiment", "tweet_count"]].corr()
    print("Full correlation matrix:")
    print(corr_matrix.round(4).to_string())
    print()

# ---------------------------------------------------------------------------
# 7. Save features
# ---------------------------------------------------------------------------

def save_features(df: pd.DataFrame, path: pathlib.Path) -> None:
    """Persist the merged features DataFrame to CSV."""
    df.to_csv(path)
    logger.info("Features saved -> %s  (%d rows, %d columns)", path, len(df), len(df.columns))

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=== Brand Stock Tracker - Sentiment Pipeline START ===")

    tweets_df = load_tweets(TWEETS_CSV)
    stock_df  = load_stock(STOCK_CSV)

    tweets_df = score_sentiment(tweets_df)
    sentiment_agg = aggregate_by_date(tweets_df)
    sentiment_agg = compute_brand_health(sentiment_agg)
    features = merge_with_stock(sentiment_agg, stock_df)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_features(features, FEATURES_CSV)
    print_correlation(features)

    logger.info("=== Sentiment Pipeline COMPLETE ===")
    logger.info("Features CSV -> %s", FEATURES_CSV)


if __name__ == "__main__":
    main()
