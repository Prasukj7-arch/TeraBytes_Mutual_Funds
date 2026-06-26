"""
Chat service for the AI Fund Advisor.

Provides a rule-based conversational engine that can answer questions about
mutual funds, portfolios, risk metrics, and investment strategies.  When an
OpenAI API key is configured the service delegates to :class:`AIService` for
enhanced natural-language responses; otherwise it falls back to rich,
pre-built answer templates that are good enough to demo without any API key.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from config.settings import OpenAIConfig

logger = logging.getLogger(__name__)

# Try importing AIService — it may not exist yet.
_AIService: type | None = None
try:
    from services.ai_service import AIService as _AIService  # type: ignore[assignment]
except ImportError:
    logger.debug("AIService not available; chat will run in offline mode.")


class ChatService:
    """Conversational assistant for mutual-fund analytics.

    Parameters
    ----------
    data_service:
        An initialised ``DataService`` instance used to look up fund data,
        categories, and portfolio information.
    """

    # Minimum similarity score (0–1) for fuzzy fund-name matching.
    _FUND_MATCH_THRESHOLD: float = 0.45

    def __init__(self, data_service: Any) -> None:
        self._ds = data_service
        self._history: list[dict[str, str]] = []
        self._ai: Any | None = None

        # Pre-load fund names for entity extraction.
        try:
            funds_df = self._ds.get_all_funds()
            self._fund_names: list[str] = funds_df["fund_name"].tolist()
            self._categories: list[str] = self._ds.get_categories()
        except Exception:
            self._fund_names = []
            self._categories = []

        # Optionally initialise AI backend.
        if OpenAIConfig.is_configured() and _AIService is not None:
            try:
                self._ai = _AIService()
            except Exception as exc:
                logger.warning("Could not initialise AIService: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_message(self, user_message: str) -> str:
        """Process *user_message* and return an assistant response.

        Routes to the most relevant handler based on intent detection.
        Appends both messages to the conversation history.
        """
        self._history.append({"role": "user", "content": user_message})

        intent, entities = self._detect_intent(user_message)

        match intent:
            case "compare":
                response = self._handle_comparison(
                    entities.get("fund_a", ""),
                    entities.get("fund_b", ""),
                )
            case "fund_info":
                response = self._handle_fund_query(entities.get("fund_name", ""))
            case "category_info":
                response = self._handle_category_query(entities.get("category", ""))
            case "portfolio":
                response = self._handle_portfolio_query()
            case "risk":
                response = self._handle_risk_query(context=entities.get("context"))
            case "recommendation":
                response = self._handle_recommendation_query(entities)
            case _:
                response = self._handle_general(user_message)

        self._history.append({"role": "assistant", "content": response})
        return response

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def _detect_intent(self, message: str) -> tuple[str, dict[str, Any]]:
        """Classify *message* into an intent and extract entities.

        Returns
        -------
        tuple[str, dict]
            ``(intent_type, extracted_entities)`` where *intent_type* is one
            of ``'compare'``, ``'fund_info'``, ``'category_info'``,
            ``'portfolio'``, ``'risk'``, ``'recommendation'``, ``'general'``.
        """
        lower = message.lower().strip()
        entities: dict[str, Any] = {}

        # --- Comparison intent ---
        if "compare" in lower or " vs " in lower or " versus " in lower:
            fund_a, fund_b = self._extract_comparison_funds(message)
            if fund_a and fund_b:
                return "compare", {"fund_a": fund_a, "fund_b": fund_b}

        # --- Category intent ---
        matched_category = self._match_category(lower)
        if matched_category and any(
            kw in lower
            for kw in [
                "category", "how", "performance", "best", "top", "worst",
                "average", "which", "list", "show", "tell",
            ]
        ):
            entities["category"] = matched_category
            return "category_info", entities

        # --- Portfolio intent ---
        portfolio_keywords = [
            "portfolio", "my fund", "my investment", "holdings",
            "allocation", "diversi", "client",
        ]
        if any(kw in lower for kw in portfolio_keywords):
            return "portfolio", entities

        # --- Risk intent ---
        risk_keywords = [
            "risk", "sharpe", "sortino", "alpha", "beta", "volatility",
            "drawdown", "max drawdown", "expense ratio", "standard deviation",
        ]
        if any(kw in lower for kw in risk_keywords):
            context_metric = next(
                (kw for kw in risk_keywords if kw in lower), None
            )
            entities["context"] = context_metric
            return "risk", entities

        # --- Recommendation intent ---
        recommend_keywords = [
            "recommend", "suggest", "best fund", "which fund", "should i",
            "good fund", "top fund", "lowest expense", "highest return",
        ]
        if any(kw in lower for kw in recommend_keywords):
            entities["category"] = matched_category
            return "recommendation", entities

        # --- Specific fund intent ---
        matched_fund = self._find_fund_in_message(message)
        if matched_fund:
            return "fund_info", {"fund_name": matched_fund}

        return "general", entities

    # ------------------------------------------------------------------
    # Entity extraction helpers
    # ------------------------------------------------------------------

    def _find_fund_in_message(self, message: str) -> str | None:
        """Return the best-matching fund name found in *message*, or None."""
        lower = message.lower()
        best_match: str | None = None
        best_score: float = 0.0

        for fund_name in self._fund_names:
            fund_lower = fund_name.lower()

            # Exact substring match is highest confidence.
            if fund_lower in lower:
                return fund_name

            # Try matching significant words from the fund name.
            significant_words = [
                w for w in fund_lower.split()
                if w not in {"fund", "-", "direct", "regular", "growth", "plan", "the"}
            ]
            if len(significant_words) >= 2:
                matched_words = sum(1 for w in significant_words if w in lower)
                word_score = matched_words / len(significant_words)
                if word_score > best_score and word_score >= 0.5:
                    best_score = word_score
                    best_match = fund_name

        # Fuzzy fallback on shorter messages that look like fund names.
        if best_match is None and len(message.split()) <= 10:
            for fund_name in self._fund_names:
                score = SequenceMatcher(
                    None, message.lower(), fund_name.lower()
                ).ratio()
                if score > best_score and score >= self._FUND_MATCH_THRESHOLD:
                    best_score = score
                    best_match = fund_name

        return best_match

    def _extract_comparison_funds(self, message: str) -> tuple[str | None, str | None]:
        """Extract two fund names from a comparison message."""
        # Try splitting on common comparison delimiters.
        for delimiter in [" vs ", " versus ", " and ", " with ", " against "]:
            if delimiter in message.lower():
                parts = re.split(re.escape(delimiter), message, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) == 2:
                    # Remove the "compare" keyword if present.
                    left = re.sub(r"(?i)^compare\s+", "", parts[0]).strip()
                    right = parts[1].strip().rstrip("?.")
                    fund_a = self._find_fund_in_message(left) or self._best_fuzzy_match(left)
                    fund_b = self._find_fund_in_message(right) or self._best_fuzzy_match(right)
                    return fund_a, fund_b

        # Fallback: find any two fund names mentioned in the full message.
        found: list[str] = []
        for fund_name in self._fund_names:
            if fund_name.lower() in message.lower():
                found.append(fund_name)
                if len(found) == 2:
                    break
        if len(found) == 2:
            return found[0], found[1]
        return None, None

    def _best_fuzzy_match(self, text: str) -> str | None:
        """Return the best fuzzy-matching fund name for *text*."""
        best: str | None = None
        best_score: float = 0.0
        text_lower = text.lower()
        for fund_name in self._fund_names:
            score = SequenceMatcher(None, text_lower, fund_name.lower()).ratio()
            if score > best_score:
                best_score = score
                best = fund_name
        return best if best_score >= self._FUND_MATCH_THRESHOLD else None

    def _match_category(self, text_lower: str) -> str | None:
        """Return a matching category name if mentioned in *text_lower*."""
        for category in self._categories:
            if category.lower() in text_lower:
                return category
        # Partial / keyword matching.
        category_aliases: dict[str, list[str]] = {
            "Large Cap": ["large cap", "largecap", "large-cap", "bluechip", "blue chip"],
            "Mid Cap": ["mid cap", "midcap", "mid-cap"],
            "Small Cap": ["small cap", "smallcap", "small-cap"],
            "Flexi Cap": ["flexi cap", "flexicap", "flexi-cap"],
            "Multi Cap": ["multi cap", "multicap", "multi-cap"],
            "ELSS": ["elss", "tax sav"],
            "Hybrid": ["hybrid", "balanced"],
            "Debt": ["debt", "bond", "fixed income", "liquid"],
            "Index": ["index", "passive", "nifty 50", "sensex"],
        }
        for category, aliases in category_aliases.items():
            if any(alias in text_lower for alias in aliases):
                if category in self._categories:
                    return category
        return None

    # ------------------------------------------------------------------
    # Handler methods
    # ------------------------------------------------------------------

    def _handle_comparison(self, fund_a_name: str, fund_b_name: str) -> str:
        """Compare two funds side-by-side."""
        try:
            fund_a = self._ds.get_fund_by_name(fund_a_name)
            fund_b = self._ds.get_fund_by_name(fund_b_name)
        except Exception:
            return (
                "⚠️ I couldn't find one or both of those funds. "
                "Please check the fund names and try again.\n\n"
                "💡 *Tip:* You can browse the full fund list on the "
                "**Fund Analysis** page."
            )

        if fund_a is None or fund_b is None:
            return (
                "⚠️ I couldn't find one or both of those funds. "
                "Please check the fund names and try again."
            )

        lines: list[str] = [
            f"## ⚖️ Fund Comparison\n",
            f"| Metric | **{self._short_name(fund_a_name)}** | **{self._short_name(fund_b_name)}** |",
            "|--------|--------|--------|",
        ]

        metrics = [
            ("Category", "category", ""),
            ("NAV", "nav", "₹"),
            ("AUM (Cr)", "aum", "₹"),
            ("1Y Return", "returns_1y", "%"),
            ("3Y Return", "returns_3y", "%"),
            ("5Y Return", "returns_5y", "%"),
            ("CAGR", "cagr", "%"),
            ("Expense Ratio", "expense_ratio", "%"),
            ("Sharpe Ratio", "sharpe_ratio", ""),
            ("Sortino Ratio", "sortino_ratio", ""),
            ("Alpha", "alpha", ""),
            ("Beta", "beta", ""),
            ("Volatility", "volatility", "%"),
            ("Max Drawdown", "max_drawdown", "%"),
            ("Risk Score", "risk_score", "/10"),
        ]

        for label, key, suffix in metrics:
            val_a = self._safe_get(fund_a, key)
            val_b = self._safe_get(fund_b, key)
            fmt_a = self._format_metric(val_a, suffix)
            fmt_b = self._format_metric(val_b, suffix)
            lines.append(f"| {label} | {fmt_a} | {fmt_b} |")

        # Add a verdict.
        lines.append("")
        lines.append(self._comparison_verdict(fund_a, fund_b, fund_a_name, fund_b_name))

        return "\n".join(lines)

    def _handle_fund_query(self, fund_name: str) -> str:
        """Look up a single fund and return its summary."""
        try:
            fund = self._ds.get_fund_by_name(fund_name)
        except Exception:
            fund = None

        if fund is None:
            return (
                f"⚠️ I couldn't find a fund matching **{fund_name}**.\n\n"
                "Please check the name and try again, or browse the "
                "**Fund Analysis** page for the complete list."
            )

        return self._format_fund_summary(fund)

    def _handle_category_query(self, category: str) -> str:
        """Summarise performance and key statistics for a category."""
        try:
            funds_df = self._ds.get_all_funds()
        except Exception:
            return "⚠️ Unable to load fund data at the moment."

        cat_funds = funds_df[funds_df["category"] == category]
        if cat_funds.empty:
            return f"No funds found in the **{category}** category."

        count = len(cat_funds)
        avg_1y = cat_funds["returns_1y"].mean()
        avg_3y = cat_funds["returns_3y"].mean()
        avg_5y = cat_funds["returns_5y"].mean()
        avg_expense = cat_funds["expense_ratio"].mean()
        avg_sharpe = cat_funds["sharpe_ratio"].mean()
        avg_risk = cat_funds["risk_score"].mean()
        best_fund = cat_funds.loc[cat_funds["returns_1y"].idxmax()]
        worst_fund = cat_funds.loc[cat_funds["returns_1y"].idxmin()]

        lines = [
            f"## 📊 {category} Category Overview\n",
            f"**{count} funds** available in this category.\n",
            "### Average Performance",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| 1-Year Return | {avg_1y:.2f}% |",
            f"| 3-Year Return | {avg_3y:.2f}% |",
            f"| 5-Year Return | {avg_5y:.2f}% |",
            f"| Expense Ratio | {avg_expense:.2f}% |",
            f"| Sharpe Ratio | {avg_sharpe:.2f} |",
            f"| Avg Risk Score | {avg_risk:.1f}/10 |",
            "",
            "### 🏆 Top Performer (1Y)",
            f"**{best_fund['fund_name']}** — {best_fund['returns_1y']:.2f}% return",
            "",
            "### 📉 Bottom Performer (1Y)",
            f"**{worst_fund['fund_name']}** — {worst_fund['returns_1y']:.2f}% return",
        ]

        # Top 5 by 1Y return.
        top5 = cat_funds.nlargest(5, "returns_1y")
        lines.append("")
        lines.append("### Top 5 Funds by 1-Year Return")
        lines.append("| # | Fund | 1Y Return | Sharpe |")
        lines.append("|---|------|-----------|--------|")
        for rank, (_, row) in enumerate(top5.iterrows(), 1):
            lines.append(
                f"| {rank} | {self._short_name(row['fund_name'])} | "
                f"{row['returns_1y']:.2f}% | {row['sharpe_ratio']:.2f} |"
            )

        return "\n".join(lines)

    def _handle_portfolio_query(self) -> str:
        """Provide general portfolio analysis and advice."""
        try:
            portfolio_df = self._ds.get_portfolio_data()
        except Exception:
            portfolio_df = pd.DataFrame()

        if portfolio_df.empty:
            return (
                "📁 **Portfolio Analysis**\n\n"
                "No portfolio data is currently loaded. Here are some "
                "general portfolio guidelines:\n\n"
                "1. **Diversify** across Large Cap, Mid Cap, and Debt\n"
                "2. **Rebalance** annually to maintain target allocation\n"
                "3. Keep **expense ratios** below 1% for long-term savings\n"
                "4. Match your **risk tolerance** to your investment horizon\n"
                "5. Use **SIP** for rupee-cost averaging in volatile markets"
            )

        clients = portfolio_df["client_name"].unique().tolist()
        lines = [
            "## 📁 Portfolio Summary\n",
            f"I have data for **{len(clients)}** client portfolio(s):\n",
        ]
        for client in clients:
            client_data = portfolio_df[portfolio_df["client_name"] == client]
            total_invested = client_data["investment_amount"].sum()
            total_current = client_data["current_value"].sum()
            gain = total_current - total_invested
            gain_pct = (gain / total_invested * 100) if total_invested > 0 else 0.0
            num_funds = len(client_data)
            categories = client_data["category"].nunique()
            gain_emoji = "📈" if gain >= 0 else "📉"

            lines.append(f"### {client}")
            lines.append(f"- 💰 Invested: ₹{total_invested:,.0f}")
            lines.append(f"- 💎 Current Value: ₹{total_current:,.0f}")
            lines.append(f"- {gain_emoji} Gain/Loss: ₹{gain:,.0f} ({gain_pct:+.2f}%)")
            lines.append(f"- 📦 Holdings: {num_funds} funds across {categories} categories")
            lines.append("")

        lines.append("---")
        lines.append(
            "💡 *Ask about a specific client (e.g. 'How is Client A doing?') "
            "for a detailed breakdown.*"
        )
        return "\n".join(lines)

    def _handle_risk_query(self, context: str | None = None) -> str:
        """Explain risk metrics with practical examples."""
        explanations: dict[str, str] = {
            "sharpe": (
                "## 📐 Sharpe Ratio\n\n"
                "The **Sharpe Ratio** measures *risk-adjusted return* — how much "
                "excess return you earn per unit of risk (volatility).\n\n"
                "**Formula:** (Fund Return − Risk-Free Rate) ÷ Standard Deviation\n\n"
                "| Rating | Sharpe Ratio |\n"
                "|--------|-------------|\n"
                "| 🟢 Excellent | > 1.5 |\n"
                "| 🟡 Good | 1.0 – 1.5 |\n"
                "| 🟠 Average | 0.5 – 1.0 |\n"
                "| 🔴 Poor | < 0.5 |\n\n"
                "💡 *A higher Sharpe Ratio means better returns for the risk taken.*"
            ),
            "sortino": (
                "## 📐 Sortino Ratio\n\n"
                "The **Sortino Ratio** is similar to Sharpe but only penalises "
                "*downside* volatility, ignoring upside fluctuations.\n\n"
                "**Formula:** (Fund Return − Risk-Free Rate) ÷ Downside Deviation\n\n"
                "A fund with high upside swings but stable downside will have a "
                "better Sortino than Sharpe.\n\n"
                "💡 *Sortino > 2.0 is generally considered excellent.*"
            ),
            "alpha": (
                "## 📐 Alpha\n\n"
                "**Alpha** measures how much a fund outperforms (or underperforms) "
                "its benchmark after adjusting for market risk (beta).\n\n"
                "| Alpha | Interpretation |\n"
                "|-------|---------------|\n"
                "| > 0 | 🟢 Outperforming the benchmark |\n"
                "| = 0 | 🟡 Matching the benchmark |\n"
                "| < 0 | 🔴 Underperforming the benchmark |\n\n"
                "💡 *Positive alpha indicates genuine fund-manager skill.*"
            ),
            "beta": (
                "## 📐 Beta\n\n"
                "**Beta** measures a fund's sensitivity to market movements.\n\n"
                "| Beta | Meaning |\n"
                "|------|--------|\n"
                "| 1.0 | Moves exactly with the market |\n"
                "| > 1.0 | More volatile than market (amplifies moves) |\n"
                "| < 1.0 | Less volatile (dampens moves) |\n"
                "| < 0 | Inversely correlated (very rare) |\n\n"
                "💡 *Conservative investors prefer beta < 1.0.*"
            ),
            "volatility": (
                "## 📐 Volatility\n\n"
                "**Volatility** (standard deviation of returns) measures how much "
                "a fund's NAV fluctuates over time.\n\n"
                "| Category | Typical Volatility |\n"
                "|----------|-------------------|\n"
                "| Debt / Liquid | 2% – 6% |\n"
                "| Large Cap | 10% – 18% |\n"
                "| Mid Cap | 14% – 24% |\n"
                "| Small Cap | 18% – 30% |\n\n"
                "💡 *Higher volatility means bigger swings — both up and down.*"
            ),
            "drawdown": (
                "## 📐 Maximum Drawdown\n\n"
                "**Max Drawdown** is the largest peak-to-trough decline in NAV, "
                "representing the worst-case loss an investor could have experienced.\n\n"
                "For example, a max drawdown of −25% means the fund lost 25% "
                "from its peak before recovering.\n\n"
                "💡 *Look at drawdown alongside recovery time for full context.*"
            ),
            "max drawdown": (
                "## 📐 Maximum Drawdown\n\n"
                "**Max Drawdown** is the largest peak-to-trough decline in NAV, "
                "representing the worst-case loss an investor could have experienced.\n\n"
                "For example, a max drawdown of −25% means the fund lost 25% "
                "from its peak before recovering.\n\n"
                "💡 *Look at drawdown alongside recovery time for full context.*"
            ),
            "expense ratio": (
                "## 💰 Expense Ratio\n\n"
                "The **Expense Ratio** (TER) is the annual fee charged by the "
                "fund house, expressed as a percentage of AUM.\n\n"
                "| Type | Typical Range |\n"
                "|------|-------------|\n"
                "| Index / Passive | 0.10% – 0.50% |\n"
                "| Direct Plans | 0.25% – 1.50% |\n"
                "| Regular Plans | 1.00% – 2.50% |\n\n"
                "💡 *Even a 0.5% difference compounds significantly over 20+ years.*"
            ),
            "risk": (
                "## ⚠️ Understanding Risk in Mutual Funds\n\n"
                "Risk in mutual funds is multi-dimensional:\n\n"
                "1. **Market Risk** – NAV drops when markets fall\n"
                "2. **Volatility** – How much NAV swings day to day\n"
                "3. **Concentration Risk** – Over-exposure to one sector/stock\n"
                "4. **Liquidity Risk** – Difficulty redeeming in stress\n"
                "5. **Credit Risk** – Default risk in debt funds\n\n"
                "### Key Risk Metrics\n"
                "| Metric | What It Tells You |\n"
                "|--------|------------------|\n"
                "| Sharpe Ratio | Return per unit of total risk |\n"
                "| Sortino Ratio | Return per unit of downside risk |\n"
                "| Beta | Sensitivity to market moves |\n"
                "| Max Drawdown | Worst historical loss |\n"
                "| Risk Score | Overall risk rating (1–10) |\n\n"
                "💡 *Ask me about any specific metric for a deeper explanation!*"
            ),
        }

        if context and context in explanations:
            return explanations[context]

        # Default: overview of all risk metrics.
        return explanations["risk"]

    def _handle_recommendation_query(self, entities: dict[str, Any]) -> str:
        """Provide fund recommendations based on extracted context."""
        try:
            funds_df = self._ds.get_all_funds()
        except Exception:
            return "⚠️ Unable to load fund data for recommendations."

        category = entities.get("category")

        if category:
            cat_funds = funds_df[funds_df["category"] == category]
            if cat_funds.empty:
                return f"No funds found in the **{category}** category."
            top_funds = cat_funds.nlargest(5, "sharpe_ratio")
        else:
            top_funds = funds_df.nlargest(5, "sharpe_ratio")

        cat_label = f" in **{category}**" if category else ""
        lines = [
            f"## 🌟 Top Recommended Funds{cat_label}\n",
            "Ranked by **Sharpe Ratio** (best risk-adjusted returns):\n",
            "| # | Fund | Category | 1Y Return | Sharpe | Expense |",
            "|---|------|----------|-----------|--------|---------|",
        ]

        for rank, (_, fund) in enumerate(top_funds.iterrows(), 1):
            lines.append(
                f"| {rank} | {self._short_name(fund['fund_name'])} | "
                f"{fund['category']} | {fund['returns_1y']:.2f}% | "
                f"{fund['sharpe_ratio']:.2f} | {fund['expense_ratio']:.2f}% |"
            )

        lines.extend([
            "",
            "---",
            "⚠️ *This is not financial advice. Past performance does not "
            "guarantee future results. Please consult a SEBI-registered "
            "advisor before investing.*",
        ])
        return "\n".join(lines)

    def _handle_general(self, user_message: str) -> str:
        """Handle general / unclassified messages."""
        # Try AI service first.
        if self._ai is not None:
            try:
                context = self._build_ai_context()
                return self._ai.get_response(user_message, context=context)
            except Exception:
                logger.debug("AI service failed; falling back to canned response.")

        # Rule-based fallback for common questions.
        lower = user_message.lower()

        if any(w in lower for w in ["hello", "hi", "hey", "good morning", "good evening"]):
            return (
                "👋 Hello! I'm your AI Fund Advisor. How can I help you today?\n\n"
                "Here are some things I can do:\n"
                "- 📊 Analyse any mutual fund\n"
                "- ⚖️ Compare two funds side by side\n"
                "- 📁 Review portfolio allocation\n"
                "- 📐 Explain risk metrics\n"
                "- 🌟 Recommend funds\n\n"
                "Just ask away!"
            )

        if any(w in lower for w in ["thank", "thanks", "thx"]):
            return (
                "You're welcome! 😊 Feel free to ask me anything else "
                "about mutual funds, portfolios, or investment strategies."
            )

        if "sip" in lower or "systematic investment" in lower:
            return (
                "## 💰 Systematic Investment Plan (SIP)\n\n"
                "SIP lets you invest a fixed amount regularly (monthly/weekly) "
                "in a mutual fund.\n\n"
                "### Benefits\n"
                "- **Rupee Cost Averaging** – buy more units when NAV is low\n"
                "- **Discipline** – automates saving habit\n"
                "- **Compounding** – small amounts grow significantly over time\n"
                "- **Flexibility** – start with as little as ₹500/month\n\n"
                "### SIP Example (₹10,000/month)\n"
                "| Duration | Total Invested | Est. Value (12% CAGR) |\n"
                "|----------|---------------|----------------------|\n"
                "| 5 years | ₹6,00,000 | ₹8,24,861 |\n"
                "| 10 years | ₹12,00,000 | ₹23,23,391 |\n"
                "| 20 years | ₹24,00,000 | ₹99,91,479 |\n\n"
                "💡 *Start early — time in the market beats timing the market!*"
            )

        if any(w in lower for w in ["nav", "net asset value"]):
            return (
                "## 📈 Net Asset Value (NAV)\n\n"
                "NAV is the per-unit market value of a mutual fund scheme. "
                "It's calculated as:\n\n"
                "**NAV = (Total Assets − Total Liabilities) ÷ Outstanding Units**\n\n"
                "- NAV is updated daily after market close\n"
                "- A 'high' NAV does NOT mean a fund is expensive\n"
                "- Returns matter, not the absolute NAV value\n\n"
                "💡 *Two funds with NAV ₹50 and ₹500 can give the same returns!*"
            )

        if "aum" in lower or "assets under management" in lower:
            return (
                "## 🏦 Assets Under Management (AUM)\n\n"
                "AUM is the total market value of all investments managed by "
                "a fund house or scheme.\n\n"
                "- **Large AUM** (>₹10,000 Cr): Better liquidity, lower impact cost\n"
                "- **Small AUM** (<₹500 Cr): May have higher tracking error "
                "(for index funds) or concentration risk\n\n"
                "💡 *Very high AUM in mid/small-cap funds can actually be a "
                "disadvantage as deployment becomes harder.*"
            )

        # Default fallback.
        return (
            "I'm not sure I understood that. Here are some things you can ask:\n\n"
            "- **\"Tell me about HDFC Large Cap Fund\"** – Fund details\n"
            "- **\"Compare SBI Blue Chip vs ICICI Bluechip\"** – Side-by-side comparison\n"
            "- **\"How are mid-cap funds performing?\"** – Category analysis\n"
            "- **\"What is Sharpe Ratio?\"** – Risk metric explanations\n"
            "- **\"Show my portfolio\"** – Portfolio overview\n"
            "- **\"Recommend funds for me\"** – Top fund picks\n\n"
            "💡 *Try clicking one of the **Quick Questions** on the right!*"
        )

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_fund_summary(self, fund: pd.Series) -> str:
        """Format a fund Series as a readable text block with emojis."""
        name = fund.get("fund_name", "Unknown Fund")
        category = fund.get("category", "N/A")
        fund_house = fund.get("fund_house", "N/A")
        nav = fund.get("nav", 0)
        aum = fund.get("aum", 0)
        expense = fund.get("expense_ratio", 0)

        ret_1m = fund.get("returns_1m", 0)
        ret_3m = fund.get("returns_3m", 0)
        ret_6m = fund.get("returns_6m", 0)
        ret_1y = fund.get("returns_1y", 0)
        ret_3y = fund.get("returns_3y", 0)
        ret_5y = fund.get("returns_5y", 0)
        cagr = fund.get("cagr", 0)

        sharpe = fund.get("sharpe_ratio", 0)
        sortino = fund.get("sortino_ratio", 0)
        alpha = fund.get("alpha", 0)
        beta = fund.get("beta", 0)
        volatility = fund.get("volatility", 0)
        max_dd = fund.get("max_drawdown", 0)
        risk_score = fund.get("risk_score", 0)

        # Performance emoji.
        perf_emoji = "🟢" if ret_1y > 15 else ("🟡" if ret_1y > 0 else "🔴")
        risk_emoji = "🟢" if risk_score <= 4 else ("🟡" if risk_score <= 7 else "🔴")
        sharpe_emoji = "🟢" if sharpe > 1.5 else ("🟡" if sharpe > 0.8 else "🔴")

        lines = [
            f"## 🏦 {name}\n",
            f"**{fund_house}** · {category}\n",
            "### 💰 Key Details",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| NAV | ₹{nav:.2f} |",
            f"| AUM | ₹{aum:,.0f} Cr |",
            f"| Expense Ratio | {expense:.2f}% |",
            "",
            f"### {perf_emoji} Returns",
            f"| Period | Return |",
            f"|--------|--------|",
            f"| 1 Month | {ret_1m:+.2f}% |",
            f"| 3 Months | {ret_3m:+.2f}% |",
            f"| 6 Months | {ret_6m:+.2f}% |",
            f"| 1 Year | {ret_1y:+.2f}% |",
            f"| 3 Years | {ret_3y:+.2f}% |",
            f"| 5 Years | {ret_5y:+.2f}% |",
            f"| CAGR | {cagr:+.2f}% |",
            "",
            f"### {risk_emoji} Risk Profile (Score: {risk_score}/10)",
            f"| Metric | Value | Rating |",
            f"|--------|-------|--------|",
            f"| Sharpe Ratio | {sharpe:.2f} | {sharpe_emoji} |",
            f"| Sortino Ratio | {sortino:.2f} | {'🟢' if sortino > 2 else '🟡'} |",
            f"| Alpha | {alpha:+.2f} | {'🟢' if alpha > 0 else '🔴'} |",
            f"| Beta | {beta:.2f} | {'🟢' if beta < 1.1 else '🟡'} |",
            f"| Volatility | {volatility:.2f}% | {'🟢' if volatility < 15 else '🟡'} |",
            f"| Max Drawdown | {max_dd:.2f}% | {'🟢' if max_dd > -20 else '🔴'} |",
        ]

        return "\n".join(lines)

    @staticmethod
    def _short_name(fund_name: str) -> str:
        """Shorten a fund name for table display."""
        # Remove common suffixes.
        short = fund_name
        for suffix in [" - Direct Growth", " - Regular Growth"]:
            short = short.replace(suffix, "")
        if len(short) > 35:
            short = short[:32] + "…"
        return short

    @staticmethod
    def _safe_get(series: pd.Series, key: str) -> Any:
        """Safely get a value from a pandas Series."""
        try:
            val = series.get(key, None)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                return val
        except Exception:
            pass
        return None

    @staticmethod
    def _format_metric(value: Any, suffix: str) -> str:
        """Format a metric value with its suffix for table display."""
        if value is None:
            return "N/A"
        if suffix == "₹":
            if isinstance(value, (int, float)):
                return f"₹{value:,.2f}"
            return f"₹{value}"
        if suffix == "%":
            if isinstance(value, (int, float)):
                return f"{value:.2f}%"
            return f"{value}%"
        if suffix == "/10":
            return f"{value}/10"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    def _comparison_verdict(
        self,
        fund_a: pd.Series,
        fund_b: pd.Series,
        name_a: str,
        name_b: str,
    ) -> str:
        """Generate a brief verdict comparing two funds."""
        score_a = 0
        score_b = 0

        comparisons = [
            ("returns_1y", True),   # higher is better
            ("returns_3y", True),
            ("returns_5y", True),
            ("sharpe_ratio", True),
            ("sortino_ratio", True),
            ("alpha", True),
            ("expense_ratio", False),  # lower is better
            ("max_drawdown", True),    # less negative is better
        ]

        for metric, higher_is_better in comparisons:
            val_a = self._safe_get(fund_a, metric)
            val_b = self._safe_get(fund_b, metric)
            if val_a is not None and val_b is not None:
                if higher_is_better:
                    if val_a > val_b:
                        score_a += 1
                    elif val_b > val_a:
                        score_b += 1
                else:
                    if val_a < val_b:
                        score_a += 1
                    elif val_b < val_a:
                        score_b += 1

        short_a = self._short_name(name_a)
        short_b = self._short_name(name_b)

        if score_a > score_b:
            return (
                f"### 🏆 Verdict\n"
                f"**{short_a}** leads on **{score_a}** of {score_a + score_b} "
                f"key metrics. It appears to offer better risk-adjusted performance.\n\n"
                f"⚠️ *Past performance is not indicative of future results.*"
            )
        if score_b > score_a:
            return (
                f"### 🏆 Verdict\n"
                f"**{short_b}** leads on **{score_b}** of {score_a + score_b} "
                f"key metrics. It appears to offer better risk-adjusted performance.\n\n"
                f"⚠️ *Past performance is not indicative of future results.*"
            )
        return (
            f"### 🏆 Verdict\n"
            f"Both funds are closely matched across key metrics. Your choice "
            f"may depend on specific factors like fund house preference, lock-in "
            f"periods, or personal risk appetite.\n\n"
            f"⚠️ *Past performance is not indicative of future results.*"
        )

    def _build_ai_context(self) -> str:
        """Build a data-context string for the AI service."""
        try:
            funds_df = self._ds.get_all_funds()
            n_funds = len(funds_df)
            categories = self._ds.get_categories()
            return (
                f"You are an expert Indian mutual fund advisor. "
                f"You have access to data on {n_funds} mutual funds across "
                f"categories: {', '.join(categories)}. "
                f"Metrics available: NAV, AUM, returns (1M/3M/6M/1Y/3Y/5Y), "
                f"CAGR, Sharpe ratio, Sortino ratio, alpha, beta, volatility, "
                f"max drawdown, expense ratio, and risk score (1-10). "
                f"Provide concise, accurate, and helpful advice. "
                f"Always include a disclaimer about past performance."
            )
        except Exception:
            return "You are a helpful mutual fund advisor."

    # ------------------------------------------------------------------
    # Suggested questions
    # ------------------------------------------------------------------

    def get_suggested_questions(self) -> list[str]:
        """Return a curated list of suggested questions for the chat UI."""
        return [
            "Which mid-cap fund performed best this year?",
            "Compare HDFC Large Cap vs SBI Blue Chip",
            "What is Sharpe Ratio?",
            "How diversified is Client A's portfolio?",
            "Which funds have the lowest expense ratio?",
            "Explain the risk in small-cap funds",
            "Recommend top funds for wealth creation",
            "What is SIP and how does it work?",
        ]
