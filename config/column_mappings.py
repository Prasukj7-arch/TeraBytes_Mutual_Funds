"""
Semantic column mapping definitions.

Maps canonical column names to lists of known aliases and keywords.
The ColumnMapper uses these to fuzzy-match columns from any Databricks schema.

Structure:
    CANONICAL_NAME: {
        "aliases": [exact or near-exact matches],
        "keywords": [substring/keyword matches],
        "type": expected data type ("numeric", "string", "date"),
        "required": whether this column is critical,
    }
"""

# --------------------------------------------------------------------------
# Canonical Column Definitions
# --------------------------------------------------------------------------

COLUMN_DEFINITIONS: dict[str, dict] = {
    # --- Identifiers ---
    "fund_name": {
        "aliases": [
            "fund_name", "scheme_name", "mutual_fund_name", "mf_name",
            "fund", "scheme", "name", "fund_title", "scheme_title",
        ],
        "keywords": ["fund", "scheme", "name", "title"],
        "type": "string",
        "required": True,
        "group": "identifier",
    },
    "fund_code": {
        "aliases": [
            "fund_code", "scheme_code", "amfi_code", "isin", "fund_id",
            "scheme_id", "mf_code", "code",
        ],
        "keywords": ["code", "isin", "id", "amfi"],
        "type": "string",
        "required": False,
        "group": "identifier",
    },
    "fund_house": {
        "aliases": [
            "fund_house", "amc", "amc_name", "fund_company", "asset_management_company",
            "company", "house", "manager",
        ],
        "keywords": ["amc", "house", "company", "manager", "asset_management"],
        "type": "string",
        "required": False,
        "group": "identifier",
    },
    "category": {
        "aliases": [
            "category", "mf_category", "fund_category", "scheme_category",
            "fund_type", "scheme_type", "type", "asset_class", "sub_category",
        ],
        "keywords": ["category", "type", "class", "cap"],
        "type": "string",
        "required": True,
        "group": "identifier",
    },

    # --- NAV & Pricing ---
    "nav": {
        "aliases": [
            "nav", "current_nav", "latest_nav", "net_asset_value",
            "price", "unit_price", "current_price",
        ],
        "keywords": ["nav", "net_asset", "price", "unit_value"],
        "type": "numeric",
        "required": True,
        "group": "pricing",
    },
    "nav_date": {
        "aliases": [
            "nav_date", "date", "as_of_date", "price_date", "valuation_date",
            "report_date", "data_date",
        ],
        "keywords": ["date", "as_of", "valuation"],
        "type": "date",
        "required": False,
        "group": "pricing",
    },

    # --- AUM ---
    "aum": {
        "aliases": [
            "aum", "aum_cr", "aum_crore", "total_aum", "assets_under_management",
            "fund_size", "net_assets", "corpus", "fund_aum",
        ],
        "keywords": ["aum", "asset", "corpus", "fund_size", "net_asset"],
        "type": "numeric",
        "required": False,
        "group": "size",
    },

    # --- Returns ---
    "returns_1m": {
        "aliases": [
            "returns_1m", "return_1m", "one_month_return", "1m_return",
            "monthly_return", "return_1_month", "1_month_return",
        ],
        "keywords": ["1m", "one_month", "monthly", "1_month"],
        "type": "numeric",
        "required": False,
        "group": "returns",
    },
    "returns_3m": {
        "aliases": [
            "returns_3m", "return_3m", "three_month_return", "3m_return",
            "return_3_month", "3_month_return", "quarterly_return",
        ],
        "keywords": ["3m", "three_month", "3_month", "quarterly"],
        "type": "numeric",
        "required": False,
        "group": "returns",
    },
    "returns_6m": {
        "aliases": [
            "returns_6m", "return_6m", "six_month_return", "6m_return",
            "return_6_month", "6_month_return", "half_yearly_return",
        ],
        "keywords": ["6m", "six_month", "6_month", "half_year"],
        "type": "numeric",
        "required": False,
        "group": "returns",
    },
    "returns_1y": {
        "aliases": [
            "returns_1y", "return_1y", "one_year_return", "1y_return",
            "annual_return", "yearly_return", "return_1_year", "1_year_return",
        ],
        "keywords": ["1y", "one_year", "1_year", "annual", "yearly"],
        "type": "numeric",
        "required": False,
        "group": "returns",
    },
    "returns_3y": {
        "aliases": [
            "returns_3y", "return_3y", "three_year_return", "3y_return",
            "return_3_year", "3_year_return",
        ],
        "keywords": ["3y", "three_year", "3_year"],
        "type": "numeric",
        "required": False,
        "group": "returns",
    },
    "returns_5y": {
        "aliases": [
            "returns_5y", "return_5y", "five_year_return", "5y_return",
            "return_5_year", "5_year_return",
        ],
        "keywords": ["5y", "five_year", "5_year"],
        "type": "numeric",
        "required": False,
        "group": "returns",
    },

    # --- Risk Metrics ---
    "expense_ratio": {
        "aliases": [
            "expense_ratio", "ter", "total_expense_ratio", "management_fee",
            "expense", "fee_ratio",
        ],
        "keywords": ["expense", "ter", "fee", "cost"],
        "type": "numeric",
        "required": False,
        "group": "risk",
    },
    "sharpe_ratio": {
        "aliases": [
            "sharpe_ratio", "sharpe", "risk_adjusted_return",
        ],
        "keywords": ["sharpe"],
        "type": "numeric",
        "required": False,
        "group": "risk",
    },
    "alpha": {
        "aliases": ["alpha", "jensen_alpha", "fund_alpha"],
        "keywords": ["alpha"],
        "type": "numeric",
        "required": False,
        "group": "risk",
    },
    "beta": {
        "aliases": ["beta", "fund_beta", "market_beta"],
        "keywords": ["beta"],
        "type": "numeric",
        "required": False,
        "group": "risk",
    },
    "volatility": {
        "aliases": [
            "volatility", "std_dev", "standard_deviation", "vol",
            "annualized_volatility", "risk",
        ],
        "keywords": ["volatility", "std_dev", "std", "deviation", "vol"],
        "type": "numeric",
        "required": False,
        "group": "risk",
    },
    "max_drawdown": {
        "aliases": [
            "max_drawdown", "drawdown", "maximum_drawdown", "mdd",
            "worst_drawdown",
        ],
        "keywords": ["drawdown", "mdd"],
        "type": "numeric",
        "required": False,
        "group": "risk",
    },
    "risk_score": {
        "aliases": [
            "risk_score", "risk_rating", "risk_level", "risk_grade",
            "riskometer", "risk_category",
        ],
        "keywords": ["risk_score", "risk_rating", "riskometer", "risk_grade"],
        "type": "numeric",
        "required": False,
        "group": "risk",
    },
    "cagr": {
        "aliases": [
            "cagr", "compound_annual_growth_rate", "annualized_return",
            "cagr_return", "compounded_return",
        ],
        "keywords": ["cagr", "compound", "annualized"],
        "type": "numeric",
        "required": False,
        "group": "returns",
    },
    "sortino_ratio": {
        "aliases": ["sortino_ratio", "sortino"],
        "keywords": ["sortino"],
        "type": "numeric",
        "required": False,
        "group": "risk",
    },
}


