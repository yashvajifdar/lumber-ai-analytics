# Lumber AI Analytics — Project Context

**Standards to load:** `standards/engineering.md` + `standards/data-engineering.md` + `standards/ai-engineering.md`

Read workspace `CLAUDE.md` for who Yash is and the file map. This file is project-specific context only.

---

## What This Is

A consulting demo and portfolio piece: an end-to-end analytics platform for
lumber / building supply businesses. Demonstrates:

- Data engineering: synthetic data generation, ETL pipeline, SQLite warehouse
- Analytics: 11 trusted KPI functions, metrics layer
- AI: natural language querying routed to analytics functions via Anthropic tool use
- Product: Streamlit chat UI (local) + Next.js chat page at yashvajifdar.com/demos/lumber

**Framing:** This is an analytics platform with a chat interface,
not "a chatbot." The data model is the product.

---

## Architecture

```
etl/
  generate_data.py    ← synthetic data (200 customers, 20 SKUs, ~4K orders, 15 months)
  loader.py           ← ETL: CSV → transform → SQLite

metrics/
  kpis.py             ← all business logic (11 KPI functions, no raw SQL in app layer)

app/
  main.py             ← Streamlit: chat-only UI
  api.py              ← FastAPI: POST /ask, GET /health (for personal website)
  engine_factory.py   ← build_engine() — reads AI_PROVIDER, returns engine instance
  engine_tools.py     ← shared: TOOL_DEFINITIONS, CHART_SPECS, KPI_DISPATCH, ChatResult
  anthropic_engine.py ← AnthropicEngine: two-turn tool-use flow
  gemini_engine.py    ← GeminiEngine: same interface, Google provider
  chart_builder.py    ← build_chart(df, spec) → Plotly figure

tests/
  conftest.py         ← shared fixtures (in-memory SQLite, deterministic data)
  test_etl.py         ← ETL transformation tests
  test_kpis.py        ← KPI function tests (known-value assertions)
  test_chat_engine.py ← AI engine tests (mocked API)

data/
  raw/                ← generated CSVs (not committed)
  lumber.db           ← SQLite warehouse (not committed)
```

---

## Data Model

Core tables in `lumber.db`:

- `customers` — 200 customers (120 contractors, 80 retail)
- `products` — 20 SKUs across 8 categories
- `orders` — ~3,900 orders (Jan 2024 – Mar 2025)
- `order_items` — ~19,700 line items with revenue, COGS, margin
- `inventory` — 60 SKU-location records
- `fact_sales` — denormalized, completed orders only (main analytics table)
- `daily_summary` — pre-aggregated daily metrics

---

## Current KPI Functions

In `metrics/kpis.py`:

1. `revenue_over_time(period)` — day/week/month
2. `margin_trend(period)`
3. `top_products(n, by)`
4. `bottom_margin_products(n)`
5. `revenue_by_category()`
6. `top_customers(n)`
7. `customer_type_split()`
8. `repeat_customer_rate()`
9. `revenue_by_location(period)`
10. `inventory_health()`
11. `slow_moving_inventory()`

---

## Current Status

- [x] Data generator
- [x] ETL loader
- [x] 11 KPI functions
- [x] Streamlit chat app (suggestion cards, follow-up chips)
- [x] Anthropic tool-use engine + Gemini engine (same interface)
- [x] Tests — 119 tests passing
- [x] README
- [x] FastAPI backend — `app/api.py`
- [x] Personal website integration — yashvajifdar.com/demos/lumber
- [x] Docs — architecture.md, roadmap.md, runbook.md
- [ ] Deploy FastAPI to Railway
- [ ] Demo video

---

## How to Run

```bash
cd /Users/yashvajifdar/Workspace/projects/lumber-ai-analytics
source venv/bin/activate
python etl/generate_data.py   # generate CSVs
python etl/loader.py          # load to SQLite
streamlit run app/main.py     # Streamlit chat UI (localhost:8501)
uvicorn app.api:app --reload --port 8001  # FastAPI backend (localhost:8001)
```

Tests:

```bash
python -m pytest tests/ -v
```

Full procedures: `docs/runbook.md`

---

## Key Docs

| Doc | Purpose |
| --- | --- |
| `docs/architecture.md` | System design, decisions, tradeoff tables |
| `docs/roadmap.md` | Milestones, press release, risks |
| `docs/runbook.md` | Local dev, Railway deploy, adding KPIs, troubleshooting |
