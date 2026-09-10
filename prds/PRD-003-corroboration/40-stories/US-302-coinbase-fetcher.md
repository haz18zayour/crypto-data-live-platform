---
id: US-302
title: Coinbase fetcher — fields by name, UTC alignment asserted per venue
priority: 2
touches:
  - ingest/fetchers/coinbase.py
  - ingest/schemas.py
  - ingest/registry.yaml
  - tests/test_coinbase_fetcher.py
context:
  - AGENTS.md
  - prds/PRD-003-corroboration/10-research.md
---

As the owner, I want the second venue read by named fields with its own UTC assertion, so that
the mistake that created this PRD cannot simply repeat at the new source.

Two traps, both documented in `10-research.md`:

**Field order agrees by luck.** OKX is `[ts, open, high, low, close, …]`; Coinbase is
`[time, low, high, open, close, volume]` — **low and high before open**; Kraken is
`[ts, open, high, low, close, …]`. Close lands at index 4 on all three, so a naive port works
today and silently swaps high and low the moment someone generalises it.

**Coinbase documents nothing about 86400 bucket alignment.** This project exists because an
undocumented alignment was assumed once. The 59-day measurement tracking OKX 1Dutc is evidence,
not proof.

## Acceptance criteria

- [test: the fetcher reads close by its named field, not a shared array index] Named per venue in the registry, as `source_field` already requires
- [test: the daily source_timestamp falls on a UTC midnight boundary] Asserted for Coinbase independently — not inherited from OKX's assertion
- [test: the response model rejects an added field, a renamed field and a type change] PRD-002's `extra='forbid'` and strict typing applied to the new venue
- [test: a fetch failure returns Error with FETCH_FAILED, never Ok] The status union from PRD-001 crosses this boundary too
- [test: bucket convention matches OKX's stored convention] OKX converts bucket-start to bucket-END (`okx.py:84-85`); Coinbase returns bucket-start. A mismatch would misalign by a full day on every run
- [integration: a live Coinbase request returns a closed BTC daily candle on a UTC boundary] Hits the real endpoint

## Notes for the implementer

- Endpoint: `https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400`.
- Coinbase's array is `[time, low, high, open, close, volume]` — verify against the response,
  do not copy OKX's indices.
- Coinbase has **no** closed-candle flag and **no** documented positional rule (Kraken has the
  latter, OKX has the former). Closure must be inferred from the bucket time against a trusted
  clock, and that inference deserves its own test.
- Reuse PRD-002's harness: strict model, recorded fixture, truncation and contiguity checks.
