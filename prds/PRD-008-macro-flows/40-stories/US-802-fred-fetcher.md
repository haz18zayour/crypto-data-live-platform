---
id: US-802
title: FRED fetcher — series registry, real published-date metadata, "." never becomes 0, revision disclosed not swallowed
priority: 2
touches:
  - ingest/fetchers/fred.py
  - ingest/schemas.py
  - tests/test_fred_fetcher.py
context:
  - AGENTS.md
  - prds/PRD-008-macro-flows/10-research.md
  - prds/PRD-008-macro-flows/20-decisions.yaml
---

As the owner, I want one FRED fetcher that reads a series' real reference period and true
publication date from FRED's own metadata, never a naive `realtime_start` default that would
stamp every observation as "published today," so this board's macro rows are exactly as honest
about their own age as every other data category already is.

Research flagged FRED's `"."` missing-observation marker (used on holidays and market closures)
and the naive-`realtime_start` publication-date trap as **UNVERIFIED** pending a live probe —
this story is where that probe happens, before any of the seven registered series (US-803) can
trust the fetcher's output.

## Acceptance criteria

- [test: a `"."` observation value is never coerced to 0 — the fetcher walks back to the last real observation and that observation's own date becomes the reference period] Matches this project's "never a proxy, never 0" rule
- [integration: a live FRED request confirms which response field actually carries the true publication date, distinct from realtime_start's request-time default] The load-bearing live probe this story exists for
- [test: the fetcher's returned reference_period reflects the observation's own period, not the request date] Directly guards against the naive-realtime_start trap
- [test: a second fetch returning a different value for an already-persisted observation date is surfaced as a revision (source_field states "revised from `<old value>`"), never a silent overwrite] The explicit revision-disclosure decision from 20-decisions.yaml
- [test: an HTTP 429 (FRED's documented rate-limit response) returns Error(FETCH_FAILED) with the status in the detail, never a silent retry] Matches this project's fail-loud rate-limit discipline from every prior fetcher
- [test: a malformed or reshaped FRED response is rejected by the response model] `extra="forbid"` on the new schema, same discipline as every existing fetcher
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Confirm the FRED_API_KEY used for this story's live/integration criteria is the project's own
  dedicated key, not the one shared with `crypto-investing-signals` (per the assumption logged at
  G1) — check `project-documents/15_Services_and_Credentials.md` first; provisioning a fresh key
  is a manual, instant, free step if the dedicated one doesn't exist yet.
- This story builds the shared fetcher only; it does not register any of the seven series — that
  is US-803, which depends on this story's fetcher being correct first.
- The revision-disclosure mechanism only needs to handle the case of a value changing under an
  already-persisted observation date; it does not need to reconstruct or display a full revision
  history.
