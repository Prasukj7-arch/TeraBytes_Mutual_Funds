"""
Personalised mutual fund recommendation engine.

Builds an optimised portfolio allocation from the fund universe based on
the investor's age, risk appetite, investment horizon, and financial goal.
Funds are scored using a composite of returns, Sharpe ratio, alpha,
drawdown resilience, and cost efficiency.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from config.settings import AppConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profile constants
# ---------------------------------------------------------------------------

_PROFILE_ALLOCATIONS: dict[str, dict[str, float]] = {
    "conservative": {
        "Large Cap": 40.0,
        "Mid Cap": 5.0,
        "Small Cap": 0.0,
        "Flexi Cap": 10.0,
        "ELSS": 0.0,
        "Debt": 25.0,
        "Hybrid": 10.0,
        "Index": 10.0,
    },
    "moderate": {
        "Large Cap": 25.0,
        "Mid Cap": 20.0,
        "Small Cap": 10.0,
        "Flexi Cap": 15.0,
        "ELSS": 10.0,
        "Debt": 15.0,
        "Hybrid": 0.0,
        "Index": 5.0,
    },
    "aggressive": {
        "Large Cap": 15.0,
        "Mid Cap": 25.0,
        "Small Cap": 25.0,
        "Flexi Cap": 20.0,
        "ELSS": 15.0,
        "Debt": 0.0,
        "Hybrid": 0.0,
        "Index": 0.0,
    },
}

_GOAL_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "Tax Saving": {"ELSS": 15.0, "Debt": -5.0, "Large Cap": -5.0, "Index": -5.0},
    "Retirement": {"Debt": 10.0, "Hybrid": 10.0, "Small Cap": -10.0, "Mid Cap": -10.0},
    "Wealth Creation": {"Small Cap": 5.0, "Mid Cap": 5.0, "Debt": -5.0, "Hybrid": -5.0},
    "Child Education": {"Flexi Cap": 5.0, "Large Cap": 5.0, "Small Cap": -5.0, "Debt": -5.0},
    "House Purchase": {"Debt": 10.0, "Hybrid": 5.0, "Small Cap": -10.0, "Mid Cap": -5.0},
    "Emergency Fund": {"Debt": 20.0, "Hybrid": 5.0, "Small Cap": -15.0, "Mid Cap": -5.0, "ELSS": -5.0},
}

# Weights for the composite fund-quality score
_SCORE_WEIGHTS = {
    "returns_1y": 0.30,
    "sharpe_ratio": 0.25,
    "alpha": 0.20,
    "drawdown_resilience": 0.15,
    "cost_efficiency": 0.10,
}


class RecommendationEngine:
    """Build personalised mutual-fund portfolio recommendations.

    Parameters
    ----------
    data_service:
        Instance providing fund-universe data.
    ai_service:
        Instance for generating human-readable explanations.
    """

    def __init__(self, data_service: Any, ai_service: Any) -> None:
        self._data_service = data_service
        self._ai_service = ai_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_recommendations(
        self,
        investment_amount: float,
        age: int,
        risk_appetite: str,
        horizon_years: int,
        goal: str,
    ) -> dict[str, Any]:
        """Generate a complete set of fund recommendations.

        Args:
            investment_amount: Total amount to invest (₹).
            age: Investor age in years.
            risk_appetite: One of 'Low', 'Medium', 'High'.
            horizon_years: Investment horizon in years.
            goal: Financial goal (from AppConfig.GOALS).

        Returns:
            Dict with keys: recommended_funds, portfolio_summary,
            allocation_chart_data.
        """
        funds_df = self._data_service.get_all_funds()

        # 1. Determine risk profile
        profile = self._determine_risk_profile(age, risk_appetite, horizon_years)

        # 2. Compute target category allocation
        allocation = self._build_allocation(profile, goal)

        # 3. Score all funds
        scored = self._score_funds(funds_df)

        # 4. Select best fund per category
        recommended: list[dict[str, Any]] = []
        user_profile = {
            "age": age,
            "risk_appetite": risk_appetite,
            "horizon_years": horizon_years,
            "goal": goal,
            "investment_amount": investment_amount,
        }

        for category, pct in allocation.items():
            if pct <= 0:
                continue
            category_funds = scored[scored["category"] == category]
            if category_funds.empty:
                continue
            # Pick the top fund in this category
            top_fund = category_funds.iloc[0]

            fund_dict = top_fund.to_dict()
            reason = self._ai_service.generate_recommendation_explanation(
                fund_dict, user_profile,
            )

            recommended.append({
                "fund_name": top_fund["fund_name"],
                "category": category,
                "expected_return": float(top_fund.get("returns_1y", 12.0)),
                "risk_score": int(top_fund.get("risk_score", 5)),
                "allocation_pct": pct,
                "reason": reason,
                "sharpe_ratio": float(top_fund.get("sharpe_ratio", 1.0)),
                "expense_ratio": float(top_fund.get("expense_ratio", 1.0)),
                "alpha": float(top_fund.get("alpha", 0.0)),
                "max_drawdown": float(top_fund.get("max_drawdown", -15.0)),
            })

        # 5. Build summary
        if recommended:
            weighted_return = sum(
                r["expected_return"] * r["allocation_pct"] for r in recommended
            ) / sum(r["allocation_pct"] for r in recommended)
            weighted_risk = sum(
                r["risk_score"] * r["allocation_pct"] for r in recommended
            ) / sum(r["allocation_pct"] for r in recommended)
            n_categories = len({r["category"] for r in recommended})
            # Diversification: 1 - HHI
            total_alloc = sum(r["allocation_pct"] for r in recommended)
            shares = [r["allocation_pct"] / total_alloc for r in recommended if total_alloc > 0]
            hhi = sum(s ** 2 for s in shares) if shares else 1.0
            diversification = round((1.0 - hhi) * 100, 1)
        else:
            weighted_return = 0.0
            weighted_risk = 5.0
            diversification = 0.0

        risk_label = "Low" if weighted_risk <= 4 else ("High" if weighted_risk >= 7 else "Moderate")

        portfolio_summary = {
            "total_allocation": sum(r["allocation_pct"] for r in recommended),
            "expected_cagr": round(weighted_return, 2),
            "risk_level": risk_label,
            "risk_score": round(weighted_risk, 1),
            "diversification_score": diversification,
            "profile": profile,
            "num_funds": len(recommended),
            "num_categories": len({r["category"] for r in recommended}),
        }

        # 6. Allocation chart data
        alloc_chart = pd.DataFrame([
            {"category": r["category"], "allocation_pct": r["allocation_pct"]}
            for r in recommended
        ]) if recommended else pd.DataFrame(columns=["category", "allocation_pct"])

        return {
            "recommended_funds": recommended,
            "portfolio_summary": portfolio_summary,
            "allocation_chart_data": alloc_chart,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_risk_profile(age: int, risk_appetite: str, horizon_years: int) -> str:
        """Map (age, risk_appetite, horizon) to a risk profile label.

        Returns one of: 'conservative', 'moderate', 'aggressive'.
        """
        # Score each dimension 0-2 (0 = conservative, 2 = aggressive)
        if age >= 50:
            age_score = 0
        elif age >= 35:
            age_score = 1
        else:
            age_score = 2

        appetite_map = {"Low": 0, "Medium": 1, "High": 2}
        appetite_score = appetite_map.get(risk_appetite, 1)

        if horizon_years <= 3:
            horizon_score = 0
        elif horizon_years <= 7:
            horizon_score = 1
        else:
            horizon_score = 2

        # Weighted composite (appetite has highest weight)
        composite = 0.3 * age_score + 0.4 * appetite_score + 0.3 * horizon_score
        if composite <= 0.7:
            return "conservative"
        if composite <= 1.3:
            return "moderate"
        return "aggressive"

    @staticmethod
    def _build_allocation(profile: str, goal: str) -> dict[str, float]:
        """Build target category allocation from profile + goal adjustments.

        Returns dict mapping category name → allocation percentage.
        """
        base = dict(_PROFILE_ALLOCATIONS.get(profile, _PROFILE_ALLOCATIONS["moderate"]))

        adjustments = _GOAL_ADJUSTMENTS.get(goal, {})
        for cat, delta in adjustments.items():
            if cat in base:
                base[cat] = max(0.0, base[cat] + delta)

        # Normalise to 100%
        total = sum(base.values())
        if total > 0 and total != 100.0:
            factor = 100.0 / total
            base = {k: round(v * factor, 1) for k, v in base.items()}

        # Drop zero allocations
        return {k: v for k, v in base.items() if v > 0}

    @staticmethod
    def _score_funds(funds_df: pd.DataFrame) -> pd.DataFrame:
        """Rank every fund using a composite quality score.

        The output DataFrame is sorted by descending score within each category.
        """
        df = funds_df.copy()

        # Percentile ranks within each category (higher = better)
        df["returns_1y_rank"] = df.groupby("category")["returns_1y"].rank(pct=True, ascending=True)
        df["sharpe_rank"] = df.groupby("category")["sharpe_ratio"].rank(pct=True, ascending=True)
        df["alpha_rank"] = df.groupby("category")["alpha"].rank(pct=True, ascending=True)

        # Drawdown resilience: less negative is better → rank ascending (more = better)
        df["drawdown_rank"] = df.groupby("category")["max_drawdown"].rank(pct=True, ascending=True)

        # Cost efficiency: lower expense is better → rank descending
        df["expense_rank"] = df.groupby("category")["expense_ratio"].rank(pct=True, ascending=False)

        df["composite_score"] = (
            _SCORE_WEIGHTS["returns_1y"] * df["returns_1y_rank"]
            + _SCORE_WEIGHTS["sharpe_ratio"] * df["sharpe_rank"]
            + _SCORE_WEIGHTS["alpha"] * df["alpha_rank"]
            + _SCORE_WEIGHTS["drawdown_resilience"] * df["drawdown_rank"]
            + _SCORE_WEIGHTS["cost_efficiency"] * df["expense_rank"]
        )

        df = df.sort_values(
            ["category", "composite_score"], ascending=[True, False]
        ).reset_index(drop=True)

        return df
