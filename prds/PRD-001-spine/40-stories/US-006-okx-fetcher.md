---
id: US-006
title: OKX fetcher — BTC daily close, closed candles only
priority: 6
touches:
  - ingest/fetchers/okx.py
  - tests/test_okx_fetcher.py
context:
  - AGENTS.md
  - prds/PRD-001-spine/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the BTC daily close fetched only from candles OKX has marked final, with
every failure mode returning an explicit status, so that a still-forming candle or a failed
request can never be mistaken for a settled price.

Measured on 2026-09-07, OKX returned the newest daily candle with `confirm = "0"` and the two
before it with `"1"`. An indicator computed over that newest candle is wrong in the worst
possible way: it silently corrects itself by the next day.

## Acceptance criteria

- [test: candles with confirm not equal to 1 are excluded] The forming candle is dropped, and the value returned is the most recent **closed** candle
- [test: an empty result after filtering returns Unavailable(FETCH_FAILED), never a zero or a stale value] No candle means no value
- [test: an HTTP error returns Error with the status code in the detail, and no value] The fetcher never raises past its own boundary and never substitutes a default
- [test: source_timestamp is the candle close time and is strictly in the past] A value whose source timestamp lies in the future is rejected — the direct F11 defence
- [test: measured_on equals BTC] The fetcher declares what it actually measured, never what it is being displayed as
- [integration: a live OKX request returns a closed BTC daily candle with a past source timestamp] Hits the real endpoint and asserts confirm handling against real data

## Notes for the implementer

Endpoint: `https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D`.

Response rows are arrays, newest first. Index 0 is the open time in **milliseconds**, index 4
is the close price, and the **last element is `confirm`** — `"0"` forming, `"1"` final. Verified
by measurement; OKX's docs page is JS-rendered and did not confirm the semantics directly, so
the test against live data is what establishes it.

- `source_timestamp` is the candle's **close** time, not its open time. For a 1D bar that is
  open time + 86,400,000 ms. Getting this wrong shifts every value by a day.
- Return the union type from US-003. No bare floats cross this boundary.
- No retries and no fallback venue in this story. A fallback source is a **different
  indicator** — the prior system silently swapped FRED's `DTWEXBGS` for yfinance's `DX-Y.NYB`
  behind one "DXY" label, and the value jumped discontinuously whenever it did.
- Mark the live-network test so it can be deselected offline, but it must run in CI.
