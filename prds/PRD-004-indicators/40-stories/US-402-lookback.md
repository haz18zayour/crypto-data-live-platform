---
id: US-402
title: required_bars validated against TA-Lib's own lookback
priority: 2
touches:
  - ingest/registry.py
  - ingest/registry.yaml
  - tests/test_lookback.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want every indicator's `required_bars` checked against the minimum TA-Lib
itself reports, so that a number I chose by reading a table is verified by the engine that will
compute it.

TA-Lib's abstract API exposes `Function(name).lookback` — the leading inputs consumed before
the first output, **for the given parameters**. That is the mechanical floor, free and
per-parameter. It does not prove convergence; it proves legality.

## Acceptance criteria

- [test: every registry indicator declares required_bars greater than its TA-Lib lookback] Derived from the registry, so a new indicator is covered without anyone remembering
- [test: lookback is read for the indicator's actual parameters, not defaults] RSI(14) and RSI(21) have different lookbacks; the check must use what the registry declares
- [test: an indicator whose required_bars is below its lookback fails validation] Proven by constructing one, so the mechanism bites
- [test: recursive indicators declare at least 250 bars] RSI, ATR, EMA, StochRSI and MACD — the published convergence figure, not the mechanical floor
- [cmd: uv run python -m ingest.registry --validate] The shipped registry validates

## Notes for the implementer

- **MACD must declare 250 despite TA-Lib carrying no unstable-period annotation for it.** The
  docs annotate RSI and STOCHRSI and leave MACD alone, so a reader deriving N from the
  annotations sets MACD at 35. The EMA-26 inside it is recursive regardless of the docs.
- Lookback is the floor and 250 is the target; the test asserts both, because they answer
  different questions — "is this legal" and "is this converged".
