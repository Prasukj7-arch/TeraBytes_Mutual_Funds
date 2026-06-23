"""
Application settings and configuration.

Loads from environment variables / .env file.
Provides typed access to all configuration values.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class DatabricksConfig:
    """Databricks connection settings."""

    HOST: str = os.getenv("DATABRICKS_HOST", "")
    TOKEN: str = os.getenv("DATABRICKS_TOKEN", "")
    HTTP_PATH: str = os.getenv("DATABRICKS_HTTP_PATH", "")
    CATALOG: str = os.getenv("DATABRICKS_CATALOG", "")
    SCHEMA: str = os.getenv("DATABRICKS_SCHEMA", "")

    # Optional explicit table names (auto-discovered if empty)
    FUND_TABLE: str = os.getenv("DATABRICKS_FUND_TABLE", "")
    NAV_HISTORY_TABLE: str = os.getenv("DATABRICKS_NAV_HISTORY_TABLE", "")
    PORTFOLIO_TABLE: str = os.getenv("DATABRICKS_PORTFOLIO_TABLE", "")

    @classmethod
    def is_configured(cls) -> bool:
        """Check if Databricks credentials are provided."""
        return bool(cls.HOST and cls.TOKEN and cls.HTTP_PATH)


class OpenAIConfig:
    """OpenAI / Azure OpenAI settings."""

    API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Azure OpenAI (alternative)
    AZURE_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    AZURE_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    @classmethod
    def is_configured(cls) -> bool:
        """Check if any AI provider is configured."""
        return bool(cls.API_KEY or cls.AZURE_API_KEY)

    @classmethod
    def use_azure(cls) -> bool:
        """Check if Azure OpenAI should be used."""
        return bool(cls.AZURE_API_KEY and cls.AZURE_ENDPOINT)


class AppConfig:
    """Application-level settings."""

    MODE: str = os.getenv("APP_MODE", "demo")  # "demo" or "live"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    APP_TITLE: str = "MF Analytics Pro"
    APP_ICON: str = "📊"
    APP_DESCRIPTION: str = "Mutual Fund Analytics & Portfolio Recommendation Platform"

    # Supported fund categories (auto-discovered from data, these are defaults)
    DEFAULT_CATEGORIES: list[str] = [
        "Large Cap",
        "Mid Cap",
        "Small Cap",
        "Flexi Cap",
        "Multi Cap",
        "ELSS",
        "Hybrid",
        "Debt",
        "Index",
    ]

    # Risk levels
    RISK_LEVELS: list[str] = ["Low", "Medium", "High"]

    # Investment goals
    GOALS: list[str] = [
        "Wealth Creation",
        "Retirement",
        "Tax Saving",
        "Child Education",
        "House Purchase",
        "Emergency Fund",
    ]

    @classmethod
    def is_demo_mode(cls) -> bool:
        """Check if running in demo mode."""
        return cls.MODE.lower() == "demo"
