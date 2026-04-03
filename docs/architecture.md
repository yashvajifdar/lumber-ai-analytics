# Lumber AI Analytics — Architecture & Design Document

## 1. Problem Statement

Mid-market lumber and building supply businesses have years of operational data spread across
POS systems, accounting tools, and spreadsheets. They cannot turn this data into decisions
because they lack dedicated analytics staff and the tools available (Tableau, Looker, Power BI)
are too expensive and too technical for their operators.

**Goal:** Build a platform that ingests their operational data, computes trusted business metrics,
and lets owners and managers ask business questions in plain English.

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                  │
│  CSV / Excel │ QuickBooks │ POS Systems │ Inventory Tools │ ERP     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   INGESTION LAYER   │
                    │  etl/loader.py      │
                    │  - schema mapping   │
                    │  - type coercion    │
                    │  - null handling    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  TRANSFORMATION     │
                    │  etl/loader.py      │
                    │  - financial calcs  │
                    │  - fact table join  │
                    │  - daily summaries  │
                    │  - return exclusion │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   DATA WAREHOUSE    │
                    │   SQLite (MVP)      │
                    │   ─────────────     │
                    │   customers         │
                    │   products          │
                    │   orders            │
                    │   order_items       │
                    │   inventory         │
                    │   fact_sales ◄──── (primary analytics table)
                    │   daily_summary     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   METRICS LAYER     │
                    │   metrics/kpis.py   │
                    │  ───────────────    │
                    │  revenue_over_time  │
                    │  margin_trend       │
                    │  top_products       │
                    │  top_customers      │
                    │  inventory_health   │
                    │  + 6 more           │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               │                               │
   ┌───────────▼──────────┐     ┌──────────────▼──────────┐
   │  DASHBOARD LAYER     │     │    AI CHAT LAYER         │
   │  app/main.py         │     │    app/chat_engine.py    │
   │  - Streamlit pages   │     │    ─────────────────     │
   │  - Plotly charts     │     │    Anthropic Tool Use    │
   │  - KPI cards         │     │    ─────────────────     │
   └──────────────────────┘     │  1. User question        │
                                │  2. Claude selects tool  │
                                │  3. Execute KPI function │
                                │  4. Claude explains data │
                                │  5. Return text + chart  │
                                └──────────────────────────┘
```

---

## 3. Data Flow (step by step)

### 3.1 Ingestion
```
Raw data (CSV / API response)
  → validate schema (required columns present, correct types)
  → handle nulls (drop or fill based on column business rules)
  → write to data/raw/
```

### 3.2 Transformation
```
data/raw/orders.csv + order_items.csv + products.csv + customers.csv
  → compute revenue = quantity × unit_price
  → compute cogs = quantity × unit_cost
  → compute gross_profit = revenue - cogs
  → join all into fact_sales (denormalized)
  → filter: status == "completed" (exclude returns)
  → write to SQLite: fact_sales, daily_summary
```

### 3.3 Analytics query
```
User question (natural language)
  → ChatEngine.ask()
  → Anthropic API call #1: Claude selects tool + parameters
  → Execute KPI function (e.g. kpis.top_products(n=10))
  → DataFrame returned (real, tested data)
  → Anthropic API call #2: Claude explains the data in plain English
  → ChatResult: text + DataFrame + chart_spec
  → chart_builder.build_chart(df, spec) → Plotly figure
  → Streamlit renders text + chart
