---
id: US-411
title: MACD and StochRSI — registered, oracle-checked, coverage green
priority: 6
touches:
  - ingest/registry.yaml
  - ingest/registry.py
  - ingest/indicators.py
  - ingest/schemas.py
  - tests/goldens/**
  - tests/test_differential.py
  - tests/test_macd_stochrsi.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
  - prds/PRD-004-indicators/10-research.md
---

As the owner, I want MACD and StochRSI registered, computed, checked against an independent
implementation, and leaving the repository's coverage invariant green — in one story, because
these are not separable.

**Why this is one story.** A previous split registered the two indicators without their goldens
and coverage failed immediately: *"btc_macd is missing a golden file; okx has no response model
for btc_macd"*. That was PRD-002's registry-generated coverage working correctly. Registering an
indicator and supplying its evidence are the same act, and no publisher tabulates worked
examples for these two — so the golden can only come from the differential oracle. They are
coupled; treat them as one.

**Three traps, all from `10-research.md`:**

1. **`pandas-ta-classic` silently delegates to TA-Lib when TA-Lib is installed** — ours always
   is, since it is the compute engine. A differential test written the obvious way compares
   TA-Lib against TA-Lib and passes unconditionally, with no visible symptom.
2. **TA-Lib's `STOCHRSI` defaults `fastk_period` to 5**, not the near-universal 14, and applies
   the *fast* stochastic where TradingView applies the smoothed form — so TA-Lib's `fastd`
   corresponds to TradingView's **K**, not its D.
3. **MACD carries no unstable-period annotation and needs 250 bars anyway.** Its EMA-26 is
   recursive regardless of what the docs annotate.

## Acceptance criteria

- [test: load_registry returns IndicatorDefinition entries for MACD and StochRSI] Parsed objects — a substring search of registry.yaml cannot tell an entry from a comment
- [test: the loaded StochRSI definition declares fastk_period 14 and MACD declares required_bars 250] Read from parsed parameters, not file text
- [test: the oracle proves TA-Lib was not called during the independent computation] By spying on the TA-Lib function, not by trusting the talib=False flag
- [test: forcing delegation makes the differential test fail] The guard demonstrated to bite, not merely present
- [test: MACD and StochRSI agree with the independent implementation on the converged tail] After warm-up, using the registry's parameters
- [test: registry coverage passes over the whole registry] Goldens and response models exist for both new entries — the invariant PRD-002 established, not a special case
- [cmd: uv run pytest -q --no-header -o addopts=] The entire suite is green, including the canary and coverage tests

## Notes for the implementer

- `pandas-ta-classic` is **test-only** and must not enter the runtime path.
- The goldens for these two are generated from the independent implementation and must record
  that provenance honestly — they are weaker evidence than US-404's published vectors, and the
  `source` field should say so rather than implying parity.
- Leave the repository green. A story that registers an indicator and breaks coverage has not
  finished.
