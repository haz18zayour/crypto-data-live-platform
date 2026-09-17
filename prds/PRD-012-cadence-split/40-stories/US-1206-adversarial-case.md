---
id: US-1206
title: The adversarial case — forced fast-tier staleness read, full-cycle row-count reconciliation across all three tiers, and confirmed canary/collect schedule independence
priority: 6
touches:
  - tests/test_persist_board.py
  - prds/PRD-012-cadence-split/50-evidence/
context:
  - AGENTS.md
  - prds/PRD-012-cadence-split/30-spec.md
  - project-documents/25_PRD_Acceptance_Protocol.md
---

As the owner, I want direct proof that this PRD's specific guarantees hold — that a fast-tier
cell's tight freshness bound is actually honored, that splitting one job into three tiers drops
or duplicates no row, and that the collect and canary schedules are genuinely independent — not
just proven by a green test suite that nobody thought to point at exactly these failure modes.

Per `25_PRD_Acceptance_Protocol.md`, every PRD's acceptance demonstration needs "an adversarial
case chosen to attack this PRD's specific guarantee," not a general regression test.

## Acceptance criteria

- [test: a simulated missed fast-tier collection window causes the affected cell to read STALE within its existing 450-second freshness-warn bound, not hours or days later] Directly tests the fast tier's whole reason for existing
- [test: over one full cycle (one fast + one medium + one daily run), the union of persisted rows equals the full 71-row registry set exactly once each — no row missing, no row duplicated across tiers] Directly guards against the blind spot research flagged: a canary can pass shape-checks while a tier filter silently drops or duplicates a row
- [human: the owner confirms, from real Healthchecks.io check history or a real dispatched run, that contract-canary's 6-hourly heartbeat and the new tiered collect heartbeats fire independently of each other — a failure in one schedule does not silently suppress or trigger the other] The demonstration item the acceptance protocol calls for, not a machine check

## Notes for the implementer

- This story does not change any production code by itself unless the tests above find a defect
  in an earlier story's tier filter or freshness fields — if they pass against the existing
  implementation unmodified, that is the demonstration succeeding, not a sign the story did
  nothing.
- The `[human]` criterion is the one this framework will not let any agent judge for you. Do not
  attempt to satisfy it with an automated check; leave it for the G6 gate.
- If a genuinely useful captured artifact (e.g. real Healthchecks.io check timestamps across all
  four schedules over a real cycle) would make the human criterion easier to judge quickly,
  produce one in `prds/PRD-012-cadence-split/50-evidence/US-1206/` — optional, not a substitute
  for the owner actually looking at real check history.
