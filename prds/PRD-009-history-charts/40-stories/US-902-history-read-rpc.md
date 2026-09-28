---
id: US-902
title: History-read RPC — at most N points per cell as one JSON array, ordered by the existing unique index
priority: 2
touches:
  - supabase/migrations/
  - web/src/history.ts
  - tests/test_history_read.py
context:
  - AGENTS.md
  - prds/PRD-009-history-charts/10-research.md
  - prds/PRD-009-history-charts/20-decisions.yaml
---

As the owner, I want one bounded query that returns a cell's recent history as a single JSON
array, so the sparkline component never has to assemble history from a board-wide row-per-point
query that risks silent truncation at PostgREST's default response cap.

Research's recommended approach (A) reuses `datapoints` directly rather than a second table or a
materialized rollup — this story is the read path that makes that approach practical at this
board's real scale (~150 indicators across up to 5 assets).

## Acceptance criteria

- [test: a database function/RPC accepts indicator_key, asset, and a point limit, and returns at most that many of the most recent origin='live'-or-'backfill' rows for that exact cell, newest first] The bounded read
- [test: rows returned are ordered by source_timestamp, with a defined tie-break when timestamps are equal, and never include a row whose source_timestamp is null (an UNAVAILABLE/ERROR row) in the point series] Correct ordering; absence rows do not become fake history points
- [test: the RPC pins to a single source_vendor per call, never interleaving two vendors' rows for the same indicator/asset into one series] Corroborated indicators (e.g. spot close from two venues) must not produce a zig-zag sparkline from mixed vendors
- [test: calling the RPC for a cell with zero rows returns an empty array, not an error] A brand-new registry entry with no history yet is a valid, distinct state
- [integration: the RPC's response for one real, populated indicator/asset/vendor is confirmed under PostgREST's actual row-response limit at this board's real point counts] Directly checks the assumption research flagged as unverified
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Depends on US-901's `origin` column existing — this RPC reads it to decide what counts as a
  valid history point but does not itself write anything.
- Follow the existing migration file naming convention if the RPC/function requires a migration.
  A new function is not automatically blast radius the way an ALTER TABLE is, but check
  `.uf/config.json`'s `blastRadius` patterns before assuming so.
- Do not build any frontend rendering here — that is US-908. This story is the data path only.
