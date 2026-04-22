# ADR-0001: Render over Railway for FastAPI Backend

**Date:** 2026-04-16
**Status:** Accepted
**Owner:** Yash Vajifdar

## Context

The FastAPI backend needs a hosted target so the Next.js personal website
(yashvajifdar.com/demos/lumber) can reach it. The workload is a demo: bursty traffic
from a handful of visits per week during prospect conversations. No always-on cost is
acceptable at this stage.

## Options Considered

### Railway
Runs containers 24/7. Build system is clean, Procfile-based deploys work without
additional config. Starts instantly because the container is always warm.

**Against:** Free tier is gone. Paid tier runs continuous compute regardless of
traffic. For a demo that may serve fewer than 50 requests a week, this is pure waste.

### Render (free tier)
Sleeps after 15 minutes of inactivity. Wakes on the next request. Supports a
declarative `render.yaml` that pins build command, start command, and env vars
in the repo. Free tier is generous enough for demo traffic.

**Against:** First request after sleep takes 30–60 seconds (cold start). Client-facing
code must handle the wait.

### Self-hosted (EC2 + nginx)
Full control, lowest marginal cost at scale, and on-brand for an AWS standards file
that names AWS as primary. Overkill for a demo.

**Against:** Adds operational surface area the project does not need yet. The goal
is to ship a demo, not run infrastructure.

## Decision

Ship on Render free tier. Accept the cold-start behavior and absorb it in the client:
the Next.js proxy route has a 30-second timeout, and the chat UI shows a "warming up"
state on the first request after idle.

## Consequences

**Positive**
- Zero ongoing cost for the demo period.
- `render.yaml` keeps deploy configuration in code — rebuilds are reproducible.
- Swap to paid Render or to AWS (Bedrock + ECS) is a configuration change. The
  FastAPI app does not know where it runs.

**Negative**
- Cold start on first call after idle. A prospect who clicks the demo link during
  a long idle window sees a 30–60 second spinner. The UI handles this but it is
  not ideal for a first impression.
- Free tier has bandwidth and build-minute caps. Not a problem at demo scale;
  would be at pilot scale.

## When to Revisit

Move off Render when any of these is true:
- First pilot client connects real data. Pilot traffic plus data-sensitivity
  requirements push toward AWS Bedrock + ECS.
- Cold-start latency affects a real prospect conversation. Switch to a paid
  tier or always-on host before it costs a deal.
- Build minutes or bandwidth caps become a limiter.

## References

- `docs/runbook.md` §9 — Render deploy procedure
- `docs/architecture.md` §5.4 — FastAPI decision, fail-fast pattern
- `render.yaml` — live config in the repo
- `standards/data-engineering.md` — AWS as the primary cloud; this ADR documents
  the demo-phase deviation and the exit path back to AWS
