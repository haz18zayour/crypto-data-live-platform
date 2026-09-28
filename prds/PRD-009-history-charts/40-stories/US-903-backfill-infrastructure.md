---
id: US-903
title: Backfill job infrastructure — shared entry point, idempotent writes, and a coverage test requiring every registry entry to declare a recipe or an honest non-backfillable reason
priority: 3
touches:
  - ingest/backfill.py
  - ingest/registry.py
  - ingest/registry.yaml
  - tests/test_backfill_coverage.py
  - .github/workflows/backfill.yml
context:
  - AGENTS.md
  - prds/PRD-009-history-charts/10-research.md
  - prds/PRD-009-history-charts/20-decisions.yaml
---

As the owner, I want one shared, idempotent backfill entry point that every vendor recipe plugs
into, and a build-time guarantee that no registry entry can silently ship without either a real
backfill recipe or an honest declaration that it cannot be backfilled, so future PRDs cannot
quietly add an indicator that never gets history and nobody notices.

Research's own coverage-discipline precedent (PRD-002's registry coverage check) is the model:
turn "did we forget one" into a build failure, not a hope.

## Acceptance criteria

- [test: ingest/backfill.py exposes one entry point accepting an indicator_key (or all registered keys) and dispatches to that entry's own backfill recipe function] The shared entry point
- [test: every write from a backfill recipe goes through persist_datapoint/persist_board with origin='backfill', using the same unique index (indicator_key, asset, source_vendor, source_timestamp) as the live pipeline] One write path, not a second one
- [test: re-running backfill for an indicator that was already backfilled writes no duplicate rows] Idempotency, proven directly
- [test: a registry entry with neither a registered backfill recipe nor an explicit not_backfillable declaration fails the coverage test by name] The actual guarantee this story exists to build
- [test: Solana on-chain history (SOL active-address/staking-adjacent history cells) and validators.app both declare not_backfillable with their own distinct, real reasons, and the coverage test passes with both present] Proves the test accepts a genuine declared absence, not just a genuine recipe
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Depends on US-901 — every backfill write uses `origin='backfill'`, which does not exist until
  that migration lands.
- This story builds the shared mechanism and the coverage test only. Do not implement any
  vendor's actual historical fetch logic here — OKX, Coin Metrics, FRED, SoSoValue, DefiLlama, and
  alternative.me each get their own story (US-904 through US-907). A minimal fake/no-op recipe is
  sufficient here to prove the mechanism and the coverage test both work.
- The `not_backfillable` reason strings for Solana on-chain history and validators.app must each
  be genuinely distinct from each other and from every other NOT_DEFINABLE/UNAVAILABLE reason
  already on the board — this project's established anti-category-collapse discipline applies to
  this new vocabulary entry the same way it applies to every existing one.
- If a dedicated `backfill.yml` GitHub Actions workflow is added, it needs its own `env:` block
  with every secret its dispatched recipes will need (`FRED_API_KEY`, `SOSOVALUE_API_KEY`, etc.)
  — this project has twice shipped a workflow missing a required secret this session; check the
  workflow file directly rather than assuming.
