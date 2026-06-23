"""
Synthetic mutual fund data generator for demo mode.

Generates realistic data for ~150 Indian mutual funds spanning 9 categories,
including daily NAV history (3 years) and 3 client portfolios with varying
risk profiles.  All randomness is seeded with ``numpy.random.seed(42)`` so
results are fully reproducible across runs.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEED: int = 42

_FUND_HOUSES: list[str] = [
    "HDFC",
    "SBI",
    "ICICI Prudential",
    "Axis",
    "Kotak",
    "Nippon India",
    "Tata",
    "DSP",
    "Aditya Birla",
    "UTI",
    "Mirae Asset",
    "Canara Robeco",
    "PGIM",
    "Edelweiss",
    "Motilal Oswal",
]

# Category-specific naming fragments used to build realistic scheme names.
_CATEGORY_NAME_PARTS: dict[str, list[str]] = {
    "Large Cap": [
        "Large Cap Fund",
        "Blue Chip Fund",
        "Bluechip Fund",
        "Top 100 Fund",
        "Large Cap Equity Fund",
        "Frontline Equity Fund",
        "Large & Midcap Fund",
    ],
    "Mid Cap": [
        "Midcap Fund",
        "Mid Cap Fund",
        "Midcap Opportunities Fund",
        "Emerging Equities Fund",
        "Mid Cap Equity Fund",
        "Midcap Select Fund",
    ],
    "Small Cap": [
        "Small Cap Fund",
        "Smallcap Fund",
        "Small Cap Equity Fund",
        "Emerging Fund",
        "Small Cap Opportunities Fund",
        "Micro Cap Fund",
    ],
    "Flexi Cap": [
        "Flexi Cap Fund",
        "Flexicap Fund",
        "Focused Equity Fund",
        "Capital Builder Fund",
        "Flexi Cap Equity Fund",
    ],
    "Multi Cap": [
        "Multi Cap Fund",
        "Multicap Fund",
        "Diversified Equity Fund",
        "Equity Advantage Fund",
        "Multi Cap Growth Fund",
    ],
    "ELSS": [
        "ELSS Tax Saver Fund",
        "Tax Advantage Fund",
        "Long Term Equity Fund",
        "Tax Saver Fund",
        "ELSS Fund",
    ],
    "Hybrid": [
        "Aggressive Hybrid Fund",
        "Balanced Advantage Fund",
        "Equity Savings Fund",
        "Hybrid Equity Fund",
        "Dynamic Asset Allocation Fund",
    ],
    "Debt": [
        "Short Duration Fund",
        "Corporate Bond Fund",
        "Banking & PSU Debt Fund",
        "Liquid Fund",
        "Money Market Fund",
        "Dynamic Bond Fund",
    ],
    "Index": [
        "Nifty 50 Index Fund",
        "Sensex Index Fund",
        "Nifty Next 50 Index Fund",
        "Nifty Midcap 150 Index Fund",
        "S&P BSE Sensex Index Fund",
        "Nifty 500 Index Fund",
    ],
}

_PLAN_SUFFIXES: list[str] = ["Direct Growth", "Regular Growth"]

# Per-category statistical profiles.
# Keys: count, return_1y_lo, return_1y_hi, vol_lo, vol_hi, beta_lo, beta_hi,
#        expense_lo, expense_hi, risk_lo, risk_hi, nav_lo, nav_hi, aum_lo, aum_hi
_CATEGORY_PROFILES: dict[str, dict[str, Any]] = {
    "Large Cap": dict(
        count=20, ret1y_lo=8, ret1y_hi=20,
        vol_lo=10, vol_hi=18, beta_lo=0.85, beta_hi=1.15,
        expense_lo=0.25, expense_hi=1.60, risk_lo=4, risk_hi=7,
        nav_lo=30, nav_hi=450, aum_lo=1500, aum_hi=45000,
    ),
    "Mid Cap": dict(
        count=18, ret1y_lo=10, ret1y_hi=30,
        vol_lo=14, vol_hi=24, beta_lo=0.90, beta_hi=1.25,
        expense_lo=0.30, expense_hi=1.80, risk_lo=5, risk_hi=8,
        nav_lo=20, nav_hi=400, aum_lo=800, aum_hi=30000,
    ),
    "Small Cap": dict(
        count=18, ret1y_lo=12, ret1y_hi=40,
        vol_lo=18, vol_hi=30, beta_lo=0.95, beta_hi=1.45,
        expense_lo=0.35, expense_hi=2.00, risk_lo=7, risk_hi=10,
        nav_lo=15, nav_hi=350, aum_lo=500, aum_hi=25000,
    ),
    "Flexi Cap": dict(
        count=15, ret1y_lo=8, ret1y_hi=25,
        vol_lo=11, vol_hi=20, beta_lo=0.85, beta_hi=1.20,
        expense_lo=0.25, expense_hi=1.70, risk_lo=4, risk_hi=7,
        nav_lo=25, nav_hi=500, aum_lo=1000, aum_hi=40000,
    ),
    "Multi Cap": dict(
        count=15, ret1y_lo=10, ret1y_hi=28,
        vol_lo=12, vol_hi=22, beta_lo=0.90, beta_hi=1.25,
        expense_lo=0.30, expense_hi=1.80, risk_lo=5, risk_hi=8,
        nav_lo=20, nav_hi=400, aum_lo=800, aum_hi=28000,
    ),
    "ELSS": dict(
        count=15, ret1y_lo=8, ret1y_hi=22,
        vol_lo=12, vol_hi=22, beta_lo=0.85, beta_hi=1.20,
        expense_lo=0.30, expense_hi=1.80, risk_lo=5, risk_hi=8,
        nav_lo=20, nav_hi=400, aum_lo=1000, aum_hi=20000,
    ),
    "Hybrid": dict(
        count=15, ret1y_lo=6, ret1y_hi=15,
        vol_lo=6, vol_hi=14, beta_lo=0.50, beta_hi=0.90,
        expense_lo=0.30, expense_hi=1.80, risk_lo=3, risk_hi=6,
        nav_lo=20, nav_hi=350, aum_lo=800, aum_hi=35000,
    ),
    "Debt": dict(
        count=17, ret1y_lo=4, ret1y_hi=9,
        vol_lo=2, vol_hi=6, beta_lo=0.10, beta_hi=0.45,
        expense_lo=0.10, expense_hi=1.00, risk_lo=1, risk_hi=4,
        nav_lo=10, nav_hi=100, aum_lo=500, aum_hi=50000,
    ),
    "Index": dict(
        count=17, ret1y_lo=8, ret1y_hi=18,
        vol_lo=10, vol_hi=18, beta_lo=0.95, beta_hi=1.05,
        expense_lo=0.10, expense_hi=0.50, risk_lo=4, risk_hi=7,
        nav_lo=15, nav_hi=350, aum_lo=500, aum_hi=30000,
    ),
}

# Number of trading days for the NAV history (≈ 3 calendar years).
_NAV_TRADING_DAYS: int = 756


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_fund_name(fund_house: str, name_part: str, suffix: str) -> str:
    """Compose a realistic scheme name.

    Example output:
        ``'HDFC Large Cap Fund - Direct Growth'``
    """
    return f"{fund_house} {name_part} - {suffix}"


def _generate_fund_names(rng: np.random.RandomState) -> list[dict[str, str]]:
    """Build the full list of ``(fund_name, fund_house, category)`` tuples.

    Each category is assigned its target number of funds.  Fund-house
    assignments cycle through ``_FUND_HOUSES`` and are shuffled per
    category so that every AMC appears across multiple categories.
    """
    records: list[dict[str, str]] = []

    for category, profile in _CATEGORY_PROFILES.items():
        count: int = profile["count"]
        name_parts = _CATEGORY_NAME_PARTS[category]

        # Shuffle houses per category for variety.
        houses = list(_FUND_HOUSES)
        rng.shuffle(houses)

        for i in range(count):
            house = houses[i % len(houses)]
            name_part = name_parts[i % len(name_parts)]
            suffix = _PLAN_SUFFIXES[i % len(_PLAN_SUFFIXES)]
            fund_name = _build_fund_name(house, name_part, suffix)

            # Avoid exact duplicate names by appending a serial for later
            # cycles through the same name-part list.
            cycle = i // len(name_parts)
            if cycle > 0:
                fund_name = _build_fund_name(
                    house,
                    name_part.replace(" Fund", f" Fund - Series {cycle}"),
                    suffix,
                )

            records.append(
                {"fund_name": fund_name, "fund_house": house, "category": category}
            )

    return records


def _correlated_returns(
    rng: np.random.RandomState,
    ret_1y: float,
    volatility: float,
) -> dict[str, float]:
    """Derive shorter-horizon returns from the 1-year figure.

    Uses a simple random perturbation around annualised scaling so that
    return columns are broadly consistent.
    """
    noise = lambda scale: rng.normal(0, scale)  # noqa: E731

    # Monthly return ≈ 1y / 12 with noise
    ret_1m = round(ret_1y / 12 + noise(volatility / 30), 2)
    ret_3m = round(ret_1y / 4 + noise(volatility / 15), 2)
    ret_6m = round(ret_1y / 2 + noise(volatility / 10), 2)

    # 3-year and 5-year CAGRs dampen toward the mean
    ret_3y = round(ret_1y * rng.uniform(0.75, 1.10), 2)
    ret_5y = round(ret_1y * rng.uniform(0.65, 1.05), 2)

    cagr = round(ret_5y + noise(0.5), 2)

    return {
        "returns_1m": ret_1m,
        "returns_3m": ret_3m,
        "returns_6m": ret_6m,
        "returns_1y": round(ret_1y, 2),
        "returns_3y": ret_3y,
        "returns_5y": ret_5y,
        "cagr": cagr,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_fund_data() -> pd.DataFrame:
    """Generate a DataFrame of ~150 mutual fund records with realistic metrics.

    Returns:
        DataFrame with columns matching the canonical schema defined in
        ``config.column_mappings``.
    """
    rng = np.random.RandomState(_SEED)
    fund_names = _generate_fund_names(rng)
    rows: list[dict[str, Any]] = []

    for entry in fund_names:
        category = entry["category"]
        p = _CATEGORY_PROFILES[category]

        # --- Core metrics ---
        nav = round(rng.uniform(p["nav_lo"], p["nav_hi"]), 2)
        aum = round(rng.uniform(p["aum_lo"], p["aum_hi"]), 2)
        expense_ratio = round(rng.uniform(p["expense_lo"], p["expense_hi"]), 2)
        volatility = round(rng.uniform(p["vol_lo"], p["vol_hi"]), 2)
        beta = round(rng.uniform(p["beta_lo"], p["beta_hi"]), 2)
        risk_score = int(rng.randint(p["risk_lo"], p["risk_hi"] + 1))
        ret_1y = round(rng.uniform(p["ret1y_lo"], p["ret1y_hi"]), 2)

        # --- Derived returns ---
        returns = _correlated_returns(rng, ret_1y, volatility)

        # --- Risk-adjusted metrics ---
        risk_free_rate = 6.5  # India 10-year benchmark
        sharpe_ratio = round(
            (returns["returns_1y"] - risk_free_rate) / max(volatility, 1.0), 2
        )
        sharpe_ratio = round(max(0.10, min(sharpe_ratio, 3.00)), 2)

        # Alpha relative to a rough benchmark
        benchmark_return = 12.0 if category not in ("Debt", "Hybrid") else 7.0
        alpha = round(returns["returns_1y"] - beta * benchmark_return, 2)
        alpha = round(max(-5.0, min(alpha, 10.0)), 2)

        # Sortino ≈ Sharpe * [1.1 … 1.4] (down-capture is a subset of vol)
        sortino_ratio = round(sharpe_ratio * rng.uniform(1.05, 1.45), 2)
        sortino_ratio = round(max(0.20, min(sortino_ratio, 3.50)), 2)

        # Max drawdown scales with volatility
        max_drawdown = round(-volatility * rng.uniform(1.0, 2.2), 2)
        max_drawdown = round(max(-50.0, min(max_drawdown, -5.0)), 2)

        row: dict[str, Any] = {
            "fund_name": entry["fund_name"],
            "fund_house": entry["fund_house"],
            "category": category,
            "nav": nav,
            "aum": aum,
            "expense_ratio": expense_ratio,
            "volatility": volatility,
            "beta": beta,
            "risk_score": risk_score,
            "sharpe_ratio": sharpe_ratio,
            "alpha": alpha,
            "sortino_ratio": sortino_ratio,
            "max_drawdown": max_drawdown,
            **returns,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def generate_nav_history() -> pd.DataFrame:
    """Generate daily NAV time-series for every fund over 3 years.

    Uses *geometric Brownian motion* (GBM) calibrated to each fund's
    annualised return and volatility so that the ending NAV is broadly
    consistent with the fund's stated performance.

    Returns:
        DataFrame with columns ``['date', 'fund_name', 'nav']``.
    """
    rng = np.random.RandomState(_SEED)
    funds_df = generate_fund_data()

    end_date = datetime(2026, 6, 20)
    # Build a vector of trading-day dates (skip weekends).
    all_dates: list[datetime] = []
    cursor = end_date - timedelta(days=int(_NAV_TRADING_DAYS * 365 / 252) + 30)
    while len(all_dates) < _NAV_TRADING_DAYS:
        if cursor.weekday() < 5:  # Mon-Fri
            all_dates.append(cursor)
        cursor += timedelta(days=1)
    all_dates = all_dates[-_NAV_TRADING_DAYS:]

    date_series = pd.to_datetime(all_dates)
    dt = 1.0 / 252.0  # fraction of year per trading day

    frames: list[pd.DataFrame] = []

    for _, fund in funds_df.iterrows():
        annual_return = fund["returns_1y"] / 100.0
        annual_vol = fund["volatility"] / 100.0
        current_nav: float = fund["nav"]

        # GBM: S(t) = S(0) * exp( (mu - sigma^2/2)*t + sigma*W(t) )
        drift = (annual_return - 0.5 * annual_vol ** 2) * dt
        diffusion = annual_vol * np.sqrt(dt)
        shocks = rng.normal(0, 1, _NAV_TRADING_DAYS)

        log_returns = drift + diffusion * shocks
        cumulative = np.cumsum(log_returns)

        # Scale so that the final NAV equals the fund's current NAV.
        raw_path = np.exp(cumulative)
        nav_path = current_nav * (raw_path / raw_path[-1])
        nav_path = np.round(nav_path, 2)

        frame = pd.DataFrame(
            {
                "date": date_series,
                "fund_name": fund["fund_name"],
                "nav": nav_path,
            }
        )
        frames.append(frame)

    nav_df = pd.concat(frames, ignore_index=True)
    return nav_df


def generate_portfolio_data() -> pd.DataFrame:
    """Generate holdings for three model client portfolios.

    * **Client A – Conservative (Age 55):** 40% Large Cap, 15% Debt,
      15% Hybrid, 15% Index, 10% Mid Cap, 5% Small Cap.
    * **Client B – Moderate (Age 35):** 25% Large Cap, 20% Mid Cap,
      15% Small Cap, 15% Flexi Cap, 15% Debt, 10% ELSS.
    * **Client C – Aggressive (Age 25):** 30% Small Cap, 25% Mid Cap,
      20% Flexi Cap, 15% ELSS, 10% Large Cap.

    Returns:
        DataFrame with columns ``['client_name', 'fund_name', 'category',
        'investment_amount', 'current_value', 'units', 'allocation_pct']``.
    """
    rng = np.random.RandomState(_SEED)
    funds_df = generate_fund_data()

    # Portfolio definitions: (client_name, total_investment,
    # {category: (allocation_pct, num_funds)})
    portfolios: list[tuple[str, float, dict[str, tuple[float, int]]]] = [
        (
            "Client A - Conservative",
            2_500_000.0,
            {
                "Large Cap": (40.0, 3),
                "Mid Cap": (10.0, 1),
                "Small Cap": (5.0, 1),
                "Debt": (15.0, 2),
                "Hybrid": (15.0, 1),
                "Index": (15.0, 1),
            },
        ),
        (
            "Client B - Moderate",
            1_500_000.0,
            {
                "Large Cap": (25.0, 2),
                "Mid Cap": (20.0, 2),
                "Small Cap": (15.0, 2),
                "Flexi Cap": (15.0, 1),
                "Debt": (15.0, 2),
                "ELSS": (10.0, 1),
            },
        ),
        (
            "Client C - Aggressive",
            800_000.0,
            {
                "Large Cap": (10.0, 1),
                "Mid Cap": (25.0, 2),
                "Small Cap": (30.0, 2),
                "Flexi Cap": (20.0, 2),
                "ELSS": (15.0, 1),
            },
        ),
    ]

    rows: list[dict[str, Any]] = []

    for client_name, total_inv, allocations in portfolios:
        for category, (alloc_pct, num_funds) in allocations.items():
            category_funds = funds_df[funds_df["category"] == category]
            if category_funds.empty:
                continue

            # Pick the top *num_funds* by AUM (simulates choosing popular funds).
            selected = category_funds.nlargest(num_funds, "aum")

            # Split the category allocation roughly equally across picks,
            # with a small random perturbation.
            raw_weights = rng.dirichlet(np.ones(len(selected)))
            fund_allocs = raw_weights * alloc_pct

            for (_, fund), fund_alloc in zip(selected.iterrows(), fund_allocs):
                inv_amount = round(total_inv * fund_alloc / 100.0, 2)
                # Current value = investment * (1 + 1-year return)
                growth = 1 + fund["returns_1y"] / 100.0
                current_value = round(inv_amount * growth, 2)
                units = round(current_value / fund["nav"], 4)

                rows.append(
                    {
                        "client_name": client_name,
                        "fund_name": fund["fund_name"],
                        "category": category,
                        "investment_amount": inv_amount,
                        "current_value": current_value,
                        "units": units,
                        "allocation_pct": round(fund_alloc, 2),
                    }
                )

    portfolio_df = pd.DataFrame(rows)
    return portfolio_df


def get_demo_data() -> dict[str, pd.DataFrame]:
    """Return all demo datasets in a single call.

    Returns:
        Dictionary with keys ``'funds'``, ``'nav_history'``, and
        ``'portfolios'``, each mapping to the corresponding DataFrame.
    """
    funds = generate_fund_data()
    nav_history = generate_nav_history()
    portfolios = generate_portfolio_data()
    return {
        "funds": funds,
        "nav_history": nav_history,
        "portfolios": portfolios,
    }


# ---------------------------------------------------------------------------
# Quick-check when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating demo fund data...")
    funds = generate_fund_data()
    print(f"  Funds: {len(funds)} rows, columns: {list(funds.columns)}")
    print(f"  Categories: {funds['category'].value_counts().to_dict()}")
    print()

    print("Generating NAV history...")
    nav = generate_nav_history()
    print(f"  NAV history: {len(nav)} rows")
    print(f"  Date range: {nav['date'].min()} to {nav['date'].max()}")
    print()

    print("Generating portfolio data...")
    port = generate_portfolio_data()
    print(f"  Portfolio rows: {len(port)}")
    print(f"  Clients: {port['client_name'].unique().tolist()}")
    print()

    print("Sample funds:")
    print(funds[["fund_name", "category", "nav", "aum", "returns_1y"]].head(10).to_string())