# --------------------------------------------------------------------------
# Category Classification Keywords
# --------------------------------------------------------------------------

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Large Cap": ["large cap", "largecap", "large-cap", "bluechip", "blue chip", "nifty 50", "sensex"],
    "Mid Cap": ["mid cap", "midcap", "mid-cap", "nifty midcap"],
    "Small Cap": ["small cap", "smallcap", "small-cap", "nifty smallcap"],
    "Flexi Cap": ["flexi cap", "flexicap", "flexi-cap", "flexible"],
    "Multi Cap": ["multi cap", "multicap", "multi-cap", "diversified"],
    "ELSS": ["elss", "tax saving", "tax saver", "equity linked", "80c"],
    "Hybrid": ["hybrid", "balanced", "aggressive hybrid", "conservative hybrid", "equity savings"],
    "Debt": ["debt", "bond", "fixed income", "liquid", "money market", "gilt", "corporate bond", "credit risk"],
    "Index": ["index", "passive", "etf", "nifty index", "sensex index", "tracker"],
}


# --------------------------------------------------------------------------
# Column Groups for UI display
# --------------------------------------------------------------------------

COLUMN_GROUPS: dict[str, list[str]] = {
    "Identifiers": ["fund_name", "fund_code", "fund_house", "category"],
    "Pricing": ["nav", "nav_date"],
    "Size": ["aum"],
    "Returns": ["returns_1m", "returns_3m", "returns_6m", "returns_1y", "returns_3y", "returns_5y", "cagr"],
    "Risk Metrics": ["expense_ratio", "sharpe_ratio", "alpha", "beta", "volatility", "max_drawdown", "risk_score", "sortino_ratio"],
}
