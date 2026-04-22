# ADR-0002: Drill-Down as a Scoped Follow-Up Question

**Date:** 2026-04-16
**Status:** Accepted
**Owner:** Yash Vajifdar

## Context

The pie charts for revenue-by-category and customer-type split are natural entry points
for a second question: *which products in this category?* or *who are the top customers
in this segment?* Users expect to click a slice and see the breakdown.

The question was where to put that interaction.

## Options Considered

### 1. Frontend filters on the existing DataFrame
When the user clicks a slice, filter the data in the browser and re-render a new chart
from what is already on the page.

**Against:** The existing DataFrame does not contain the drill-down data. The category
pie shows totals per category; it does not carry per-product rows. The frontend would
need a second, richer payload on every answer, or a second API call. Either way the
business logic drifts out of the metrics layer and into the frontend.

### 2. A new `/drill` API endpoint
Accept a parent tool name, a filter key, and a value. Route to the appropriate function.

**Against:** Two paths into the same system. The chat pipeline already handles tool
selection, parameter passing, and response shaping. A parallel endpoint duplicates
that work and invites drift between the two.

### 3. Templated follow-up question routed through the existing chat pipeline
Attach a `drill_key` and a `drill_question` template to the chart spec. On click, the
frontend substitutes the clicked value into the template and posts the resolved question
to `/ask` as a normal chat turn. The LLM selects the new drill-down KPI and returns
a standard ChatResult.

**For:** One model of execution. Every answer runs the same tool-use loop against the
same tested KPI functions. The LLM's routing, the response format, the follow-up chips,
and the chart rendering all work without modification.

## Decision

Ship option 3.

Two new KPI functions (`top_products_by_category`, `top_customers_by_type`) with their
own tool definitions, dispatch entries, chart specs, and tests. The parent pie charts
gain `drill_key` and `drill_question` fields. The frontend reads those on click, resolves
the template, posts the resolved question as if the user had typed it.

## Consequences

**Positive**
- No new API surface. The click is a shortcut for typing a question.
- Drill-down answers go through the same tests, the same system prompt, and the same
  error handling as any other answer.
- Adding drill-down to a new chart is a backend-only change: write the KPI, register
  the tool, add the template. Frontend logic does not move.
- The LLM sees every drill-down question in its history, so any subsequent follow-up
  ("what about in Treated Lumber?") already has context.

**Negative**
- Two API round trips for a drill-down (the original question, then the drill) instead
  of one filtered render on the client. For a demo at this scale that cost is negligible.
  At pilot scale the second call is already cached-friendly because the question is
  deterministic per clicked slice.
- The `drill_question` templates live in `CHART_SPECS`, which is a small layering
  choice. They are presentation-adjacent (the text the user would have typed), not
  pure data logic. Acceptable because they travel with the chart spec that triggers
  them, and they are tested the same way any string literal is tested.

## When to Revisit

- If drill-down depth needs to grow past one level (e.g. category → product → location)
  and the linearly-chained templates get unwieldy.
- If any drill-down target needs parameters the LLM cannot infer from the clicked value
  alone.
- If the frontend grows a need for true client-side filtering of existing data
  (e.g. a date-range slider on a chart that is already on screen). That is a different
  feature than drill-down and belongs in its own design.

## References

- `app/engine_tools.py` — `CHART_SPECS` entries with `drill_key` and `drill_question`
- `metrics/kpis.py` — `top_products_by_category`, `top_customers_by_type`
- `docs/runbook.md` §6a — the operational recipe for adding drill-down to a chart
- `standards/ai-engineering.md` — metrics-first principle; this ADR applies it to
  click-driven interactions, not just typed queries
