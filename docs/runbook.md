# Lumber AI Analytics — Operations Runbook

Step-by-step procedures for every operational task on this project.
If something breaks or needs changing, this is the first place to look.

---

## 1. Prerequisites

```bash
# Activate the venv before every session — all commands below assume it is active
cd /path/to/lumber-ai-analytics
source venv/bin/activate
# Prompt shows (venv) when active. If you see ModuleNotFoundError, the venv is not active.
```

---

## 2. Generate Data and Run ETL

Run these once to create `data/lumber.db`. Re-run only if you want a fresh dataset.

```bash
python etl/generate_data.py   # writes CSVs to data/raw/
python etl/loader.py          # transforms CSVs → SQLite at data/lumber.db
```

The database is gitignored. Every developer (and every CI run) generates their own.

---

## 3. Start the Streamlit App

```bash
streamlit run app/main.py
```

Opens at <http://localhost:8501>. Requires `data/lumber.db` to exist (run step 2 first).

---

## 4. Start the FastAPI Backend

```bash
uvicorn app.api:app --reload --port 8001
```

- Health check: <http://localhost:8001/health>
- Interactive API docs: <http://localhost:8001/docs>
- The `--reload` flag restarts automatically on code changes (development only).

To test the API locally from the personal website, set `LUMBER_API_URL=http://localhost:8001`
in `personal-website/.env.local`, then run `npm run dev` in that project.

---

## 5. Run Tests

```bash
# All tests
python -m pytest tests/ -v

# Single module
python -m pytest tests/test_kpis.py -v
python -m pytest tests/test_etl.py -v
python -m pytest tests/test_chat_engine.py -v

# Quiet (just pass/fail counts)
python -m pytest tests/ -q
```

Tests use an in-memory SQLite DB with deterministic data — no `.env` required,
no production DB touched, no real API calls made.

**Expected:** 157 tests, 0 failures.

---

## 6. Adding a New KPI Function

Follow all six steps — skipping any one will break the AI routing or chart rendering.

1. **Add the function** to `metrics/kpis.py`
   - Accept only simple scalar arguments (`n: int`, `period: str`, etc.)
   - Always return a `pd.DataFrame`
   - Use only `fact_sales` or core tables — no raw order data

2. **Add a tool definition** to `TOOL_DEFINITIONS` in `app/engine_tools.py`
   - Use JSON Schema under `"parameters"` (not Anthropic-specific format)
   - Write a clear `"description"` — the LLM reads this to decide when to use the tool

3. **Add a chart spec** to `CHART_SPECS` in `app/engine_tools.py`
   - Keys must match DataFrame column names from step 1
   - Supported types: `bar`, `line`, `horizontal_bar`, `pie`, `scatter`, `line_multi`, `table`

4. **Add to dispatch table** — `KPI_DISPATCH` in `app/engine_tools.py`
   - Maps tool name → KPI function

5. **Add follow-up suggestions** — `FOLLOW_UP_SUGGESTIONS` in `app/engine_tools.py`
   - Each entry: `(short_label, full_question)` tuple
   - Short label shown in UI; full question sent to the engine

6. **Write tests** in `tests/test_kpis.py`
   - Use the `db` fixture from `conftest.py`
   - Assert on known values, not just row counts

7. **If the new KPI is a drill-down target:** also add `drill_key` and `drill_question`
   to the *parent* chart's spec in `CHART_SPECS`. Example: a slice click on the category
   pie chart resolves `"Show me the top products in {category}"` and posts it to `/ask`
   as a normal question. See §6a below for the full pattern.

---

## 6a. Chart Drill-Down Pattern

Drill-down is a templated follow-up question, not a separate code path. Every answer,
whether typed or clicked, runs through the same tool-use loop.

### How to make a chart drill-capable

1. Write a KPI function that accepts the filter parameter (e.g. `top_products_by_category(category, n)`).
2. Register the tool and dispatch entry as usual (§6 steps 2–4).
3. On the *parent* chart spec in `CHART_SPECS`, add two keys:
   ```python
   "drill_key": "category",                                  # column in the parent DataFrame
   "drill_question": "Show me the top products in {category}"  # template
   ```
4. The frontend (Next.js or Streamlit) reads these on click, substitutes the clicked value,
   and posts the resolved question to the engine. No frontend logic changes.

### Current drill-capable charts

| Parent chart | Drill key | Drill target KPI |
| --- | --- | --- |
| `get_revenue_by_category` (pie) | `category` | `get_top_products_by_category` |
| `get_customer_type_split` (pie) | `type` | `get_top_customers_by_type` |

### Why this pattern

One model of execution for every answer. Every result is produced by a tested KPI
function called via tool use against the LLM. A clicked drill-down is just a question
the user did not have to type. Frontend stays thin; new drill-down scenarios ship by
adding backend code only.

---

## 7. Adding a New AI Provider

1. Create `app/<provider>_engine.py` — implement a class with:

   ```python
   def ask(self, question: str, history: list[dict] | None = None) -> ChatResult:
       ...
   ```

2. Add a branch in `build_engine()` in `app/engine_factory.py`
3. Add the new `AI_PROVIDER` value to `.env.example`
4. All tests that mock the engine should still pass — the interface is `ChatResult`

---

## 8. Switching AI Provider Locally

Edit `.env`:

```bash
AI_PROVIDER=anthropic   # or: gemini
ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AIza...  # only if using gemini
```

