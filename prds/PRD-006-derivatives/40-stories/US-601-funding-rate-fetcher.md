---
id: US-601
title: OKX funding-rate-history fetcher — settled series, interval derived from fundingTime deltas
priority: 1
touches:
  - ingest/fetchers/okx_derivatives.py
  - ingest/schemas.py
  - tests/test_okx_derivatives_fetcher.py
context:
  - AGENTS.md
  - prds/PRD-006-derivatives/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want BTC's settled funding rate fetched with its interval derived from the
actual settlement history, so that annualising it later can never assume a cadence the
instrument doesn't currently have.

Research (`10-research.md`) is explicit about why this is the hard part of this PRD: OKX's
`public/funding-rate-history` endpoint returns the realized, settled rate per period — but
**no interval field**. The interval must be derived from the gap between consecutive settled
`fundingTime` values in the response itself. A practitioner guide published in 2026 and
surfaced in this project's own research hardcodes "8 hours" as a constant throughout its
examples — proof this is a live mistake being made in print, not a hypothetical one. OKX's
own settlement ladder (8h → 4h → 2h → 1h, and back, on a rolling 12-hour lookback near a
rate's cap or floor) means a single instrument can genuinely show more than one interval
within weeks.

This story fetches BTC only, proves the interval-derivation logic against real data, and
establishes the response contract the other three metrics' stories will reuse the pattern of.
Registering all four assets is US-602.

## Acceptance criteria

- [test: the fetcher returns the newest settled funding rate, never the live/predicted field] `public/funding-rate` is never called by this fetcher — only `public/funding-rate-history`
- [test: the interval is computed from the delta between the two newest settled fundingTime values, in seconds] Never a hardcoded 8h/28800s constant anywhere in the computation path
- [test: the derived interval is recorded in the returned result's source-field text, distinct from the static registry source_field] So a later change in this instrument's actual cadence is visible on the datapoint that measured it, not hidden behind a static description
- [test: fewer than two settled entries in the response is Error(FETCH_FAILED)] An interval cannot be derived from a single point, and a single point silently treated as "no interval / assume default" is exactly the bug this story exists to prevent
- [test: an HTTP error returns Error with the status code in the detail, and no value] Same discipline as `okx.py` — the fetcher never raises past its own boundary
- [test: a malformed or reshaped response is rejected by the response model] `extra="forbid"` on the new `OkxFundingRateHistoryResponse` — an added, renamed, or retyped field fails loud, not silently ignored
- [test: source_timestamp is the newest settlement's fundingTime and is strictly in the past] The direct F11 defence, same rule as every other fetcher in this project
- [integration: a live OKX request returns settled funding history for BTC-USDT-SWAP and the derived interval matches the actual gap between the two newest entries] Hits the real endpoint; this is what actually pins field names and shape, since research could not independently re-verify OKX's rubik/stat-adjacent docs page field-level detail
- [cmd: uv run mypy ingest --strict] Strict typing holds for the new module

## Notes for the implementer

- Endpoint: `GET https://www.okx.com/api/v5/public/funding-rate-history` with `instId=BTC-USDT-SWAP`
  (USDT-margined per the G1 decision). This is a **public, no-auth** endpoint per every source
  surveyed in research.
- **Verify the exact response field names against the live endpoint before writing the response
  model.** Research confirms the endpoint exists and confirms its general behavior (settled,
  paginated, capped at 400 records total per the practitioner guide cited in research) but could
  not independently re-verify every field name from OKX's own JS-rendered docs page — the same
  situation `okx.py`'s `confirm` field was in, resolved the same way: the live-integration test
  is what actually establishes the contract, not this story's prose.
- Pagination is `before`/`after` on `fundingTime`; research flags this as "brittle for
  multi-symbol sweeps" for a *different* story (US-602's four-asset registration) — this story
  only needs enough records to prove interval derivation, not a full backfill.
- Mirror `okx.py`'s structure: explicit `httpx.Client` injection, `Result` return type from
  `ingest/status.py`, no bare floats or dicts crossing the function boundary.
- Mark the live-network test so it can be deselected offline, but it must run in CI, matching
  every other venue-hitting test in this project.
