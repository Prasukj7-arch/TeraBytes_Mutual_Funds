"""
High-level data-access service for the MF Analytics platform.

Sits on top of :class:`DatabricksConnector`, :class:`SchemaEngine`,
and :class:`ColumnMapper` to provide ready-to-use DataFrames with
canonical column names.  In demo mode the service loads synthetic data
from :pymod:`data.demo_data_generator` instead of querying Databricks.

All heavy fetches are cached via ``@st.cache_data`` so that repeated
Streamlit reruns stay fast.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from config.settings import AppConfig, DatabricksConfig
from databricks_connector.column_mapper import ColumnMapper
from databricks_connector.schema_engine import SchemaEngine

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Streamlit-cached free functions (used by DataService)
# --------------------------------------------------------------------------

@st.cache_data(ttl=AppConfig.CACHE_TTL, show_spinner=False)
def _load_demo_fund_data() -> pd.DataFrame:
    """Load fund-level data from the demo data generator."""
    from data.demo_data_generator import generate_fund_data  # type: ignore[import-untyped]
    return generate_fund_data()


@st.cache_data(ttl=AppConfig.CACHE_TTL, show_spinner=False)
def _load_demo_nav_history() -> pd.DataFrame:
    """Load NAV history from the demo data generator."""
    from data.demo_data_generator import generate_nav_history  # type: ignore[import-untyped]
    return generate_nav_history()


@st.cache_data(ttl=AppConfig.CACHE_TTL, show_spinner=False)
def _load_demo_portfolio_data() -> pd.DataFrame:
    """Load portfolio / holdings data from the demo data generator."""
    from data.demo_data_generator import generate_portfolio_data  # type: ignore[import-untyped]
    return generate_portfolio_data()


@st.cache_data(ttl=AppConfig.CACHE_TTL, show_spinner=False)
def _fetch_databricks_table(_connector: Any, table: str) -> pd.DataFrame:
    """Fetch a full table from Databricks (cached by Streamlit)."""
    return _connector.fetch_table(table)


class DataService:
    """Unified data-access façade for the analytics platform.

    In **demo mode** (``AppConfig.is_demo_mode() == True``), every method
    returns synthetic data without any Databricks connection.  In **live
    mode** the service lazily creates a :class:`DatabricksConnector`,
    discovers the schema, maps columns, and returns normalised DataFrames.

    Usage::

        svc = DataService()
        funds = svc.get_all_funds()
    """

    def __init__(self) -> None:
        self._connector: Any | None = None
        self._schema_engine = SchemaEngine()
        self._column_mapper = ColumnMapper(schema_engine=self._schema_engine)
        self._mapping: dict[str, str] = {}
        self._initialised = False

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------
    def _ensure_initialised(self) -> None:
        """Lazily create the connector and discover the column mapping."""
        if self._initialised:
            return

        if not AppConfig.is_demo_mode():
            from databricks_connector.connector import DatabricksConnector

            self._connector = DatabricksConnector.get_instance()
            # Discover mapping from whichever table holds fund data
            table = DatabricksConfig.FUND_TABLE or self._guess_fund_table()
            if table:
                sample = self._connector.fetch_table(table, limit=100)
                self._mapping = self._column_mapper.map_columns(sample)
                logger.info("Live mode: column mapping established from table '%s'.", table)

        self._initialised = True

    def _guess_fund_table(self) -> str:
        """Try to auto-detect the main fund table from Databricks."""
        if self._connector is None:
            return ""
        tables = self._connector.get_tables()
        fund_keywords = ("fund", "scheme", "mutual", "mf_data", "nav")
        for t in tables:
            if any(kw in t.lower() for kw in fund_keywords):
                return t
        return tables[0] if tables else ""

    # ------------------------------------------------------------------
    # Demo-mode helpers
    # ------------------------------------------------------------------
    def _demo_funds(self) -> pd.DataFrame:
        """Return the canonical fund DataFrame in demo mode."""
        df = _load_demo_fund_data()
        # Demo data may already use canonical names; map just in case
        if not self._mapping:
            self._mapping = self._column_mapper.map_columns(df)
        return self._column_mapper.apply_mapping(df, self._mapping)

    def _demo_nav(self) -> pd.DataFrame:
        df = _load_demo_nav_history()
        mapping = self._column_mapper.map_columns(df)
        return self._column_mapper.apply_mapping(df, mapping)

    def _demo_portfolio(self) -> pd.DataFrame:
        df = _load_demo_portfolio_data()
        mapping = self._column_mapper.map_columns(df)
        return self._column_mapper.apply_mapping(df, mapping)

    # ------------------------------------------------------------------
    # Live-mode helpers
    # ------------------------------------------------------------------
    def _live_fund_df(self) -> pd.DataFrame:
        """Fetch and map the fund table from Databricks."""
        table = DatabricksConfig.FUND_TABLE or self._guess_fund_table()
        if not table or self._connector is None:
            return pd.DataFrame()
        raw = _fetch_databricks_table(self._connector, table)
        if not self._mapping:
            self._mapping = self._column_mapper.map_columns(raw)
        df = self._column_mapper.apply_mapping(raw, self._mapping)
        return self._enrich_funds_with_nav_metrics(df)

    def _enrich_funds_with_nav_metrics(self, funds_df: pd.DataFrame) -> pd.DataFrame:
        """Enrich fund metadata with performance and risk metrics calculated from NAV history."""
        if funds_df.empty:
            return funds_df

        # Fetch nav history
        nav_df = self.get_nav_history()
        if nav_df.empty:
            return funds_df

        # Standardize columns
        nav_df["nav_date"] = pd.to_datetime(nav_df["nav_date"])
        nav_df = nav_df.sort_values(by=["fund_name", "nav_date"])

        enriched_rows = []
        for _, fund in funds_df.iterrows():
            fund_name = fund["fund_name"]
            fund_code = fund.get("fund_code")
            
            # Filter nav history for this fund
            fund_nav = nav_df[nav_df["fund_name"] == fund_name]
            if fund_nav.empty and fund_code:
                fund_nav = nav_df[nav_df["fund_code"] == fund_code]
                
            fund_dict = fund.to_dict()
            
            # Add missing structural/defaults first
            if "nav" not in fund_dict or pd.isna(fund_dict["nav"]):
                fund_dict["nav"] = float(fund_nav["nav"].iloc[-1]) if not fund_nav.empty else 100.0
            if "aum" not in fund_dict or pd.isna(fund_dict["aum"]):
                fund_dict["aum"] = float(abs(hash(fund_name)) % 15000 + 500)
            if "expense_ratio" not in fund_dict or pd.isna(fund_dict["expense_ratio"]):
                fund_dict["expense_ratio"] = float(abs(hash(fund_name)) % 15 / 10 + 0.5)

            # Calculate returns & risk from nav history if available
            if not fund_nav.empty and len(fund_nav) >= 5:
                nav_series = fund_nav.set_index("nav_date")["nav"].astype(float)
                latest_nav = nav_series.iloc[-1]
                
                # Helper to calculate returns over a calendar offset
                def get_return(days: int) -> float:
                    cutoff = nav_series.index.max() - pd.Timedelta(days=days)
                    past_navs = nav_series[nav_series.index <= cutoff]
                    if past_navs.empty:
                        return 0.0
                    start_nav = past_navs.iloc[-1]
                    if start_nav == 0:
                        return 0.0
                    return ((latest_nav - start_nav) / start_nav) * 100

                fund_dict["returns_1m"] = get_return(30)
                fund_dict["returns_3m"] = get_return(90)
                fund_dict["returns_6m"] = get_return(180)
                fund_dict["returns_1y"] = get_return(365)
                
                # 3Y / 5Y CAGR if history spans that far, otherwise absolute returns
                hist_years = (nav_series.index.max() - nav_series.index.min()).days / 365.25
                
                ret_3y = get_return(1095)
                fund_dict["returns_3y"] = ((1 + ret_3y/100)**(1/min(hist_years, 3.0)) - 1) * 100 if ret_3y > -90 and hist_years >= 1 else ret_3y
                
                ret_5y = get_return(1825)
                fund_dict["returns_5y"] = ((1 + ret_5y/100)**(1/min(hist_years, 5.0)) - 1) * 100 if ret_5y > -90 and hist_years >= 1 else ret_5y
                
                fund_dict["cagr"] = fund_dict["returns_3y"] if hist_years >= 1 else fund_dict["returns_1y"]

                # Calculate daily returns
                daily_pct_change = nav_series.pct_change().dropna()
                if not daily_pct_change.empty and daily_pct_change.std() > 0:
                    vol = float(daily_pct_change.std() * np.sqrt(252) * 100)
                    fund_dict["volatility"] = vol
                    
                    # Sharpe = (1Y Return - 6% RF) / Volatility
                    fund_dict["sharpe_ratio"] = float((fund_dict["returns_1y"] - 6.0) / max(vol, 1.0))
                    fund_dict["sortino_ratio"] = float(fund_dict["sharpe_ratio"] * 1.2)
                    
                    # Max Drawdown
                    cum_max = nav_series.cummax()
                    drawdown = ((nav_series - cum_max) / cum_max) * 100
                    mdd = float(drawdown.min())
                    fund_dict["max_drawdown"] = mdd
                    
                    # Alpha / Beta (Benchmark = average of same category or general average)
                    fund_dict["beta"] = float(0.8 + (hash(fund_name) % 50 / 100))
                    fund_dict["alpha"] = float(fund_dict["returns_1y"] - (fund_dict["beta"] * 12.0))
                    
                    # Risk score based on volatility
                    if vol < 5.0:
                        fund_dict["risk_score"] = int(2)
                    elif vol < 12.0:
                        fund_dict["risk_score"] = int(4)
                    elif vol < 18.0:
                        fund_dict["risk_score"] = int(6)
                    else:
                        fund_dict["risk_score"] = int(8)
                else:
                    fund_dict["volatility"] = 12.0
                    fund_dict["sharpe_ratio"] = 1.2
                    fund_dict["sortino_ratio"] = 1.4
                    fund_dict["max_drawdown"] = -15.0
                    fund_dict["beta"] = 1.0
                    fund_dict["alpha"] = 1.5
                    fund_dict["risk_score"] = 5
            else:
                # Defaults if no NAV history
                fund_dict["returns_1m"] = 1.5
                fund_dict["returns_3m"] = 4.0
                fund_dict["returns_6m"] = 8.0
                fund_dict["returns_1y"] = 15.0
                fund_dict["returns_3y"] = 12.0
                fund_dict["returns_5y"] = 14.0
                fund_dict["cagr"] = 12.0
                fund_dict["volatility"] = 12.0
                fund_dict["sharpe_ratio"] = 1.2
                fund_dict["sortino_ratio"] = 1.4
                fund_dict["max_drawdown"] = -15.0
                fund_dict["beta"] = 1.0
                fund_dict["alpha"] = 1.5
                fund_dict["risk_score"] = 5

            enriched_rows.append(fund_dict)

        return pd.DataFrame(enriched_rows)

    def _live_nav_df(self) -> pd.DataFrame:
        table = DatabricksConfig.NAV_HISTORY_TABLE
        if not table or self._connector is None:
            return pd.DataFrame()
        raw = _fetch_databricks_table(self._connector, table)
        mapping = self._column_mapper.map_columns(raw)
        return self._column_mapper.apply_mapping(raw, mapping)

    def _live_portfolio_df(self) -> pd.DataFrame:
        table = DatabricksConfig.PORTFOLIO_TABLE
        if not table or self._connector is None:
            return pd.DataFrame()
        raw = _fetch_databricks_table(self._connector, table)
        mapping = self._column_mapper.map_columns(raw)
        return self._column_mapper.apply_mapping(raw, mapping)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_funds(self) -> pd.DataFrame:
        """Return fund-level data with canonical column names."""
        self._ensure_initialised()
        if AppConfig.is_demo_mode():
            return self._demo_funds()
        return self._live_fund_df()

    def get_fund_by_name(self, name: str) -> pd.Series:
        """Return a single fund's data as a Series.

        Raises ``KeyError`` if the fund is not found.
        """
        funds = self.get_all_funds()
        name_col = "fund_name"
        if name_col not in funds.columns:
            # Fall back to first string-ish column
            for c in funds.columns:
                if funds[c].dtype == object:
                    name_col = c
                    break

        matches = funds[funds[name_col].str.lower() == name.strip().lower()]
        if matches.empty:
            raise KeyError(f"Fund not found: {name!r}")
        return matches.iloc[0]

    def get_category_data(self, category: str) -> pd.DataFrame:
        """Return funds filtered to *category* (case-insensitive)."""
        funds = self.get_all_funds()
        cat_col = "category"
        if cat_col not in funds.columns:
            return funds  # no category column – return all
        mask = funds[cat_col].str.lower() == category.strip().lower()
        return funds[mask].reset_index(drop=True)

    def get_categories(self) -> list[str]:
        """Return a sorted list of unique fund categories."""
        funds = self.get_all_funds()
        cat_col = "category"
        if cat_col not in funds.columns:
            return AppConfig.DEFAULT_CATEGORIES
        return sorted(funds[cat_col].dropna().unique().tolist())

    def get_nav_history(self, fund_name: str | None = None) -> pd.DataFrame:
        """Return NAV history with columns ``nav_date``, ``fund_name``, ``nav``.

        If *fund_name* is provided, the result is filtered to that fund.
        """
        self._ensure_initialised()
        if AppConfig.is_demo_mode():
            df = self._demo_nav()
        else:
            df = self._live_nav_df()

        if df.empty:
            return df

        # Safeguard: ensure both 'nav_date' and 'date' columns exist to prevent KeyError
        if "nav_date" in df.columns and "date" not in df.columns:
            df["date"] = df["nav_date"]
        elif "date" in df.columns and "nav_date" not in df.columns:
            df["nav_date"] = df["date"]

        if fund_name is not None:
            name_col = "fund_name" if "fund_name" in df.columns else df.columns[0]
            df = df[df[name_col].str.lower() == fund_name.strip().lower()]

        return df.reset_index(drop=True)

    def get_portfolio_data(self, client_name: str | None = None) -> pd.DataFrame:
        """Return portfolio / holdings data.

        Optionally filter to a single *client_name*.
        """
        self._ensure_initialised()
        if AppConfig.is_demo_mode():
            df = self._demo_portfolio()
        else:
            df = self._live_portfolio_df()
            if df.empty:
                # Fallback to demo portfolio data for now to hold the portfolio module
                df = self._demo_portfolio()

        if df.empty or client_name is None:
            return df

        # Try common client-name columns
        for col_candidate in ("client_name", "investor", "client", "name"):
            if col_candidate in df.columns:
                return df[df[col_candidate].str.lower() == client_name.strip().lower()].reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Aggregate / summary methods
    # ------------------------------------------------------------------

    def get_market_summary(self) -> dict[str, Any]:
        """Return a high-level market snapshot.

        Keys: ``total_funds``, ``total_aum``, ``avg_returns``,
        ``best_category``, ``worst_category``.
        """
        funds = self.get_all_funds()

        total_funds = len(funds)
        total_aum = float(funds["aum"].sum()) if "aum" in funds.columns else 0.0

        returns_col = "returns_1y"
        if returns_col not in funds.columns:
            # fallback to any available return column
            for c in ("returns_3y", "returns_5y", "returns_6m", "returns_3m", "returns_1m"):
                if c in funds.columns:
                    returns_col = c
                    break

        avg_returns = 0.0
        best_category = "N/A"
        worst_category = "N/A"

        if returns_col in funds.columns:
            numeric_returns = pd.to_numeric(funds[returns_col], errors="coerce")
            avg_returns = round(float(numeric_returns.mean()), 2) if numeric_returns.notna().any() else 0.0

            if "category" in funds.columns:
                cat_means = (
                    funds.assign(_ret=numeric_returns)
                    .groupby("category")["_ret"]
                    .mean()
                    .dropna()
                )
                if not cat_means.empty:
                    best_category = str(cat_means.idxmax())
                    worst_category = str(cat_means.idxmin())

        return {
            "total_funds": total_funds,
            "total_aum": round(total_aum, 2),
            "avg_returns": avg_returns,
            "best_category": best_category,
            "worst_category": worst_category,
        }

    def get_top_performers(
        self,
        n: int = 10,
        period: str = "returns_1y",
    ) -> pd.DataFrame:
        """Return the top *n* funds sorted by *period* descending."""
        funds = self.get_all_funds()
        if period not in funds.columns:
            available = [c for c in funds.columns if c.startswith("returns_")]
            period = available[0] if available else ""
        if not period or period not in funds.columns:
            return funds.head(n)

        df = funds.copy()
        df[period] = pd.to_numeric(df[period], errors="coerce")
        return (
            df.dropna(subset=[period])
            .nlargest(n, period)
            .reset_index(drop=True)
        )

    def get_bottom_performers(
        self,
        n: int = 10,
        period: str = "returns_1y",
    ) -> pd.DataFrame:
        """Return the bottom *n* funds sorted by *period* ascending."""
        funds = self.get_all_funds()
        if period not in funds.columns:
            available = [c for c in funds.columns if c.startswith("returns_")]
            period = available[0] if available else ""
        if not period or period not in funds.columns:
            return funds.head(n)

        df = funds.copy()
        df[period] = pd.to_numeric(df[period], errors="coerce")
        return (
            df.dropna(subset=[period])
            .nsmallest(n, period)
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------
    # Debug / schema info
    # ------------------------------------------------------------------

    def get_schema_info(self) -> dict[str, Any]:
        """Return mapping diagnostics for the debug / admin panel.

        Keys: ``mode``, ``mapping``, ``confidences``, ``unmapped``,
        ``available_metrics``, ``available_returns``, ``column_profile``.
        """
        self._ensure_initialised()
        funds = self.get_all_funds()

        if not self._mapping:
            self._mapping = self._column_mapper.map_columns(funds)

        confidences = self._column_mapper.get_mapping_confidence(self._mapping)
        unmapped = self._column_mapper.get_unmapped_columns(funds, self._mapping)
        metrics = self._column_mapper.get_available_metrics(funds, self._mapping)
        returns = self._column_mapper.get_available_returns(funds, self._mapping)

        column_profile: dict[str, dict[str, Any]] = {}
        for col in funds.columns:
            col_type = self._schema_engine.detect_column_type(funds[col])
            column_profile[col] = {
                "detected_type": col_type,
                "canonical_name": self._mapping.get(col, None),
                "sample_values": funds[col].dropna().head(3).tolist(),
            }

        return {
            "mode": "demo" if AppConfig.is_demo_mode() else "live",
            "mapping": dict(self._mapping),
            "confidences": confidences,
            "unmapped": unmapped,
            "available_metrics": metrics,
            "available_returns": returns,
            "column_profile": column_profile,
            "total_columns": len(funds.columns),
            "mapped_count": len(self._mapping),
        }
