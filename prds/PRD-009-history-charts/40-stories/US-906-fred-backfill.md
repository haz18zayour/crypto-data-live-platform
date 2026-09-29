---
id: US-906
title: FRED backfill recipe — chunked initial-release vintages matching live semantics
priority: 6
touches:
  - ingest/backfill.py
  - ingest/fetchers/fred.py
  - tests/test_backfill_fred.py
context:
  - AGENTS.md
  - prds/PRD-009-history-charts/10-research.md
  - prds/PRD-009-history-charts/20-decisions.yaml
---

As the owner, I want FRED's seven registered series to backfill using the same initial-release
(`output_type=4`) semantics the live fetcher already uses, chunked so it never hits the
vintage-date cap that already broke four of the seven series once in PRD-008, so backfilled
history means the same thing as the live value it sits next to on the same sparkline.

## Acceptance criteria

- [test: backfill requests output_type=4 in realtime_start-bounded chunks small enough that no chunk's vintage-date count can approach FRED's cap, for both a low-frequency series (M2SL) and a high-frequency one (VIXCLS)] Chunking must work for the exact series class that broke in PRD-008
- [test: a backfilled historical value for an observation date already covered by a live row exactly matches that live row's value] Proves the two semantics agree at the seam, not just independently
- [test: a value revised under the same observation date backfills with the same disclosed-revision handling the live fetcher already uses (never silently overwritten)] Consistency with PRD-008's revision-disclosure decision
- [integration: a live chunked backfill for one high-frequency series (e.g. DFF) returns real historical values spanning at least 90 days without hitting the vintage-date cap] Directly proves the chunking fix works against the real API, not a mock
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Depends on US-903's shared backfill entry point and coverage test.
- Reuse `ingest/fetchers/fred.py`'s existing `REALTIME_WINDOW_DAYS` constant and chunking logic
  where possible rather than inventing a second chunking scheme — the live fetcher's fix for this
  exact cap (see its own module docstring/comments) is the reference implementation.
- `FRED_API_KEY` must be available wherever this backfill actually runs (a `workflow_dispatch` job
  or equivalent) — check the workflow's `env:` block directly rather than assuming it inherits
  from `ingest.yml`.
