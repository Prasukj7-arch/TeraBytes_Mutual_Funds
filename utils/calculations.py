"""Financial calculation utilities for mutual fund analytics.

Provides functions for computing returns, risk metrics, portfolio-level
aggregations, and forward-looking projections used throughout the platform.
"""

import numpy as np
import pandas as pd


def calculate_cagr(start_value: float, end_value: float, years: float) -> float:
    """Calculate Compound Annual Growth Rate.

    Args:
        start_value: Initial investment value.
        end_value: Final investment value.
        years: Number of years between start and end.

    Returns:
        CAGR as a decimal (e.g. 0.12 for 12%).
    """
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1 / years) - 1


def calculate_sharpe_ratio(
    returns_series: pd.Series, risk_free_rate: float = 0.06
) -> float:
    """Calculate annualized Sharpe Ratio.

    Args:
        returns_series: Series of periodic (daily) returns as decimals.
        risk_free_rate: Annualized risk-free rate (default 6% for India).

    Returns:
        Annualized Sharpe Ratio.
    """
    if returns_series.empty or returns_series.std() == 0:
        return 0.0
    daily_rf = risk_free_rate / 252
    excess_returns = returns_series - daily_rf
    mean_excess = excess_returns.mean()
    std_excess = excess_returns.std(ddof=1)
    if std_excess == 0:
        return 0.0
    return (mean_excess / std_excess) * np.sqrt(252)


def calculate_sortino_ratio(
    returns_series: pd.Series, risk_free_rate: float = 0.06
) -> float:
    """Calculate annualized Sortino Ratio.

    Like Sharpe but penalises only downside volatility.

    Args:
        returns_series: Series of periodic (daily) returns as decimals.
        risk_free_rate: Annualized risk-free rate.

    Returns:
        Annualized Sortino Ratio.
    """
    if returns_series.empty:
        return 0.0
    daily_rf = risk_free_rate / 252
    excess_returns = returns_series - daily_rf
    downside = excess_returns[excess_returns < 0]
    if downside.empty or downside.std(ddof=1) == 0:
        return 0.0
    downside_std = downside.std(ddof=1)
    return (excess_returns.mean() / downside_std) * np.sqrt(252)


def calculate_alpha(
    fund_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.06,
) -> float:
    """Calculate Jensen's Alpha (annualized).

    Alpha = (Rf_annual + beta * (Rm_annual - Rf_annual)) subtracted from
    the fund's annualized return.

    Args:
        fund_returns: Series of daily fund returns.
        benchmark_returns: Series of daily benchmark returns.
        risk_free_rate: Annualized risk-free rate.

    Returns:
        Annualized Jensen's Alpha as a decimal.
    """
    if fund_returns.empty or benchmark_returns.empty:
        return 0.0
    # Align the two series on their common index
    aligned_fund, aligned_bench = fund_returns.align(benchmark_returns, join="inner")
    if len(aligned_fund) < 2:
        return 0.0
    beta = calculate_beta(aligned_fund, aligned_bench)
    fund_annual = aligned_fund.mean() * 252
    bench_annual = aligned_bench.mean() * 252
    return fund_annual - (risk_free_rate + beta * (bench_annual - risk_free_rate))


def calculate_beta(
    fund_returns: pd.Series, benchmark_returns: pd.Series
) -> float:
    """Calculate Beta of fund relative to benchmark.

    Beta = Cov(fund, benchmark) / Var(benchmark).

    Args:
        fund_returns: Series of daily fund returns.
        benchmark_returns: Series of daily benchmark returns.

    Returns:
        Beta coefficient.
    """
    aligned_fund, aligned_bench = fund_returns.align(benchmark_returns, join="inner")
    if len(aligned_fund) < 2:
        return 1.0
    bench_var = aligned_bench.var(ddof=1)
    if bench_var == 0:
        return 1.0
    covariance = aligned_fund.cov(aligned_bench)
    return covariance / bench_var


def calculate_volatility(
    returns_series: pd.Series, annualize: bool = True
) -> float:
    """Calculate volatility (standard deviation of returns).

    Args:
        returns_series: Series of periodic returns.
        annualize: If True, multiply by sqrt(252) for daily data.

    Returns:
        Volatility as a decimal.
    """
    if returns_series.empty:
        return 0.0
    vol = returns_series.std(ddof=1)
    if annualize:
        vol *= np.sqrt(252)
    return vol


def calculate_max_drawdown(nav_series: pd.Series) -> float:
    """Calculate maximum peak-to-trough decline.

    Args:
        nav_series: Series of NAV values indexed by date.

    Returns:
        Maximum drawdown as a negative decimal (e.g. -0.25 for -25%).
    """
    if nav_series.empty or len(nav_series) < 2:
        return 0.0
    cumulative_max = nav_series.cummax()
    drawdowns = (nav_series - cumulative_max) / cumulative_max
    return drawdowns.min()


def calculate_risk_score(
    volatility: float, max_drawdown: float, beta: float
) -> int:
    """Compute a composite risk score on a 1-10 scale.

    Combines annualized volatility, maximum drawdown depth, and beta
    into a single integer score where 1 = lowest risk, 10 = highest.

    Args:
        volatility: Annualized volatility as a decimal.
        max_drawdown: Max drawdown as a negative decimal.
        beta: Beta coefficient.

    Returns:
        Risk score from 1 to 10.
    """
    # Normalize each component to a 0-10 range
    # Volatility: 0% → 0, ≥40% → 10
    vol_score = min(volatility / 0.04, 10.0)
    # Drawdown: 0% → 0, ≥-60% → 10  (max_drawdown is negative)
    dd_score = min(abs(max_drawdown) / 0.06, 10.0)
    # Beta: 0 → 0, ≥2 → 10
    beta_score = min(max(beta, 0.0) / 0.2, 10.0)
    # Weighted composite
    composite = 0.4 * vol_score + 0.35 * dd_score + 0.25 * beta_score
    return max(1, min(10, round(composite)))


