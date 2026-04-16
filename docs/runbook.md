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

**Expected:** 119 tests, 0 failures.

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

- `Procfile` — `web: uvicorn app.api:app --host 0.0.0.0 --port $PORT`
- `nixpacks.toml` — builds data at deploy time (generates `data/lumber.db`)
- `requirements.txt` — includes `fastapi` and `uvicorn`

### Deploy to Render

1. Go to [render.com](https://render.com) → **Sign up with GitHub** (free)

2. Click **New → Web Service**

3. Connect the `yashvajifdar/lumber-ai-analytics` GitHub repo

4. Fill in the settings:
   - **Name:** `lumber-ai-analytics`
   - **Region:** US East (or closest)
   - **Branch:** `main`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt && python etl/generate_data.py && python etl/loader.py`
   - **Start Command:** `uvicorn app.api:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free

5. Under **Environment Variables**, add:
   - `AI_PROVIDER` = `anthropic`
   - `ANTHROPIC_API_KEY` = `sk-ant-...` (from console.anthropic.com)

6. Click **Create Web Service** — build takes ~3–5 minutes

7. Copy the URL shown at the top: `https://lumber-ai-analytics.onrender.com`

### Test the backend

```bash
curl https://lumber-ai-analytics.onrender.com/health
# → {"status":"ok"}
# (first call after idle may take 30-60s — that's the cold start)
```

### Connect to Vercel

1. Go to [vercel.com](https://vercel.com) → `personal-website` → **Settings → Environment Variables**
2. Add:
   - Name: `LUMBER_API_URL`
   - Value: `https://lumber-ai-analytics.onrender.com`
   - Environment: Production
3. Click **Save**
4. Redeploy: **Deployments** → latest → **Redeploy** (or just push any commit to `main`)

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

---

## 12. If the Streamlit App Errors

1. Check the terminal for the Python traceback
2. If `data/lumber.db` is missing: run step 2
3. If the AI returns a 503: wait 30 seconds, retry — Gemini and Anthropic APIs occasionally overload
4. If follow-up chips raise `ValueError`: the session state has old string-format entries — restart Streamlit