Restart the Streamlit app or FastAPI server. No code changes needed.

---

## 9. Deploying the FastAPI Backend

**Target: Render free tier** — auto-sleeps after 15 minutes of inactivity, wakes on the
next request. No always-on cost. Perfect for a demo app.

> **Why not Railway?** Railway runs containers 24/7 — no auto-sleep, continuous compute
> cost even with zero traffic. Render's free tier gives sleep-on-idle behavior by default.
>
> **Trade-off:** First request after the service has been idle takes 30–60 seconds (cold
> start while Render wakes the container). Subsequent requests are fast. The `/demos/lumber`
> proxy has a 30-second timeout, so cold starts are handled gracefully.

### What's already in the repo

No files to create — everything is committed:

- `render.yaml` — defines build command, start command, and required env vars in code
- `Procfile` — fallback start command (used if Render doesn't pick up `render.yaml`)
- `requirements.txt` — all dependencies including `fastapi`, `uvicorn`, and AI SDKs

**Why `render.yaml`?** The SQLite database (`data/lumber.db`) is gitignored — it's a
generated artifact, not source data. Without a build step, Render has no database and
every KPI query fails with `no such table: fact_sales`. The build command runs the full
ETL pipeline so the database exists before the server starts.

### Deploy to Render

1. Go to [render.com](https://render.com) → **Sign up with GitHub** (free)

2. Click **New → Web Service**

3. Connect the `yashvajifdar/lumber-ai-analytics` GitHub repo

4. Render will detect `render.yaml` and pre-fill build/start commands automatically.
   Confirm the settings:
   - **Name:** `lumber-ai-analytics`
   - **Region:** US East (or closest)
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt && python etl/generate_data.py && python etl/loader.py`
   - **Start Command:** `uvicorn app.api:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free

5. Under **Environment Variables**, add your API key (never committed):
   - `GOOGLE_API_KEY` = your Gemini key (from [aistudio.google.com](https://aistudio.google.com))
   - `AI_PROVIDER` is already set to `gemini` in `render.yaml`

   > To switch to Anthropic: change `AI_PROVIDER` to `anthropic` and add `ANTHROPIC_API_KEY` instead.
   > No code changes needed — `engine_factory.py` handles the switch.

6. Click **Create Web Service** — build takes ~3–5 minutes on free tier
   (installing dependencies + running ETL on every deploy)

7. Copy the URL: `https://lumber-ai-analytics.onrender.com`

### Test the backend

```bash
curl https://lumber-ai-analytics.onrender.com/health
# → {"status":"ok"}
# (first call after idle may take 30–60s — that's the cold start)
```

If the service starts but `/ask` returns 500, check the Render logs. A `RuntimeError`
at startup means the API key env var is missing or not being found. The server will refuse
to start rather than serve broken requests — this is intentional (fail-fast pattern).

### Connect to Vercel

1. Go to [vercel.com](https://vercel.com) → `personal-website` → **Settings → Environment Variables**
2. Add:
   - Name: `LUMBER_API_URL`
   - Value: `https://lumber-ai-analytics.onrender.com`
   - Environment: Production
3. Click **Save**
4. Redeploy: **Deployments** → latest → **Redeploy** (or push any commit to `main`)

### Verify end-to-end

Visit [yashvajifdar.com/demos/lumber](https://yashvajifdar.com/demos/lumber) and ask
"How has revenue trended this year?" — you should get an AI response within ~10 seconds
(or ~60 seconds if the Render service is waking from sleep).

---

## 10. Regenerating Synthetic Data

The data generator produces deterministic-ish data but adds some randomness. If you need
a fully reproducible dataset, set the seed explicitly in `etl/generate_data.py`.

```bash
python etl/generate_data.py   # regenerate CSVs
python etl/loader.py          # reload into SQLite
```

**Do not commit** `data/raw/` or `data/lumber.db` — both are gitignored.

---

## 11. If Tests Fail

**Check first:** Is the venv active?

```bash
which python  # should show .../venv/bin/python
```

**Common causes:**

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError` | venv not active | `source venv/bin/activate` |
| `no such table: fact_sales` | DB not generated | Run step 2 |
| `ANTHROPIC_API_KEY not set` | Missing `.env` | `cp .env.example .env` + fill in key |
| AI engine tests fail | `load_dotenv()` timing | Check `engine_factory.py` — `load_dotenv()` must be at module level |
| Follow-up chips crash | Stale session state format | Restart Streamlit; the defensive unpacking handles mixed formats |
| Render: `RuntimeError: Engine failed to initialize` | API key env var not set on Render | Go to Render dashboard → Environment → add `GOOGLE_API_KEY` or `ANTHROPIC_API_KEY` |
| Render: `no such table: fact_sales` | ETL never ran — database doesn't exist on server | Confirm build command in Render includes `python etl/generate_data.py && python etl/loader.py`; check `render.yaml` is detected |
| Render: 502 on first load | Service was restarting or waking from sleep | Wait 30–60 seconds and retry; 502 during a deploy is normal |

---

## 12. If the Streamlit App Errors

1. Check the terminal for the Python traceback
2. If `data/lumber.db` is missing: run step 2
3. If the AI returns a 503: wait 30 seconds, retry — Gemini and Anthropic APIs occasionally overload
4. If follow-up chips raise `ValueError`: the session state has old string-format entries — restart Streamlit
