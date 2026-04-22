# Lumber AI Analytics — Project Context

Read `../../CLAUDE.md` (Workspace root) first. This file adds project-specific context.

---

## Session Protocol — Do This Before Any Edit

Every session that touches this project follows the same four steps. State each one
explicitly in the first response. No edits land before the protocol clears.

### 1. Declare the task type

Classify the work in one line: `ai`, `data`, `docs`, `frontend`, `ops`, or `mixed`.

### 2. Load the matching standards

| Task type | Standards that must be loaded |
|---|---|
| `ai` (prompts, tool defs, engine code, evals) | `standards/engineering.md` + `standards/ai-engineering.md` |
| `data` (ETL, KPIs, schema, dbt, data quality) | `standards/engineering.md` + `standards/data-engineering.md` |
| `docs` (architecture, runbook, roadmap, ADRs, READMEs) | `standards/engineering.md` + `standards/writing.md` |
| `frontend` (Streamlit UI, Next.js pages, charts) | `standards/engineering.md` + `standards/frontend.md` |
| `ops` (deploy, env, runbook operational steps) | `standards/engineering.md` (operational excellence section) |
| `mixed` | Load every standard that applies. No shortcuts. |

### 3. Invoke the matching sub-agent for delegated specialist work

| Task type | Sub-agent |
|---|---|
| `ai` | `ai-engineer` |
| `data` | `data-engineer` |
| `docs` (internal technical docs) | `technical-writer` |
| `docs` (LinkedIn, outreach, brand content) | `linkedin-brand-agent` |
| Any code change, before commit | `doc-sync` |

Agents live in `~/.claude/agents/`. Full prompts load only on invocation — near-zero token cost.

### 4. Block on missing ADR

If the change involves a non-trivial design decision (new tool, new API surface,
swap of a core component, change of deploy target), write an ADR in `docs/decisions/`
before or alongside the code. `standards/engineering.md` requires this and it is
not negotiable on this project.

### Drift check at the end of every session

Before reporting "done," run the `doc-sync` agent against the four reference docs
(`architecture.md`, `roadmap.md`, `runbook.md`, `CLAUDE.md`). If drift is detected,
fix it in the same session. Drift fixed later is drift that never gets fixed.

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
  kpis.py             ← all business logic (13 KPI functions, no raw SQL in app layer)

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
6. `top_products_by_category(category, n)` — drill-down target from category pie chart
7. `top_customers(n)`
8. `customer_type_split()`
9. `top_customers_by_type(customer_type, n)` — drill-down target from customer-type pie chart
10. `repeat_customer_rate()`
11. `revenue_by_location(period)`
12. `inventory_health()`
13. `slow_moving_inventory()`

---

## Current Status

- [x] Data generator
- [x] ETL loader
- [x] 13 KPI functions (11 core + 2 drill-down)
- [x] Streamlit chat app (suggestion cards, follow-up chips)
- [x] Anthropic tool-use engine + Gemini engine (same interface)
- [x] Tests — 119 tests passing
- [x] README
- [x] FastAPI backend — `app/api.py`
- [x] FastAPI deployed on Render (free tier, auto-sleeps)
- [x] Personal website integration — yashvajifdar.com/demos/lumber
- [x] Chart drill-down (category → products, customer type → customers)
- [x] Docs — architecture.md, roadmap.md, runbook.md
- [x] ADRs in docs/decisions/ — 0001 (Render over Railway), 0002 (drill-down as scoped follow-up), 0003 (tool use over SQL generation)
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
| `docs/runbook.md` | Local dev, Render deploy, adding KPIs, troubleshooting |
| `docs/decisions/` | ADRs — 0001 Render, 0002 drill-down, 0003 tool-use |
