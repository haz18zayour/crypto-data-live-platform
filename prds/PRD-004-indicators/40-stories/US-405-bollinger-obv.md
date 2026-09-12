---
id: US-405
title: Bollinger and OBV, population stdev, hand-computed goldens
priority: 5
touches:
  - ingest/indicators.py
  - tests/goldens/**
  - tests/test_bollinger_obv.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want Bollinger and OBV computed with their conventions pinned and their goldens
hand-computed, so the two indicators a human can actually verify by arithmetic are verified
that way.

Bollinger's own published defaults: **20 periods, two standard deviations**. TA-Lib's `BBANDS`
uses the **population** standard deviation (`ddof=0`) by construction. That matters the moment
anything cross-checks with pandas, whose default is `ddof=1` — the same series then produces
bands roughly 2.6% wider at N=20, which looks like a plausible difference rather than an obvious
bug.

## Acceptance criteria

- [test: Bollinger bands match a hand-computed 20-period population-stdev golden] Input, mean, stdev and both bands committed, arithmetic checkable by hand
- [test: a sample-stdev implementation fails the golden] Proves the test discriminates between ddof=0 and ddof=1 rather than merely passing
- [test: OBV matches a hand-computed golden over a short series] Including at least one flat close, where the direction rule is ambiguous unless stated
- [test: OBV uses base volume, and the registry records which] Cross-exchange volume is not comparable; the field must be named per venue as source_field already requires
- [test: each golden names its external source and the arithmetic used] Hand-computed counts as external only if the working is recorded
- [cmd: uv run pytest tests/test_bollinger_obv.py -q --no-header -o addopts= --tb=short] Runs on its own

## Notes for the implementer

- Bollinger and OBV are non-recursive, so they do **not** need 250 bars. Give each its own
  honest `required_bars` rather than inheriting the recursive family's number.
- State the flat-close rule for OBV explicitly in the registry note. Conventions differ, and an
  unstated one is exactly how two implementations disagree without either being wrong.
