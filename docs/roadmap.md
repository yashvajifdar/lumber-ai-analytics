# Lumber AI Analytics — Working Backwards Plan

*Amazon-style working backwards: start with the customer experience, then build the plan.*

*Last updated: 2026-04-17 — post-Finetco meeting, next call scheduled. Partnership/distribution deal in discussion.*

---

## Press Release (Working Backwards)

FOR IMMEDIATE RELEASE

### Lumber Analytics AI Lets Yard Owners Ask Their Business Questions in Plain English

*Providence, RI* — Independent lumber and building supply operators can now connect their
existing sales, inventory, and customer data and ask questions like "Why did margin drop
last month?" or "Which products are slow-moving?" in natural language — and get instant,
accurate answers with supporting data.

The platform requires no technical staff. It connects to systems operators already use —
including Epicor BisTrack and common accounting exports — computes trusted business metrics,
and surfaces insights that previously required a data analyst or expensive BI software.

Early users report visibility they never had before: which contractor accounts are becoming
less active, which SKUs carry inventory cost without turning, and which locations are
underperforming on margin. Scheduled weekly digests land in the owner's inbox every Monday
morning, summarizing the prior week without anyone having to log in.

*"I used to spend an hour every Monday morning pulling numbers from three different places
just to understand last week. Now I ask a question and have the answer in seconds."*
— Pilot customer

---

## Platform Principles

These are non-negotiable constraints on every design decision.

**One platform, many businesses.** Data and connectors are swappable per client.
The KPI layer, AI engine, and infrastructure are shared. Adding client #2 means wiring a
new connector and a new `kpis.py` — not rebuilding the product.

**Trust is in the architecture.** The LLM never writes SQL and never touches raw data.
It selects from pre-defined, tested KPI functions with explicit parameters. If a function
doesn't exist for a question, the model says so. Hallucination is structurally prevented,
not patched.

**Scale at minimal cost.** SQLite for development. DuckDB or managed Postgres for
production scale. Serverless or free-tier compute where latency allows. API costs
(LLM, BisTrack) are passed to the client — they own their credentials. Our infrastructure
cost per client should stay under $100/month until significant query volume is proven.

**Operational excellence first.** Structured logging on every request. Health endpoints.
Automated data validation on every ETL run. Alerting before clients notice problems.
Runbook kept current. Every deploy is repeatable and documented.

**Security and privacy are not afterthoughts.** PII handling is defined before real data
is ingested. Security scanning runs in CI. Credentials never touch code or logs.
The platform must be auditable — clients need to trust that their business data stays theirs.

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

**Q: How does the platform support multiple businesses?**
A: Each client has a `DataSource` (their connector: BisTrack, CSV, QuickBooks) and a
`kpis.py` (their business logic). The AI engine, API, UI, and infrastructure are shared.
Switching context means pointing the engine at a different DataSource + KPI module.
No forking. No duplicating infrastructure.

**Q: Why not a general SQL query builder instead of fixed KPI functions?**
A: Free-form SQL generation is powerful but untrustworthy — the AI can generate plausible
but wrong queries, and there's no way to test every possible question in advance. Fixed KPI
functions with rich filter parameters give 95% of the expressiveness with 100% of the
auditability. Edge cases get new functions, not free-form SQL.

**Q: What about security and client data privacy?**
A: Client credentials (API keys, DB connections) live in environment variables — never in
code or logs. PII fields are identified and handled in the ETL layer before data reaches
the AI. Security scanning runs in CI to catch regressions. The platform is designed so
one client's data is never accessible to another.

**Q: How does someone access the demo?**
A: Two paths. (1) Run the Streamlit app locally — full chart rendering, full feature set.
(2) Visit yashvajifdar.com/demos/lumber — a Next.js chat page backed by the FastAPI API,
embedded in the personal brand site with consistent design.

---

## Milestones

### M0 — Foundation (complete)

