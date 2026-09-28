---
id: US-909
title: The adversarial case — sparse-history honesty, and a cross-vendor seam check proving no splice at the backfill/live boundary
priority: 9
touches:
  - tests/test_backfill_seam.py
  - prds/PRD-009-history-charts/50-evidence/
context:
  - AGENTS.md
  - project-documents/25_PRD_Acceptance_Protocol.md
  - prds/PRD-009-history-charts/10-research.md
---

As the owner, I want direct proof that this PRD's specific guarantees hold — that sparse history
never fakes a trend, and that the boundary between backfilled and live data is not a place a
silent value splice can hide — because a green test suite proves nothing about a distinction
nobody thought to test for directly.

Per `25_PRD_Acceptance_Protocol.md`, every PRD's acceptance demonstration needs "an adversarial
case chosen to attack this PRD's specific guarantee," not a general regression test. Research's
own blind-spot finding is explicit: a cross-check against the same endpoint and parameters
backfill used proves nothing about a splice — the check must land on a date within the overlap
between live and backfilled data, verified against the *live* endpoint's own value for that day.

## Acceptance criteria

- [test: a registry entry with exactly one persisted row renders the insufficient-history state, never a sparkline, and the test constructs this scenario directly rather than relying on whatever real indicator happens to be sparse at test time] Sparse-history honesty, proven deterministically
- [integration: for one real indicator with both live and backfilled rows, the backfilled value at a date within the overlap between the two matches a fresh, independent live call to that indicator's live endpoint for the same date] The actual seam check research's blind-spot analysis calls for — not a replay of backfill's own request
- [test: the board_read/datapoints_read fix from US-901 is confirmed still in effect after a real backfill run has executed — no backfilled row appears as any cell's current displayed value] Re-proves the single most likely defect this PRD identified does not exist in the final, fully-backfilled state
- [human: the owner reads the live board and confirms at least one sparkline shows a real historical swing (a genuine drawdown or spike already in the data) rendered accurately against real numbers, with the min/max labels' dates matching what the owner can independently see on the source vendor's own site or API] The demonstration item the acceptance protocol calls for, not a machine check

## Notes for the implementer

- This story does not change production code by itself unless the tests above find a defect in
  an earlier story's work — if they pass against the existing implementation unmodified, that is
  the demonstration succeeding, not a sign this story did nothing.
- The `[human]` criterion is the one this framework will not let any agent judge for you. Do not
  attempt to satisfy it with an automated check; leave it for the G6 gate.
- Pick the indicator for the human criterion carefully — it should be one where a real, visible
  swing already exists in backfilled history (research suggests checking BTC's own price/RSI
  history, or funding rate around a known volatile period), not an indicator whose real history
  happens to be flat.
