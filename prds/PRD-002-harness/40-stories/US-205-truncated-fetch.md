---
id: US-205
title: A truncated fetch is an error, never a shorter series
priority: 5
touches:
  - ingest/fetchers/okx.py
  - tests/test_truncation.py
context:
  - AGENTS.md
  - prds/PRD-002-harness/10-research.md
---

As the owner, I want a fetch that returns fewer bars than asked for to fail loudly, so that an
indicator is never computed over an incomplete window that looks structurally fine.

This is the hazard `ai-hedge-fund` taught us via its `test_mid_walk_*` cases, and it has a
shipped instance on our own venue: **ccxt** on OKX, where callers requesting 300 candles
*"silently receive fewer candles than requested — specifically 100 history candles instead of
300 live candles — without obvious notification."* Nothing errors. The series is shorter, valid,
and wrong.

The industry's usual answer is worse. **Freqtrade's "Missing data fillup" synthesises candles
across gaps**, logging lines like `Missing data fillup for BCH/USDT, 15m: before: 39 - after:
124 - 217.95%` — a series that arrived 68% incomplete becomes structurally valid and silently
usable. That is this guarantee inverted: repair instead of error.

## Acceptance criteria

- [test: a response with fewer bars than requested returns Error, not a short series] The count is checked against what was asked for, before any value is built
- [test: a gap in the bar sequence returns Error] Timestamps must be contiguous at the expected interval; a hole is a failure, not something to interpolate
- [test: bars are strictly ordered and non-duplicated] A repeated or out-of-order timestamp is an error
- [test: no code path synthesises, pads or interpolates a bar] Asserted directly — the fetcher never invents data to reach a count
- [test: the error detail names how many bars arrived versus how many were expected] So the 2am diagnosis is immediate

## Notes for the implementer

- Check the count **and** contiguity. ccxt's bug produced the right *shape* with the wrong
  *span*, so a length check alone is not enough.
- The expected interval comes from the registry's `expected_update_interval_seconds`.
- No retry loop here. A retry masks an intermittent truncation, and the question is categorical.
- This composes with US-201: a truncated fetch cannot satisfy `required_bars` either, so the
  two defences are independent and both should hold.