- [x] Synthetic data generator (15 months, 200 customers, 20 SKUs, 9 sales reps)
- [x] ETL pipeline: CSV → transform → SQLite (customer_name flows through to fact_sales)
- [x] 15 trusted KPI functions in `metrics/kpis.py`
- [x] Streamlit chat app (suggestion cards, follow-up chips, chart rendering)
- [x] AI chat with Anthropic tool use (two-turn flow)
- [x] Google Gemini provider (same interface, one-line switch)
- [x] Test suite: 145 tests, 100% passing
- [x] Architecture and design documentation

### M1 — Demo-ready (complete)

- [x] README with architecture diagram and setup instructions
- [x] FastAPI backend (`app/api.py`) — `POST /ask`, `GET /health`
- [x] Personal website chat page (`yashvajifdar.com/demos/lumber`)
- [x] Next.js API proxy hiding backend URL from browser
- [x] GitHub repo: github.com/yashvajifdar/lumber-ai-analytics
- [x] Deploy FastAPI backend to Render (free, auto-sleeps)
- [x] Structured logging + user-friendly error messages
- [x] Chart rendering in Next.js demo (Recharts: bar, line, pie, horizontal bar)
- [x] Drill-down: category → products, customer type → customers
- [x] ADRs: 0001 (Render), 0002 (drill-down), 0003 (tool use over SQL generation)
- [ ] Record 3-minute demo video (walk through chat with real questions)

### M2 — Pilot engagement (target: Q2 2026)

*Client: Finetco (Bill + Ryan Finnegan) — 4-location building supply, New England/NY.*
*Next call scheduled. They are on Epicor BisTrack.*

**Go-to-market partnership (confirmed in second meeting):**
Finetco has agreed to co-build this service using their own use case as the reference
implementation — and in return will help market and refer the platform to the hundreds of
lumber and building supply contacts in their network. This changes the commercial structure:
Finetco is not just a paying client, they are a distribution partner and a reference customer.
Pricing and deal structure must reflect both the build contribution and the referral pipeline.
Nail the experience for them, and the funnel to 100s of similar businesses opens.

**Bill's top questions (received via email — map to KPI backlog):**

Analytics AI can answer today (synthetic data):
- Sales by location, by sales rep → `sales_by_rep` ✓ built
- Customers with less/no sales last period → `inactive_customers` ✓ built
- Top customers filtered by revenue threshold → `top_customers(min_revenue=X)` ✓ built

Needs real BisTrack schema before building (data not in synthetic model):
- Customer invoices by date paid, GM, net after discount/CC fee → needs AR/payment table
- Orders delivered by truck/driver, miles, duration → needs delivery table
- Picked by — SKUs and qty by person → needs picking log table
- Picking errors by person → needs error log table
- Time a ticket stays in each status → needs status change log
- By-location summary (orders, picks, deliveries, errors, cycle counts) → needs above tables

Automation (separate product surface — parking lot):
- AP automation, check processing, PO acknowledgment, quote entry, kitchen entry, take-off

**Before next meeting — demo goals:**
- [ ] Demo: filter parameters working in chat — show date range, location, rep, threshold queries
- [ ] Demo: `sales_by_rep` and `inactive_customers` live on website
- [ ] Prepare question list for next call: schema (tables, row counts, ERD), expected
      query volume, user count, BisTrack Epicor rep contact, their top 10 business questions
- [ ] Draft compute/API cost estimate sheet
- [ ] Draft partnership/commercial structure options (see M3 commercial section)

**Query expressiveness (complete):**
- [x] Filter parameters on all KPI tools: `date_from`, `date_to`, `location`, `customer_type`
- [x] Threshold filters: `min_revenue`, `min_orders`, `min_margin_pct`, `min_lifetime_revenue`
- [x] `sort_by` on top_customers, top_customers_by_type, sales_by_rep
- [x] New KPI: `sales_by_rep(location, date_from, date_to, customer_type, sort_by)`
- [x] New KPI: `inactive_customers(period, location, customer_type, min_lifetime_revenue)`
- [x] Customer names displayed in all customer KPIs and charts (not IDs)
- [ ] New KPI: `customer_cross_sell_gap(product_has, product_missing)` — "customers who bought X but not Y"

**Connector layer (blocked on BisTrack access details):**
- [ ] Research BisTrack API vs SQL Server direct access vs Smart Views — waiting for Finetco access info
- [ ] `DataSource` abstraction — design once connection method is confirmed
- [ ] CSV upload flow — works from their export files, no ERP integration needed
- [ ] ETL validation: row count checks, schema drift detection, alert on anomalies

