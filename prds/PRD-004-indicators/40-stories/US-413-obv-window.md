---
id: US-413
title: OBV needs a window chosen for the board, not for the test
priority: 10
touches:
  - ingest/registry.yaml
  - tests/test_obv_window.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want OBV computed over a span long enough to mean something, with the choice of
span written down, because it currently uses five days and nobody decided that.

OBV went from `required_bars: 1` to `required_bars: 5`. **Five is the length of its own
hand-computed golden vector** — the smallest number that satisfied a criterion reading "greater
than 1". It was not chosen for the product, and no reasoning was recorded.

OBV is cumulative: it accumulates signed volume, so its entire informational content is *how
much conviction has built up over a span*. Five daily bars of that is noise. The indicator is
not wrong — the formula matches its StockCharts golden — it is simply being asked a question too
short to have an interesting answer.

Unlike RSI or EMA there is no convergence point to measure toward, because OBV never converges;
it drifts with cumulative volume forever. So the window is a **product decision** and must be
stated as one.

## Acceptance criteria

- [test: OBV declares required_bars of at least 200] Long enough to accumulate a meaningful span on a daily board
- [test: the OBV registry entry carries a note explaining why that window was chosen] Read from the parsed definition — the reasoning is part of the indicator, not a commit message
- [test: OBV over its declared window differs materially from OBV over 5 bars] Proves the window is load-bearing rather than nominal
- [test: the existing hand-computed golden still passes at its own vector length] Formula correctness and window choice are separate claims and must be tested separately
- [test: registry coverage passes over the whole registry] The invariant holds
- [cmd: uv run pytest -q --no-header] The default offline suite is green

## Notes for the implementer

- Do **not** change the golden to match a new window. The golden proves the formula; this story
  decides the span. Conflating them would let a window change silently invalidate the formula
  evidence.
- The note belongs on the registry entry so it travels with the indicator. A reader asking "why
  200?" in six months should find the answer next to the number, not in git history.