def calculate_returns(nav_series: pd.Series, period_days: int) -> float:
    """Calculate total return over a given number of trailing days.

    Args:
        nav_series: Series of NAV values indexed by date, sorted ascending.
        period_days: Look-back period in calendar/trading days.

    Returns:
        Total return as a decimal.
    """
    if nav_series.empty or len(nav_series) < 2:
        return 0.0
    sorted_nav = nav_series.sort_index()
    end_val = sorted_nav.iloc[-1]
    # Pick the value closest to `period_days` ago
    start_idx = max(0, len(sorted_nav) - period_days - 1)
    start_val = sorted_nav.iloc[start_idx]
    if start_val == 0:
        return 0.0
    return (end_val - start_val) / start_val


def calculate_rolling_returns(
    nav_series: pd.Series, window: int = 252
) -> pd.Series:
    """Calculate rolling returns over a sliding window.

    Args:
        nav_series: Series of NAV values indexed by date.
        window: Rolling window size in trading days (default 252 ≈ 1 year).

    Returns:
        Series of rolling returns aligned to the end of each window.
    """
    if nav_series.empty or len(nav_series) <= window:
        return pd.Series(dtype=float)
    sorted_nav = nav_series.sort_index()
    rolling_ret = sorted_nav / sorted_nav.shift(window) - 1
    return rolling_ret.dropna()


def calculate_portfolio_metrics(holdings_df: pd.DataFrame) -> dict:
    """Aggregate weighted portfolio-level metrics from individual holdings.

    Expects ``holdings_df`` to contain columns:
        - weight (decimal, should sum to ~1.0)
        - returns_1y
        - cagr_3y
        - volatility
        - sharpe_ratio
        - beta
        - max_drawdown

    Missing columns are silently ignored.

    Args:
        holdings_df: DataFrame with one row per holding.

    Returns:
        Dictionary of weighted-average portfolio metrics.
    """
    if holdings_df.empty or "weight" not in holdings_df.columns:
        return {
            "weighted_return_1y": 0.0,
            "weighted_cagr_3y": 0.0,
            "weighted_volatility": 0.0,
            "weighted_sharpe": 0.0,
            "weighted_beta": 0.0,
            "weighted_max_drawdown": 0.0,
            "total_weight": 0.0,
        }
    weights = holdings_df["weight"]
    total_weight = weights.sum()

    def _weighted(col: str) -> float:
        if col in holdings_df.columns:
            return (holdings_df[col] * weights).sum() / max(total_weight, 1e-9)
        return 0.0

    return {
        "weighted_return_1y": _weighted("returns_1y"),
        "weighted_cagr_3y": _weighted("cagr_3y"),
        "weighted_volatility": _weighted("volatility"),
        "weighted_sharpe": _weighted("sharpe_ratio"),
        "weighted_beta": _weighted("beta"),
        "weighted_max_drawdown": _weighted("max_drawdown"),
        "total_weight": total_weight,
    }


def calculate_diversification_score(allocation_pcts: list[float]) -> float:
    """Calculate a diversification score from 0 to 100.

    Based on the Herfindahl-Hirschman Index (HHI).  A perfectly
    concentrated single-asset portfolio scores 0; an equally-weighted
    portfolio across many assets approaches 100.

    Args:
        allocation_pcts: List of allocation percentages (should sum to ~100).

    Returns:
        Diversification score between 0 and 100.
    """
    if not allocation_pcts or sum(allocation_pcts) == 0:
        return 0.0
    total = sum(allocation_pcts)
    shares = [p / total for p in allocation_pcts if p > 0]
    if len(shares) <= 1:
        return 0.0
    hhi = sum(s ** 2 for s in shares)
    # HHI ranges from 1/n (perfect diversification) to 1 (full concentration)
    n = len(shares)
    min_hhi = 1.0 / n
    # Normalize: 0 when hhi=1 (concentrated), 100 when hhi=min_hhi
    if hhi >= 1.0:
        return 0.0
    score = (1.0 - hhi) / (1.0 - min_hhi) * 100
    return round(max(0.0, min(100.0, score)), 2)


def calculate_expected_future_value(
    investment: float, cagr: float, years: float
) -> float:
    """Project the future value of an investment at a constant growth rate.

    Args:
        investment: Current investment amount.
        cagr: Expected annual growth rate as a decimal.
        years: Investment horizon in years.

    Returns:
        Projected future value.
    """
    if investment <= 0 or years <= 0:
        return investment
    return investment * (1 + cagr) ** years


def calculate_monthly_returns(nav_series: pd.Series) -> pd.Series:
    """Calculate month-over-month return percentages.

    Resamples NAV to month-end and computes percentage change.

    Args:
        nav_series: Series of NAV values with a DatetimeIndex.

    Returns:
        Series of monthly returns as decimals, indexed by month-end date.
    """
    if nav_series.empty or len(nav_series) < 2:
        return pd.Series(dtype=float)
    sorted_nav = nav_series.sort_index()
    # Ensure datetime index
    if not isinstance(sorted_nav.index, pd.DatetimeIndex):
        sorted_nav.index = pd.to_datetime(sorted_nav.index)
    monthly_nav = sorted_nav.resample("ME").last().dropna()
    monthly_ret = monthly_nav.pct_change().dropna()
    return monthly_ret
