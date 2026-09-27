---
id: US-803
title: Seven FRED rows registered — VIXCLS, DFF, T10Y2Y, DFII10, DTWEXBGS, CPIAUCSL, M2SL, each with correct release-cadence staleness thresholds
priority: 3
touches:
  - ingest/registry.yaml
  - tests/test_registry.py
context:
  - AGENTS.md
  - prds/PRD-008-macro-flows/20-decisions.yaml
---

As the owner, I want each of the seven confirmed FRED series registered with a staleness
threshold that matches its own real release cadence — daily, weekly, or monthly — so a weekly
series like `DTWEXBGS` does not read `STALE` every single week by design, and a monthly series
like `M2SL` is not held to a daily-freshness bar it was never going to meet.

Research found `DTWEXBGS`'s staleness follows a weekly sawtooth (a fixed "stale after 3 days"
threshold would trip it every week, not on genuine failure) — this story's whole point is
registering each series against its own real cadence, not a one-size-fits-all interval.

## Acceptance criteria

- [test: all seven confirmed series (VIXCLS, DFF, T10Y2Y, DFII10, DTWEXBGS, CPIAUCSL, M2SL) are registered, each using US-802's shared fetcher] The exact G1-confirmed row set, no more, no fewer
- [test: DTWEXBGS's freshness thresholds are sized against its real weekly (H.10) release cadence, not a daily assumption] Directly guards against the sawtooth false-stale case research found
- [test: CPIAUCSL's and M2SL's freshness thresholds are sized against their real monthly release cadences] Same guard, for the two slowest series
- [test: each of the seven entries' uncorroborated note states FRED mirrors the Fed/BLS directly, so a second source would check the mirror against its origin rather than provide genuine independent corroboration] The G1-confirmed corroboration decision, disclosed on the registry entry itself
- [test: `assert_registry_coverage` passes for all seven new entries] Golden, response model, required_bars, parameters
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Do not register SP500, NASDAQCOM, SOFR, or FEDFUNDS — all four were explicitly deferred at G1
  (S&P licensing/history-depth for the first two; near-duplication of DFF for the latter two).
- Same web-test hardcoded-count note as every prior story adding a family to this board.
