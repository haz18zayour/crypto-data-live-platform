---
id: US-412
title: The missing EMA stack, and OBV's meaningless one-bar window
priority: 9
touches:
  - ingest/registry.yaml
  - ingest/registry.py
  - ingest/indicators.py
  - tests/goldens/**
  - tests/test_ema.py
  - tests/test_obv_window.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
  - prds/PRD-004-indicators/10-research.md
---

As the owner, I want the EMA stack built and OBV given a real window, because PRD-004 passed
8/8 with both defects present and neither was caught by any criterion.

**Defect 1 — EMA(20/50/200) was specified and never built.** `30-spec.md` line 20 names it
alongside RSI, MACD, StochRSI, Bollinger, ATR and OBV. `grep -c "EMA" ingest/registry.yaml`
returns **0**. Registry coverage cannot catch this: it verifies that every registered indicator
has its evidence, and is structurally blind to an indicator nobody registered. **Absence is not
a thing the criteria describe.**

**Defect 2 — OBV is registered with `required_bars: 1`.** OBV is cumulative; it accumulates
signed volume across the whole series. Measured:

```
OBV over 5 bars : [100. 220. 130. 280. 410.]
OBV over 1 bar  : [130.]
```

Over one bar it returns that bar's volume carrying no history, so the value on the board is
noise wearing an indicator's name. The StockCharts golden passes because the *formula* is right;
only the window is wrong — which is precisely the shape of failure this product exists to
surface.

EMA is **recursive**, so it belongs to the 250-bar family. TA-Lib reports `EMA(200).lookback`
as 199 — that is the mechanical floor, not convergence. Measured on real closes, RSI(14) moves
12 points between 15 bars and its converged value; EMA(200) has a far longer memory than
RSI(14).

## Acceptance criteria

- [test: load_registry returns EMA entries for periods 20, 50 and 200 on every supported asset] Parsed IndicatorDefinition objects, not a substring search of the yaml
- [test: each EMA entry declares required_bars 250 and its timeperiod explicitly] Recursive family; no reliance on a library default
- [test: EMA is checked against an independently computed value] Hand-computed or published, with the source recorded on the golden as PRD-002 requires
- [test: OBV declares a required_bars of at least 200 and its registry note states why that window] A window that merely satisfies 'more than 1' is the golden vector's length, not a product decision — OBV accumulates conviction over a span, and 5 days of it says nothing on a daily board
- [test: OBV's value differs materially between its declared window and a 5-bar window] Demonstrates the window is load-bearing rather than nominal
- [test: OBV computed over its declared window matches its hand-computed golden] The existing StockCharts vector, at a window that carries history
- [test: registry coverage passes over the whole registry] Every new entry has a golden and a model — the invariant, not a special case
- [cmd: uv run pytest -q --no-header] The default offline suite is green
- [cmd: uv run python -m ingest.registry --validate] The shipped registry validates

## Notes for the implementer

- EMA(20), EMA(50) and EMA(200) are three separate registry entries per asset, each declaring
  its own `timeperiod`. They are not one "stack" entry.
- **Do not lower EMA's required_bars to its lookback.** TA-Lib's 199 for EMA(200) is the floor
  at which an output first exists, not the point at which it stops drifting.
- Choose OBV's window deliberately and record the reasoning in the registry note. Cumulative
  indicators have no natural convergence point, so the honest framing is "OBV over the last N
  bars", and N must be stated rather than implied.
