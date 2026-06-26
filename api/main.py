"""
Mutual Fund Insight & Forecasting Platform — API entrypoint.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Then visit:
    http://127.0.0.1:8000/docs   -> interactive Swagger UI

This is a Day-1 skeleton. Person B fills in app/routes/, app/models/, and
app/services/ as the Snowflake schema (Person A) and contract
(docs/api-contract.md) firm up. See docs/api-contract.md for the agreed
request/response shapes before building each route.
"""

import sys
from pathlib import Path

# Prevent root app.py from shadowing local app/ package
_ROOT_DIR = str(Path(__file__).resolve().parent.parent)
sys.path = [p for p in sys.path if p != _ROOT_DIR]

_API_DIR = str(Path(__file__).resolve().parent)
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Mutual Fund Insight & Forecasting API",
    description=(
        "Fund history, dip/hike detection, user portfolios, recommendations, "
        "and NAV forecasts. Educational project — not financial advice."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Database Initialization & Routers
# ---------------------------------------------------------------------------

from app.services.db import init_db
try:
    init_db()
except Exception as e:
    print(f"Error initializing DB: {e}")

from app.routes import portfolio
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])



@app.get("/")
def root():
    return {
        "message": "Mutual Fund Insight & Forecasting API is running.",
        "endpoints_planned": {
            "/funds": "List tracked funds",
            "/funds/{scheme_code}/history": "NAV history for one fund",
            "/funds/{scheme_code}/events": "Detected dip/hike events",
            "/funds/{scheme_code}/forecast": "NAV forecast",
            "/portfolio": "Add a holding (POST)",
            "/portfolio/{user_id}": "Get a user's holdings",
            "/portfolio/{user_id}/recommendations": "Fund recommendations",
        },
        "contract": "See docs/api-contract.md for exact request/response shapes.",
    }
