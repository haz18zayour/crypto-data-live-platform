---
id: US-605
title: Taker buy/sell ratio — fetcher and registry entries for four assets
priority: 5
touches:
  - ingest/fetchers/okx_derivatives.py
  - ingest/schemas.py
  - ingest/registry.yaml
  - tests/test_okx_derivatives_fetcher.py
  - tests/test_registry.py
context:
  - AGENTS.md
  - prds/PRD-006-derivatives/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the taker buy/sell volume ratio fetched and persisted for all four assets,
completing the four metrics this PRD scopes.

## Acceptance criteria

- [test: the fetcher returns the newest ratio and its own timestamp, never a client-computed average] Read exactly what OKX returns
- [test: a malformed or reshaped response is rejected by the response model] `extra="forbid"` on the new `OkxTakerVolumeResponse`
- [test: an HTTP error returns Error with the status code in the detail, and no value] Same discipline as every fetcher in this project
- [test: source_timestamp is strictly in the past] The F11 defence
- [test: the registry carries four taker-ratio entries, one per asset, each declaring uncorroborated] Same reasoning as the other three metrics
- [test: `assert_registry_coverage` passes for all four new entries] Golden, response model, required_bars, parameters
- [test: a run persists one taker-ratio datapoint per asset] End to end for this metric
- [integration: a live OKX request returns a taker buy/sell ratio for all four assets] Hits the real endpoint for each asset
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green

## Notes for the implementer

- Endpoint: OKX's `rubik/stat/taker-volume` (currency-level, per `python-okx`'s constants) —
  confirm whether it returns a ratio directly or separate buy/sell volumes that this fetcher must
  divide. If it is the latter, compute the ratio here rather than persisting two raw volumes as
  one indicator; keep the arithmetic simple and auditable (buy volume / sell volume), and record
  exactly which two fields it was computed from in `source_field`.
- This is the fourth and last new metric in this PRD's scope. If the pattern established by
  US-603/US-604 (fetcher function, response model, four registry entries, persistence) needed
  any adjustment by this point, this story is where that would surface — flag it rather than
  quietly diverging from the established shape.
