---
id: US-407
title: The registry carries ~32 entries and coverage still holds
priority: 7
touches:
  - ingest/registry.yaml
  - ingest/registry.py
  - tests/test_coverage.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the registry to grow from one entry to roughly thirty-two with the
generated coverage still meaningful, because a check that becomes noise at scale is a check
that will be ignored.

The prior system's integrity check validated **exactly two hardcoded rows** while reporting
`clean`. PRD-002 replaced that with coverage derived from the registry — and this is the story
that finds out whether derivation actually holds when the registry is thirty times larger.

## Acceptance criteria

- [test: every registry entry has a golden, a required_bars and a response model] The PRD-002 rule, now over ~32 entries rather than one
- [test: adding an uncovered indicator fails coverage, naming the key and what is missing] The mechanism demonstrated at scale, not asserted
- [test: no indicator key is duplicated across assets] Thirty-two entries is where a copy-paste collision first becomes likely
- [test: every indicator declares its parameters explicitly] RSI(14) and RSI(21) are different indicators; neither may rely on a library default
- [test: coverage failure messages name the specific key] A bare assertion failure over 32 entries costs the reader the diagnosis
- [integration: the assembled coverage check runs over the real registry and passes] The real file, not a fixture
- [cmd: uv run python -m ingest.registry --validate] The shipped registry validates

## Notes for the implementer

- Coverage stays **derived**. If the test file contains a literal list of indicator keys, the
  story has not been done.
- Registry entries will repeat structure across four assets. Repetition is acceptable;
  a generator that hides which assets an indicator is actually declared for is not — the point
  of `definable_for` is that it is read, not computed.