**Onboarding:**
- [ ] Onboarding script: data audit → field mapping → ETL load → first session walkthrough
- [ ] Map Finetco's real table/column names to platform schema

**Collect feedback:**
- [ ] Document every question they ask that the platform can't answer → new KPI backlog
- [ ] Identify data quality issues in real data

### M3 — First paying client (target: Q3 2026)

**Scheduled AI reports:**
- [ ] Report engine: list of questions → run through AI engine → format as email digest
- [ ] Configurable schedule: daily or weekly per client preference
- [ ] Report questions defined by client (collect list at next Finetco meeting)
- [ ] Delivery: email (SendGrid or similar) and/or PDF download
- [ ] ADR for report scheduling approach (Render cron vs. standalone scheduler)

**Scale and storage:**
- [ ] Evaluate DuckDB vs managed Postgres for analytics at real data volumes
      (decision gates on Finetco's actual row counts and table count from schema audit)
- [ ] Migrate storage from SQLite to chosen target
- [ ] Connection pooling, query timeouts, graceful degradation under load
- [ ] Performance baseline: p50/p95 query latency targets defined and measured

**Security and privacy:**
- [ ] PII audit: identify sensitive fields in Finetco schema, mask/exclude from AI context
- [ ] Security scanner in CI (e.g., Bandit for Python, dependency vulnerability scan)
- [ ] Secrets audit: confirm no credentials in code, logs, or error messages
- [ ] Define data retention and deletion policy

**Product:**
- [ ] User auth — single login per client deployment
- [ ] Fix top issues from pilot feedback
- [ ] Add 3–5 new KPI functions from questions collected in M2

**Commercial:**
- [ ] Define partnership structure with Finetco — options to evaluate:
      (a) discounted/subsidized rate for Finetco in exchange for referrals + co-build input;
      (b) revenue share on referred clients (e.g., 10–15% of first-year contract per referral);
      (c) Finetco as formal reseller with margin built in.
      Do not lock in pricing before understanding the referral pipeline value.
- [ ] Standard pricing for referred clients: setup fee + monthly SaaS + optional support retainer
      (value anchor: replaces $60–80K/year part-time analyst; target $2,500–4,000/month per client)
- [ ] First invoice issued to Finetco
- [ ] First testimonial and reference case captured — this becomes the primary sales asset
      for the 100s of contacts in their network

### M4 — Platform hardening (target: Q4 2026)

- [ ] Multi-business support: one deployment can serve multiple clients;
      switching context = swapping DataSource + KPI module; no data bleed between clients
- [ ] ADR for multi-tenancy strategy (separate DBs vs. schema-per-client vs. row-level security)
- [ ] Penetration test / full security audit
- [ ] Privacy tooling: automated PII detection scan on incoming data
- [ ] Operational dashboard: request volume, error rates, query latency, ETL job health
- [ ] Alerting: ETL failures, API errors, and anomalous query patterns notify on-call
- [ ] Runbook updated to cover multi-client ops
- [ ] Second client onboarded (lumber or adjacent vertical — decision pending)

### M5 — SaaS / multi-vertical (target: 2027)

- [ ] Decision: stay lumber-focused (deep vertical) or expand (HVAC, distribution, field
      services) — Finetco engagement informs this; use them to surface every lumber pain point
- [ ] Self-serve onboarding flow (data upload → auto-mapping → live in <1 day)
- [ ] Each vertical ships as: `connectors/<vertical>/`, `metrics/<vertical>/kpis.py`,
      shared engine + infra
- [ ] Pricing tiers published; invoicing automated

---

## Parking Lot (future, not forgotten)

These items came up but are intentionally deferred until the right milestone.

| Item | Why deferred | When to revisit |
|---|---|---|
| Document matching / AP automation (invoice vs. receipt reconciliation, PO entry) | Valuable but a separate product surface — requires understanding their AP workflow first | After M3; treat as a second module, not part of analytics platform |
| QuickBooks export parser | Lower priority than BisTrack for Finetco; still needed for SMBs without an ERP | M2 or M3 depending on Finetco's actual accounting setup |
| 50+ table schema support | Real scope TBD — client may be overestimating; schema audit in M2 will clarify | M3 storage migration; only ingest analytics-relevant tables |
| Demo video | M1 remaining item, easy win | Before next Finetco demo |

---

## Task Breakdown (M2 pre-meeting sprint)

| Task | Est. | Notes |
|---|---|---|
| Prepare question list for next Finetco meeting | 30m | Schema, volume, BisTrack rep, their top 10 questions |
| Filter parameters on KPI tools | 3–4h | `date_from`, `date_to`, `location`, `customer_type`, `product_category` |
| `customer_cross_sell_gap` KPI function | 2h | New function + test coverage |
| `DataSource` abstraction layer | 2–3h | Interface only; BisTrack + CSV as first implementations |
| Draft cost estimate sheet | 1h | LLM tokens × query volume; infra fixed costs |
| Record demo video | 1h | M1 remaining item — do before next call |

---

## Parallelization Plan (if headcount available)

```text
Engineer A (Senior DE / you)
  → Architecture, ETL, connector layer, AI engine
  → Technical decisions, code review, standards, ADRs

Engineer B (Full-stack / Mid-level)
  → Scheduled report engine, email delivery
  → UI: filter controls, report preview, onboarding flow

Engineer C (Data / Analytics)
  → New KPI functions from client question backlog
  → Schema mapping, data quality checks, PII audit

TPM (or you wearing the hat)
  → Roadmap, milestone tracking
  → Client communication, question collection, feedback loops
  → Pricing and commercial structure
```

**Key parallelization principle:** Engineers B and C can work independently once the
`DataSource` interface and KPI function signatures with filter parameters are locked.
Lock those first.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real data is messier than synthetic | High | High | Schema audit before any ETL work; CSV flow first |
| Client's 50+ tables creates scope creep | High | Medium | Audit tables upfront; ingest only analytics-relevant tables; defer rest |
| BisTrack API gated behind Epicor rep | Medium | Medium | Ask Finetco to initiate with their rep at next meeting |
| Client doesn't maintain data discipline | Medium | Medium | Automated ETL validation + weekly alerts |
| AI gives a wrong answer on real data | Medium | High | KPI functions are the only data path; review and test all functions against real schema before go-live |
| Security vulnerability exposes client data | Low | High | Security scanner in CI from M3; PII audit before real data ingested |
| First client churns before testimonial | Low | High | Under-promise, over-deliver. Be the analyst they can't afford. |
| LLM/API costs spike unexpectedly | Low | Medium | Client owns their API key; cost transparency sheet shared upfront |
| POS/ERP integration takes 3× longer than expected | High | Medium | DataSource abstraction means CSV fallback always works; integration is not on the critical path |
| FastAPI backend goes down mid-demo | Low | High | Streamlit Cloud as backup demo path |
| Finetco partnership loses momentum before first invoice | Medium | High | Keep meeting cadence tight; deliver demo wins at every call; get commercial terms in writing before M3 |
| Referral pipeline doesn't materialize | Medium | Medium | Don't build the business plan around referrals until 2–3 actual referrals land; Finetco's value as a reference case is real regardless |
| Pricing anchored too low before deal is signed | Medium | High | Do not name a number until partnership structure is clear; present options, not a price |

---

## Definition of Success at Each Stage

**M1 success:** Someone with no context visits yashvajifdar.com/demos/lumber and says
"I'd pay for that."

**M2 success:** A real business owner (Finetco) uses the product without hand-holding,
asks a question we haven't pre-built, and we build the KPI function for them within 24 hours.

**M3 success:** First invoice paid. Scheduled weekly report lands in the owner's inbox
without any manual work. First testimonial captured.

**M4 success:** Two clients running on the same infrastructure. Adding a third client takes
less than one day of engineering. Security audit passed with no critical findings.

**M5 success:** The business logic for each vertical fits in its own `metrics/<vertical>/kpis.py`.
The infrastructure is shared. We are a platform, not a consulting engagement. At least 5 clients
came in through the Finetco referral network. The reference case sells itself.
