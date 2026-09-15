---
id: US-708
title: The adversarial case — the four-asset on-chain column read at a glance, plus a forced PAYWALLED cell
priority: 8
touches:
  - tests/test_coinmetrics_fetcher.py
  - prds/PRD-007-onchain/50-evidence/
context:
  - AGENTS.md
  - prds/PRD-007-onchain/10-research.md
  - project-documents/25_PRD_Acceptance_Protocol.md
---

As the owner, I want direct proof that this PRD's specific guarantee holds — that collapsing
`NO-METRIC`, `PAID`, and genuinely `OK` into one blank cell is exactly the failure R2 named in
the prior system, and this board does not repeat it — because a green test suite proves nothing
about a distinction nobody thought to test for directly.

Per `25_PRD_Acceptance_Protocol.md`, every PRD's acceptance demonstration needs "an adversarial
case chosen to attack this PRD's specific guarantee," not a general regression test.

## Acceptance criteria

- [human: the owner reads the live board's MVRV, active-addresses, exchange-flow and staking rows across all four assets and confirms each absence reads distinctly — SOL's MVRV/exchange-flow NOT_DEFINABLE reason is not interchangeable with BNB's exchange-flow NOT_DEFINABLE reason, and neither is interchangeable with ETH's or BNB's staking NOT_DEFINABLE reason] The demonstration item the acceptance protocol calls for, not a machine check
- [test: a forced Coin Metrics `forbidden` response (the real `CapRealUSD` behavior on the free tier) renders as PAYWALLED on the board, never silently substituting a different metric's value in its place] The second, cheaper adversarial case named in the spec
- [test: every not_definable reason string registered by this PRD's stories is unique — no two entries share identical reason text] Directly guards against the category-collapse this PRD exists to prevent, checked mechanically across the whole registry, not just spot-checked by eye

## Notes for the implementer

- This story does not change any production code by itself unless the tests above find a
  defect in an earlier story's registry entries — if they pass against the existing
  implementation unmodified, that is the demonstration succeeding, not a sign the story did
  nothing.
- The `[human]` criterion is the one this framework will not let any agent judge for you. Do not
  attempt to satisfy it with an automated check; leave it for the G6 gate.
- If a genuinely distinguishable screenshot or captured board state would make the human
  criterion easier to judge quickly, produce one in `prds/PRD-007-onchain/50-evidence/US-708/` —
  optional, not a substitute for the owner actually looking at the live page.
