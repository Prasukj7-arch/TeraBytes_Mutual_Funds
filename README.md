# Mutual Fund Insight & Forecasting Platform

A 3-day mini project that ingests ~20 years of historical NAV data for Indian
mutual funds, detects significant dips/hikes, stores user portfolios,
recommends comparable funds, and produces a lightweight NAV forecast.

> Educational / informational project only — nothing here is financial advice.

## Team & Ownership

| Owner | Folder | Responsibility |
|---|---|---|
| **Person A** | `data-engineering/` | Ingest NAV history (mfapi.in/AMFI) → S3 → Snowflake. Dip/hike detection SQL. Data quality checks. |
| **Person B** | `api/` | FastAPI service exposing fund history, dip/hike events, and user portfolio endpoints. |
| **Person C** | `analytics-forecasting/` | Recommendation logic, NAV forecasting model, Airflow DAG, demo assets. |

See [`docs/api-contract.md`](docs/api-contract.md) for the agreed request/response
shapes all three layers build against — **agree this on Day 1 and avoid changing
field names afterward without telling everyone.**

## Repo Structure

```
mf-platform/
├── data-engineering/        # Person A
│   ├── ingestion/           # scripts pulling from mfapi.in / AMFI into S3
│   ├── sql/                 # Snowflake DDL + dip/hike window-function queries
│   └── notebooks/           # exploratory analysis, threshold tuning
│
├── api/                     # Person B
│   ├── app/
│   │   ├── routes/          # FastAPI route handlers (funds, events, portfolio)
│   │   ├── models/          # pydantic schemas / DB models
│   │   └── services/        # Snowflake connector, business logic
│   ├── requirements.txt
│   └── main.py
│
├── analytics-forecasting/   # Person C
│   ├── notebooks/           # EDA, recommendation logic prototyping
│   ├── models/              # forecasting scripts (moving avg / ARIMA)
│   └── dags/                # Airflow DAG (optional, daily refresh)
│
├── docs/
│   ├── api-contract.md      # shared contract — read this first
│   ├── data-dictionary.md   # table/column definitions
│   └── architecture.md      # system diagram + notes
│
├── .github/workflows/       # CI (optional, stretch goal)
├── .gitignore
└── README.md
```

## Getting Started

```bash
# Clone
git clone <your-repo-url>
cd mf-platform

# Each person works inside their own folder.
# Data Engineering (Person A)
cd data-engineering && pip install -r requirements.txt

# API (Person B)
cd api && pip install -r requirements.txt
uvicorn main:app --reload

# Analytics/Forecasting (Person C)
cd analytics-forecasting && pip install -r requirements.txt
```

Each subfolder will get its own `requirements.txt` as dependencies are added —
don't install everything globally; keep each layer's dependencies scoped to
its folder so the API doesn't end up needing PySpark, etc.

## Branching Convention

See [`docs/branching-convention.md`](docs/branching-convention.md) for the
full convention. Short version:

- `main` — always working. Never push broken code directly to `main`.
- `feature/<owner>-<short-description>` — e.g. `feature/persona-nav-ingestion`,
  `feature/personb-portfolio-endpoints`, `feature/personc-forecast-model`.
- Small, frequent PRs into `main` — at minimum once per day per person, ideally
  more. On a 3-day project, a PR sitting unreviewed for a day is a lost day.
- One teammate reviews/approves before merge if possible; if no one's free,
  self-merge rather than block, but post in chat what you merged.

## Daily Checkpoints

- **Day 1:** Schema + API contract agreed. Raw NAV data landing in S3/Snowflake.
- **Day 2:** Dip/hike detection live. Full API testable via `/docs`. Forecast v1 running.
- **Day 3:** Deployed, polished, demo-ready end to end.

Full day-by-day task breakdown lives in the project plan doc shared with the team.
