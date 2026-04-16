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

**Target:** Railway (free tier, recommended) or Render (free tier).

### What's already done

The deploy config is committed and pushed — no files to create:

- `Procfile` — tells Railway how to start the app
- `nixpacks.toml` — tells Railway to run ETL at build time (generates `data/lumber.db`)
- `requirements.txt` — includes `fastapi` and `uvicorn`
- Railway CLI installed at v4.37.4 via `npm install -g @railway/cli`

### Railway login workaround

The default `railway login` browser callback sometimes fails silently.
If `railway login` says "Unauthorized" after the browser step:

1. Go to [railway.app](https://railway.app) → sign in with GitHub
2. Go to **Account Settings → Tokens** → **Create Token** → name it `cli`
3. Copy the token
4. In terminal: `railway login --token YOUR_TOKEN_HERE`

Verify it worked: `railway whoami` should print your email.

### Deploy

```bash
cd /Users/yashvajifdar/Workspace/projects/lumber-ai-analytics

# Authenticate (see workaround above if browser flow fails)
railway login

# Create a new Railway project (run once)
railway init
# → Select "Empty Project"
# → Name it: lumber-ai-analytics

# Deploy
railway up
```

Railway runs the `nixpacks.toml` build steps (install deps + generate data + load SQLite),
then starts the server with the `Procfile` command. Build takes ~2–3 minutes.

After `railway up` completes:

```bash
railway domain   # prints your app URL, e.g. https://lumber-ai-XXXXX.up.railway.app
```

### Set environment variables in Railway dashboard

1. Go to [railway.app](https://railway.app) → your project → **Variables**
2. Add:
   - `AI_PROVIDER` = `anthropic`
   - `ANTHROPIC_API_KEY` = `sk-ant-...` (from console.anthropic.com)
3. Click **Deploy** to restart with the new vars

### Test the backend

```bash
curl https://lumber-ai-XXXXX.up.railway.app/health
# → {"status":"ok"}
```

The deployed URL looks like `https://lumber-ai-XXXXX.up.railway.app`.

### After deployment — connect to Vercel

1. In Vercel → `personal-website` → **Settings → Environment Variables** → add:
   ```text
   LUMBER_API_URL = https://your-app.up.railway.app
   ```
2. Redeploy the personal website (or it will pick up on next push to `main`)

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
