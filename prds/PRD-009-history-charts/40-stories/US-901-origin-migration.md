---
id: US-901
title: Database migration — origin column on datapoints, board_read/datapoints_read filtered to live, applied to production before any backfill runs
priority: 1
touches:
  - supabase/migrations/
  - ingest/persist.py
  - tests/test_persist.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - prds/PRD-009-history-charts/10-research.md
  - prds/PRD-009-history-charts/20-decisions.yaml
---

As the owner, I want every `datapoints` row to carry whether it was written by the live pipeline
or by a backfill job, and I want the board's "current value" views to only ever consider live
rows, so that a historical backfilled value can never be silently displayed as today's reading.

Research identified this as the single most likely first-implementation defect in this PRD:
`board_read`/`datapoints_read` currently pick the latest row per cell by `fetched_at`, and a
backfill row written today with a 2024 `source_timestamp` would win that ordering. This story
builds the guard rail before any backfill code exists to trigger it.

## Acceptance criteria

- [test: a new migration adds origin text not null default 'live' to public.datapoints] The schema change itself
- [test: every pre-existing row defaults to origin='live' and continues to read and render exactly as before] Backward compatibility — no existing row's meaning changes
- [test: board_read and datapoints_read are rebuilt to filter to origin = 'live', so a row with any other origin value never appears in either view regardless of its fetched_at or source_timestamp] The actual guard
- [test: persist_datapoint accepts an optional origin keyword argument (default 'live') and writes it] The write path
- [test: a row explicitly written with origin='backfill' and a fetched_at of now() but a source_timestamp from 2024 does not appear as the latest row in board_read or datapoints_read for its cell] The exact adversarial scenario this migration exists to prevent, proven directly
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- `.uf/config.json`'s `blastRadius` lists `**/migrations/**` — this story is blast radius and G4
  applies before merge. This migration must additionally be **applied to the real production
  database with explicit owner sign-off** before any later story in this PRD (US-902 onward) may
  be considered unblocked — per this project's established manual-migration-apply discipline
  (`ingest/migrate.py` only supports `--check`; it has no apply path by design).
- Follow the existing migration file naming convention (`YYYYMMDDHHMMSS_description.sql`) and the
  existing `checksums.sha256` update pattern already used by prior migrations in this directory.
- Do not add any backfill-writing code in this story — it exists purely to make backfill safe
  before any backfill code is written, matching the fix-then-backfill decision at G1.
