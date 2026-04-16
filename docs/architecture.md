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

```text
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
                    │  ───────────────    │
                    │  customers          │
                    │  products           │
                    │  orders             │
                    │  order_items        │
                    │  inventory          │
                    │  fact_sales ◄────── (primary analytics table)
                    │  daily_summary      │
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
          ┌────────────────────┼────────────────────┐
          │                                         │
┌─────────▼──────────┐              ┌───────────────▼──────────┐
│  STREAMLIT APP     │              │  FASTAPI BACKEND          │
│  app/main.py       │              │  app/api.py               │
│  ────────────────  │              │  ─────────────────────    │
│  Chat UI           │              │  POST /ask                │
│  Suggestion cards  │              │  GET  /health             │
│  Follow-up chips   │              │  ─────────────────────    │
└─────────┬──────────┘              │  Proxied by Vercel at     │
          │                         │  yashvajifdar.com/        │
┌─────────▼──────────┐              │    api/lumber/ask         │
│  AI ENGINE LAYER   │◄─────────────┤                           │
│  engine_factory.py │              └───────────────────────────┘
│  ────────────────  │
│  build_engine()    │
│  ↓                 │
│  AnthropicEngine   │  (app/anthropic_engine.py)
│  or GeminiEngine   │  (app/gemini_engine.py)
│  ────────────────  │
│  Turn 1: LLM picks │
│  KPI tool          │
│  Turn 2: LLM reads │
│  data and explains │
└─────────┬──────────┘
          │
┌─────────▼──────────┐
│  SHARED TOOLS      │
│  engine_tools.py   │
│  ────────────────  │
│  TOOL_DEFINITIONS  │
│  CHART_SPECS       │
│  KPI_DISPATCH      │
│  FOLLOW_UP_SUGGS   │
│  ChatResult        │
└─────────┬──────────┘
          │
┌─────────▼──────────┐
│  CHART BUILDER     │
│  chart_builder.py  │
│  ────────────────  │
│  df + spec →       │
│  Plotly figure     │
└────────────────────┘
```text

---

## 3. Data Flow (step by step)

### 3.1 Ingestion

```text
Raw data (CSV / API response)
  → validate schema (required columns present, correct types)
  → handle nulls (drop or fill based on column business rules)
  → write to data/raw/
```text

### 3.2 Transformation

```text
data/raw/orders.csv + order_items.csv + products.csv + customers.csv
  → compute revenue = quantity × unit_price
  → compute cogs = quantity × unit_cost
  → compute gross_profit = revenue - cogs
  → join all into fact_sales (denormalized)
  → filter: status == "completed" (exclude returns)
  → write to SQLite: fact_sales, daily_summary
```text

### 3.3 Analytics query (Streamlit path)

```text
User question (natural language) → Streamlit chat input
  → engine.ask(question, history)
  → Turn 1: LLM selects KPI tool + parameters
  → KPI function executes (e.g. kpis.top_products(n=10))
  → DataFrame returned (real, tested data)
  → Turn 2: LLM explains data in plain English
  → ChatResult: text + DataFrame + chart_spec + follow_ups
  → chart_builder.build_chart(df, spec) → Plotly figure
  → Streamlit renders text + chart + follow-up chips
```text

### 3.4 Analytics query (API path)

```text
Browser → POST /api/lumber/ask (Vercel proxy, Next.js route)
  → POST /ask (FastAPI backend, Railway/Render)
  → engine.ask(question, history)      [same engine as Streamlit path]
  → ChatResult serialized to JSON
      { text, follow_ups, chart_spec, chart_data, kpi_called }
  → Vercel returns JSON to browser
  → Next.js chat page renders text + data table + follow-up chips
```text

---

## 4. Module Responsibilities

| Module | Responsibility |
| --- | --- |
| `etl/generate_data.py` | Synthetic data generation — 15 months, 200 customers, 20 SKUs |
| `etl/loader.py` | ETL: CSV → transform → SQLite |
| `metrics/kpis.py` | All business logic — 11 KPI functions, no raw SQL in app layer |
| `app/engine_tools.py` | Provider-agnostic shared state: tool defs, chart specs, ChatResult |
| `app/engine_factory.py` | `build_engine()` — reads `AI_PROVIDER`, returns the right engine |
| `app/anthropic_engine.py` | Two-turn Anthropic tool-use flow |
| `app/gemini_engine.py` | Equivalent flow using Google Gemini |
| `app/chart_builder.py` | `build_chart(df, spec)` → Plotly figure |
| `app/main.py` | Streamlit chat UI |
| `app/api.py` | FastAPI: `POST /ask`, `GET /health` |

---

## 5. Component Decisions & Tradeoffs

### 5.1 Storage: SQLite

| Option | Pro | Con |
| --- | --- | --- |
| **SQLite** (chosen) | Zero infra setup, runs anywhere, sufficient for MVP | Not concurrent, not cloud-native |
| PostgreSQL | Production-grade, concurrent, indexing | Requires server, more setup |
| BigQuery | Scales to billions of rows, managed | Cost, latency, overkill for MVP |
| DuckDB | Analytical workloads, fast, embedded | Less ecosystem support |

**Decision:** SQLite for MVP. The connection string is the only thing that changes on upgrade.
All SQL is standard; no SQLite-specific syntax.

**Replacement cost:** Low. Change `DB_PATH` in `metrics/kpis.py` and `etl/loader.py`.

---

### 5.2 Chat Frontend: Streamlit (Streamlit path)

