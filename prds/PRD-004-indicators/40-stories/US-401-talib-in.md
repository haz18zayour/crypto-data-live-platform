---
id: US-401
title: TA-Lib in, with the unstable-period fixture in the same commit
priority: 1
touches:
  - pyproject.toml
  - uv.lock
  - tests/conftest.py
  - tests/test_talib_environment.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want TA-Lib added together with the guard against its one piece of global
mutable state, so that the determinism this project spent a whole PRD establishing cannot be
undone by the library that arrives to help.

`TA_SetUnstablePeriod` is process-global, "must be initialized from a single thread", and the
setting follows the function everywhere. One test setting it changes every later test in the
same process — reproducing **"same market, different score" inside our own determinism suite**,
especially under random ordering.

## Acceptance criteria

- [cmd: uv sync] TA-Lib 0.7.1 installs from a wheel — no system build step, Python 3.9–3.14 supported
- [test: an autouse fixture asserts the unstable period is at its default for every function] Runs for every test in the suite, not only these
- [test: a test that sets an unstable period fails the suite] The guard is proven to bite, not merely present
- [test: get_unstable_period returns 0 out of the box] Pinning the documented default, so a future TA-Lib change surfaces here
- [cmd: uv run mypy ingest --strict] Strict typing still passes with the new dependency
- [cmd: uv run pytest -q --no-header -o addopts=] The existing 131 tests still pass

## Notes for the implementer

- **The fixture ships in this commit or the story is not done.** It is the single most likely
  way to reproduce the prior system's uptime-dependent values, and adding TA-Lib without it
  leaves a loaded gun in the test suite.
- TA-Lib does **not** strip unconverged leading values — the unstable period defaults to zero,
  so a 30-bar RSI returns a plausible float at index 14 with no NaN band and no exception. Our
  exactly-N contract from US-201 is the only thing preventing that. Do not weaken it.
- No indicators in this story. Dependency and guard only.
