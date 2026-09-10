---
id: US-301
title: "Schema: two venues as peers, divergence stored with its tolerance"
priority: 1
touches:
  - supabase/migrations/**
  - ingest/persist.py
  - tests/test_corroboration_schema.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want two venues stored as equals for one quantity, so that nothing in the
schema can express a preference between them.

**This story exists because of a collision that would otherwise lose data silently.** The
current upsert identity is `(indicator_key, asset, source_timestamp)`
(`ingest/persist.py:66-73`). Writing OKX and then Coinbase under one `indicator_key` means the
second write **UPDATEs the first** — one of the two numbers vanishes, with no error, which is
this project's signature failure mode wearing a new hat.

**BLAST RADIUS.** Touches `**/migrations/**` and the persist path that PRD-001 and PRD-002
proved. Manual G4 review before merge.

## Acceptance criteria

- [test: two venues for the same indicator and timestamp produce two rows] Writing OKX then Coinbase yields two rows, not one updated row
- [test: re-writing the same venue and timestamp still upserts] Idempotency from PRD-001 is preserved per venue, not lost to the new identity
- [test: a corroboration record stores divergence and the tolerance in force at write time] `tolerance_bps_at_write` is persisted, so a later registry edit cannot retroactively re-judge history
- [test: the schema has no column implying a primary or preferred venue] Asserted against the live column list — no `value_secondary`, no `is_primary`
- [integration: the migration applies to a real Postgres and both venues round-trip] Applied against a live database in a throwaway uuid4 schema, dropped afterwards
- [cmd: uv run pytest tests/ -q --no-header -o addopts= --tb=line] PRD-001 and PRD-002 suites still pass against the new identity

## Notes for the implementer

- Tests create a uuid4-named throwaway schema and drop only that. **Never touch `public`** —
  it holds the live spine.
- The advisory-lock key in `persist.py` is derived from the old identity; it must include the
  vendor or two venues will serialise against each other unnecessarily.
- Do not add a "preferred" or "primary" flag, even as a convenience. The brief's central risk
  is that a preference gets expressed later by someone who did not read the brief.
