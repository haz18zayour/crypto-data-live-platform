---
id: US-204
title: Parsing pinned against recorded vendor shapes
priority: 4
touches:
  - tests/fixtures/**
  - tests/test_vendor_shapes.py
context:
  - AGENTS.md
  - prds/PRD-002-harness/10-research.md
---

As the owner, I want our parsing pinned against recorded real responses, so that a change to
*our* code cannot quietly alter how a known payload is interpreted.

**Be precise about what this does and does not prove.** A recording replays forever and is
structurally incapable of noticing that the live vendor changed — that is US-206's job. This
story pins **our side** of the contract: given this exact payload, we still produce this exact
result.

## Acceptance criteria

- [test: a recorded OKX candle payload parses to the expected value and timestamp] The fixture is a real captured response, committed
- [test: the recorded payload includes an unclosed candle and it is excluded] confirm != "1" is dropped, pinned against real data rather than a hand-built ideal
- [test: a fixture whose recorded status is an error produces Error, not Ok] The failure path is pinned too, not only the happy one
- [test: fixtures are loaded from disk, not constructed inline] A test that builds its own payload proves only that the test agrees with itself
- [cmd: uv run pytest tests/test_vendor_shapes.py -q --no-header -o addopts= --tb=short] The suite runs and passes on its own

## Notes for the implementer

- Use `httpx.MockTransport`, already the idiom in `tests/test_okx_fetcher.py`. Do **not** add
  VCR.py or pytest-recording — the research weighed them and they bring tooling this project's
  scale does not need.
- Capture fixtures from a real call once and commit them, with a note of when they were taken.
- Include at least one payload that is deliberately malformed, so the error path has a pinned
  shape as well.
