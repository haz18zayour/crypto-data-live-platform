---
id: US-1005
title: The per-source freshness rollup panel — real data age vs. threshold per vendor, wall-clock-stamped sources rendered unmeasurable, integrity self-check surfaced
priority: 3
touches:
  - web/src/IntegrityPanel.tsx
  - web/src/IntegrityPanel.test.tsx
  - web/src/App.tsx
context:
  - AGENTS.md
  - prds/PRD-010-integrity-dashboard/10-research.md
  - prds/PRD-010-integrity-dashboard/20-decisions.yaml
---

As the owner, I want one panel showing every source's real freshness at a glance, computed from
data age rather than from whether a scheduled job happened to fire, so a source that has gone
silent is visible even though nothing about its last fetch technically errored.

## Acceptance criteria

- [test: the panel renders one row per source vendor, aggregating US-1002's freshness state across that vendor's indicators/assets] One row per vendor, not per cell
- [test: a vendor whose worst indicator state is fresh/warn/stale renders that state's real age against its registry threshold, not a boolean] Real numbers, not a pass/fail badge
- [test: a vendor carrying freshness_unmeasurable renders "unmeasurable: <reason>" rather than any shade of green, red, or a numeric age] The false-comfort gap this PRD exists to close
- [test: the panel surfaces US-1003's stale-self-check state distinctly from any per-vendor freshness state — a stale integrity read is visible as "integrity check itself may be stale," never silently presented as a normal rollup] The self-check reaches the actual UI, not just the client library
- [cmd: npm --prefix web test] The web suite stays green
- [cmd: npm --prefix web run typecheck] Typecheck holds
- [browser: load the live board at http://localhost:5174, open the integrity panel, and visually confirm every registered vendor appears exactly once, the two wall-clock-stamped vendors (DefiLlama stablecoin supply's vendor, validators.app) show "unmeasurable" rather than green, and no vendor is silently missing from the rollup] Real rendering against the real registry, not a fixture subset

## Notes for the implementer

- This story depends on US-1002's migration being applied to production before the `[browser:]`
  criterion can be judged against real data.
- "One row per vendor" should genuinely aggregate — check the registry for how many distinct
  vendors exist across all ~150 indicators before assuming a small, easily-enumerated list; do not
  hardcode a vendor list that a future registry addition could silently fall outside of.
- Healthchecks.io's own status is explicitly out of scope for this rollup per G1 decision 6 — do
  not add an HC API call here.
