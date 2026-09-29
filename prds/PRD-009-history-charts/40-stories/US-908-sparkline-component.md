---
id: US-908
title: Sparkline component — min/max value labels with dates, real time axis with raw points, cadence-tiered minimum-history threshold, explicit insufficient-history state
priority: 8
agent: claude
touches:
  - web/src/Sparkline.tsx
  - web/src/Sparkline.test.tsx
  - web/src/CellDetail.tsx
  - web/src/history.ts
context:
  - AGENTS.md
  - project-documents/20_Design_System.md
  - prds/PRD-009-history-charts/10-research.md
  - prds/PRD-009-history-charts/20-decisions.yaml
---

As the owner, I want a cell's own recent history rendered as a plain sparkline — a line, its
min/max value labels with their real dates, the last point marked — and nothing that reads as a
verdict about that history, matching the project's absolute rule against any score, band,
percentile, or colour-coded significance.

**Use the skills.** This is a design-led, dataviz-shaped story and is routed to Claude for
exactly that reason — Codex cannot invoke any plugin skill. Fire `open-design-local:
d3-visualization` for the actual chart-rendering approach (a sparkline is a small, dense,
information-forward chart — treat it as a real dataviz problem, not a decorative flourish),
`open-design-local:apple-hig` and `taste-skill` for restraint and density against the existing
board's Apple-grade pass (PRD-005's US-512), `color-expert` so the marked last point and any
axis text stay within the existing light/dark token system rather than inventing a new palette,
and `open-design-local:design-review` as the audit pass before calling this done. A sparkline
that looks like a stock-app widget with a green/red trend colour is the specific failure mode to
avoid — colour must not encode "up is good," since this board makes no judgement about any value.

## Acceptance criteria

- [test: the sparkline renders a min value label and a max value label, each paired with the real date of that point, at the axis ends] The distribution-context mechanism confirmed at G1
- [test: the sparkline never renders a shaded band, a percentile marker, a "range position" indicator, or any colour keyed to a point's position within the range] Directly guards the project's no-signal rule for this new UI surface
- [test: the sparkline's time window (e.g. "90d" or "7d") is printed as text next to the chart, reflecting that cell's actual returned point range, not a fixed universal label] Guards against two cells silently implying comparable ranges when their real backfill depth differs
- [test: a cell with fewer than the cadence-tiered minimum point count (>=7 points and >=2 distinct values for daily-or-faster indicators; a lower threshold for monthly-cadence indicators) renders an explicit "not enough history yet (n points since <date>)" state instead of a line] The core honesty guarantee of this story
- [test: the insufficient-history state is visually and textually distinct from NOT_DEFINABLE, UNAVAILABLE, PAYWALLED, and FETCH_FAILED] Never conflates "we haven't collected enough yet" with an existing absence reason
- [test: points from a fast-tier indicator (dense recent 5-minute points next to sparser historical daily points) render on a real time axis, with no resampling that would hide the density change] Matches the G1 decision
- [browser: the sparkline is visible on the rendered board for at least one real cell with sufficient history, with axis labels legible at the board's existing cell size] Renders correctly in the real layout, not just in isolation
- [cmd: npm --prefix web test] The full web suite stays green

## Notes for the implementer

- Depends on US-902's history-read RPC for real data to render against.
- `project-documents/20_Design_System.md` already establishes this project's colour-is-never-
  the-sole-channel discipline for `CellFace.tsx` — the sparkline must not introduce a first
  colour-only distinction anywhere on the board.
- Do not add any hover tooltip, badge, or secondary label that states a value's percentile,
  rank, or "how it compares" beyond the plain min/max value+date labels this story's criteria
  name explicitly — that is exactly the line 20-decisions.yaml draws.
