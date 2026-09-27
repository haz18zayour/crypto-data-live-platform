---
id: US-807
title: One ingest run persists all four new fetchers alongside the existing board — pipeline and heartbeat integration, daily tier
priority: 7
touches:
  - ingest/pipeline.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
  - prds/PRD-012-cadence-split/30-spec.md
---

As the owner, I want the macro and flows entries persisted by the same daily-tier run that
already persists the technical board, derivatives, and on-chain panels, so this PRD does not
repeat US-414's original gap (a working computation with no path to the database) or PRD-006's
structural near-miss (entries a persistence filter excludes by construction).

`persist_board`/`run_scheduled_board` were already generalized in PRD-012 to filter by cadence
tier via `expected_update_interval_seconds`. This story registers the new entries at the daily
tier's interval and extends the same shape — no new filter, no new branch, one persistence path
for four data categories now instead of three.

## Acceptance criteria

- [test: persist_board accepts macro/flows results alongside technical, derivatives, and on-chain results, without a macro-specific branch inside it] One persistence path, not a fifth one bolted on
- [test: a single daily-tier ingest run writes rows for every registered entry, including all new FRED/SoSoValue/DefiLlama/alternative.me rows] Every registered cell, one run, one heartbeat ping
- [test: one macro/flows fetch failure does not prevent any other cell — technical, derivatives, on-chain, or macro — from persisting] Matches the per-cell failure isolation established for every prior data category on this board
- [test: the daily-tier heartbeat still pings success only when the run itself completed, independent of individual cell failures] A single ERROR-status row is not a pipeline failure; a run that raised before completing is
- [integration: a real scheduled daily-tier run against all live vendors persists all four data categories and the total row count matches the full registry] End to end, the actual cron entry point
- [ci: the daily ingest workflow run completes successfully on the pushed commit] The actual scheduled job, not a local approximation

## Notes for the implementer

- Do not put any of this PRD's rows on PRD-012's fast or medium tier — confirmed at G1, nothing
  in this PRD changes intraday, and doing so would burn SoSoValue's monthly quota for zero new
  data.
- Coin Metrics', Helius's, SoSoValue's, and FRED's per-IP/per-key rate limits are independent of
  each other and of OKX's — pacing one vendor's calls does not protect against exceeding
  another's. Verify the full daily run's total call count against each vendor's own documented
  limit, not just the previous data categories' already-proven pacing.
- The `[integration:]` and `[ci:]` criteria here are not exercised by the automated pipeline by
  default — per this project's own recorded lesson, treat them as unverified until someone
  actually runs them with real credentials and can cite the real exit code and output.
