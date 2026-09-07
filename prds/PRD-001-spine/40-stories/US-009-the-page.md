---
id: US-009
title: The page — render one value, or its honest absence
priority: 9
touches:
  - web/**
context:
  - AGENTS.md
  - project-documents/10_Technical_Architecture.md
  - project-documents/11_Data_Model.md
---

As the owner, I want to open a page and see the BTC daily close together with its source, its
age, and whether it is stale, so that I can tell a trustworthy number from an untrustworthy
one without opening a database.

This is the product's entire thesis rendered once: **a wrong number must look different from
a right one.**

## Acceptance criteria

- [cmd: npm --prefix web run typecheck] TypeScript compiles with no errors
- [cmd: npm --prefix web run build] The production bundle builds
- [test: an UNAVAILABLE datapoint renders an em dash and its reason, never a zero] The three reasons render distinguishably — not definable for this chain, requires a paid tier, and fetch failed are three different messages
- [test: a STALE datapoint renders the value with its age and a visible stale treatment] A stale number is shown, but never shown as if it were current
- [test: adding a status to the union without handling it is a compile error] The exhaustive switch has a `never` fallthrough, so an unhandled case fails the build rather than falling through to a default render
- [test: the value displays its source vendor, endpoint and source timestamp] Provenance is on the face of the value, not behind a click
- [browser: prds/PRD-001-spine/50-evidence/US-009/page.png] The rendered page shows the value with its provenance and freshness

## Notes for the implementer

- Vite + React + TypeScript + Tailwind. Read via the Supabase **anon** key against the
  read-only view from US-005. The service-role key must never appear in the web bundle or in
  any `VITE_`-prefixed variable.
- Polling, not WebSockets: TanStack Query with a 30–60s interval. The underlying indicator is
  daily-close; a push layer would deliver nothing and has already been built and reverted once
  in the prior system for starving the scheduled jobs.
- Freshness is computed against the registry's thresholds, not hardcoded in the component.
- Deliberately no layout, theming or design work beyond what these criteria require. One value
  rendered honestly is the deliverable; PRD-007 designs the actual page.
- Do not add a "last known good" fallback that silently shows an older value as current. If it
  is stale, it says so.
