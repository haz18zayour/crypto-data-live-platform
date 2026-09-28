---
id: US-904
title: OKX backfill recipes — candles (deep, TA-Lib reseeded), funding (shallow, honestly bounded), open-interest history (separate endpoint), long/short and taker volume at 1D
priority: 4
touches:
  - ingest/backfill.py
  - ingest/fetchers/okx.py
  - ingest/fetchers/okx_derivatives.py
  - tests/test_backfill_okx.py
context:
  - AGENTS.md
  - prds/PRD-009-history-charts/10-research.md
  - prds/PRD-009-history-charts/20-decisions.yaml
---

As the owner, I want OKX-sourced indicators (spot close and every TA-Lib technical indicator,
funding rate, open interest, long/short ratio, taker volume) to backfill with each endpoint's own
real depth honestly represented, so a viewer never sees a sparkline that implies more or less
history exists than the vendor actually provides.

Research measured each endpoint live: candles go back years; funding history is only ~3 months;
open interest's history lives on a genuinely different endpoint from the live snapshot.

## Acceptance criteria

- [test: candle backfill recomputes every TA-Lib technical indicator (RSI, EMA stack, MACD, StochRSI, Bollinger, ATR, OBV) from backfilled candles using a seed window sized to several multiples of that indicator's own warm-up period, not just the plotted window] Correct warm-up handling for historical, not just live, computation
- [test: a backfilled technical-indicator value at a given historical bar matches the value PRD-002's existing golden-file fixtures would produce for that same bar and history depth] Live-verified per the assumption in 30-spec.md — this is the actual risk, not an assumption to leave untested
- [test: funding-rate backfill persists only as far back as the vendor's own history-endpoint actually returns, and the persisted history's earliest point's date is confirmed against a fresh, direct read of that same endpoint] Never implies deeper history than the vendor has
- [test: open-interest backfill reads from open-interest-history (not public/open-interest), and its persisted rows carry an endpoint/source_field distinct from the live snapshot's] A viewer (and the verifier) can always tell which endpoint wrote which row
- [test: long/short ratio and taker-volume backfill use period=1D; the resulting sparkline's live 5-minute points and backfilled daily points render on a real time axis without resampling, so the density change is visible] Matches the G1 decision against hiding the backfill/live seam
- [integration: a live OKX backfill run for one real asset returns real historical values, cross-checked against a fresh independent OKX API call for a date within the returned range] Real data, not fixtures
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Depends on US-903's shared backfill entry point and coverage test.
- OKX's daily candle buckets are UTC+8-aligned (`bar=1D`) unless the UTC-aligned `bar=1Dutc`
  parameter is used — confirm live which bar parameter the existing live fetcher already uses
  (`ingest/fetchers/okx.py`) and match it exactly for backfill, so live and backfilled points sit
  on the same time boundary.
- Do not resample or smooth the fast-tier (5-minute) live points to match the daily backfill
  cadence — the G1 decision is explicit that the density change must stay visible.
