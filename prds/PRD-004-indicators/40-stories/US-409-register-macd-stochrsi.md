---
id: US-409
title: Register MACD and StochRSI with corrected parameters
priority: 6
touches:
  - ingest/registry.yaml
  - ingest/registry.py
  - tests/test_macd_stochrsi_registry.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want MACD and StochRSI registered as real indicator definitions with parameters
chosen deliberately, so the board can compute them and a future reader can see why the numbers
differ from a charting site.

**Two parameter traps, both from `10-research.md`:**

TA-Lib's signature is `STOCHRSI(close, timeperiod=14, fastk_period=5, fastd_period=3, ...)`.
`fastk_period` defaults to **5**, while the near-universal published convention is **14**. TA-Lib
also applies the *fast* stochastic where TradingView applies the smoothed form, so TA-Lib's
`fastd` output corresponds to TradingView's **K**, not its D. Ship the defaults and the board
displays a number that is defensible, reproducible, self-consistent, and matches no external
reference on earth.

**MACD must declare 250 bars** even though TA-Lib annotates only RSI and STOCHRSI with an
unstable period. Its EMA-26 is recursive regardless of the annotation. Measured on real BTC
closes, RSI(14) on the same final bar reads 47.56 at 15 bars and 59.50 converged — a 12-point
error from history length alone.

## Acceptance criteria

- [test: load_registry returns IndicatorDefinition entries for MACD and StochRSI] Parsed and validated objects — a substring search of registry.yaml cannot tell an entry from a comment
- [test: the loaded StochRSI definition declares fastk_period 14] Read from the parsed parameters, not the file's text
- [test: the loaded MACD and StochRSI definitions declare required_bars 250] Both recursive, despite TA-Lib annotating only one of them
- [test: each declares its talib_function and full parameter set explicitly] No reliance on a library default for anything that changes the number
- [test: the registry note records that TA-Lib fastd corresponds to TradingView K] Present on the parsed definition, so a reader comparing against a chart is not misled
- [cmd: uv run python -m ingest.registry --validate] The shipped registry validates

## Notes for the implementer

- **This story is registration only.** The differential oracle is US-410; do not build it here.
- A previous attempt satisfied a similar criterion by adding comment lines plus a test that
  grepped the file with `read_text()`. The test passed and nothing was registered. Assert
  against parsed objects.
