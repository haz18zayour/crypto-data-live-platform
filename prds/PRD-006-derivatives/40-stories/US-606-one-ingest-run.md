---
id: US-606
title: One ingest run persists both boards — pipeline and heartbeat integration
priority: 6
touches:
  - ingest/pipeline.py
  - ingest/heartbeat.py
  - tests/test_persist_board.py
  - tests/test_heartbeat.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the sixteen new derivatives entries persisted by the same scheduled run
that already persists the technical board, so that this project does not repeat US-414's exact
gap — a working computation with no path to the database — and does not add a second cron job
that could silently stop reporting on its own.

`run_all_assets()`/`persist_board()` filter on `definition.talib_function is not None` by
construction; the sixteen entries this PRD adds have no `talib_function` at all. Left as-is,
they would compute correctly and never reach a table, the same failure `run_all_assets()` itself
had before US-414 — except this time the gap would be structural (the filter's own definition
excludes them) rather than accidental (a function signature with no connection parameter).

## Acceptance criteria

- [test: persist_board accepts results from either the technical board or the derivatives fetchers, keyed by registry entry, without a talib_function branch inside it] One persistence path, not two
- [test: a single ingest run writes rows for all 45 technical indicators and all 16 derivatives entries] 61 rows, one run, one heartbeat ping
- [test: one metric's fetch failure (e.g. long/short ratio for one asset) does not prevent the other 60 cells from persisting] Matches the per-cell failure isolation US-414 already established for the technical board
- [test: the heartbeat still pings success only when the run itself completed, independent of individual cell failures] A single ERROR-status row is not a pipeline failure; a run that raised before completing is
- [integration: a real scheduled run against live OKX persists both boards and the total row count matches the full registry] End to end, the actual cron entry point, not a test-only helper
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green
- [ci: the ingest workflow run completes successfully on the pushed commit] The actual scheduled job, not a local approximation

## Notes for the implementer

- Do not add a second `on: schedule:` job to `.github/workflows/ingest.yml`. This is exactly
  the split PRD-012 (not yet built) will formalize deliberately later, with its own reasoning;
  doing it accidentally here, for a different reason, would pre-empt that decision.
- `.github/workflows/ingest.yml` and `.uf/config.json`'s `blastRadius` both list
  `.github/workflows/**` — if this story's integration touches the workflow file at all (it
  should not need to), that is blast radius and G4 applies.
- Reuse the fetch-once-per-asset discipline `run_all_assets()` already established for the
  technical board's OHLCV bars — the four derivatives metrics do not share a single fetched
  payload the way OHLCV-derived indicators do, so this is not about avoiding duplicate bar
  fetches, but do still fetch each of the four metrics exactly once per asset per run, not once
  per registry entry (there is exactly one registry entry per metric per asset here, so this
  should already hold — verify it does).