| Option | Pro | Con |
| --- | --- | --- |
| **Streamlit** (chosen) | Python-native, fast to build, no frontend expertise required | Less flexible UI, single-user |
| React / Next.js | Full control, production-grade UX | Requires frontend stack |
| Dash (Plotly) | Python-native, more layout control | More boilerplate |
| Retool | Fast for internal tools | Vendor dependency, cost |

**Decision:** Streamlit for the Python demo. The personal website uses a Next.js chat page
(`/demos/lumber`) with the same engine accessed via the FastAPI backend.

---

### 5.3 AI Layer: Tool Use (provider-agnostic)

| Option | Pro | Con |
| --- | --- | --- |
| **Tool Use** (chosen) | Structured routing, reliable with business financials | API cost per query |
| Free-form SQL generation | Flexible | Unreliable — wrong answers destroy trust |
| Keyword routing | Zero cost, fast | Brittle on varied phrasing |
| RAG over documents | Good for prose Q&A | Wrong approach for structured analytics |

**Decision:** LLM selects from pre-defined KPI functions. It never generates SQL or accesses
raw data. This is the only approach reliable enough to trust with business financials.

**Replacement cost:** Low. Swap the engine class. `engine_tools.py` — the tool definitions,
chart specs, dispatch table, and `ChatResult` — is the shared interface. Neither the Streamlit
UI nor the FastAPI backend knows which engine is running.

---

### 5.4 API Layer: FastAPI

| Option | Pro | Con |
| --- | --- | --- |
| **FastAPI** (chosen) | Python-native, Pydantic validation, auto-docs, async-ready | Extra deploy target |
| Flask | Simpler | No type validation, no auto-docs |
| Next.js API routes only | One fewer service | Business logic would need rewriting in JS |
| Streamlit Cloud embed | No new code | Iframe UX, different design language |

**Decision:** FastAPI wrapper over the existing Python engine. The personal website proxies
to it via a Next.js API route, keeping the backend URL hidden and avoiding CORS issues.

---

### 5.5 Data Source: Synthetic Data

**Decision:** Synthetic data with realistic business logic (seasonal patterns, customer behavior,
cost fluctuation, discounting). This is not a compromise — it is the correct engineering
decision given data availability requires legal and privacy review before real client data
can be used. The pipeline replaces synthetic with real data at the ingestion layer only.

**Replacement cost:** None to the metrics or AI layers. Replace `etl/generate_data.py`
with a real connector. The `fact_sales` column contract is the only interface to preserve.

---

## 6. Modular Replacement Guide

| Component | Current | Replace with | What changes |
| --- | --- | --- | --- |
| Data source | Synthetic CSVs | QuickBooks API, POS connectors | `etl/generate_data.py` or add `etl/connectors/` |
| Storage | SQLite | Postgres, BigQuery, DuckDB | `DB_PATH` connection string |
| Transform | Pandas + Python | dbt, Spark | `etl/loader.py` |
| Metrics | Python functions | dbt metrics, Cube.js | `metrics/kpis.py` interface |
| AI provider | Anthropic | OpenAI, Gemini, local LLM | New engine class in `app/` |
| Streamlit UI | Streamlit | Any Python frontend | `app/main.py` |
| Web chat UI | Next.js + FastAPI | Any JS frontend + any API | `app/api.py` + personal website |
| Charts | Plotly | ECharts, Recharts, D3 | `app/chart_builder.py` |
| Infrastructure | Local | AWS, Railway, Render, GCP | Dockerfile + env vars |

---

## 7. Data Model

### Core tables (loaded from source)

```text
customers       customer_id, name, type, location, since
products        product_id, name, category, cost, list_price
orders          order_id, customer_id, order_date, location, status
order_items     order_id, product_id, quantity, unit_price, unit_cost, discount
inventory       product_id, location, stock_level, reorder_point, last_updated
```text

### Derived tables (computed in ETL)

```text
fact_sales      denormalized join of orders + items + products + customers
                key columns: revenue, cogs, gross_profit, margin
                filter: status = 'completed' (returns excluded)

daily_summary   fact_sales grouped by order_date
                key columns: revenue, cogs, gross_profit, orders, margin_pct
```text

### Key business definitions

| Metric | Definition |
| --- | --- |
| Revenue | `quantity × unit_price` per line item |
| COGS | `quantity × unit_cost` per line item |
| Gross Profit | `revenue - cogs` |
| Gross Margin % | `gross_profit / revenue × 100` |
| Completed orders | Orders with `status = 'completed'` (returns excluded) |
| Repeat customer | Customer with ≥ 2 distinct orders |
| Below reorder | `stock_level < reorder_point` |
| Inventory value | `stock_level × cost` |

---

## 8. Non-Functional Considerations

### Security

- API keys via environment variables only. Never in code or committed files.
- No user-supplied input reaches SQL directly. KPI functions use parameterized queries.
- `.env` always in `.gitignore`.
- FastAPI CORS whitelist limits browser access to `yashvajifdar.com` and `localhost:3000`.

### Scalability

- SQLite handles single-user demo load without issue.
- Replacing with Postgres or BigQuery requires no code changes beyond the connection string.
- FastAPI is async-ready; uvicorn can run multiple workers for concurrent requests.
- Streamlit is single-user by design. Multi-tenant production would use the FastAPI path.

### Observability (planned)

- Log every chat question, tool selected, and response time.
- Track per-answer feedback (thumbs up/down).
- Alert on data quality failures (null rate spikes, range violations).

### Data quality (planned)

- Null rate checks on `revenue`, `cost`, `customer_id` after every ingestion run.
- Range validation: `margin_pct` between 0 and 100, `revenue > 0`.
- Referential integrity: every `order_item.order_id` exists in `orders`.
- Drift detection: flag if monthly revenue deviates > 3σ from trailing average.
