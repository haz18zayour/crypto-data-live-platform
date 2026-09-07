---
id: US-007
title: Persist a datapoint with complete provenance
priority: 7
touches:
  - ingest/persist.py
  - ingest/pipeline.py
  - tests/test_persist.py
context:
  - AGENTS.md
  - project-documents/10_Technical_Architecture.md
  - project-documents/11_Data_Model.md
---

As the owner, I want each fetched value written with its vendor, endpoint, source field, fetch
time and source timestamp, so that any number on the page can be traced to exactly what
produced it.

## Acceptance criteria

- [integration: a full pipeline run fetches from OKX and writes one complete datapoint row] The assembled system runs end to end against a real Postgres and a real OKX response, and the resulting row has every provenance column populated
- [test: an Unavailable result is persisted as a row with status UNAVAILABLE, a reason, and a null value] Absence is recorded, not skipped — a missing row and an unavailable row mean different things
- [test: provenance fields are copied from the registry entry, not hardcoded at the call site] Vendor, endpoint and source_field come from the registry so they cannot drift from what was actually called
- [test: persisting a result whose measured_on differs from the target asset raises before reaching the database] Caught in application code as well as by the constraint — defence in depth, since the constraint is the last line and not the first
- [test: fetched_at is set by the writer and source_timestamp by the fetcher] The two timestamps have different meanings and different owners

## Notes for the implementer

- The pipeline is: read registry → fetch → persist. Keep it that shape; there is no scoring,
  transformation or aggregation step, and there never will be in this product.
- **A run in which the fetcher was never invoked must not write an `OK` row and must not write
  nothing.** It writes `NOT_FETCHED`. This is the whole point of the story — the prior
  system's silent `0.0` was exactly a fetcher that never ran leaving no trace.
- Use the service-role key here. It must not appear in any `VITE_`-prefixed variable or reach
  the web bundle.
- Writes are idempotent per `(indicator_key, asset, source_timestamp)` — re-running for the
  same closed candle updates rather than duplicates.
- The integration test is the one criterion in this PRD that proves the parts are wired
  together, not merely individually correct. Do not substitute it with mocks.
