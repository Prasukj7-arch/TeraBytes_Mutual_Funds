# Data Dictionary

To be filled in by Person A on Day 1 as the Snowflake schema is created.
Keep this updated as the source of truth for table/column meanings — the
API and forecasting layers should refer here, not guess.

## FUND_MASTER

| Column | Type | Description |
|---|---|---|
| scheme_code | VARCHAR | Unique AMFI scheme code (primary key) |
| scheme_name | VARCHAR | Full scheme name |
| amc_name | VARCHAR | Asset Management Company |
| category | VARCHAR | e.g. "Equity - Large Cap", "Debt - Liquid" |

## NAV_HISTORY

| Column | Type | Description |
|---|---|---|
| scheme_code | VARCHAR | FK → FUND_MASTER |
| nav_date | DATE | NAV date (no entries on weekends/market holidays) |
| nav | FLOAT | Net Asset Value on that date |

## FUND_EVENTS

| Column | Type | Description |
|---|---|---|
| scheme_code | VARCHAR | FK → FUND_MASTER |
| event_type | VARCHAR | `dip` or `hike` |
| start_date | DATE | Start of the drawdown/rally |
| end_date | DATE | End of the drawdown/rally |
| magnitude_pct | FLOAT | % change, negative for dips, positive for hikes |

> Threshold definition (fill in once agreed): a "dip" is defined as a
> drawdown of ___% or more from a trailing ___-day peak.

## USER_PORTFOLIO

| Column | Type | Description |
|---|---|---|
| user_id | VARCHAR | User identifier |
| scheme_code | VARCHAR | FK → FUND_MASTER |
| units | FLOAT | Units held |
| purchase_date | DATE | Date of purchase |
| purchase_nav | FLOAT | NAV at time of purchase |

## FORECASTS

| Column | Type | Description |
|---|---|---|
| scheme_code | VARCHAR | FK → FUND_MASTER |
| forecast_date | DATE | Date being predicted |
| predicted_nav | FLOAT | Model output |
| model_name | VARCHAR | e.g. `moving_average_trend`, `arima` |
| generated_at | TIMESTAMP | When this forecast run was generated |
