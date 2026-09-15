---
id: US-701
title: Coin Metrics fetcher — MVRV, BTC only, rate-limit handling proven against real data
priority: 1
touches:
  - ingest/fetchers/coinmetrics.py
  - ingest/schemas.py
  - tests/test_coinmetrics_fetcher.py
context:
  - AGENTS.md
  - prds/PRD-007-onchain/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want BTC's MVRV fetched from Coin Metrics' free Community API with its rate
limit respected, so that this project's first non-OKX vendor integration establishes the
pattern correctly before four more registry entries build on it.

Coin Metrics' Community tier needs no API key and returns simple, string-typed JSON —
`{"data": [{"asset": "btc", "time": "...", "CapMVRVCur": "..."}]}` — but is rate-limited to
roughly 10 requests per 6-second sliding window **per IP**, not per key. A naive concurrent
batch at the start of a scheduled run will 429; a naive sequential one with no backoff will
429 anyway once the on-chain panel's full metric set is registered. This story proves the
client respects that limit against the real endpoint before any other story reuses it.

## Acceptance criteria

- [test: the fetcher calls `/v4/timeseries/asset-metrics` with `assets=btc&metrics=CapMVRVCur`, no API key header or query param present] Community tier is genuinely key-free; sending one anyway would be a silent, undocumented assumption
- [test: a `bad_parameter` error response returns Error(FETCH_FAILED) with the message in the detail, never a value] The fetcher never interprets an error body as data
- [test: a `forbidden` error response (a credential-gated metric) returns Unavailable(PAYWALLED), distinct from FETCH_FAILED] Coin Metrics' own vocabulary for "exists, we lack credentials" maps directly onto this project's `PAYWALLED` reason — proven against the real `CapRealUSD` endpoint, which is confirmed forbidden on the free tier
- [test: a malformed or reshaped response is rejected by the response model] `extra="forbid"` on the new `CoinMetricsAssetMetricsResponse` — an added, renamed, or retyped field fails loud
- [test: consecutive requests within one run are serialized with backoff sufficient to stay under ~1.6 req/s] A burst of calls at run start must not 429 the whole batch; prove it with more than one call in the same test, not a single request that happens to succeed once
- [test: an HTTP error returns Error with the status code in the detail, and no value] Same discipline as every fetcher in this project
- [test: source_timestamp is the response's own `time` field and is strictly in the past] The F11 defence
- [integration: a live request returns BTC's current MVRV] Hits the real endpoint; this is what actually pins the response shape, since Coin Metrics' full field vocabulary was not exhaustively catalogued in research
- [cmd: uv run mypy ingest --strict] Strict typing holds for the new module

## Notes for the implementer

- Endpoint: `GET https://community-api.coinmetrics.io/v4/timeseries/asset-metrics` with
  `assets=btc`, `metrics=CapMVRVCur`, `limit_per_asset=1`, `page_size=1`. Verified live during
  this PRD's G1 gate (2026-09-15): `{"data":[{"asset":"btc","time":"2026-09-14T00:00:00...Z",
  "CapMVRVCur":"1.4708..."}]}` — every field is a string, including the numeric metric value;
  parse accordingly.
- `time` is an RFC3339 timestamp with nanosecond precision (`...000000000Z`) — Python's
  `datetime.fromisoformat` does not accept nanosecond fractions directly; strip or truncate to
  microseconds before parsing, and verify against the live response rather than assuming.
- Rate-limit backoff: research confirms ~10 requests / 6-second window per IP
  (`coinmetrics.readthedocs.io/en/latest/community.html`). A simple fixed delay between calls
  (comfortably under the limit, e.g. 1 request per second) is sufficient for this project's daily
  batch scale — no adaptive/exponential backoff is required, but a 429 must still be handled as
  `Error(FETCH_FAILED)`, never silently retried into a dropped row.
- Mirror `okx.py`'s structure: explicit `httpx.Client` injection, `Result` return type from
  `ingest/status.py`, no bare dicts or floats crossing the function boundary.
- Mark the live-network test so it can be deselected offline, but it must run in CI, matching
  every other venue-hitting test in this project.
