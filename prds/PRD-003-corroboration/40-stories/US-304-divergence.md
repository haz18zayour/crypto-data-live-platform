---
id: US-304
title: Divergence computed and stored against the registry tolerance
priority: 4
touches:
  - ingest/corroborate.py
  - ingest/registry.yaml
  - ingest/registry.py
  - tests/test_divergence.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the divergence between two venues measured in basis points and judged
against a per-indicator tolerance, so that a real error is distinguishable from ordinary venue
basis.

Measured 2026-09-10, OKX `BTC-USDT` 1Dutc vs Coinbase `BTC-USD`, 59 UTC days: **median 7.1
bps, p90 10.8, max 13.8**. The `bar=1D` defect was **35.2 bps** — 2.5× the worst honest
disagreement. **Tolerance: 25 bps**, sitting in that gap.

Two things recorded rather than hidden: 59 days is a small sample and a violent day may exceed
13.8; and Coin Metrics excludes a market at **300 bps**, so ours is roughly one-fifteenth of
the loosest shipped equivalent and **will fire more often than intuition suggests**. That is
correct for a system that reports rather than resolves.

## Acceptance criteria

- [test: divergence is computed in basis points against the midpoint] Not against either venue's value, which would make the sign of the comparison matter
- [test: tolerance is read per indicator from the registry, never a global constant] A global tolerance ignores that BTC-USDT vs BTC-USD carries the USDT peg basis
- [test: the tolerance in force at write time is stored on the record] A later registry edit cannot retroactively re-judge history
- [test: a divergence inside tolerance is recorded as corroborated, and still stores the number] Agreement is evidence too; storing only disagreement loses the baseline that justifies the threshold
- [test: no code path averages, medians or otherwise combines the two values] Asserted directly — this is the failure the PRD exists to prevent
- [test: a 35 bps divergence is flagged and a 13 bps divergence is not] The measured defect and the measured worst-honest-case, pinned as a regression
- [integration: a real run against both live venues stores a divergence with its tolerance] Both venues hit for real, result persisted

## Notes for the implementer

- Registry gains `corroboration:` with `venue`, `pair` and `tolerance_bps` per indicator.
- **Never resolve.** No averaging, no "primary wins", no median. If the two disagree, both
  values and the divergence are what gets stored.
- Store the divergence even when it is small — the baseline is what makes a future threshold
  change defensible.
