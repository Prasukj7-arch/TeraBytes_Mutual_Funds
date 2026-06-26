"""
AI service for generating recommendations, portfolio analysis, and chat answers.
Uses LangChain and OpenAI when available, falling back to a comprehensive rule-based system if offline.
"""

import logging
from typing import Any
from config.settings import OpenAIConfig

logger = logging.getLogger(__name__)

class AIService:
    """Service to interact with LLMs via LangChain or fallback to rules."""

    def __init__(self) -> None:
        self.ai_available = False
        self.llm = None

        if OpenAIConfig.is_configured():
            try:
                if OpenAIConfig.use_azure():
                    from langchain_openai import AzureChatOpenAI
                    self.llm = AzureChatOpenAI(
                        azure_endpoint=OpenAIConfig.AZURE_ENDPOINT,
                        openai_api_key=OpenAIConfig.AZURE_API_KEY,
                        azure_deployment=OpenAIConfig.AZURE_DEPLOYMENT,
                        api_version=OpenAIConfig.AZURE_API_VERSION,
                        temperature=0.7,
                    )
                else:
                    from langchain_openai import ChatOpenAI
                    self.llm = ChatOpenAI(
                        openai_api_key=OpenAIConfig.API_KEY,
                        model_name=OpenAIConfig.MODEL,
                        temperature=0.7,
                    )
                self.ai_available = True
            except Exception as e:
                logger.warning("Failed to initialize LangChain LLM: %s. Using rule-based fallback.", e)

    def generate_recommendation_explanation(self, fund_data: dict, user_profile: dict) -> str:
        """Generate a personalized explanation for why a fund was recommended."""
        if self.ai_available and self.llm:
            try:
                from langchain_core.prompts import ChatPromptTemplate
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a professional financial advisor. Explain in 2-3 bullet points why this mutual fund is suitable for the client's profile."),
                    ("user", "User Profile: {profile}\nFund Details: {fund_details}")
                ])
                chain = prompt | self.llm
                response = chain.invoke({
                    "profile": str(user_profile),
                    "fund_details": str(fund_data)
                })
                return response.content
            except Exception as e:
                logger.error("AI recommendation explanation failed: %s", e)

        # Rule-based fallback
        reasons = []
        cagr = fund_data.get("cagr", fund_data.get("returns_1y", 0))
        sharpe = fund_data.get("sharpe_ratio", 0)
        risk = fund_data.get("risk_score", 5)
        category = fund_data.get("category", "")

        reasons.append(f"Consistent returns with an expected return profile (5Y CAGR/1Y Return) of {cagr:.1f}%.")
        if sharpe > 1.5:
            reasons.append(f"Excellent risk-adjusted returns (Sharpe Ratio of {sharpe:.2f}), indicating efficient returns per unit of volatility.")
        elif sharpe > 1.0:
            reasons.append(f"Good Sharpe Ratio of {sharpe:.2f}, representing solid risk-adjusted metrics.")

        if risk <= 3:
            reasons.append("Low risk classification, suitable for preserving capital and stabilizing the portfolio.")
        elif risk >= 7:
            reasons.append("Aggressive growth asset class targeting higher potential returns over a longer investment horizon.")
        else:
            reasons.append("Moderate risk Profile, offering a balanced mix of growth and volatility control.")

        if "ELSS" in category:
            reasons.append("Provides tax saving benefits under Section 80C, making it optimal for tax-planning goals.")
        elif "Debt" in category:
            reasons.append("Debt underlying assets offer defensive allocation to shield against equity market downturns.")

        return "\n".join([f"- {r}" for r in reasons])

    def analyze_portfolio(self, portfolio_df: Any, funds_df: Any) -> dict:
        """Analyze a client's portfolio and generate strengths, weaknesses, recommendations, and health score."""
        # Calculate key statistics for rules / prompts
        total_inv = portfolio_df["investment_amount"].sum()
        curr_val = portfolio_df["current_value"].sum()
        total_ret_pct = ((curr_val - total_inv) / total_inv * 100) if total_inv > 0 else 0
        
        # Categorized allocation
        cat_alloc = portfolio_df.groupby("category")["allocation_pct"].sum().to_dict()
        
        # Rule-based calculation of metrics
        strengths = []
        weaknesses = []
        recommendations = []
        health_score = 75  # default

        # Identify simple portfolio stats
        num_funds = len(portfolio_df)
        debt_pct = cat_alloc.get("Debt", 0)
        large_pct = cat_alloc.get("Large Cap", 0)
        small_pct = cat_alloc.get("Small Cap", 0)
        mid_pct = cat_alloc.get("Mid Cap", 0)
        elss_pct = cat_alloc.get("ELSS", 0)
        
        # Evaluate diversification
        if num_funds < 4:
            weaknesses.append("High concentration risk: Portfolio contains very few funds, which increases idiosyncratic risk.")
            recommendations.append("Consider adding 2-3 more mutual funds in different categories to spread out risk.")
            health_score -= 15
        elif num_funds > 12:
            weaknesses.append("Over-diversification: Portfolio holds too many funds, which can dilute returns and make monitoring complex.")
            recommendations.append("Consolidate overlapping funds (e.g., duplicate Large Cap or Index funds) to streamline tracking.")
            health_score -= 10
        else:
            strengths.append(f"Optimum diversification with {num_funds} funds across multiple categories, balancing tracking simplicity and risk.")

        # Asset/Category-specific logic
        if debt_pct < 10 and (large_pct + small_pct + mid_pct) > 80:
            weaknesses.append("Insufficient debt allocation: High equity concentration makes the portfolio highly vulnerable to market corrections.")
            recommendations.append("Allocate 10-15% of your corpus to Short Duration or Liquid Debt Funds to provide liquidity and a safety net.")
            health_score -= 10
        elif debt_pct > 40:
            strengths.append(f"Strong conservative base with {debt_pct:.1f}% debt allocation providing robust downside protection.")
            if total_ret_pct < 8:
                weaknesses.append("Conservative drag: Large allocation to debt limits capital appreciation potential over the long term.")
                recommendations.append("If investment horizon is >5 years, consider reallocating 10-20% from debt to Flexi Cap or Large Cap equity funds.")

        if large_pct > 30:
            strengths.append(f"Solid large-cap/index core ({large_pct:.1f}%) providing long-term stability and high-quality business exposure.")

        if small_pct + mid_pct > 50:
            weaknesses.append("High volatility profile: Over 50% allocation to Mid and Small Cap funds implies substantial downside potential during market drawdowns.")
            recommendations.append("Trim Small/Mid Cap exposure and reallocate to a Flexi Cap or Multi Cap fund to allow a fund manager to handle dynamic capping.")
            health_score -= 15
        elif small_pct > 0:
            strengths.append(f"Aggressive growth boosters included via Small Cap funds ({small_pct:.1f}%) to outperform benchmarks over the long term.")

        if health_score < 30:
            health_score = 30
        if health_score > 98:
            health_score = 98

        if self.ai_available and self.llm:
            try:
                from langchain_core.prompts import ChatPromptTemplate
                import json
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are an expert mutual fund portfolio advisor. Analyze the client's portfolio and provide feedback in JSON format containing keys: 'strengths' (list of strings), 'weaknesses' (list of strings), 'recommendations' (list of strings), and 'health_score' (integer 0-100). Do not include any markdown markup other than the JSON object."),
                    ("user", "Portfolio Data: {portfolio}\nMarket Data Context: {market_context}")
                ])
                chain = prompt | self.llm
                response = chain.invoke({
                    "portfolio": portfolio_df.to_json(orient="records"),
                    "market_context": f"Total Investment: {total_inv}, Current Value: {curr_val}, Categories: {list(cat_alloc.keys())}"
                })
                
                # Try parsing the JSON
                clean_content = response.content.strip()
                if "```json" in clean_content:
                    clean_content = clean_content.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_content:
                    clean_content = clean_content.split("```")[1].split("```")[0].strip()
                res = json.loads(clean_content)
                return {
                    "strengths": res.get("strengths", strengths),
                    "weaknesses": res.get("weaknesses", weaknesses),
                    "recommendations": res.get("recommendations", recommendations),
                    "health_score": int(res.get("health_score", health_score))
                }
            except Exception as e:
                logger.error("AI portfolio analysis failed, utilizing rule-based backup: %s", e)

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "health_score": int(health_score)
        }
