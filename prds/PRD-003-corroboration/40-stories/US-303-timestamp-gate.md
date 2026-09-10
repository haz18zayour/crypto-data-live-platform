---
id: US-303
title: Timestamp equality gates the comparison
priority: 3
touches:
  - ingest/corroborate.py
  - tests/test_timestamp_gate.py
context:
  - AGENTS.md
  - prds/PRD-003-corroboration/10-research.md
---

As the owner, I want the two timestamps checked for equality **before** any divergence is
computed, so that comparing two different days can never masquerade as a price disagreement.

Comparing day *N* against day *N+1* produces a real-looking number. On a quiet day that reads
as a plausible ~20 bps disagreement — **worse than an obvious failure**, because it is
believable. And the misalignment would not be occasional: our OKX fetcher converts bucket-start
to bucket-**end** (`okx.py:84-85`) while Coinbase returns bucket-start, so a convention mismatch
misaligns **every single run**.

This is also the assertion that would have caught the original `bar=1D` defect at the second
venue, rather than relying on the value comparison to reveal it.

## Acceptance criteria

- [test: unequal source timestamps produce no divergence at all] Not a large divergence, not zero — no comparison is performed
- [test: unequal timestamps are recorded as a distinct outcome naming both timestamps] So the diagnosis is immediate rather than inferred
- [test: equal timestamps proceed to comparison] The happy path is gated, not blocked
- [test: a timestamp that is not on a UTC midnight boundary is refused before comparison] Applies to both venues independently
- [test: comparison is refused when either timestamp lies in the future] The F11 defence, applied at the comparison boundary too

## Notes for the implementer

- The gate is a precondition, not a warning alongside the result. If the timestamps differ,
  there is no divergence value to report.
- **A shared bug here is invisible to corroboration.** If the same wrong offset is applied to
  both venues, divergence is exactly zero and the check reports agreement. The per-venue UTC
  assertions in US-302 are the only defence against that, which is why they are separate
  criteria in a separate story rather than folded in here.
