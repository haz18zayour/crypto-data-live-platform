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
- [test: the registry contains real MACD and STOCHRSI entries, loaded through load_registry] Parsed and validated as IndicatorDefinition objects — a substring search of registry.yaml proves only that a comment exists
- [test: the loaded STOCHRSI definition declares fastk_period 14, not TA-Lib's default of 5] Read from the parsed parameters, not from the file's text
- [test: the loaded MACD and STOCHRSI definitions declare required_bars 250] Both are recursive despite TA-Lib annotating only STOCHRSI
- [cmd: uv run pytest tests/test_differential.py -q --no-header -o addopts= --tb=short] Runs on its own

## Notes for the implementer

- `pandas-ta-classic` is a **test-only** dependency. It must not enter the runtime path.
- Two implementations agreeing is weaker evidence than a published number — they can share an
  inherited error. That is why this story covers only the two families no publisher tabulates,
  and why US-404 remains the merge gate.
- **Add the MACD and STOCHRSI registry entries in this story.** They are the two indicators
  this story owns; US-407 grows the registry to full scale but does not create these. A
  previous attempt added only comment lines and a test that grepped for them — the test
  passed and proved nothing, which is this project's signature failure appearing inside a
  story written to prevent it.
- **Assert against parsed objects, never file text.** `REGISTRY_PATH.read_text()` with a
  substring check cannot tell a registered indicator from a comment.
