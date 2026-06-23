"""
Portfolio analysis engine for client holdings.

Computes aggregate portfolio metrics – weighted returns, risk scores,
diversification, future projections – and delegates qualitative analysis
to :class:`services.ai_service.AIService`.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from utils.calculations import (
    calculate_cagr,
    calculate_diversification_score,
    calculate_expected_future_value,
)

logger = logging.getLogger(__name__)


class PortfolioEngine:
    """Analyse a client's mutual-fund portfolio.

    Parameters
    ----------
    data_service:
        Instance that exposes portfolio / fund data queries.
    ai_service:
        Instance for generating qualitative AI insights.
    """

    def __init__(self, data_service: Any, ai_service: Any) -> None:
        self._data_service = data_service
        self._ai_service = ai_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_portfolio(self, client_name: str) -> dict[str, Any]:
        """Run a full analysis on *client_name*'s portfolio.

        Args:
            client_name: Exact client name string (e.g. 'Client A - Conservative').

        Returns:
            Dict with keys: summary, allocation, diversification_score,
            risk_analysis, ai_analysis, future_projection.
        """
        portfolio_df = self._data_service.get_portfolio_data(client_name=client_name)
        funds_df = self._data_service.get_all_funds()

        if portfolio_df.empty:
            return self._empty_result()

        # ---- Merge fund-level metrics into holdings ----
        metric_cols = [
            "fund_name", "category", "returns_1y", "returns_3y", "returns_5y",
            "sharpe_ratio", "alpha", "beta", "volatility", "max_drawdown",
            "expense_ratio", "risk_score", "cagr", "sortino_ratio", "nav",
        ]
        available_cols = [c for c in metric_cols if c in funds_df.columns]
        merged = portfolio_df.merge(
            funds_df[available_cols],
            on="fund_name",
            how="left",
            suffixes=("", "_fund"),
        )
        # Resolve category column duplication
        if "category_fund" in merged.columns and "category" in merged.columns:
            merged["category"] = merged["category"].fillna(merged["category_fund"])
            merged.drop(columns=["category_fund"], inplace=True, errors="ignore")

        # ---- Summary ----
        total_investment = merged["investment_amount"].sum()
        current_value = merged["current_value"].sum()
        total_return = current_value - total_investment
        total_return_pct = (
            (total_return / total_investment) if total_investment > 0 else 0.0
        )
        portfolio_cagr = calculate_cagr(total_investment, current_value, 1.0)

        # Weighted risk score
        if "allocation_pct" in merged.columns and "risk_score" in merged.columns:
            total_alloc = merged["allocation_pct"].sum()
            if total_alloc > 0:
                weighted_risk = (
                    (merged["risk_score"] * merged["allocation_pct"]).sum() / total_alloc
                )
            else:
                weighted_risk = merged["risk_score"].mean()
        else:
            weighted_risk = merged.get("risk_score", pd.Series([5])).mean()

        summary = {
            "total_investment": round(total_investment, 2),
            "current_value": round(current_value, 2),
            "total_return": round(total_return, 2),
            "total_return_pct": round(total_return_pct, 4),
            "cagr": round(portfolio_cagr, 4),
            "risk_score": round(float(weighted_risk), 1),
        }

        # ---- Allocation ----
        category_allocation = (
            merged.groupby("category")
            .agg(
                total_investment=("investment_amount", "sum"),
                current_value=("current_value", "sum"),
                allocation_pct=("allocation_pct", "sum"),
            )
            .reset_index()
            .sort_values("allocation_pct", ascending=False)
        )

        fund_allocation = (
            merged[["fund_name", "category", "investment_amount", "current_value", "allocation_pct"]]
            .sort_values("allocation_pct", ascending=False)
            .reset_index(drop=True)
        )

        allocation = {
            "category_allocation": category_allocation,
            "fund_allocation": fund_allocation,
        }

        # ---- Diversification ----
        alloc_values = merged["allocation_pct"].tolist() if "allocation_pct" in merged.columns else []
        diversification = calculate_diversification_score(alloc_values)

        # ---- Risk analysis ----
        risk_breakdown = self._compute_risk_breakdown(merged)
        risk_label = "Low" if weighted_risk <= 3 else ("High" if weighted_risk >= 7 else "Medium")
        risk_analysis = {
            "overall_risk": risk_label,
            "overall_risk_score": round(float(weighted_risk), 1),
            "risk_breakdown": risk_breakdown,
        }

        # ---- AI insights ----
        ai_analysis = self._ai_service.analyze_portfolio(portfolio_df, funds_df)

        # ---- Future projection ----
        future_projection = self._project_future_value(current_value, merged)

        return {
            "summary": summary,
            "allocation": allocation,
            "diversification_score": diversification,
            "risk_analysis": risk_analysis,
            "ai_analysis": ai_analysis,
            "future_projection": future_projection,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_risk_breakdown(merged: pd.DataFrame) -> dict[str, float]:
        """Compute per-dimension risk scores for radar chart display.

        Each metric is normalised to a 0-10 scale.
        """
        breakdown: dict[str, float] = {}

        # Volatility risk (0-10): 0% vol → 0, 30% vol → 10
        if "volatility" in merged.columns and "allocation_pct" in merged.columns:
            total_alloc = merged["allocation_pct"].sum()
            if total_alloc > 0:
                w_vol = (merged["volatility"] * merged["allocation_pct"]).sum() / total_alloc
            else:
                w_vol = merged["volatility"].mean()
            breakdown["Volatility"] = round(min(w_vol / 3.0, 10.0), 1)
        else:
            breakdown["Volatility"] = 5.0

        # Drawdown risk (0-10): 0% → 0, -50% → 10
        if "max_drawdown" in merged.columns and "allocation_pct" in merged.columns:
            total_alloc = merged["allocation_pct"].sum()
            if total_alloc > 0:
                w_dd = (merged["max_drawdown"].abs() * merged["allocation_pct"]).sum() / total_alloc
            else:
                w_dd = merged["max_drawdown"].abs().mean()
            breakdown["Drawdown"] = round(min(w_dd / 5.0, 10.0), 1)
        else:
            breakdown["Drawdown"] = 5.0

        # Market sensitivity (beta): 0 → 0, 2 → 10
        if "beta" in merged.columns and "allocation_pct" in merged.columns:
            total_alloc = merged["allocation_pct"].sum()
            if total_alloc > 0:
                w_beta = (merged["beta"] * merged["allocation_pct"]).sum() / total_alloc
            else:
                w_beta = merged["beta"].mean()
            breakdown["Market Sensitivity"] = round(min(w_beta * 5.0, 10.0), 1)
        else:
            breakdown["Market Sensitivity"] = 5.0

        # Concentration risk: HHI-based (0 = perfectly diversified, 10 = single fund)
        if "allocation_pct" in merged.columns:
            total = merged["allocation_pct"].sum()
            if total > 0:
                shares = (merged["allocation_pct"] / total).values
                hhi = float(np.sum(shares ** 2))
                breakdown["Concentration"] = round(hhi * 10.0, 1)
            else:
                breakdown["Concentration"] = 10.0
        else:
            breakdown["Concentration"] = 5.0

        # Expense drag: avg expense 0% → 0, 2% → 10
        if "expense_ratio" in merged.columns and "allocation_pct" in merged.columns:
            total_alloc = merged["allocation_pct"].sum()
            if total_alloc > 0:
                w_exp = (merged["expense_ratio"] * merged["allocation_pct"]).sum() / total_alloc
            else:
                w_exp = merged["expense_ratio"].mean()
            breakdown["Expense Drag"] = round(min(w_exp * 5.0, 10.0), 1)
        else:
            breakdown["Expense Drag"] = 5.0

        # Liquidity risk: inverse of AUM (smaller AUM = higher risk)
        # Placeholder heuristic: small-cap/mid-cap heavy → higher
        if "category" in merged.columns and "allocation_pct" in merged.columns:
            illiquid_cats = {"Small Cap", "Mid Cap"}
            illiquid_pct = merged.loc[
                merged["category"].isin(illiquid_cats), "allocation_pct"
            ].sum()
            breakdown["Liquidity"] = round(min(illiquid_pct / 10.0, 10.0), 1)
        else:
            breakdown["Liquidity"] = 5.0

        return breakdown

    @staticmethod
    def _project_future_value(
        current_value: float,
        merged: pd.DataFrame,
    ) -> dict[str, Any]:
        """Project portfolio value under conservative/moderate/aggressive scenarios.

        Returns dict with 'years' list and value lists for each scenario.
        """
        years = [1, 3, 5, 10]

        # Estimate base CAGR from portfolio's weighted returns
        if "cagr" in merged.columns and "allocation_pct" in merged.columns:
            total_alloc = merged["allocation_pct"].sum()
            if total_alloc > 0:
                base_cagr = (
                    (merged["cagr"] * merged["allocation_pct"]).sum() / total_alloc
                ) / 100.0  # convert from percentage to decimal
            else:
                base_cagr = 0.10
        elif "returns_1y" in merged.columns and "allocation_pct" in merged.columns:
            total_alloc = merged["allocation_pct"].sum()
            if total_alloc > 0:
                base_cagr = (
                    (merged["returns_1y"] * merged["allocation_pct"]).sum() / total_alloc
                ) / 100.0
            else:
                base_cagr = 0.10
        else:
            base_cagr = 0.10

        # Scenario adjustments
        conservative_cagr = max(base_cagr * 0.6, 0.04)
        moderate_cagr = max(base_cagr * 0.85, 0.06)
        aggressive_cagr = max(base_cagr * 1.15, 0.10)

        conservative = [
            round(calculate_expected_future_value(current_value, conservative_cagr, y), 2)
            for y in years
        ]
        moderate = [
            round(calculate_expected_future_value(current_value, moderate_cagr, y), 2)
            for y in years
        ]
        aggressive = [
            round(calculate_expected_future_value(current_value, aggressive_cagr, y), 2)
            for y in years
        ]

        return {
            "years": years,
            "conservative": conservative,
            "moderate": moderate,
            "aggressive": aggressive,
            "cagr_conservative": round(conservative_cagr * 100, 2),
            "cagr_moderate": round(moderate_cagr * 100, 2),
            "cagr_aggressive": round(aggressive_cagr * 100, 2),
        }

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        """Return a well-typed empty result when no portfolio data exists."""
        return {
            "summary": {
                "total_investment": 0.0,
                "current_value": 0.0,
                "total_return": 0.0,
                "total_return_pct": 0.0,
                "cagr": 0.0,
                "risk_score": 0.0,
            },
            "allocation": {
                "category_allocation": pd.DataFrame(
                    columns=["category", "total_investment", "current_value", "allocation_pct"]
                ),
                "fund_allocation": pd.DataFrame(
                    columns=["fund_name", "category", "investment_amount", "current_value", "allocation_pct"]
                ),
            },
            "diversification_score": 0.0,
            "risk_analysis": {
                "overall_risk": "N/A",
                "overall_risk_score": 0.0,
                "risk_breakdown": {},
            },
            "ai_analysis": {
                "strengths": ["No portfolio data available."],
                "weaknesses": [],
                "recommendations": ["Start investing to build your portfolio."],
                "health_score": 0,
            },
            "future_projection": {
                "years": [1, 3, 5, 10],
                "conservative": [0, 0, 0, 0],
                "moderate": [0, 0, 0, 0],
                "aggressive": [0, 0, 0, 0],
                "cagr_conservative": 0.0,
                "cagr_moderate": 0.0,
                "cagr_aggressive": 0.0,
            },
        }
