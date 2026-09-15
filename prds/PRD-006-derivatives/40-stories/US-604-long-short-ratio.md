---
id: US-604
title: Long/short account ratio — fetcher and registry entries for four assets
priority: 4
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

As the owner, I want the long/short account ratio fetched and persisted for all four assets, so
that positioning data joins funding and open interest on the board with the same provenance
discipline.

## Acceptance criteria

- [test: the fetcher returns the newest ratio and its own timestamp, never an average across a window it does not report] Read exactly what OKX returns; no client-side smoothing invented
- [test: a malformed or reshaped response is rejected by the response model] `extra="forbid"` on the new `OkxLongShortRatioResponse`
- [test: an HTTP error returns Error with the status code in the detail, and no value] Same discipline as every fetcher in this project
- [test: source_timestamp is strictly in the past] The F11 defence
- [test: the registry carries four long-short-ratio entries, one per asset, each declaring uncorroborated] Same reasoning as US-602 and US-603
- [test: `assert_registry_coverage` passes for all four new entries] Golden, response model, required_bars, parameters
- [test: a run persists one long-short-ratio datapoint per asset] End to end for this metric
- [integration: a live OKX request returns a long/short account ratio for all four assets] Hits the real endpoint for each asset
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green

## Notes for the implementer

- Endpoint: OKX's `rubik/stat` family exposes both an **account-ratio** and a **top-trader
  position-ratio** variant (per `tiagosiebler/okx-api`'s `getLongShortRatio()` and
  `getLongShortContractRatio()`). This story is the **account** ratio, matching the roadmap's
  plain "long/short ratio" and the G1 decision's wording — confirm the exact path against the
  live endpoint (`GET https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio`
  is the reference SDK's constant; verify the parameter it takes — `ccy` at the currency level,
  not `instId` — before writing the request).
- Research flagged this endpoint family's rate limits as **distinct from and unconfirmed
  against** the 20 req/2s figure measured only for `public/funding-rate`. Do not assume the same
  limit applies; a 429 here must surface as `FETCH_FAILED`, never a silent retry that drops the
  row — the exact failure mode research's own blind-spot section warns would look like an
  intermittently missing cell rather than an outage.
- If OKX's history endpoint for this metric has an undocumented retention ceiling (the open G1
  question research could not resolve), that only affects a future backfill story — this story
  only needs the newest value per asset.
