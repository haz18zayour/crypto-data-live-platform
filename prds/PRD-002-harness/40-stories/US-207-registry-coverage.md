---
id: US-207
title: Integrity coverage generated from the registry
priority: 7
touches:
  - tests/test_coverage.py
  - ingest/registry.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the test suite to derive what it checks from the indicator registry, so
that adding an indicator without covering it is a build error rather than an oversight.

The prior system's `_assess_data_quality` validated **exactly two hardcoded rows** —
`funding_rate/BTC` and `btc_mvrv/BTC` — while runs reported `clean` and indicators sat silently
at zero. `spx_correlation` was simply absent from `_INDICATOR_HISTORY_COLUMNS`. Coverage was a
hand-maintained list, and it drifted from reality without anyone noticing.

## Acceptance criteria

- [test: every registry entry has a golden file] An indicator with no golden fails the suite, naming the key
- [test: every registry entry has a required_bars declaration] Enforced through the same generated coverage, not a second hand-kept list
- [test: every registered vendor has a response model] A vendor with no model fails, naming it
- [test: adding an unregistered indicator to the registry fails coverage until it is covered] Proven by adding one in the test and asserting the failure, so the mechanism is demonstrated rather than asserted
- [integration: the assembled coverage check runs over the real registry and passes] Drives the real registry file, not a fixture
- [cmd: uv run pytest tests/test_coverage.py -q --no-header -o addopts= --tb=short] The coverage suite runs and passes on its own

## Notes for the implementer

- Coverage is **derived**, never enumerated. If the test file contains a literal list of
  indicator keys, the story has not been done.
- The failure message must name what is missing and for which key — a bare assertion failure
  costs the reader the diagnosis.
- This is the story that makes the other six self-maintaining as PRD-004 onward add indicators.
