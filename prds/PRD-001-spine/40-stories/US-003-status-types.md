---
id: US-003
title: Status types — make a missing value unrepresentable as a number
priority: 3
touches:
  - ingest/status.py
  - tests/test_status.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want "we have a value" and "we do not have a value" to be different types
rather than different floats, so that a fetcher which never ran cannot produce something
indistinguishable from a real reading of zero.

This is the direct structural fix for the prior system's worst class of failure: funding rate,
open interest and long/short ratio scored a confident `0.0` for months because a fetcher was
never called. Nothing errored, because nothing could.

## Acceptance criteria

- [test: an unavailable result exposes no numeric value] `Unavailable` and `Error` have no `value` attribute at all — reading one is an `AttributeError`, not a zero
- [test: constructing an OK result without a source timestamp is rejected] A value with no provenance in time cannot be built
- [test: a reason is required for unavailable and error results] The reason is one of `NOT_DEFINABLE`, `PAYWALLED`, `FETCH_FAILED`, `NOT_FETCHED` — the three kinds of absence stay distinguishable
- [test: results are immutable once constructed] A value cannot be mutated after the fact
- [cmd: uv run mypy ingest --strict] Strict typing passes, with the union exhaustively handled at every use site

## Notes for the implementer

Model the four outcomes as a discriminated union of frozen dataclasses, not as one class with
optional fields:

```
Ok(value, source_timestamp)  |  Stale(value, source_timestamp)
Unavailable(reason)          |  Error(reason, detail)
```

- `NOT_FETCHED` is the default state of an indicator the pipeline did not attempt. It exists
  specifically so "never ran" and "ran and got nothing" are different rows.
- Do **not** add a convenience accessor like `.value_or(0.0)` or `.as_float()`. Any helper that
  turns absence back into a number reintroduces the exact bug this story removes — if the
  implementer feels the need for one, the call site should be pattern-matching instead.
- No fetcher or database code in this story. Types and their tests only.
