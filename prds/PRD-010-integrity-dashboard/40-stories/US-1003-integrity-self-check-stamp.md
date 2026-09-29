---
id: US-1003
title: Integrity read carries a server-clock computed_at stamp; the frontend detects and renders its own panel's staleness
priority: 3
touches:
  - web/src/integrity.ts
  - web/src/integrity.test.ts
context:
  - AGENTS.md
  - prds/PRD-010-integrity-dashboard/10-research.md
  - prds/PRD-010-integrity-dashboard/20-decisions.yaml
---

As the owner, I want the integrity panel to know when its own read is stale, so that it cannot
report "all green" from old data through the same cache/poll layers it exists to audit — the panel
sharing a failure mode with the thing it checks would defeat the entire point of this PRD.

Research's own blind-spot finding: the integrity panel reads through the same `datapoints` table,
the same PostgREST layer, and the same browser poll/cache as the board it audits. A TanStack Query
cache serving an old response, a PostgREST schema cache never reloaded, or a CDN edge cache could
all make the panel silently stale in exactly the way this PRD exists to prevent.

## Acceptance criteria

- [test: the frontend integrity-read client surfaces the computed_at timestamp from US-1002's read alongside the integrity data itself] The stamp reaches the client
- [test: given a computed_at more than a defined threshold older than the browser's current clock, the client classifies the read as stale-self-check, distinct from any per-indicator freshness/frozen state] A stale panel is visible as stale, not as a clean bill of health
- [test: given a computed_at within the threshold of the browser's current clock, the client classifies the read as current] The healthy path renders normally
- [test: the staleness comparison uses the browser's own Date.now(), not a value round-tripped through the same read being checked] The self-check cannot be defeated by the exact cache layer it is meant to catch
- [cmd: npm --prefix web test] The web suite stays green
- [cmd: npm --prefix web run typecheck] Typecheck holds

## Notes for the implementer

- Pick a threshold that is clearly wider than this board's normal read latency but tight enough to
  catch a genuinely stuck cache — document the reasoning for whatever value you choose in the code,
  since there is no registry-declared value to reuse here (this is about the panel's own read
  freshness, not any indicator's).
- This story only needs the client-side detection logic and its own tests — wiring the resulting
  state into the visible panel UI happens in US-1005.
