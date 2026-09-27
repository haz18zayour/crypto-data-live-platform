---
id: US-801
title: Database migration — reference_period and published_at columns on datapoints, nullable, backward compatible
priority: 1
touches:
  - supabase/migrations/
  - ingest/persist.py
  - tests/test_persist.py
context:
  - AGENTS.md
  - prds/PRD-008-macro-flows/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want `datapoints` to carry a real `reference_period` and `published_at` per row,
so a macro value's honest lag can be shown as two separate facts (what period it covers, when it
was actually published) rather than a single number that depends on an undisclosed anchor
choice.

Live research confirmed the frontend already declares optional `referencePeriod`/`publishedAt`
fields on `Provenance` (`web/src/datapoint.ts:16-17`) and already computes staleness from
`publishedAt` when present (`web/src/data.ts:255`) — but no migration, no `persist_datapoint`
parameter, and no fetcher anywhere populates either field. This story builds the missing
backend half.

## Acceptance criteria

- [test: a new migration adds reference_period (text, nullable) and published_at (timestamptz, nullable) to public.datapoints] The schema change itself
- [test: every pre-existing row (from PRD-001/006/007's indicators) continues to read and render exactly as before, with both new columns null] Backward compatibility — no existing indicator's meaning changes
- [test: persist_datapoint accepts optional reference_period and published_at keyword arguments and writes them when provided] The write path
- [test: calling persist_datapoint without reference_period/published_at (the existing call pattern from every current fetcher) still succeeds and writes null for both] No existing caller breaks
- [test: reference_period and published_at are independently nullable — a row can have one without the other] Some vendors may only supply one of the two facts
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- `.uf/config.json`'s `blastRadius` lists `**/migrations/**` — this story is blast radius and G4
  applies before merge.
- Follow the existing migration file naming convention (`YYYYMMDDHHMMSS_description.sql`) and the
  existing `checksums.sha256` update pattern already used by prior migrations in this directory.
- Do not backfill `reference_period`/`published_at` for existing rows — they were never known for
  those indicators and inventing a value for them would violate the project's "never a proxy"
  rule. `null` is the honest state for pre-PRD-008 data.
