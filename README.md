# Lumber AI Analytics

An end-to-end business intelligence platform for lumber and building supply companies.
Ingests operational data, computes trusted business metrics, and lets owners ask questions
in plain English via an AI-powered chat interface.

Built as a consulting portfolio piece demonstrating production-grade data engineering,
analytics architecture, and AI integration. The live chat demo runs at
**[yashvajifdar.com/demos/lumber](https://yashvajifdar.com/demos/lumber)**.

---

## What It Does

Business owners and managers connect their operational data and ask questions like:

- *"Why did margin drop last month?"*
- *"Which products are slow-moving?"*
- *"Which contractor accounts are underperforming?"*
- *"What inventory needs reordering this week?"*

The platform returns natural language answers with supporting data — no SQL, no dashboards
to learn, no analyst required.

---

## Architecture

```
Data Sources (CSV / QuickBooks / POS)
    │
    ▼
ETL Pipeline  (etl/loader.py)
    │  schema normalization, financial calculations, return exclusion
    ▼
SQLite Warehouse  (data/lumber.db)
    │  customers, products, orders, order_items, inventory, fact_sales
    ▼
Metrics Layer  (metrics/kpis.py)
    │  11 trusted KPI functions — the only path to data
    │
    ├──▶ Streamlit App  (app/main.py)
    │       │  chat UI with suggestion cards, follow-up chips
    │       ▼
    │    AI Engine  (app/anthropic_engine.py or app/gemini_engine.py)
    │       │  LLM selects KPI tool → function executes → LLM explains result
    │       ▼
    │    Chart Builder  (app/chart_builder.py)
    │       │  df + spec → Plotly figure → Streamlit renders
    │
    └──▶ FastAPI Backend  (app/api.py)
            │  POST /ask — proxied by yashvajifdar.com/api/lumber/ask
            ▼
         Personal Website Chat UI  (yashvajifdar.com/demos/lumber)
```

**Key design principle:** The LLM never writes SQL or accesses raw data.
It selects from pre-defined, tested KPI functions. Trust is built into the architecture.

Full design decisions and tradeoff analysis: [`docs/architecture.md`](docs/architecture.md)
Roadmap and milestones: [`docs/working_backwards.md`](docs/working_backwards.md)
Operations runbook: [`docs/runbook.md`](docs/runbook.md)

---

## Quick Start

```bash
# 1. Clone and enter project
cd lumber-ai-analytics

# 2. Create virtual environment and activate it
python3 -m venv venv
source venv/bin/activate   # prompt will show (venv) when active
pip install -r requirements.txt

# 3. Configure API key
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY (or GOOGLE_API_KEY for Gemini)

# 4. Generate synthetic data and run ETL
python3 etl/generate_data.py
python3 etl/loader.py

# 5. Start the Streamlit app
python3 -m streamlit run app/main.py
```

> **Important:** always activate the venv (`source venv/bin/activate`) before running
> any command. If you see `ModuleNotFoundError`, the venv is not active.

Open **http://localhost:8501** in your browser.

To run the FastAPI backend (for the personal website demo):

```bash
uvicorn app.api:app --reload --port 8001
```

Open <http://localhost:8001/health> to confirm it's running.

---

## Demo Flow

The app opens directly to the chat interface. Ask business questions in plain English:

```text
"What were total sales this year?"
"Which products have the highest margin?"
"Why did margin drop?"
"Which customers spend the most?"
"What inventory is running low?"
```

Each question returns a natural language answer with supporting data.
The AI never makes up numbers — it queries the real data every time.

Suggestion cards are shown on first load. Follow-up chips appear after each answer.

---

## Switching AI Providers

Change one line in `.env`. No code changes required.

```bash
# Use Anthropic Claude (default)
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Use Google Gemini (free tier at aistudio.google.com)
AI_PROVIDER=gemini
GOOGLE_API_KEY=AIza...
```

The swap seam is `build_engine()` in [`app/engine_factory.py`](app/engine_factory.py).
Both engines implement the same interface and return the same `ChatResult` dataclass.
Everything else — metrics layer, chart builder, API, and all tests — is unchanged.

---

## Project Structure

```
lumber-ai-analytics/
│
├── etl/
│   ├── generate_data.py     # Synthetic data generator (15 months, realistic patterns)
│   └── loader.py            # ETL: CSV → transform → SQLite
│
├── metrics/
│   └── kpis.py              # 11 KPI functions — all business logic lives here
│
├── app/
│   ├── main.py              # Streamlit chat UI
│   ├── api.py               # FastAPI backend — POST /ask, GET /health
│   ├── engine_factory.py    # build_engine() — reads AI_PROVIDER, returns engine
│   ├── engine_tools.py      # Shared: tool defs, chart specs, ChatResult, follow-ups
│   ├── anthropic_engine.py  # AnthropicEngine — two-turn tool-use flow
│   ├── gemini_engine.py     # GeminiEngine — same interface, different provider
│   └── chart_builder.py     # build_chart(df, spec) → Plotly figure
│
├── tests/
│   ├── conftest.py          # Shared fixtures — in-memory DB with deterministic data
│   ├── test_etl.py          # ETL transformation tests
│   ├── test_kpis.py         # KPI function tests (known-value assertions)
│   └── test_chat_engine.py  # AI engine tests (mocked API, all chart specs)
│
├── docs/
│   ├── architecture.md      # System design, decisions, tradeoff tables
│   ├── working_backwards.md # Roadmap: press release, milestones, risks
│   ├── runbook.md           # Operations: local dev, deploy, adding KPIs
│   └── demo_script.md       # Walkthrough script for client demos
│
├── data/
│   ├── raw/                 # Generated CSVs (gitignored)
│   └── lumber.db            # SQLite warehouse (gitignored)
│
├── .env.example             # Environment variable reference
├── CLAUDE.md                # AI agent working context
└── requirements.txt
```

---

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific module
python -m pytest tests/test_kpis.py -v
python -m pytest tests/test_etl.py -v
python -m pytest tests/test_chat_engine.py -v
```

**119 tests, 4 test files:**

- `test_etl.py` — ETL financial calculations, returned order exclusion, date enrichment, inventory flags
- `test_kpis.py` — every KPI function, known-value assertions, edge cases
- `test_chat_engine.py` — two-turn tool-use flow (mocked API), provider swap, chart builder coverage

Tests use an in-memory SQLite DB with deterministic data — no production DB touched,
no real API calls made.

---

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `AI_PROVIDER` | No | `anthropic` (default) or `gemini` |
| `ANTHROPIC_API_KEY` | If provider=anthropic | Get at console.anthropic.com |
| `GOOGLE_API_KEY` | If provider=gemini | Get at aistudio.google.com (free tier) |

---

## Data Model

| Table | Description |
|-------|-------------|
| `customers` | 200 accounts (120 contractors, 80 retail) |
| `products` | 20 SKUs across 8 categories |
| `orders` | ~3,900 orders over 15 months |
| `order_items` | ~19,700 line items with revenue, COGS, margin |
| `inventory` | Stock levels and reorder points per SKU per yard |
| `fact_sales` | Denormalized fact table — completed orders only |
| `daily_summary` | Pre-aggregated daily metrics |

Synthetic data encodes realistic business patterns: spring/summer construction seasonality,
contractor bulk-buying vs. retail behavior, cost fluctuations, and discounting.

To connect real data: replace `etl/generate_data.py` with a real connector.
The `fact_sales` column contract is the only interface that must be preserved.

---

## KPI Functions

All business logic is in [`metrics/kpis.py`](metrics/kpis.py):

| Function | Description |
|----------|-------------|
| `revenue_over_time(period)` | Revenue, COGS, gross profit, margin by day/week/month |
| `margin_trend(period)` | Margin % trend over time |
| `top_products(n, by)` | Top N products by revenue, profit, quantity, or margin |
| `bottom_margin_products(n)` | Lowest margin products (min $5K revenue threshold) |
| `revenue_by_category()` | Revenue and margin by product category |
| `top_customers(n)` | Top N customers by revenue |
| `customer_type_split()` | Contractor vs. retail revenue split |
| `repeat_customer_rate()` | Repeat purchase rate by customer type |
| `revenue_by_location(period)` | Revenue by yard location over time |
| `inventory_health()` | Stock levels, reorder alerts, inventory value |
| `slow_moving_inventory()` | High stock + low 90-day sales velocity |

---

## Development Notes

**Adding a new KPI function:**
1. Add the function to `metrics/kpis.py`
2. Add a tool definition to `TOOL_DEFINITIONS` in `app/engine_tools.py`
3. Add a chart spec to `CHART_SPECS` in `app/engine_tools.py`
4. Add to `KPI_DISPATCH` in `app/engine_tools.py`
5. Add follow-up suggestions to `FOLLOW_UP_SUGGESTIONS` in `app/engine_tools.py`
6. Write tests in `tests/test_kpis.py`

**Adding a new AI provider:**

1. Create `app/<provider>_engine.py` with a class implementing `.ask(question, history) -> ChatResult`
2. Add a branch in `build_engine()` in `app/engine_factory.py`
3. Document the new `AI_PROVIDER` value in `.env.example`

**Upgrading storage from SQLite to Postgres:**
Change the connection string in `metrics/kpis.py` and `etl/loader.py`.
All SQL is ANSI-standard. No other changes required.
