# Lumber AI Analytics — Project Context

**Standards to load:** `standards/engineering.md` + `standards/data-engineering.md` + `standards/ai-engineering.md`

Read workspace `CLAUDE.md` for who Yash is and the file map. This file is project-specific context only.

---

## What This Is

A consulting demo and portfolio piece: an end-to-end analytics platform for
lumber / building supply businesses. Demonstrates:

- Data engineering: synthetic data generation, ETL pipeline, SQLite warehouse
- Analytics: 10+ trusted KPI functions, metrics layer
- AI: natural language querying routed to analytics functions
- Product: Streamlit chat interface — natural language questions, AI answers with charts

**Framing:** This is an analytics platform with a chat interface,
not "a chatbot." The data model is the product.

---

## Architecture

```
etl/
  generate_data.py    ← synthetic data (200 customers, 20 SKUs, ~4K orders, 15 months)
  loader.py           ← ETL: CSV → transform → SQLite

metrics/
  kpis.py             ← all business logic (10 KPI functions, no raw SQL in app layer)

app/
  main.py             ← Streamlit: Chat-only interface

tests/
  conftest.py         ← shared fixtures
  test_kpis.py        ← KPI function tests
  test_etl.py         ← transformation tests

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
- [x] KPI functions
- [x] Streamlit app (chat-only)
- [x] Basic chat with keyword routing
- [x] Tests — 112 tests passing (test_etl.py, test_kpis.py, test_chat_engine.py, conftest.py)
- [x] Anthropic API integration — tool use, ChatEngine, chart_builder
- [x] Architecture doc — docs/architecture.md (design decisions, tradeoffs, modular replacement guide)
- [x] Working backwards plan — docs/working_backwards.md (milestones, task breakdown, parallelization)
- [ ] README
- [ ] Deploy to shareable URL (Streamlit Cloud or Fly.io)
- [ ] Demo video

---

## What to Build Next

1. ~~Write tests~~ — done, 81/81 passing
2. Add Anthropic API to chat page for real NL understanding
3. Write README
4. Polish demo flow

---

## How to Run

```bash
cd /Users/yashvajifdar/Workspace/projects/lumber-ai-analytics
source venv/bin/activate
python etl/generate_data.py   # generate CSVs
python etl/loader.py          # load to SQLite
streamlit run app/main.py     # start app
```

Tests:
```bash
pytest tests/ -v
```

---

## Design Decisions

**Why SQLite (not Postgres)?**
Demo/portfolio context. The architecture is identical to a Postgres or BigQuery
backend — swap the connection string. SQLite removes infrastructure setup friction.

**Why keyword routing in chat (not free-form SQL)?**
Trust. A chatbot that sometimes gives wrong financial answers is unusable.
Routing to trusted KPI functions guarantees correct results.
LLM is added for language understanding, not query generation.

**Why Streamlit (not React)?**
Speed to demo. Streamlit lets a data engineer build a working, professional-looking
app without frontend infrastructure. For a client pitch this is sufficient.
A production version would use a proper frontend.
