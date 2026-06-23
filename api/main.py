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
# Routers
# ---------------------------------------------------------------------------
# As routes are built (see docs/api-contract.md), wire them up here, e.g.:
#
# from app.routes import funds, portfolio
# app.include_router(funds.router, prefix="/funds", tags=["funds"])
# app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])


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
