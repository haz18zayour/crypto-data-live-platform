---
id: US-005
title: Database schema — constraints that make wrong data a database error
priority: 6
touches:
  - supabase/migrations/**
  - tests/test_migration.py
  - .github/workflows/**
context:
  - AGENTS.md
  - project-documents/10_Technical_Architecture.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the `datapoints` table to reject dishonest rows at the database level,
so that presenting one asset's data as another's is impossible rather than merely discouraged.

The prior system applied BTC's on-chain data to eight other coins and its own documentation
called the result *"not degraded data, wrong data"*. No amount of application-layer care
caught it, because its schema had no column that could express the difference.

**This story is blast-radius (`**/migrations/**`) and needs gate G4 before merge.**

## Acceptance criteria

- [integration: the migration applies to a real Postgres and every constraint rejects its bad row] Applied against a live Postgres service, then each of the three constraints is exercised with a row it must refuse and a row it must accept
- [test: asset_match rejects an OK row whose measured_on differs from asset] Inserting BTC's value labelled as SOL with status OK raises an integrity error
- [test: value_iff_ok rejects an OK row with a null value and a null-status row carrying a value] Status and value cannot drift apart
- [test: reason_required rejects an UNAVAILABLE row with no reason] Absence must always say why
- [cmd: uv run python -m ingest.migrate --check] Migration files are ordered, named consistently, and none has been edited after being applied
- [cmd: uv run pytest tests/test_migration.py -q --no-header -o addopts= --tb=no -rN] The live-Postgres tests RUN — this command fails if any of them skip, because a skipped constraint test and a passing one are indistinguishable at the gate

## Notes for the implementer

Schema is specified in `30-spec.md` § "Data model changes" — implement it as written,
including all three CHECK constraints and both enum types.

- `asset_match` is the single highest-value line in this project. Do not weaken it to a
  trigger, a warning, or an application-level assertion.
- A mismatched row may still be **inserted** with status `UNAVAILABLE` for audit purposes —
  the constraint only forbids it carrying `OK`. That is deliberate: recording that we fetched
  the wrong thing is useful; displaying it as correct is not.
- Add an index on `(indicator_key, asset, fetched_at DESC)`.
- Enable RLS. The browser reads through a read-only view with a SELECT-only policy; the
  service-role key is used exclusively by ingestion.
- For the integration test, run a `postgres:16` service container in the workflow rather than
  mocking. A constraint that has only been tested against a mock has not been tested.
- **The Postgres tests must FAIL, not SKIP, when no database is reachable.** The previous
  attempt made the fixture `pytest.skip` unless `TEST_DATABASE_URL` was set; the suite then
  printed `31 passed, 4 skipped` and the gate exited 0, so a constraint suite that never ran
  was indistinguishable from one that passed. That is this product's own failure mode
  applied to its tests. Make the fixture raise with a message naming the missing variable.
- Read `TEST_DATABASE_URL` from the environment, falling back to `DATABASE_URL` in
  `.env.local` if present.
- **The tests must create a uniquely-named throwaway schema, run entirely inside it, and
  drop only that schema.** They will be pointed at the project's real Supabase database,
  so touching `public` is unacceptable: set `search_path` to the temporary schema, create
  the types and table there, and `DROP SCHEMA ... CASCADE` in teardown. A test that drops
  `public.datapoints` would destroy the thing this product exists to protect.
- Roll the schema name from a uuid4 so parallel or interrupted runs cannot collide.
- Do not write any fetcher or application code here.
