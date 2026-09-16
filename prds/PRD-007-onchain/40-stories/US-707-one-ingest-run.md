---
id: US-707
title: One ingest run persists all three data categories — pipeline and heartbeat integration
priority: 7
touches:
  - ingest/pipeline.py
  - ingest/heartbeat.py
  - tests/test_persist_board.py
  - tests/test_heartbeat.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the on-chain entries persisted by the same scheduled run that already
persists the technical board and the derivatives panel, so this PRD does not repeat US-414's
gap (a working computation with no path to the database) or PRD-006's structural near-miss
(entries a persistence filter excludes by construction).

`persist_board` was already generalized in PRD-006 to accept results keyed by registry entry
regardless of `talib_function`. This story extends the same shape to the on-chain entries — no
new filter, no new branch, one persistence path for all three data categories.

**Decided at this gate, superseding this story's original draft**: `sol_active_addresses`'s
Helius fetch takes ~2.5 hours (confirmed live in US-704), fifteen times `ingest.yml`'s 10-minute
CI timeout. Wiring it into the existing scheduled run unmodified would break that job. Rather
than parallelize the fetch (adds real complexity to a fetcher already hardened by US-704's live
defect-finding) or wait for a hypothetical future PRD-012, the owner decided directly: give
`sol_active_addresses` its own separate, less-frequent scheduled job now. Every other on-chain
entry (Coin Metrics MVRV/active-addresses/exchange-flow, Validators.app staking) persists on the
existing schedule alongside the technical board and derivatives panel, unchanged.

## Acceptance criteria

- [test: persist_board accepts on-chain results alongside technical and derivatives results, without an on-chain-specific branch inside it] One persistence path, not three
- [test: a single ingest run writes rows for the technical board, the derivatives panel, and every on-chain entry except sol_active_addresses] Every registered cell but the one on its own schedule, one run, one heartbeat ping
- [test: sol_active_addresses persists on its own separate scheduled entry point, independent of the main ingest run] The split cadence this gate decided
- [test: one on-chain metric's fetch failure does not prevent any other cell — technical, derivatives, or on-chain — from persisting] Matches the per-cell failure isolation established for every prior data category on this board
- [test: the heartbeat still pings success only when the run itself completed, independent of individual cell failures] A single ERROR-status row is not a pipeline failure; a run that raised before completing is
- [integration: a real scheduled run against all live vendors persists every entry except sol_active_addresses, and the total row count matches the full registry minus that one entry] End to end, the actual cron entry point
- [integration: a real run of the separate SOL schedule persists sol_active_addresses on its own] End to end, the actual dedicated cron entry point
- [ci: the main ingest workflow run completes successfully on the pushed commit, within its existing timeout] The actual scheduled job, not a local approximation
- [ci: the new SOL schedule's workflow run completes successfully on the pushed commit, with a timeout sized for the ~2.5hr fetch] The actual dedicated scheduled job

## Notes for the implementer

- Add a second scheduled job for `sol_active_addresses` only (e.g. a new GitHub Actions workflow
  with its own cron trigger and a timeout sized for ~2.5 hours, or a separate cron-job.org
  trigger hitting a dedicated entry point — match whatever mechanism `ingest.yml` already uses
  for the main job). Pick a cadence that respects Helius's ~270k-credit/month budget for this
  entry (documented in US-704 and this PRD's 30-spec.md) — once daily is the assumption baked
  into that budget; do not increase frequency without redoing that math.
- The main ingest run's heartbeat and row-count expectations must be updated to no longer expect
  `sol_active_addresses` on every run; give the new SOL schedule its own heartbeat/dead-man's
  switch, matching the pattern already used for `HEALTHCHECK_URL_CONTRACT_CANARY` and friends.
- Coin Metrics' per-IP rate limit and Helius's per-account rate limit are independent of each
  other and of OKX's — pacing one vendor's calls does not protect against exceeding another's.
  Verify each run's total call count against each vendor's own documented limit, not just the
  previous data categories' already-proven pacing.
- `.github/workflows/ingest.yml` and `.uf/config.json`'s `blastRadius` both list
  `.github/workflows/**` — this story touches the workflow file (adding the new SOL schedule),
  which is blast radius and G4 applies.
