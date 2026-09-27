---
id: US-808
title: The adversarial case — the staleness gradient read at a glance, the DXY-string grep, and the Fear & Greed disclosure demonstration
priority: 8
touches:
  - tests/test_registry_not_definable.py
  - prds/PRD-008-macro-flows/50-evidence/
context:
  - AGENTS.md
  - project-documents/25_PRD_Acceptance_Protocol.md
---

As the owner, I want direct proof that this PRD's specific guarantee holds — that "macro" is not
one uniform freshness bucket, that no free DXY feed is ever mislabeled as DXY, and that Fear &
Greed reads as a labeled vendor composite rather than an implied signal — because a green test
suite proves nothing about a distinction nobody thought to test for directly.

Per `25_PRD_Acceptance_Protocol.md`, every PRD's acceptance demonstration needs "an adversarial
case chosen to attack this PRD's specific guarantee," not a general regression test.

## Acceptance criteria

- [human: the owner reads the live macro panel and confirms same-day rows (VIX, DFF, T10Y2Y, DFII10), the weekly-release row (DTWEXBGS), and the two monthly rows (CPIAUCSL, M2SL) each show their own real reference period and published date, with none implying same-day freshness it doesn't have] The demonstration item the acceptance protocol calls for, not a machine check
- [test: the literal string "DXY" never appears as a label anywhere in the rendered board or its source code — only, if present at all, inside an explanatory disclosure distinguishing DTWEXBGS from ICE's proprietary DXY] Directly guards against the exact mislabeling this PRD's brief was written to prevent
- [test: every not_definable reason string this PRD's stories registered (BNB's ETF-flow absence, BTC's stablecoin-supply absence) is unique — no two entries share identical reason text, and neither matches any pre-existing NOT_DEFINABLE reason on the board] Directly guards against the category-collapse this project's history already identified once
- [test: the Fear & Greed cell's rendered face includes alternative.me's name, its composite-weight disclosure, and the paused-surveys note] Confirms US-806's disclosure criterion holds at the rendered-board level, not just in the fetcher's own unit tests

## Notes for the implementer

- This story does not change any production code by itself unless the tests above find a defect
  in an earlier story's registry entries or rendering — if they pass against the existing
  implementation unmodified, that is the demonstration succeeding, not a sign the story did
  nothing.
- The `[human]` criterion is the one this framework will not let any agent judge for you. Do not
  attempt to satisfy it with an automated check; leave it for the G6 gate.
- If a genuinely useful captured artifact (e.g. a screenshot of the four-cadence staleness
  gradient) would make the human criterion easier to judge quickly, produce one in
  `prds/PRD-008-macro-flows/50-evidence/US-808/` — optional, not a substitute for the owner
  actually looking at the live page.
