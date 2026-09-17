---
id: US-1201
title: Registry tier filter — one shared entrypoint accepts --tier {fast,medium,daily}, partitioning by expected_update_interval_seconds with no row dropped or duplicated
priority: 1
touches:
  - ingest/pipeline.py
  - ingest/registry.py
  - tests/test_registry.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - prds/PRD-012-cadence-split/10-research.md
  - project-documents/10_Technical_Architecture.md
---

As the owner, I want one shared pipeline entrypoint that can be told which cadence tier to
collect, so a future fix to fetch/write/heartbeat logic needs one change instead of three
duplicated scripts, and so no registry row can silently fall through a filter gap or land in
two tiers at once.

The registry's `expected_update_interval_seconds` field already exists and already discriminates
exactly three values across all 71 entries (verified at G1: `300` x12, `28800` x4, `86400` x55).
This story adds the filter; it does not change what any indicator's cadence is declared to be.

## Acceptance criteria

- [test: a `--tier fast` run collects exactly the 12 registry entries with expected_update_interval_seconds == 300, and no others] The fast tier, exactly
- [test: a `--tier medium` run collects exactly the 4 registry entries with expected_update_interval_seconds == 28800, and no others] The medium tier, exactly
- [test: a `--tier daily` run collects exactly the 54 registry entries with expected_update_interval_seconds == 86400, and no others] The daily tier, exactly
- [test: the union of one fast + one medium + one daily run's persisted rows equals the full 71-row registry set with no row missing and no row appearing twice] Directly guards against a row silently falling through a filter gap or landing in two tiers
- [test: a registry entry with an expected_update_interval_seconds value outside {300, 28800, 86400} causes an explicit, named error at load time rather than silently being excluded from every tier] Fail loud if a future story ever adds a 4th cadence value without updating the tier filter
- [test: running with no --tier argument preserves the current full-registry behavior] Backward compatibility for any caller not yet updated to pass a tier
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Do not duplicate `run_all_assets`/`run_pipeline`/`run_scheduled_board`'s fetch, write, or
  heartbeat logic across tiers — the filter should restrict which registry rows a single run
  processes, not fork the pipeline itself.
- This story does not touch any GitHub Actions workflow file — that is US-1202/1203/1204. This
  story is the shared Python-side filter those workflows will each call with their own tier.
