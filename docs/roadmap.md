# Lumber AI Analytics — Working Backwards Plan

*Amazon-style working backwards: start with the customer experience, then build the plan.*

---

## Press Release (Working Backwards)

FOR IMMEDIATE RELEASE

### Lumber Analytics AI Lets Yard Owners Ask Their Business Questions in Plain English

*Providence, RI* — Independent lumber and building supply operators can now connect their
existing sales, inventory, and customer data and ask questions like "Why did margin drop
last month?" or "Which products are slow-moving?" in natural language — and get instant,
accurate answers with supporting data.

The platform requires no technical staff. It connects to systems operators already use,
computes trusted business metrics, and surfaces insights that previously required a data
analyst or expensive BI software.

Early users report visibility they never had before: which contractor accounts are becoming
less active, which SKUs carry inventory cost without turning, and which locations are
underperforming on margin.

*"I used to spend an hour every Monday morning pulling numbers from three different places
just to understand last week. Now I ask a question and have the answer in seconds."*
— Pilot customer

---

## FAQ (Internal)

**Q: Why synthetic data first?**
A: Data availability is a legal, privacy, and security problem before it is a technical one.
Rather than block the entire engineering effort on data access approvals, we built the pipeline
against a synthetic dataset that mirrors real business schema and patterns. When a pilot client
connects real data, only the ingestion layer changes. Everything else ships.

**Q: Why not just build a dashboard?**
A: Static dashboards require users to know what to look for. Business owners want answers,
not charts. The AI layer converts natural language questions into trusted KPI queries — giving
the owner analyst-level insight without analyst-level skill.

**Q: What stops the AI from giving wrong answers?**
A: The LLM never writes SQL or accesses raw data. It selects from pre-defined, tested KPI
functions. If a function doesn't exist for a question, the model says so rather than
hallucinating. Trust is built into the architecture, not patched on top of it.

**Q: How does someone access the demo?**
A: Two paths. (1) Run the Streamlit app locally — full chart rendering, full feature set.
(2) Visit yashvajifdar.com/demos/lumber — a Next.js chat page backed by the FastAPI API,
embedded in the personal brand site with consistent design.

---

## Milestones

### M0 — Foundation (complete)

- [x] Synthetic data generator (15 months, 200 customers, 20 SKUs)
- [x] ETL pipeline: CSV → transform → SQLite
- [x] 11 trusted KPI functions in `metrics/kpis.py`
- [x] Streamlit chat app (suggestion cards, follow-up chips, chart rendering)
- [x] AI chat with Anthropic tool use (two-turn flow)
- [x] Google Gemini provider (same interface, one-line switch)
- [x] Test suite: 119 tests, 100% passing
- [x] Architecture and design documentation

### M1 — Demo-ready (complete)

- [x] README with architecture diagram and setup instructions
- [x] FastAPI backend (`app/api.py`) — `POST /ask`, `GET /health`
- [x] Personal website chat page (`yashvajifdar.com/demos/lumber`)
- [x] Next.js API proxy hiding backend URL from browser
- [x] GitHub repo: github.com/yashvajifdar/lumber-ai-analytics
- [ ] Deploy FastAPI backend to Railway — **next action**
- [ ] Record 3-minute demo video (walk through chat with real questions)

### M2 — Pilot client (target: Q2 2026)

- [ ] Finetco (Ryan Finnegan) — 4-location building supply, New England/NY — demo shared, next steps sent
- [ ] CSV upload flow (no integration required — just upload exports from their system)
- [ ] QuickBooks export parser (most SMBs use QuickBooks)
- [ ] Onboarding script: data audit → mapping → load → first session
- [ ] Collect feedback: which questions matter most, where data breaks

### M3 — First paying client (target: Q3 2026)

- [ ] Fix top issues from pilot feedback
- [ ] Add 3–5 new KPI functions based on real questions asked
- [ ] Move storage to Postgres (pilot scale, concurrent users)
- [ ] Add user auth (single login, one client per deployment)
- [ ] Price the service and invoice the first client

### M4 — Second vertical (target: Q4 2026)

- [ ] Identify second vertical (field services, HVAC/contractor, or distribution)
- [ ] Clone project, adapt schema and KPIs for new domain
- [ ] Build client #2 based on what worked in M3

---

## Task Breakdown (M1 remaining)

| Task | Est. | Notes |
| --- | --- | --- |
| Deploy FastAPI to Railway | 1h | See `docs/runbook.md` section 9 |
| Set `LUMBER_API_URL` in Vercel | 15m | Vercel → personal-website → Settings → Env vars |
| Record demo video | 1h | Screen + voiceover, 3 min max |
| Add Streamlit Cloud deploy | 1h | Secondary path for Python-native demo |

---

## Parallelization Plan (if headcount available)

```text
Engineer A (Senior DE / you)
  → Architecture, ETL, metrics layer, AI integration
  → Technical decisions, code review, standards

Engineer B (Full-stack / Mid-level)
  → Frontend polish, React chart components, UI improvements
  → Onboarding flow, CSV upload UX

Engineer C (Data / Analytics)
  → New KPI functions per client feedback
  → Data quality checks, schema validation
  → QuickBooks / POS connector research

TPM (or you wearing the hat)
  → Working backwards doc (this file)
  → Milestone tracking
  → Client communication and feedback loops
  → Demo coordination
```

**Key parallelization principle:** Engineers B and C can work independently once the
data contract (`fact_sales` schema) and metrics interface (KPI function signatures) are locked.
That happens in M0. Everything in M1+ can be parallelized against those contracts.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Real data is messier than synthetic | High | High | CSV upload flow first, not live integration |
| Client doesn't maintain data discipline | Medium | Medium | Weekly automated validation + alerts |
| AI gives a wrong answer on real data | Medium | High | KPI functions are the only data path — review them first |
| First client churns before we get testimonial | Low | High | Under-promise, over-deliver. Be the analyst they can't afford. |
| POS integration takes 3x longer than expected | High | Medium | Don't build integrations until post-M3 |
| FastAPI backend goes down mid-demo | Low | High | Deploy Streamlit Cloud as backup demo path |

---

## Definition of Success at Each Stage

**M1 success:** Someone with no context visits yashvajifdar.com/demos/lumber and says
"I'd pay for that."

**M2 success:** A real business owner (Finetco or similar) uses the product without
hand-holding and finds a real insight they didn't have before.

**M3 success:** First invoice paid. First testimonial received.

**M4 success:** The business logic for each vertical fits in its own `metrics/kpis.py`.
The infrastructure is shared. We are building a platform, not one-off projects.
