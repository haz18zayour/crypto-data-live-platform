---
id: US-406
title: MACD and StochRSI via a differential oracle that cannot be a tautology
priority: 6
touches:
  - ingest/indicators.py
  - ingest/registry.yaml
  - tests/test_differential.py
context:
  - AGENTS.md
  - prds/PRD-004-indicators/10-research.md
---

As the owner, I want MACD and StochRSI checked against a second, genuinely independent
implementation, because no publisher tabulates worked examples for them — and I want proof the
second implementation really is independent.

**The trap, and it has no visible symptom.** `pandas-ta-classic` documents that *"34 core
indicators auto-use TA-Lib's C implementation when installed; pass `talib=False` to force
native."* Our environment always has TA-Lib installed — it is the compute engine. A differential
test written the obvious way therefore compares **TA-Lib against TA-Lib** and passes
unconditionally. That is US-006's failure at library scope.

**And StochRSI's defaults are wrong for the world.** TA-Lib's signature is
`STOCHRSI(close, timeperiod=14, fastk_period=5, ...)` — `fastk_period` defaults to **5**, while
the near-universal published convention is 14. TA-Lib also applies the *fast* stochastic where
TradingView applies the smoothed form, so TA-Lib's `fastd` corresponds to TradingView's **K**,
not its D. Shipping the defaults produces a number that is defensible, reproducible,
self-consistent, and matches no external reference on earth.

## Acceptance criteria

- [test: the differential oracle asserts talib=False is actually in effect] Not merely passed as an argument — asserted, so the tautology cannot return silently
- [test: forcing the oracle to delegate to TA-Lib makes the differential test fail] Proves the guard bites rather than being decorative
- [test: MACD agrees with the independent implementation within epsilon after warm-up] Compared on the converged tail, not the leading bars
- [test: StochRSI uses fastk_period 14, not TA-Lib's default of 5] Asserted against the registry
- [test: the registry records that TA-Lib fastd corresponds to TradingView K] So a future reader comparing against a chart is not misled
- [cmd: uv run pytest tests/test_differential.py -q --no-header -o addopts= --tb=short] Runs on its own

## Notes for the implementer

- `pandas-ta-classic` is a **test-only** dependency. It must not enter the runtime path.
- Two implementations agreeing is weaker evidence than a published number — they can share an
  inherited error. That is why this story covers only the two families no publisher tabulates,
  and why US-404 remains the merge gate.
