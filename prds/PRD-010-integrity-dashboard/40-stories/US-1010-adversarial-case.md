---
id: US-1010
title: The adversarial case — a real frozen sequence trips the flag, propagation to a derived indicator, a wall-clock fetcher never shows green, a stale integrity read is visible as stale, and the coverage gate rejects a placeholder
priority: 4
touches:
  - tests/test_integrity_adversarial.py
  - web/src/integrity.test.ts
context:
  - AGENTS.md
  - project-documents/25_PRD_Acceptance_Protocol.md
  - prds/PRD-010-integrity-dashboard/10-research.md
---

As the owner, I want this PRD's five hardest claims proven directly against realistic scenarios,
not just asserted by the individual stories' own narrower unit tests — the same adversarial
discipline every prior PRD in this project has closed with.

## Acceptance criteria

- [test: seeding a throwaway schema with a real sequence of distinct-source_timestamp rows holding an identical value for exactly frozen_after_observations observations (using the postgres fixture, real database, not a mock) causes US-1002's read to report that root indicator as frozen; one fewer observation, or any single differing value in the sequence, reports it as not frozen] The exact boundary, proven directly, not assumed from the SQL alone
- [test: seeding the same throwaway schema so a root indicator is frozen, and a dependent indicator (real derives_from link from the registry) has genuinely different, moving values of its own, still reports the dependent as frozen via propagation] The finding that motivated this whole PRD, proven end to end — a derived indicator whose own values are moving is still correctly flagged, because what matters is its root's honesty, not its own superficial variance
- [test: a registry entry declaring freshness_unmeasurable never reports a fresh/warn/stale state from US-1002's read regardless of how recent or old its most recent row is] The false-comfort gap closed, proven at the boundary
- [test: constructing an integrity read with a computed_at older than US-1003's threshold causes the frontend client to classify it as stale-self-check even when every individual indicator's own freshness/frozen state would otherwise read as healthy] The panel cannot present a false all-clear from an old snapshot
- [test: attempting to satisfy US-1006's coverage gate with a placeholder — a golden fixture byte-copied from an existing indicator's golden, or a test function that references a key's name in a comment/string without asserting anything about it — causes the coverage pytest to fail] The gate resists exactly the gaming research warned about
- [human] The owner opens the live integrity panel and the board, confirms at least one real or deliberately-seeded frozen indicator shows its badge with a correct date, confirms the freshness rollup shows real per-vendor ages with the two wall-clock fetchers reading "unmeasurable" rather than green, and confirms nothing about the panel implies a judgement (a score, a colour ranking, a composite health number) beyond the honest per-source facts this PRD computes
- [cmd: uv run pytest -q] The full offline suite stays green
- [cmd: npm --prefix web test && npm --prefix web run typecheck] The full web suite and typecheck stay green

## Notes for the implementer

- The `[human]` criterion is the one this framework will not let any agent judge. Do not attempt to
  satisfy it with an automated check; leave it for the G6 gate.
- Every criterion above must exercise the *real* propagation/exemption/staleness logic already built
  by US-1002 through US-1006 — do not re-derive a parallel, simplified version of any of them just
  to make this story's own tests easier to write. If a criterion cannot be proven against the real
  implementation, that is a signal the earlier story's implementation is incomplete, not that this
  story's test should be softened.
- If the production migration from US-1002 has not yet landed by the time this story runs, the
  `[human]` criterion's live-board portion cannot yet be satisfied — say so plainly rather than
  presenting the offline tests as if they covered it.
