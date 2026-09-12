---
id: US-410
title: A differential oracle that cannot be a tautology
priority: 7
touches:
  - ingest/indicators.py
  - tests/test_differential.py
context:
  - AGENTS.md
  - prds/PRD-004-indicators/10-research.md
---

As the owner, I want MACD and StochRSI checked against a second implementation, with proof that
the second implementation is genuinely independent, because no publisher tabulates worked
examples for either.

**The trap has no visible symptom.** `pandas-ta-classic` documents that *"34 core indicators
auto-use TA-Lib's C implementation when installed; pass `talib=False` to force native."* Our
environment always has TA-Lib — it is the compute engine. A differential test written the
obvious way therefore compares **TA-Lib against TA-Lib** and passes unconditionally.

Passing `talib=False` is not enough on its own; the test must prove delegation did not happen.

## Acceptance criteria

- [test: the oracle asserts TA-Lib is installed and available] So the independence claim is meaningful rather than vacuous on a machine where delegation was impossible anyway
- [test: the oracle proves TA-Lib was not called during the independent computation] By spying on the TA-Lib function, not by trusting the flag
- [test: forcing delegation makes the differential test fail] The guard is demonstrated to bite, not merely present
- [test: MACD agrees with the independent implementation within epsilon on the converged tail] Compared after warm-up, not across the leading bars where both are unconverged
- [test: StochRSI agrees with the independent implementation on the converged tail] Using the registry's parameters, not library defaults
- [cmd: uv run pytest tests/test_differential.py -q --no-header -o addopts= --tb=short] Runs on its own

## Notes for the implementer

- `pandas-ta-classic` is **test-only**. It must not enter the runtime path.
- Registration is US-409's job and is already done — read the parameters from the registry
  rather than hardcoding them here.
- Two implementations agreeing is weaker evidence than a published number; they can share an
  inherited error. That is why this covers only the two families no publisher tabulates, and
  why US-404's published vectors remain the merge gate.
