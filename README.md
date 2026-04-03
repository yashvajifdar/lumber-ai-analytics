# Lumber AI Analytics

An end-to-end business intelligence platform for lumber and building supply companies.
Ingests operational data, computes trusted business metrics, and lets owners ask questions
in plain English via an AI-powered chat interface.

Built as a consulting portfolio piece demonstrating production-grade data engineering,
analytics architecture, and AI integration.

---

## What It Does

Business owners and managers connect their operational data and ask questions like:

- *"Why did margin drop last month?"*
- *"Which products are slow-moving?"*
- *"Which contractor accounts are underperforming?"*
- *"What inventory needs reordering this week?"*

The platform returns natural language answers with supporting charts — no SQL, no dashboards
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
    ▼
    ├──▶ Dashboard  (Streamlit pages: revenue, products, customers, inventory)
    │
    └──▶ AI Chat Engine  (app/anthropic_engine.py / app/gemini_engine.py)
              │  LLM selects tool → KPI function executes → LLM explains result
              ▼
         Chart Builder  (app/chart_builder.py)
              │  df + spec → Plotly figure
              ▼
         Streamlit Chat UI
```

**Key design principle:** The LLM never writes SQL or accesses raw data.
It selects from pre-defined, tested KPI functions. Trust is built into the architecture.

Full design decisions and tradeoff analysis: [`docs/architecture.md`](docs/architecture.md)
Working backwards plan and milestones: [`docs/working_backwards.md`](docs/working_backwards.md)

---

## Quick Start

```bash
# 1. Clone and enter project
cd lumber-ai-analytics

# 2. Create virtual environment and activate it
python3 -m venv venv
source venv/bin/activate   # your prompt will show (venv) when active
pip install -r requirements.txt

# 3. Configure API key
cp .env.example .env
# Edit .env — add your GOOGLE_API_KEY (Gemini) or ANTHROPIC_API_KEY

# 4. Generate data and run ETL
python3 etl/generate_data.py
python3 etl/loader.py

# 5. Start the app
python3 -m streamlit run app/main.py
```

> **Important:** always activate the venv (`source venv/bin/activate`) before running
> any command. All dependencies are installed inside the venv, not system-wide.
> If you see `ModuleNotFoundError`, the venv is not active.

Open **http://localhost:8501** in your browser. The app has 5 pages in the left sidebar.

---

## App Pages & Demo Flow

### Sidebar navigation
| Page | What it shows |
|------|--------------|
| **Dashboard** | Revenue and margin trends over time, location comparison. Use the period selector (day / week / month) at the top. |
| **Products** | Top products by revenue, lowest margin products, revenue by category |
| **Customers** | Contractor vs retail split, repeat purchase rate, top accounts |
| **Inventory** | Items below reorder point, slow-moving stock scatter plot |
| **Chat** | AI-powered natural language interface — type any business question |

### Demo script (recommended order for a client walkthrough)

**1. Start on Dashboard**
- Change the period to "week" to show week-over-week trends
- Point out the margin % line — it tells a story about cost pressure

**2. Go to Products**
- Show the horizontal bar chart — color-coded by margin
- Point out the lowest-margin products section — this is where money is leaking

**3. Go to Customers**
- Show the contractor vs retail revenue split
- Highlight the repeat customer rate — contractors are sticky, retail is not

**4. Go to Inventory**
- Show items flagged below reorder point
- Show the slow-moving scatter — high stock, low sales = cash tied up

**5. Finish on Chat — this is the wow moment**
Ask these questions in order:
```
"What were total sales this year?"
"Which products have the highest margin?"
"Why did margin drop?"
"Which customers spend the most?"
"What inventory is running low?"
```
Each question returns a natural language answer with a supporting chart.
The AI never makes up numbers — it queries the real data every time.

---

## Switching AI Providers

Change one line in `.env`. No code changes required.

```bash
# Use Anthropic Claude (default)
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Use Google Gemini (free tier available at aistudio.google.com)
AI_PROVIDER=gemini
GOOGLE_API_KEY=AIza...
```

The swap seam is `build_engine()` in [`app/chat_engine.py`](app/chat_engine.py).
Both engines return the same `ChatResult` dataclass. Everything else in the system
is unchanged — metrics layer, chart builder, dashboard pages, and all tests.

See [`docs/architecture.md`](docs/architecture.md) for the full modular replacement guide
(storage, frontend, visualization, and infrastructure are equally swappable).

---

## Project Structure

```
lumber-ai-analytics/
│
├── etl/
│   ├── generate_data.py     # Synthetic data generator (15 months, realistic business patterns)
│   └── loader.py            # ETL: CSV → transform → SQLite
│
├── metrics/
│   └── kpis.py              # 11 KPI functions — all business logic lives here
│
├── app/
│   ├── main.py              # Streamlit UI (Dashboard, Products, Customers, Inventory, Chat)
│   ├── chat_engine.py       # Anthropic tool-use engine + build_engine() factory
│   ├── gemini_engine.py     # Google Gemini engine (same interface)
│   └── chart_builder.py     # build_chart(df, spec) → Plotly figure
│
├── tests/
│   ├── conftest.py          # Shared fixtures — temp DB with deterministic test data
│   ├── test_etl.py          # ETL transformation tests (pure pandas, no DB)
│   ├── test_kpis.py         # KPI function tests (61 tests, known-value assertions)
│   └── test_chat_engine.py  # AI engine tests (mocked API, all chart specs)
│
├── docs/
│   ├── architecture.md      # Full system design, decisions, tradeoff tables
│   └── working_backwards.md # Amazon-style: press release, milestones, task breakdown
│
├── data/
│   ├── raw/                 # Generated CSVs (gitignored)
│   └── lumber.db            # SQLite warehouse (gitignored)
│
├── .env.example             # Environment variable reference
├── CLAUDE.md                # AI agent context for this project
└── requirements.txt
```

---

## Running Tests

```bash
# All tests
venv/bin/python -m pytest tests/ -v

