---
id: US-414
title: Persist the computed board — 44 indicators reach the database
priority: 11
touches:
  - ingest/pipeline.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the 44 computed indicators written to the database, because right now they
are computed correctly and thrown away.

**Measured today.** `run_all_assets()` produces 44 results in 49 seconds, every one `OK` —
BTC RSI 54.89, EMA 20/50/200 stacked in trend order, Bollinger bands straddling the middle band,
ATR scaled sensibly per asset. Then the function returns and the values are discarded, because
its signature takes **no connection**. Meanwhile `run_pipeline(connection, fetcher)` — the
function the scheduled job actually calls — persists exactly one indicator, `btc_daily_close`.

The database holds **5 rows across 1 distinct indicator**. The board exists in memory for 49
seconds a day and nowhere else.

This is a criterion gap, not an implementation failure: US-408 asked that a full run *"computes
indicators for BTC, ETH, SOL and BNB against live venues"*, and it does precisely that. Nobody
asked for persistence.

## Acceptance criteria

- [test: a full run writes one datapoint row per computed indicator] 44 rows, not 1
- [test: each persisted row carries the provenance the schema demands] vendor, endpoint, source_field, fetched_at, source_timestamp, measured_on — the same discipline PRD-001 established for one indicator
- [test: a computed result that is not Ok is persisted with its status and reason] An indicator that failed to compute is recorded as such, never skipped — absence must be visible
- [test: persistence is idempotent per (indicator_key, asset, source_vendor, source_timestamp)] Re-running does not duplicate, matching the identity PRD-003 established
- [test: one indicator failing does not prevent the other 43 being written] A partial board is the failure this product exists to surface, and it must be surfaced per-cell rather than by losing the run
- [integration: a real run against live venues persists the full board and the row count matches the registry] End to end, real requests, real database
- [cmd: uv run pytest -q --no-header] The offline suite stays green

## Notes for the implementer

- The scheduled job must call whatever persists the **whole** board. Leaving
  `run_pipeline(connection, fetcher)` as the entry point would keep shipping one indicator a day.
- Do not fetch the same bars twice per asset. Four assets × 250 bars is already the expensive
  part; recomputing per indicator would multiply live requests by eleven and throttle the venues,
  which is exactly what pushed the test suite to four hours.
- Write results and failures in the same pass. A row that says `ERROR` with a reason is worth
  more than a missing row, because a missing row is indistinguishable from an indicator nobody
  registered — the defect that hid EMA for an entire PRD.
