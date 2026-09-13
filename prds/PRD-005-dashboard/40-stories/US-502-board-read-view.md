---
id: US-502
title: board_read — one bounded query, latest row per cell
priority: 2
agent: claude
touches:
  - supabase/migrations/20260913120000_create_board_read.sql
  - tests/test_board_read.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the whole board to arrive in one request that returns one row per cell,
because the alternative downloads every row we have ever written in order to display 45 numbers.

Measured 2026-09-13 against the live database: 50 rows, 45 distinct `(indicator_key, asset)`
pairs. `select distinct on (indicator_key, asset) ... order by indicator_key, asset, fetched_at
desc` returns exactly 45. The table gains roughly 45 rows per day.

Today the gap is five rows and nobody would notice. In a year it is about sixteen thousand rows
fetched to render one screen, getting slower every single day, with nothing anywhere reporting
it. **That is the failure this product was started to fix**, so shipping the client-side
reduction and promising to revisit it would be an unusually direct self-contradiction.

The index this sort wants — `datapoints_indicator_asset_fetched_at_idx` on `(indicator_key,
asset, fetched_at desc)` — already exists from the original schema.

The view follows the pattern established twice already in this repo: `security_invoker = true`,
then `revoke all` followed by `grant select` to `anon` and `authenticated`. RLS on the
underlying table keeps doing the work; the view must not become a way around it.

**Blast radius.** `**/migrations/**`. G4 does not fire on its own; it is run manually before
merge.

## Acceptance criteria

- [test: board_read returns exactly one row for every distinct indicator_key and asset pair in datapoints] The count matches the distinct-pair count, computed in the test rather than hard-coded
- [test: given two rows for one cell the view returns the one with the later fetched_at] Written with the older row inserted last, so an ordering bug cannot pass by accident
- [test: board_read exposes every column the page needs including status reason source_vendor and source_timestamp] Named individually; a select-star view would satisfy a weaker criterion while hiding a later column drop
- [test: anon can select from board_read and cannot insert update or delete through it] The view is a read surface, not a hole in RLS
- [cmd: uv run python -m ingest.migrate --check] The migration ledger is consistent
- [cmd: uv run pytest -q --no-header] The Python suite passes

## Notes for the implementer

- The `order by` must lead with the two grouping columns. `distinct on` keeps the first row per
  group *after the sort*, so an order that starts with `fetched_at` silently returns an
  arbitrary row per cell and every test that only counts rows will still pass.
- Tests that need a live PostgreSQL go through `TEST_DATABASE_URL`, the way
  `tests/test_migration.py` already does. Do not point them at the production database.
- Do not add filtering, window trimming or a date bound to the view. Its job is one row per
  cell, nothing else. Anything clever here becomes invisible behaviour later.
- No change to `datapoints`, its constraints, or its policies.
