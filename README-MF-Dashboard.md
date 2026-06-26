# Mutual Fund Analytics & Portfolio Recommendation Platform

An enterprise-grade, schema-adaptive Mutual Fund dashboard designed to run on top of **Databricks SQL & Delta Tables** or offline in **Demo Mode** using highly realistic synthetic Indian Mutual Fund datasets.

---

## Key Features

1. **Dynamic Databricks Schema Engine**
   - Automatically inspects and discovers schemas of Delta Tables.
   - Uses semantic fuzzy mapping (`thefuzz`) to map different table layouts to canonical analytics schemas without code changes.
   - Automatically caches queries and handles database connections gracefully.

2. **Market Overview Dashboard**
   - Glassmorphism key performance indicators (Total Funds, Total AUM, Average Returns, Risk Index, Best/Worst performing category).
   - Treemaps detailing AUM distributions.
   - Category performance heatmap matrices.
   - Scatter risk plots benchmarking all active schemes.

3. **Individual Fund Performance Analytics**
   - Fully searchable deep-dives for over 150 funds.
   - 3-year historical Net Asset Value (NAV) interactive line charts.
   - Peer risk-return bubble charts comparing peer funds in the same asset class.
   - Timeline return comparisons showing the fund's historical performance vs. category averages.

4. **Fund Ups & Downs Analysis**
   - Identifies top 10 gainers and losers across 1M, 3M, 6M, 1Y, 3Y, and 5Y horizons.
   - Visual return rankings and category average comparisons.

5. **Category Analytics**
   - Specialized dashboards for Large Cap, Mid Cap, Small Cap, Flexi Cap, and other categories.
   - Radar charts comparing risk vectors against market indices.
   - Distribution metrics (volatility histograms, AUM area spreads).

6. **AI Recommendation Engine**
   - Aligns allocations dynamically based on client age, investment amount, risk tolerance, timeline, and goals (e.g., Tax Saving, Wealth Creation, Retirement).
   - Multi-factor mathematical scoring system.
   - Generates interactive compound interest growth projections.
   - Automatically generates personalized explanations using **LangChain & OpenAI**.

7. **Client Portfolio Analytics**
   - Analyzes three distinct client portfolios (Conservative, Moderate, Aggressive).
   - Computes weighted stats, category donut shares, HHI diversification index, and future growth paths.
   - **AI Portfolio Advisor**: Reviews portfolio health, listing strengths, weaknesses, and actionable recommendations.



---

## Project Structure

```text
mf_analytics/
├── app.py                              # Main application entry point
├── requirements.txt                    # Python dependencies
├── .env.example                        # Template config file
│
├── config/
│   ├── settings.py                     # App settings loader
│   └── column_mappings.py              # Semantic aliases mapping
│
├── data/
│   └── demo_data_generator.py          # Synthetic data engine
│
├── databricks_connector/
│   ├── connector.py                    # Connection manager
│   ├── schema_engine.py                # Schema profiling
│   ├── column_mapper.py                # Fuzzy mapper
│   └── data_service.py                 # Data orchestrator
│
├── modules/
│   ├── market_overview/                # Module 1
│   ├── fund_analysis/                  # Module 2
│   ├── ups_downs/                      # Module 3
│   ├── category_analysis/              # Module 4
│   ├── ai_recommendation/              # Module 5
│   └── portfolio_analysis/             # Module 6
│
├── services/
│   ├── ai_service.py                   # LangChain & OpenAI integration
│   ├── recommendation_engine.py        # Logic for target allocations
│   └── portfolio_engine.py             # Math & Stats for client assets
│
├── charts/
│   ├── chart_factory.py                # Centralized Plotly charts
│   └── theme.py                        # Premium dark template configuration
│
├── utils/
│   ├── calculations.py                 # Core financial formulas
│   └── formatters.py                   # INR and formatting helpers
│
├── assets/
│   └── styles.css                      # Glassmorphism dark-theme CSS
│
└── tests/
    └── test_calculations.py            # Unit tests
```

---

## Getting Started

### 1. Installation
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configuration
Copy the template configuration file to `.env`:
```bash
cp .env.example .env
```
Open `.env` and adjust the variables:
- Set `APP_MODE=demo` to test the platform immediately offline using synthetic data.
- Set `APP_MODE=live` to connect directly to Databricks (requires entering your credentials).
- Insert your `OPENAI_API_KEY` to activate AI recommendations.

### 3. Run the Dashboard
Start the Streamlit application:
```bash
streamlit run app.py
```
This will open the dashboard in your default web browser (typically at `http://localhost:8501`).