# Specific module
venv/bin/python -m pytest tests/test_kpis.py -v
venv/bin/python -m pytest tests/test_etl.py -v
venv/bin/python -m pytest tests/test_chat_engine.py -v
```

**112 tests, 4 test classes:**
- `test_etl.py` — 20 tests: financial calculations, returned order exclusion, date enrichment, inventory flags
- `test_kpis.py` — 61 tests: every KPI function, known-value assertions, edge cases
- `test_chat_engine.py` — 31 tests: two-turn tool-use flow (mocked API), chart builder coverage

Tests use an in-memory SQLite DB with deterministic data — no production DB touched,
no real API calls made.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AI_PROVIDER` | No | `anthropic` (default) or `gemini` |
| `ANTHROPIC_API_KEY` | If provider=anthropic | Get at console.anthropic.com |
| `GOOGLE_API_KEY` | If provider=gemini | Get at aistudio.google.com (free tier) |

---

## Data Model

The platform runs on a small canonical schema:

| Table | Description |
|-------|-------------|
| `customers` | 200 accounts (120 contractors, 80 retail) |
| `products` | 20 SKUs across 8 categories |
| `orders` | ~3,900 orders over 15 months |
| `order_items` | ~19,700 line items with revenue, COGS, margin |
| `inventory` | Stock levels and reorder points per SKU per yard |
| `fact_sales` | Denormalized fact table — completed orders only |
| `daily_summary` | Pre-aggregated daily metrics |

The synthetic dataset encodes realistic business patterns: spring/summer construction
seasonality, contractor bulk-buying vs. retail behavior, cost fluctuations, and discounting.

Replacing synthetic data with real data requires only changing the ingestion layer
(`etl/generate_data.py`). The schema contract (`fact_sales` columns) is the only interface
that must be preserved.

---

## KPI Functions

All business logic is in [`metrics/kpis.py`](metrics/kpis.py):

| Function | Description |
|----------|-------------|
| `revenue_over_time(period)` | Revenue, COGS, gross profit, margin by day/week/month |
| `margin_trend(period)` | Margin % trend over time |
| `top_products(n, by)` | Top N products by revenue, profit, or quantity |
| `bottom_margin_products(n)` | Lowest margin products (min $5K revenue) |
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
2. Add a tool definition to `TOOLS` in `app/chat_engine.py`
3. Add a chart spec to `CHART_SPECS` in `app/chat_engine.py`
4. Add to `_KPI_DISPATCH` in `app/chat_engine.py`
5. Write tests in `tests/test_kpis.py`

**Adding a new AI provider:**
1. Create `app/<provider>_engine.py` with a class implementing `.ask(question) -> ChatResult`
2. Add a branch in `build_engine()` in `app/chat_engine.py`
3. Document the new `AI_PROVIDER` value in `.env.example`

**Upgrading storage from SQLite to Postgres:**
Change `DB_PATH` in `metrics/kpis.py` and `etl/loader.py` to a Postgres connection string.
All SQL is ANSI-standard. No other changes required.