```

---

## 4. Component Decisions & Tradeoffs

### 4.1 Storage: SQLite

| Option | Pro | Con |
|--------|-----|-----|
| **SQLite** (chosen) | Zero infra setup, runs anywhere, sufficient for MVP scale | Not concurrent, not cloud-native |
| PostgreSQL | Production-grade, concurrent, indexing | Requires server, more setup |
| BigQuery | Scales to billions of rows, managed | Cost, latency, overkill for MVP |
| DuckDB | Analytical workloads, fast, embedded | Less ecosystem support |

**Decision:** SQLite for MVP. The connection string is the only thing that changes when
we upgrade. All SQL is standard; no SQLite-specific syntax.

**Replacement cost:** Low. Change `DB_PATH` in `metrics/kpis.py` and `etl/loader.py`.
Everything else is unchanged.

---

### 4.2 Frontend: Streamlit

| Option | Pro | Con |
|--------|-----|-----|
| **Streamlit** (chosen) | Python-native, fast to build, no frontend expertise required | Less flexible UI, less polished than React |
| React / Next.js | Full control, production-grade UX | Requires frontend stack, slower to build |
| Dash (Plotly) | Python-native, more layout control | More boilerplate than Streamlit |
| Retool | Fast for internal tools | Vendor dependency, cost at scale |

**Decision:** Streamlit for MVP demo. A production version would use React/Next.js.
The chart layer (`chart_builder.py`) is already decoupled from Streamlit rendering — it
returns Plotly figures that work in any Python frontend.

**Replacement cost:** Moderate. Replace `app/main.py` UI calls. `chat_engine.py`,
`chart_builder.py`, and `metrics/` are untouched.

---

### 4.3 AI Layer: Anthropic Tool Use

| Option | Pro | Con |
|--------|-----|-----|
| **Anthropic Tool Use** (chosen) | Structured intent routing, Claude understands business context well | API cost per query |
| OpenAI Function Calling | Equivalent capability, large ecosystem | Alternative vendor |
| Keyword routing (removed) | Zero cost, fast | Brittle, fails on varied phrasing |
| Free-form LLM SQL generation | Flexible | Unreliable, trust-destroying if wrong |
| Retrieval-Augmented Generation | Good for document Q&A | Overkill for structured analytics |

**Decision:** Tool use with pre-defined KPI functions. The model routes language to logic;
it never generates SQL or accesses raw data. This is the only approach that is reliable
enough to trust with business financials.

**Replacement cost:** Low. Swap `ChatEngine` implementation. Tool definitions and KPI
dispatch table (`_KPI_DISPATCH`) are the interface. The rest of the system doesn't know
which AI provider is in use.

---

### 4.4 Data Source: Synthetic Data

| Option | Pro | Con |
|--------|-----|-----|
| **Synthetic data** (chosen) | No privacy/legal blockers, full schema control, ship immediately | Not real business data |
| Real data from a pilot client | Validates product, builds trust | Privacy review, legal review, data quality work |
| Open datasets (Kaggle etc.) | Available immediately | Wrong domain, wrong schema |

**Decision:** Synthetic data with realistic business logic. The data generator encodes:
- Seasonal patterns (spring/summer peak in construction)
- Customer behavior (contractor bulk buying vs. retail small orders)
- Market-driven cost fluctuation
- Discount patterns

This is not a compromise. It is the correct engineering decision given:
1. Data availability is a legal/privacy/security loop, not a technical one
2. The pipeline is designed to replace synthetic with real data at the ingestion layer only
3. Demonstrating the architecture is the goal — the data is a placeholder

**Replacement cost:** None to the metrics or AI layers. Replace `etl/generate_data.py` with
a real connector. The schema contract (fact_sales columns, inventory columns) is the only
interface that must be preserved.

---

### 4.5 Visualization: Plotly via chart_builder.py

| Option | Pro | Con |
|--------|-----|-----|
| **Plotly** (chosen) | Python-native, rich chart types, works in Streamlit and browser | |
| ECharts / Apache Superset | More chart types | Requires separate service |
| D3.js | Maximum flexibility | Requires JavaScript frontend |
| Recharts | React-native, clean | Requires React frontend |

**Decision:** Plotly via the decoupled `chart_builder.py` module. Chart specs are defined
in `chat_engine.CHART_SPECS` as data, not as Plotly code. Swapping Plotly means changing
only `chart_builder.py`.

---

## 5. Modular Replacement Guide

The system is designed so each layer is independently replaceable:

| Component | Current | Replace with | What changes |
|-----------|---------|--------------|--------------|
| Data source | Synthetic CSVs | QuickBooks API, POS connectors | `etl/generate_data.py` or add new `etl/connectors/` |
| Storage | SQLite | Postgres, BigQuery, Snowflake, DuckDB | `DB_PATH` connection string |
| Transform | Pandas + Python | dbt, Spark, Beam | `etl/loader.py` |
| Metrics | Python functions | dbt metrics, Cube.js semantic layer | `metrics/kpis.py` interface |
| AI provider | Anthropic | OpenAI, Mistral, local LLM | `ChatEngine` class in `chat_engine.py` |
| Frontend | Streamlit | React/Next.js | `app/main.py` |
| Charts | Plotly | ECharts, Recharts, D3 | `app/chart_builder.py` |
| Infrastructure | Local | AWS, Azure, GCP, on-prem | Dockerfile + env vars |

---

## 6. Data Model

### Core tables (loaded from source)
```
customers       customer_id, name, type, location, since
products        product_id, name, category, cost, list_price
orders          order_id, customer_id, order_date, location, status
order_items     order_id, product_id, quantity, unit_price, unit_cost, discount
inventory       product_id, location, stock_level, reorder_point, last_updated
```

### Derived tables (computed in ETL)
```
fact_sales      denormalized join of orders + items + products + customers
                key columns: revenue, cogs, gross_profit, margin
                filter: status = 'completed' (returns excluded)

daily_summary   fact_sales grouped by order_date
                key columns: revenue, cogs, gross_profit, orders, margin_pct
```

### Key business definitions

| Metric | Definition |
|--------|-----------|
| Revenue | `quantity × unit_price` per line item |
| COGS | `quantity × unit_cost` per line item |
| Gross Profit | `revenue - cogs` |
| Gross Margin % | `gross_profit / revenue × 100` |
| Completed orders | Orders with `status = 'completed'` (returns excluded) |
| Repeat customer | Customer with ≥ 2 distinct orders |
| Below reorder | `stock_level < reorder_point` |
| Inventory value | `stock_level × cost` |

---

## 7. Non-Functional Considerations

### Security
- API keys via environment variables only. Never in code or committed files.
- No user-supplied input reaches SQL directly. KPI functions use parameterized queries.
- `.env` always in `.gitignore`.

### Scalability
- SQLite handles single-user demo load without issue.
- Replacing with Postgres or BigQuery requires no code changes beyond the connection.
- Streamlit is single-user by design. Multi-tenant would require a proper API backend.

### Observability (future)
- Log every chat question, tool selected, and response time.
- Track user feedback per answer (thumbs up/down).
- Alert on data quality failures (null rate spikes, range violations).

### Data quality (future)
- Null rate checks on `revenue`, `cost`, `customer_id` after every ingestion.
- Range validation: `margin_pct` between 0 and 100, `revenue > 0`.
- Referential integrity: every `order_item.order_id` exists in `orders`.
- Drift detection: flag if monthly revenue deviates > 3σ from trailing average.
