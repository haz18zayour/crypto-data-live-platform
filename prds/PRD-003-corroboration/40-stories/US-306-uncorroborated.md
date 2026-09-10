---
id: US-306
title: Single-source indicators are marked uncorroborated, visibly
priority: 6
touches:
  - ingest/registry.yaml
  - ingest/registry.py
  - tests/test_uncorroborated.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want an indicator with only one possible source to say so, so that "no
disagreement" is never mistaken for "two venues agreed".

An unmarked single-source value and a corroborated one look identical on a page, and the
difference is exactly what this PRD is for.

Coin Metrics MVRV is the sharp case, and it is worse than merely uncorroborated: it is a
**resolved consolidation of many venues whose disagreement has already been discarded by
someone else** — they exclude a market whose VWAP sits more than 3% from the median and publish
no dispersion at all. Calling it "uncorroborated" is correct but understates the situation, and
the registry note should say so.

## Acceptance criteria

- [test: an indicator with no second source is marked uncorroborated in the registry] Explicitly declared, never inferred from absence
- [test: a corroborated and an uncorroborated value are distinguishable in the stored data] Not by the absence of a divergence row, which is ambiguous with a failed comparison
- [test: registry validation rejects an indicator that declares neither a second source nor uncorroborated] Silence is not an option — the same discipline as `definable_for` rejecting a wildcard
- [test: coverage from PRD-002 includes the corroboration declaration] So a new indicator cannot ship without stating which it is
- [cmd: uv run python -m ingest.registry --validate] The shipped registry validates

## Notes for the implementer

- Extend PRD-002's registry-generated coverage rather than adding a second hand-kept list.
- For a vendor that internally consolidates (Coin Metrics), record that fact in the registry
  note. It changes how much a single number should be trusted.
