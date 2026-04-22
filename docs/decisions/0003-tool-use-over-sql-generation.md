# ADR-0003: Tool Use over SQL Generation for Natural Language Queries

**Date:** 2026-04-17
**Status:** Accepted
**Owner:** Yash Vajifdar

## Context

The core product feature is a chat interface that answers business questions about lumber
sales data in natural language. The system needs a strategy for translating a user's
question into a data result.

Two plausible approaches exist. The choice is architectural: it shapes how the system is
tested, how it fails, how it is extended, and what the AI layer is actually responsible for.

This decision was made before the first line of engine code was written. It is documented
here because the rationale was not written down at the time and two subsequent design
choices (drill-down via templated follow-up, Gemini as a second provider) both relied on
the same foundation.

## Options Considered

### 1. LLM generates SQL

The user's question is passed to an LLM. The LLM generates a SQL query against the
`lumber.db` schema. The query runs. The result is returned and formatted.

**For:**
- Zero boilerplate. Any question the LLM can express in SQL is answerable without
  writing a new function.
- Appears to scale — adding a new metric does not require a new function.

**Against:**

_Correctness is unverifiable._ Generated SQL is not owned code. There is no systematic
way to assert that "what was our best month?" produces the same SQL — or the same result
— across model versions, prompt changes, or schema updates. The only test is "does it
look right," which is not a test.

_Silent wrong answers are the worst failure mode._ An LLM-generated query that runs
without error but joins on the wrong column, aggregates at the wrong grain, or misreads
a schema column name produces a confident, formatted, wrong answer. The user does not
know. There is no test that catches it. The system appears to work until a sophisticated
user notices the number is wrong.

_The LLM must know the schema._ To generate SQL, the LLM must be told the full table
structure: column names, types, foreign keys, what each column means. This is schema
knowledge in the prompt, which means any schema change requires a prompt update, and
any prompt truncation silently degrades query quality.

_No provider abstraction._ SQL generation is tightly coupled to the LLM's output format
and its understanding of this specific schema. Switching providers means re-validating
every query pattern. There is no interface to test against.

_Not evaluable._ You cannot write a test suite for "does the LLM generate correct SQL."
You can write evals, but they are probabilistic, expensive to run, and do not give you
a binary pass/fail on correctness.

### 2. LLM selects a tool; tool calls a deterministic KPI function

The user's question is passed to an LLM along with a set of tool definitions — one per
KPI. The LLM selects the right tool and supplies parameters. The system calls the
registered KPI function, which owns its own SQL. The result is passed back to the LLM
for formatting.

**For:**

_The KPI function is tested code._ `revenue_over_time("month")` is a Python function
with a unit test that asserts the result matches known values. The SQL is written once,
reviewed once, and does not change unless the schema changes. The test catches regressions.

_The LLM's responsibility is narrow and evaluable._ Did it select the right tool? Did
it supply the right parameter? These are binary questions. A five-query eval catches
routing regressions. Tool selection accuracy is measurable; SQL correctness is not.

_Schema knowledge stays in the metrics layer._ The LLM sees tool descriptions and
parameter names (`period: "month" | "week" | "day"`), not column names and foreign keys.
Schema changes do not require prompt changes unless the function's interface changes.

_Provider abstraction falls out naturally._ `TOOL_DEFINITIONS` is in JSON Schema format,
not Anthropic's wire format. `AnthropicEngine` and `GeminiEngine` both import from the
same definitions and convert to their own format. Adding a new provider is one new file.
The KPI functions do not know which provider called them.

_Auditable._ Every answer traces to a function call: which tool, which parameters, which
function, which SQL. A support request ("your revenue number is wrong") has a clear
investigation path.

**Against:**

_Every new metric requires a new function._ The system cannot answer a question for
which no KPI function exists. An open-ended query ("what is happening with Product X in
the Northwest?") that does not map to a registered tool returns a "I don't have a
function for that" response rather than an improvised answer.

_Tool definition maintenance._ As the function library grows, the tool list grows. The
LLM's ability to select the right tool from a large set degrades if descriptions are
ambiguous. This requires discipline in writing tool descriptions and periodic eval
as the library expands.

## Decision

Ship option 2: tool use over SQL generation.

The metrics layer owns all business logic. The AI layer owns intent understanding and
response formatting. These are two different jobs and they should not share code or
responsibility.

The concrete implementation:
- All KPI functions live in `metrics/kpis.py`
- All tool definitions live in `app/engine_tools.py` as `TOOL_DEFINITIONS` in JSON Schema
- All dispatch lives in `KPI_DISPATCH` — a dict from tool name to function
- `AnthropicEngine` and `GeminiEngine` convert `TOOL_DEFINITIONS` to provider format at startup
- No SQL appears in `app/` outside of `engine_tools.py`, and no SQL appears there —
  it is in `metrics/kpis.py` only

## Consequences

**Positive**
- 119 tests pass against deterministic KPI functions. The AI layer is covered by
  tool-selection evals, not probabilistic SQL correctness checks.
- Adding a new provider (Gemini) required one new file. The KPI functions, tool
  definitions, and dispatch table were not touched.
- Every answer in production is traceable: tool name + parameters → function call →
  SQL in version control.
- Drill-down (ADR-0002) fell out cleanly: new drill-down KPIs are new functions
  with new tool definitions. The routing and formatting machinery does not change.

**Negative**
- The system cannot answer questions outside the registered KPI set. A user asking
  "how many orders were returned last Tuesday?" gets a graceful "I don't have a
  function for that" if no returns KPI exists. This is acceptable for a demo scoped
  to 13 metrics; it requires honest framing in the demo script.
- Each new metric is a code change, not a config change. This is the right constraint
  for a demo where correctness matters more than scope. It becomes a product decision
  at pilot scale: either expand the KPI library systematically, or add a SQL generation
  fallback with explicit correctness caveats surfaced to the user.

## When to Revisit

- A pilot client asks questions the KPI library does not cover and the business value
  of answering them outweighs the correctness risk of generated SQL. If that point
  arrives, the fallback should be opt-in ("I don't have a dedicated metric for that —
  want me to try a direct query? Results are not guaranteed"), not silent.
- The KPI library grows past ~30 tools and tool selection accuracy degrades measurably
  in eval. At that point, consider grouping tools into categories and using a two-stage
  router (classify intent, then select within category).

## References

- `app/engine_tools.py` — `TOOL_DEFINITIONS`, `KPI_DISPATCH`, `SYSTEM_PROMPT`
- `app/anthropic_engine.py` — Anthropic tool-use loop (two-turn)
- `app/gemini_engine.py` — Gemini implementation of the same interface
- `metrics/kpis.py` — all 13 KPI functions; SQL lives here only
- `tests/test_kpis.py` — known-value assertions for every KPI function
- `standards/ai-engineering.md` — metrics-first principle (the foundation this ADR applies)
- ADR-0002 — drill-down implementation, which depends on this decision
