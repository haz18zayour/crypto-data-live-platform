---
title: Derivatives panel — funding, open interest, long/short and taker ratio
branch: feat/prd-006-derivatives
assumptions:
  - claim: OKX's rubik/stat endpoints (OI-volume, long-short-ratio, taker-volume) return
      data cleanly attributable to one margin type, without blending linear and inverse
      contracts under one instType=SWAP aggregate.
    tripwire: Any fetcher finding a rubik/stat response that cannot be cleanly separated
      by margin type reopens this — the coin/USD unit-mixing trap this PRD exists to
      prevent could reappear one layer up, inside an OKX-computed ratio the fetcher never
      gets to inspect or split.
    acceptedBy: default
  - claim: A funding datapoint's interval must be derived fresh from consecutive settled
      fundingTime deltas on every fetch, never read from a static registry field.
    tripwire: Any story that persists an "interval" sourced from the registry rather than
      computed from the fetched history itself. OKX's escalation ladder reverts after a
      12-hour lookback of stable settlements — a value set once at registry-authoring time
      and never re-derived will drift stale silently, looking plausible rather than
      obviously wrong.
    acceptedBy: default
  - claim: Four assets × four metrics on OKX's rubik/stat family will not exceed rate
      limits on the existing GitHub Actions cron cadence.
    tripwire: A 429 response must surface as FETCH_FAILED, never a silent retry that drops
      the row. A throttling failure here looks like an intermittently missing cell —
      exactly what PRD-005's completeness matrix exists to catch, but only if the fetcher
      reports it.
    acceptedBy: default
---

# Derivatives panel — funding, open interest, long/short and taker ratio

## What this delivers

A second data category on the existing completeness matrix: **funding rate (settled,
never live/predicted), open interest, long/short account ratio, and taker buy/sell ratio**,
for BTC/ETH/SOL/BNB perpetual swaps. No new UI — PRD-005's board model already generalizes to
any registry entry; these are new rows in the grid that already exists. Every entry declares
`uncorroborated` per US-306, with the reason recorded once (Approach, below) rather than
repeated per entry.

## Why (from research)

Three findings from `10-research.md` are load-bearing, not background:

1. **A settled funding rate and a live funding-rate field are different things, and this
   board renders only the settled one.** OKX's `public/funding-rate` is the live/predicted
   field this PRD never fetches for display; `public/funding-rate-history` is the realized,
   settled series. Same discipline PRD-004 already applied to OHLCV — closed bars only,
   never the live one.
2. **Funding intervals are not fixed per instrument.** OKX's dynamic settlement ladder
   (8h → 4h → 2h → 1h and back, on a rolling 12-hour lookback of settlements near cap/floor)
   means an instrument's interval can change within weeks, and the settled-history endpoint
   does not return an interval field at all — it must be derived from consecutive
   `fundingTime` deltas in the fetched series itself. A practitioner guide surfaced in
   research, published in 2026, hardcodes "8 hours" as a constant throughout its examples —
   proof this is a live mistake, not a hypothetical one.
3. **Coin-margined and USD-margined open interest use different units.** This board
   standardizes on USDT-margined (linear) perpetuals for all four assets (G1 decision),
   avoiding the mixing trap by construction rather than by validation after the fact.

## Approach

**One new fetcher module, `ingest/fetchers/okx_derivatives.py`**, following `okx.py`'s
existing shape: no API key (all four OKX endpoints used here are public), explicit
`httpx.Client` injection for testing, and the same failure discipline — an HTTP error, a
malformed response, a non-contiguous or out-of-order series, or a source timestamp at or
after the current time are all `Error(reason=FETCH_FAILED)`, never a default or a stale
carry-forward.

Four new response models in `ingest/schemas.py` (`OkxFundingRateHistoryResponse`,
`OkxOpenInterestResponse`, `OkxLongShortRatioResponse`, `OkxTakerVolumeResponse`), each
`extra="forbid"` so an added, renamed, or reshaped field is rejected rather than silently
ignored — the same contract PRD-002 already requires of `OkxCandleResponse`.

**Funding rate's interval is derived, not declared.** The fetcher pulls at least two
consecutive settled entries from `funding-rate-history`, computes the delta between their
`fundingTime` values, and writes the derived interval into that datapoint's `source_field`
as prose (`"OKX funding-rate-history, interval derived as 8h from consecutive fundingTime
deltas"`) — the same place `btc_daily_close` already records its own derivation logic. No
new database column, no registry field: the fact is computed per-fetch and travels with the
row it belongs to, so it cannot go stale between fetches the way a static field would.

**Sixteen new registry entries** (four metrics × four assets), each with `talib_function`
omitted (registry.py already accepts this — `btc_daily_close` has none either) and
`uncorroborated` set, citing the research finding directly: *"No second venue's derivatives
public endpoints were confirmed to exist or be reachable from this compute; Binance's futures
API returns HTTP 451 to US IPs on public endpoints, and Coinbase/Kraken's derivatives surface
was not verified to expose these fields at all."*

**Persistence extends the existing daily run, not a new cron job.** `ingest/pipeline.py`'s
`run_all_assets()`/`persist_board()` pair is TA-Lib-only by construction (filtered on
`definition.talib_function is not None`); derivatives entries have no `talib_function` and
need their own fetch-and-assemble step. A parallel `run_derivatives()` returns the same
per-key `Result` mapping shape `FullAssetRun.indicators` already uses, and `persist_board`
is generalized to accept results from either source rather than duplicated. `heartbeat.py`'s
single `run_pipeline()` call persists both categories in one run, one heartbeat ping, one
failure surface — not a second job that could silently stop reporting on its own.

## Data model changes

**None.** No new column, no migration. The derived funding interval travels in the existing
`source_field text` column as prose, matching precedent. Sixteen new registry entries and one
new fetcher module are additive; `datapoints`, its constraints, and RLS are untouched.

## Out of scope

Restated from `00-brief.md`, confirmed at G1: liquidation data (modeled, not measured, per
research — a modeled estimate does not get to look like a measured value here); options data
(Deribit-only, thin SOL liquidity); basis/term structure; any new panel layout (PRD-005's
board already generalizes); any composite, score, signal, or cross-indicator judgement,
permanently; the live/predicted funding-rate field, ever, for display.

## The adversarial case

**Catch an instrument mid funding-interval-change, or construct the fixture if that can't be
observed live in the build window, and show the recorded interval on that specific datapoint
— not a hardcoded assumption — drives any downstream annualisation.** This is the exact bug
research names as the single most common mistake in this data category: a 2026-published
practitioner guide makes it in print. A fallback adversarial case if the first is impractical
to demonstrate: show a linear (USDT-margined) open-interest value is structurally incapable of
being summed with an inverse (coin-margined) one, because this board never fetches the latter.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-601 | OKX funding-rate-history fetcher — settled series, interval derived from fundingTime deltas | — |
| US-602 | Funding rate registered across BTC/ETH/SOL/BNB, persisted alongside the technical board | US-601 |
| US-603 | Open interest — USDT-margined only, fetcher and registry entries for four assets | US-601 |
| US-604 | Long/short account ratio — fetcher and registry entries for four assets | US-601 |
| US-605 | Taker buy/sell ratio — fetcher and registry entries for four assets | US-601 |
| US-606 | One ingest run persists both boards — pipeline and heartbeat integration | US-602, US-603, US-604, US-605 |
| US-607 | The adversarial case — a funding-interval change drives its own datapoint's derived interval, not a hardcoded assumption | US-606 |
