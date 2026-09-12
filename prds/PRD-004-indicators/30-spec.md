---
title: Spot OHLCV and technical indicators
branch: feat/prd-004-indicators
assumptions:
  - claim: 250 bars is sufficient for convergence on all recursive indicators here.
    tripwire: Any indicator still moving materially between N=250 and N=500 on the same tail — raise N for that indicator and record the measurement.
    acceptedBy: default
  - claim: BNB has enough Coinbase history for corroboration.
    tripwire: Measured at ~317 daily bars today against a 250 requirement. Any asset below its required_bars at a venue is declared uncorroborated rather than silently computed on short data.
    acceptedBy: default
  - claim: TA-Lib will not silently return unconverged values.
    tripwire: It will — the unstable period defaults to zero and a 30-bar RSI returns a plausible float at index 14. The exactly-N contract is the only thing preventing this.
    acceptedBy: default
---

# Spot OHLCV and technical indicators

## What this delivers

RSI(14), EMA(20/50/200), MACD(12/26/9), StochRSI(14), Bollinger(20,2), ATR(14) and OBV for
BTC, ETH, SOL and BNB — taking the board from **1 cell to ~32**, every one carrying the
provenance, status, freshness and corroboration machinery already built.

## Why (from research)

Three findings changed the shape of this PRD:

1. **Warm-up was understated by ~4×.** Our "50–70 bars" was our own derivation. StockCharts, who
   publish their operational number, use **at least 250** and warn that less "will not replicate
   our RSI numbers".
2. **MACD carries no unstable-period annotation and needs 250 anyway.** Reading TA-Lib's docs
   would set it at 35. The EMA-26 inside it is recursive regardless.
3. **A differential test against pandas-ta-classic is a tautology unless `talib=False` is
   asserted** — it delegates to TA-Lib's C implementation when TA-Lib is installed, which ours
   always will be.

## Approach

TA-Lib 0.7.1 computes; published worked-example vectors are the merge gate; pandas-ta-classic
(test-only, `talib=False` asserted) fills MACD and StochRSI where no publisher tabulates; one
TradingView spot-check is committed as an evidence artifact. See `20-decisions.yaml`.

## Data model changes

Registry only — ~32 entries with `required_bars`, parameters, and measured per-venue history
availability. **No `datapoints` schema change, so not blast-radius.**

## Out of scope

Composites, scores, signals or rankings (permanent); derivatives/on-chain/macro; dashboard
design (PRD-005); any indicator without an external golden; new venues; intraday.

## The adversarial case

**Check a computed indicator against a value produced outside this codebase** — a published
worked example — not against our own output.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-401 | TA-Lib in, with the unstable-period fixture in the same commit | — |
| US-402 | required_bars validated against TA-Lib's own lookback | US-401 |
| US-403 | Historical bars fetched to depth, truncation and gaps still fatal | — |
| US-404 | RSI and ATR pinned to published worked examples | US-401, US-403 |
| US-405 | Bollinger and OBV, population stdev, hand-computed goldens | US-401 |
| US-411 | MACD and StochRSI — registered, oracle-checked, coverage green (replaces US-406/409/410) | US-401 |
| US-407 | The registry carries ~32 entries and coverage still holds | US-404, US-405, US-411 |
| US-408 | Four assets, with per-venue history availability declared | US-407 |
| US-412 | The missing EMA stack, and OBV's meaningless one-bar window | US-407 |
