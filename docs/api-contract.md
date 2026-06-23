# API Contract (Draft — Day 1)

This is the agreed shape of data flowing between Data Engineering → API → 
Analytics/Forecasting. **Fill in/confirm with the whole team before anyone
builds against it. Once agreed, don't change field names without telling
everyone** — this is the file the most people depend on.

Status: 🟡 DRAFT — fill in checkboxes as each endpoint is confirmed by Person B.

---

## 1. Fund Catalog

### `GET /funds`
Returns the list of tracked funds.

```json
[
  {
    "scheme_code": "119598",
    "scheme_name": "HDFC Flexi Cap Fund - Growth",
    "amc_name": "HDFC Mutual Fund",
    "category": "Equity - Flexi Cap"
  }
]
```
- [ ] Confirmed by Person A (matches FUND_MASTER table)
- [ ] Confirmed by Person B (matches route implementation)

---

## 2. NAV History

### `GET /funds/{scheme_code}/history`
Returns the full (or date-ranged) NAV time series for one fund.

**Optional query params:** `from_date`, `to_date` (format `YYYY-MM-DD`)

```json
{
  "scheme_code": "119598",
  "scheme_name": "HDFC Flexi Cap Fund - Growth",
  "history": [
    { "date": "2024-01-02", "nav": 145.32 },
    { "date": "2024-01-03", "nav": 146.01 }
  ]
}
```
- [ ] Confirmed by Person A (matches NAV_HISTORY table)
- [ ] Confirmed by Person B

---

## 3. Dip/Hike Events

### `GET /funds/{scheme_code}/events`
Returns detected dips and hikes for one fund.

```json
{
  "scheme_code": "119598",
  "events": [
    {
      "event_type": "dip",
      "start_date": "2020-02-20",
      "end_date": "2020-03-23",
      "magnitude_pct": -34.7
    },
    {
      "event_type": "hike",
      "start_date": "2020-03-23",
      "end_date": "2020-09-01",
      "magnitude_pct": 58.2
    }
  ]
}
```
- [ ] Confirmed dip/hike threshold definition with Person A
  (e.g. "dip = drawdown of X% or more from a trailing peak")
- [ ] Confirmed by Person B

---

## 4. User Portfolio

### `POST /portfolio`
Add a holding to a user's portfolio.

**Request:**
```json
{
  "user_id": "user_001",
  "scheme_code": "119598",
  "units": 120.5,
  "purchase_date": "2023-06-15",
  "purchase_nav": 132.10
}
```
**Response:** `201 Created` + the created record (or an error shape — see below)

### `GET /portfolio/{user_id}`
Returns all holdings for a user, ideally with current value computed.

```json
{
  "user_id": "user_001",
  "holdings": [
    {
      "scheme_code": "119598",
      "scheme_name": "HDFC Flexi Cap Fund - Growth",
      "units": 120.5,
      "purchase_date": "2023-06-15",
      "purchase_nav": 132.10,
      "current_nav": 158.40,
      "current_value": 19087.20,
      "gain_pct": 19.9
    }
  ]
}
```
- [ ] Confirmed table design with Person A (USER_PORTFOLIO table)
- [ ] Confirmed by Person B

---

## 5. Recommendations

### `GET /portfolio/{user_id}/recommendations`
For each held fund, suggest comparable/better funds in the same category.

```json
{
  "user_id": "user_001",
  "recommendations": [
    {
      "held_scheme_code": "119598",
      "held_scheme_name": "HDFC Flexi Cap Fund - Growth",
      "suggested_scheme_code": "120503",
      "suggested_scheme_name": "Parag Parikh Flexi Cap Fund - Growth",
      "reason": "Higher trailing 3yr return in the same category",
      "trailing_3yr_return_pct": 24.1
    }
  ]
}
```
- [ ] Confirmed scoring logic with Person C
- [ ] Confirmed by Person B
- [ ] Disclaimer text agreed (must state this is informational, not financial advice)

---

## 6. Forecast

### `GET /funds/{scheme_code}/forecast`
Returns a short-horizon NAV projection.

```json
{
  "scheme_code": "119598",
  "model": "moving_average_trend",
  "generated_at": "2026-06-23",
  "forecast": [
    { "date": "2026-06-24", "predicted_nav": 159.10 },
    { "date": "2026-06-25", "predicted_nav": 159.35 }
  ],
  "disclaimer": "Illustrative projection only, not investment advice."
}
```
- [ ] Confirmed model choice with Person C (moving average / ARIMA)
- [ ] Confirmed by Person B

---

## Error Shape (applies to all endpoints)

```json
{
  "detail": "Scheme code 999999 not found."
}
```
Standard FastAPI `HTTPException` shape — keep this consistent across every
route so the frontend/demo layer only needs to handle one error format.
