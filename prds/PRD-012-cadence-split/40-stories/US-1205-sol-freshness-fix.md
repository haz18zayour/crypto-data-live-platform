---
id: US-1205
title: sol_active_addresses registry freshness fields corrected to match its real weekly schedule
priority: 5
touches:
  - ingest/registry.yaml
  - tests/test_registry.py
context:
  - AGENTS.md
  - prds/PRD-012-cadence-split/20-decisions.yaml
  - .github/workflows/sol-active-addresses.yml
---

As the owner, I want `sol_active_addresses`'s declared registry freshness fields to match the
weekly schedule it has actually run on since PRD-007, so this cell stops reading `STALE` against
its own declared contract for roughly 5 of every 7 days — a mismatch discovered live during
PRD-012's own G1 verification, not something this PRD's cadence-split logic causes or depends on.

`ingest/registry.yaml`'s `sol_active_addresses` entry currently declares
`expected_update_interval_seconds: 86400` and `freshness_stale_seconds: 172800` (daily/2-day),
but `.github/workflows/sol-active-addresses.yml` runs on `cron: '43 3 * * 0'` — weekly. This
story does not change the schedule (a separate, already-settled PRD-007/US-707 decision driven
by Helius's credit budget); it corrects the registry's own declared expectation to match reality.

## Acceptance criteria

- [test: sol_active_addresses' expected_update_interval_seconds reflects its real ~7-day cadence, not 86400] The core correction
- [test: sol_active_addresses' freshness_warn_seconds and freshness_stale_seconds are sized with real headroom above the ~7-day cadence, not the current daily/2-day values] Enough slack that a normal weekly run never trips a false warning
- [test: no other registry entry's freshness fields are altered by this change] Isolated, single-entry correction
- [test: a datapoint persisted at the moment sol-active-addresses.yml's real cron last fired reads fresh (not STALE) under the corrected fields for the full week until its next scheduled run] Directly proves the fix — the cell must not fall into STALE partway through a normal week
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- This is a registry-only change. Do not touch `.github/workflows/sol-active-addresses.yml`'s
  own cron — that schedule is out of scope for this story and this PRD.
- Pick concrete values for `expected_update_interval_seconds`/`freshness_warn_seconds`/
  `freshness_stale_seconds` and state your reasoning for the exact numbers chosen (e.g. how much
  headroom above 7 days) in this story's evidence, the same way every other registry entry in
  this project documents its freshness reasoning.
