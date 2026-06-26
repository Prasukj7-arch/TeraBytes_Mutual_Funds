# Wealth Analytics Pro: Combined Stocks & MFs

A comprehensive analytics platform for tracking, analyzing, and forecasting both **Mutual Funds** and **Stocks**. This project features a unified database architecture, an interactive Streamlit dashboard, and a FastAPI backend to manage user portfolios and provide actionable insights.

> Educational / informational project only — nothing here is financial advice.

## Key Features

- **Consolidated Dashboard**: View your overall net worth, combined asset performance (Stocks + Mutual Funds), and profit/loss metrics.
- **Stock Watchlist**: Track live stock prices, historic performance, and key metrics via Yahoo Finance (`yfinance`).
- **Stock Brand Analytics**: Analyze brand sentiment and signals using natural language processing (`vaderSentiment` and `tweepy`).
- **Mutual Fund Analytics**: Insights into fund performance, market overviews, and category analytics.
- **AI Chat Advisor**: Ask natural language questions about your portfolio and receive AI-driven recommendations.
- **Unified Portfolio Engine**: A streamlined backend (`services/db.py`) handling both stocks and mutual funds interchangeably using SQLite/PostgreSQL.

## Repo Structure

```text
wealth-analytics-pro/
├── api/                     # FastAPI backend
│   ├── app/
│   │   ├── routes/          # API route handlers (e.g. portfolio.py)
│   │   └── models/          # Pydantic schemas / DB models
│   ├── requirements.txt     # API-specific dependencies
│   └── main.py              # FastAPI entrypoint
│
├── modules/                 # Streamlit UI Components
│   ├── ai_recommendation/
│   ├── category_analysis/
│   ├── chatbot/
│   ├── consolidated_dashboard/
│   ├── fund_analysis/
│   ├── market_overview/
│   ├── portfolio_analysis/
│   ├── stock_brand_analytics/
│   ├── stock_watchlist/
│   └── ups_downs/
│
├── services/                # Unified Business Logic & DB
│   ├── stock_analytics/     # Ingestion, sentiment, and signal engines
│   ├── ai_service.py        # LLM integration logic
│   ├── chat_service.py      # Chatbot conversation logic
│   ├── db.py                # Database connection and schema initialization
│   ├── portfolio_engine.py  # Portfolio calculations
│   └── recommendation_engine.py
│
├── docs/                    # Documentation
│   ├── api-contract.md      # API request/response shapes
│   ├── architecture.md      # System diagram + notes
│   └── data-dictionary.md   # Table/column definitions
│
├── app.py                   # Main Streamlit Entrypoint
├── requirements.txt         # Core dependencies (Streamlit, UI, Data)
├── test_api_endpoints.py    # Test suite for FastAPI routes
├── test_combined_db.py      # Test suite for the unified database layer
└── README.md
```

## Getting Started

### 1. Clone & Setup Virtual Environment
```bash
git clone <your-repo-url>
cd TeraBytes_Mutual_Funds

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
There are two requirement files—one for the core Streamlit app and data services, and one for the FastAPI endpoints.
```bash
# Core dependencies
pip install -r requirements.txt

# API dependencies
pip install -r api/requirements.txt
```

### 3. Run the Streamlit Dashboard
```bash
streamlit run app.py
```
*Navigate to `http://localhost:8501` to view the UI.*

### 4. Run the FastAPI Service
```bash
cd api
uvicorn main:app --reload --port 8000
```
*Navigate to `http://localhost:8000/docs` to view the interactive Swagger UI.*

## Environment Variables

You can supply credentials and configurations using a `.env` file in the root directory (which is ignored by Git).

Example keys you might need:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (if using PostgreSQL instead of the local SQLite fallback)
- API keys for LLMs or external data services.

## Testing

To ensure the local database and logic are functioning correctly, you can run the unified database tests:
```bash
python test_combined_db.py
```

To run API endpoint tests:
```bash
pytest test_api_endpoints.py
```
