---
id: US-201
title: Bar-slice contract — exactly N bars, or an error
priority: 1
touches:
  - ingest/registry.py
  - ingest/registry.yaml
  - ingest/compute.py
  - tests/test_bar_slice.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want every indicator to declare exactly how many bars it is computed over, and
the compute boundary to reject any other length, so that a value cannot drift as a cache grows.

The prior system computed its ATR modifier, Bollinger squeeze quantile and OBV normaliser over
"whatever `ohlcv_cache` currently holds, which grows forever from a 500-bar seed", and its own
post-mortem recorded the result as **"Same market, different score."**

Research (`10-research.md`) shows why pinning the window is not enough: TA-Lib's recursive
functions — EMA, RSI, ATR, ADX, CMO, DX, KAMA, T3 among ~22 — carry an *unstable period*, so
the same bar computed over 500 bars and over 5000 differs **at the final bar**, converging
rather than snapping. "Same bars, same window" therefore does not mean "same number". Only an
exact slice length does.

## Acceptance criteria

- [test: registry rejects an indicator with no required_bars] Every entry declares the exact bar count it is computed over; an entry without one fails validation at load
- [test: compute rejects a slice longer than required_bars] Passing 600 bars to an indicator declaring 500 raises — "at least N" is not the contract, exactly N is
- [test: compute rejects a slice shorter than required_bars] Too few bars is an error, never a partial computation over what happened to arrive
- [test: the same bars produce the same value across repeated calls] Called twice in one process and once in a fresh interpreter, the result is byte-identical
- [test: a growing cache cannot change a computed value] Simulates the prior system's bug directly — seed a slice, extend it, and assert the boundary refuses the longer slice rather than returning a drifted number
- [cmd: uv run mypy ingest --strict] Strict typing passes

## Notes for the implementer

- `required_bars` is a mandatory registry field, alongside `source_field` and `definable_for`.
- The check belongs at the **compute boundary**, not inside each indicator, so a new indicator
  inherits it without remembering to.
- **Do not add TA-Lib in this story.** If a later story does, it must add an autouse fixture
  asserting `TA_SetUnstablePeriod` is at its default in the same commit — it is process-global
  mutable state that "must be initialized from a single thread" and follows the function
  everywhere, so one test setting it changes every later test in the process. Under random
  ordering that reproduces "same market, different score" *inside the determinism suite*.
- Never synthesise a bar to reach the required count. Freqtrade's "Missing data fillup" does
  exactly that — logging `217.95%` fillup on a 68%-incomplete series — which turns a hole into
  a structurally valid lie. Too few bars is an error.
