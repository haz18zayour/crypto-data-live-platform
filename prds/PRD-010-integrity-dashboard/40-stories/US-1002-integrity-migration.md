---
id: US-1002
title: Integrity migration — frozen-state and freshness views/RPC outside the ingest path, applied to production before any downstream story runs
priority: 2
touches:
  - supabase/migrations/
  - supabase/migrations/checksums.sha256
  - tests/test_integrity_read.py
context:
  - AGENTS.md
  - prds/PRD-010-integrity-dashboard/10-research.md
  - prds/PRD-010-integrity-dashboard/20-decisions.yaml
---

As the owner, I want frozen-value and freshness state computed by a read-only view or RPC entirely
outside the ingest path, so that a stopped pipeline cannot silently stop its own audit, and so a
historical value's staleness is judged from real data age rather than from whether a scheduled
GitHub Actions run happened to fire.

This is a genuine migration and follows this project's established blast-radius discipline: written,
reviewed, and applied to production with the owner's explicit sign-off before US-1003 through
US-1006 may be considered unblocked — the same gating PRD-009's `origin` column followed before any
backfill story could run.

## Acceptance criteria

- [test: a new SQL function/view computes freshness state (fresh/warn/stale/unmeasurable) per indicator+asset+vendor from source_timestamp age versus the registry's freshness_warn_seconds/freshness_stale_seconds, taking freshness_unmeasurable-declared entries straight to unmeasurable regardless of age] Freshness, computed from data age, not run history
- [test: the same read computes frozen state for a root indicator (no derives_from) as true only when its latest frozen_after_observations rows, ordered by distinct source_timestamp, share a bit-identical value, and false the moment any of those values differs] Frozen, over distinct observations only, per the project's own upsert-key finding — never over repeated fetches of the same source_timestamp
- [test: an entry declaring expected_constant is never flagged frozen regardless of how many consecutive identical values it holds] The explicit exemption holds
- [test: a dependent indicator (derives_from set) reports its declared root's own frozen state rather than computing an independent identical-value check on itself] Propagation, not independent detection
- [test: an entry declaring frozen_propagation_unavailable (US-1001's honest exemption for ETH/SOL/BNB's technical indicators, which have no registered root to derive from) reports a distinct propagation-unavailable state, never a false "not frozen" and never an independent identical-value check run on the derived series itself] No silent downgrade to a check research already found unreliable for derived indicators, and no pretending the answer is known when it isn't
- [test: the read returns a server-clock computed_at timestamp alongside every result] The self-check stamp US-1003 will consume
- [test: the migration is purely additive — no existing column, constraint, or datapoint_status value changes, and every pre-existing row's live board rendering is unaffected] No blast radius beyond the new objects themselves
- [test: applying the migration to a throwaway schema (via the existing postgres fixture, real database, not a mock) seeded with real registry declarations and real persisted rows (a frozen root, a propagating dependent, an expected_constant entry, an unmeasurable entry) produces the exact states described above] Proves the SQL against a real database, not an assumption about it — this project's established convention marks a throwaway-schema real-Postgres test UNMARKED, not [integration:], which is reserved for a genuinely live third-party vendor or deployed-instance call
- [integration: once applied to production, the deployed PostgREST endpoint for the new integrity RPC responds successfully over a real HTTP call using the anon/authenticated grants (not the service-role key), for at least one real, currently-populated indicator/asset] Directly checks that the RPC is actually reachable through the real deployed system, not merely present in the schema — this project has already been bitten once by a migration that worked in isolation but never returned real data through the actual browser call path (US-908's sourceVendor case-sensitivity defect) and once by a PostgREST schema cache that needed an explicit reload notification
- [cmd: uv run pytest -q -m "not integration"] The full offline suite stays green

## Notes for the implementer

- `.uf/config.json`'s `blastRadius` lists `**/migrations/**` — this story is blast radius and G4
  applies before merge. This migration must additionally be **applied to the real production
  database with explicit owner sign-off** before US-1003 through US-1006 may be considered
  unblocked, per this project's established manual-migration-apply discipline.
- Follow the existing migration file naming convention (`YYYYMMDDHHMMSS_description.sql`) and the
  existing `checksums.sha256` update pattern.
- Do not build any UI or API surface for this in this story — US-1003 through US-1006 consume this
  view. This story is the SQL and its own direct tests only.
