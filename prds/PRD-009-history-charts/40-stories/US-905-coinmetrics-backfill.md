---
id: US-905
title: Coin Metrics backfill recipe — MVRV, active addresses, exchange flows via catalog-v2 min_time, empty response never treated as no-history
priority: 5
touches:
  - ingest/backfill.py
  - ingest/fetchers/coinmetrics.py
  - tests/test_backfill_coinmetrics.py
context:
  - AGENTS.md
  - prds/PRD-009-history-charts/10-research.md
  - prds/PRD-009-history-charts/20-decisions.yaml
---

As the owner, I want Coin Metrics-sourced indicators (MVRV, active addresses, exchange flows) to
backfill only as far back as the vendor's own free-tier entitlement genuinely allows, so a viewer
never mistakes an entitlement boundary for "no data existed before this date."

Research confirmed live: querying outside the entitlement window returns an empty response, not
an error — a backfill that treats "0 rows" as "no history exists" would silently record a falsely
short history for every affected metric.

## Acceptance criteria

- [test: backfill queries catalog-v2 for each metric's real min_time before requesting history, and never requests a start_time earlier than that value] The entitlement check
- [test: a mocked empty response from asset-metrics for a start_time inside the entitlement window is treated as a genuine "no data for this range" result, distinct from a start_time outside the window] The exact failure mode research found — an empty response is ambiguous without the catalog-v2 check
- [test: backfill respects Coin Metrics' community rate limit (10 requests per 6 seconds, sliding window) without erroring or being throttled into failure] Real vendor constraint, not assumed away
- [test: pagination via next_page_url is followed unmodified until exhausted, with no row duplicated or dropped across pages] Correct pagination
- [integration: a live Coin Metrics backfill for one real BTC metric (MVRV or active addresses) returns real historical values whose earliest date matches that metric's own live catalog-v2 min_time] Real data, not fixtures
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Depends on US-903's shared backfill entry point and coverage test.
- BNB and SOL's existing NOT_DEFINABLE declarations for metrics Coin Metrics does not offer them
  (established in PRD-007) are unaffected by this story — this is backfill for metrics that are
  already live-fetched successfully today, not an attempt to backfill an already-NOT_DEFINABLE
  cell.
