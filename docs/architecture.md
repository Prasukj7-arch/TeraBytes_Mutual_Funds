# Architecture

## Flow

```
mfapi.in / AMFI (source)
        │
        ▼
   S3 (raw zone)              <- Person A
        │
        ▼
   Snowflake                  <- Person A
   ├─ FUND_MASTER
   ├─ NAV_HISTORY
   └─ FUND_EVENTS (dip/hike, computed via SQL window functions)
        │
        ▼
   FastAPI service             <- Person B
   ├─ /funds
   ├─ /funds/{code}/history
   ├─ /funds/{code}/events
   ├─ /portfolio
   └─ /funds/{code}/forecast, /portfolio/{id}/recommendations
        │              ▲
        ▼              │
   Demo UI       Forecasting + Recommendation logic   <- Person C
   (charts)      (writes to FORECASTS table, reads NAV_HISTORY)
```

## Notes

- Snowflake is the primary warehouse for this project. Databricks/PySpark is
  an optional stretch goal only if the team wants to explicitly demonstrate
  distributed processing — not required for a handful of funds.
- User portfolios can live in the same Snowflake schema as everything else
  to avoid adding a second database for a 3-day build, unless the team
  decides a separate Postgres/DynamoDB table is cleaner.
- Airflow DAG (daily refresh) is optional — only build if Day 1-2 finish
  ahead of schedule.

(Expand this doc with an actual diagram image or more detail as the
architecture solidifies during Day 1.)
